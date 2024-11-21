import threading
from typing import List
from Widgets import Device
import os
import requests
import json
import paramiko
from scp import SCPClient
import time

FILE_DIR = "probe_files"
LOG_DIR = "logs"

class DeployProbesThread(threading.Thread):
    def __init__(self, devices: List[Device], insite_ip):
        super().__init__()
        self.devices = devices
        self.probe_files = []

        self.insite_ip = insite_ip

        self.download_thread = DownloadManager(self.devices, insite_ip)
        self.scp_thread = SCPManager(self.devices)
        #self.ssh_thread = SSHThread(self.devices)

        self.total_devices = 0
        self.successful_devices = 0
        self.completed_device = 0
        self.current_device = ""
        self.status1 = ""
        self.status2 = ""
        self.status3 = ""
        self.log_file = open(f"logs/log-{time.strftime('%Y-%m-%d__%H-%M-%S')}.txt", "w")

        self.end_event = threading.Event()
        self.start()


    def run(self):
        # Delete the local file
        #self.delete_probe_files()
        self.end_event.set()
        self.log_file.close()

    def log(self, message, status=True):
        self.log_file.write(f"{message}\n")
        self.log_file.flush()
        print(message)
        if status:
            self.status1 = message

    def delete_probe_files(self):
        if os.path.exists(FILE_DIR):
            self.status1 = "Deleting locally downloaded probe files."
            os.remove(FILE_DIR)

class ProbeFile:
    def __init__(self, probe_type, file_type):
        self.probe_type = probe_type
        self.file_type = file_type
        self.error = False
        self.completed = False
        self.is_downloading = False
        self.progress = 0
        self.log = []

class DownloadManager(threading.Thread):
    def __init__(self, devices, insite_ip, batch_size=3):
        super().__init__()
        self.devices = devices
        self.insite_ip = insite_ip
        self.probe_files = []
        self.batch_size = batch_size
        self.active_threads = []
        self.thread_lock = threading.Lock()
        seen_pairs = {}
        for device in self.devices:
            pair = (device.probe_type, device.file_type)
            if pair not in seen_pairs:
                seen_pairs[pair] = "_"
                self.probe_files.append(ProbeFile(device.probe_type, device.file_type))

    def run(self):
        if not os.path.exists(FILE_DIR):
            os.makedirs(FILE_DIR)

        for probe_file in self.probe_files:
            # Start threads if batch size is not exceeded
            with self.thread_lock:
                while len(self.active_threads) == self.batch_size:
                    # Clean up completed threads
                    self.active_threads = [t for t in self.active_threads if t.is_alive()]
                    threading.Event().wait(1)  # Small delay to prevent busy waiting

                probe_type, file_type = probe_file.probe_type, probe_file.file_type
                thread = SingleDownloadThread(self.insite_ip, probe_type, file_type, self)
                thread.start()
                self.active_threads.append(thread)

        while self.active_threads:
            self.active_threads = [t for t in self.active_threads if t.is_alive()]
            threading.Event().wait(1) # Small delay to prevent busy waiting

        print("All downloads completed.")


class SingleDownloadThread(threading.Thread):
    def __init__(self, insite_ip, probe_file:ProbeFile, manager, retries = 3):
        super().__init__()
        self.end_event = threading.Event()
        self.insite_ip = insite_ip
        self.probe_file = probe_file
        self.status = ""
        self.manager = manager
        self.retries = retries

    def log(self, msg):
        self.probe_file.log.append(msg)
        print(msg)

    def run(self):
        self.probe_file.is_downloading = True
        for attempt in range(self.retries):
            try:
                url = f"https://{self.insite_ip}/api/-/model/probes?static-asset=true"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "type": self.probe_file.probe_type,
                    "os": {"family": "linux", "architecture": "amd64"},
                    "bits": 64,
                    "archive-type": self.probe_file.file_type,
                    "port": 22222,
                    "beats": {"filebeat": True, "metricbeat": True},
                }

                response = requests.post(url, headers=headers, data=json.dumps(payload), verify=False)
                if response.status_code == 200:
                    path = response.json().get("path")

                    if path:
                        download_url = f"https://{self.insite_ip}/probe/download/{path}"

                        response = requests.head(download_url, verify=False) # Get content length
                        total_size = int(response.headers.get("content-length", 0))

                        with requests.get(download_url, stream=True, verify=False) as download_response:
                            if download_response.status_code == 200:
                                file_path = f"{FILE_DIR}/{self.probe_file.probe_type}.{self.probe_file.file_type.lower()}"
                                with open(file_path, "wb") as file:
                                    downloaded_size = 0
                                    for chunk in download_response.iter_content(chunk_size=1024):
                                        if chunk:
                                            file.write(chunk)
                                            downloaded_size += len(chunk)
                                            progress = (downloaded_size / total_size) * 100
                                            self.probe_file.progress = progress
                                            print(f"Progress: {progress:.2f}%")

                                self.log(f"Attempt: {attempt}. File downloaded successfully")
                                self.probe_file.is_downloading = False
                                self.probe_file.completed = True
                                return  # Exit after successful download
                            else:
                                self.log(f"Attempt: {attempt}. Failed to download file. Attempt: {attempt}. Status code: {download_response.status_code}")
                else:
                    self.log(f"Attempt: {attempt}. Failed to get download path. Status code: {response.status_code}")

            except Exception as e:
                self.log(f"Attempt: {attempt}.  Error in downloading {self.probe_file.probe_type}.{self.probe_file.file_type}: {e}")

        # Retries exhausted
        self.log(f"Failed after {self.retries} retries")
        self.probe_file.error = True

