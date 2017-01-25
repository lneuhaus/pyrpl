"""
A widget for the spectrum analyzer
"""
from .base_module_widget import ModuleWidget

from PyQt4 import QtCore, QtGui
import pyqtgraph as pg
from time import time
import numpy as np

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

