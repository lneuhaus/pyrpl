"""
A widget for the spectrum analyzer
"""
import logging
logger = logging.getLogger(name=__name__)
from PyQt4 import QtCore, QtGui
import pyqtgraph as pg
from time import time
import numpy as np
from .base_module_widget import ModuleWidget
from ...errors import NotReadyError

APP = QtGui.QApplication.instance()


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
        self.main_layout.addWidget(self.win)

        self.plot_item = self.win.addPlot(title="PSD")
        self.curve = self.plot_item.plot(pen='m')

        #self.run_avg_widget = self.module.__class__.avg._create_widget(
        #    self.module)
        #self.curve_name_widget = \
        #    self.module.__class__.curve_name._create_widget(
        #    self.module)



        self.button_single = QtGui.QPushButton("Run single")
        self.button_single.clicked.connect(self.run_single_clicked)

        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.button_continuous.clicked.connect(self.run_continuous_clicked)

        self.button_restart_averaging = QtGui.QPushButton('Restart averaging')
        self.button_restart_averaging.clicked.connect(self.module.stop)

        self.button_save = QtGui.QPushButton("Save curve")
        self.button_save.clicked.connect(self.module.save_curve)

        aws = self.attribute_widgets
        self.attribute_layout.removeWidget(aws["avg"])
        self.attribute_layout.removeWidget(aws["curve_name"])

        self.button_layout.addWidget(aws["avg"])
        self.button_layout.addWidget(aws["curve_name"])
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_restart_averaging)
        self.button_layout.addWidget(self.button_save)
        self.main_layout.addLayout(self.button_layout)

        # Not sure why the stretch factors in button_layout are not good by
        # default...
        self.button_layout.setStretchFactor(self.button_single, 1)
        self.button_layout.setStretchFactor(self.button_continuous, 1)
        self.button_layout.setStretchFactor(self.button_restart_averaging, 1)
        self.button_layout.setStretchFactor(self.button_save, 1)
        # self.button_layout.setStretchFactor(self.run_avg_widget, 1)
        # self.button_layout.setStretchFactor(self.curve_name_widget, 1)

        # self.running = False
        # self.attribute_changed.connect(self.module.restart_averaging)

        ##### self.attribute_widgets["rbw_auto"].value_changed.connect(
        #####     self.update_rbw_visibility)
        ##### self.update_rbw_visibility()

    def update_attribute_by_name(self, name, new_value_list):
        super(SpecAnWidget, self).update_attribute_by_name(name, new_value_list)
        if name in ['running_state',]:
            self.update_running_buttons()

    def update_running_buttons(self):
        """
        Change text of Run continuous button and visibility of run single button
        according to module.running_continuous
        """
        if self.module.current_avg>0:
            number_str = ' (' + str(self.module.current_avg) + ")"
        else:
            number_str = ""
        if self.module.running_state == 'running_continuous':
            if self.module.current_avg >= self.module.avg:
                # shows a plus sign when number of averages is available
                number_str = number_str[:-1] + '+)'
            self.button_continuous.setText("Pause" + number_str)
            self.button_single.setText("Run single")
            self.button_single.setEnabled(False)
        else:
            if self.module.running_state == "running_single":
                self.button_continuous.setText("Run continuous")
                self.button_single.setText("Stop" + number_str)
                self.button_single.setEnabled(True)
            else:
                self.button_continuous.setText("Run continuous" + number_str)
                self.button_single.setText("Run single")
                self.button_single.setEnabled(True)

    #### def update_rbw_visibility(self):
    ####     self.attribute_widgets["rbw"].widget.setEnabled(not
    #### self.module.rbw_auto)

    def autoscale_display(self):
        """Autoscale pyqtgraph"""
        self.plot_item.autoRange()

    def run_continuous_clicked(self):
        """
        Toggles the button run_continuous to stop or vice versa and starts the acquisition timer
        """

        if str(self.button_continuous.text()).startswith("Run continuous"):
            self.module.continuous()
        else:
            self.module.pause()

    def run_single_clicked(self):
        if str(self.button_single.text()).startswith('Stop'):
            self.module.stop()
        else:
            self.module.single_async()

    def display_curve(self, datas):
        """
        Displays all active channels on the graph.
        """
        self.curve.setData(datas[0],
                           self.module.data_to_dBm(datas[1]))
        self.curve.setVisible(True)
        #else:
        #    self.curve.setVisible(False)
        self.update_running_buttons()
