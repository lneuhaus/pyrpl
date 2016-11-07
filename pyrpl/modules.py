from six import with_metaclass
from pyrpl.attributes import NamedDescriptorResolverMetaClass, BaseAttribute
from pyrpl.module_widgets import ModuleWidget
import logging

import numpy as np

class BaseModule(with_metaclass(NamedDescriptorResolverMetaClass, object)):
    # python 3-compatible way of using metaclass
    # attributes have automatically their internal name set properly upon module creation
    """
    BaseModules have a create_gui function that returns a widget according to widget_class
    """

    name = 'BaseModule'
    widget_class = ModuleWidget  # Change this to provide a custom graphical class
    gui_attributes = []  # class inheriting from ModuleWidget can automatically generate gui from a list of attributes
    save_attributes = []  # attributes listed here will be saved in the config file everytime they are updated.
    widget = None  # instance-level attribute created in create_widget
    attribute_widgets = None  # instance-level attribute created in create_widget
    # the list of parameters that constitute the "state" of the Module
    parameter_names = []

    # def __new__(cls, *args, **kwds): # to be removed (only one descriptor, several module instances)...
    #    new_instance = object.__new__(cls)
    #    for obj in new_instance.__class__.__dict__.values():
    #        if isinstance(obj, ModuleAttribute):
    #            obj.module = new_instance
    #    return new_instance

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
        self.attribute_widgets = dict()
        self.widget = self.widget_class(self.name, self)
        return self.widget


class HardwareModule(BaseModule):
    """
    Module that directly maps a Redpitaya module.
    """

    # factor to manually compensate 125 MHz oscillator frequency error
    # real_frequency = 125 MHz * _frequency_correction
    @property
    def _frequency_correction(self):
        try:
            return self._parent.frequency_correction
        except AttributeError:
            self._logger.warning("Warning: Parent of %s has no attribute "
                                 "'frequency_correction'. ", self.name)
            return 1.0

    # prevent the user from setting a nonexisting attribute
    def __setattr__(self, name, value):
        if hasattr(self, name) or name.startswith('_') or hasattr(type(self), name):
            super(BaseModule, self).__setattr__(name, value)
        else:
            raise ValueError("New module attributes may not be set at runtime. Attribute "
                             + name + " is not defined in class " + self.__class__.__name__)

    def __init__(self,
                 client,
                 addr_base=0x40000000,
                 parent=None):
        """ Creates the prototype of a RedPitaya Module interface

        arguments: client must be a viable redpitaya memory client
                   addr_base is the base address of the module, such as 0x40300000
                   for the PID module
        """
        self._logger = logging.getLogger(name=__name__)
        self._client = client
        self._addr_base = addr_base
        self.__doc__ = "Available registers: \r\n\r\n" + self.help()
        self._parent = parent

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