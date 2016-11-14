from PyQt4 import QtCore, QtGui

APP = QtGui.QApplication.instance()
if APP is None:
    APP = QtGui.QApplication(["pyrpl"])


class PyrplWidget(QtGui.QMainWindow):
    def __init__(self, pyrpl_instance):
        self.parent = pyrpl_instance
        self.logger = self.parent.logger
        super(PyrplWidget, self).__init__()
        self.setDockNestingEnabled(True)
        self.dock_widgets = {}
        self.last_docked = None

        self.menu_modules = self.menuBar().addMenu("Modules")
        self.module_actions = []

        for module in self.parent.software_modules:
            self.add_dock_widget(module.create_widget(), module.name)

        self.set_window_position()
        self.timer_save_pos = QtCore.QTimer()
        self.timer_save_pos.setInterval(1000)
        self.timer_save_pos.timeout.connect(self._save_window_position)
        self.timer_save_pos.start()

        self.setWindowTitle(self.parent.c.pyrpl.name)

    def add_dock_widget(self, widget, name):
        dock_widget = QtGui.QDockWidget(name)
        dock_widget.setObjectName(name)
        dock_widget.setFeatures(
            QtGui.QDockWidget.DockWidgetFloatable |
            QtGui.QDockWidget.DockWidgetMovable |
            QtGui.QDockWidget.DockWidgetVerticalTitleBar|
            QtGui.QDockWidget.DockWidgetClosable)
        self.dock_widgets[name] = dock_widget
        dock_widget.setWidget(widget)
        self.addDockWidget(QtCore.Qt.TopDockWidgetArea,
                                           dock_widget)
        if self.last_docked is not None:
            self.tabifyDockWidget(self.last_docked, dock_widget)
        self.last_docked = dock_widget

        action = QtGui.QAction(name, self.menu_modules)
        action.setCheckable(True)

        # make sure menu and widget are in sync
        action.changed.connect(lambda:dock_widget.setVisible(action.isChecked()))
        dock_widget.visibilityChanged.connect(lambda:action.setChecked(dock_widget.isVisible()))

        self.module_actions.append(action)
        self.menu_modules.addAction(action)

    def _save_window_position(self):
        if self.isVisible(): # Don't try to save position if window is closed (otherwise, random position is saved)
            if (not "dock_positions" in self.parent.c.pyrpl._keys()) or \
               (self.parent.c.pyrpl["dock_positions"]!=bytes(
                    self.saveState())):
                self.parent.c.pyrpl["dock_positions"] = bytes(self.saveState())
            try:
                _ = self.parent.c.pyrpl.window_position
            except KeyError:
                self.parent.c.pyrpl["window_position"] = dict()
            try:
                if self.parent.c.pyrpl["window_position"]!=self.window_position:
                    self.parent.c.pyrpl["window_position"] = self.window_position
            except Exception as e:
                self.logger.warning("Gui is not started. Cannot save position.\n"\
                                    + str(e))

    def set_window_position(self):
        if "dock_positions" in self.parent.c.pyrpl._keys():
            if not self.restoreState(self.parent.c.pyrpl.dock_positions):
                self.logger.warning("Sorry, " + \
                    "there was a problem with the restoration of Dock positions")
        try:
            coords = self.parent.c.pyrpl["window_position"]
        except KeyError:
            coords = [0, 0, 800, 600]
        try:
            self.window_position = coords
        #self._lock_window_position()
        except Exception as e:
            self.logger.warning("Gui is not started. Cannot save position.\n"\
                                +str(e))

    @property
    def window_position(self):
        xy = self.pos()
        x = xy.x()
        y = xy.y()
        dxdy = self.size()
        dx = dxdy.width()
        dy = dxdy.height()
        return [x, y, dx, dy]

    @window_position.setter
    def window_position(self, coords):
        self.move(coords[0], coords[1])
        self.resize(coords[2], coords[3])


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