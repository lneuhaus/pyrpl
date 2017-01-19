"""
ModuleWidgets's hierarchy is parallel to that of Modules.
Each Module instance can have a widget created by calling create_widget.
To use a different class of Widget than the preset (for instance subclass it), the attribute ModuleClass.WidgetClass
can be changed before calling create_widget()
"""

from PyQt4 import QtCore, QtGui
from collections import OrderedDict
import functools

APP = QtGui.QApplication.instance()

class MyMenuLabel(QtGui.QLabel):
    """
    A label on top of the menu widget that is able to display save or load menu.
    """
    def __init__(self, module_widget):
        self.module_widget = module_widget
        self.module = module_widget.module
        super(MyMenuLabel, self).__init__(self.text, module_widget)

    def get_menu(self):
        menu = QtGui.QMenu(self)
        self.actions = []
        for state in self.module.states:
            action = QtGui.QAction(state, self)
            self.actions.append(action)
            action.triggered.connect(functools.partial(self.func, state))
            menu.addAction(action)
        return menu

    def contextMenuEvent(self, event):
        menu = self.get_menu()
        menu.exec_(event.globalPos())


class LoadLabel(MyMenuLabel):
    """
    "Load" label
    """
    text = "  .:Load:. "
    def func(self, state):
        self.module.load_state(state)

class SaveLabel(MyMenuLabel):
    """
    "Save" label
    """
    text = " .:Save:."

    def __init__(self, module_widget):
        super(SaveLabel, self).__init__(module_widget)

    def func(self, state):
        self.module.save_state(state)

    def get_menu(self):
        menu = super(SaveLabel, self).get_menu()
        action_new = QtGui.QAction('<New...>', self)
        action_new.triggered.connect(self.new_state)
        menu.addAction(action_new)
        return menu

    def new_state(self):
        state, accept = QtGui.QInputDialog.getText(self,
                                                   "Save %s state"%self.module.name, "Enter new state name:")
        state = str(state)
        if accept:
            if state in self.module.states:
                raise ValueError("State %s of module %s already exists!"%(state, self.module.name))
            self.module.save_state(state)


class ModuleWidget(QtGui.QGroupBox):
    """
    Base class for a module Widget. In general, this is one of the DockWidget of the Pyrpl MainWindow.
    """
    title_pos = (12, 0)

    attribute_changed = QtCore.pyqtSignal()
    # register_names = [] # a list of all register name to expose in the gui

    def set_title(self, title):
        if hasattr(self, "title_label"): # ModuleManagerWidgets don't have a title_label
            self.title_label.setText(title)
            self.title_label.adjustSize()
            self.title_label.move(*self.title_pos)
            self.load_label.move(self.title_label.width() + self.title_pos[0], self.title_pos[1])
            self.save_label.move(self.load_label.width() + self.load_label.pos().x(), self.title_pos[1])

    def __init__(self, name, module, parent=None):
        super(ModuleWidget, self).__init__(parent)
        self.module = module
        self.name = name
        self.attribute_widgets = OrderedDict()

        self.init_gui() # performs the automatic gui creation based on register_names
        self.create_title_bar()
        # self.setStyleSheet("ModuleWidget{border:0;color: transparent;}") # frames and title hidden for software_modules
                                        # ModuleManagerWidget sets them visible for the HardwareModuleWidgets...
        self.show_ownership()
        self.module.signal_launcher.connect_widget(self)

    def update_attribute_by_name(self, name, new_value_list):
        """
        Updates a specific attribute. New value is passed as a 1-element list to avoid typing problems in signal-slot.
        """
        if name in self.module.gui_attributes:
            self.attribute_widgets[str(name)].update_widget(new_value_list[0])

    def create_title_bar(self):
        self.title_label = QtGui.QLabel("yo", parent=self)
         # title should be at the top-left corner of the widget
        self.load_label = LoadLabel(self)
        self.load_label.adjustSize()

        self.save_label = SaveLabel(self)

        self.save_label.adjustSize()

        # self.setStyleSheet("ModuleWidget{border: 1px dashed gray;color: black;}")
        self.setStyleSheet("ModuleWidget{margin: 0.1em; margin-top:0.6em; border: 1 dotted gray;border-radius:5}")
        # margin-top large enough for border to be in the middle of title
        self.layout().setContentsMargins(0, 5, 0, 0)

    def show_ownership(self):
        if self.module.owner is not None:
            self.setEnabled(False)
            self.set_title(self.module.name + ' (' + self.module.owner + ')')
        else:
            self.setEnabled(True)
            self.set_title(self.module.name)

    def init_attribute_layout(self):
        """
        Automatically creates the gui properties for the register_widgets in register_names.
        :return:
        """

        self.attribute_layout = QtGui.QHBoxLayout()
        self.main_layout.addLayout(self.attribute_layout)

        for attr_name in self.module.gui_attributes:
            widget = getattr(self.module.__class__, attr_name).create_widget(self.module)
            self.attribute_widgets[attr_name] = widget
            self.attribute_layout.addWidget(widget)
            widget.value_changed.connect(self.attribute_changed)

    def save_curve(self, x_values, y_values, **attributes):
        """
        Saves the curve in some database system.
        To change the database system, overwrite this function
        or patch Module.curvedb if the interface is identical.

        :param  x_values: numpy array with x values
        :param  y_values: numpy array with y values
        :param  attributes: extra curve parameters (such as relevant module settings)
        """

        c = self.curve_class.create(x_values,
                                    y_values,
                                    **attributes)
        c.name = attributes["curve_name"]
        return c

    def init_gui(self):
        """
        To be overwritten in derived class

        :return:
        """

        self.main_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.init_attribute_layout()