"""
The parameters of the lockbox are controlled by descriptors deriving from
BaseAttribute.

An attribute is a field that can be set or get by several means:
      - programmatically: module.attribute = value
      - graphically: attribute.create_widget(module) returns a widget to
        manipulate the value
      - via loading the value in a config file for permanent value preservation

Of course, the gui/parameter file/actual values have to stay "in sync" each
time the attribute value is changed. The necessary mechanisms are happening
behind the scene, and they are coded in this file.
"""
from __future__ import division
from .pyrpl_utils import Bijection
from .widgets.attribute_widgets import BoolAttributeWidget, \
                                       FloatAttributeWidget, \
                                       FilterAttributeWidget, \
                                       IntAttributeWidget, \
                                       SelectAttributeWidget, \
                                       StringAttributeWidget, \
                                       ListComplexAttributeWidget, \
                                       FrequencyAttributeWidget, \
                                       ListFloatAttributeWidget, \
                                       BoolIgnoreAttributeWidget
import logging
import sys
import numpy as np
import numbers
from PyQt4 import QtCore, QtGui


logger = logging.getLogger(name=__name__)

#way to represent the smallest positive value
#needed to set floats to minimum count above zero
epsilon = sys.float_info.epsilon


class BaseAttribute(object):
    """An attribute is a field that can be set or get by several means:
      - programmatically: module.attribute = value
      - graphically: attribute.create_widget(module) returns a widget to
        manipulate the value
      - via loading the value in a config file for permanence

    The concrete derived class need to have certain attributes properly
    defined:
      - widget_class: the class of the widget to use for the gui (see
        attribute_widgets.py)
      - a function set_value(instance, value) that effectively sets the value
        (on redpitaya or elsewhere)
      - a function get_value(instance, owner) that reads the value from
        wherever it is stored internally
    """
    _widget_class = None
    widget = None

    def __init__(self,
                 default=None,
                 doc="",
                 ignore_errors=False,
                 call_setup=False):
        """
        default: if provided, the value is initialized to it
        """
        if default is not None:
            self.default = default
        self.call_setup = call_setup
        self.ignore_errors = ignore_errors
        self.__doc__ = doc

    def __set__(self, instance, value):
        """
        This function is called for any BaseAttribute, such that all the gui updating, and saving to disk is done
        automagically. The real work is delegated to self.set_value.
        """
        value = self.validate_and_normalize(value, instance)  # self.to_serializable(value)
        self.set_value(instance, value)  # sets the value internally
        self.value_updated(instance, value)  # lauch signal and update config and callback

    def validate_and_normalize(self, value, module):
        """
        This function should raise an exception if the value is incorrect.
        Normalization can be:
           - returning value.name if attribute "name" exists
           - rounding to nearest multiple of step for float_registers
           - rounding elements to nearest valid_frequencies for FilterAttributes
        """
        return value  # by default any value is valid

    def value_updated(self, module, value):
        """
        Once the value has been changed internally, this function is called to perform the following actions:
         - launch the signal module._signal_launcher.attribute_changed (this is used in particular for gui update)
         - saves the new value in the config file (if flag module._autosave_active is True).
         - calls the callback function if the attribute is in module.callback
         Note for developers:
         we might consider moving the 2 last points in a connection behind the signal "attribute_changed".
        """
        self.launch_signal(module, value)
        if module._autosave_active:  # (for module, when module is slaved, don't save attributes)
            if self.name in module._setup_attributes:
                    self.save_attribute(module, value)
        if self.call_setup: # _setup should be triggered...
            if not module._setup_ongoing: # unless a bunch of attributes are
                # being changed together.
                module.setup()
        return value

    def __get__(self, instance, owner):
        if instance is None:
            return self
        try:
            get_value = self.get_value
        except AttributeError as e:
            raise NotImplementedError("The attribute %s doesn't have a method "
                                      "get_value. Did you use an Attribute "
                                      "instead of a Property?" % self.name)
        val = get_value(instance, owner)
        return val

    def launch_signal(self, module, new_value):
        """
        Updates the widget with the module's value.
        """
        # if self.name in module._widget.attribute_widgets:
        #   module._widget.attribute_widgets[self.name].update_widget()
        #if self.name in module._gui_attributes:
        try:
            module._signal_launcher.update_attribute_by_name.emit(self.name,
                                                             [new_value])
        except AttributeError:  # occurs if nothing is connected (TODO: remove this)
            pass

    def save_attribute(self, module, value):
        """
        Saves the module's value in the config file.
        """
        module.c[self.name] = value

    def _create_widget(self, module, name=None):
        """
        Creates a widget to graphically manipulate the attribute.
        """
        if self._widget_class is None:
            logger.warning("Module %s of type %s is trying to create a widget for %s, but no _widget_class is defined!",
                           str(module), type(module), self.name)
            return None
        if name is None:
            name = self.name  # attributed by the metaclass of module
        widget = self._widget_class(name, module)
        return widget


