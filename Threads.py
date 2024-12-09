import random
import threading
import os
import requests
import json
import paramiko
import time
import urllib3

FILE_DIR = "probe_files"
LOG_DIR = "logs"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class DeployProbesThread(threading.Thread):
	def __init__(self, devices, insite_ip, download_batch, sftp_batch):
		super().__init__()
		self.devices = devices
		self.insite_ip = insite_ip

		seen_pairs = {}
		self.download_jobs = []
		self.sftp_jobs = []
		self.ssh_jobs = []
		for device in devices:
			self.sftp_jobs.append(Job(device))
			self.ssh_jobs.append(Job(device))

			pair = (device.probe_type, device.file_type)
			if pair not in seen_pairs:
				seen_pairs[pair] = ""
				self.download_jobs.append(Job(device))

		self.download_manager = DownloadManager(self.download_jobs, insite_ip, download_batch, self)
		self.sftp_manager = SftpManager(self.sftp_jobs, sftp_batch, self)
		self.ssh_manager = SSHManager(self.ssh_jobs)
		self.end_event = threading.Event()

	def handle_download_error(self, probe_type, file_type):
		for job in self.sftp_jobs:
			if job.device.probe_type == probe_type and job.device.file_type == file_type:
				job.add_log("Probe package download failed, cannot transfer.")
				job.error = True

		for job in self.ssh_jobs:
			if job.device.probe_type == probe_type and job.device.file_type == file_type:
				job.add_log("Probe package download failed.")
				job.error = True

	def handle_sftp_error(self, device):
		for job in self.ssh_jobs:
			if job.device is device:
				job.error = True
				job.add_log("Probe package transfer failed.")

	def run(self):
		self.download_manager.start()
		while self.download_manager.is_alive():
			if self.end_event.is_set():
				self.download_manager.stop(block=True)
				return
			time.sleep(1)

		self.sftp_manager.start()
		while self.sftp_manager.is_alive():
			if self.end_event.is_set():
				self.sftp_manager.end_event.set()
				return
			time.sleep(1)

		self.ssh_manager.start()
		while self.ssh_manager.is_alive():
			if self.end_event.is_set():
				self.ssh_manager.end_event.set()
				return
			time.sleep(1)

		self.log_data()
		self.delete_files()
		self.end_event.set()

	def log_data(self):
		if not os.path.exists("logs"):
			os.makedirs("logs")
		filename = time.strftime("%m-%d__%H-%M")
		with open(f"logs/log--{filename}.log", "w") as file:
			file.write("Download tasks\n")
			for job in self.download_jobs:
				file.write("----------------------------------\n")
				file.write(f"File: {job.device.probe_type}.{job.device.file_type}\n")
				for log in job.logs:
					file.write(log + "\n")
			file.write("\n\nSftp tasks\n")
			for job in self.sftp_jobs:
				file.write("-------------------------------------------------\n")
				file.write(f"Alias: {job.device.alias}    Control IP: {job.device.control_ip}\n")
				for log in job.logs:
					file.write(log + "\n")
			file.write("\n\nSSH Commands\n")
			for job in self.ssh_jobs:
				file.write("-------------------------------------------------\n")
				file.write(f"Alias: {job.device.alias}    Control IP: {job.device.control_ip}\n")
				for log in job.logs:
					file.write(log + "\n")

	@staticmethod
	def delete_files():
		if not os.path.exists(FILE_DIR):
			return

		for filename in os.listdir(FILE_DIR):
			file_path = os.path.join(FILE_DIR, filename)
			try:
				if os.path.isfile(file_path):
					os.remove(file_path)
			except Exception as e:
				print(f"Failed to delete {file_path}. Reason: {e}")

	def stop(self, block=False):
		"""Signal the thread to stop and optionally block until exited."""
		self.end_event.set()
		if self.download_manager.is_alive():
			self.download_manager.stop(block)
		if self.sftp_manager.is_alive():
			self.sftp_manager.stop(block)
		if self.ssh_manager.is_alive():
			self.ssh_manager.stop(block)
		if block is True:
			self.join()


