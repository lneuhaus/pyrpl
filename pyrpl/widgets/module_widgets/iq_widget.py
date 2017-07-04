"""
A widget for the iq modules
"""
from .base_module_widget import ModuleWidget

from qtpy import QtCore, QtWidgets


class IqWidget(ModuleWidget):
    """
    Widget for the IQ module
    """

    def init_gui(self):
        super(IqWidget, self).init_gui()
        ##Then remove properties from normal property layout
        ## We will make one where buttons are stack on top of each others by functional column blocks
        for key, widget in self.attribute_widgets.items():
            layout = widget.layout_v
            self.attribute_layout.removeWidget(widget)
        self.attribute_widgets["bandwidth"].widget.set_max_cols(2)
        self.attribute_layout.addWidget(self.attribute_widgets["input"])
        self.attribute_layout.addWidget(self.attribute_widgets["acbandwidth"])
        self.attribute_layout.addWidget(self.attribute_widgets["frequency"])
        self.attribute_widgets["frequency"].layout_v.insertWidget(2, self.attribute_widgets["phase"])
        self.attribute_layout.addWidget(self.attribute_widgets["bandwidth"])
        self.attribute_layout.addWidget(self.attribute_widgets["quadrature_factor"])
        self.attribute_layout.addWidget(self.attribute_widgets["gain"])
        self.attribute_layout.addWidget(self.attribute_widgets["amplitude"])
        self.attribute_layout.addWidget(self.attribute_widgets["output_signal"])
        self.attribute_widgets["output_signal"].layout_v.insertWidget(2, self.attribute_widgets["output_direct"])