import wx
import threading
import os
from typing import Dict, List
import Widgets
import Threads
import utils
import requests
import Config

class Panel(wx.Panel):
    def __init__(self, parent) -> None:
        wx.Panel.__init__(self, parent)
        self.parent= parent

        self.fetch_insite = ""      # Stores the IP of fetched Insite IP
        self.device_types: Dict[str, List[Widgets.Device]] = {}
        self.deploy_thread = None

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)

        self.ip_label= wx.StaticText(self, label="Magnum Analytics IP:")
        self.insite_ip: wx.TextCtrl = wx.TextCtrl(self, size=(90, -1), value="172.17.223.4")

        self.user_label = wx.StaticText(self, label="Username:")
        self.user_input: wx.TextCtrl = wx.TextCtrl(self, size=(90, -1), value="admin")

        self.pass_label= wx.StaticText(self, label="Password:")
        self.pass_input: wx.TextCtrl = wx.TextCtrl(self, size=(90, -1), value="admin")

        self.fetch: wx.Button = wx.Button(self, label="Fetch")
        self.fetch.Bind(wx.EVT_BUTTON, self.on_fetch)

        self.deploy: wx.Button = wx.Button(self, label="Start Deployment")
        self.deploy.Bind(wx.EVT_BUTTON, self.on_deploy)

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
        self.grid1.Add(self.deploy, pos=(0, 7), flag=button_flag, border=15)

        vbox: wx.BoxSizer = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.grid1, 0, wx.ALIGN_CENTER | wx.TOP, 5)

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
        for device_key, device_list in self.device_types.items():
            for device in device_list:
                if device.deploy:
                    configured += 1
                total += 1
        if configured == 0:
            self.error_alert("No devices have been configured for deployment.")
            return
        if configured < total:
            if not self.informational_alert(f"{configured} out of {total} devices have been configured. Do you want to continue?"):
                return
        self.deploy_thread = Threads.DeployProbesThread(self.fetch_insite, self.device_types)
        self.deploy_thread.total_devices = configured
        self.timer.Start(300)

    def on_fetch(self, event: wx.Event) -> None:
        """Starts a background thread to fetch data."""
        threading.Thread(target=self._fetch_data).start()

    def _fetch_data(self) -> None:
        # ip: str = self.insite_ip.GetValue()
        # user: str = self.user_input.GetValue()
        # password: str = self.pass_input.GetValue()
        #
        # if not utils.is_valid_ip(ip):
        #     wx.CallAfter(self.error_alert, "Magnum Analytics IP is not valid.")
        #     return
        #
        # self.fetch_insite = ip
        #
        # login_url: str = f"https://{ip}:50443/api/-/login"
        # login_payload: dict = {
        #     'username': user,
        #     'password': password
        # }
        #
        # try:
        #     login_response: requests.Response = requests.post(login_url, json=login_payload, verify=False)
        #     response_json: dict = login_response.json()
        #
        #     if response_json.get("status") != "ok":
        #         wx.CallAfter(self.error_alert, "Incorrect Username/Password")
        #         return
        #
        #     # Proceed to fetch device identity settings
        #     url: str = f"https://{ip}:50443/api/-/settings/device-identity"
        #     response: requests.Response = requests.get(url, verify=False)
        #     data: dict = response.json()
        #
        #     self.device_types = {}
        #     for device in data['devices']:
        #         identification: dict = device['identification']
        #         alias: str = identification.get('alias')
        #         control_ip: str = identification.get('control-ips', [])[0]
        #         device_type: str = identification.get('device-type')
        #         if utils.is_valid_ip(control_ip):
        #             if device_type not in self.device_types:
        #                 self.device_types[device_type] = [Widgets.Device(alias, control_ip)]
        #             else:
        #                 self.device_types[device_type].append(Widgets.Device(alias, control_ip))

         self.device_types = {"Test Device Type 1": [Widgets.Device("Ubuntu Test Server 1 ", "172.17.235.12"),
                                                   Widgets.Device("Ubuntu Test Server 2 ", "172.17.235.3"),
                                                   Widgets.Device("Ubuntu Test Server 3 ", "172.17.235.32")],
                              "Test Device Type 2": [Widgets.Device("Cent OS Test Server", "172.17.235.89"),
                                                   Widgets.Device("Debian Test Server 2 ", "172.17.235.34"),]}
         wx.CallAfter(self.list.add_devices, self.device_types)
        # except requests.RequestException as e:
        #     # Handle any connection errors
        #     wx.CallAfter(self.error_alert, f"Failed to connect: {str(e)}")

    def set_status_text(self, text: str, number: int) -> None:
        self.parent.SetStatusText(text, number)

    def OnTimer(self, event: wx.Event) -> None:
        """Called periodically while the flooder threads are running."""
        self.set_status_text(self.deploy_thread.status, 0)
        self.set_status_text(f"Deploying on {self.deploy_thread.current_device}", 1)
        self.set_status_text(f"Completed {self.deploy_thread.completed_device}/{self.deploy_thread.total_devices}", 2)
        if self.deploy_thread.end_event.is_set():
            successful = self.deploy_thread.successful_devices
            total = self.deploy_thread.total_devices
            self.set_status_text(f"Deployment completed. Successfully deployed probes on {successful} out of {total} devices.", 0)
            self.set_status_text("", 1)
            self.timer.Stop()
        pass

    def error_alert(self, message: str) -> None:
        dlg: wx.MessageDialog = wx.MessageDialog(self, message, "Error", wx.OK | wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()

    def informational_alert(self, message: str) -> bool:
        dlg = wx.MessageDialog(self, message, "Continue?", wx.YES_NO | wx.ICON_INFORMATION)
        result = dlg.ShowModal()
        dlg.Destroy()
        return result == wx.ID_YES

# End class Panel(wx.Panel)


if __name__ == '__main__':
    import Main

    Main.Main()
