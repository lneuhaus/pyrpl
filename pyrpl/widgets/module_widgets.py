"""
ModuleWidgets's hierarchy is parallel to that of Modules.
Each Module instance can have a widget created by calling create_widget.
To use a different class of Widget than the preset (for instance subclass it), the attribute ModuleClass.WidgetClass
can be changed before calling create_widget()
"""

from .schematics import MyImage, MyFrame, MyLabel, MyFrameDrawing, Connection # useful stuffs for IqManagerWidget

from PyQt4 import QtCore, QtGui
from pyrpl import CurveDB
from collections import OrderedDict
import pyqtgraph as pg
from pyrpl.errors import NotReadyError

from time import time
import numpy as np
import functools

APP = QtGui.QApplication.instance()

class MyMenuLabel(QtGui.QLabel):
    """
    A label on top of the menu widget that is able to display save or load menu.
    """
    def __init__(self, module_widget):
        self.module_widget = module_widget
        self.module = module_widget.module
        super(MyMenuLabel, self).__init__(self.text, module_widget)

    def get_menu(self):
        menu = QtGui.QMenu(self)
        self.actions = []
        for state in self.module.states:
            action = QtGui.QAction(state, self)
            self.actions.append(action)
            action.triggered.connect(functools.partial(self.func, state))
            menu.addAction(action)
        return menu

    def contextMenuEvent(self, event):
        menu = self.get_menu()
        menu.exec_(event.globalPos())


class LoadLabel(MyMenuLabel):
    """
    "Load" label
    """
    text = "  .:Load:. "
    def func(self, state):
        self.module.load_state(state)

class SaveLabel(MyMenuLabel):
    """
    "Save" label
    """
    text = " .:Save:."

    def __init__(self, module_widget):
        super(SaveLabel, self).__init__(module_widget)

    def func(self, state):
        self.module.save_state(state)

    def get_menu(self):
        menu = super(SaveLabel, self).get_menu()
        action_new = QtGui.QAction('<New...>', self)
        action_new.triggered.connect(self.new_state)
        menu.addAction(action_new)
        return menu

    def new_state(self):
        state, accept = QtGui.QInputDialog.getText(self,
                                                   "Save %s state"%self.module.name, "Enter new state name:")
        state = str(state)
        if accept:
            if state in self.module.states:
                raise ValueError("State %s of module %s already exists!"%(state, self.module.name))
            self.module.save_state(state)


class ModuleWidget(QtGui.QGroupBox):
    """
    Base class for a module Widget. In general, this is one of the Tab in the
    final RedPitayaGui object.
    """
    title_pos = (12, 0)

    attribute_changed = QtCore.pyqtSignal()
    # register_names = [] # a list of all register name to expose in the gui
    curve_class = CurveDB # Change this to save the curve with a different system

    def set_title(self, title):
        if hasattr(self, "title_label"): # ModuleManagerWidgets don't have a title_label
            self.title_label.setText(title)
            self.title_label.adjustSize()
            self.title_label.move(*self.title_pos)
            self.load_label.move(self.title_label.width() + self.title_pos[0], self.title_pos[1])
            self.save_label.move(self.load_label.width() + self.load_label.pos().x(), self.title_pos[1])

    def __init__(self, name, module, parent=None):
        super(ModuleWidget, self).__init__(parent)
        self.module = module
        self.name = name
        self.attribute_widgets = OrderedDict()

        self.init_gui() # performs the automatic gui creation based on register_names
        self.create_title_bar()
        # self.setStyleSheet("ModuleWidget{border:0;color: transparent;}") # frames and title hidden for software_modules
                                        # ModuleManagerWidget sets them visible for the HardwareModuleWidgets...
        self.show_ownership()

    def create_title_bar(self):
        self.title_label = QtGui.QLabel("yo", parent=self)
         # title should be at the top-left corner of the widget
        self.load_label = LoadLabel(self)
        self.load_label.adjustSize()

        self.save_label = SaveLabel(self)

        self.save_label.adjustSize()

        # self.setStyleSheet("ModuleWidget{border: 1px dashed gray;color: black;}")
        self.setStyleSheet("ModuleWidget{margin: 0.1em; margin-top:0.6em; border: 1 dotted gray;border-radius:5}")
        # margin-top large enough for border to be in the middle of title
        self.layout().setContentsMargins(0, 5, 0, 0)

    def show_ownership(self):
        if self.module.owner is not None:
            self.setEnabled(False)
            self.set_title(self.module.name + ' (' + self.module.owner + ')')
        else:
            self.setEnabled(True)
            self.set_title(self.module.name)

    def init_attribute_layout(self):
        """
        Automatically creates the gui properties for the register_widgets in register_names.
        :return:
        """

        self.attribute_layout = QtGui.QHBoxLayout()
        self.main_layout.addLayout(self.attribute_layout)

        for attr_name in self.module.gui_attributes:
            widget = getattr(self.module.__class__, attr_name).create_widget(self.module)
            self.attribute_widgets[attr_name] = widget
            self.attribute_layout.addWidget(widget)
            widget.value_changed.connect(self.attribute_changed)

    def save_curve(self, x_values, y_values, **attributes):
        """
        Saves the curve in some database system.
        To change the database system, overwrite this function
        or patch Module.curvedb if the interface is identical.

        :param  x_values: numpy array with x values
        :param  y_values: numpy array with y values
        :param  attributes: extra curve parameters (such as relevant module settings)
        """

        c = self.curve_class.create(x_values,
                                    y_values,
                                    **attributes)
        return c

    def init_gui(self):
        """
        To be overwritten in derived class

        :return:
        """

        self.main_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.init_attribute_layout()


