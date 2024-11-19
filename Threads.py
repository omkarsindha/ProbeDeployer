import threading
from typing import Dict,List
from Widgets import Device
import os
import requests
import json
import paramiko
from scp import SCPClient
import time
import Config

class DeployProbesThread(threading.Thread):
    def __init__(self, insite_ip, device_types: Dict[str, List[Device]]):
        super().__init__()
        self.device_types = device_types
        self.insite_ip = insite_ip
        self.total_devices = 0
        self.successful_devices = 0
        self.completed_device = 0
        self.current_device = ""
        self.status = ""
        current_date_time = time.strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = open(f"logs/log-{current_date_time}.txt", "w")

        self.end_event = threading.Event()
        self.start()

    def log(self, message, status=True):
        self.log_file.write(f"{message}\n")
        self.log_file.flush()
        print(message)
        if status:
            self.status = message

    def run(self):
        base_url = f"https://{self.insite_ip}"
        local_path = "probe_package.tar"
        for device_type, devices in self.device_types.items():
            for device in devices:
                self.current_device = device.alias
                self.log("-----------------------------", False)
                self.log(f"Alais - {self.current_device} Control IP - {device.control_ip}")
                if not device.deploy:
                    self.log("Device not selected for deployment. Skipping Device")
                    continue

                remote_temp_path = f"/home/{device.username}/{local_path}"
                remote_final_path = f'/opt/evertz/insite/probe/{local_path}'
                # Download the file
                if self.download_file(device.type, base_url, local_path):
                    self.log("Probe package downloaded successfully.")
                    # SCP the file to the device
                    if self.scp_file(local_path, remote_temp_path, device.control_ip, 22, device.username, device.password):
                        self.log("Probe package SCP to device successful.")
                        # SSH and run commands on the device
                        if self.ssh_and_run_commands(device.control_ip, 22, device.username, device.password, remote_temp_path, remote_final_path, local_path):
                            self.log("Probe deployed successfully,")
                            self.successful_devices += 1
                self.completed_device += 1
                # Delete the local file
                if os.path.exists(local_path):
                    self.status = "Deleting locally downloaded probe package."
                    os.remove(local_path)
        self.end_event.set()
        self.log_file.close()

    def download_file(self, probe_type:str, base_url, local_path):
        url = f"{base_url}/api/-/model/probes?static-asset=true"
        headers = {
            "Content-Type": "application/json"
        }
        payload =  Config.PROBE_TYPE[probe_type]
        self.status = "Requesting probe package path."
        response = requests.post(url, headers=headers, data=json.dumps(payload), verify=False)
        if response.status_code == 200:
            response_data = response.json()
            path = response_data.get('path')

            if path:
                self.log("Path retrieved successfully.")
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
                            self.log("File downloaded successfully")
                            return True
                    else:
                        msg = f"Failed to download file. Status code: {download_response.status_code}"
                        self.log(msg)
                        return False
        else:
            msg = f"Failed to get download path. Status code: {response.status_code}"
            self.log(msg)
            return False

    def scp_file(self, local_path, remote_temp_path, ssh_host, ssh_port, ssh_username, ssh_password):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh.connect(ssh_host, port=ssh_port, username=ssh_username, password=ssh_password)
            self.log("SCP Started.")

            def progress(filename, size, sent):
                if isinstance(filename, bytes):
                    filename = filename.decode('utf-8')
                sent_mb = sent / (1024 * 1024)
                size_mb = size / (1024 * 1024)
                progress_percentage = (sent / size) * 100
                self.status = f"Transferring {filename} to device: {sent_mb:.2f}/{size_mb:.2f} MB ({progress_percentage:.2f}%)"

            with SCPClient(ssh.get_transport(), progress=progress) as scp:
                scp.put(local_path, remote_temp_path)
            return True
        except Exception as e:
            self.log(f"SCP failed: {str(e)}")
            return False
        finally:
            ssh.close()

    def ssh_and_run_commands(self, host, port, username, password, remote_temp_path, remote_final_path, file_name) -> bool:
        try:
            transport = paramiko.Transport((host, port))
            transport.start_client()
        except paramiko.SSHException as err:
            self.log(f"SSH Failed: {str(err)}")
            return False

        try:
            transport.auth_password(username=username, password=password)
        except paramiko.SSHException as err:
            self.log(f"SSH failed: {str(err)}")
            return False

        if not transport.is_authenticated():
            self.log(f"SSH authorization failed.")
            return False

        self.status = "Running commands to install Probe onto device."
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
        commands = [
            'mkdir -p /opt/evertz/insite/probe',
            f'mv {remote_temp_path} {remote_final_path}',
            'cd /opt/evertz/insite/probe',
            f'sudo tar -xvf {file_name}',
            'cd /opt/evertz/insite/probe/insite-probe/setup',
            'chmod +x ./install',
            'rm -f user_consent.json',  # So that the script asks for consent even if Consent has already been given
            'rm -rf /bin/insite-probe',
            'echo -e "1\nyes" | ./install'
        ]

        for command in commands:
            channel.send(command + '\n')
            out = read_until(channel, b'#', 5)
            print(f"Command: {command}")
            print(f"Output: {out}")
            time.sleep(0.5)

        # Check the status of the insite-probe service
        channel.send('systemctl status insite-probe\n')
        output = read_until(channel, b'#', 5)
        print(output)

        if 'active (running)' not in output:
            channel.send('systemctl start insite-probe\n')
            output = read_until(channel, b'#', 5)
            print(output)

            time.sleep(0.5)
            channel.send('systemctl status insite-probe\n')
            output = read_until(channel, b'#', 5)
            print(output)

        transport.close()
        return True


