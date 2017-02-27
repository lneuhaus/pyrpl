"""
Modules are the basic building blocks of Pyrpl:
  - The internal structure of the FPGA is made of individual modules
  performing a well defined task. Each of these FPGA modules are represented
  in python by a HardwareModule.
  - Higher-level operations, for instance those that need a coordinated
  operation of several HardwareModules is performed by SoftwareModules.
Both HardwareModules and SoftwareModules inherit BaseModule that give them
basic capabilities such as displaying their attributes in the GUI having
their state load and saved in the config file...
"""

from .attributes import BaseAttribute
from .widgets.module_widgets import ModuleWidget
from . import CurveDB

import logging
import numpy as np
from six import with_metaclass
from collections import OrderedDict
from PyQt4 import QtCore

class SignalLauncher(QtCore.QObject):
    """
    A QObject that is connected to the widgets to update their value when
    attributes of a module change. Any timers needed to implement the module
    functionality shoud be implemented here as well
    """
    update_attribute_by_name = QtCore.pyqtSignal(str, list)
    # The name of the property that has changed, the list is [new_value],
    # the new_value of the attribute
    change_options = QtCore.pyqtSignal(str, list) # name of the
    # SelectProperty,  list of new options
    change_ownership = QtCore.pyqtSignal() # The owner of the module  has
    # changed

    def __init__(self, module):
        super(SignalLauncher, self).__init__()
        self.module = module

    def kill_timers(self):
        """
        kill all timers
        """
        pass

    def connect_widget(self, widget):
        """
        Establishes all connections between the module and the widget by name.
        """
        #self.update_attribute_by_name.connect(widget.update_attribute_by_name)
        for key in dir(self.__class__):
            val = getattr(self, key)
            if isinstance(val, QtCore.pyqtBoundSignal) and hasattr(widget,
                                                                   key):
                val.connect(getattr(widget, key))


class ModuleMetaClass(type):
    """ Generate Module classes with two features:
    - __new__ lets attributes know what name they are referred two in the
    class that contains them
    - __init__ auto-generates the function setup() and its docstring """
    def __new__(cls, classname, bases, classDict):
        """
        Magic to retrieve the name of the attributes in the attributes
        themselves.
        see http://code.activestate.com/recipes/577426-auto-named-decriptors/
        Iterate through the new class' __dict__ and update the .name of all
        recognised BaseAttribute.
        """
        for name, attr in classDict.items():
            if isinstance(attr, BaseAttribute):
                attr.name = name
        return type.__new__(cls, classname, bases, classDict)

    def __init__(self, classname, bases, classDict):
        """
        Takes care of creating 'setup(**kwds)' function of the module.
        The setup function executes set_attributes(**kwds) and then _setup().

        We cannot use normal inheritance because we want a customized
        docstring for each module. The docstring is created here by
        concatenating the module's _setup docstring and individual
        setup_attribute docstrings.
        """
        super(ModuleMetaClass, self).__init__(classname, bases, classDict)
        #if hasattr(self, "setup_attributes"):
        if "setup" not in self.__dict__:
            # 1. generate a setup function
            def setup(self, **kwds):
                self._callback_active = False
                try:
                    # user can redefine any setup_attribute through kwds
                    self.set_setup_attributes(**kwds)
                    # derived class
                    if hasattr(self, '_setup'):
                        self._setup()
                finally:
                    self._callback_active = True
            # 2. place the new setup function in the module class
            setattr(self, "setup", setup)
        # 3. if setup has no docstring, then make one
        # docstring syntax differs between python versions. Python 3:
        if hasattr(self.setup, "__func__"):
            if (self.setup.__func__.__doc__ is None or
                        self.setup.__func__.__doc__ == ""):
                self.setup.__func__.__doc__ = self.make_setup_docstring()
        # ... python 2
        elif (self.setup.__doc__ is None or
                      self.setup.__doc__ == ""):
            setup.__doc__ = self.make_setup_docstring()

    def make_setup_docstring(self):
        """
        Returns a docstring for the function 'setup' that is composed of:
          - the '_setup' docstring
          - the list of all setup_attributes docstrings
        """
        doc = ""
        if hasattr(self, "_setup"):
            doc += self._setup.__doc__ + '\n'
        doc += "attributes\n=========="
        for attr_name in self._setup_attributes:
            attr = getattr(self, attr_name)
            doc += "\n  " + attr_name + ": " + attr.__doc__
        return doc


