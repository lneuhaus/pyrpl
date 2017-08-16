from . import ModuleWidget

from qtpy import QtCore, QtWidgets


class CurrentAvgLabel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(CurrentAvgLabel, self).__init__(parent)
        self.main_lay = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_lay)
        self.label = QtWidgets.QLabel("current_avg")
        self.main_lay.addWidget(self.label)
        self.value_label = QtWidgets.QLabel("0 /")
        self.main_lay.addWidget(self.value_label)
        self.main_lay.addStretch(1)
        self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        self.main_lay.setContentsMargins(0,0,0,0)

    def set_value(self, val):
        self.value_label.setText(str(val) + ' /')


class AcquisitionModuleWidget(ModuleWidget):
    def init_gui(self):
        self.button_single = QtWidgets.QPushButton("Run single")
        self.button_single.clicked.connect(self.run_single_clicked)

        self.button_continuous = QtWidgets.QPushButton("Run continuous")
        self.button_continuous.clicked.connect(self.run_continuous_clicked)

        self.button_restart_averaging = QtWidgets.QPushButton(
            'Restart averaging')
        self.button_restart_averaging.clicked.connect(self.restart_clicked)

        self.button_save = QtWidgets.QPushButton("Save curve")
        self.button_save.clicked.connect(self.module.save_curve)

        self.current_avg_label = CurrentAvgLabel()

        aws = self.attribute_widgets
        self.attribute_layout.removeWidget(aws["trace_average"])
        self.attribute_layout.removeWidget(aws["curve_name"])

        self.button_layout.addWidget(self.current_avg_label)
        self.button_layout.addWidget(aws["trace_average"])
        self.button_layout.addWidget(aws["curve_name"])
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_restart_averaging)
        self.button_layout.addWidget(self.button_save)
        self.main_layout.addLayout(self.button_layout)

        self.button_layout.setStretchFactor(self.button_single, 1)
        self.button_layout.setStretchFactor(self.button_continuous, 1)
        self.button_layout.setStretchFactor(self.button_restart_averaging, 1)
        self.button_layout.setStretchFactor(self.button_save, 1)
        self.button_layout.addStretch(1)
        self.attribute_layout.setStretch(0, 0) # since widgets are all removed
        # and re-added, the stretch ends up on the left, so better cancel it
        # and make a new one at the end

    def run_single_clicked(self):
        if str(self.button_single.text()).startswith("Run single"):
            self.module.single_async()
        else:
            self.module.stop()

    def run_continuous_clicked(self):
        """
        Toggles the button run_continuous to stop or vice versa and starts
        he acquisition timer
        """

        if str(self.button_continuous.text()).startswith("Run continuous"):
            self.module.continuous()
        else:
            self.module.pause()

    def restart_clicked(self):
        old_running_state = self.module.running_state
        self.module.stop()
        if old_running_state in ["running_single", "running_continuous"]:
            self.module.running_state = old_running_state
        self.update_current_average()

    def update_current_average(self):
        self.current_avg_label.set_value(self.module.current_avg)

    def update_running_buttons(self):
        """
        Change text of Run continuous button and visibility of run single button
        according to module.running_continuous
        """
        self.update_current_average()
        if self.module.current_avg>0:
            number_str = ' (' + str(self.module.current_avg) + ")"
        else:
            number_str = ""
        if self.module.running_state == 'running_continuous':
            #if self.module.current_avg >= self.module.trace_average:
            #    # shows a plus sign when number of averages is available
            #    number_str = number_str[:-1] + '+)'
            self.button_continuous.setText("Pause")# + number_str)
            self.button_single.setText("Run single")
            self.button_single.setEnabled(False)
        else:
            if self.module.running_state == "running_single":
                self.button_continuous.setText("Run continuous")
                self.button_single.setText("Stop")# + number_str)
                self.button_single.setEnabled(True)
            else:
                self.button_continuous.setText("Run continuous")# + number_str)
                self.button_single.setText("Run single")
                self.button_single.setEnabled(True)
