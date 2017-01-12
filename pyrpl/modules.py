"""
Modules are the basic building blocks of Pyrpl:
  - The internal structure of the FPGA is made of individual modules performing a well defined task. Each of these
    FPGA modules are represented in python by a HardwareModule.
  - Higher-level operations, for instance those that need a coordinated operation of several HardwareModules is
    performed by SoftwareModules.
Both HardwareModules and SoftwareModules inherit BaseModule that give them basic capabilities such as displaying their
attributes in the GUI having their state load and saved in the config file...
"""

from .attributes import BaseAttribute
from .widgets.module_widgets import ModuleWidget

import logging
import numpy as np
from six import with_metaclass
from collections import OrderedDict



def get_setup_docstring(cls):
    """
    Returns a docstring for the function 'setup' that is composed of:
      - the '_setup' docstring
      - the list of all setup_attributes docstrings
    """
    if not hasattr(cls, "_setup"):
        raise NotImplementedError("class '" + cls.__name__ + "' needs to implement a method '_setup'")
    doc = cls._setup.__doc__ + '\n'
    doc += "attributes\n=========="
    for attr_name in cls.setup_attributes:
        attr = getattr(cls, attr_name)
        doc += "\n  " + attr_name + ": " + attr.__doc__
    return doc

def new_func_setup():
    def setup(self, **kwds):
        """
        First: sets the attributes specified in kwds with set_setup_attributes(**kwds).
        Second: setup the module with the current attributes (using _setup())

        Many instances of this function will be created by the module's metaclass
        (one per subclass having a setup_attributes field) and each of these functions will have the present docstring
        overwritten by a more descriptive one based on _setup.__doc__ and module attributes docstrings.
        """
        self._callback_active = False
        try:
            self.set_setup_attributes(**kwds)
            self._setup()
        finally:
            self._callback_active = True
    return setup

class NameAttributesMetaClass(type):
    '''
    Magic to retrieve the name of the attributes in the attributes themselves.
    see http://code.activestate.com/recipes/577426-auto-named-decriptors/
    '''
    def __new__(cls, classname, bases, classDict):
        """
        Iterate through the new class' __dict__ and update the .name of all recognised BaseAttribute.
        Otherwise, we would have to declare every attribute with the following unpleasantly redundant code:
        foo = SomeAttribute(bits=14, min=0, max=1, name='foo')
        """
        for name, attr in classDict.items():
            if isinstance(attr, BaseAttribute):
                attr.name = name
        return type.__new__(cls, classname, bases, classDict)


class ModuleMetaClass(NameAttributesMetaClass):
    '''
    Builds the setup docstring by aggregating _setup's and setup_attributes's docstrings.
    '''
    def __init__(self, classname, bases, classDict):
        """
        Takes care of creating the module's 'setup' function.
        The setup function combines set_attributes(**kwds) with _setup().
        We cannot use normal inheritance because we want a customized docstring for each module.
        The docstring is created here by combining the module's _setup docstring and individual attributes' docstring.
        """
        super(ModuleMetaClass, self).__init__(classname, bases, classDict)
        if hasattr(self, "setup_attributes"):
            if not "setup" in self.__dict__:  # function setup is inherited--> this is bad because we want a docstring
                # different for each subclass
                setattr(self, "setup", new_func_setup())
                overwrite_docstring = True
            else:
                overwrite_docstring = (self.setup.__doc__ == "")  # keep the docstring if it was made manually
            if overwrite_docstring:
                if hasattr(self.setup, "__func__"): # Should evaluate to True in Python 2
                    self.setup.__func__.__doc__ = get_setup_docstring(self)  # In a MetaClass, self is a class...
                else:  # in python 3, __doc__ is directly an attribute of the function
                    self.setup.__doc__ = get_setup_docstring(self)


