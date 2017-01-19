"""
A widget for pid modules.
"""

from .base_module_widget import ModuleWidget

from PyQt4 import QtCore, QtGui

APP = QtGui.QApplication.instance()

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
        self.timer_ival.setInterval(1000)
        self.timer_ival.timeout.connect(self.update_ival)
        self.timer_ival.start()

    def update_ival(self):
        widget = self.attribute_widgets['ival']
        if self.isVisible(): # avoid unnecessary ssh traffic
            if not widget.editing():
                widget.update_widget(self.module.ival)