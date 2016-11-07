"""
The parameters of the lockbox are controlled by descriptors deriving from BaseAttribute.

An attribute is a field that can be set or get by several means:
      - programmatically: module.attribute = value
      - graphically: attribute.create_widget(module) returns a widget to manipulate the value
      - via loading the value in a config file for permanent value preservation

Of course, the gui/parameter file/actual values have to stay "in sync" each time the attribute value is
changed. The necessary mechanisms are happening behind the scene, and they are coded in this file.
"""

import numpy as np
import sys
import logging
logger = logging.getLogger(name=__name__)

#way to represent the smallest positive value
#needed to set floats to minimum count above zero
epsilon = sys.float_info.epsilon

from .bijection import Bijection
from .attribute_widgets import BoolRegisterWidget, FloatRegisterWidget, FilterRegisterWidget, IntRegisterWidget,\
                              PhaseRegisterWidget, FrequencyRegisterWidget, SelectRegisterWidget, StringRegisterWidget


class NamedDescriptorResolverMetaClass(type):
    '''
    Magic to retrieve the name of the registers and the module in the registers themselves
    see http://code.activestate.com/recipes/577426-auto-named-decriptors/
    '''

    def __new__(cls, classname, bases, classDict):
        # Iterate through the new class' __dict__ and update all recognised NamedDescriptor member names
        for name, attr in classDict.items():
            if isinstance(attr, BaseAttribute):
                attr.name = name
        return type.__new__(cls, classname, bases, classDict)


## ModuleAttributes are here in case a layer between ModuleWidget attributes and registers is needed
class BaseAttribute(object):
    """An attribute is a field that can be set or get by several means:
      - programmatically: module.attribute = value
      - graphically: attribute.create_widget(module) returns a widget to manipulate the value
      - via loading the value in a config file for permanence

    The concrete derived class need to have certain attributes properly defined:
      - widget_class: the class of the widget to use for the gui (see attribute_widgets.py)
      - a function set_value(instance, value) that effectively sets the value (on redpitaya or elsewhere)
      - a function get_value(instance, owner) that reads the value from wherever it is stored internally
    """
    widget_class = None

    def __init__(self, default=None, doc=""):
        """
        default: if provided, the value is initialized to it
        """

        if default is not None:
            self.value = default
        self.__doc__ = doc

    def __set__(self, instance, value):
        """
        This function is called for any BaseAttribute, such that all the gui updating, and saving to disk is done
        automagically. The real work is delegated to self.set_value

        :param instance:
        :param value:
        :return:
        """

        self.set_value(instance, value)
        if instance.widget is not None: # update gui only if it exists
            if self.name in instance.widget.attribute_widgets:
                self.update_gui(instance)
        if self.name in instance.save_attributes:
            self.save_attribute(instance)
        return value

    def __get__(self, instance, owner):
        if instance is None:
            return self
        val = self.get_value(instance, owner)
        return val

    def update_gui(self, module):
        module.widget.attribute_widgets[self.name].update_widget()

    def save_attribute(self, module):
        pass

    def create_widget(self, module, name=None):
        if name is None:
            name = self.name # attributed by the metaclass of module
        widget = self.widget_class(name, module)
        module.attribute_widgets[name] = widget
        return widget


class NumberAttribute(BaseAttribute):
    """
    Abstract class for ints and floats
    """

    def create_widget(self, module, name=None):
        widget = super(NumberAttribute, self).create_widget(module, name=name)
        widget.set_increment(self.increment)
        widget.set_maximum(self.max)
        widget.set_minimum(self.min)
        return widget

class FloatAttribute(NumberAttribute):
    """
    An attribute for a float value.
    """
    widget_class = FloatRegisterWidget

    def __init__(self, default=None, increment=0.001, min=-.1, max=1., doc=""):
        super(FloatAttribute, self).__init__(default=default, doc=doc)
        self.increment = increment
        self.min = min
        self.max = max

class FrequencyAttribute(FloatAttribute):
    def __init__(self, default=None, increment=0.1, min=0, max=125e6/2, doc=""):
        super(FloatAttribute, self).__init__(default=default, doc=doc)
        self.increment = increment
        self.min = min
        self.max = max


class IntAttribute(NumberAttribute):
    """
    An attribute for integer values
    """
    widget_class = IntRegisterWidget

    def __init__(self, default=None, min=0, max=2**14, increment=1, doc=""):
        super(IntAttribute, self).__init__(default=default, doc=doc)
        self.min = min
        self.max = max
        self.increment = increment


class BoolAttribute(BaseAttribute):
    """
    An attribute for booleans
    """
    widget_class = BoolRegisterWidget


class SelectAttribute(BaseAttribute):
    """
    An attribute for a multiple choice value.
    The options have to be specified as a list at the time of attribute creation (Module declaration)
    """
    widget_class = SelectRegisterWidget

    def __init__(self, options, default=None, doc=""):
        """

        :param options: either a list of strings if options are known at class declaration time
                        or a function f(module) --> list-of-strings
        :param default:
        :param doc:
        """
        super(SelectAttribute, self).__init__(default=default, doc=doc)
        self._options = options

    def options(self, obj):
        if callable(self._options):
            return self._options(obj)
        else:
            if hasattr(self._options, 'keys'):
                return self._options.keys()
            else:
                return self._options

    def create_widget(self, module, name=None):
        if name is None:
            name = self.name
        self.widget = SelectRegisterWidget(name, module, self.options(module))
        return self.widget


class StringAttribute(BaseAttribute):
    widget_class = StringRegisterWidget


class PhaseAttribute(FloatAttribute):
    def __init__(self, increment=1., min=0., max=360., doc=""):
        super(PhaseAttribute, self).__init__(increment=increment, min=min, max=max, doc=doc)


class FilterAttribute(BaseAttribute):
    """
    An attribute for a list of bandwidth. Each bandwidth is represented by a multiple choice box, however,
    the options and the number of boxes are inferred from the value returned at runtime.
    """

    widget_class = FilterRegisterWidget