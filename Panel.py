import wx
import threading
import os
from typing import Dict, List
import Widgets
import Threads
import utils
import requests
from Widgets import TaskListDialog


class Panel(wx.Panel):
    def __init__(self, parent) -> None:
        wx.Panel.__init__(self, parent)
        self.parent= parent
        self.wxconfig = wx.Config("ProbeDeployer")
        self.fetched_insite_ip = ""      # Stores the IP of fetched Insite IP
        self.device_types: Dict[str, List[Widgets.Device]] = {}
        self.deploy_thread = None
        self.animation_counter = 0

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)

        self.ip_label= wx.StaticText(self, label="Insite IP:")
        self.insite_ip: wx.TextCtrl = wx.TextCtrl(self, size=(100, -1), value=self.wxconfig.Read('/insiteIP', defaultVal=""))

        self.user_label = wx.StaticText(self, label="Username:")
        self.user_input: wx.TextCtrl = wx.TextCtrl(self, size=(90, -1), value=self.wxconfig.Read('/insiteUser', defaultVal=""))

        self.pass_label= wx.StaticText(self, label="Password:")
        self.pass_input: wx.TextCtrl = wx.TextCtrl(self, size=(90, -1), value=self.wxconfig.Read('/insitePass', defaultVal=""))

        self.fetch: wx.Button = wx.Button(self, label="Fetch")
        self.fetch.Bind(wx.EVT_BUTTON, self.on_fetch)

        self.deploy: wx.Button = wx.Button(self, label="Start Deployment")
        self.deploy.Bind(wx.EVT_BUTTON, self.on_deploy)

        self.tasks = wx.Button(self, label="Current Tasks")
        self.tasks.Bind(wx.EVT_BUTTON, self.on_task)

        down_batch_label = wx.StaticText(self, label="Download Batch Size:")
        self.down_batch_input = wx.SpinCtrl(self, value=self.wxconfig.Read('/downloadBatch', defaultVal="2") ,size=(60, -1), min=1)

        sftp_batch_label = wx.StaticText(self, label="Transfer Batch Size:")
        self.sftp_batch_input = wx.SpinCtrl(self, value=self.wxconfig.Read('/sftpBatch', defaultVal="3"), size=(60, -1), min=1)

        self.list: Widgets.DeviceListView = Widgets.DeviceListView(self)
        self.main_vbox: wx.BoxSizer = wx.BoxSizer(wx.VERTICAL)
        main_box: wx.StaticBox = wx.StaticBox(self)
        main_box.SetFont(wx.Font(wx.FontInfo(12).Bold()))

        label_flag = wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT | wx.RIGHT
        input_flag = wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT | wx.RIGHT
        button_flag = wx.ALIGN_CENTER_VERTICAL | wx.CENTER | wx.RIGHT | wx.LEFT
        self.grid1: wx.GridBagSizer = wx.GridBagSizer()
        self.grid1.Add(self.ip_label, pos=(0, 0), flag=label_flag, border=5)
        self.grid1.Add(self.insite_ip, pos=(0, 1), flag=input_flag, border=15)
        self.grid1.Add(self.user_label, pos=(0, 2), flag=label_flag, border=5)
        self.grid1.Add(self.user_input, pos=(0, 3), flag=input_flag, border=15)
        self.grid1.Add(self.pass_label, pos=(0, 4), flag=label_flag, border=5)
        self.grid1.Add(self.pass_input, pos=(0, 5), flag=input_flag, border=15)
        self.grid1.Add(self.fetch, pos=(0, 6), flag=button_flag, border=15)

        self.grid2: wx.GridBagSizer = wx.GridBagSizer()
        self.grid2.Add( down_batch_label, pos=(0, 0), flag=label_flag, border=5)
        self.grid2.Add(self.down_batch_input, pos=(0, 1), flag=input_flag, border=15)
        self.grid2.Add(sftp_batch_label, pos=(0, 2), flag=label_flag, border=5)
        self.grid2.Add(self.sftp_batch_input, pos=(0, 3), flag=input_flag, border=15)
        self.grid2.Add(self.deploy, pos=(0, 4), flag=button_flag, border=15)
        self.grid2.Add(self.tasks, pos=(0, 5), flag=button_flag, border=15)

        vbox: wx.BoxSizer = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.grid1, 0, wx.ALIGN_CENTER | wx.TOP, 5)
        vbox.Add(self.grid2, 0, wx.ALIGN_CENTER | wx.TOP, 15)

        self.main_vbox.Add(vbox, flag=wx.ALIGN_CENTER | wx.ALL, border=5)
        self.main_vbox.Add(self.list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        self.SetSizer(self.main_vbox)

    def on_edit_ips(self, event: wx.Event) -> None:
        """Opens notepad to edit the Device IP file"""
        file_path: str = "Config/ips.txt"
        text_editor_command: str = "notepad"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                f.write('')

        def run_code() -> None:
            os.system(f"{text_editor_command} {file_path}")

        edit_thread: threading.Thread = threading.Thread(target=run_code)
        edit_thread.start()

    def on_deploy(self, event: wx.Event) -> None:
        if self.deploy_thread is not None:
            self.error_alert("Probes are already being deployed.")
            return

        if self.device_types == {}:
            self.error_alert("No devices available for probe deployment. Please fetch devices first.")
            return

        total = 0
        configured = 0
        devices = []
        for _, device_list in self.device_types.items():
            for device in device_list:
                if device.deploy:
                    devices.append(device)
                    configured += 1
                total += 1

        if configured == 0:
            self.error_alert("No devices have been configured for deployment.")
            return

        if configured < total:
            if not self.informational_alert(f"{configured} out of {total} devices have been configured. Do you want to continue?"):
                return

        download_batch_size = self.down_batch_input.GetValue()
        sftp_batch_size = self.sftp_batch_input.GetValue()
        self.wxconfig.Write("/downloadBatch", str(download_batch_size))
        self.wxconfig.Write("/sftpBatch", str(sftp_batch_size))
        self.deploy_thread = Threads.DeployProbesThread(devices, self.fetched_insite_ip, download_batch_size, sftp_batch_size)
        self.deploy_thread.start()
        self.list.Disable()
        self.timer.Start(300)

    def on_task(self, event):
        if not self.deploy_thread or not self.deploy_thread.is_alive():
            self.error_alert("No tasks available. Please try deploying first.")
            return

        TaskListDialog(self, self.deploy_thread).ShowModal()

    def on_fetch(self, event: wx.Event) -> None:
        """Starts a background thread to fetch data."""
        threading.Thread(target=self._fetch_data).start()

    def _fetch_data(self) -> None:
        ip: str = self.insite_ip.GetValue()
        user: str = self.user_input.GetValue()
        password: str = self.pass_input.GetValue()

        if not utils.is_valid_ip(ip):
            wx.CallAfter(self.error_alert, "Magnum Analytics IP is not valid.")
            return
        self.wxconfig.Write("/insiteIP", ip)
        self.wxconfig.Write("/insiteUser", user)
        self.wxconfig.Write("/insitePass", password)
        self.fetched_insite_ip = ip

        login_url: str = f"https://{ip}:50443/api/-/login"
        login_payload: dict = {
            'username': user,
            'password': password
        }

        try:
            login_response: requests.Response = requests.post(login_url, json=login_payload, verify=False, timeout=5)
            response_json: dict = login_response.json()

            if response_json.get("status") != "ok":
                wx.CallAfter(self.error_alert, "Incorrect Username/Password")
                return

            # Proceed to fetch device identity settings
            url: str = f"https://{ip}:50443/api/-/settings/device-identity"
            response: requests.Response = requests.get(url, verify=False)
            data: dict = response.json()

            self.device_types = {}
            for device in data['devices']:
                identification: dict = device['identification']
                alias: str = identification.get('alias')
                control_ips: List[str] = identification.get('control-ips', [])
                if len(control_ips) == 0:
                    continue
                control_ip = control_ips[0]
                device_type: str = identification.get('device-type')
                if utils.is_valid_ip(control_ip):
                    if device_type not in self.device_types:
                        self.device_types[device_type] = [Widgets.Device(alias, control_ip)]
                    else:
                        self.device_types[device_type].append(Widgets.Device(alias, control_ip))
            self.device_types = {k: self.device_types[k] for k in sorted(self.device_types, key=str.lower)}
            wx.CallAfter(self.list.add_devices, self.device_types)
        except requests.RequestException as e:
            # Handle any connection errors
            wx.CallAfter(self.error_alert, f"Failed to connect: {str(e)}")

        # self.device_types = {"Test Device Type 1": [Widgets.Device("Ubuntu Test Server 1 ", "172.17.235.12"),
        #                                             Widgets.Device("Ubuntu Test Server 2 ", "172.17.235.3"),],
        #                      "Test Device Type 2": [Widgets.Device("Cent OS Test Server", "172.17.235.89"),
        #                                             Widgets.Device("Opensuse Test Server", "172.17.235.34"),
        #                                             Widgets.Device("Debian Test", "172.17.235.40")]}
        # wx.CallAfter(self.list.add_devices, self.device_types)

    def set_status_text(self, text: str) -> None:
        self.parent.SetStatusText(text)

    def OnTimer(self, event: wx.Event) -> None:
        """Called periodically while the flooder threads are running."""
        self.animation_counter += 1
        self.set_status_text(f"Deploying Probes{'.' * (self.animation_counter % 10)}")

        if not self.deploy_thread.is_alive():
            self.set_status_text(f"Deployment completed.")
            self.deploy_thread = None
            self.list.Enable()
            self.timer.Stop()

    def error_alert(self, message: str) -> None:
        dlg: wx.MessageDialog = wx.MessageDialog(self, message, "Error", wx.OK | wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()

    def informational_alert(self, message: str) -> bool:
        dlg = wx.MessageDialog(self, message, "Continue?", wx.YES_NO | wx.ICON_INFORMATION)
        result = dlg.ShowModal()
        dlg.Destroy()
        return result == wx.ID_YES

    def stop_deployment(self, event):
        if self.deploy_thread:
            self.deploy_thread.end_event.set()
# End class Panel(wx.Panel)


if __name__ == '__main__':
    import Main

    Main.Main()
