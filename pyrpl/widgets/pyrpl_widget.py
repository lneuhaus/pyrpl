from qtpy import QtCore, QtWidgets
import sys
from traceback import format_exception, format_exception_only
import logging
from .. import APP



class ExceptionLauncher(QtCore.QObject):
    #  Used to display exceptions in the status bar of PyrplWidgets
    show_exception = QtCore.Signal(list) # use a signal to make
    # sure no thread is messing up with gui
    show_log = QtCore.Signal(list)

    def __init__(self):
        super(ExceptionLauncher, self).__init__()

    def display_exception(self, etype, evalue, tb):
        #self.etype = etype
        #self.evalue = evalue
        #self.tb = tb
        self.show_exception.emit([etype, evalue, tb])
        self.old_except_hook(etype, evalue, tb)

    def display_log(self, record):
        self.show_log.emit([record])


EL = ExceptionLauncher()
# Exceptions raised by the event loop should be displayed in the MainWindow status_bar.
# see http://stackoverflow.com/questions/40608610/exceptions-in-pyqt-event-loop-and-ipython
# when running in ipython, we have to monkeypatch sys.excepthook in the qevent loop.

def patch_excepthook():
    EL.old_except_hook = sys.excepthook
    sys.excepthook = EL.display_exception

TIMER = QtCore.QTimer()
TIMER.setSingleShot(True)
TIMER.setInterval(0)
TIMER.timeout.connect(patch_excepthook)
TIMER.start()


class LogHandler(QtCore.QObject, logging.Handler):
    """
    A handler class which sends log strings to a wx object
    """
    show_log = QtCore.Signal(list)

    def __init__(self):
        """
        Initialize the handler
        """
        logging.Handler.__init__(self)
        QtCore.QObject.__init__(self)
        # set format of logged messages
        self.setFormatter(logging.Formatter('%(levelname)s (%(name)s): %(message)s'))

    def emit(self, record):
        """
        Emit a record.
        """
        try:
            msg = self.format(record)
            self.show_log.emit([msg])
            #EL.display_log(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class MyDockWidget(QtWidgets.QDockWidget):
    """
    A DockWidget where the inner widget is only created when needed (To reduce load times).
    """
    scrollable = True  # use scroll bars?

    def __init__(self, create_widget_func, name):
        """
        create_widget_func is a function to create the widget.
        """
        super(MyDockWidget, self).__init__(name)
        self.setObjectName(name)
        self.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFloatable |
            QtWidgets.QDockWidget.DockWidgetMovable |
            QtWidgets.QDockWidget.DockWidgetVerticalTitleBar|
            QtWidgets.QDockWidget.DockWidgetClosable)
        self.create_widget_func = create_widget_func
        self.widget = None

    def showEvent(self, event):
        if self.widget is None:
            self.widget = self.create_widget_func()
            if self.scrollable:
                self.scrollarea = QtWidgets.QScrollArea()
                self.scrollarea.setWidget(self.widget)
                self.scrollarea.setWidgetResizable(True)
                self.setWidget(self.scrollarea)
            else:
                self.setWidget(self.widget)
        super(MyDockWidget, self).showEvent(event)

    def event(self, event):
        event_type = event.type()
        if event.type() == 176:  # QEvent::NonClientAreaMouseButtonDblClick
            if self.isFloating():
                if self.isMaximized():
                    fn = lambda: self.showNormal()
                else:
                    fn = lambda: self.showMaximized()
                # strange bug: always goes back to normal
                # self.showMaximized()
                # dirty workaround: make a timer
                self.timer = QtCore.QTimer()
                self.timer.timeout.connect(fn)
                self.timer.setSingleShot(True)
                self.timer.setInterval(1)
                self.timer.start()
            event.accept()
            return True
        else:
            #return super(MyDockWidget, self).event(event)
            return QtWidgets.QDockWidget.event(self, event)


