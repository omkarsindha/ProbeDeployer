from smtpd import program

import Threads
import wx
import threading
from typing import Dict, List, Tuple
import wx.dataview as dv

PROBE_TYPES = { "ubuntu": ["TAR", "DEB"], "debian": ["TAR", "DEB"], "centos": ["TAR"], "fedora": ["TAR"], "opensuse": ["TAR"], "suse": ["TAR"]}
FILE_TYPES = {"TAR": ["centos","ubuntu","debian","fedora","opensuse","suse"], "DEB":["ubuntu","debian"]}

class Device:
    def __init__(self, alias: str, control_ip: str) -> None:
        self.alias: str = alias
        self.control_ip: str = control_ip
        self.username: str = ''
        self.password: str = ''
        self.probe_type: str = 'ubuntu'  # Set to ubuntu by default
        self.file_type = 'tar'           # Set to tar by default
        self.deploy = False              # Used to keep track of devices that have been configured or not

    def __str__(self) -> str:
        return f"Device(alias={self.alias}, ip={self.control_ip}, username={self.username}, password={self.password})"


class DeviceListView(wx.Panel):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.wxconfig = parent.wxconfig
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
        """Number is the number of devices configured in a given device probe_type"""
        for index in range(self.device_list_ctrl.GetItemCount()):
            if self.device_list_ctrl.GetItemText(index) == device_type:
                self.device_list_ctrl.SetItem(index, 2, f'{configured} out of {total}')
                break