class ScopeWidget(ModuleWidget):
    """
    Widget for scope
    """

    def init_gui(self):
        """
        sets up all the gui for the scope.
        """

        self.datas = [None, None]
        self.times = None
        self.ch_col = ('green', 'red')
        self.module.__dict__['curve_name'] = 'scope'
        self.main_layout = QtGui.QVBoxLayout()
        self.init_attribute_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("Scope")
        self.win = pg.GraphicsWindow(title="Scope")
        self.plot_item = self.win.addPlot(title="Scope")
        self.plot_item.showGrid(y=True, alpha=1.)
        self.button_single = QtGui.QPushButton("Run single")
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.button_save = QtGui.QPushButton("Save curve")
        self.curves = [self.plot_item.plot(pen=color[0]) \
                       for color in self.ch_col]
        self.main_layout.addWidget(self.win)
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_save)
        self.main_layout.addLayout(self.button_layout)
        self.cb_ch = []
        for i in (1, 2):
            self.cb_ch.append(QtGui.QCheckBox("Channel " + str(i)))
            self.button_layout.addWidget(self.cb_ch[-1])

        self.button_single.clicked.connect(self.run_single)
        self.button_continuous.clicked.connect(self.run_continuous_clicked)
        self.button_save.clicked.connect(self.save)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(10)
        self.timer.setSingleShot(True)

        self.timer.timeout.connect(self.check_for_curves)

        for cb, col in zip(self.cb_ch, self.ch_col):
            cb.setCheckState(2)
            cb.setStyleSheet('color: ' + col)
        for cb in self.cb_ch:
            cb.stateChanged.connect(self.display_curves)

        self.rolling_group = QtGui.QGroupBox("Trigger mode")
        self.checkbox_normal = QtGui.QRadioButton("Normal")
        self.checkbox_untrigged = QtGui.QRadioButton("Untrigged (rolling)")
        self.checkbox_normal.setChecked(True)
        self.lay_radio = QtGui.QVBoxLayout()
        self.lay_radio.addWidget(self.checkbox_normal)
        self.lay_radio.addWidget(self.checkbox_untrigged)
        self.rolling_group.setLayout(self.lay_radio)
        self.attribute_layout.insertWidget(
            list(self.attribute_widgets.keys()).index("trigger_source"), self.rolling_group)
        self.checkbox_normal.clicked.connect(self.rolling_mode_toggled)
        self.checkbox_untrigged.clicked.connect(self.rolling_mode_toggled)
        self.update_rolling_mode_visibility()
        self.attribute_widgets['duration'].value_changed.connect(self.update_rolling_mode_visibility)
        self.set_running_state()
        self.set_rolling_mode()


    def display_channel(self, ch):
        """
        Displays channel ch (1 or 2) on the graph
        :param ch:
        """
        try:
            self.datas[ch-1] = self.module.curve(ch)
            self.times = self.module.times
            self.curves[ch - 1].setData(self.times,
                                        self.datas[ch-1])
        except NotReadyError:
            pass

    def display_curves(self):
        """
        Displays all active channels on the graph.
        """
        if not self.rolling_mode: # otherwise, evrything is handled in check_for_curves
            for i in (1, 2):
                if self.cb_ch[i - 1].checkState() == 2:
                    self.display_channel(i)
                    self.curves[i - 1].setVisible(True)
                else:
                    self.curves[i - 1].setVisible(False)

    def run_single(self):
        """
        When run_single is pressed, launches a single acquisition.
        """

        self.module.setup()
        self.plot_item.enableAutoRange('xy', True)
        self.display_curves()

    def check_for_curves(self):
        """
        This function is called periodically by a timer when in run_continuous mode.
        1/ Check if curves are ready.
        2/ If so, plots them on the graph
        3/ Restarts the timer.
        """

        if not self.rolling_mode:
            if self.module.curve_ready():
                self.display_curves()
                if self.first_shot_of_continuous:
                    self.first_shot_of_continuous = False  # autoscale only upon first curve
                    self.plot_item.enableAutoRange('xy', False)
                self.module.setup()
        else:
            wp0 = self.module._write_pointer_current
            self.datas = [None, None]
            for ch in (1, 2):
                if self.cb_ch[ch - 1].checkState() == 2:
                    self.datas[ch-1] = self.module._get_ch_no_roll(ch)
            wp1 = self.module._write_pointer_current
            for index, data in enumerate(self.datas):
                if data is None:
                    self.curves[index].setVisible(False)
                    continue
                to_discard = (wp1 - wp0) % self.module.data_length
                data = np.roll(data, self.module.data_length - wp0)[
                       to_discard:]
                data = np.concatenate([[np.nan] * to_discard, data])
                times = self.module.times
                times -= times[-1]
                self.datas[index] = data
                self.times = times
                self.curves[index].setData(times, data)
                self.curves[index].setVisible(True)
        try:
            self.curve_display_done()
        except Exception as e:
            print(e)
        self.timer.start()

    def curve_display_done(self):
        """
        User may overwrite this function to implement custom functionality
        at each graphical update.
        :return:
        """
        pass

    @property
    def state(self):
        if self.module.running_continuous: #button_continuous.text()=="Stop":
            return "running"
        else:
            return "stopped"

    def run_continuous(self):
        """
        Toggles the button run_continuous to stop and starts the acquisition timer.
        This function is part of the public interface.
        """

        self.button_continuous.setText("Stop")
        self.button_single.setEnabled(False)
        self.module.setup()
        if self.module.rolling_mode:
            self.module._trigger_source = 'off'
            self.module._trigger_armed = True
        self.plot_item.enableAutoRange('xy', True)
        self.first_shot_of_continuous = True
        self.timer.start()

    def stop(self):
        """
        Toggles the button stop to run_continuous to stop and stops the acquisition timer
        """

        self.button_continuous.setText("Run continuous")
        self.timer.stop()
        self.button_single.setEnabled(True)

    def set_running_state(self):
        """
        Set running state (stop/run continuous) according to module's attribute "running_continuous"
        """
        if self.module.running_continuous:
            self.run_continuous()
        else:
            self.stop()

    def set_rolling_mode(self):
        """
        Set rolling mode or on off based on the module's attribute "rolling_mode"
        """
        self.rolling_mode = self.module.rolling_mode

    def run_continuous_clicked(self):
        """
        Toggles the button run_continuous to stop or vice versa and starts the acquisition timer
        """

        if str(self.button_continuous.text()) \
                == "Run continuous":
            self.module.running_continuous = True # run_continuous()
        else:
            self.module.running_continuous = False

    def rolling_mode_toggled(self):
        self.module.rolling_mode = self.rolling_mode

    @property
    def rolling_mode(self):
        # Note for future improvement: rolling mode should be a BoolAttribute of
        # Scope rather than a dirty attribute of ScopeWidget. Parameter saving would also require to use it
        # as a parameter of Scope.setup()

        return ((self.checkbox_untrigged.isChecked()) and \
                self.rolling_group.isEnabled())

    @rolling_mode.setter
    def rolling_mode(self, val):
        if val:
            self.checkbox_untrigged.setChecked(True)
        else:
            self.checkbox_normal.setChecked(True)
        if self.state=='running':
            self.stop()
            self.run_continuous()
        return val

    def update_rolling_mode_visibility(self):
        """
        hide rolling mode checkbox for duration < 100 ms
        """

        self.rolling_group.setEnabled(self.module.duration > 0.1)
        self.attribute_widgets['trigger_source'].widget.setEnabled(
            not self.rolling_mode)
        old = self.attribute_widgets['threshold_ch1'].widget.isEnabled()
        self.attribute_widgets['threshold_ch1'].widget.setEnabled(
            not self.rolling_mode)
        self.attribute_widgets['threshold_ch2'].widget.setEnabled(
            not self.rolling_mode)
        self.button_single.setEnabled(not self.rolling_mode)
        if old==self.rolling_mode:
            self.rolling_mode_toggled()

    def autoscale(self):
        """Autoscale pyqtgraph"""

        self.plot_item.autoRange()

    def save(self):
        """
        Save the active curve(s). If you would like to overwrite the save behavior, maybe you should
        consider overwriting Module.save_curve or Module.curve_db rather than this function.
        """

        for ch in [1, 2]:
            d = self.module.get_setup_attributes()
            d.update({'ch': ch,
                      'name': self.module.curve_name + ' ch' + str(ch)})
            self.save_curve(self.times,
                            self.datas[ch-1],
                            **d)


class AsgWidget(ModuleWidget):
    def __init__(self, *args, **kwds):
        super(AsgWidget, self).__init__(*args, **kwds)
        self.attribute_widgets['trigger_source'].value_changed.connect(self.module.setup)


class IqWidget(ModuleWidget):
    """
    Widget for the IQ module
    """

    def init_gui(self):
        super(IqWidget, self).init_gui()
        ##Then remove properties from normal property layout
        ## We will make one where buttons are stack on top of each others by functional column blocks


        for key, widget in self.attribute_widgets.items():
            layout = widget.layout_v
            self.attribute_layout.removeWidget(widget)
        self.attribute_widgets["bandwidth"].widget.set_max_cols(2)
        self.attribute_layout.addWidget(self.attribute_widgets["input"])
        self.attribute_layout.addWidget(self.attribute_widgets["acbandwidth"])
        self.attribute_layout.addWidget(self.attribute_widgets["frequency"])
        self.attribute_widgets["frequency"].layout_v.insertWidget(2, self.attribute_widgets["phase"])
        self.attribute_layout.addWidget(self.attribute_widgets["bandwidth"])
        self.attribute_layout.addWidget(self.attribute_widgets["quadrature_factor"])
        self.attribute_layout.addWidget(self.attribute_widgets["gain"])
        self.attribute_layout.addWidget(self.attribute_widgets["amplitude"])
        self.attribute_layout.addWidget(self.attribute_widgets["output_signal"])
        self.attribute_widgets["output_signal"].layout_v.insertWidget(2, self.attribute_widgets["output_direct"])


class PidWidget(ModuleWidget):
    """
    Widget for a single PID.
    """
    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.init_attribute_layout()
        input_filter_widget = self.attribute_widgets["inputfilter"]
        self.attribute_layout.removeWidget(input_filter_widget)
        self.main_layout.addWidget(input_filter_widget)
        for prop in 'p', 'i', 'd':
            self.attribute_widgets[prop].widget.set_log_increment()
        # can't avoid timer to update ival
        self.timer_ival = QtCore.QTimer()
        self.timer_ival.setInterval(100)
        self.timer_ival.timeout.connect(self.update_ival)
        self.timer_ival.start()

    def update_ival(self):
        widget = self.attribute_widgets['ival']
        if self.isVisible(): # avoid unnecessary ssh traffic
            if not widget.editing():
                widget.update_widget()