class NumberAttribute(BaseAttribute):
    """
    Abstract class for ints and floats
    """

    def _create_widget(self, module, name=None):
        widget = super(NumberAttribute, self)._create_widget(module, name=name)
        widget.set_increment(self.increment)
        widget.set_maximum(self.max)
        widget.set_minimum(self.min)
        return widget

    def validate_and_normalize(self, value, module):
        """
        Saturates value with min and max.
        """
        return max(min(value, self.max), self.min)


class FloatAttribute(NumberAttribute):
    """
    An attribute for a float value.
    """
    _widget_class = FloatAttributeWidget

    def __init__(self,
                 default=None,
                 increment=0.001,
                 min=-1.,
                 max=1.,
                 doc="",
                 ignore_errors=False,
                 call_setup=False):
        super(FloatAttribute, self).__init__(default=default,
                                             doc=doc,
                                             ignore_errors=ignore_errors,
                                             call_setup=call_setup)
        self.increment = increment
        self.min = min
        self.max = max

    def validate_and_normalize(self, value, module):
        """
        Try to convert to float, then saturates with min and max
        """
        return super(FloatAttribute, self).validate_and_normalize(float(value),
                                                                  module)

class FrequencyAttribute(FloatAttribute):
    """
    An attribute for frequency values
    """
    _widget_class = FrequencyAttributeWidget

    def __init__(self,
                 default=None,
                 increment=0.1,
                 min=0,
                 max=1e100,
                 doc="",
                 ignore_errors=False,
                 call_setup=False):
        super(FloatAttribute, self).__init__(default=default,
                                             doc=doc,
                                             ignore_errors=ignore_errors,
                                             call_setup=call_setup)
        self.increment = increment
        self.min = min
        self.max = max

    def validate_and_normalize(self, value, module):
        """
        Same as FloatAttribute, except it saturates with 0.
        """
        return max(0, super(FrequencyAttribute, self).validate_and_normalize(value, module))


class IntAttribute(NumberAttribute):
    """
    An attribute for integer values
    """
    _widget_class = IntAttributeWidget

    def __init__(self,
                 default=None,
                 min=0,
                 max=2**14,
                 increment=1,
                 doc="",
                 ignore_errors=False,
                 call_setup=False):
        super(IntAttribute, self).__init__(default=default,
                                           doc=doc,
                                           ignore_errors=ignore_errors,
                                           call_setup=call_setup)
        self.min = min
        self.max = max
        self.increment = increment

    def validate_and_normalize(self, value, module):
        """
        Accepts float, but rounds to integer
        """
        return super(IntAttribute, self).validate_and_normalize(int(round(value)), module)


class BoolAttribute(BaseAttribute):
    """
    An attribute for booleans
    """
    _widget_class = BoolAttributeWidget

    def validate_and_normalize(self, value, module):
        """
        Converts value to bool.
        """
        return bool(value)


class BoolIgnoreAttribute(BaseAttribute):
    """
    An attribute for booleans
    """
    _widget_class = BoolIgnoreAttributeWidget

    def validate_and_normalize(self, value, module):
        """
        Converts value to bool.
        """
        if isinstance(value, basestring):
            if value.lower() == 'true':
                return True
            elif value.lower() == 'false':
                return False
            else:
                return 'ignore'
        else:
            return bool(value)


