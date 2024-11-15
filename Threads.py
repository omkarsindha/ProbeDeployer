import threading
from typing import Dict,List
from Widgets import Device
import os
import requests
import json
import paramiko
from scp import SCPClient
import time


class DeployProbesThread(threading.Thread):
    def __init__(self, device_types: Dict[str, List[Device]]):
        super().__init__()
        self.device_types = device_types

        self.total_devices = 0
        self.completed_device = 0
        self.current_device = ""
        self.status = "" # Will hold the status for current task

        self.end_event = threading.Event()
        self.start()

    def run(self):
        base_url = "https://172.17.223.4"
        local_path = "probe_package.tar"
        for device_type, devices in self.device_types.items():
            for device in devices:
                if not device.deploy:
                    continue

                self.current_device = device.alias

                print(f"Processing device: {device}")
                remote_temp_path = f"/home/{device.username}/{local_path}"
                remote_final_path = f'/opt/evertz/insite/probe/{local_path}'
                # Download the file
                if self.download_file(base_url, local_path):
                    # SCP the file to the device
                    if self.scp_file(local_path, remote_temp_path, device.control_ip, 22, device.username, device.password):
                        # SSH and run commands on the device
                        self.ssh_and_run_commands(device.control_ip, 22, device.username, device.password, remote_temp_path, remote_final_path)
                self.completed_device += 1
                # Delete the local file
                if os.path.exists(local_path):
                    self.status = "Deleting locally downloaded Probe package"
                    os.remove(local_path)

    def download_file(self, base_url, local_path):
        url = f"{base_url}/api/-/model/probes?static-asset=true"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "type": "ubuntu",
            "os": {
                "family": "linux",
                "architecture": "amd64"
            },
            "bits": 64,
            "archive-type": "TAR",
            "port": 22222,
            "beats": {
                "filebeat": True,
                "metricbeat": True
            }
        }
        self.status = "Requesting Probe Package Path"
        response = requests.post(url, headers=headers, data=json.dumps(payload), verify=False)
        if response.status_code == 200:
            response_data = response.json()
            path = response_data.get('path')

            if path:
                download_url = f"{base_url}/probe/download/{path}"

                # To get content length
                response = requests.head(download_url, verify=False)
                total_size = int(response.headers.get('content-length', 0))

                # Stream the download and show progress bar
                with requests.get(download_url, stream=True, verify=False) as download_response:
                    if download_response.status_code == 200:
                        with open(local_path, "wb") as file:
                            downloaded_size = 0
                            for chunk in download_response.iter_content(chunk_size=1024):
                                if chunk:
                                    file.write(chunk)
                                    downloaded_size += len(chunk)
                                    progress = (downloaded_size / total_size) * 100
                                    downloaded_mb = downloaded_size / (1024 * 1024)
                                    total_mb = total_size / (1024 * 1024)
                                    self.status = f"Downloading Probe Package: {downloaded_mb:.2f}/{total_mb:.2f} MB ({progress:.2f}%)"
                            self.status = "\nFile downloaded successfully."
                            return True
                    else:
                        self.status = f"Failed to download file. Status code: {download_response.status_code}"
                        return False
        else:
            self.status = f"Failed to get download path. Status code: {response.status_code}"
            return False

    def scp_file(self, local_path, remote_temp_path, ssh_host, ssh_port, ssh_username, ssh_password):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh.connect(ssh_host, port=ssh_port, username=ssh_username, password=ssh_password)
            print("Now SCP the file to device")

            def progress(filename, size, sent):
                sent_mb = sent / (1024 * 1024)
                size_mb = size / (1024 * 1024)
                progress_percentage = (sent / size) * 100
                self.status = f"Transferring {filename} to device: {sent_mb:.2f}/{size_mb:.2f} MB ({progress_percentage:.2f}%)"
                print(self.status, end="\r")

            with SCPClient(ssh.get_transport(), progress=progress) as scp:
                scp.put(local_path, remote_temp_path)

            print("\nSCP Complete")
            return True
        finally:
            ssh.close()

    def ssh_and_run_commands(self, host, port, username, password, remote_temp_path, remote_final_path) -> bool:
        try:
            transport = paramiko.Transport((host, port))
            transport.start_client()
        except paramiko.SSHException as err:
            print(str(err))
            return False

        try:
            transport.auth_password(username=username, password=password)
        except paramiko.SSHException as err:
            print(str(err))
            return False

        if not transport.is_authenticated():
            print("Authentication failed.")
            return False

        channel = transport.open_session()
        channel.get_pty(term='vt100', width=300, height=24)
        channel.invoke_shell()

        def read_until(channel, expected, timeout=None):
            """Read the given channel until the expected text shows up or the timeout
               (in seconds) expires. If timeout is None, it will wait forever. If
               expected is None it will simply read for the given timeout."""
            start = time.time()
            reply = bytearray()
            while channel.recv_ready() or channel.exit_status_ready() is False:
                if channel.recv_ready():
                    reply.extend(channel.recv(8192))
                    # Is our expected response in the reply?
                    pos = reply.find(expected) if expected else -1
                    if pos > -1:
                        break
                else:
                    time.sleep(0.1)
                elapsed = abs(time.time() - start)
                if timeout and elapsed > timeout:
                    break
            return reply.decode('utf-8')

        channel.send('sudo -s\n')
        read_until(channel, b'[sudo] password for', 5)
        channel.send(password + '\n')
        read_until(channel, b'#', 5)

        # Now you are in a root shell, you can run commands as root
        channel.send('mkdir -p /opt/evertz/insite/probe\n')
        read_until(channel, b'#', 5)

        #channel.send(f'mv {remote_temp_path} {remote_final_path}\n')
        #read_until(channel, b'#', 5)

        commands = [
            'cd /opt/evertz/insite/probe',
            'sudo tar -xvf probe_package.tar',
            'cd /opt/evertz/insite/probe/insite-probe/setup',
            'chmod +x ./install',
            'echo "yes" | echo "1" | ./install'
        ]

        for command in commands:
            print(f"Command: {command}")
            channel.send(command + '\n')
            out = read_until(channel, b'#', 5)
            print(f"Output: {out}")

        # Check the status of the insite-probe service
        channel.send('systemctl status insite-probe\n')
        output = read_until(channel, b'#', 5)
        print(output)

        if 'active (running)' not in output:
            channel.send('systemctl start insite-probe\n')
            read_until(channel, b'#', 5)
            print('Probe started.')

        channel.send('systemctl status insite-probe\n')
        output = read_until(channel, b'#', 5)
        print(output)
        return True
        transport.close()