class NaWidget(ModuleWidget):
    """
    Network Analyzer Tab.
    """

    def init_gui(self):
        """
        Sets up the gui
        """
        #self.module.__dict__['curve_name'] = 'na trace'
        self.main_layout = QtGui.QVBoxLayout()
        self.init_attribute_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("NA")
        self.win = pg.GraphicsWindow(title="Amplitude")
        self.win_phase = pg.GraphicsWindow(title="Phase")
        self.plot_item = self.win.addPlot(title="Magnitude (dB)")
        self.plot_item_phase = self.win_phase.addPlot(title="Phase (deg)")
        self.plot_item_phase.setXLink(self.plot_item)
        self.button_single = QtGui.QPushButton("Run single")
        self.button_single.my_label = "Single"
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.button_continuous.my_label = "Continuous"
        self.button_restart_averaging = QtGui.QPushButton('Restart averaging')

        self.button_save = QtGui.QPushButton("Save curve")

        self.curve = self.plot_item.plot(pen='y')
        self.curve_phase = self.plot_item_phase.plot(pen=None, symbol='o')
        self.main_layout.addWidget(self.win)
        self.main_layout.addWidget(self.win_phase)
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_restart_averaging)
        self.button_layout.addWidget(self.button_save)
        self.main_layout.addLayout(self.button_layout)

        self.button_single.clicked.connect(self.run_single_clicked)
        self.button_continuous.clicked.connect(self.run_continuous_clicked)
        self.button_restart_averaging.clicked.connect(
            self.ask_restart_and_do_it)
        self.button_save.clicked.connect(self.save)
        self.timer = QtCore.QTimer()  # timer for point acquisition
        self.timer.setInterval(10)
        self.timer.setSingleShot(True)

        self.update_timer = QtCore.QTimer()  # timer for plot update
        self.update_timer.setInterval(50)  # 50 ms refreshrate max
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.setSingleShot(True)

        self.continuous = True
        self.paused = True
        self.need_restart = True

        self.attribute_changed.connect(self.ask_restart)

        self.timer.timeout.connect(self.add_one_point)

        self.paused = True
        # self.restart_averaging() # why would you want to do that? Comment?


        self.attribute_widgets["infer_open_loop_tf"].acquisition_property = False
        self.attribute_widgets["curve_name"].acquisition_property = False

        self.arrow = pg.ArrowItem()
        self.arrow.setVisible(False)
        self.arrow_phase = pg.ArrowItem()
        self.arrow_phase.setVisible(False)
        self.plot_item.addItem(self.arrow)
        self.plot_item_phase.addItem(self.arrow_phase)

    def save_current_curve_attributes(self):
        """
        Stores the attributes in a dictionary self.current_curve_attributes.
        """

        self.current_curve_attributes = self.module.get_setup_attributes()

    def save(self):
        """
        Save the current curve. If you would like to overwrite the save behavior, maybe you should
        consider overwriting Module.save_curve or Module.curve_db rather than this function.
        """

        self.save_curve(self.x[:self.last_valid_point],
                        self.data[:self.last_valid_point],
                        **self.current_curve_attributes)

    def init_data(self):
        """
        Prepares empty arrays before starting the scan
        """

        self.data = np.zeros(self.module.points, dtype=complex)
        self.x = np.empty(self.module.points)
        self.post_average = 0

    def ask_restart(self):
        """
        Called whenever a property is changed: the execution should stop and
        when the user wants to acquire more, the acquisition should restart
        from scratch. However, the current curve is not immediately erased in
        case the user would like to save it.
        """

        self.set_state(continuous=self.continuous, paused=True,
                       need_restart=True, n_av=0)

    def ask_restart_and_do_it(self):
        """
        Restart is actually done immediately (Called when the user clicks on restart averaging)
        """

        if not self.paused:
            self.timer.stop()
            self.restart_averaging()
            self.new_run()
            self.timer.start()
            self.set_state(continuous=self.continuous, paused=self.paused,
                           need_restart=False, n_av=0)
        else:
            self.set_state(continuous=self.continuous, paused=self.paused,
                           need_restart=True, n_av=0)

    def restart_averaging(self):
        """
        Initializes the data, sets the timer, launches the run.
        """

        self.init_data()
        self.timer.setInterval(self.module.time_per_point * 1000)
        self.update_timer.setInterval(10)
        self.new_run()

    def run_single(self):
        """
        Launches a single run (part of the public interface).
        Restarts averaging from scratch.
        """

        self.restart_averaging()
        self.new_run()
        self.set_state(continuous=False, paused=False, need_restart=False)
        self.timer.start()

    def run_single_clicked(self):
        """
        Toggles between pause and running.
        """
        if self.paused:
            if self.continuous or self.need_restart:  # restart from scratch
                self.run_single()
            else:  # continue with the previously started scan
                self.set_state(continuous=False, paused=False,
                               need_restart=False)
                self.timer.start()
        else:  # If already running, then set to paused
            self.set_state(continuous=False, paused=True, need_restart=False)

    def stop(self):
        """
        Stop the current execution (part of the public interface).
        """

        self.set_state(continuous=self.continuous, paused=True,
                       need_restart=self.need_restart)
        self.module.iq.amplitude = 0

    def new_run(self):
        """
        Sets up the fpga modules for a new run and save the run parameters.
        """

        self.module.setup()
        self.values = self.module.values()
        self.save_current_curve_attributes()

    def set_state(self, continuous, paused, need_restart, n_av=0):
        """
        The current state is composed of 3 flags and a number. This function
        updates the flags and reflects on the gui the required state.

        :param continuous: True or False means continuous or single
        :param paused: True or False Whether the acquisition is running or stopped
        :param need_restart: True or False: whether the current data could be averaged with upcoming ones
        :param n_av: current number of averages
        :return:
        """

        self.continuous = continuous
        self.paused = paused
        self.need_restart = need_restart
        active_button = self.button_continuous if continuous else self.button_single
        inactive_button = self.button_single if continuous else self.button_continuous
        self.button_restart_averaging.setEnabled(not need_restart)
        active_button.setEnabled(True)
        inactive_button.setEnabled(self.paused)
        first_word = 'Run ' if need_restart else 'Continue '
        if self.paused:
            self.button_single.setText("Run single")
            self.button_continuous.setText(first_word + "(%i averages)" % n_av)
            self.module.iq.amplitude = 0
        else:
            if active_button == self.button_single:
                active_button.setText('Pause')
            else:
                active_button.setText('Pause (%i averages)' % n_av)

    @property
    def last_valid_point(self):
        """
        Index of the last point that contains more than 0 averages
        """
        if self.post_average > 0:
            max_point = self.module.points
        else:
            max_point = self.module.current_point
        return max_point

    def threshold_hook(self, current_val):
        """
        A convenience function to stop the run upon some condition
        (such as reaching of a threshold. current_val is the complex amplitude
        of the last data point).

        To be overwritten in derived class...
        Parameters
        ----------
        current_val

        Returns
        -------

        """
        pass

    def update_plot(self):
        """
        Update plot only every 10 ms max...

        Returns
        -------
        """
        # plot_time_start = time()
        x = self.x[:self.last_valid_point]
        y = self.data[:self.last_valid_point]

        # check if we shall display open loop tf
        if self.module.infer_open_loop_tf:
            y = y / (1.0 + y)
        mag = 20 * np.log10(np.abs(y))
        phase = np.angle(y, deg=True)
        log_mod = self.module.logscale
        self.curve.setLogMode(xMode=log_mod, yMode=None)
        self.curve_phase.setLogMode(xMode=log_mod, yMode=None)

        self.plot_item.setLogMode(x=log_mod, y=None) # this seems also needed
        self.plot_item_phase.setLogMode(x=log_mod, y=None)

        self.curve.setData(x, mag)
        self.curve_phase.setData(x, phase)

        cur = self.module.current_point - 1
        visible = self.last_valid_point!=cur + 1
        logscale = self.module.logscale
        freq = x[cur]
        xpos = np.log10(freq) if logscale else freq
        if cur>0:
            self.arrow.setPos(xpos, mag[cur])
            self.arrow.setVisible(visible)
            self.arrow_phase.setPos(xpos, phase[cur])
            self.arrow_phase.setVisible(visible)
        # plot_time = time() - plot_time_start # actually not working, because done later
        # self.update_timer.setInterval(plot_time*10*1000) # make sure plotting
        # is only marginally slowing
        # down the measurement...
        self.update_timer.setInterval(self.last_valid_point / 100)

    def add_one_point(self):
        """
        This function is called by a timer periodically to add new points in the buffer.
        Plotting is actually done by another independent loop.
        """

        if self.paused:
            return
        cur = self.module.current_point
        try:
            x, y, amp = next(self.values)
            self.threshold_hook(y)
        except StopIteration:
            self.post_average += 1
            if self.continuous:
                self.new_run()
                self.set_state(continuous=True, paused=False,
                               need_restart=False, n_av=self.post_average)
                self.timer.start()
            else:
                self.set_state(continuous=True, paused=True,
                               need_restart=False, n_av=self.post_average)  # 1
                self.button_single.setText("Run single")
            return
        self.data[cur] = (self.data[cur] * self.post_average + y) \
                         / (self.post_average + 1)
        self.x[cur] = x
        # fomerly, we had buffers for both phase and magnitude. This was faster
        # but more messy. We could restore them once the display get
        # exceedingly slow. In that case, they should be calculated right
        # after acquisition, i.e. here.

        if not self.update_timer.isActive():
            self.update_timer.start()

        self.timer.setInterval(self.module.time_per_point * 1000)
        self.timer.start()

    def run_continuous(self):
        """
        Launch a continuous acquisition (part of the public interface).
        Averages from scratch
        """

        self.restart_averaging()
        self.new_run()
        self.set_state(continuous=True, paused=False, need_restart=False,
                       n_av=self.post_average)
        self.timer.start()

    def resume_acquisition(self):
        """
        Resumes the current acquisition (continuous or single) if it was stopped.
        An AveragingError is launched if the parameters have changed in the mean time.
        """

        if self.need_restart:
            raise AveragingError("""parameters have changed in the mean time, cannot average
                with previous data""")
        else:
            self.set_state(continuous=self.continuous,
                           paused=False,
                           need_restart=self.need_restart,
                           n_av=self.post_average)

    def run_continuous_clicked(self):
        """
        Toggles the run continuous button, and performs the required action.
        """
        if self.paused:
            if self.need_restart:
                self.run_continuous()
            else:
                self.set_state(continuous=True, paused=False,
                               need_restart=False, n_av=self.post_average)
                self.timer.start()
        else:
            self.set_state(continuous=True, paused=True, need_restart=False,
                           n_av=self.post_average)


