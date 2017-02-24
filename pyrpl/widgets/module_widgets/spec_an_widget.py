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

        self.button_single = QtGui.QPushButton("Run single")
        self.button_single.clicked.connect(self.run_single_clicked)

        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.button_continuous.clicked.connect(self.run_continuous_clicked)

        self.button_restart_averaging = QtGui.QPushButton('Restart averaging')
        self.button_restart_averaging.clicked.connect(self.module.restart_averaging)

        self.button_save = QtGui.QPushButton("Save curve")
        self.button_save.clicked.connect(self.module.save_curve)

        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_restart_averaging)
        self.button_layout.addWidget(self.button_save)
        self.main_layout.addLayout(self.button_layout)

        self.running = False
        self.attribute_changed.connect(self.module.restart_averaging)

        self.attribute_widgets["rbw_auto"].value_changed.connect(self.update_rbw_visibility)
        self.update_rbw_visibility()

    def update_attribute_by_name(self, name, new_value_list):
        super(SpecAnWidget, self).update_attribute_by_name(name, new_value_list)
        if name in ['running_continuous',]:
            self.update_running_buttons()

    def update_running_buttons(self):
        """
        Change text of Run continuous button and visibility of run single button
        according to module.running_continuous
        """
        if self.module.current_average>0:
            number_str = ' (' + str(self.module.current_average) + ")"
        else:
            number_str = ""
        if self.module.running_continuous:
            if self.module.current_average >= self.module.avg:
                # shows a plus sign when number of averages is available
                number_str = number_str[:-1] + '+)'
            self.button_continuous.setText("Stop" + number_str)
            self.button_single.setText("Run single")
            self.button_single.setEnabled(False)
        else:
            if self.module.running_single:
                self.button_continuous.setText("Run continuous")
                self.button_single.setText("Stop" + number_str)
                self.button_single.setEnabled(True)
            else:
                self.button_continuous.setText("Run continuous" + number_str)
                self.button_single.setText("Run single")
                self.button_single.setEnabled(True)

    def update_rbw_visibility(self):
        self.attribute_widgets["rbw"].widget.setEnabled(not self.module.rbw_auto)

    def autoscale_display(self):
        """Autoscale pyqtgraph"""
        self.plot_item.autoRange()

    def run_continuous_clicked(self):
        """
        Toggles the button run_continuous to stop or vice versa and starts the acquisition timer
        """

        if str(self.button_continuous.text()).startswith("Run continuous"):
            self.module.run_continuous()
        else:
            self.module.stop()

    def run_single_clicked(self):
        if str(self.button_single.text()).startswith('Stop'):
            self.module.stop()
        else:
            self.module.run_single()

    def run_single_clicked_old(self):
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
        Displays all active channels on the graph.
        """
        if self.module.data is not None:
            self.curve.setData(self.module.frequencies, self.module.data_to_dBm(self.module.data))
            self.curve.setVisible(True)
        else:
            self.curve.setVisible(False)
        self.update_running_buttons()