class BaseModule(with_metaclass(ModuleMetaClass, object)):
    # python 3-compatible way of using metaclass
    # attributes have automatically their internal name set properly upon module creation
    """
    Several fields have to be implemented in child class:
      - setup_attributes: attributes that are touched by setup(**kwds)/saved/restored upon module creation
      - gui_attributes: attributes to be displayed by the widget
      - widget_class: class of the widget to use to represent the module in the gui (a child of ModuleWidget)
      - _setup(): sets the module ready for acquisition/output with the current attribute's values.

    BaseModules implements several functions itself:
      - create_widget: returns a widget according to widget_class
      - get_setup_attributes(): returns a dictionary with the current setup_attribute key value pairs
      - load_setup_attributes(): loads setup_attributes from config file
      - set_setup_attributes(**kwds): sets the provided setup_attributes

    Finally, setup(**kwds) is created by ModuleMetaClass. it combines set_setup_attributes(**kwds) with _setup()
    """
    pyrpl_config = None
    name = None # instance-level attribute
    section_name = 'basemodule' # name that is going to be used for the section in the config file (class-level)
    widget_class = ModuleWidget  # Change this to provide a custom graphical class
    gui_attributes = []  # class inheriting from ModuleWidget can automatically generate gui from a list of attributes
    setup_attributes = []  # attributes listed here will be saved in the config file everytime they are updated.
    callback_attributes = [] # Changing these attributes outside setup(**kwds) will trigger self.callback()
    # standard callback defined in BaseModule is to call setup()
    widget = None  # instance-level attribute created in create_widget

    _callback_active = True # This flag is used to desactivate callback during setup
    _autosave_active = True # This flag is used to desactivate saving into file during init
    _owner = None

    def get_setup_attributes(self):
        """
        :return: a dict with the current values of the setup attributes
        """
        kwds = dict()
        for attr in self.setup_attributes:
            kwds[attr] = getattr(self, attr)
        return kwds

    def set_setup_attributes(self, **kwds):
        """
        Sets the values of the setup attributes. Without calling any callbacks
        """
        old_callback_active = self._callback_active
        self._callback_active = False
        try:
            for key in self.setup_attributes:
                if key in kwds:
                    value = kwds.pop(key)
                    setattr(self, key, value)
        finally:
            self._callback_active = old_callback_active
        if len(kwds)>0:
            raise ValueError("Attribute %s of module %s doesn't exist." % (kwds[0], self.name))
        #    for key, value in kwds.items():
        #        if not key in self.setup_attributes:
        #            raise ValueError("Attribute %s of module %s doesn't exist."%(key, self.name))
        #        setattr(self, key, value)
        #finally:
        #    self._callback_active = old_callback_active

    def load_setup_attributes(self):
        """
         Load and sets all setup attributes from config file
        """
        dic = dict()
        if self.c is not None:
            for key, value in self.c._dict.items():
                if key in self.setup_attributes:
                    dic[key] = value
            self.set_setup_attributes(**dic)

    @property
    def c_states(self):
        """
        Returns the config file branch corresponding to the "states" section.
        """
        if not "states" in self.c._parent._keys():
            self.c._parent["states"] = dict()
        return self.c._parent.states

    def save_state(self, name, state_section=None):
        """Saves the current state under the name "name" in the config file. If state_section is left unchanged,
        uses the normal class_section.states convention."""
        if state_section is None:
            state_section = self.c_states
        state_section[name] = self.get_setup_attributes()

    def load_state(self, name, state_section=None):
        """
        Loads the state with name "name" from the config file. If state_section is left unchanged, uses the normal
        class_section.states convention.
        """
        if state_section is None:
            state_section = self.c_states
        if not name in state_section._keys():
            raise KeyError("State %s doesn't exist for modules %s"%(name, self.__class__.name))
        self.setup(**state_section[name])

    @property
    def states(self):
        return list(self.c_states._keys())

    def _setup(self):
        """
        Sets the module up for acquisition with the current setup attribute values.
        """
        pass

    def help(self, register=''):
        """returns the docstring of the specified register name
           if register is an empty string, all available docstrings are returned"""
        if register:
            string = type(self).__dict__[register].__doc__
            return string
        else:
            string = ""
            for key in type(self).__dict__.keys():
                if isinstance(type(self).__dict__[key], BaseAttribute):
                    docstring = self.help(key)
                    if not docstring.startswith('_'):  # mute internal registers
                        string += key + ": " + docstring + '\r\n\r\n'
            return string

    def create_widget(self):
        """
        Creates the widget specified in widget_class.
        """
        self._callback_active = False # otherwise, saved values will be overwritten by default gui values
        self._autosave_active = False # otherwise, default gui values will be saved
        try:
            self.widget = self.widget_class(self.name, self)
        finally:
            self._callback_active = True
            self._autosave_active = True
        return self.widget

    @property
    def c(self):
        """
        The config file instance. In practice, writing values in here will write the values in the corresponding
        section of the config file.
        """
        manager_section_name = self.section_name + "s" # for instance, iqs
        if not manager_section_name in self.parent.c._keys():
            self.parent.c[manager_section_name] = OrderedDict()
        manager_section = getattr(self.parent.c, manager_section_name)
        if not self.name in manager_section._keys():
            manager_section[self.name] = OrderedDict()
        return getattr(manager_section, self.name)

    def callback(self):
        """
        This function is called whenever an attribute listed in callback_attributes is changed outside setup()
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
         - re-setups the module with the module attributes in the config-file if new ownership is None
        """
        old = self.owner
        self._owner = val
        if val==None:
            self._autosave_active = True
        else:
            self._autosave_active = False # desactivate autosave for slave modules
        self.ownership_changed(old, val)
        if self.widget is not None:
            self.widget.show_ownership()
        if val is None:
            self.setup(**self.c._dict)