class DevicePopup(wx.Dialog):
    def __init__(self, parent: DeviceListView, device_type: str, devices: List[Device]) -> None:
        super().__init__(parent, title=f"Devices for {device_type}", size=(700, 400), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.parent = parent
        self.wxconfig = parent.wxconfig
        self.device_type: str = device_type
        self.devices: List[Device] = devices
        self.cmb_bx_tuples = []

        self.main_sizer: wx.BoxSizer = wx.BoxSizer(wx.VERTICAL)

        top_grid= wx.GridBagSizer()
        self.username_label_all: wx.StaticText = wx.StaticText(self, label="User:")
        self.username_text_all: wx.TextCtrl = wx.TextCtrl(self, size=(90, -1), value=self.wxconfig.Read('/deviceUser', defaultVal=""))
        self.password_label_all: wx.StaticText = wx.StaticText(self, label="Password:")
        self.password_text_all: wx.TextCtrl = wx.TextCtrl(self, size=(90, -1),  value=self.wxconfig.Read('/devicePass', defaultVal=""))
        self.probe_type = wx.ComboBox(self, choices=list(PROBE_TYPES.keys()), style=wx.CB_READONLY)
        self.probe_type.SetSelection(0)
        self.probe_type.Bind(wx.EVT_COMBOBOX, self.on_probe_type_changed)
        self.file_type = wx.ComboBox(self, choices=list(FILE_TYPES.keys()), style=wx.CB_READONLY)
        self.file_type.SetSelection(0)
        self.file_type.Bind(wx.EVT_COMBOBOX, self.on_file_type_changed)
        self.cmb_bx_tuples.append((self.probe_type, self.file_type))
        self.apply_all_button: wx.Button = wx.Button(self, label="Apply All")
        top_grid.Add(self.probe_type, pos=(0, 0), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        top_grid.Add(self.file_type, pos=(0, 1), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        top_grid.Add(self.username_label_all, pos=(0, 2), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        top_grid.Add(self.username_text_all, pos=(0, 3), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        top_grid.Add(self.password_label_all, pos=(0, 4), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        top_grid.Add(self.password_text_all, pos=(0, 5), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        top_grid.Add(self.apply_all_button, pos=(0, 6), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        # Create a scrolled panel for the bottom grid
        scrolled_panel = wx.ScrolledWindow(self, style=wx.VSCROLL | wx.HSCROLL)
        scrolled_panel.SetScrollRate(5, 5)
        bottom_grid = wx.GridBagSizer()
        self.device_controls: Dict[Device, Tuple[wx.CheckBox, wx.ComboBox, wx.ComboBox, wx.TextCtrl, wx.TextCtrl]] = {}

        bottom_grid.Add(wx.StaticText(scrolled_panel, label="Deploy"), pos=(0, 0),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        bottom_grid.Add(wx.StaticText(scrolled_panel, label="Alias"), pos=(0, 1),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        bottom_grid.Add(wx.StaticText(scrolled_panel, label="Control IP"), pos=(0, 2),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        bottom_grid.Add(wx.StaticText(scrolled_panel, label="Probe Type"), pos=(0, 3),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        bottom_grid.Add(wx.StaticText(scrolled_panel, label="File Type"), pos=(0, 4),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        bottom_grid.Add(wx.StaticText(scrolled_panel, label="Username"), pos=(0, 5),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        bottom_grid.Add(wx.StaticText(scrolled_panel, label="Password"), pos=(0, 6),
                        flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)

        for i, device in enumerate(devices):
            deploy_chk_bx = wx.CheckBox(scrolled_panel)
            if device.deploy:
                deploy_chk_bx.SetValue(True)
            alias_label: wx.StaticText = wx.StaticText(scrolled_panel, label=device.alias)
            control_ip_label: wx.StaticText = wx.StaticText(scrolled_panel, label=device.control_ip)
            probe_type = wx.ComboBox(scrolled_panel, choices=list(PROBE_TYPES.keys()), style=wx.CB_READONLY)
            probe_type.SetStringSelection(device.probe_type)
            probe_type.Bind(wx.EVT_COMBOBOX, self.on_probe_type_changed)
            file_type = wx.ComboBox(scrolled_panel, choices=list(FILE_TYPES.keys()), style=wx.CB_READONLY)
            file_type.SetStringSelection(device.file_type)
            file_type.Bind(wx.EVT_COMBOBOX, self.on_file_type_changed)
            self.cmb_bx_tuples.append((probe_type,file_type))
            username_text: wx.TextCtrl = wx.TextCtrl(scrolled_panel, size=(90, -1))
            username_text.SetValue(device.username)
            password_text: wx.TextCtrl = wx.TextCtrl(scrolled_panel, size=(90, -1))
            password_text.SetValue(device.password)

            bottom_grid.Add(deploy_chk_bx, pos=(i + 1, 0), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            bottom_grid.Add(alias_label, pos=(i+1, 1), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            bottom_grid.Add(control_ip_label, pos=(i+1, 2), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            bottom_grid.Add(probe_type, pos=(i+1, 3), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            bottom_grid.Add(file_type, pos=(i + 1, 4), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            bottom_grid.Add(username_text, pos=(i+1, 5), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            bottom_grid.Add(password_text, pos=(i+1, 6), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
            self.device_controls[device] = (deploy_chk_bx, probe_type, file_type, username_text, password_text)

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
        for device, (deploy_chk_bx, probe_type, file_type, username_text, password_text) in self.device_controls.items():
            device.username = username_text.GetValue()
            device.password = password_text.GetValue()
            device.deploy = deploy_chk_bx.IsChecked()
            device.file_type = file_type.GetStringSelection()
            device.probe_type = probe_type.GetStringSelection()
            if device.deploy:
                configured += 1
            total += 1
        self.parent.mark_configured(self.device_type, configured, total)
        self.Close()

    def on_cancel(self, event: wx.Event) -> None:
        self.Close()

    def on_apply_all(self, event: wx.Event) -> None:
        probe_type = self.probe_type.GetStringSelection()
        file_type = self.file_type.GetStringSelection()
        username: str = self.username_text_all.GetValue()
        password: str = self.password_text_all.GetValue()
        self.wxconfig.Write("/deviceUser", username)
        self.wxconfig.Write("/devicePass", password)
        for device, (deploy_chk_bx, probe_type_bx, file_type_bx, username_text, password_text) in self.device_controls.items():
            deploy_chk_bx.SetValue(True)
            probe_type_bx.SetStringSelection(probe_type)
            file_type_bx.SetStringSelection(file_type)
            username_text.SetValue(username)
            password_text.SetValue(password)

    def on_probe_type_changed(self, event):
        # Find which probe ComboBox triggered the event
        for probe_cb, file_cb in self.cmb_bx_tuples:
            if event.GetEventObject() == probe_cb:
                selected_probe = probe_cb.GetValue() #centos
                selected_file = file_cb.GetValue()   # tar
                valid_file_types = PROBE_TYPES.get(selected_probe)
                file_cb.Clear()
                file_cb.AppendItems(valid_file_types)
                file_cb.SetStringSelection(selected_file)
                break

    def on_file_type_changed(self, event):
        # Find which file ComboBox triggered the event
        for probe_cb, file_cb in self.cmb_bx_tuples:
            if event.GetEventObject() == file_cb:
                selected_probe = probe_cb.GetValue()
                selected_file = file_cb.GetValue()
                valid_probes = [probe for probe, files in PROBE_TYPES.items() if selected_file in files]
                probe_cb.Clear()
                probe_cb.AppendItems(valid_probes)
                probe_cb.SetStringSelection(selected_probe)
                break


class TaskListDialog(wx.Dialog):
    def __init__(self, parent, thread: Threads.DeployProbesThread, title="Task List"):
        super().__init__(parent, title=title, size=(900, 600), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.thread = thread
        self.task_list_view = TaskListView(self, self.thread)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.task_list_view, 1, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(sizer)

    def on_close(self, event):
        self.task_list_view.timer.Stop()
        self.Destroy()

class TaskListView(dv.DataViewListCtrl):
    def __init__(self, parent, deploy_thread):
        super().__init__(parent, style=dv.DV_ROW_LINES | dv.DV_VERT_RULES)

        # Add columns
        self.AppendTextColumn("Task Name", width=300)
        self.AppendTextColumn("Size", width=100)
        self.AppendProgressColumn("Progress", width=120)
        self.AppendTextColumn("%", width=80)
        self.AppendTextColumn("Status", width=120)
        self.AppendTextColumn("Avg Speed", width=120)
        self.Bind(dv.EVT_DATAVIEW_ITEM_ACTIVATED, self.on_task_click)
        self.client_data = {}
        self.timer: wx.Timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.refresh_tasks, self.timer)
        self.timer.Start(1000)

        self.deploy_thread = deploy_thread
        self.initialize_tasks()

    def initialize_tasks(self):
        """Add a task to the list."""
        for job in self.deploy_thread.download_jobs:
            name = f"Download {job.device.file_type} file for {job.device.probe_type}"
            size = "?" if job.size == 0 else f"{str(round(job.size, 2))} MB"
            status = "Error" if job.error else "Completed" if job.completed else "Downloading" if job.in_progress else "Pending"
            speed = f"{round(job.speed, 1)} MB/s"
            self.AppendItem([name, size, int(job.progress), f"{round(job.progress, 1)} %", status, speed])
            self.client_data[len(self.client_data)] = job.logs

        for job in self.deploy_thread.sftp_jobs:
            name = f"Transfer {job.device.probe_type}.{job.device.file_type.lower()} to {job.device.alias}"
            size = "?" if job.size == 0 else f"{str(round(job.size, 2))} MB"
            status = "Error" if job.error else "Completed" if job.completed else "Transferring" if job.in_progress else "Pending"
            speed = f"{round(job.speed, 1)} MB/s"
            self.AppendItem([name, size, int(job.progress), f"{round(job.progress, 1)} %", status, speed])
            self.client_data[len(self.client_data)] = job.logs

        for job in self.deploy_thread.ssh_jobs:
            name = f"Executing SSH commands on {job.device.alias}"
            size = "N/A"
            status = "Error" if job.error else "Completed" if job.completed else "In progress" if job.in_progress else "Pending"
            speed = "N/A"
            self.AppendItem([name, size, int(job.progress), f"{round(job.progress, 1)} %", status, speed])
            self.client_data[len(self.client_data)] = job.logs


    def refresh_tasks(self, event):
        """Refresh the task list to reflect updates from the thread."""
        index = 0
        for job in self.deploy_thread.download_jobs:
            if job.progress == 0 or job.final_update_done:
                index += 1
                continue

            size = "?" if job.size == 0 else str(round(job.size, 2))
            if job.progress == 100:
                job.final_update_done = True
            status = "Error" if job.error else "Completed" if job.completed else "Downloading" if job.in_progress else "Pending"
            self.update_task(index, size, job.progress, status, job.speed)
            index += 1

        for job in self.deploy_thread.sftp_jobs:
            if job.progress == 0 or job.final_update_done:
                index += 1
                continue
            size = "?" if job.size == 0 else str(round(job.size, 2))
            if job.progress == 100:
                job.final_update_done = True
            status = "Error" if job.error else "Completed" if job.completed else "Transferring" if job.in_progress else "Pending"
            self.update_task(index, size, job.progress, status, job.speed)
            index += 1

        for job in self.deploy_thread.ssh_jobs:
            if job.progress == 0 or job.final_update_done:
                index += 1
                continue
            if job.progress == 100:
                job.final_update_done = True
            status = "Error" if job.error else "Completed" if job.completed else "In progress" if job.in_progress else "Pending"
            self.update_task(index, None, job.progress, status, None)
            index += 1

    def update_task(self, index, size, progress, status, speed):
        """Update an existing task."""
        size_str = f"{size} MB" if speed is not None else "N/A"
        speed_str = f"{round(speed, 1)} MB/s" if speed is not None else "N/A"

        self.SetValue(size_str, index, 1)            # size
        self.SetValue(int(progress), index, 2)   # progress bar
        self.SetValue(f"{round(progress, 1)} %", index, 3)  # progress %
        self.SetValue(status, index, 4)               # status
        self.SetValue(speed_str, index, 5)   # speed

    def on_task_click(self, event: dv.DataViewEvent):
        """Handle task item click event."""
        item = event.GetItem()
        if item.IsOk():
            index = self.ItemToRow(item)
            dlg = LogListDialog(self, self.client_data[index])
            dlg.ShowModal()
            dlg.Destroy()


class LogListDialog(wx.Dialog):
    def __init__(self, parent: wx.Window, logs: list) -> None:
        super().__init__(parent, title="", size=(500, 300), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.main_sizer: wx.BoxSizer = wx.BoxSizer(wx.VERTICAL)

        self.device_list_ctrl: wx.ListCtrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.device_list_ctrl.InsertColumn(0, 'Logs:', width=500)

        self.main_sizer.Add(self.device_list_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(self.main_sizer)

        self.populate_list(logs)

    def populate_list(self, logs: list) -> None:
        for index, log in enumerate(logs):
            self.device_list_ctrl.InsertItem(index, log)