class Job:
	def __init__(self, device):
		self.device = device
		self.error = False
		self.completed = False
		self.in_progress = False
		self.final_update_done = False  # Used by GUI to track the animation
		self.size = 0
		self.done = 0  # Store the downloaded/transferred portion
		self.progress = 0  # Percentage of completed job
		self.speed = 0
		self.logs = []
		self.lock = threading.Lock()

	def get_logs(self):
		with self.lock:
			return self.logs[:]

	def add_log(self, message):
		with self.lock:
			self.logs.append(message)


class BaseManager(threading.Thread):
	def __init__(self, jobs, batch_size, parent):
		super().__init__()
		self.jobs = jobs
		self.batch_size = batch_size
		self.parent = parent
		self.active_threads = []
		self.thread_lock = threading.Lock()
		self.end_event = threading.Event()

	def run(self):
		for job in self.jobs:
			with self.thread_lock:
				while len(self.active_threads) == self.batch_size:
					self.active_threads = [t for t in self.active_threads if t.is_alive()]
					threading.Event().wait(1)

				if self.end_event.is_set():
					return

				thread = self.create_worker(job)
				thread.start()
				self.active_threads.append(thread)

		while self.active_threads:
			self.active_threads = [t for t in self.active_threads if t.is_alive()]
			threading.Event().wait(1)

	def stop(self, block=False):
		self.end_event.set()
		for thread in self.active_threads:
			thread.stop()

		if block is True:
			self.join()

	def create_worker(self, job):
		raise NotImplementedError("Subclasses should implement this method")


class DownloadManager(BaseManager):
	def __init__(self, download_jobs, insite_ip, batch_size, parent):
		super().__init__(download_jobs, batch_size, parent)
		self.insite_ip = insite_ip
		if not os.path.exists(FILE_DIR):
			os.makedirs(FILE_DIR)

	def create_worker(self, job):
		return DownloadWorker(self.insite_ip, job, self)

	def handle_download_error(self, probe_type, file_type):
		self.parent.handle_download_error(probe_type, file_type)


class DownloadWorker(threading.Thread):
	def __init__(self, insite_ip, job: Job, manager: DownloadManager, retries=3):
		super().__init__()
		self.insite_ip = insite_ip
		self.job = job
		self.manager = manager
		self.retries = retries
		self.end_event = threading.Event()

	def log(self, msg):
		self.job.add_log(msg)

	def run(self):
		self.job.in_progress = True
		file = f"{self.job.device.probe_type}.{self.job.device.file_type.lower()}"
		self.log("Starting download")
		for attempt in range(1, self.retries + 1):
			try:
				url = f"https://{self.insite_ip}/api/-/model/probes?static-asset=true"
				headers = {"Content-Type": "application/json"}
				payload = {
					"type": self.job.device.probe_type,
					"os": {"family": "linux", "architecture": "amd64"},
					"bits": 64,
					"archive-type": self.job.device.file_type,
					"port": 22222,
					"beats": {"filebeat": True, "metricbeat": True},
				}
				self.log(f"Attempt {attempt}: Requesting probe File Path")
				response = requests.post(url, headers=headers, data=json.dumps(payload), verify=False)
				self.log(f"Attempt {attempt}: Response status code: {response.status_code}")
				if response.status_code == 200:
					path = response.json().get("path")
					self.log(f"Attempt {attempt}: Path retrieved: {path}")

					if path:
						download_url = f"https://{self.insite_ip}/probe/download/{path}"
						self.log(f"Attempt {attempt}: Requesting file size from {download_url}")
						response = requests.head(download_url, verify=False)  # Get content length
						total_size = int(response.headers.get("content-length", 0))
						self.job.size = total_size / (1024 * 1024)
						self.log(f"Attempt {attempt}: Total file size: {self.job.size} MB")
						self.log(f"Attempt {attempt}: Downloading file...")
						with requests.get(download_url, stream=True, verify=False) as download_response:
							self.log(
								f"Attempt {attempt}: Download response status code: {download_response.status_code}")
							if download_response.status_code == 200:
								file_path = f"{FILE_DIR}/{file}"
								with open(file_path, "wb") as file:
									downloaded_size = 0
									start_time = time.time()
									for chunk in download_response.iter_content(chunk_size=1024):
										if chunk:
											file.write(chunk)
											downloaded_size += len(chunk)
											progress = (downloaded_size / total_size) * 100
											self.job.progress = progress

											elapsed_time = time.time() - start_time
											if elapsed_time > 0:
												speed = downloaded_size / elapsed_time  # bytes per second
												self.job.speed = speed / (1024 * 1024)  # MB/s

											if self.end_event.is_set():
												return

								self.log(f"Attempt {attempt}: File downloaded successfully")
								self.job.in_progress = False
								self.job.completed = True
								self.job.progress = 100
								return  # Exit after successful download
							else:
								self.log(
									f"Attempt {attempt}: Failed to download file. Status code: {download_response.status_code}")
				else:
					self.log(f"Attempt {attempt}: Failed to get download path. Status code: {response.status_code}")

			except Exception as e:
				self.log(f"Attempt {attempt}: Error in downloading {file}: {e}")

		# Retries exhausted
		self.log(f"Failed after {self.retries} retries")
		self.error()
		self.manager.handle_download_error(self.job.device.probe_type, self.job.device.file_type)

	def error(self):
		self.job.error = True
		self.job.progress = 100
		self.job.in_progress = False
		self.job.completed = False

	def stop(self, block=False):
		"""Signal the thread to stop and optionally block until exited."""
		self.end_event.set()
		if block is True:
			self.join()