class PyrplWidget(QtWidgets.QMainWindow):
    def __init__(self, pyrpl_instance):
        self.parent = pyrpl_instance
        self.logger = self.parent.logger
        self.handler = LogHandler()
        self.logger.addHandler(self.handler)

        super(PyrplWidget, self).__init__()
        self.setDockNestingEnabled(True)  # allow dockwidget nesting
        self.setAnimated(True)  # animate docking of dock widgets

        self.dock_widgets = {}
        self.last_docked = None

        self.menu_modules = self.menuBar().addMenu("Modules")
        self.module_actions = []

        for module in self.parent.software_modules:
            self.add_dock_widget(module._create_widget, module.name)
        # self.showMaximized()  # maximized by default

        self.centralwidget = QtWidgets.QFrame()
        self.setCentralWidget(self.centralwidget)
        self.centrallayout = QtWidgets.QVBoxLayout()
        self.centrallayout.setAlignment(QtCore.Qt.AlignCenter)
        self.centralwidget.setLayout(self.centrallayout)
        self.centralbutton = QtWidgets.QPushButton('Click on "Modules" in the '
                                             'upper left corner to load a '
                                             'specific PyRPL module!')
        self.centralbutton.clicked.connect(self.click_menu_modules)
        self.centrallayout.addWidget(self.centralbutton)

        self.set_window_position()
        self.timer_save_pos = QtCore.QTimer()
        self.timer_save_pos.setInterval(1000)
        self.timer_save_pos.timeout.connect(self.save_window_position)
        self.timer_save_pos.start()

        self.timer_toolbar = QtCore.QTimer()
        self.timer_toolbar.setInterval(1000)
        self.timer_toolbar.setSingleShot(True)
        self.timer_toolbar.timeout.connect(self.vanish_toolbar)

        self.status_bar = self.statusBar()
        EL.show_exception.connect(self.show_exception)
        self.handler.show_log.connect(self.show_log)
        self.setWindowTitle(self.parent.c.pyrpl.name)
        self.timers = [self.timer_save_pos, self.timer_toolbar]
        #self.set_background_color(self)

    def click_menu_modules(self):
        self.menu_modules.popup(self.mapToGlobal(QtCore.QPoint(10,10)))

    def hide_centralbutton(self):
        for dock_widget in self.dock_widgets.values():
            if dock_widget.isVisible():
                self.centralwidget.hide()
                return
        # only if no dockwidget is shown, show central button
        self.centralwidget.show()

    def show_exception(self, typ_val_tb):
        """
        show exception in red in toolbar
        """
        typ, val, tb = typ_val_tb
        self.timer_toolbar.stop()
        self.status_bar.showMessage(''.join(format_exception_only(typ, val)))
        self.status_bar.setStyleSheet('color: white;background-color: red;')
        self._next_toolbar_style = 'color: orange;'
        self.status_bar.setToolTip(''.join(format_exception(typ, val, tb)))
        self.timer_toolbar.start()

    def show_log(self, records):
        record = records[0]
        self.timer_toolbar.stop()
        self.status_bar.showMessage(record)
        self.status_bar.setStyleSheet('color: white;background-color: green;')
        self._next_toolbar_style = 'color: grey;'
        self.timer_toolbar.start()

    def vanish_toolbar(self):
        """
        Toolbar becomes orange after (called 1s after exception occured)
        """
        self.status_bar.setStyleSheet(self._next_toolbar_style)

    def _clear(self):
        for timer in self.timers:
            timer.stop()

    def add_dock_widget(self, create_widget, name):
        dock_widget = MyDockWidget(create_widget,
                                   name + ' (%s)' % self.parent.name)
        self.dock_widgets[name] = dock_widget
        self.addDockWidget(QtCore.Qt.TopDockWidgetArea,
                           dock_widget)
        if self.last_docked is not None:
            self.tabifyDockWidget(self.last_docked, dock_widget)
        # put tabs on top
        self.setTabPosition(dock_widget.allowedAreas(),
                            QtWidgets.QTabWidget.North)
        self.last_docked = dock_widget
        self.last_docked.hide()  # by default no widget is created...

        action = QtWidgets.QAction(name, self.menu_modules)
        action.setCheckable(True)
        self.module_actions.append(action)
        self.menu_modules.addAction(action)

        # make sure menu and widget are in sync
        action.changed.connect(lambda: dock_widget.setVisible(action.isChecked()))
        dock_widget.visibilityChanged.connect(lambda:action.setChecked(dock_widget.isVisible()))
        dock_widget.visibilityChanged.connect(self.hide_centralbutton)
        self.set_background_color(dock_widget)

    def remove_dock_widget(self, name):
        dock_widget = self.dock_widgets.pop(name)
        # return later whether the widget was visible
        wasvisible = dock_widget.isVisible()
        # disconnect signals from widget
        dock_widget.blockSignals(True)  # avoid further signals
        # remove action button from context menu
        for action in self.module_actions:
            buttontext = action.text()
            if buttontext == name:
                action.blockSignals(True)  # avoid further signals
                self.module_actions.remove(action)
                self.menu_modules.removeAction(action)
                action.deleteLater()
        # remove dock widget
        if self.last_docked == dock_widget:
            self.last_docked = list(self.dock_widgets.values())[-1]
            # not sure what this is supposed to mean, but dict keys/values
            # are not indexable in python 3. Please, convert to list before!
        self.removeDockWidget(dock_widget)
        dock_widget.deleteLater()
        # return whether the widget was visible
        return wasvisible

    def reload_dock_widget(self, name):
        """
        This function destroys the old lockbox widget and loads a new one
        """
        pyrpl = self.parent
        module = getattr(pyrpl, name)
        # save window position
        self.timer_save_pos.stop()
        self.save_window_position()
        pyrpl.c._write_to_file()  # make sure positions are written
        # the widget should be redisplayed afterwards if it was visible
        visible = self.dock_widgets[name].isVisible()
        # replace dock widget
        self.remove_dock_widget(name)
        self.add_dock_widget(module._create_widget, name)
        # restore window position and widget visibility
        self.set_window_position()  # reset the same window position as before
        self.timer_save_pos.start()
        if visible:
            self.dock_widgets[name].show()


    def save_window_position(self):
        # Don't try to save position if window is closed (otherwise, random position is saved)
        if self.isVisible():
            #  pre-serialize binary data as "latin1" string
            act_state = (bytes(self.saveState())).decode("latin1")
            if (not "dock_positions" in self.parent.c.pyrpl._keys()) or \
               (self.parent.c.pyrpl["dock_positions"]!=act_state):
                self.parent.c.pyrpl["dock_positions"] = act_state
            act_window_pos = self.window_position
            saved_window_pos = self.parent.c.pyrpl._get_or_create("window_position")._data
            if saved_window_pos != act_window_pos:
                self.parent.c.pyrpl.window_position = self.window_position
        #else:
        #    self.logger.debug("Gui is not started. Cannot save position.\n")

    def set_window_position(self):
        if "dock_positions" in self.parent.c.pyrpl._keys():
            try:
                self.restoreState(
                    self.parent.c.pyrpl.dock_positions.encode("latin1"))
            except:
                self.logger.warning("Sorry, there was a problem with the "
                                    "restoration of Dock positions. ")
        try:
            coords = self.parent.c.pyrpl["window_position"]._data
        except KeyError:
            coords = [0, 0, 800, 600]
        try:
            self.window_position = coords
            if QtWidgets.QApplication.desktop().screenNumber(self)==-1:
                # window doesn't fit inside screen
                self.window_position = (0,0)
        except Exception as e:
            self.logger.warning("Gui is not started. Cannot set window position.\n"\
                                + str(e))

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

    def set_background_color(self, widget):
        try:
            color = str(self.parent.c.pyrpl.background_color)
        except KeyError:
            return
        else:
            if color.strip() == "":
                return
            try:  # hex values must receive a preceeding hashtag
                int(color, 16)
            except ValueError:
                pass
            else:
                color = "#"+color
            widget.setStyleSheet("background-color:%s"%color)
