"""
The control panel above the plotting area allows to manipulate the following
attributes specific to the :class:`~pyrpl.hardware_modules.scope.Scope`:

* :attr:`~.Scope.ch1_active`/:attr:`~.Scope.ch2_active`: Hide/show the trace
  corresponding to ch1/ch2.
* :attr:`~.Scope.input1`/:attr:`~.Scope.input2`: Choose the input among a
  list of possible signals. Internal signals can be referenced by their
  symbolic name e.g. :code:`lockbox.outputs.output1`.
* :attr:`~.Scope.threshold`: The voltage threshold for the scope trigger.
* :attr:`~.Scope.hysteresis`: Hysteresis for the scope trigger, i.e. the scope
  input signal must exceed the :attr:`~.Scope.threshold` value by more than
  the hysteresis value to generate a trigger event.
* :attr:`~.Scope.duration`: The full duration of the scope trace to acquire,
  in units of seconds.
* :attr:`~.Scope.trigger_delay`: The delay beteween trigger event and the
  center of the trace.
* :attr:`~.Scope.trigger_source`: The channel to use as trigger input.
* :attr:`~.Scope.average`: Enables "averaging" a.k.a. "high-resolution" mode,
  which averages all data samples acquired at the full sampling rate between
  two successive points of the trace. If disabled, only a sample of the
  full-rate signal is shown as the trace. The averaging mode corresponds to a
  moving-average filter with a cutoff frequency of
  :attr:`~.pyrpl.hardware_modules.scope.Scope.sampling_time` :math:`^{-1} = 2^{14}/\\mathrm{duration}`
  in units of Hz.
* :attr:`~.Scope.xy_mode`: If selected, channel 2 is plotted as a function of
  channel 1 (instead of channels 1 and 2 as a function of time).
* :code:`Trigger mode` (internally represented by :attr:`~.Scope.rolling_mode`):

  * :code:`Normal` is used for triggered acquisition.
  * :code:`Untriggered (rolling)` is used for continuous acquisition without
    requiring a trigger signal, where the traces "roll" through the plotting
    area from right to left in real-time. The rolling mode does not allow for
    trace averaging nor durations below 0.1 s.
"""
import pyqtgraph as pg
from qtpy import QtCore, QtGui, QtWidgets
import numpy as np
from ...errors import NotReadyError
from .base_module_widget import ModuleWidget
from .acquisition_module_widget import AcquisitionModuleWidget


