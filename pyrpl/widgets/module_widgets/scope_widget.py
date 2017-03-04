"""
A widget for the scope module
"""
from pyrpl.errors import NotReadyError
from .base_module_widget import ModuleWidget

import pyqtgraph as pg
from PyQt4 import QtCore, QtGui
import numpy as np

APP = QtGui.QApplication.instance()


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
        #self.module.__dict__['curve_name'] = 'scope'
        self.main_layout = QtGui.QVBoxLayout()
        self.init_attribute_layout()
        aws = self.attribute_widgets

        self.layout_channels = QtGui.QVBoxLayout()
        self.layout_ch1 = QtGui.QHBoxLayout()
        self.layout_ch2 = QtGui.QHBoxLayout()
        self.layout_channels.addLayout(self.layout_ch1)
        self.layout_channels.addLayout(self.layout_ch2)


        self.attribute_layout.removeWidget(aws['ch1_active'])
        self.attribute_layout.removeWidget(aws['input1'])
        self.attribute_layout.removeWidget(aws['threshold_ch1'])

        self.layout_ch1.addWidget(aws['ch1_active'])
        self.layout_ch1.addWidget(aws['input1'])
        self.layout_ch1.addWidget(aws['threshold_ch1'])

        self.attribute_layout.removeWidget(aws['ch2_active'])
        self.attribute_layout.removeWidget(aws['input2'])
        self.attribute_layout.removeWidget(aws['threshold_ch2'])

        self.layout_ch2.addWidget(aws['ch2_active'])
        self.layout_ch2.addWidget(aws['input2'])
        self.layout_ch2.addWidget(aws['threshold_ch2'])

        self.attribute_layout.addLayout(self.layout_channels)

        self.attribute_layout.removeWidget(aws['duration'])
        self.attribute_layout.removeWidget(aws['trigger_delay'])
        self.layout_duration = QtGui.QVBoxLayout()
        self.layout_duration.addWidget(aws['duration'])
        self.layout_duration.addWidget(aws['trigger_delay'])
        self.attribute_layout.addLayout(self.layout_duration)

        self.attribute_layout.removeWidget(aws['trigger_source'])
        self.attribute_layout.removeWidget(aws['average'])
        self.layout_misc = QtGui.QVBoxLayout()
        self.layout_misc.addWidget(aws['trigger_source'])
        self.layout_misc.addWidget(aws['average'])
        self.attribute_layout.addLayout(self.layout_misc)

        #self.attribute_layout.removeWidget(aws['curve_name'])

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
        self.main_layout.addWidget(self.win, stretch=10)
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_save)
        #self.button_layout.addWidget(aws['curve_name'])
        #aws['curve_name'].setMaximumWidth(250)
        self.main_layout.addLayout(self.button_layout)

        self.button_single.clicked.connect(self.module.run.single)
        self.button_continuous.clicked.connect(self.run_continuous_clicked)
        self.button_save.clicked.connect(self.save_clicked)

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
        #self.update_rolling_mode_visibility()
        self.attribute_widgets['duration'].value_changed.connect(self.update_rolling_mode_visibility)

        # since trigger_mode radiobuttons is not a regular attribute_widget,
        # it is not synced with the module at creation time.
        self.update_running_buttons()
        self.update_rolling_mode_visibility()
        self.rolling_mode = self.module.run.rolling_mode

    def update_attribute_by_name(self, name, new_value_list):
        """
        Updates all attributes on the gui when their values have changed.
        """
        super(ScopeWidget, self).update_attribute_by_name(name, new_value_list)
        if name in ['rolling_mode', 'duration']:
            self.rolling_mode = self.module.run.rolling_mode
        if name in ['running_state',]:
            self.update_running_buttons()

    def update_running_buttons(self):
        """
        Change text of Run continuous button and visibility of run single
        button according to module.running_continuous
        """
        if self.module.run.running_state=="running_continuous":
            self.button_continuous.setText("Stop")
            self.button_single.setEnabled(False)
            self.button_single.setText("Run single")
        if self.module.run.running_state=="running_single":
            self.button_continuous.setText("Run continuous")
            self.button_single.setEnabled(True)
            self.button_single.setText("Stop")
        if self.module.run.running_state=="paused":
            self.button_continuous.setText("Run continuous")
            self.button_single.setEnabled(True)
            self.button_single.setText("Run single")
        if self.module.run.running_state=="stopped":
            self.button_continuous.setText("Run continuous")
            self.button_single.setEnabled(True)
            self.button_single.setText("Run single")

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

    def display_curves(self, list_of_arrays):
        """
        Displays all active channels on the graph.
        """
        times, ch1, ch2 = list_of_arrays
        for ch, data in enumerate([ch1, ch2]):
            if data is not None:
                self.curves[ch].setData(times, data)
                self.curves[ch].setVisible(True)
            else:
                self.curves[ch].setVisible(False)

    # currently not implemented?
    #def curve_display_done(self):
    #    """
    #    User may overwrite this function to implement custom functionality
    #    at each graphical update.
    #    :return:
    #    """
    #    pass

    def set_rolling_mode(self):
        """
        Set rolling mode on or off based on the module's attribute "rolling_mode"
        """
        self.rolling_mode = self.module.run.rolling_mode

    def run_continuous_clicked(self):
        """
        Toggles the button run_continuous to stop or vice versa and starts the acquisition timer
        """

        if str(self.button_continuous.text()) \
                == "Run continuous":
            self.module.run.continuous()
        else:
            self.module.run.stop()

    def rolling_mode_toggled(self):
        self.module.run.rolling_mode = self.rolling_mode

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
        return val

    def update_rolling_mode_visibility(self):
        """
        Hide rolling mode checkbox for duration < 100 ms
        """
        self.rolling_group.setEnabled(self.module.run._rolling_mode_allowed())
        self.attribute_widgets['trigger_source'].widget.setEnabled(
            not self.rolling_mode)
        self.attribute_widgets['threshold_ch1'].widget.setEnabled(
            not self.rolling_mode)
        self.attribute_widgets['threshold_ch2'].widget.setEnabled(
            not self.rolling_mode)
        self.button_single.setEnabled(not self.rolling_mode)

    def autoscale(self):
        """Autoscale pyqtgraph. The current behavior is to autoscale x axis
        and set y axis to  [-1, +1]"""
        #mini = np.nan
        #maxi = np.nan
        #for curve in self.curves:
        #    if curve.isVisible():
        #        mini = np.nanmin([self., mini])
        #        maxi = np.nanmax([curve.xData.max(), maxi])
        #if not np.isnan(mini):

        if self.module.run._is_rolling_mode_active():
            mini = -self.module.duration
            maxi = 0
        else:
            mini = min(self.module.times)
            maxi = max(self.module.times)
        self.plot_item.setRange(xRange=[mini,
                                        maxi])
        self.plot_item.setRange(yRange=[-1,1])
        # self.plot_item.autoRange()

    def save_clicked(self):
        self.module.run.save_curve()