class SelectAttribute(BaseAttribute):
    """
    An attribute for a multiple choice value.
    The options have to be specified as a list at the time of attribute creation (Module declaration).
    If options are numbers (int or float), rounding to the closest value is performed during the validation
    If options are strings, validation is strict.
    """
    _widget_class = SelectAttributeWidget

    def __init__(self,
                 options=[],
                 default=None,
                 doc="",
                 ignore_errors=False,
                 call_setup=False):
        """
        Options can be specified at attribute creation, but it can also be updated later on a per-module basis using
        change_options(new_options)
        """
        super(SelectAttribute, self).__init__(default=default,
                                              doc=doc,
                                              ignore_errors=ignore_errors,
                                              call_setup=call_setup)
        self._starting_options = options

    def options(self, instance):
        """
        options are evaluated at run time. options may be callable with instance as optional argument.
        """
        if hasattr(instance, '__' + self.name + '_' + 'options'):
            options = getattr(instance, '__' + self.name + '_' + 'options')
        else:
            options = self._starting_options
        if callable(options):
            try:
                options = options(instance)
            except TypeError:
                options = options()
        return sorted(options)

    def change_options(self, instance, new_options):
        """
        Changes the possible options acceptable by the Attribute
          - New validation takes effect immediately (otherwise a script involving 1. changing the options/2. selecting
          one of the new options could not be executed at once)
          - Update of the ComboxBox is performed behind a signal-slot mechanism to be thread-safe
          - If the current value is not in the new_options, then value is changed to some available option
        """
        setattr(instance, '__' + self.name + '_' + 'options', new_options)
        options = self.options(instance)
        instance._signal_launcher.change_options.emit(self.name, options)
        # this is strange behaviour, an option should be actively selected..
        if not getattr(instance, self.name) in options:
            logger.debug("Option %s is not a valid choice for "
                         "SelectAttribute %s. A random choice is being "
                         "made which may lead to undesired behavior.."
                         % (getattr(instance, self.name), self.name))
            if len(options) > 0:
                setattr(instance, self.name, options[0])
            else:
                setattr(instance, self.name, None)

    def _create_widget(self, module, name=None):
        """
        This function is reimplemented to pass the options to the widget.
        """
        if name is None:
            name = self.name
        widget = SelectAttributeWidget(name, module, self.options(module))
        return widget

    def validate_and_normalize(self, value, module):
        """
        Looks for attribute name, otherwise, converts to string and rejects if not in self.options
        """
        options = sorted(self.options(module))
        if len(options) == 0 and value is None:
            return None
        if isinstance(options[0], basestring) and isinstance(options[-1], basestring):
            if hasattr(value, 'name'):
                value = str(value.name)
            else:
                value = str(value)
            if not (value in options):
                msg = "Value %s is not an option for SelectAttribute {%s} of %s"\
                      % (value, self.name, module.name)
                if self.ignore_errors:
                    # value = None
                    # logger.warning(msg + ". Selecting value 'None' instead.")
                    value = options[0]
                    logger.warning(msg + ". Picking an arbitrary value %s instead."
                                   % str(value))
                else:
                    raise ValueError(msg)
            return value
        elif isinstance(options[0], numbers.Number) and isinstance(options[-1], numbers.Number):
            value = float(value)
            return min([opt for opt in options], key=lambda x: abs(x - value))
        else:
            return super(SelectAttribute, self).validate_and_normalize(value, module)


class StringAttribute(BaseAttribute):
    """
    An attribute for string (in practice, there is no StringRegister at this stage).
    """
    _widget_class = StringAttributeWidget

    def validate_and_normalize(self, value, module):
        """
        Reject anything that is not a basestring
        """
        if not isinstance(value, basestring):
            raise ValueError("value %s cannot be used for StringAttribute %s of module %s"%(str(value),
                                                                                            self.name,
                                                                                            module.name))
        else:
            return value


class PhaseAttribute(FloatAttribute):
    """
    An attribute to represent a phase
    """
    def __init__(self,
                 increment=1.,
                 min=0.,
                 max=360.,
                 doc="",
                 ignore_errors=False,
                 call_setup=False):
        super(PhaseAttribute, self).__init__(increment=increment,
                                             min=min,
                                             max=max,
                                             doc=doc,
                                             ignore_errors=ignore_errors,
                                             call_setup=call_setup)

    def validate_and_normalize(self, value, module):
        """
        Rejects anything that is not float, and takes modulo 360
        """
        return super(PhaseAttribute, self).validate_and_normalize(value%360, module)


class FilterAttribute(BaseAttribute):
    """
    An attribute for a list of bandwidth. Each bandwidth has to be chosen in a list given by
    self.valid_frequencies(module) (evaluated at runtime). If floats are provided, they are normalized to the
    nearest values in the list. Individual floats are also normalized to a singleton.
    The number of elements in the list are also defined at runtime.
    """

    _widget_class = FilterAttributeWidget

    def validate_and_normalize(self, value, module):
        """
        Returns a list with the closest elements in module.valid_frequencies
        """
        if not np.iterable(value):
            value = [value]
        return [min([opt for opt in self.valid_frequencies(module)], key=lambda x: abs(x - val)) for val in value]


class ListFloatAttribute(BaseAttribute):
    """
    An arbitrary length list of float numbers.
    """
    _widget_class = ListFloatAttributeWidget

    def validate_and_normalize(self, value, module):
        """
        Converts the value in a list of float numbers.
        """
        if not np.iterable(value):
            value = [value]
        return [float(val) for val in value]


