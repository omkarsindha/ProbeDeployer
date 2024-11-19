import Config
import wx
import threading
from typing import Dict, List, Tuple


class Device:
    def __init__(self, alias: str, control_ip: str) -> None:
        self.alias: str = alias
        self.control_ip: str = control_ip
        self.username: str = ''
        self.password: str = ''
        self.type: str = 'ubuntu'  # Set to ubuntu by default
        self.deploy = False      # Used to keep track of devices that have been configured or not.

    def __str__(self) -> str:
        return f"Device(alias={self.alias}, ip={self.control_ip}, username={self.username}, password={self.password})"


class DeviceListView(wx.Panel):
    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)
        self.main_sizer: wx.BoxSizer = wx.BoxSizer(wx.VERTICAL)

        self.device_list_ctrl: wx.ListCtrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.device_list_ctrl.InsertColumn(0, 'Device Type', width=220)
        self.device_list_ctrl.InsertColumn(1, 'Number of Devices', width=140)
        self.device_list_ctrl.InsertColumn(2, 'Configured', width=100)

        self.device_list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_device_type_double_click)

        self.main_sizer.Add(self.device_list_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(self.main_sizer)

        self.device_types: Dict[str, List[Device]] = {}
        self.device_credentials: Dict[str, Tuple[str, str]] = {}

    def add_devices(self, device_types: Dict[str, List[Device]]) -> None:
        """Runs the device-adding process in a new thread."""
        threading.Thread(target=self._add_devices_thread, args=(device_types,)).start()

    def _add_devices_thread(self, device_types: Dict[str, List[Device]]) -> None:
        wx.CallAfter(self.device_list_ctrl.DeleteAllItems)
        self.device_types = device_types

        for device_type, devices in device_types.items():
            index: int = self.device_list_ctrl.InsertItem(self.device_list_ctrl.GetItemCount(), device_type)
            self.device_list_ctrl.SetItem(index, 1, str(len(devices)))
            self.device_list_ctrl.SetItem(index, 2, f'0 out of {str(len(devices))}')

    def on_device_type_double_click(self, event: wx.ListEvent) -> None:
        device_type: str = event.GetText()
        devices: List[Device] = self.device_types.get(device_type, [])
        DevicePopup(self, device_type, devices).ShowModal()

    def mark_configured(self, device_type: str, configured, total) -> None:
        """Number is the number of devices configured in a given device type"""
        print(f'{device_type}  {configured} out of {total}')
        for index in range(self.device_list_ctrl.GetItemCount()):
            if self.device_list_ctrl.GetItemText(index) == device_type:
                self.device_list_ctrl.SetItem(index, 2, f'{configured} out of {total}')
                break

class DevicePopup(wx.Dialog):
    def __init__(self, parent, device_type: str, devices: List[Device]) -> None:
        super().__init__(parent, title=f"Devices for {device_type}", size=(600, 400))
        self.parent = parent
        self.device_type: str = device_type
        self.devices: List[Device] = devices

        self.main_sizer: wx.BoxSizer = wx.BoxSizer(wx.VERTICAL)

        top_grid= wx.GridBagSizer()
        self.username_label_all: wx.StaticText = wx.StaticText(self, label="Username (All):")
        self.username_text_all: wx.TextCtrl = wx.TextCtrl(self, size=(90, -1))
        self.password_label_all: wx.StaticText = wx.StaticText(self, label="Password (All):")
        self.password_text_all: wx.TextCtrl = wx.TextCtrl(self, size=(90, -1))
        self.apply_all_button: wx.Button = wx.Button(self, label="Apply All")
        top_grid.Add(self.username_label_all, pos=(0, 0), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        top_grid.Add(self.username_text_all, pos=(0, 1), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        top_grid.Add(self.password_label_all, pos=(0, 2), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        top_grid.Add(self.password_text_all, pos=(0, 3), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        top_grid.Add(self.apply_all_button, pos=(0, 4), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        # Create a scrolled panel for the bottom grid
        scrolled_panel = wx.ScrolledWindow(self, style=wx.VSCROLL | wx.HSCROLL)
        scrolled_panel.SetScrollRate(5, 5)
        bottom_grid = wx.GridBagSizer()
        self.device_controls: Dict[Device, Tuple[wx.CheckBox, wx.ComboBox, wx.TextCtrl, wx.TextCtrl]] = {}

        bottom_grid.Add(wx.StaticText(scrolled_panel, label="Deploy"), pos=(0, 0),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        bottom_grid.Add(wx.StaticText(scrolled_panel, label="Alias"), pos=(0, 1),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        bottom_grid.Add(wx.StaticText(scrolled_panel, label="Control IP"), pos=(0, 2),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        bottom_grid.Add(wx.StaticText(scrolled_panel, label="Probe Type"), pos=(0, 3),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        bottom_grid.Add(wx.StaticText(scrolled_panel, label="Username"), pos=(0, 4),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        bottom_grid.Add(wx.StaticText(scrolled_panel, label="Password"), pos=(0, 5),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        for i, device in enumerate(devices):
            deploy_chk_bx = wx.CheckBox(scrolled_panel)
            if device.deploy:
                deploy_chk_bx.SetValue(True)
            alias_label: wx.StaticText = wx.StaticText(scrolled_panel, label=device.alias)
            control_ip_label: wx.StaticText = wx.StaticText(scrolled_panel, label=device.control_ip)
            probe_type = wx.ComboBox(scrolled_panel, choices=list(Config.PROBE_TYPE.keys()), style=wx.CB_READONLY)
            probe_type.SetStringSelection(device.type)
            username_text: wx.TextCtrl = wx.TextCtrl(scrolled_panel, size=(90, -1))
            username_text.SetValue(device.username)
            password_text: wx.TextCtrl = wx.TextCtrl(scrolled_panel, size=(90, -1))
            password_text.SetValue(device.password)

            bottom_grid.Add(deploy_chk_bx, pos=(i + 1, 0), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            bottom_grid.Add(alias_label, pos=(i+1, 1), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            bottom_grid.Add(control_ip_label, pos=(i+1, 2), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            bottom_grid.Add(probe_type, pos=(i+1, 3), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            bottom_grid.Add(username_text, pos=(i+1, 4), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            bottom_grid.Add(password_text, pos=(i+1, 5), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            self.device_controls[device] = (deploy_chk_bx, probe_type, username_text, password_text)

        scrolled_panel.SetSizer(bottom_grid)
        scrolled_panel.FitInside()

        self.main_sizer.Add(top_grid, 0, wx.ALL | wx.CENTER, 5)
        self.main_sizer.Add(scrolled_panel, 1, wx.EXPAND | wx.ALL, 20)

        self.save_button: wx.Button = wx.Button(self, label="Save")
        self.cancel_button: wx.Button = wx.Button(self, label="Cancel")
        self.button_sizer: wx.BoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.button_sizer.Add(self.save_button, 0, wx.ALL, 5)
        self.button_sizer.Add(self.cancel_button, 0, wx.ALL, 5)
        self.main_sizer.Add(self.button_sizer, 0, wx.ALIGN_CENTER)

        self.SetSizer(self.main_sizer)

        self.save_button.Bind(wx.EVT_BUTTON, self.on_save)
        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
        self.apply_all_button.Bind(wx.EVT_BUTTON, self.on_apply_all)

    def on_save(self, event: wx.Event) -> None:
        total = 0
        configured = 0
        for device, (deploy_chk_bx, probe_type, username_text, password_text) in self.device_controls.items():
            device.username = username_text.GetValue()
            device.password = password_text.GetValue()
            device.deploy = deploy_chk_bx.IsChecked()
            device.type = probe_type.GetStringSelection()
            if device.deploy:
                configured += 1
            total += 1
        self.parent.mark_configured(self.device_type, configured, total)
        self.Close()

    def on_cancel(self, event: wx.Event) -> None:
        self.Close()

    def on_apply_all(self, event: wx.Event) -> None:
        username: str = self.username_text_all.GetValue()
        password: str = self.password_text_all.GetValue()
        for device, (deploy_chk_bx, username_text, password_text) in self.device_controls.items():
            deploy_chk_bx.SetValue(True)
            username_text.SetValue(username)
            password_text.SetValue(password)
