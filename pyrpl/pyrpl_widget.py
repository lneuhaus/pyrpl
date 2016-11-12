from PyQt4 import QtCore, QtGui

APP = QtGui.QApplication.instance()
if APP is None:
    APP = QtGui.QApplication(["redpitaya_gui"])


class PyrplWidget(QtGui.QMainWindow):
    def __init__(self, pyrpl_instance):
        self.parent = pyrpl_instance
        super(PyrplWidget, self).__init__()
        self.setDockNestingEnabled(True)
        self.dock_widgets = {}
        self.last_docked = None

    def add_dock_widget(self, widget, name):
        dock_widget = QtGui.QDockWidget(name)
        dock_widget.setObjectName(name)
        dock_widget.setFeatures(
            QtGui.QDockWidget.DockWidgetFloatable |
            QtGui.QDockWidget.DockWidgetMovable |
            QtGui.QDockWidget.DockWidgetVerticalTitleBar)
        self.dock_widgets[name] = dock_widget
        dock_widget.setWidget(widget)
        self.addDockWidget(QtCore.Qt.TopDockWidgetArea,
                                           dock_widget)
        if self.last_docked is not None:
            self.tabifyDockWidget(self.last_docked, dock_widget)
        self.last_docked = dock_widget

"""
    def setup_gui(self):
        self.all_gui_modules = []
        self.na_widget = NaGui(name="na",
                               rp=self,
                               parent=None,
                               module=self.na)
        from pyrpl.gui.iq_gui import AllIqWidgets
        self.iq_widget = AllIqWidgets(rp=self,
                                  parent=None)
        self.scope_widget = ScopeWidget(name="scope",
                                        rp=self,
                                        parent=None,
                                        module=self.scope)
        self.sa_widget = SpecAnGui(name="spec an",
                                   rp=self,
                                   parent=None,
                                   module=self.spec_an)
        self.scope_sa_widget = ScopeSaWidget(self.scope_widget, self.sa_widget)
        self.all_asg_widget = AllAsgGui(parent=None,
                                        rp=self)
        self.all_pid_widget = AllPidGui(parent=None,
                                        rp=self)

        self.dock_widgets = {}
        self.last_docked = None
        self.main_window = QtGui.QMainWindow()
        for widget, name in [(self.scope_sa_widget, "Scope/Spec. An."),
                             (self.all_asg_widget, "Asgs"),
                             (self.all_pid_widget, "Pids"),
                             (self.na_widget, "Na"),
                             (self.iq_widget, "Iq")]:
            self.add_dock_widget(widget, name)
        self.main_window.setDockNestingEnabled(True)  # DockWidgets can be
        # stacked with one below the other one in the same column
        self.dock_widgets["Scope/Spec. An."].raise_()  # select first tab
"""