import wx
import wx.lib.scrolledpanel as scrolled
import threading

class DeviceListView(scrolled.ScrolledPanel):
    def __init__(self, parent):
        super().__init__(parent)
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.panel = wx.Panel(self)
        self.sizer = wx.GridBagSizer(vgap=5, hgap=5)

        headers = ['Index', 'Control IP', 'Alias', 'Device Type', 'Probe Type', 'Username', 'Password']
        for col, header in enumerate(headers):
            lbl = wx.StaticText(self.panel, label=header)
            self.sizer.Add(lbl, pos=(0, col), flag=wx.ALL, border=5)

        self.row_count = 1
        self.controls = []

        self.panel.SetSizer(self.sizer)

        self.main_sizer.Add(self.panel, 1, wx.EXPAND)
        self.SetSizer(self.main_sizer)

        self.SetupScrolling(scroll_x=True, scroll_y=True)

    def add_devices(self, devices):
        """Runs the device-adding process in a new thread."""
        self.Freeze()
        threading.Thread(target=self._add_devices_thread, args=(devices,)).start()

    def _add_devices_thread(self, devices):
        for control_ip, alias, device_type in devices:
            wx.CallAfter(self._add_device_row, control_ip, alias, device_type)

        wx.CallAfter(self.panel.Layout)
        wx.CallAfter(self.FitInside)
        wx.CallAfter(self.Thaw)

    def _add_device_row(self, control_ip, alias, device_type):
        row = self.row_count
        index = wx.StaticText(self.panel, label=str(row))
        ip = wx.StaticText(self.panel, label=control_ip)
        al = wx.StaticText(self.panel, label=alias)
        device = wx.StaticText(self.panel, label=device_type)
        probe = wx.ComboBox(self.panel, choices=['Ubuntu'], style=wx.CB_READONLY)
        probe.SetSelection(0)
        username = wx.TextCtrl(self.panel)
        password = wx.TextCtrl(self.panel)

        # Add each widget to the sizer in the correct position
        self.sizer.Add(index, pos=(row, 0), flag=wx.ALL | wx.ALIGN_CENTER, border=5)
        self.sizer.Add(ip, pos=(row, 1), flag=wx.EXPAND | wx.ALL, border=5)
        self.sizer.Add(al, pos=(row, 2), flag=wx.EXPAND | wx.ALL, border=5)
        self.sizer.Add(device, pos=(row, 3), flag=wx.EXPAND | wx.ALL, border=5)
        self.sizer.Add(probe, pos=(row, 4), flag=wx.EXPAND | wx.ALL, border=5)
        self.sizer.Add(username, pos=(row, 5), flag=wx.EXPAND | wx.ALL, border=5)
        self.sizer.Add(password, pos=(row, 6), flag=wx.EXPAND | wx.ALL, border=5)

        self.controls.append((device_type, index, ip, al, device, probe, username, password))
        self.row_count += 1

    def clear(self):
        self.Freeze()
        try:
            for controls in self.controls:
                for control in controls[1:]:  # Skip the device type element
                    control.Destroy()
            self.controls.clear()
            self.row_count = 1

            self.sizer.Clear()
            self.panel.Layout()
            self.FitInside()
        finally:
            self.Thaw()