class SftpManager(BaseManager):
	def create_worker(self, job):
		return SftpWorker(job, self)

	def handle_sftp_error(self, device):
		self.parent.handle_sftp_error(device)


class SftpWorker(threading.Thread):
	def __init__(self, job: Job, manager):
		super().__init__()
		self.job = job
		self.device = job.device
		self.manager = manager
		self.start_time = None
		self.end_event = threading.Event()

	def log(self, msg):
		self.job.add_log(msg)

	def run(self):
		if self.job.error:  # If error is true from the get-go...
			self.error()
			return

		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		try:
			self.log("Connecting to device via SSH")
			ssh.connect(self.device.control_ip, 22, self.device.username, self.device.password)
			self.log("SFTP Started")
			sftp = ssh.open_sftp()
			try:
				file = f"{self.device.probe_type}.{self.device.file_type.lower()}"
				file_path = f"{FILE_DIR}/{file}"
				dest = f"/home/{self.device.username}/{file}"

				self.start_time = time.time()
				self.job.in_progress = True

				def sftp_progress(transferred, total):
					if self.end_event.is_set():
						raise InterruptedError("Transfer interrupted by user")

					sent_mb = transferred / (1024 * 1024)
					size_mb = total / (1024 * 1024)
					progress_percentage = (transferred / total) * 100 if total > 0 else 0
					self.job.done = sent_mb
					self.job.size = size_mb
					self.job.progress = progress_percentage
					elapsed_time = time.time() - self.start_time
					if elapsed_time > 0:
						self.job.speed = sent_mb / elapsed_time

				self.log(f"Transferring {file_path} to {dest}")
				sftp.put(file_path, dest, callback=sftp_progress)
				self.log("Probe package SFTP to device successful")
				self.job.in_progress = False
				self.job.completed = True
			except InterruptedError:
				self.log("Transfer stopped by user")
				self.error()
			finally:
				sftp.close()

		except Exception as e:
			self.log(f"SFTP failed: {str(e)}")
			self.error()
		finally:
			ssh.close()

	def error(self):
		self.manager.handle_sftp_error(self.device)
		self.job.error = True
		self.job.progress = 100
		self.job.in_progress = False
		self.job.completed = False

	def stop(self, block=False):
		"""Signal the thread to stop and optionally block until exited."""
		self.end_event.set()
		if block:
			self.join()


class SSHManager(threading.Thread):
	def __init__(self, ssh_jobs):
		super().__init__()
		self.jobs = ssh_jobs
		self.end_event = threading.Event()
		self.workers = []
	def run(self):
		for ssh_job in self.jobs:
			if self.end_event.is_set():
				break
			worker: SSHWorker = SSHWorker(ssh_job)
			worker.start()
			self.workers.append(worker)

		for worker in self.workers:
			worker.join()

	def stop(self, block=False):
		"""Signal the thread to stop and optionally block until exited."""
		self.end_event.set()
		if block is True:
			self.join()