class MyGraphicsWindow(pg.GraphicsWindow):
    def __init__(self, title, parent_widget):
        super(MyGraphicsWindow, self).__init__(title)
        self.parent_widget = parent_widget
        self.setToolTip("IIR transfer function: \n"
                        "----------------------\n"
                        "CTRL + Left click: add one more pole. \n"
                        "SHIFT + Left click: add one more zero\n"
                        "Left Click: select pole (other possibility: click on the '+j' labels below the graph)\n"
                        "Left/Right arrows: change imaginary part (frequency) of the current pole or zero\n"
                        "Up/Down arrows; change the real part (width) of the current pole or zero. \n"
                        "Poles are represented by 'X', zeros by 'O'")

    def mousePressEvent(self, *args, **kwds):
        event = args[0]
        try:
            modifier = int(event.modifiers())
            it = self.getItem(0, 0)
            pos = it.mapToScene(event.pos()) #  + it.vb.pos()
            point = it.vb.mapSceneToView(pos)
            x, y = point.x(), point.y()
            x = 10 ** x
            new_z = -100 - 1.j * x
            if modifier==QtCore.Qt.CTRL:
                self.parent_widget.module.poles += [new_z]
                self.parent_widget.attribute_widgets['poles'].set_selected(-1)
            if modifier == QtCore.Qt.SHIFT:
                self.parent_widget.module.zeros += [new_z]
                self.parent_widget.attribute_widgets['zeros'].set_selected(-1)
        except BaseException as e:
            self.parent_widget.module._logger.error(e)
        finally:
            return super(MyGraphicsWindow, self).mousePressEvent(*args, **kwds)


class IirWidget(ModuleWidget):
    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.win = MyGraphicsWindow(title="Amplitude", parent_widget=self)
        self.win_phase = MyGraphicsWindow(title="Phase", parent_widget=self)
        # self.proxy = pg.SignalProxy(self.win.scene().sigMouseClicked, rateLimit=60, slot=self.mouse_clicked)
        self.plot_item = self.win.addPlot(title="Magnitude (dB)")
        self.plot_item_phase = self.win_phase.addPlot(title="Phase (deg)")
        self.plot_item_phase.setXLink(self.plot_item)
        # self.proxy_phase = pg.SignalProxy(self.win_phase.scene().sigMouseClicked, rateLimit=60, slot=self.mouse_clicked)

        self.curve = self.plot_item.plot(pen='y')
        self.curve_phase = self.plot_item_phase.plot(pen=None, symbol='o', symbolSize=1)

        self.points_poles = pg.ScatterPlotItem(size=20,
                                               symbol='x',
                                               pen=pg.mkPen(None),
                                               brush=pg.mkBrush(255, 0, 255, 120))
        self.plot_item.addItem(self.points_poles)
        self.points_poles_phase =  pg.ScatterPlotItem(size=20,
                                                      pen=pg.mkPen(None),
                                                      symbol='x',
                                                      brush=pg.mkBrush(255, 0, 255, 120))
        self.plot_item_phase.addItem(self.points_poles_phase)

        self.points_zeros = pg.ScatterPlotItem(size=20,
                                               symbol='o',
                                               pen=pg.mkPen(None),
                                               brush=pg.mkBrush(255, 0, 255, 120))
        self.plot_item.addItem(self.points_zeros)
        self.points_zeros_phase = pg.ScatterPlotItem(size=20,
                                                     pen=pg.mkPen(None),
                                                     symbol='o',
                                                     brush=pg.mkBrush(255, 0, 255, 120))
        self.plot_item_phase.addItem(self.points_zeros_phase)

        self.main_layout.addWidget(self.win)
        self.main_layout.addWidget(self.win_phase)
        self.init_attribute_layout()
        self.second_attribute_layout = QtGui.QVBoxLayout()
        self.attribute_layout.addLayout(self.second_attribute_layout)
        self.third_attribute_layout = QtGui.QVBoxLayout()
        self.attribute_layout.addLayout(self.third_attribute_layout)
        index = 0
        for key, widget in self.attribute_widgets.items():
            index+=1
            if index>3:
                layout = self.third_attribute_layout
            else:
                layout = self.second_attribute_layout
            if key!='poles' and key!='zeros':
                self.attribute_layout.removeWidget(widget)
                layout.addWidget(widget, stretch=0)

        self.second_attribute_layout.addStretch(1)
        self.third_attribute_layout.addStretch(1)
        for attribute_widget in self.attribute_widgets.values():
            self.main_layout.setStretchFactor(attribute_widget, 0)

        self.frequencies = np.logspace(1, np.log10(5e6), 2000)


        self.xlog = True
        self.curve.setLogMode(xMode=self.xlog, yMode=None)
        self.curve_phase.setLogMode(xMode=self.xlog, yMode=None)

        # self.points_poles.setLogMode(xMode=True, yMode=None)
        # self.points_poles_phase.setLogMode(xMode=self.xlog, yMode=None)

        # self.points_zeros.setLogMode(xMode=self.xlog, yMode=None)
        # self.points_zeros_phase.setLogMode(xMode=self.xlog, yMode=None)

        self.plot_item.setLogMode(x=self.xlog, y=None) # this seems also needed
        self.plot_item_phase.setLogMode(x=self.xlog, y=None)

        self.module.setup()
        self.update_plot()

        self.points_poles.sigClicked.connect(self.select_pole)
        self.points_poles_phase.sigClicked.connect(self.select_pole)

        self.points_zeros.sigClicked.connect(self.select_zero)
        self.points_zeros_phase.sigClicked.connect(self.select_zero)

    """
    def mouse_clicked(self, event):
        event = event[0]
        modifier = int(event.modifiers())
        print(event.pos())
        it = self.win.getItem(0, 0)
        vb = it.vb
        print('evt.pos ', event.pos())
        pos = it.mapToScene(event.pos() + it.vb.pos())
        print('pos ', pos)
        point = vb.mapSceneToView(pos)
        print("point", point)
        x, y = point.x(), point.y()
        x = 10 ** x
        new_z = -100 - 1.j * x
        if modifier==QtCore.Qt.CTRL:
            self.module.poles += [new_z]
            self.attribute_widgets['poles'].set_selected(-1)
        if modifier == QtCore.Qt.SHIFT:
            self.module.zeros += [new_z]
            self.attribute_widgets['zeros'].set_selected(-1)
    """

    def select_pole(self, plot_item, spots):
        index = spots[0].data()
        self.attribute_widgets['poles'].set_selected(index)

    def select_zero(self, plot_item, spots):
        index = spots[0].data()
        self.attribute_widgets['zeros'].set_selected(index)

    def update_plot(self):
        tf = self.module.transfer_function(self.frequencies)
        self.curve.setData(self.frequencies, abs(tf))
        self.curve_phase.setData(self.frequencies, 180.*np.angle(tf)/np.pi)
        freq_poles = abs(np.imag(self.module.poles))
        tf_poles = self.module.transfer_function(freq_poles)  # why is frequency the imaginary part? is it
        # related to Laplace transform?
        freq_zeros = abs(np.imag(self.module.zeros))
        tf_zeros = self.module.transfer_function(freq_zeros)
        selected_pole = self.attribute_widgets["poles"].get_selected()
        brush_poles = [{True: pg.mkBrush(color='r'), False: pg.mkBrush(color='b')}[num==selected_pole] \
                                    for num in range(self.attribute_widgets["poles"].number)]
        self.points_poles_phase.setPoints([{'pos': (freq, phase), 'data': index, 'brush': brush} for (index, (freq, phase, brush)) in \
                                     enumerate(zip(np.log10(freq_poles), 180./np.pi*np.angle(tf_poles), brush_poles))])
        self.points_poles.setPoints([{'pos': (freq, mag), 'data': index, 'brush': brush} for (index, (freq, mag, brush)) in \
                                                            enumerate(zip(np.log10(freq_poles), abs(tf_poles), brush_poles))])

        selected_zero = self.attribute_widgets["zeros"].get_selected()
        brush_zeros = [{True: pg.mkBrush(color='r'), False: pg.mkBrush(color='b')}[num==selected_zero] \
                                    for num in range(self.attribute_widgets["zeros"].number)]
        self.points_zeros_phase.setPoints(
            [{'pos': (freq, phase), 'data': index, 'brush': brush} for (index, (freq, phase, brush)) in \
             enumerate(zip(np.log10(freq_zeros), 180. / np.pi * np.angle(tf_zeros), brush_zeros))])
        self.points_zeros.setPoints([{'pos': (freq, mag), 'data': index, 'brush': brush} for (index, (freq, mag, brush)) in \
                                     enumerate(zip(np.log10(freq_zeros), abs(tf_zeros), brush_zeros))])


class ModuleManagerWidget(ModuleWidget):

    def create_title_bar(self):
        """
        ModuleManagerWidgets don't have a title bar
        """
        self.setStyleSheet(
            "ModuleManagerWidget{border:0;color:transparent;}")  # frames and title hidden for software_modules

    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.module_widgets = []

        for index, mod in enumerate(self.module.all_modules):
            module_widget = mod.create_widget()
            # frames and titles visible only for sub-modules of Managers
            # module_widget.setStyleSheet("ModuleWidget{border: 1px dashed gray;color: black;}")
            self.module_widgets.append(module_widget)
            self.main_layout.addWidget(module_widget)
        self.main_layout.addStretch(5) # streth space between Managers preferentially.
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)


class PidManagerWidget(ModuleManagerWidget):
    pass


class ScopeManagerWidget(ModuleManagerWidget):
    pass


class IirManagerWidget(ModuleManagerWidget):
    pass