class ScopeWidget(AcquisitionModuleWidget):
    """
    Widget for scope
    """
    def init_gui(self):
        """
        sets up all the gui for the scope.
        """
        self.datas = [None, None]
        self.times = None
        self.ch_color = ('green', 'red', 'blue')
        self.ch_transparency = (255, 255, 255)  # 0 is transparent, 255 is not  # deactivated transparency for speed reasons
        #self.module.__dict__['curve_name'] = 'scope'
        #self.main_layout = QtWidgets.QVBoxLayout()
        self.init_main_layout(orientation="vertical")
        self.init_attribute_layout()
        aws = self.attribute_widgets

        self.layout_channels = QtWidgets.QVBoxLayout()
        self.layout_ch1 = QtWidgets.QHBoxLayout()
        self.layout_ch2 = QtWidgets.QHBoxLayout()
        self.layout_math = QtWidgets.QHBoxLayout()
        self.layout_channels.addLayout(self.layout_ch1)
        self.layout_channels.addLayout(self.layout_ch2)
        self.layout_channels.addLayout(self.layout_math)

        self.attribute_layout.removeWidget(aws['xy_mode'])

        self.attribute_layout.removeWidget(aws['ch1_active'])
        self.attribute_layout.removeWidget(aws['input1'])
        self.attribute_layout.removeWidget(aws['threshold'])

        self.layout_ch1.addWidget(aws['ch1_active'])
        self.layout_ch1.addWidget(aws['input1'])
        self.layout_ch1.addWidget(aws['threshold'])
        aws['ch1_active'].setStyleSheet("color: %s" % self.ch_color[0])

        self.attribute_layout.removeWidget(aws['ch2_active'])
        self.attribute_layout.removeWidget(aws['input2'])
        self.attribute_layout.removeWidget(aws['hysteresis'])
        aws['ch2_active'].setStyleSheet("color: %s" % self.ch_color[1])

        self.layout_ch2.addWidget(aws['ch2_active'])
        self.layout_ch2.addWidget(aws['input2'])
        self.layout_ch2.addWidget(aws['hysteresis'])

        self.layout_math.addWidget(aws['ch_math_active'])
        aws['ch_math_active'].setStyleSheet("color: %s" % self.ch_color[2])
        self.layout_math.addWidget(aws['math_formula'])

        self.attribute_layout.addLayout(self.layout_channels)

        self.attribute_layout.removeWidget(aws['duration'])
        self.attribute_layout.removeWidget(aws['trigger_delay'])
        self.layout_duration = QtWidgets.QVBoxLayout()
        self.layout_duration.addWidget(aws['duration'])
        self.layout_duration.addWidget(aws['trigger_delay'])
        self.attribute_layout.addLayout(self.layout_duration)

        self.attribute_layout.removeWidget(aws['trigger_source'])
        self.attribute_layout.removeWidget(aws['average'])
        self.layout_misc = QtWidgets.QVBoxLayout()
        self.layout_misc.addWidget(aws['trigger_source'])
        self.layout_misc.addWidget(aws['average'])
        self.attribute_layout.addLayout(self.layout_misc)

        #self.attribute_layout.removeWidget(aws['curve_name'])

        self.button_layout = QtWidgets.QHBoxLayout()

        aws = self.attribute_widgets
        self.attribute_layout.removeWidget(aws["trace_average"])
        self.attribute_layout.removeWidget(aws["curve_name"])
        self.button_layout.addWidget(aws["xy_mode"])
        self.button_layout.addWidget(aws["trace_average"])
        self.button_layout.addWidget(aws["curve_name"])


        #self.setLayout(self.main_layout)
        self.setWindowTitle("Scope")
        self.win = pg.GraphicsLayoutWidget(title="Scope")
        self.plot_item = self.win.addPlot(title="Scope")
        self.plot_item.showGrid(y=True, alpha=1.)


        #self.button_single = QtWidgets.QPushButton("Run single")
        #self.button_continuous = QtWidgets.QPushButton("Run continuous")
        #self.button_save = QtWidgets.QPushButton("Save curve")

        self.curves = [self.plot_item.plot(pen=(QtGui.QColor(color).red(),
                                                QtGui.QColor(color).green(),
                                                QtGui.QColor(color).blue()
                                                ))
                                                #,trans)) \
                       for color, trans in zip(self.ch_color,
                                               self.ch_transparency)]
        self.main_layout.addWidget(self.win, stretch=10)


        #self.button_layout.addWidget(self.button_single)
        #self.button_layout.addWidget(self.button_continuous)
        #self.button_layout.addWidget(self.button_save)
        #self.button_layout.addWidget(aws['curve_name'])
        #aws['curve_name'].setMaximumWidth(250)
        self.main_layout.addLayout(self.button_layout)

        #self.button_single.clicked.connect(self.run_single_clicked)
        #self.button_continuous.clicked.connect(self.run_continuous_clicked)
        #self.button_save.clicked.connect(self.save_clicked)

        self.rolling_group = QtWidgets.QGroupBox("Trigger mode")
        self.checkbox_normal = QtWidgets.QRadioButton("Normal")
        self.checkbox_untrigged = QtWidgets.QRadioButton("Untrigged (rolling)")
        self.checkbox_normal.setChecked(True)
        self.lay_radio = QtWidgets.QVBoxLayout()
        self.lay_radio.addWidget(self.checkbox_normal)
        self.lay_radio.addWidget(self.checkbox_untrigged)
        self.rolling_group.setLayout(self.lay_radio)
        self.attribute_layout.insertWidget(
            list(self.attribute_widgets.keys()).index("trigger_source"),
            self.rolling_group)
        self.checkbox_normal.clicked.connect(self.rolling_mode_toggled)
        self.checkbox_untrigged.clicked.connect(self.rolling_mode_toggled)
        #self.update_rolling_mode_visibility()
        self.attribute_widgets['duration'].value_changed.connect(
            self.update_rolling_mode_visibility)

        super(ScopeWidget, self).init_gui()
        # since trigger_mode radiobuttons is not a regular attribute_widget,
        # it is not synced with the module at creation time.
        self.update_running_buttons()
        self.update_rolling_mode_visibility()
        self.rolling_mode = self.module.rolling_mode
        self.attribute_layout.addStretch(1)
        # Not sure why the stretch factors in button_layout are not good by
        # default...
        #self.button_layout.setStretchFactor(self.button_single, 1)
        #self.button_layout.setStretchFactor(self.button_continuous, 1)
        #self.button_layout.setStretchFactor(self.button_save, 1)

    def update_attribute_by_name(self, name, new_value_list):
        """
        Updates all attributes on the gui when their values have changed.
        """
        super(ScopeWidget, self).update_attribute_by_name(name, new_value_list)
        if name in ['rolling_mode', 'duration']:
            self.rolling_mode = self.module.rolling_mode
            self.update_rolling_mode_visibility()
        if name in ['_running_state',]:
            self.update_running_buttons()

    def display_channel_obsolete(self, ch):
        """
        Displays channel ch (1 or 2) on the graph
        :param ch:
        """
        try:
                self.datas[ch-1] = self.module.trace(ch)
                self.times = self.module.times
                self.curves[ch-1].setData(self.times,
                                          self.datas[ch-1])
        except NotReadyError:
            pass

    def change_ownership(self):
        """
        For some reason the visibility of the rolling mode panel is not updated
        when the scope becomes free again unless we ask for it explicitly...
        """
        super(ScopeWidget, self).change_ownership()
        self.update_rolling_mode_visibility()

    def display_curve(self, list_of_arrays):
        """
        Displays all active channels on the graph.
        """
        times, (ch1, ch2) = list_of_arrays
        disp = [(ch1, self.module.ch1_active), (ch2, self.module.ch2_active)]
        if self.module.xy_mode:
            self.curves[0].setData(ch1, ch2)
            self.curves[0].setVisible(True)
            self.curves[1].setVisible(False)
        else:
            for ch, (data, active) in enumerate(disp):
                if active:
                    self.curves[ch].setData(times, data)
                    self.curves[ch].setVisible(True)
                else:
                    self.curves[ch].setVisible(False)
            if self.module.ch_math_active:
                # catch numpy warnings instead of printing them
                # https://stackoverflow.com/questions/15933741/how-do-i-catch-a-numpy-warning-like-its-an-exception-not-just-for-testing
                backup_np_err = np.geterr()
                np.seterr(all='ignore')
                try:
                    math_data = eval(self.module.math_formula,
                       dict(ch1=ch1, ch2=ch2, np=np, times=times))
                except:
                    pass
                else:
                    self.curves[2].setData(times, math_data)
                np.seterr(**backup_np_err)
                self.curves[2].setVisible(True)
            else:
                self.curves[2].setVisible(False)
        self.update_current_average() # to update the number of averages

    def set_rolling_mode(self):
        """
        Set rolling mode on or off based on the module's attribute
        "rolling_mode"
        """
        self.rolling_mode = self.module.rolling_mode

    def rolling_mode_toggled(self):
        self.module.rolling_mode = self.rolling_mode

    @property
    def rolling_mode(self):
        return ((self.checkbox_untrigged.isChecked()) and self.rolling_group.isEnabled())

    @rolling_mode.setter
    def rolling_mode(self, val):
        if val:
            self.checkbox_untrigged.setChecked(True)
        else:
            self.checkbox_normal.setChecked(True)
        return val

    def update_rolling_mode_visibility(self):
        """
        Hide rolling mode checkbox for duration < 100 ms
        """
        self.rolling_group.setEnabled(self.module._rolling_mode_allowed())
        self.attribute_widgets['trigger_source'].widget.setEnabled(
            not self.rolling_mode)
        self.attribute_widgets['threshold'].widget.setEnabled(
            not self.rolling_mode)
        self.attribute_widgets['hysteresis'].widget.setEnabled(
            not self.rolling_mode)
        single_enabled = (not self.module._is_rolling_mode_active()) and \
                            self.module.running_state!="running_continuous"
        self.button_single.setEnabled(single_enabled)

    def update_running_buttons(self):
        super(ScopeWidget, self).update_running_buttons()
        self.update_rolling_mode_visibility()

    def autoscale_x(self):
        """Autoscale pyqtgraph. The current behavior is to autoscale x axis
        and set y axis to  [-1, +1]"""
        if self.module.xy_mode:
            return
        if self.module._is_rolling_mode_active():
            mini = -self.module.duration
            maxi = 0
        else:
            mini = min(self.module.times)
            maxi = max(self.module.times)
        self.plot_item.setRange(xRange=[mini, maxi])
        self.plot_item.setRange(yRange=[-1,1])
        # self.plot_item.autoRange()

    def save_clicked(self):
        self.module.save_curve()