class SSHWorker(threading.Thread):
	def __init__(self, job: Job):
		super().__init__()
		self.device = job.device
		self.job = job

	def log(self, msg):
		self.job.add_log(msg)

	@staticmethod
	def read_until(channel, expected, timeout=None):
		"""Read from the channel until the expected text is found or the timeout expires."""
		start = time.time()
		reply = bytearray()
		while not channel.exit_status_ready():
			if channel.recv_ready():
				reply.extend(channel.recv(8192))
				if expected and expected in reply:
					break
			elif timeout and time.time() - start > timeout:
				break
			time.sleep(0.1)
		return reply.decode('utf-8')

	def authenticate(self, transport):
		"""Authenticate to the SSH server."""
		try:
			self.log("Authenticating to SSH server")
			transport.auth_password(self.device.username, self.device.password)
			if not transport.is_authenticated():
				raise paramiko.SSHException("Authorization failed.")
		except paramiko.SSHException as err:
			self.log(f"Authentication failed: {str(err)}")
			self.error()
			return False
		return True

	def error(self):
		self.job.error = True
		self.job.completed = True
		self.job.in_progress = False
		self.job.progress = 100

	def execute_commands(self, channel, commands):
		"""Send a list of commands to the SSH channel."""
		for command in commands:
			self.log(f"Executing command: {command}")
			channel.send(command + '\n')
			out = self.read_until(channel, b'#', 20)

	def install_probe(self, channel):
		"""Install the probe on the device."""
		file = f"{self.device.probe_type}.{self.device.file_type.lower()}"
		if self.device.file_type == "TAR":
			commands = [
				'rm -rf /opt/evertz/insite/probe',
				'rm /lib/systemd/system/insite-probe.service',
				'rm /usr/lib/systemd/system/insite-probe.service',
				'rm -rf /bin/insite-probe',
				'mkdir -p /opt/evertz/insite/probe',
				f'mv /home/{self.device.username}/{file} /opt/evertz/insite/probe/{file}',
				'cd /opt/evertz/insite/probe',
				f'tar -xvf {file}',
				'cd /opt/evertz/insite/probe/insite-probe/setup',
				'chmod +x ./install',
				'./install',
				'1',
				'y'
			]
		else:
			commands = [f'dpkg -i {file}']

		self.execute_commands(channel, commands)

	def check_and_start_service(self, channel):
		"""Check and start the `insite-probe` service if not running."""
		self.log("Starting probe service")
		systemctl = "/bin/systemctl" if self.device.probe_type in ["centos", "fedora"] else "systemctl"
		channel.send(f'{systemctl} start insite-probe\n')
		self.read_until(channel, b'#', 5)

		channel.send(f'{systemctl} status insite-probe\n')
		output = self.read_until(channel, b'#', 5)

		if 'active (running)' not in output:
			self.log("Probe not started. Error occurred while installing it.")
			self.log("This was because the deployer could not confirm the status of probe service.")
			self.error()
		else:
			self.log("Probe started successfully.")

	def run(self):
		if self.job.error:  # If error is true from the get-go....
			self.error()
			return

		self.job.in_progress = True
		self.job.progress = random.randint(7, 11)
		self.log("Starting working on SSH job")
		try:
			self.log(f"Connecting to {self.device.control_ip}")
			transport = paramiko.Transport((self.device.control_ip, 22))
			self.log("SSH connection established")
			transport.start_client()

			if not self.authenticate(transport):
				return

			self.log("Executing SSH commands")
			channel = transport.open_session()
			channel.get_pty(term='vt100', width=300, height=24)
			channel.invoke_shell()
			self.job.progress = random.randint(27, 34)

			# Gain root access
			self.log("Switching to root shell")
			if self.job.device.probe_type == "debian":
				sudo = 'su\n'
				passw = b'Password:'
			else:
				sudo = 'sudo -s\n'
				passw = b'[sudo] password for'

			channel.send(sudo)
			self.read_until(channel, passw, 5)
			channel.send(self.device.password + '\n')
			out = self.read_until(channel, b'#', 5)
			if '#' in out:
				self.log("Switched to root shell")
			else:
				self.log("Could not gain root shell.")
				self.error()
				return

			self.job.progress = random.randint(38, 45)
			self.install_probe(channel)
			self.job.progress = random.randint(80, 89)
			self.check_and_start_service(channel)
			self.job.completed = True
			self.job.in_progress = False
			self.job.progress = 100
			transport.close()
			self.log("SSH connection closed")
		except paramiko.SSHException as err:
			self.log(f"SSH Error: {str(err)}")
			self.error()