class IirManagerWidget(ModuleManagerWidget):
    pass


class IqManagerWidget(ModuleManagerWidget):
    def init_gui(self):
        """
        In addition to the normal ModuleManagerWidget stacking of module attributes, the IqManagerWidget
        displays a schematic of the iq  module internal logic.
        """

        super(IqManagerWidget, self).init_gui()
        self.button_hide = QtGui.QPushButton('^', parent=self)
        self.button_hide.setMaximumHeight(15)
        self.button_hide.clicked.connect(self.button_hide_clicked)
        nr = 0
        self.main_layout.setAlignment(QtCore.Qt.AlignTop)
        self.scene = QtGui.QGraphicsScene()
        self.view = QtGui.QGraphicsView(self.scene)
        self.view.setMinimumHeight(150)
        col = self.palette().background().color().name()
        self.view.setStyleSheet("border: 0px; background-color: " + col)
        self.main_layout.addWidget(self.view)
        self.make_drawing()
        self.button_hide_clicked()
        # self.adjust_drawing()

    def button_hide_clicked(self):
        if str(self.button_hide.text())=='v':
            self.button_hide.setText('^')
            for widget in self.module_widgets:
                self.main_layout.setStretchFactor(widget, 0)
            self.view.show()
            for frame in self.frames:
                frame.show()
            for frame in self.frames_drawing:
                frame.show()
            last_module_widget = self.module_widgets[-1]
            #self.setMaximumHeight(600)
        else:
            self.button_hide.setText('v')
            for widget in self.module_widgets:
                self.main_layout.setStretchFactor(widget, 1.)
            self.view.hide()
            for frame in self.frames:
                frame.hide()
            for frame in self.frames_drawing:
                frame.hide()
            # last_module_widget = self.module_widgets[-1]
            # self.setMaximumHeight(last_module_widget.pos().y() + last_module_widget.height())
            # self.setMaximumHeight(600) # By calling twice, forces the window to shrink
        self.adjust_drawing()

    def adjust_drawing(self):
        """
        When the user resizes the window, the drawing elements follow the x-positions of the corresponding
        attribute_widgets.
        """

        for item in self.graphic_items:
            item.move_to_right_position()
        for conn in self.connections:
            conn.adjust()
        iq = self.module_widgets[0]

        for index, prop in enumerate(["input", "acbandwidth", "frequency",
                                      "bandwidth", "quadrature_factor", "gain",
                                      "amplitude", "output_direct"][::2]):
            widget = iq.attribute_widgets[prop]
            self.frames[index].setFixedSize(widget.width() + iq.main_layout.spacing(), self.height())
            self.frames[index].move(widget.x() + iq.pos().x() - iq.main_layout.spacing() / 2, 0)

            self.frames_drawing[index].setFixedSize(widget.width() + iq.main_layout.spacing(), self.height())
            self.frames_drawing[index].move(widget.x() + iq.pos().x() - self.view.pos().x() - iq.main_layout.spacing() / 2,
                                            0)
        self.scene.setSceneRect(QtCore.QRectF(self.view.rect()))
        #x, y = self.view.pos().x(), self.view.pos().y()
        button_width = 150
        self.button_hide.move(self.width()/2 - button_width/2, self.height() - 17)
        self.button_hide.setFixedWidth(button_width)
        self.button_hide.raise_()

    def make_drawing(self):
        """
        Uses the primitives defined in schematics.py to draw the diagram.
        """
        brush = QtGui.QBrush(QtCore.Qt.black)

        row_center = 0.55
        row_up = 0.3
        row_down = 0.8
        row_top = 0.15
        row_center_up = 0.47
        row_center_down = 0.63
        self.graphic_items = []
        self.input = MyLabel("input", row_center, "input", parent=self)

        self.high_pass = MyImage('acbandwidth', row_center, "high_pass.bmp", parent=self)
        self.low_pass1 = MyImage('bandwidth', row_up, "low_pass.bmp", parent=self, x_offset=-40)
        self.low_pass2 = MyImage('bandwidth', row_down, "low_pass.bmp", parent=self, x_offset=-40)

        self.x_sin1 = MyLabel("frequency", row_up, "x sin", parent=self)
        self.x_cos1 = MyLabel("frequency", row_down, "x cos", parent=self)
        self.x_sin2 = MyLabel("amplitude", row_up, "x sin", parent=self, x_offset=40)
        self.x_cos2 = MyLabel("amplitude", row_down, "x cos", parent=self, x_offset=40)

        self.na_real = MyLabel("bandwidth", row_center_up, "na real", parent=self, x_offset=20)
        self.na_imag = MyLabel("bandwidth", row_center_down, "na imag", parent=self, x_offset=20)

        self.x_1 = MyLabel("quadrature_factor", row_top, "X", parent=self)
        self.x_2 = MyLabel("gain", row_up, "X", parent=self)
        self.x_3 = MyLabel('gain', row_down, "X", parent=self)

        self.plus = MyLabel("amplitude", row_up, "+", parent=self, x_offset=0)

        self.cte = MyLabel("amplitude", row_center, "Cte", parent=self, x_offset=0)

        self.plus_2 = MyLabel("amplitude", row_center, "+", parent=self, x_offset=40)

        self.output_direct = MyLabel("output_signal", row_center, "output\ndirect", parent=self)
        self.output_signal = MyLabel("output_signal", row_top, "output\nsignal", parent=self)

        self.connections = []
        self.connect(self.input, self.high_pass)
        self.connect(self.high_pass, self.x_sin1)
        self.connect(self.high_pass, self.x_cos1)
        self.connect(self.x_sin1, self.low_pass1)
        self.connect(self.x_cos1, self.low_pass2)
        self.connect(self.low_pass1, self.na_real, h_first=False)
        self.connect(self.low_pass2, self.na_imag, h_first=False)
        self.connect(self.low_pass1, self.x_1, h_first=False)
        self.connect(self.low_pass1, self.x_2)
        self.connect(self.low_pass2, self.x_3)
        self.connect(self.x_2, self.plus)
        self.connect(self.cte, self.plus, h_first=False)
        self.connect(self.plus, self.x_sin2)
        self.connect(self.x_3, self.x_cos2)
        self.connect(self.x_1, self.output_signal)
        self.connect(self.x_sin2, self.plus_2, h_first=False)
        self.connect(self.x_cos2, self.plus_2, h_first=False)
        self.connect(self.plus_2, self.output_direct)
        self.connect(self.output_direct, self.output_signal, h_first=False)

        self.frames = [MyFrame(self) for i in range(4)]
        self.frames_drawing = [MyFrameDrawing(self) for i in range(4)]

    def connect(self, widget1, widget2, h_first=True):
        """
        Connects 2 blocks with an arrow h_first means the first line originating from widget1 is horizontal.
        """

        self.connections.append(Connection(widget1, widget2, h_first, self))

    def resizeEvent(self, event):
        """
        call adjust_drawing upon resize.
        """

        super(IqManagerWidget, self).resizeEvent(event)
        self.adjust_drawing()