class ListComplexAttribute(BaseAttribute):
    """
    An arbitrary length list of complex numbers.
    """

    _widget_class = ListComplexAttributeWidget

    def validate_and_normalize(self, value, module):
        """
        Converts the value in a list of complex numbers.
        """
        if not np.iterable(value):
            value = [value]
        return [complex(val) for val in value]


class ModuleAttribute(BaseAttribute):
    """
    This class is used to handle submodules of a module.
    The ModuleAttribute is declared with:
    ModuleAttribute(module_cls, default, doc)

    The module_cls is instantiated in the __init__ of the parent module

    For the moment, the following actions are supported:
       - module.sub = dict(...) : module.sub.set_setup_attributes(dict(...))
       - module.sub: returns the submodule.
    """
    def __init__(self,
                 module_cls,
                 default=None,
                 doc="",
                 ignore_errors=False,
                 call_setup=False):
        self.module_cls = module_cls
        super(ModuleAttribute, self).__init__(default=default,
                                              doc=doc,
                                              ignore_errors=ignore_errors,
                                              call_setup=call_setup)


# docstring does not work yet, see:
# http://stackoverflow.com/questions/37255109/python-docstring-for-descriptors
# for now there is a workaround: call Module.help(register)
class BaseRegister(object):
    """Registers implement the necessary read/write logic for storing an attribute on the redpitaya.
    Interface for basic register of type int. To convert the value between register format and python readable
    format, registers need to implement "from_python" and "to_python" functions"""

    def __init__(self, address, doc="", bitmask=None):
        self.address = address
        self.__doc__ = doc
        self.bitmask = bitmask

    def get_value(self, obj, objtype=None):
        """
        Retrieves the value that is physically on the redpitaya device.
        """
        if obj is None:
            return self  # allows to access the descriptor by calling class.Register
            # see http://nbviewer.jupyter.org/urls/gist.github.com/ChrisBeaumont/5758381/raw/descriptor_writeup.ipynb
        # self.parent = obj  # store obj in memory
        if self.bitmask is None:
            return self.to_python(obj._read(self.address), obj)
        else:
            return self.to_python(obj._read(self.address) & self.bitmask, obj)

    def set_value(self, obj, val):
        """
        Sets the value on the redpitaya device.
        """
        # self.parent = obj  #store obj in memory<-- very bad practice: there is one Register for the class
        # and potentially many obj instances (think of having 2 redpitayas in the same python session), then
        # _read should use different clients depending on which obj is calling...)
        if self.bitmask is None:
            obj._write(self.address, self.from_python(val, obj))
        else:
            act = obj._read(self.address)
            new = act & (~self.bitmask) | (int(self.from_python(val, obj)) & self.bitmask)
            obj._write(self.address, new)

    def _writes(self, obj, addr, v):
        return obj._writes(addr, v)

    def _reads(self, obj, addr, l):
        return obj._reads(addr, l)

    def _write(self, obj, addr, v):
        return obj._write(addr, v)

    def _read(self, obj, addr):
        return obj._read(addr)


class NumberRegister(BaseRegister):
    """
    Base register for numbers.
    """
    def __init__(self, address, bits=64, **kwargs):
        super(NumberRegister, self).__init__(address=address, **kwargs)


class IntRegister(NumberRegister, IntAttribute):
    """
    Register for integer values encoded on less than 32 bits.
    """
    def __init__(self, address, bits=32, call_setup=False, **kwargs):
        super(IntRegister, self).__init__(address=address, **kwargs)
        IntAttribute.__init__(self, min=0, max=2 ** bits, increment=1,
                              call_setup=call_setup)
        self.bits = bits
        self.size = int(np.ceil(float(self.bits) / 32))

    def to_python(self, value, obj):
        return int(value)

    def from_python(self, value, obj):
        return int(value)