class HardwareModule(BaseModule):
    """
    Module that directly maps a FPGA module. In addition to BaseModule's requirements, HardwareModule classes have to
    possess the following class attributes
      - addr_base: the base address of the module, such as 0x40300000
    """

    parent = None # parent will be redpitaya instance

    def ownership_changed(self, old, new):
        """
        This hook is there to make sure any ongoing measurement is stopped when the module get slaved
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
        # prevent the user from setting a nonexisting attribute (I am not sure anymore if it's not making everyone's
        # life harder...)
        if hasattr(self, name) or name.startswith('_') or hasattr(type(self), name):
            super(BaseModule, self).__setattr__(name, value)
        else:
            raise ValueError("New module attributes may not be set at runtime. Attribute "
                             + name + " is not defined in class " + self.__class__.__name__)

    def __init__(self, redpitaya, name=None):
        """ Creates the prototype of a RedPitaya Module interface

        if no name provided, will use cls.name
        """
        self._autosave_active = False
        if name is not None:
            self.name = name
        self._logger = logging.getLogger(name=__name__)
        self._client = redpitaya.client
        self._addr_base = self.addr_base # why ?
        self.__doc__ = "Available registers: \r\n\r\n" + self.help()
        self._rp = redpitaya
        self.parent = redpitaya
        self.pyrpl_config = redpitaya.c
        self.init_module()
        self._autosave_active = True

    def init_module(self):
        """
        To implement in child class if needed.
        """
        pass

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

    def get_state(self):
        """Returns a dictionaty with all current values of the parameters
        listed in parameter_names"""

        res = dict()
        for par in self.parameter_names:
            res[par] = getattr(self, par)
        return res

    def set_state(self, dic):
        """Sets all parameters to the values in dic. When necessary,
        the function also calls setup()"""

        res = dict()
        for key, value in dic.iteritems():
            setattr(self, key, value)


class SoftwareModule(BaseModule):
    """
    Module that doesn't communicate with the Redpitaya directly.
    Child class needs to implement:
      - init_module(pyrpl): initializes the module (attribute values aren't saved during that stage)
      - setup_attributes: see BaseModule
      - gui_attributes: see BaseModule
      - _setup(): see BaseModule, this function is called when the user calls setup(**kwds) and should set the module
      ready for acquisition/output with the current setup_attributes' values.
    """

    def __init__(self, parent, name=None):
        """
        Creates a module with given name. If name is None, uses cls.name.
        parent is either a pyrpl instance, or another SoftwareModule.
          - First case: config file entry is in self.__class__.name + 's'--> self.name
          - Second case: config file entry is in parent_entry-->self.__class__.name + 's'-->self.name
        """
        self._autosave_active = False  # attribute values are not overwritten in the config file
        if name is not None:
            self.name = name
        self.parent = parent
        #self._parent = pyrpl
        #self.pyrpl_config = pyrpl.c
        self.init_module()
        self._autosave_active = True

    @property
    def pyrpl(self):
        """
        Recursively looks through patent modules untill pyrpl instance is reached.
        """
        from .pyrpl import Pyrpl
        parent = self.parent
        while(not isinstance(parent, Pyrpl)):
            parent = parent.parent
        return parent

    def init_module(self):
        """
        To be reimplemented in child class.
        """
        pass