class SpecAnWidget(ModuleWidget):
    _display_max_frequency = 25  # max 25 Hz framerate
    def init_gui(self):
        """
        Sets up the gui.
        """
        self.main_layout = QtGui.QVBoxLayout()
        self.module.__dict__['curve_name'] = 'pyrpl spectrum'
        self.init_attribute_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        # self.setWindowTitle("Spec. An.")
        self.win = pg.GraphicsWindow(title="PSD")
        self.plot_item = self.win.addPlot(title="PSD")
        self.button_single = QtGui.QPushButton("Run single")
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.button_restart_averaging = QtGui.QPushButton('Restart averaging')

        self.button_save = QtGui.QPushButton("Save curve")

        self.curve = self.plot_item.plot(pen='m')

        self.main_layout.addWidget(self.win)

        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_restart_averaging)
        self.button_layout.addWidget(self.button_save)
        self.main_layout.addLayout(self.button_layout)

        self.button_single.clicked.connect(self.run_single)
        self.button_continuous.clicked.connect(self.run_continuous_clicked)
        self.button_restart_averaging.clicked.connect(self.restart_averaging)
        self.button_save.clicked.connect(self.save)

        self.timer = QtCore.QTimer()
        # self.timer.setSingleShot(True)
        #  dont know why but this removes the bug with with freezing gui
        self.timer.setSingleShot(False)
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.acquire_one_curve)

        self.running = False
        self.attribute_changed.connect(self.restart_averaging)

        self.attribute_widgets["rbw_auto"].value_changed.connect(self.update_rbw_visibility)
        self.update_rbw_visibility()

    def update_rbw_visibility(self):
        self.attribute_widgets["rbw"].widget.setEnabled(not self.module.rbw_auto)

    def save(self):
        """
        Saves the current curve.
        """
        self.save_curve(self.x_data,
                        self.module.data_to_dBm(self.y_data),
                        **self.get_state())

    @property
    def current_average(self):
        return self._current_average

    @current_average.setter
    def current_average(self, v):
        # putting a ceiling to the current average, together with the math
        # in acquire_one_curve, automatically creates a lowpass-like
        # averaging mode with a 'bandwidth' defined by avg
        if v > self.module.avg:
            v = self.module.avg
        self._current_average = v

    def run_single(self):
        """
        Runs a single acquisition.
        """

        self.button_continuous.setEnabled(False)
        self.restart_averaging()
        self.module.setup()
        self.acquire_one_curve()
        self.button_continuous.setEnabled(True)

    def update_display(self):
        """
        Updates the curve and the number of averages. Framerate has a ceiling.
        """

        if not hasattr(self, '_lasttime') \
                or (time() - 1.0/self._display_max_frequency) > self._lasttime:
            self._lasttime = time()
            # convert data from W to dBm
            x = self.x_data
            y = self.module.data_to_dBm(self.y_data)
            self.curve.setData(x, y)
            if self.running:
                buttontext = 'Stop (%i' % self.current_average
                if self.current_average >= self.module.avg:
                    # shows a plus sign when number of averages is available
                    buttontext += '+)'
                else:
                    buttontext += ')'
                self.button_continuous.setText(buttontext)

    def acquire_one_curve(self):
        """
        Acquires only one curve.
        """

        # self.module.setup() ### For small BW, setup() then curve() takes

        # several seconds... In the mean time, no other event can be
        # treated. That's why the gui freezes...
        self.y_data = (self.current_average * self.y_data \
                       + self.module.curve()) / (self.current_average + 1)
        self.current_average += 1
        self.update_display()
        if self.running:
            self.module.setup()

    def run_continuous(self):
        """
        Launches a continuous acquisition (part of the public interface).
        """

        self.running = True
        self.button_single.setEnabled(False)
        self.button_continuous.setText("Stop")
        self.restart_averaging()
        self.module.setup()
        self.timer.setInterval(self.module.duration*1000)
        self.timer.start()

    def stop(self):
        """
        Stops the current continuous acquisition (part of the public interface).
        """
        self.timer.stop()
        self.button_continuous.setText("Run continuous")
        self.running = False
        self.button_single.setEnabled(True)
        self.module.scope.owner = None # since the scope is between setup() and curve(). We have to free it manually

    def run_continuous_clicked(self):
        """
        Toggles the run continuous button and performs the required action.
        """

        if self.running:
            self.stop()
        else:
            self.run_continuous()

    def restart_averaging(self):
        """
        Restarts the curve averaging.
        """
        self.x_data = self.module.freqs()
        self.y_data = np.zeros(len(self.x_data))
        self.current_average = 0


class AnalogTfDialog(QtGui.QDialog):
    def __init__(self, parent):
        super(AnalogTfDialog, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        self.setWindowTitle("Analog transfer function for output %s" % self.module.name)
        self.lay_v = QtGui.QVBoxLayout(self)
        self.lay_h = QtGui.QHBoxLayout()
        self.ok = QtGui.QPushButton('Ok')
        self.lay_h.addWidget(self.ok)
        self.ok.clicked.connect(self.validate)
        self.cancel = QtGui.QPushButton('Cancel')
        self.lay_h.addWidget(self.cancel)
        self.group = QtGui.QButtonGroup()
        self.flat = QtGui.QRadioButton("Flat response")
        self.filter = QtGui.QRadioButton('Analog filter (in "assisted design section")')
        self.curve = QtGui.QRadioButton("User defined curve")
        self.group.addButton(self.flat)
        self.group.addButton(self.filter)
        self.group.addButton(self.curve)

        self.lay_v.addWidget(self.flat)
        self.lay_v.addWidget(self.filter)
        self.lay_v.addWidget(self.curve)
        self.label = QtGui.QLabel("Curve #")
        self.line = QtGui.QLineEdit("coucou")

        self.lay_line = QtGui.QHBoxLayout()
        self.lay_v.addLayout(self.lay_line)
        self.lay_v.addWidget(self.line)
        self.lay_line.addStretch(1)
        self.lay_line.addWidget(self.label)
        self.lay_line.addWidget(self.line, stretch=10)
        self.lay_v.addSpacing(20)
        self.lay_v.addLayout(self.lay_h)
        self.curve.toggled.connect(self.change_visibility)
        {'flat':self.flat, 'filter':self.filter, 'curve':self.curve}[self.module.tf_type].setChecked(True)

        self.line.setText(str(self.module.tf_curve))
        self.line.textEdited.connect(lambda: self.line.setStyleSheet(""))
        self.cancel.clicked.connect(self.reject)
        self.curve_id = None
        self.res = None


    def change_visibility(self, checked):
        print(checked)
        for widget in self.label, self.line:
            widget.setEnabled(checked)

    def validate(self):
        self.line.setStyleSheet('')
        if self.flat.isChecked():
            self.res = "flat"
            self.accept()
        if self.filter.isChecked():
            self.res = 'filter'
            self.accept()
        if self.curve.isChecked():
            try:
                curve_id = int(str(self.line.text()))
            except:
                self.line.setStyleSheet('background-color:red;')
            else:
                self.res = 'curve'
                self.curve_id = curve_id
                self.accept()

    def get_type_number(self):
        accept = self.exec_()
        return accept, self.res, self.curve_id


class AnalogTfSpec(QtGui.QWidget):
    """
    A button + label that allows to display and change the transfer function specification
    """
    def __init__(self, parent):
        super(AnalogTfSpec, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        self.layout = QtGui.QVBoxLayout(self)
        self.label = QtGui.QLabel("Analog t. f.")
        self.layout.addWidget(self.label)
        self.button = QtGui.QPushButton('Change...')
        self.layout.addWidget(self.button)
        self.button.clicked.connect(self.change)
        self.dialog = AnalogTfDialog(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.change_analog_tf()

    def change(self, ev):
        accept, typ, number = self.dialog.get_type_number()
        if accept:
            if typ=='curve':
                self.module.tf_curve = number
            self.module.tf_type = typ

    def change_analog_tf(self):
        txt = self.module.tf_type
        if self.module.tf_type=='curve':
            txt += ' #' + str(self.module.tf_curve)
        self.button.setText(txt)


class MainOutputProperties(QtGui.QGroupBox):
    def __init__(self, parent):
        super(MainOutputProperties, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        aws = self.parent.attribute_widgets
        self.layout = QtGui.QHBoxLayout(self)
        self.v1 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v1)
        self.v2 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v2)
        self.v1.addWidget(aws["name"])
        self.v1.addWidget(aws['dc_gain'])
        aws['dc_gain'].set_log_increment()
        self.v2.addWidget(aws["output_channel"])
        # self.v2.addWidget(aws["tf_type"])
        self.button_tf = AnalogTfSpec(self)
        self.v2.addWidget(self.button_tf)

#        aws['tf_curve'].hide()
        self.setTitle('main attributes')
        for v in self.v1, self.v2:
            v.setSpacing(9)

    def change_analog_tf(self):
        self.button_tf.change_analog_tf()


class SweepOutputProperties(QtGui.QGroupBox):
    def __init__(self, parent):
        super(SweepOutputProperties, self).__init__(parent)
        self.parent = parent
        aws = self.parent.attribute_widgets
        self.layout = QtGui.QHBoxLayout(self)
        self.v1 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v1)
        self.v2 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v2)
        self.v1.addWidget(aws["sweep_frequency"])
        self.v1.addWidget(aws['sweep_amplitude'])
        self.v2.addWidget(aws["sweep_offset"])
        self.v2.addWidget(aws["sweep_waveform"])
        aws['is_sweepable'].hide()
        self.setTitle("sweep attributes")


class WidgetManual(QtGui.QWidget):
    def __init__(self, parent):
        super(WidgetManual, self).__init__(parent)
        self.parent = parent
        self.layout = QtGui.QVBoxLayout(self)
        self.p = parent.parent.attribute_widgets["p"]
        self.i = parent.parent.attribute_widgets["i"]
        self.p.label.setText('p [1] ')
        self.i.label.setText('i [Hz]')
        self.p.label.setFixedWidth(24)
        self.i.label.setFixedWidth(24)
        # self.p.adjustSize()
        # self.i.adjustSize()

        for prop in self.p, self.i:
            prop.widget.set_log_increment()

        self.p.set_horizontal()
        self.i.set_horizontal()
        self.layout.addWidget(self.p)
        self.layout.addWidget(self.i)
        # self.i.label.setMinimumWidth(6)

class WidgetAssisted(QtGui.QWidget):
    def __init__(self, parent):
        super(WidgetAssisted, self).__init__(parent)
        self.parent = parent
        self.layout = QtGui.QHBoxLayout(self)
        self.v1 = QtGui.QVBoxLayout()
        self.v2 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v1)
        self.layout.addLayout(self.v2)
        self.desired = parent.parent.attribute_widgets["unity_gain_desired"]
        self.desired.set_log_increment()
        self.analog_filter = parent.parent.attribute_widgets["analog_filter"]
        #self.analog_filter.set_horizontal()
        # self.analog_filter.layout_v.setSpacing(0)
        # self.analog_filter.layout_v.setContentsMargins(0, 0, 0, 0)
        self.analog_filter.set_max_cols(2)
        self.v1.addWidget(self.desired)
        self.v2.addWidget(self.analog_filter)

