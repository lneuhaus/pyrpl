"""
The basic functionality of all module widgets are inherited from the base
class :class:`.ModuleWidget`.

A module widget is delimited by a dashed-line (a QGroupBox). The following
menu is available on the top part of each ModuleWidget, directly behind the
name of the module (e.g. :code:`pid0`, :code:`pid1`, ...). Right click on
the item (e.g. :code:`.:Load:.`, :code:`.:Save:.`, ...) to access the associated
submenu:

* :code:`.:Load:.` Loads the state of the module from a list of previously saved states.
* :code:`.:Save:.` Saves the current state under a given state name.
* :code:`.:Erase:.` Erases one of the previously saved states.
* :code:`.:Edit:.` Opens a text window to edit the yml code of a state.
* :code:`.:Hide/Show:.` Hides or shows the content of the module widget.

Inside the module widget, different attribute values can be manipulated using
the shown sub-widgets (e.g. :code:`input`, :code:`setpoint`, :code:`max_voltage`, ...). The
modifications will take effect immediately. Only the module state
:code:`<current state>` is affected by these changes. Saving the state under
a different name only preserves the state at the moment of saving for later
retrieval.

At the next startup with the same config file, the :code:<current state> of
all modules is loaded.

If a module-widget is grayed out completely, it has been reserved by another,
higher-level module whose name appears in parentheses after the name of the
module (e.g. :code:`pid2 (output1)` means that the module :code:`pid2` is
being used by the module :code:`output1`, which is actually a submodule of the
:code:`lockbox` module). You can right-click anywhere on the grayed out
widget and click on "Free" to override that reservation and use the module
for your own purposes.

.. warning:: If you override a module reservation, the module in parenthesis
             might stop to function properly. A better practice is to identify
             the top-level module responsible for the reservation, remove its
             name from the list in your configuration file (located at
             /HOME/pyrpl_user_dir/config/<string_shown_in_top_bar_of_the_gui>.yml)
             and restart PyRPL with that configuration.
"""
from qtpy import QtCore, QtWidgets
from collections import OrderedDict
import functools
import logging
from ..yml_editor import YmlEditor


class MyMenuLabel(QtWidgets.QLabel):
    """
    A label on top of the menu widget that is able to display save or load menu.
    """
    def __init__(self, module_widget):
        self.module_widget = module_widget
        self.module = module_widget.module
        super(MyMenuLabel, self).__init__(self.text, module_widget)

    def get_menu(self):
        menu = QtWidgets.QMenu(self)
        self.actions = []
        for state in self.module.states:
            action = QtWidgets.QAction(state, self)
            self.actions.append(action)
            action.triggered.connect(functools.partial(self.func, state))
            menu.addAction(action)
        return menu

    def contextMenuEvent(self, event):
        menu = self.get_menu()
        if menu is not None:
            menu.exec_(event.globalPos())


class LoadLabel(MyMenuLabel):
    """
    "Load" label
    """
    text = " .:Load:. "
    def func(self, state):
        self.module.load_state(state)


class SaveLabel(MyMenuLabel):
    """
    "Save" label
    """
    text = " .:Save:. "

    def __init__(self, module_widget):
        super(SaveLabel, self).__init__(module_widget)

    def func(self, state):
        self.module.save_state(state)

    def get_menu(self):
        menu = super(SaveLabel, self).get_menu()
        action_new = QtWidgets.QAction('<New...>', self)
        action_new.triggered.connect(self.new_state)
        menu.addAction(action_new)
        return menu

    def new_state(self):
        state, accept = QtWidgets.QInputDialog.getText(self, "Save %s "
                            "state"%self.module.name, "Enter new state name:")
        state = str(state)
        if accept:
            if state in self.module.states:
                raise ValueError( "State %s of module %s already exists!"%(
                    state, self.module.name))
            self.module.save_state(state)

class EraseLabel(MyMenuLabel):
    """
    "Erase" label
    """
    text = " .:Erase:. "

    def func(self, state):
        self.module.erase_state(state)


