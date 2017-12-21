"""
The Hk widget allows to change port direction, set the value of output ports,
get the value of input ports
"""
from .base_module_widget import ModuleWidget
from collections import OrderedDict
from qtpy import QtCore, QtWidgets
import pyqtgraph as pg
import numpy as np
import sys
from ... import APP


class HkWidget(ModuleWidget):
    """
    Widget for the HK module
    """

    def init_gui(self):
        super(HkWidget, self).init_gui()
        ##Then remove properties from normal property layout
        ## We will make one where buttons are stack on top of each others by functional column blocks
        self.main_lay = QtWidgets.QVBoxLayout()
        self.lay_h1 = QtWidgets.QHBoxLayout()
        self.lay_h1.addWidget(self.attribute_widgets['led'])
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.lay_h1.addWidget(self.refresh_button)
        self.main_lay.addLayout(self.lay_h1)
        self.main_layout.removeItem(self.attribute_layout)
        self.main_lay.addLayout(self.attribute_layout)
        self.main_layout.addLayout(self.main_lay)
        self.lay_h1.setStretch(0,0)
        self.lay_h1.addStretch(1)

        self.layout_vs = []
        for i in range(8):
            lay = QtWidgets.QVBoxLayout()
            self.layout_vs.append(lay)
            self.attribute_layout.addLayout(lay)
            for sign in ['P', 'N']:
                val_widget = self.attribute_widgets['expansion_' + sign + str(i)]
                direction_widget = self.attribute_widgets['expansion_' + sign +
                                                          str(i) + '_output']
                self.attribute_layout.removeWidget(val_widget)
                self.attribute_layout.removeWidget(direction_widget)
                lay.addWidget(val_widget)
                lay.addWidget(direction_widget)



        self.attribute_layout.setStretch(0,0)
        self.attribute_layout.addStretch(1)

    def refresh(self):
        for i in range(8):
            for sign in ['P', 'N']:
                name = 'expansion_' + sign + str(i)
                self.attribute_widgets[name].write_attribute_value_to_widget()