class SCPManager(threading.Thread):
    def __init__(self, devices, batch_size=3):
        super().__init__()
        self.devices = devices
        self.probe_files = []
        self.batch_size = batch_size
        self.active_threads = []
        self.thread_lock = threading.Lock()

    def run(self):
        for device in self.devices:
            # Start threads if batch size is not exceeded
            with self.thread_lock:
                while len(self.active_threads) == self.batch_size:
                    # Clean up completed threads
                    self.active_threads = [t for t in self.active_threads if t.is_alive()]
                    threading.Event().wait(1)  # Small delay to prevent busy waiting

                thread = SingleSCPThread(device, self)
                thread.start()
                self.active_threads.append(thread)

        while self.active_threads:
            self.active_threads = [t for t in self.active_threads if t.is_alive()]
            threading.Event().wait(1) # Small delay to prevent busy waiting

        print("All downloads completed.")

class SingleSCPThread(threading.Thread):
    def __init__(self, device, manager):
        super().__init__()
        self.device = device
        self.manager = manager

    def run(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(self.device.control_ip, port=22, username=self.device.username, password=self.device.password)
            self.log("SCP Started.")

            def progress(filename, size, sent):
                if isinstance(filename, bytes):
                    filename = filename.decode('utf-8')
                sent_mb = sent / (1024 * 1024)
                size_mb = size / (1024 * 1024)
                progress_percentage = (sent / size) * 100
                self.status1 = f"Transferring {filename} to device: {sent_mb:.2f}/{size_mb:.2f} MB ({progress_percentage:.2f}%)"

            with SCPClient(ssh.get_transport(), progress=progress) as scp:
                file = f"{self.device.probe_type}.{self.device.file_type.lower()}"
                file_path = f"{FILE_DIR}/{file}"
                remote_path = f"/home/{self.device.username}/{file}"
                print(file_path)
                print(remote_path)
                scp.put(file_path, remote_path)
                self.log("Probe package SCP to device successful")
            return True
        except Exception as e:
            self.log(f"SCP failed: {str(e)}")
            return False
        finally:
            ssh.close()


# class SSHThread(threading.Thread):
#     def __init__(self, devices):
#         super().__init__()
#         self.devices = devices
#         pass
#
#     def run(self):
#         try:
#             transport = paramiko.Transport((device.control_ip, 22))
#             transport.start_client()
#         except paramiko.SSHException as err:
#             self.log(f"SSH Failed: {str(err)}")
#             return False
#         try:
#             transport.auth_password(username=device.username, password=device.password)
#         except paramiko.SSHException as err:
#             self.log(f"SSH failed: {str(err)}")
#             return False
#
#         if not transport.is_authenticated():
#             self.log(f"SSH authorization failed.")
#             return False
#
#         self.status1 = "Running commands to install Probe onto device."
#         channel = transport.open_session()
#         channel.get_pty(term='vt100', width=300, height=24)
#         channel.invoke_shell()
#
#         def read_until(channel, expected, timeout=None):
#             """Read the given channel until the expected text shows up or the timeout
#                (in seconds) expires. If timeout is None, it will wait forever. If
#                expected is None it will simply read for the given timeout."""
#             start = time.time()
#             reply = bytearray()
#             while channel.recv_ready() or channel.exit_status_ready() is False:
#                 if channel.recv_ready():
#                     reply.extend(channel.recv(8192))
#                     # Is our expected response in the reply?
#                     pos = reply.find(expected) if expected else -1
#                     if pos > -1:
#                         break
#                 else:
#                     time.sleep(0.1)
#                 elapsed = abs(time.time() - start)
#                 if timeout and elapsed > timeout:
#                     break
#             return reply.decode('utf-8')
#
#         channel.send('sudo -s\n')
#         read_until(channel, b'[sudo] password for', 5)
#
#         channel.send(device.password + '\n')
#         read_until(channel, b'#', 5)
#
#         file = f"{device.probe_type}.{device.file_type.lower()}"
#         # Now you are in a root shell, you can run commands as root
#         if device.file_type == "TAR":
#             commands = [
#                 'mkdir -p /opt/evertz/insite/probe',
#                 f'mv /home/{device.username}/{file} /opt/evertz/insite/probe/{file}',
#                 'cd /opt/evertz/insite/probe',
#                 f'sudo tar -xvf {file}',
#                 'cd /opt/evertz/insite/probe/insite-probe/setup',
#                 'chmod +x ./install',
#                 'rm -f user_consent.json',  # So that the script asks for consent even if Consent has already been given
#                 'rm -rf /bin/insite-probe',
#                 'echo -e "1\nyes" | ./install'
#             ]
#         else:
#             commands = [
#                 f'sudo dpkg -i {file}',
#             ]
#
#         for command in commands:
#             channel.send(command + '\n')
#             out = read_until(channel, b'#', 5)
#             print(f"Command: {command}")
#             print(f"Output: {out}")
#             time.sleep(0.5)
#
#         if device.probe_type == "centos" or device.probe_type == "fedora":
#             systemctl = "/bin/systemctl"
#         else:
#             systemctl = "systemctl"
#         # Check the status of the insite-probe service
#         channel.send(f'{systemctl} status insite-probe\n')
#         output = read_until(channel, b'#', 5)
#         print(output)
#
#         if 'active (running)' not in output:
#             channel.send(f'{systemctl} start insite-probe\n')
#             output = read_until(channel, b'#', 5)
#             print(output)
#
#             time.sleep(0.5)
#             channel.send(f'{systemctl} status insite-probe\n')
#             output = read_until(channel, b'#', 5)
#             print(output)
#
#         transport.close()
#         return True