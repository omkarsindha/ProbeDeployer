import requests
import wx.lib.intctrl
import wx
import threading
import os
import Widgets
import utils


class Panel(wx.Panel):
    def __init__(self, parent, wxconfig):
        wx.Panel.__init__(self, parent)
        self.wxconfig = wxconfig
        self.parent = parent
        # Dict with keys as IP found in capture and value as list of packets for that ip
        self.destination_ips:dict[str,list] = {}
        self.destination_ports:dict[str,list] = {}  # Same as above but for port
        self.packets = []                           # List of first 300 packets

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)

        self.ip_label = wx.StaticText(self, label="Magnum Analytics IP:")
        self.insite_ip = wx.TextCtrl(self, size=(90, -1), value="172.17.223.4")

        self.user_label = wx.StaticText(self, label="Username:")
        self.user_input = wx.TextCtrl(self, size=(90, -1), value="admin")

        self.pass_label = wx.StaticText(self, label="Password:")
        self.pass_input = wx.TextCtrl(self, size=(90, -1), value="admin")

        self.fetch = wx.Button(self, label="Fetch")
        self.fetch.Bind(wx.EVT_BUTTON, self.on_fetch)

        self.deploy = wx.Button(self, label="Deploy Probe")
        self.deploy.Bind(wx.EVT_BUTTON, self.on_deploy)

        self.list = Widgets.DeviceListView(self)
        self.main_vbox = wx.BoxSizer(wx.VERTICAL)
        main_box = wx.StaticBox(self)
        main_box.SetFont(wx.Font(wx.FontInfo(12).Bold()))

        label_flag = wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT | wx.RIGHT
        input_flag = wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT | wx.RIGHT
        button_flag = wx.ALIGN_CENTER_VERTICAL | wx.CENTER | wx.RIGHT | wx.LEFT
        self.grid1 = wx.GridBagSizer()
        self.grid1.Add(self.ip_label, pos=(0,0), flag=label_flag, border=5)
        self.grid1.Add(self.insite_ip, pos=(0,1), flag=input_flag, border=15)
        self.grid1.Add(self.user_label, pos=(0, 2), flag=label_flag, border=5)
        self.grid1.Add(self.user_input, pos=(0, 3), flag=input_flag, border=15)
        self.grid1.Add(self.pass_label, pos=(0, 4), flag=label_flag, border=5)
        self.grid1.Add(self.pass_input, pos=(0, 5), flag=input_flag, border=15)
        self.grid1.Add(self.fetch, pos=(0,6), flag=button_flag, border=15)
        self.grid1.Add(self.deploy, pos=(0, 7), flag=button_flag, border=15)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.grid1, 0, wx.ALIGN_CENTER | wx.TOP, 5)

        self.main_vbox.Add(vbox, flag= wx.ALIGN_CENTER | wx.ALL, border=5)
        self.main_vbox.Add(self.list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        self.SetSizer(self.main_vbox)

    def on_edit_ips(self, event):
        """Opens notepad to edit the Device IP file"""
        file_path = "Config/ips.txt"
        text_editor_command = "notepad"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                f.write('')
        def run_code():
            os.system(f"{text_editor_command} {file_path}")
        edit_thread = threading.Thread(target=run_code)
        edit_thread.start()

    def on_deploy(self, event):
        pass

    def on_fetch(self, event):
        """Starts a background thread to fetch data."""
        threading.Thread(target=self._fetch_data).start()

    def _fetch_data(self):
        ip = self.insite_ip.GetValue()
        user = self.user_input.GetValue()
        password = self.pass_input.GetValue()

        if not utils.is_valid_ip(ip):
            wx.CallAfter(self.error_prompt, "Magnum Analytics IP is not valid.")
            return

        login_url = f"https://{ip}:50443/api/-/login"
        login_payload = {
            'username': user,
            'password': password
        }

        try:
            login_response = requests.post(login_url, json=login_payload, verify=False)
            response_json = login_response.json()

            if response_json.get("status") != "ok":
                wx.CallAfter(self.error_prompt, "Incorrect Username/Password")
                return

            # Proceed to fetch device identity settings
            url = f"https://{ip}:50443/api/-/settings/device-identity"
            response = requests.get(url, verify=False)
            data = response.json()

            devices = []
            for device in data['devices']:
                identification = device['identification']
                alias = identification.get('alias')
                control_ip = identification.get('control-ips', [])[0]
                device_type = identification.get('device-type')
                if utils.is_valid_ip(control_ip):
                    devices.append((control_ip, alias, device_type))

            # Update the device list in the main thread
            wx.CallAfter(self.list.add_devices, devices)

        except requests.RequestException as e:
            # Handle any connection errors
            wx.CallAfter(self.error_prompt, f"Failed to connect: {str(e)}")

    def set_status_text(self, text):
        self.parent.SetStatusText(text)

    def OnTimer(self, event):
        """Called periodically while the flooder threads are running."""
        pass


    def error_prompt(self, message):
        dlg = wx.MessageDialog(self, message, "Error", wx.OK | wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()
# End class Panel(wx.Panel)


if __name__ == '__main__':
    import Main

    Main.Main()
