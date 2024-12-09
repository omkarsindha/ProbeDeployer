import threading
import paramiko
import time
import time

class Device:
	def __init__(self, alias: str, control_ip: str, user, passw, probe="") -> None:
		self.alias: str = alias
		self.control_ip: str = control_ip
		self.username: str = user
		self.password: str = passw
		self.probe_type = probe

class SSHWorker(threading.Thread):
	def __init__(self, device):
		super().__init__()
		self.device = device

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
			transport.auth_password(self.device.username, self.device.password)
			if not transport.is_authenticated():
				raise paramiko.SSHException("Authorization failed.")
		except paramiko.SSHException as err:
			return False
		return True


	def execute_commands(self, channel, commands):
		"""Send a list of commands to the SSH channel."""
		for command in commands:
			print(f"Executing command: {command}")
			channel.send(command + '\n')
			out = self.read_until(channel, b'#', 20)
			print(out)

	def uninstall_probe(self, channel):
		"""uninstall the probe on the device."""
		commands = [
			'rm -rf /opt/evertz/insite/probe',
			'rm /lib/systemd/system/insite-probe.service',
			'rm /usr/lib/systemd/system/insite-probe.service',
			'rm -rf /bin/insite-probe',
			'systemctl reboot'
		]
		self.execute_commands(channel, commands)


	def run(self):
		try:
			transport = paramiko.Transport((self.device.control_ip, 22))
			transport.start_client()

			if not self.authenticate(transport):
				return

			channel = transport.open_session()
			channel.get_pty(term='vt100', width=300, height=24)
			channel.invoke_shell()

			# Gain root access
			if self.device.probe_type == "debian":
				sudo = 'su\n'
				passw = b'Password:'
			else:
				sudo = 'sudo -s\n'
				passw = b'[sudo] password for'

			channel.send(sudo)
			self.read_until(channel, passw, 5)
			channel.send(self.device.password + '\n')
			out = self.read_until(channel, b'#', 5)
			if not '#' in out:
				return

			self.uninstall_probe(channel)
			transport.close()
		except paramiko.SSHException as err:
			pass

devices = [Device("Ubuntu Test Server 1 ", "172.17.235.12", "evertz", "evertz"),
		   Device("Ubuntu Test Server 2 ", "172.17.235.3", "evertz", "evertz"),
		   Device("Cent OS Test Server", "172.17.235.89", "evertz", "evertz"),
		   Device("Opensuse Test Server", "172.17.235.34", "evertz", "evertz"),
 		   Device("Debian Test", "172.17.235.40", "evertz", "evertz", "debian")]

for device in devices:
	w = SSHWorker(device)
	w.start()
