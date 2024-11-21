import sys
import requests
import json
import paramiko
from scp import SCPClient
import os
import time


def download_file(base_url, payload, local_path):
    url = f"{base_url}/api/-/model/probes?static-asset=true"
    headers = {
        "Content-Type": "application/json"
    }

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
                                # End="" so that it stays on same line \r to rewrite on the same line
                                print(f"\rDownloading: {downloaded_size}/{total_size} bytes ({progress:.2f}%)", end="")
                    print("\nFile downloaded successfully.")
                else:
                    print(f"Failed to download file. Status code: {download_response.status_code}")
                    exit(1)
    else:
        print(f"Failed to get download path. Status code: {response.status_code}")
        exit(1)

def scp_file(local_path, remote_temp_path, ssh_host, ssh_port, ssh_username, ssh_password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(ssh_host, port=ssh_port, username=ssh_username, password=ssh_password)
        print("Now SCP the file to device")

        def progress(filename, size, sent):
            progress_percentage = (sent / size) * 100
            print(f"\rTransferring {filename}: {sent}/{size} bytes ({progress_percentage:.2f}%)", end="")

        with SCPClient(ssh.get_transport(), progress=progress) as scp:
            scp.put(local_path, remote_temp_path)

        print("\nSCP Complete")
    finally:
        ssh.close()

def ssh_and_run_commands(host, port, username, password):
    try:
        transport = paramiko.Transport((host, port))
        transport.start_client()
    except paramiko.SSHException as err:
        print(str(err))
        sys.exit()

    try:
        transport.auth_password(username=username, password=password)
    except paramiko.SSHException as err:
        print(str(err))
        sys.exit()

    if not transport.is_authenticated():
        print("Authentication failed.")
        sys.exit()

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

    transport.close()

# Usage
base_url = "https://172.17.223.4"
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
local_path = "probe_files/centos.tar"
#download_file(base_url, payload, local_path)

host = '172.17.235.12'
port = 22
username = 'evertz'
password = 'evertz'
remote_temp_path = '/home/evertz/probe_package.tar'
scp_file(local_path, remote_temp_path, host, port, username, password)

remote_final_path = '/opt/evertz/insite/probe/probe_package.tar'
#ssh_and_run_commands(host, port, username, password, remote_temp_path, remote_final_path)

#os.remove(local_path)