class PidProperties(QtGui.QGroupBox):
    def __init__(self, parent):
        super(PidProperties, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        aws = self.parent.attribute_widgets
        self.layout = QtGui.QHBoxLayout(self)
        self.v1 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v1)
        self.v2 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v2)

        self.radio_group = QtGui.QButtonGroup()
        self.manual = QtGui.QRadioButton('manual design')
        self.assisted = QtGui.QRadioButton('assisted design')
        self.radio_group.addButton(self.manual)
        self.radio_group.addButton(self.assisted)
        self.assisted.clicked.connect(self.toggle_mode)
        self.manual.clicked.connect(self.toggle_mode)

        self.manual_widget = WidgetManual(self)
        self.v1.addWidget(self.manual)
        self.v1.addWidget(self.manual_widget)
        # self.col3.addWidget(aws["tf_filter"])

        self.assisted_widget = WidgetAssisted(self)
        self.v2.insertWidget(0, self.assisted)
        self.v2.addWidget(self.assisted_widget)
        self.v2.addStretch(5)

        self.setTitle("Pid control")

        for v in (self.v1, self.v2, self.layout):
            v.setSpacing(0)
            v.setContentsMargins(5, 1, 0, 0)

    def toggle_mode(self): # button clicked
        if self.manual.isChecked():
            self.module.assisted_design = False
        else:
            self.module.assisted_design = True

    def set_assisted(self):
        self.manual_widget.setEnabled(False)
        self.assisted_widget.setEnabled(True)

    def set_manual(self):
        self.manual_widget.setEnabled(True)
        self.assisted_widget.setEnabled(False)

class PostFiltering(QtGui.QGroupBox):
    def __init__(self, parent):
        super(PostFiltering, self).__init__(parent)
        self.parent = parent
        aws = self.parent.attribute_widgets
        self.layout = QtGui.QVBoxLayout(self)

        aws = self.parent.attribute_widgets
        self.layout.addWidget(aws["additional_filter"])

        self.mod_layout = QtGui.QHBoxLayout()
        self.mod_layout.addWidget(aws["extra_module"])
        self.mod_layout.addWidget(aws["extra_module_state"])
        self.layout.addLayout(self.mod_layout)
        self.layout.setSpacing(12)

        self.setTitle("post filtering")


class OutputSignalWidget(ModuleWidget):
    @property
    def name(self):
        return self.module.name

    @name.setter
    def name(self, value):
        return value # only way to modify widget name is to change output.display_name

    def change_analog_tf(self):
        self.main_props.change_analog_tf()

    def set_assisted_design(self, val):
        """
        Disable the corresponding buttons in the pid property section.
        """
        self.pid_props.blockSignals(True)
        self.pid_props.manual.setChecked(not val)
        self.pid_props.assisted.setChecked(val)
        self.pid_props.blockSignals(False)
        {True:self.pid_props.set_assisted, False:self.pid_props.set_manual}[val]()

    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.init_attribute_layout()
        for widget in self.attribute_widgets.values():
            self.main_layout.removeWidget(widget)
        self.upper_layout = QtGui.QHBoxLayout()
        self.main_layout.addLayout(self.upper_layout)
        self.col1 = QtGui.QVBoxLayout()
        self.col2 = QtGui.QVBoxLayout()
        self.col3 = QtGui.QVBoxLayout()
        self.col4 = QtGui.QVBoxLayout()
        self.upper_layout.addStretch(1)
        self.upper_layout.addLayout(self.col1)
        self.upper_layout.addStretch(1)
        self.upper_layout.addLayout(self.col2)
        self.upper_layout.addStretch(1)
        self.upper_layout.addLayout(self.col3)
        self.upper_layout.addStretch(1)
        self.upper_layout.addLayout(self.col4)
        self.upper_layout.addStretch(1)

        aws = self.attribute_widgets
        self.main_props = MainOutputProperties(self)
        self.col1.addWidget(self.main_props)
        self.col1.addStretch(5)

        self.sweep_props = SweepOutputProperties(self)
        self.col2.addWidget(self.sweep_props)
        self.col2.addStretch(5)

        self.pid_props = PidProperties(self)
        self.set_assisted_design(self.module.assisted_design)
        self.col3.addWidget(self.pid_props)

        self.col3.addStretch(5)

        self.post_props = PostFiltering(self)
        self.col4.addWidget(self.post_props)

        self.col4.addStretch(5)

        self.win = pg.GraphicsWindow(title="Amplitude")
        self.win_phase = pg.GraphicsWindow(title="Phase")
        self.plot_item = self.win.addPlot(title="Magnitude (dB)")
        self.plot_item_phase = self.win_phase.addPlot(title="Phase (deg)")
        self.plot_item.showGrid(y=True, x=True, alpha=1.)
        self.plot_item_phase.showGrid(y=True, x=True, alpha=1.)

        self.plot_item_phase.setXLink(self.plot_item)

        self.curve = self.plot_item.plot(pen='y')
        self.curve_phase = self.plot_item_phase.plot(pen=None, symbol='o', symbolSize=1)

        self.plot_item.setLogMode(x=True, y=True)
        self.plot_item_phase.setLogMode(x=True, y=None)
        self.curve.setLogMode(xMode=True, yMode=True)
        self.curve_phase.setLogMode(xMode=True, yMode=None)

        self.main_layout.addWidget(self.win)
        self.main_layout.addWidget(self.win_phase)
        self.update_transfer_function()

    def update_transfer_function(self):
        """
        Updates the transfer function curve of the output.
        """
        freqs = self.module.tf_freqs()
        curve = self.module.transfer_function(freqs)
        self.curve.setData(freqs, abs(curve))
        self.curve_phase.setData(freqs, 180./np.pi*np.angle(curve))


class LockboxInputWidget(ModuleWidget):
    """
    A widget to represent a single lockbox input
    """
    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout(self)
        self.init_attribute_layout()

        self.win = pg.GraphicsWindow(title="Expected signal")
        self.plot_item = self.win.addPlot(title='Expected ' + self.module.name)
        self.plot_item.showGrid(y=True, x=True, alpha=1.)
        self.curve = self.plot_item.plot(pen='y')
        self.curve_slope = self.plot_item.plot(pen=pg.mkPen('b', width=5))
        self.symbol = self.plot_item.plot(pen='b', symbol='o')
        self.main_layout.addWidget(self.win)

        self.button_calibrate = QtGui.QPushButton('Calibrate')

        self.main_layout.addWidget(self.button_calibrate)
        self.button_calibrate.clicked.connect(self.module.calibrate)

    def hide_lock(self):
        self.curve_slope.setData([], [])
        self.symbol.setData([], [])
        self.plot_item.enableAutoRange(enable=True)

    def show_lock(self, input, variable_value):
        signal = self.module.expected_signal(variable_value)
        slope = self.module.expected_slope(variable_value)
        dx = 1
        self.plot_item.enableAutoRange(enable=False)
        self.curve_slope.setData([variable_value - dx, variable_value + dx],
                                 [signal - slope * dx, signal + slope*dx])
        self.symbol.setData([variable_value], [signal])

    def show_graph(self, x, y):
        """
        x, y are two 1D arrays.
        """
        self.curve.setData(x, y)

class InputsWidget(QtGui.QWidget):
    """
    A widget to represent all input signals on the same tab
    """
    name = 'inputs'
    def __init__(self, all_sig_widget):
        self.all_sig_widget = all_sig_widget
        self.lb_widget = self.all_sig_widget.lb_widget
        super(InputsWidget, self).__init__(all_sig_widget)
        self.layout = QtGui.QHBoxLayout(self)
        self.input_widgets = []
        #self.layout.addStretch(1)
        for signal in self.lb_widget.module.inputs:
            self.add_input(signal)
        #self.layout.addStretch(1)

    def remove_input(self, input):
        if input.widget in self.input_widgets:
            input.widget.hide()
            self.input_widgets.remove(input.widget)
            input.widget.deleteLater()

    def add_input(self, input):
        widget = input.create_widget()
        self.input_widgets.append(widget)
        self.layout.addWidget(widget, stretch=3)


class PlusTab(QtGui.QWidget):
    name = '+'


class MyTabBar(QtGui.QTabBar):
    def tabSizeHint(self, index):
        """
        Tab '+' and 'inputs' are smaller since they don't have a close button
        """
        size = super(MyTabBar, self).tabSizeHint(index)
        #if index==0 or index==self.parent().count() - 1:
        #    return QtCore.QSize(size.width() - 15, size.height())
        #else:
        return size

