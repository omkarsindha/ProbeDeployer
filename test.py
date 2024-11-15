import requests
import json
import paramiko
from scp import SCPClient
import os
import time


base_url = "https://172.17.223.4"

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

response = requests.post(url, headers=headers, data=json.dumps(payload), verify=False)

if response.status_code == 200:
    response_data = response.json()
    path = response_data.get('path')

    if path:
        download_url = f"{base_url}/probe/download/{path}"

        # TO get content length
        response = requests.head(download_url, verify=False)
        total_size = int(response.headers.get('content-length', 0))

        # Stream the download and show progress bar
        with requests.get(download_url, stream=True, verify=False) as download_response:
            if download_response.status_code == 200:
                local_path = "probe_package.tar"
                with open(local_path, "wb") as file:
                    downloaded_size = 0
                    for chunk in download_response.iter_content(chunk_size=1024):
                        print(type(chunk))
                        if chunk:
                            file.write(chunk)
                            downloaded_size += len(chunk)
                            progress = (downloaded_size / total_size) * 100
                            # End="" so that it stays on same line \r to rewrite on the same line
                            print(f"\rDownloading: {downloaded_size}/{total_size} bytes ({progress:.2f}%)", end="")
                print("File downloaded successfully.")
            else:
                print(f"Failed to download file. Status code: {download_response.status_code}")
                exit(1)

            remote_temp_path = f'/home/evertz/downloaded_file.tar'
            remote_final_path = '/opt/evertz/insite/probe/downloaded_file.tar'

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                ssh.connect('172.17.235.12', port=22, username='evertz', password='evertz')
                print("Now SCP the file to device")

                def progress(filename, size, sent):
                    progress_percentage = (sent / size) * 100
                    print(f"\rTransferring {filename}: {sent}/{size} bytes ({progress_percentage:.2f}%)", end="")

                with SCPClient(ssh.get_transport(), progress=progress) as scp:
                    scp.put(local_path, remote_temp_path)

                print("SCP Complete")

                shell = ssh.invoke_shell()
                def send_command(command, prompt='#', buffer_size=10000, timeout=0.1):
                    shell.send(command + '\n')
                    output = ""
                    while not shell.recv_ready():
                        time.sleep(timeout)
                    while shell.recv_ready():
                        output += shell.recv(buffer_size).decode()
                        time.sleep(timeout)
                    while not output.strip().endswith(prompt):
                        time.sleep(timeout)
                        if shell.recv_ready():
                            output += shell.recv(buffer_size).decode()
                    return output

                print("HIII")
                output = send_command('sudo -s', '[sudo] password for')
                print(output)
                if '[sudo] password for' in output:
                    output = send_command(password, '#')
                print(output)

                output = send_command('mkdir -p /opt/evertz/insite/probe')
                print(output)

                output = send_command(f'mv {remote_temp_path} {remote_final_path}')
                print(output)

                commands = [
                    'cd /opt/evertz/insite/probe',
                    'tar -xvf downloaded_file.tar',
                    'cd /opt/evertz/insite/probe/insite-probe/setup',
                    'chmod +x ./install',
                    'echo "1" | ./install'
                ]

                for command in commands:
                    output = send_command(command)
                    print(output)

                output = send_command('systemctl status insite-probe')
                print(output)

                if 'active (running)' not in output:
                    send_command('systemctl start insite-probe')
                    print('Probe started.')

                output = send_command('systemctl status insite-probe')
                print(output)

            finally:
                ssh.close()

            os.remove(local_path)