class BaseModule(with_metaclass(ModuleMetaClass, object)):
    # The Syntax for defining a metaclass changed from Python 2 to 3.
    # with_metaclass is compatible with both versions and roughly does this:
    # def with_metaclass(meta, *bases):
    #     """Create a base class with a metaclass."""
    #     return meta("NewBase", bases, {})
    # Specifically, ModuleMetaClass ensures that attributes have automatically
    # their internal name set properly upon module creation.
    """
    A module is a component of pyrpl doing a specific task, such as e.g.
    Scope/Lockbox/NetworkAnalyzer. The module can have a widget to interact
    with it graphically.

    It is composed of attributes (see attributes.py) whose values represent
    the current state of the module (more precisely, the state is defined
    by the value of all attributes in _setup_attributes)

    The module can be slaved or freed by a user or another module. When the
    module is freed, it goes back to the state immediately before being
    slaved. To make sure the module is freed, use the syntax:

    with pyrpl.mod_mag.pop('owner') as mod:
            mod.do_something()

    public methods
    --------------
     - get_setup_attributes(): returns a dict with the current values of
     the setup attributes
     - set_setup_attributes(**kwds): sets the provided setup_attributes
     (setup is not called)
     - save_state(name): saves the current "state" (using
     get_setup_attribute) into the config file
     - load_state(name): loads the state 'name' from the config file (setup
     is not called by default)
     - erase_state(name): erases state "name" from config file
     - create_widget(): returns a widget according to widget_class
     - setup(**kwds): first, performs set_setup_attributes(**kwds),
     then calls _setup() to set the module ready for acquisition. This
     method is automatically created by ModuleMetaClass and it combines the
     docstring of individual setup_attributes with the docstring of _setup()
     - free(): sets the module owner to None, and brings the module back the
     state before it was slaved equivalent to module.owner = None)
     - get_yml(state=None): get the yml code representing the state "state'
     or the current state if state is None
     - set_yml(yml_content, state=None): sets the state "state" with the
     content of yml_content. If state is None, the state is directly loaded
     into the module.


     Public attributes:
     ------------------
     - name: attributed based on _section_name at instance creation
     (also used as a section key in the config file)
     - states: the list of states available in the config file
     - owner: (string) a module can be owned (reserved) by a user or another
     module. The module is free if and only if owner is None
     - pyrpl: recursively looks through parent modules until it reaches the
     pyrpl instance

    class attributes to be implemented in derived class:
    ----------------------------------------------------
     - individual attributes (instances of BaseAttribute)
     - _setup_attributes: attribute names that are touched by setup(**kwds)/
     saved/restored upon module creation
     - _gui_attributes: attribute names to be displayed by the widget
     - _callback_attributes: attribute_names that triggers a callback when
     their value is changed in the base class, _callback just calls setup()
     - _widget_class: class of the widget to use to represent the module in
     the gui(a child of ModuleWidget)
     - _section_name: the name under which all instances of the class should
     be stored in the config file

    methods to implement in derived class:
    --------------------------------------
     - _init_module(): initializes the module at startup. During this
     initialization, attributes can be initialized without overwriting config
     file values. Practical to use instead of __init__ to avoid calling
     super().__init__()
     - _setup(): sets the module ready for acquisition/output with the
     current attribute's values. The metaclass of the module autogenerates a
     function like this:
        def setup(self, **kwds):
            *** docstring of function _setup ***
            *** for attribute in self.setup_attributes:
            print-attribute-docstring-here ****

            self.set_setup_attributes(kwds)
            return self._setup()
     - _ownership_changed(old, new): this function is called when the module
     owner changes it can be used to stop the acquisition for instance.
    """

    # Change this to save the curve with a different system
    _curve_class = CurveDB
    # a QOBject used to communicate with the widget
    _signal_launcher = None
    # name that is going to be used for the section in the config file
    # (class-level)
    _section_name = 'basemodule'
    # Change this to provide a custom graphical class
    _widget_class = ModuleWidget
    # attributes listed here will be saved in the config file everytime they
    # are updated.
    _setup_attributes = []
    # class inheriting from ModuleWidget can
    # automatically generate gui from a list of attributes
    _gui_attributes = []
    # Changing these attributes outside setup(
    # **kwds) will trigger self.callback()
    # standard callback defined in BaseModule is to call setup()
    _callback_attributes = []
    # instance-level attribute created in create_widget
    # This flag is used to desactivate callback during setup
    _callback_active = True
    # This flag is used to desactivate saving into file during init
    _autosave_active = True
    # placeholder for widget
    #_widget = None
    # internal memory for owner of the module (to avoid conflicts)
    _owner = None
    # name of the module, automatically assigned one per instance
    name = None
    # the class for the SignalLauncher to be used
    _signal_launcher = SignalLauncher

    def __init__(self, parent, name=None):
        """
        Creates a module with given name. If name is None, cls.name is
        assigned by the metaclass.

        Parent is either
          - a pyrpl instance: config file entry is in
            (self.__class__.name + 's').(self.name)
          - or another SoftwareModule: config file entry is in
            (parent_entry).(self.__class__.name + 's').(self.name)
        """
        if name is not None:
            self.name = name
        self._logger = logging.getLogger(name=__name__)
        # create the signal launcher object from its class
        self._signal_launcher = self._signal_launcher(self)
        self.parent = parent
        self._autosave_active = False
        self._init_module()
        self._autosave_active = True

    def _init_module(self):
        """
        To implement in child class if needed.
        """
        pass

    def get_setup_attributes(self):
        """
        :return: a dict with the current values of the setup attributes
        """
        kwds = OrderedDict()
        for attr in self._setup_attributes:
            kwds[attr] = getattr(self, attr)
        return kwds

    def set_setup_attributes(self, **kwds):
        """
        Sets the values of the setup attributes. Without calling any callbacks
        """
        old_callback_active = self._callback_active
        self._callback_active = False
        try:
            for key in self._setup_attributes:
                if key in kwds:
                    value = kwds.pop(key)
                    setattr(self, key, value)
        finally:
            self._callback_active = old_callback_active
        if len(kwds) > 0:
            raise ValueError("Attribute %s of module %s doesn't exist." %  (
                kwds[0], self.name))

    def _load_setup_attributes(self):
        """
         Load and sets all setup attributes from config file
        """
        dic = OrderedDict()
        if self.c is not None:
            for key, value in self.c._dict.items():
                if key in self._setup_attributes:
                    dic[key] = value
            self.set_setup_attributes(**dic)

    @property
    def _c_states(self):
        """
        Returns the config file branch corresponding to the "states" section.
        """
        if not "states" in self.c._parent._keys():
            self.c._parent["states"] = dict()
        return self.c._parent.states

    def _c_state(self, state_name, state_branch=None):
        """
        :param state_name: Name of the state to explore.
        :param state_branch: If not None, look inside the provided branch.
        :return: The memory branch of the requested state.
        """
        if state_branch is None: # look in the normal c_states
            state_branch = self._c_states
        if state_name not in state_branch._keys():
            raise KeyError("State %s doesn't exist for modules %s"
                           % (state_name, self.__class__.name))
        return getattr(state_branch, state_name) #[state_name]

    def save_state(self, name, state_branch=None):
        """
        Saves the current state under the name "name" in the config file. If
        state_section is left unchanged, uses the normal
        class_section.states convention.
        """
        if state_branch is None:
            state_branch = self._c_states
        state_branch[name] = self.get_setup_attributes()

    def load_state(self, name, state_branch=None):
        """
        Loads the state with name "name" from the config file. If
        state_branch is left unchanged, uses the normal
        class_section.states convention.
        """
        branch = self._c_state(name, state_branch=None)
        self.set_setup_attributes(**branch._data) # ugly... MemoryTree needs to
                                               # implement the API of a dict...

    def erase_state(self, name):
        """
        Removes the state "name' from the config file
        :param name: name of the state to erase
        :return: None
        """
        self._c_state(name)._erase()

    def _save_curve(self, x_values, y_values, **attributes):
        """
        Saves a curve in some database system.
        To change the database system, overwrite this function
        or patch Module.curvedb if the interface is identical.

        :param  x_values: numpy array with x values
        :param  y_values: numpy array with y values
        :param  attributes: extra curve parameters (such as relevant module
        settings)
        """

        c = self._curve_class.create(x_values,
                                     y_values,
                                     **attributes)
        return c

    def free(self):
        """
        Change ownership to None
        """
        self.owner = None

    @property
    def states(self):
        return list(self._c_states._keys())

    def _setup(self):
        """
        Sets the module up for acquisition with the current setup attribute
        values.
        """
        pass

    def help(self, register=''):
        """returns the docstring of the specified register name
           if register is an empty string, all available docstrings are
           returned"""
        if register:
            string = type(self).__dict__[register].__doc__
            return string
        else:
            string = ""
            for key in type(self).__dict__.keys():
                if isinstance(type(self).__dict__[key], BaseAttribute):
                    docstring = self.help(key)
                    # mute internal registers
                    if not docstring.startswith('_'):
                        string += key + ": " + docstring + '\r\n\r\n'
            return string

    def create_widget(self):
        """
        Creates the widget specified in widget_class.
        """
        callback_bkp = self._callback_active
        self._callback_active = False # otherwise, saved values will be
        # overwritten by default gui values
        autosave_bkp = self._autosave_active
        self._autosave_active = False # otherwise, default gui values will be
        # saved
        try:
            widget = self._widget_class(self.name, self)
            #self._widget = self._widget_class(self.name, self)
        finally:
            self._callback_active = callback_bkp
            self._autosave_active = autosave_bkp
        return widget # self._widget

    @property
    def c(self):
        """
        The config file instance. In practice, writing values in here will
        write the values in the corresponding section of the config file.
        """
        manager_section_name = self._section_name + "s" # for instance, iqs
        try:
            manager_section = getattr(self.parent.c, manager_section_name)
        except KeyError:
            self.parent.c[manager_section_name] = dict()
            manager_section = getattr(self.parent.c, manager_section_name)
        if not self.name in manager_section._keys():
            manager_section[self.name] = dict()
        return getattr(manager_section, self.name)

    def _callback(self):
        """
        This function is called whenever an attribute listed in
        callback_attributes is changed outside setup()
        """
        self.setup()

    @property
    def owner(self):
        return self._owner

    @owner.setter
    def owner(self, val):
        """
        Changing module ownership automagically:
         - changes the visibility of the module_widget in the gui
         - re-setups the module with the module attributes in the config-file
           if new ownership is None
        """
        old = self.owner
        self._owner = val
        if val is None:
            self._autosave_active = True
        else:
            # desactivate autosave for slave modules
            self._autosave_active = False
        self._ownership_changed(old, val)
        if val is None:
            self.set_setup_attributes(**self.c._dict)
        self._signal_launcher.change_ownership.emit()

    def __enter__(self):
        """
        This function is executed in the context manager construct with
        ... as ... :
        """
        return self

    def __exit__(self, type, val, traceback):
        """
        To make sure the module will be freed afterwards, use the context
         manager construct:
        with pyrpl.module_manager.pop('owner') as mod:
            mod.do_something()
        # module automatically freed at this point

        The free operation is performed in this function
        see http://stackoverflow.com/questions/1369526/what-is-the-python-keyword-with-used-for
        """
        self.owner = None

    @property
    def pyrpl(self):
        """
        Recursively looks through patent modules untill pyrpl instance is
        reached.
        """
        from .pyrpl import Pyrpl
        parent = self.parent
        while (not isinstance(parent, Pyrpl)):
            parent = parent.parent
        return parent

    def get_yml(self, state=None):
        """
        :param state: The name of the state to inspect. If state is None-->
        then, use the current instrument state.
        :return: a string containing the yml code
        """
        if state is None:
            return self.c._get_yml()
        else:
            return self._c_state(state)._get_yml()

    def set_yml(self, yml_content, state=None):
        """
        :param yml_content: some yml code to encode the module content.
        :param state: The name of the state to set. If state is None-->
        then, use the current instrument state and reloads it immediately
        :return: None
        """
        if state is None:
            self.c._set_yml(yml_content)
            self._load_setup_attributes()
        else:
            self._c_state(state)._set_yml(yml_content)


