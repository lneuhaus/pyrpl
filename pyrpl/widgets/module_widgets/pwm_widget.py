

from .base_module_widget import ModuleWidget

from qtpy import QtCore, QtWidgets


class PwmWidget(ModuleWidget):
    """
    Widget for the pwm module
    """

    def init_gui(self):
        super(PwmWidget, self).init_gui()
        ##Then remove properties from normal property layout
        ## We will make one where buttons are stack on top of each others by functional column blocks
        for key, widget in self.attribute_widgets.items():
            layout = widget.layout_v
            self.attribute_layout.removeWidget(widget)

        self.attribute_layout.addWidget(self.attribute_widgets["input"])
        self.attribute_layout.setStretch(0,0)
        self.attribute_layout.addStretch(1)