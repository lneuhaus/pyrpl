from qtpy import QtCore, QtWidgets
from .base_module_widget import ReducedModuleWidget


class CurveViewerWidget(ReducedModuleWidget):
    def init_gui(self):
        """
        To be overwritten in derived class
        :return:
        """
        self.top_level_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.top_level_layout)
        self.main_layout = QtWidgets.QHBoxLayout()
        self.top_level_layout.addLayout(self.main_layout)
        self.bottom_layout = QtWidgets.QHBoxLayout()
        self.top_level_layout.addLayout(self.bottom_layout)
        self.init_attribute_layout()

    def init_attribute_layout(self):
        super(CurveViewerWidget, self).init_attribute_layout()
        self.textbox = QtWidgets.QHBoxLayout()
        self.bottom_layout.addLayout(self.textbox)
        curve = self.attribute_widgets["curve"]
        for name in ["pk", "curve", "params"]:
            widget = self.attribute_widgets[name]
            self.main_layout.removeWidget(widget)
            self.textbox.addWidget(widget)
            #widget.children()[2].setFixedHeight(500)
            widget.children()[2].setMinimumHeight(500)
            widths = {'pk': 100, 'params': 200}
            if name in widths:
                #widget.children()[2].setFixedWidth(widths[name])
                widget.children()[2].setMinimumWidth(widths[name])