class HardwareModule(BaseModule):
    """
    Module that directly maps a FPGA module. In addition to BaseModule's r
    equirements, HardwareModule classes have to possess the following class
    attributes
      - addr_base: the base address of the module, such as 0x40300000
    """

    parent = None  # parent will be redpitaya instance

    def __init__(self, parent, name=None):
        """ Creates the prototype of a RedPitaya Module interface

        if no name provided, will use cls.name
        """
        self._client = parent.client
        self._addr_base = self.addr_base
        self._rp = parent
        super(HardwareModule, self).__init__(parent, name=name)
        self.__doc__ = "Available registers: \r\n\r\n" + self.help()

    def _ownership_changed(self, old, new):
        """
        This hook is there to make sure any ongoing measurement is stopped when
        the module gets slaved

        old: name of old owner (eventually None)
        new: name of new owner (eventually None)
        """
        pass

    @property
    def _frequency_correction(self):
        """
        factor to manually compensate 125 MHz oscillator frequency error
        real_frequency = 125 MHz * _frequency_correction
        """
        try:
            return self._rp.frequency_correction
        except AttributeError:
            self._logger.warning("Warning: Parent of %s has no attribute "
                                 "'frequency_correction'. ", self.name)
            return 1.0


    def __setattr__(self, name, value):
        # prevent the user from setting a nonexisting attribute
        # (I am not sure anymore if it's not making everyone's life harder...)
        # if hasattr(self, name) or name.startswith('_') or
        # hasattr(type(self), name):
        if name.startswith("_") \
                or (name in self.__dict__) \
                or hasattr(self.__class__, name):
            # we don't want class.attr
            # to be executed to save one communication time,
            # this was the case with hasattr(self, name)
            super(BaseModule, self).__setattr__(name, value)
        else:
            raise ValueError("New module attributes may not be set at runtime."
                             " Attribute " + name + " is not defined in class "
                             + self.__class__.__name__)

    def _reads(self, addr, length):
        return self._client.reads(self._addr_base + addr, length)

    def _writes(self, addr, values):
        self._client.writes(self._addr_base + addr, values)

    def _read(self, addr):
        return int(self._reads(addr, 1)[0])

    def _write(self, addr, value):
        self._writes(addr, [int(value)])

    def _to_pyint(self, v, bitlength=14):
        v = v & (2 ** bitlength - 1)
        if v >> (bitlength - 1):
            v = v - 2 ** bitlength
        return int(v)

    def _from_pyint(self, v, bitlength=14):
        v = int(v)
        if v < 0:
            v = v + 2 ** bitlength
        v = (v & (2 ** bitlength - 1))
        return np.uint32(v)


class SoftwareModule(BaseModule):
    """
    Module that doesn't communicate with the Redpitaya directly.
    Child class needs to implement:
      - init_module(pyrpl): initializes the module (attribute values aren't
        saved during that stage)
      - setup_attributes: see BaseModule
      - gui_attributes: see BaseModule
      - _setup(): see BaseModule, this function is called when the user calls
        setup(**kwds) and should set the module
        ready for acquisition/output with the current setup_attributes' values.
    """
    pass