class EditLabel(MyMenuLabel):
    """
    "Edit" label
    """
    text = " .:Edit:. "

    def func(self, state):
        editor = YmlEditor(self.module, state)
        self.module_widget.yml_editors[str(self.module.name) + '__' + str(
            state)] = editor
        editor.show()

    def get_menu(self):
        menu = super(EditLabel, self).get_menu()
        action_current = QtWidgets.QAction('<Current>', self)
        action_current.triggered.connect(functools.partial(self.func, None))
        others = menu.actions()
        if len(others)>0:
            other = others[0]
            menu.insertAction(other, action_current)
        else:
            menu.addAction(action_current) # will append the action at the end
        return menu


class HideShowLabel(MyMenuLabel):
    """
    "Hide/Show" label
    """
    text = " .:Hide/Show:. "

    def get_menu(self):
        if hasattr(self, 'hidden') and self.hidden:
            self.module_widget.show_widget()
            self.hidden = False
        else:
            self.module_widget.hide_widget()
            self.hidden = True
        return None


class ReducedModuleWidget(QtWidgets.QGroupBox):
    """
    Base class for a module Widget.

    In general, this is one of the DockWidget of the Pyrpl MainWindow.
    """
    attribute_changed = QtCore.Signal()
    title_pos = (12, 0)

    def __init__(self, name, module, parent=None):
        super(ReducedModuleWidget, self).__init__(parent)
        self._logger = logging.getLogger(__name__)
        self.module = module
        self.name = name
        self.attribute_widgets = OrderedDict()
        self.yml_editors = dict()  # optional widgets to edit the yml code of module on a per-state basis
        self.init_gui() # performs the automatic gui creation based on register_names
        # self.setStyleSheet("ModuleWidget{border:0;color: transparent;}") # frames and title hidden for software_modules
                                        # ModuleManagerWidget sets them visible for the HardwareModuleWidgets...
        self.create_title_bar()
        self.change_ownership() # also sets the title
        self.module._signal_launcher.connect_widget(self)

    def init_main_layout(self, orientation='horizontal'):
        self.root_layout = QtWidgets.QHBoxLayout()
        self.main_widget = QtWidgets.QWidget()
        self.root_layout.addWidget(self.main_widget)
        if orientation == "vertical":
            self.main_layout = QtWidgets.QVBoxLayout()
        else:
            self.main_layout = QtWidgets.QHBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        self.setLayout(self.root_layout)

    def show_widget(self):
        """ shows the widget after it has been hidden """
        self.main_widget.show()

    def hide_widget(self):
        """ shows the widget after it has been hidden """
        self.main_widget.hide()

    def init_gui(self):
        """
        To be overwritten in derived class
        :return:
        """
        self.init_main_layout()
        self.init_attribute_layout()

    def init_attribute_layout(self):
        """
        Automatically creates the gui properties for the register_widgets in register_names.
        :return:
        """
        if '\n' in self.module._gui_attributes:
            self.attributes_layout = QtWidgets.QVBoxLayout()
            self.main_layout.addLayout(self.attributes_layout)
            self.attribute_layout = QtWidgets.QHBoxLayout()
            self.attributes_layout.addLayout(self.attribute_layout)
        else:
            self.attribute_layout = QtWidgets.QHBoxLayout()
            self.main_layout.addLayout(self.attribute_layout)
        for attr_name in self.module._gui_attributes:
            if attr_name == '\n':
                self.attribute_layout = QtWidgets.QHBoxLayout()
                self.attributes_layout.addLayout(self.attribute_layout)
            else:
                attribute_value = getattr(self.module, attr_name)  # needed for
                # passing the instance to the descriptor
                attribute = getattr(self.module.__class__, attr_name)
                if callable(attribute):
                    # assume that attribute is a function
                    widget = QtWidgets.QPushButton(attr_name)
                    widget.clicked.connect(getattr(self.module, attr_name))
                else:
                    # standard case: make attribute widget
                    widget = attribute._create_widget(self.module)
                    if widget is None:
                        continue
                    widget.value_changed.connect(self.attribute_changed)
            self.attribute_widgets[attr_name] = widget
            self.attribute_layout.addWidget(widget)
        self.attribute_layout.addStretch(1)

    def update_attribute_by_name(self, name, new_value_list):
        """
        SLOT: don't change name unless you know what you are doing
        Updates a specific attribute. New value is passed as a 1-element list
        to avoid typing problems in signal-slot.
        """
        if name in self.module._gui_attributes:
            widget = self.attribute_widgets[str(name)]
            try:  # try to propagate the change of attribute to the widget
                widget.update_attribute_by_name(new_value_list)
            except:  # directly set the widget value otherwise
                self.attribute_widgets[str(name)].widget_value = new_value_list[0]

    def change_options(self, select_attribute_name, new_options):
        """
        SLOT: don't change name unless you know what you are doing
        New options should be displayed for some SelectAttribute.
        """
        if select_attribute_name in self.module._gui_attributes:
            self.attribute_widgets[str(select_attribute_name)].change_options(new_options)

    def refresh_filter_options(self, filter_attribute_name):
        """
        SLOT: don't change name unless you know what you are doing
        New options should be displayed for some FilterProperty.
        """
        if filter_attribute_name in self.module._gui_attributes:
            self.attribute_widgets[str(
                filter_attribute_name)].refresh_options(self.module)

    def change_ownership(self):
        """
        SLOT: don't change name unless you know what you are doing
        Display the new ownership
        """
        #name = self.module.pyrpl.name + " - " + self.module.name
        name = self.module.name
        if self.module.owner is not None:
            self.setEnabled(False)
            self.set_title(name + ' (' + self.module.owner + ')')
        else:
            self.setEnabled(True)
            self.set_title(name)

    def set_title(self, title):
        return self.setTitle(str(title))

    def create_title_bar(self):
        # manage spacings of title bar / box around module
        for v in [self.main_layout]:
            v.setSpacing(0)
            v.setContentsMargins(5, 1, 0, 0)

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


