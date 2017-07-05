from qtpy import QtCore, QtWidgets
from .base_module_widget import ReducedModuleWidget


class PyrplConfigWidget(ReducedModuleWidget):
    def init_attribute_layout(self):
        super(PyrplConfigWidget, self).init_attribute_layout()
        textwidget = self.attribute_widgets["text"]
        self.main_layout.removeWidget(textwidget)
        self.textbox = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(self.textbox)
        self.textbox.addWidget(textwidget)
