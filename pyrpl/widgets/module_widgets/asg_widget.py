"""
A widget for the scope module
"""

from .base_module_widget import ModuleWidget

from qtpy import QtCore, QtWidgets


APP = QtWidgets.QApplication.instance()


class AsgWidget(ModuleWidget):
    def __init__(self, *args, **kwds):
        super(AsgWidget, self).__init__(*args, **kwds)
        self.attribute_widgets['trigger_source'].value_changed.connect(self.module.setup)