class LongRegister(IntRegister, IntAttribute):
    """Interface for register of python type int/long with arbitrary length 'bits' (effectively unsigned)"""

    def __init__(self, address, bits=64, **kwargs):
        super(LongRegister, self).__init__(address=address, **kwargs)
        IntAttribute.__init__(self, min=0, max=2 ** bits, increment=1)
        self.bits = bits
        self.size = int(np.ceil(float(self.bits) / 32))

    def get_value(self, obj, objtype=None):
        if obj is None:
            return self
        values = obj._reads(self.address, self.size)
        value = int(0)
        for i in range(self.size):
            value += int(values[i]) << (32 * i)
        if self.bitmask is None:
            return self.to_python(value, obj)
        else:
            return (self.to_python(value, obj) & self.bitmask)

    def set_value(self, obj, val):
        val = self.from_python(val, obj)
        values = np.zeros(self.size, dtype=np.uint32)
        if self.bitmask is None:
            for i in range(self.size):
                values[i] = (val >> (32 * i)) & 0xFFFFFFFF
        else:
            act = obj._reads(self.address, self.size)
            for i in range(self.size):
                localbitmask = (self.bitmask >> 32 * i) & 0xFFFFFFFF
                values[i] = ((val >> (32 * i)) & localbitmask) | \
                            (int(act[i]) & (~localbitmask))
        obj._writes(self.address, values)


class BoolRegister(BaseRegister, BoolAttribute):
    """Inteface for boolean values, 1: True, 0: False.
    invert=True inverts the mapping"""

    def __init__(self, address, bit=0, invert=False, call_setup=False, **kwargs):
        super(BoolRegister, self).__init__(address=address, **kwargs)
        BoolAttribute.__init__(self, call_setup=call_setup)
        self.bit = bit
        assert type(invert) == bool
        self.invert = invert

    def to_python(self, value, obj):
        value = bool((value >> self.bit) & 1)
        if self.invert:
            value = not value
        return value

    def set_value(self, obj, val):
        if self.invert:
            val = not val
        if val:
            v = obj._read(self.address) | (1 << self.bit)
        else:
            v = obj._read(self.address) & (~(1 << self.bit))
        obj._write(self.address, v)
        return val


class IORegister(BoolRegister):
    """Interface for digital outputs
    if argument outputmode is True, output mode is set, else input mode"""

    def __init__(self, read_address, write_address, direction_address,
                 outputmode=True, bit=0, **kwargs):
        if outputmode:
            address = write_address
        else:
            address = read_address
        super(IORegister, self).__init__(address=address, bit=bit, **kwargs)
        self.direction_address = direction_address
        # self.direction = BoolRegister(direction_address,bit=bit, **kwargs)
        self.outputmode = outputmode  # set output direction

    def direction(self, obj, v=None):
        """ sets the direction (inputmode/outputmode) for the Register """
        if v is None:
            v = self.outputmode
        if v:
            v = obj._read(self.address) | (1 << self.bit)
        else:
            v = obj._read(self.direction_address) & (~(1 << self.bit))
        obj._write(self.direction_address, v)

    def get_value(self, obj, objtype=None):
        if obj is None:
            return self
        # self.parent = obj  # store obj in memory <--- BAD, WHAT IF SEVERAL MODULES SHARE THE SAME REGISTER ?
        self.direction(obj)
        return super(IORegister, self).get_value(obj, objtype)

    def set_value(self, obj, val):
        # self.parent = obj  # store obj in memory
        self.direction(obj)
        return super(IORegister, self).set_value(obj, val)


class SelectRegister(BaseRegister, SelectAttribute):
    """Implements a selection, such as for multiplexers"""

    def __init__(self, address,
                 options={},
                 doc="",
                 call_setup=False,
                 **kwargs):
        super(SelectRegister, self).__init__(
            address=address,
            doc=doc + "\r\nOptions:\r\n" + str(options),
            **kwargs)
        SelectAttribute.__init__(self, options, call_setup=call_setup)
        self._options = Bijection(options)

    def to_python(self, value, obj):
        return self._options.inverse[value]

    def from_python(self, value, obj):
        return self._options[value]