class ModuleWidget(ReducedModuleWidget):
    """
    Base class for a module Widget. In general, this is one of the DockWidget of the Pyrpl MainWindow.
    """
    def set_title(self, title):
        title = str(title)
        if hasattr(self, "title_label"): # ModuleManagerWidgets don't have a title_label
            self.title_label.setText(title)
            self.title_label.adjustSize()
            self.title_label.move(*self.title_pos)
            self.load_label.move(self.title_label.width() + self.title_pos[0],
                                 self.title_pos[1])
            self.save_label.move(self.load_label.width() +
                                 self.load_label.pos().x(), self.title_pos[1])
            self.erase_label.move(self.save_label.width() +
                                 self.save_label.pos().x(), self.title_pos[1])
            self.edit_label.move(self.erase_label.width() +
                                 self.erase_label.pos().x(), self.title_pos[1])
            self.hideshow_label.move(self.edit_label.width() +
                                     self.edit_label.pos().x(),
                                     self.title_pos[1])

    def create_title_bar(self):
        self.title_label = QtWidgets.QLabel("yo", parent=self)
         # title should be at the top-left corner of the widget
        self.load_label = LoadLabel(self)
        self.load_label.adjustSize()

        self.save_label = SaveLabel(self)
        self.save_label.adjustSize()

        self.erase_label = EraseLabel(self)
        self.erase_label.adjustSize()

        self.edit_label = EditLabel(self)
        self.edit_label.adjustSize()

        self.hideshow_label = HideShowLabel(self)
        self.hideshow_label.adjustSize()

        # self.setStyleSheet("ModuleWidget{border: 1px dashed gray;color: black;}")
        self.setStyleSheet("ModuleWidget{margin: 0.1em; margin-top:0.6em; border: 1 dotted gray;border-radius:5}")
        # margin-top large enough for border to be in the middle of title
        self.layout().setContentsMargins(0, 5, 0, 0)
