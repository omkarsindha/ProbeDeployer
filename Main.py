import os
import sys
import wx
import wx.adv
from Panel import Panel


class MainFrame(wx.Frame):
    def __init__(self, *args, **kw):
        super(MainFrame, self).__init__(*args, **kw)

        self.Center()
        self.SetMinSize((400, 400))

        self.panel = Panel(self)

        helpMenu = wx.Menu()
        helpMenu.Append(wx.ID_ABOUT, "&About")

        logMenu = wx.Menu()
        logMenu.Append(wx.ID_FILE, "&Logs")

        menubar = wx.MenuBar()
        menubar.Append(helpMenu, "&Help")
        menubar.Append(logMenu, "&Log")
        #  Binding the menu options to their methods
        self.Bind(wx.EVT_MENU, self.on_about, id=wx.ID_ABOUT)
        self.Bind(wx.EVT_MENU, self.on_log, id=wx.ID_FILE)
        self.SetMenuBar(menubar)

        self.CreateStatusBar(number=1, style=wx.STB_SIZEGRIP | wx.STB_ELLIPSIZE_END)
        self.SetStatusWidths([-1])
        self.SetStatusText("Welcome :)",0)

    def on_about(self, event):
        info = wx.adv.AboutDialogInfo()
        info.SetName('Magnum Analytics Probe Deployer')
        info.SetDescription(
            "Python version %s.%s.%s (%s %s)\n" % tuple(sys.version_info) +
            "Powered by wxPython %s\n" % (wx.version()) +
            "Running on %s\n\n" % (wx.GetOsDescription()) +
            "Process ID = %s\n" % (os.getpid()))
        info.SetWebSite("www.evertz.com", "Evertz")
        info.AddDeveloper("Omkarsinh Sindha")
        wx.adv.AboutBox(info)

    def on_log(self, event):
        path = "logs"
        if os.path.isdir(path):
            os.startfile(path)
        else:
            self.panel.error_alert("No logs available")

# End class MainFrame(wx.Frame)

    def on_close(self, event: wx.CloseEvent):
        """User wants to close the application. Forward to app_panel."""
        # Skip event by default, so it propagates the closing the application.
        event.Skip()
        self.panel.stop_deployment(event)

def Main():
    app = wx.App()
    frame = MainFrame(None, title="Magnum Analytics Probe Deployer", size=(700, 600))
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    Main()