class FloatRegister(BaseRegister, FloatAttribute):
    """Implements a fixed point register, seen like a (signed) float from python"""

    def __init__(self, address,
                 bits=14,  # total number of bits to represent on fpga
                 norm=1,  # fpga value corresponding to 1 in python
                 signed=True,  # otherwise unsigned
                 invert=False,  # if False: FPGA=norm*python, if True: FPGA=norm/python
                 **kwargs):
        super(FloatRegister, self).__init__(address=address, **kwargs)
        # if invert:
        #    raise NotImplementedError("increment not implemented for inverted registers")#return self.norm/2**self.bits
        # else:
        increment =  1./norm
        FloatAttribute.__init__(self, increment=increment, min=-norm, max=norm)
        self.bits = bits
        self.norm = float(norm)
        self.invert = invert
        self.signed = signed

    def to_python(self, value, obj):
        # 2's complement
        if self.signed:
            if value >= 2 ** (self.bits - 1):
                value -= 2 ** self.bits
        # normalization
        if self.invert:
            if value == 0:
                return float(0)
            else:
                return 1.0 / float(value) / self.norm
        else:
            return float(value) / self.norm

    def from_python(self, value, obj):
        # round and normalize
        if self.invert:
            if value == 0:
                v = 0
            else:
                v = int(round(1.0 / float(value) * self.norm))
        else:
            v = int(round(float(value) * self.norm))
            # make sure small float values are not rounded to zero
        if (v == 0 and value > 0):
            v = 1
        elif (v == 0 and value < 0):
            v = -1
        if self.signed:
            # saturation
            if (v >= 2 ** (self.bits - 1)):
                v = 2 ** (self.bits - 1) - 1
            elif (v < -2 ** (self.bits - 1)):
                v = -2 ** (self.bits - 1)
            # 2's complement
            if (v < 0):
                v += 2 ** self.bits
        else:
            v = abs(v)  # take absolute value
            # unsigned saturation
            if v >= 2 ** self.bits:
                v = 2 ** self.bits - 1
        return v

    def validate_and_normalize(self, value, module):
        """
        saturates to min/max, and rounds to the nearest value authorized by the register.
        """
        return super(FloatRegister, self).validate_and_normalize(int(round(value/self.increment))*self.increment, module)


class PhaseRegister(FloatRegister, PhaseAttribute):
    """Registers that contain a phase as a float in units of degrees."""

    def __init__(self, address, bits=32, **kwargs):
        super(PhaseRegister, self).__init__(address=address, bits=bits, **kwargs)
        PhaseAttribute.__init__(self, increment=360. / 2 ** bits)

    def from_python(self, value, obj):
        # make sure small float values are not rounded to zero
        if self.invert:
            value = float(value) * (-1)
        return int(round((float(value) % 360) / 360 * 2 ** self.bits) % 2 ** self.bits)

    def to_python(self, value, obj):
        phase = float(value) / 2 ** self.bits * 360
        if self.invert:
            phase *= -1
        return phase % 360.0

    def validate_and_normalize(self, value, module):
        """
        Rounds to nearest authorized register value and take modulo 360
        """
        value = (int(round((float(value) % 360) / 360 * 2 ** self.bits)) / 2 ** self.bits)*360.
        return value

class FrequencyRegister(FloatRegister, FrequencyAttribute):
    """Registers that contain a frequency as a float in units of Hz"""
    # attention: no bitmask can be defined for frequencyregisters
    CLOCK_FREQUENCY = 125e6

    def __init__(self, address,
                 bits=32,  # total number of bits to represent on fpga
                 **kwargs):
        super(FrequencyRegister, self).__init__(address=address, bits=bits, **kwargs)
        self.max = self.CLOCK_FREQUENCY / 2
        if self.invert:
            raise NotImplementedError("Increment not implemented for inverted registers")
        increment = self.CLOCK_FREQUENCY / 2 ** self.bits  # *obj._frequency_correction
        FloatAttribute.__init__(self, increment=increment, min=0, max=self.CLOCK_FREQUENCY * 0.5)

    def get_value(self, obj, objtype=None):
        if obj is None:
            return self
        return self.to_python(obj._read(self.address), obj)

    def set_value(self, obj, val):
        obj._write(self.address, self.from_python(val, obj))

    def from_python(self, value, obj):
        # make sure small float values are not rounded to zero
        value = abs(float(value) / obj._frequency_correction)
        if (value == epsilon):
            value = 1
        else:
            # round and normalize
            value = int(round(
                value / self.CLOCK_FREQUENCY * 2 ** self.bits))  # Seems correct (should not be 2**bits -1): 125 MHz
            # out of reach because 2**bits is out of reach
        return value

    def to_python(self, value, obj):
        return 125e6 / 2 ** self.bits * float(
            value) * obj._frequency_correction  # Seems correct (should not be 2**bits -1): 125 MHz
        # out of reach because 2**bits is out of reach

    def validate_and_normalize(self, value, module):
        """
        Same as FloatRegister, except the value should be positive.
        """
        return FrequencyAttribute.validate_and_normalize(self,
                                                         FloatRegister.validate_and_normalize(self, value, module),
                                                         module)