class AllSignalsWidget(QtGui.QTabWidget):
    """
    A tab widget combining all inputs and outputs of the lockbox
    """
    def __init__(self, lockbox_widget):
        super(AllSignalsWidget, self).__init__()
        self.tab_bar = MyTabBar()
        self.setTabBar(self.tab_bar)
        self.setTabsClosable(True)
        self.tabBar().setSelectionBehaviorOnRemove(QtGui.QTabBar.SelectLeftTab) # otherwise + tab could be selected by
        # removing previous tab
        self.output_widgets = []
        self.lb_widget = lockbox_widget
        self.inputs_widget = InputsWidget(self)
        self.addTab(self.inputs_widget, "inputs")
        self.tabBar().tabButton(0, QtGui.QTabBar.RightSide).resize(0, 0) # hide "close" for "inputs" tab
        self.tab_plus = PlusTab()  # dummy widget that will never be displayed
        self.addTab(self.tab_plus, "+")
        self.tabBar().tabButton(self.count() - 1, QtGui.QTabBar.RightSide).resize(0, 0)  # hide "close" for "+" tab
        for signal in self.lb_widget.module.outputs:
            self.add_output(signal)
        self.currentChanged.connect(self.tab_changed)
        self.tabCloseRequested.connect(self.close_tab)
        self.update_output_names()

    def tab_changed(self, index):
        if index==self.count()-1: # tab "+" clicked
            self.lb_widget.module.add_output()
            self.setCurrentIndex(self.count()-2) # bring created output tab on top

    def close_tab(self, index):
        lockbox = self.lb_widget.module
        lockbox.remove_output(lockbox.outputs[index - 1])

    ## Output Management
    def add_output(self, signal):
        """
        signal is an instance of OutputSignal
        """
        widget = signal.create_widget()
        self.output_widgets.append(widget)
        self.insertTab(self.count() - 1, widget, widget.name)

    def remove_output(self, output):
        tab_nr = self.output_widgets.index(output.widget) + 1  # count "inputs" tab
        if output.widget in self.output_widgets:
            output.widget.hide()
            self.output_widgets.remove(output.widget)
            self.removeTab(tab_nr)
            output.widget.deleteLater()

    def update_output_names(self):
        for index in range(self.count()):
            widget = self.widget(index)
            self.setTabText(index, widget.name)

    ## Input Management
    def add_input(self, input):
        self.inputs_widget.add_input(input)

    def remove_input(self, input):
        self.inputs_widget.remove_input(input)

class MyCloseButton(QtGui.QPushButton):
    def __init__(self, parent=None):
        super(MyCloseButton, self).__init__(parent)
        style = APP.style()
        close_icon = style.standardIcon(QtGui.QStyle.SP_TitleBarCloseButton)
        self.setIcon(close_icon)
        self.setFixedHeight(16)
        self.setFixedWidth(16)


class LockboxStageWidget(ModuleWidget):
    """
    A widget representing a single lockbox stage
    """
    @property
    def name(self):
        return self.module.name

    @name.setter
    def name(self, value):
        return value  # only way to modify widget name is to change output.display_name

    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout(self)
        self.init_attribute_layout()
        for name, attr in self.attribute_widgets.items():
            self.attribute_layout.removeWidget(attr)
        self.lay_h1 = QtGui.QHBoxLayout()
        self.main_layout.addLayout(self.lay_h1)
        self.lay_v1 = QtGui.QVBoxLayout()
        self.lay_h1.addLayout(self.lay_v1)
        self.lay_v2 = QtGui.QVBoxLayout()
        self.lay_h1.addLayout(self.lay_v2)
        aws = self.attribute_widgets
        self.lay_v1.addWidget(aws['name'])
        self.lay_v1.addWidget(aws['input'])
        self.lay_v2.addWidget(aws['duration'])
        self.lay_v2.addWidget(aws['variable_value'])
        self.main_layout.addWidget(aws['output_on'])

        self.main_layout.addWidget(aws['function_call'])

        self.button_goto = QtGui.QPushButton('Goto stage')
        self.button_goto.clicked.connect(self.module.setup)
        self.main_layout.addWidget(self.button_goto)

    def create_title_bar(self):
        super(LockboxStageWidget, self).create_title_bar()
        self.close_button = MyCloseButton(self)
        self.close_button.clicked.connect(self.close)
        self.close_button.move(self.width() - self.close_button.width(), self.title_pos[1] + 8)

    def resizeEvent(self, evt):
        super(LockboxStageWidget, self).resizeEvent(evt)
        self.close_button.move(evt.size().width() - self.close_button.width(), self.title_pos[1])

    def close(self):
        self.module.parent.remove_stage(self.module)

    def show_lock(self):
        self.parent().parent().set_button_green(self.button_goto)



class LockboxSequenceWidget(ModuleWidget):
    """
    A widget to represent all lockbox stages
    """
    def init_gui(self):
        self.main_layout = QtGui.QHBoxLayout(self)
        self.init_attribute_layout() # eventhough, I don't think there's any attribute
        self.stage_widgets = []
        self.button_add = QtGui.QPushButton('+')
        self.button_add.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Expanding)
        self.button_add.setMinimumHeight(60)
        for stage in self.module.stages:
            self.add_stage(stage)
        self.button_add.clicked.connect(self.module.add_stage)
        self.main_layout.addWidget(self.button_add)
        self.main_layout.addStretch(2)

    def add_stage(self, stage):
        widget = stage.create_widget()
        self.stage_widgets.append(widget)
        self.main_layout.insertWidget(self.main_layout.indexOf(self.button_add), widget)
        return stage

    def remove_stage(self, stage):
        if stage.widget in self.stage_widgets:
            stage.widget.hide()
            self.stage_widgets.remove(stage.widget)
            self.main_layout.removeWidget(stage.widget)
            stage.widget.deleteLater()

    def update_stage_names(self):
        for widget in self.stage_widgets:
            widget.set_title(widget.name)


class LockboxWidget(ModuleWidget):
    """
    The LockboxWidget combines the lockbox submodules widget: model, inputs, outputs, lockbox_control
    """
    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.init_attribute_layout()
        self.button_lock = QtGui.QPushButton("Lock")
        self.button_unlock = QtGui.QPushButton("Unlock")
        self.button_green = self.button_unlock
        self.set_button_green(self.button_green)
        self.button_lock.clicked.connect(self.module.lock)
        self.attribute_layout.addWidget(self.button_lock)
        self.attribute_layout.addWidget(self.button_unlock)
        self.button_unlock.clicked.connect(self.module.unlock)
        self.button_sweep = QtGui.QPushButton("Sweep")
        self.button_sweep.clicked.connect(self.module.sweep)
        self.attribute_layout.addWidget(self.button_sweep)
        self.button_calibrate_all = QtGui.QPushButton("Calibrate all inputs")
        self.attribute_layout.addWidget(self.button_calibrate_all)
        self.button_calibrate_all.clicked.connect(self.module.calibrate_all)

        self.model_widget = self.module.model.create_widget()
        self.main_layout.addWidget(self.model_widget)
        self.all_sig_widget = AllSignalsWidget(self)
        self.main_layout.addWidget(self.all_sig_widget)
        self.sequence_widget = self.module.sequence.create_widget()
        self.main_layout.addWidget(self.sequence_widget)
        self.main_layout.addStretch(5)
        self.setLayout(self.main_layout)

    ## Input Management
    def add_input(self, input):
        """
        Adds an input to the widget
        """
        self.all_sig_widget.add_input(input)

    def remove_input(self, input):
        """
        Remove an input to the widget
        """
        self.all_sig_widget.remove_input(input)

    ## Output Management
    def update_output_names(self):
        """
        Refresh all output name tabs in the widget
        """
        self.all_sig_widget.update_output_names()

    def add_output(self, output):
        """
        Adds an output to the widget
        """
        self.all_sig_widget.add_output(output)

    def remove_output(self, output):
        """
        Removes an output to the widget
        """
        self.all_sig_widget.remove_output(output)

    ## Model management
    def change_model(self, model):
        """
        displays the new model
        """
        self.model_widget.hide()
        self.main_layout.removeWidget(self.model_widget)
        self.model_widget.deleteLater()
        widget = model.create_widget()
        self.model_widget = widget
        self.main_layout.insertWidget(1, widget)

    ## Sequence Management
    def add_stage(self, stage):
        """
        Adds a new stage to the widget
        """
        self.sequence_widget.add_stage(stage)

    def remove_stage(self, stage):
        """
        Removes a stage to the model
        """
        self.sequence_widget.remove_stage(stage)

    def set_state(self, val):
        if val=='unlock':
            self.set_button_green(self.button_unlock)
            self.hide_lock_points()
            return
        if val=='sweep':
            self.hide_lock_points()
            self.set_button_green(self.button_sweep)
            return
        index = self.module.stage_names.index(val)
        self.set_button_green(self.sequence_widget.stage_widgets[index].button_goto)
        self.show_lock(val)

    def set_button_green(self, button):
        """
        Only one colored button can exist at a time
        """
        self.button_green.setStyleSheet("")
        button.setStyleSheet("background-color:green")
        self.button_green = button

    def show_lock(self, stage):
        """
        The button of the stage widget becomes green, the expected signal graph of input show the lock point and slope.
        """
        self.hide_lock_points()
        if isinstance(stage, basestring):
            stage = self.module.get_stage(stage)
        if stage is not None:
            if stage.widget is not None:
                stage.widget.show_lock()
            input_widget = self.module.get_input(stage.input).widget
            if input_widget is not None:
                input_widget.show_lock(stage.input, stage.variable_value)

    def hide_lock_points(self):
        """
        make sure all input graphs are not displaying any setpoints and slopes
        """
        for input_widget in self.all_sig_widget.inputs_widget.input_widgets:
            input_widget.hide_lock()



   #def update_stage_names(self):
    #    """
    #    Refresh all stage tabs in the widget
    #    """
    #    self.sequence_widget.update_output_names()