import paramiko
import sys
import time

host = '172.17.235.12'
username = 'evertz'
password = 'evertz'

try:
	transport = paramiko.transport.Transport(host)
	transport.start_client()
except paramiko.SSHException as err:
	print(str(err))
	sys.exit()

try:
	transport.auth_password(username=username, password=password)
except paramiko.SSHException as err:
	print(str(err))
	sys.exit()

channel = transport.open_session()
channel.get_pty(term='vt100', width=300, height=24)

CMD = 'echo This'
channel.exec_command(CMD)

cmd_output = bytearray()
while channel.recv_ready() or channel.closed is False:
	if channel.recv_ready():
		try:
			cmd_output.extend(channel.recv(65535))
		except (IOError, EOFError, paramiko.SSHException) as err:
			break
	else:
		time.sleep(0.01)    # No data available. Sleep for a bit.
# Command has exited, channel has closed, or an error occurred.
if channel.exit_status_ready() is True:
	exit_status = channel.recv_exit_status()

output_text = cmd_output.decode('utf-8')
print(output_text)