class FilterRegister(BaseRegister, FilterAttribute):
    """
    Interface for up to 4 low-/highpass filters in series (filter_block.v)
    """
    _widget_class = FilterAttributeWidget

    def __init__(self, address, filterstages, shiftbits, minbw, **kwargs):
        super(FilterRegister, self).__init__(address=address, **kwargs)
        FilterAttribute.__init__(self, **kwargs)
        self.filterstages = filterstages
        self.shiftbits = shiftbits
        self.minbw = minbw

    def read_and_save(self, obj, attr_name):
        # save the value upon first execution in order to only read this once
        var_name = self.name + "_" + attr_name
        if not hasattr(obj, var_name):
            setattr(obj, var_name, obj._read(getattr(self, attr_name)))
        return getattr(obj, var_name)

    def _FILTERSTAGES(self, obj):
        return self.read_and_save(obj, "filterstages")

    def _SHIFTBITS(self, obj):
        return self.read_and_save(obj, "shiftbits")

    def _MINBW(self, obj):
        return self.read_and_save(obj, "minbw")

    def _ALPHABITS(self, obj):
        return int(np.ceil(np.log2(125000000 / self._MINBW(obj))))

    def valid_frequencies(self, obj):
        # this function NEEDS TO BE OPTIMIZED: TAKES 50 ms !!!!
        """ returns a list of all valid filter cutoff frequencies"""
        valid_bits = range(0, 2 ** self._SHIFTBITS(obj))
        pos = list([self.to_python(b | 0x1 << 7, obj) for b in valid_bits])
        pos = [int(val) if not np.iterable(val) else int(val[0]) for val in pos]
        neg = [-val for val in reversed(pos)]
        return neg + [0] + pos

    def to_python(self, value, obj):
        """
        returns a list of bandwidths for the low-pass filter cascade before the module
        negative bandwidth stands for high-pass instead of lowpass, 0 bandwidth for bypassing the filter
        """

        filter_shifts = value
        shiftbits = self._SHIFTBITS(obj)
        alphabits = self._ALPHABITS(obj)
        bandwidths = []
        for i in range(self._FILTERSTAGES(obj)):
            v = (filter_shifts >> (i * 8)) & 0xFF
            shift = v & (2 ** shiftbits - 1)
            filter_on = ((v >> 7) == 0x1)
            highpass = (((v >> 6) & 0x1) == 0x1)
            if filter_on:
                bandwidth = float(2 ** shift) / \
                            (2 ** alphabits) * 125e6 / 2 / np.pi
                if highpass:
                    bandwidth *= -1.0
            else:
                bandwidth = 0
            bandwidths.append(bandwidth)
        if len(bandwidths) == 1:
            return bandwidths[0]
        else:
            return bandwidths

    def from_python(self, value, obj):
        filterstages = self._FILTERSTAGES(obj)
        try:
            v = list(value)[:filterstages]
        except TypeError:
            v = list([value])[:filterstages]
        filter_shifts = 0
        shiftbits = self._SHIFTBITS(obj)
        alphabits = self._ALPHABITS(obj)
        for i in range(filterstages):
            if len(v) <= i:
                bandwidth = 0
            else:
                bandwidth = float(v[i])
            if bandwidth == 0:
                continue
            else:
                shift = int(np.round(np.log2(np.abs(bandwidth) * \
                                             (2 ** alphabits) * 2 * np.pi / 125e6)))
                if shift < 0:
                    shift = 0
                elif shift > (2 ** shiftbits - 1):
                    shift = (2 ** shiftbits - 1)
                shift += 2 ** 7  # turn this filter stage on
                if bandwidth < 0:
                    shift += 2 ** 6  # turn this filter into a highpass
                filter_shifts += (shift) * 2 ** (8 * i)
        return filter_shifts


class PWMRegister(FloatRegister, FloatAttribute):
    # FloatRegister that defines the PWM voltage similar to setting a float
    # see FPGA code for more detailed description on how the PWM works
    def __init__(self, address, CFG_BITS=24, PWM_BITS=8, **kwargs):
        super(PWMRegister, self).__init__(address=address, bits=14, norm=1, **kwargs)
        self.min = 0   # voltage of pwm outputs ranges from 0 to 1.8 volts
        self.max = 1.8
        self.increment = (self.max-self.min)/2**(self.bits-1)  # actual resolution is 14 bits (roughly 0.1 mV incr.)
        self.CFG_BITS = int(CFG_BITS)
        self.PWM_BITS = int(PWM_BITS)

    def to_python(self, value, obj):
        value = int(value)
        pwm = float(value >> (self.CFG_BITS - self.PWM_BITS) & (2 ** self.PWM_BITS - 1))
        mod = value & (2 ** (self.CFG_BITS - self.PWM_BITS) - 1)
        postcomma = float(bin(mod).count('1')) / (self.CFG_BITS - self.PWM_BITS)
        voltage = 1.8 * (pwm + postcomma) / 2 ** self.PWM_BITS
        if voltage > 1.8:
            logger.error("Readout value from PWM (%h) yields wrong voltage %f",
                         value, voltage)
        return voltage

    def from_python(self, value, obj):
        # here we don't bother to minimize the PWM noise
        # room for improvement is in the low -> towrite conversion
        value = 0 if (value < 0) else float(value) / 1.8 * (2 ** self.PWM_BITS)
        high = np.floor(value)
        if (high >= 2 ** self.PWM_BITS):
            high = 2 ** self.PWM_BITS - 1
        low = int(np.round((value - high) * (self.CFG_BITS - self.PWM_BITS)))
        towrite = int(high) << (self.CFG_BITS - self.PWM_BITS)
        towrite += ((1 << low) - 1) & ((1 << self.CFG_BITS) - 1)
        return towrite

    # validate_and_normalize from FloatRegister is fine


class BaseProperty(object):
    """
    A Property is a special type of attribute that is not mapping a fpga value,
    but rather an attribute _attr_name of the module. This is used mainly in
    SoftwareModules
    """
    def get_value(self, obj, obj_type):
        if obj is None:
            return self
        if not hasattr(obj, '_' + self.name):
            setattr(obj, '_' + self.name, self.default)
        return getattr(obj, '_' + self.name)

    def set_value(self, obj, val):
        setattr(obj, '_' + self.name, val)
        return val  # maybe better with getattr... but more expensive


class SelectProperty(SelectAttribute, BaseProperty):
    """
    A property for multiple choice values, if options are numbers, rounding will be performed,
    otherwise validator is strict.
    """
    def get_value(self, obj, obj_type):
        if obj is None:
            return self
        if not hasattr(obj, '_' + self.name):
            # choose any value in the options as default.
            default = sorted(self.options(obj))
            if len(default) > 0:
                val = default[0]
                setattr(obj, '_' + self.name, val)
                return val
            else:
                return None
        return getattr(obj, '_' + self.name)


#class DynamicSelectProperty(DynamicSelectAttribute, BaseProperty):
#    """
#    A property for multiple choice values, the options can be set dynamically at runtime
#    """
#    def get_value(self, obj, obj_type):
#        if obj is None:
#            return self
#        if not hasattr(obj, '_' + self.name):
#            # choose any value in the options as default.
#            default = sorted(self.options(obj))[0]
#            setattr(obj, '_' + self.name, default)
#        return getattr(obj, '_' + self.name)


class StringProperty(StringAttribute, BaseProperty):
    """
    A property for a string value
    """
    default = ""


class PhaseProperty(PhaseAttribute, BaseProperty):
    """
    A property for a phase value
    """
    default = 0


class FloatProperty(FloatAttribute, BaseProperty):
    """
    A property for a float value
    """
    default = 0.


class FrequencyProperty(FrequencyAttribute, BaseProperty):
    """
    A property for a frequency value
    """
    default = 0.
    min = 0.


class LongProperty(IntAttribute, BaseProperty):
    """
    A property for a long value
    """
    def __init__(self,
                 min=0,
                 max=2**14,
                 increment=1,
                 default=0,
                 doc="",
                 ignore_errors=False,
                 call_setup=False):
        super(LongProperty, self).__init__(min=min,
                                           max=max,
                                           increment=increment,
                                           default=default,
                                           doc=doc,
                                           ignore_errors=ignore_errors,
                                           call_setup=call_setup)
    default = 0


class BoolProperty(BoolAttribute, BaseProperty):
    """
    A property for a boolean value
    """
    default = False

class BoolIgnoreProperty(BoolIgnoreAttribute, BaseProperty):
    """
    A property for a boolean value
    """
    default = False


class FilterProperty(FilterAttribute, BaseProperty):
    """
    A property for a list of float values to be chosen in valid_frequencies(module).
    """
    def get_value(self, obj, obj_type):
        if obj is None:
            return self
        if not hasattr(obj, '_' + self.name):
            # choose any value in the options as default.
            default = self.valid_frequencies(obj)[0]
            setattr(obj, '_' + self.name, default)
        return getattr(obj, '_' + self.name)

    def set_value(self, obj, value):
        return super(FilterProperty, self).set_value(obj, value)


class ListFloatProperty(ListFloatAttribute, BaseProperty):
    """
    A property for list of float values
    """
    default = [0, 0, 0, 0]


class ListComplexProperty(ListComplexAttribute, BaseProperty):
    """
    A property for a list of complex values
    """
    default = [0.]

