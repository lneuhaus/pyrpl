"""
The parameters of any module are controlled by descriptors deriving from
:obj:`BaseAttribute`.

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
from functools import partial
from .pyrpl_utils import recursive_getattr, recursive_setattr
from .widgets.attribute_widgets import BoolAttributeWidget, \
                                       FloatAttributeWidget, \
                                       FilterAttributeWidget, \
                                       IntAttributeWidget, \
                                       SelectAttributeWidget, \
                                       StringAttributeWidget, \
                                       BoolIgnoreAttributeWidget, \
                                       TextAttributeWidget, \
                                       CurveAttributeWidget, \
                                       DataAttributeWidget, \
                                       CurveSelectAttributeWidget, \
                                       LedAttributeWidget, \
                                       PlotAttributeWidget, \
                                       BasePropertyListPropertyWidget, \
                                       ComplexAttributeWidget

from .curvedb import CurveDB
from collections import OrderedDict
import logging
import sys
import numpy as np
import numbers

logger = logging.getLogger(name=__name__)

#way to represent the smallest positive value
#needed to set floats to minimum count above zero
epsilon = sys.float_info.epsilon


class BaseAttribute(object):
    """base class for attribute - only used as a placeholder"""

class BaseProperty(BaseAttribute):
    """
    A Property is a special type of attribute that is not mapping a fpga value,
    but rather an attribute _name of the module. This is used mainly in
    SoftwareModules

    An attribute is a field that can be set or get by several means:

    * programmatically: module.attribute = value
    * graphically: attribute.create_widget(module) returns a widget to
      manipulate the value
    * via loading the value in a config file for permanence

    The concrete derived class need to have certain attributes properly
    defined:

    * widget_class: the class of the widget to use for the gui (see
      attribute_widgets.py)
    * a function set_value(instance, value) that effectively sets the value
      (on redpitaya or elsewhere)
    * a function get_value(instance) that reads the value from
      wherever it is stored internally

    """
    _widget_class = None
    widget = None
    default = None

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

    def __set__(self, obj, value):
        """
        This function is called for any BaseAttribute, such that all the gui
        updating, and saving to disk is done automatically. The real work is
        delegated to self.set_value.
        """
        value = self.validate_and_normalize(obj, value)
        self.set_value(obj, value)
        # save new value in config, lauch signal and possibly call setup()
        self.value_updated(obj, value)#self.get_value(obj))

    def validate_and_normalize(self, obj, value):
        """
        This function should raise an exception if the value is incorrect.
        Normalization can be:

        - returning value.name if attribute "name" exists
        - rounding to nearest multiple of step for float_registers
        - rounding elements to nearest valid_frequencies for FilterAttributes
        """
        return value  # by default any value is valid

    def value_updated(self, module, value=None, appendix=[]):
        """
        Once the value has been changed internally, this function is called to perform the following actions:

        - launch the signal module._signal_launcher.attribute_changed (this is
          used in particular for gui update)
        - saves the new value in the config file (if flag
          module._autosave_active is True).
        - calls the callback function if the attribute is in module.callback

         Note for developers: We might consider moving the 2 last points in a connection behind the signal "attribute_changed".
        """
        if value is None:
            value = self.get_value(module)
        self.launch_signal(module, value, appendix=appendix)
        if module._autosave_active:  # (for module, when module is slaved, don't save attributes)
            if self.name in module._setup_attributes:
                self.save_attribute(module, value)
        if self.call_setup and not module._setup_ongoing:
            # call setup unless a bunch of attributes are being changed together.
            module._logger.debug('Calling setup() for %s.%s ...', module.name, self.name)
            module.setup()
        return value

    def __get__(self, instance, owner):
        # self.parent = instance
        #store instance in memory <-- very bad practice: there is one Register for the class
        # and potentially many obj instances (think of having 2 redpitayas in the same python session), then
        # _read should use different clients depending on which obj is calling...)
        if instance is None:
            return self
        return self.get_value(instance)

    def launch_signal(self, module, new_value, appendix=[]):
        """
        Updates the widget and other subscribers with the module's value.
        """
        try:
            module._signal_launcher.update_attribute_by_name.emit(
                self.name,
                [new_value]+appendix)
        except AttributeError as e:  # occurs if nothing is connected (TODO:
            # remove this)
            module._logger.error("Error in launch_signal of %s: %s",
                                 module.name, e)

    def save_attribute(self, module, value):
        """
        Saves the module's value in the config file.
        """
        module.c[self.name] = value

    def _create_widget(self, module, widget_name=None):
        """
        Creates a widget to graphically manipulate the attribute.
        """
        if self._widget_class is None:
            logger.warning("Module %s of type %s is trying to create a widget "
                           "for %s, but no _widget_class is defined!",
                           str(module), type(module), self.name)
            return None
        widget = self._widget_class(module, self.name, widget_name=widget_name)
        return widget

    def get_value(self, obj):
        if not hasattr(obj, '_' + self.name):
            setattr(obj, '_' + self.name, self.default)
        return getattr(obj, '_' + self.name)

    def set_value(self, obj, val):
        setattr(obj, '_' + self.name, val)


class BaseRegister(BaseProperty):
    """Registers implement the necessary read/write logic for storing an attribute on the redpitaya.
    Interface for basic register of type int. To convert the value between register format and python readable
    format, registers need to implement "from_python" and "to_python" functions"""
    default = None
    def __init__(self, address, bitmask=None, **kwargs):
        self.address = address
        self.bitmask = bitmask
        BaseProperty.__init__(self, **kwargs)

    def _writes(self, obj, addr, v):
        return obj._writes(addr, v)

    def _reads(self, obj, addr, l):
        return obj._reads(addr, l)

    def _write(self, obj, addr, v):
        return obj._write(addr, v)

    def _read(self, obj, addr):
        return obj._read(addr)

    def get_value(self, obj):
        """
        Retrieves the value that is physically on the redpitaya device.
        """
        # self.parent = obj  # store obj in memory
        if self.bitmask is None:
            return self.to_python(obj, obj._read(self.address))
        else:
            return self.to_python(obj, obj._read(self.address) & self.bitmask)

    def set_value(self, obj, val):
        """
        Sets the value on the redpitaya device.
        """
        if self.bitmask is None:
            obj._write(self.address, self.from_python(obj, val))
        else:
            act = obj._read(self.address)
            new = act & (~self.bitmask) | (int(self.from_python(obj, val)) & self.bitmask)
            obj._write(self.address, new)

    def __set__(self, obj, value):
        """
        this is very similar to the __set__ function of the parent,
        but here, value_updated is called with the return from
        validate_and_normalize instead of with the new from get_value in
        order to save one read operation.
        """
        value = self.validate_and_normalize(obj, value)
        self.set_value(obj, value)
        # save new value in config, lauch signal and possibly call setup()
        self.value_updated(obj, value)


class BoolProperty(BaseProperty):
    """
    A property for a boolean value
    """
    _widget_class = BoolAttributeWidget
    default = False

    def validate_and_normalize(self, obj, value):
        """
        Converts value to bool.
        """
        return bool(value)


class LedProperty(BoolProperty):
    _widget_class = LedAttributeWidget

    def __init__(self,
                 true_function = None,
                 false_function = None,
                 **kwargs):
        """
        default: if provided, the value is initialized to it
        """
        self.true_function = true_function or self.true_function
        self.false_function = false_function or self.false_function
        super(LedProperty, self).__init__(**kwargs)

    def set_value(self, obj, val):
        try:
            if val:
                self.true_function(obj)
            else:
                self.false_function(obj)
        except TypeError as e:
            obj._logger.debug('Cannot call %s of %s.%s: %s',
                              'true_function' if val else 'false_function',
                              obj.name, self.name, e)
        else:
            super(LedProperty, self).set_value(obj, val)


class BoolRegister(BaseRegister, BoolProperty):
    """Inteface for boolean values, 1: True, 0: False.
    invert=True inverts the mapping"""
    def __init__(self, address, bit=0, bitmask=None, invert=False, **kwargs):
        self.bit = bit
        assert type(invert) == bool
        self.invert = invert
        BaseRegister.__init__(self, address=address, bitmask=bitmask)
        BoolProperty.__init__(self, **kwargs)

    def to_python(self, obj, value):
        value = bool((value >> self.bit) & 1)
        if self.invert:
            value = not value
        return value

    def from_python(self, obj, val):
        if self.invert:
            val = not val
        if val:
            towrite = obj._read(self.address) | (1 << self.bit)
        else:
            towrite = obj._read(self.address) & (~(1 << self.bit))
        return towrite


class BoolIgnoreProperty(BoolProperty):
    """
    An attribute for booleans
    """
    _widget_class = BoolIgnoreAttributeWidget
    default = False

    def validate_and_normalize(self, obj, value):
        """
        Converts value to bool.
        """
        if isinstance(value, str):  # used to be basestring
            if value.lower() == 'true':
                return True
            elif value.lower() == 'false':
                return False
            else:
                return 'ignore'
        else:
            return bool(value)


class IORegister(BoolRegister):
    """Interface for digital outputs
    if argument outputmode is True, output mode is set, else input mode"""
    def __init__(self, read_address, write_address, direction_address,
                 outputmode=True, **kwargs):
        self.write_address = write_address
        self.read_address = read_address
        if outputmode:
            address = write_address
        else:
            address = read_address
        self.direction_address = direction_address
        # self.direction = BoolRegister(direction_address,bit=bit, **kwargs)
        self.outputmode = outputmode  # set output direction
        BoolRegister.__init__(self, address=address, **kwargs)

    def direction(self, obj, v=None):
        """ sets the direction (inputmode/outputmode) for the Register """
        if v is None:
            v = self.outputmode
        else:
            self.outputmode = v
        self.address = self.write_address if v else self.read_address
        if v:
            v = obj._read(self.direction_address) | (1 << self.bit)
        else:
            v = obj._read(self.direction_address) & (~(1 << self.bit))
        obj._write(self.direction_address, v)

    def get_value(self, obj):
        self.direction(obj)
        return BoolRegister.get_value(self, obj)

    def set_value(self, obj, val):
        self.direction(obj)
        return BoolRegister.set_value(self, obj, val)


class NumberProperty(BaseProperty):
    """
    Abstract class for ints and floats
    """
    _widget_class = IntAttributeWidget
    default = 0

    def __init__(self,
                 min=-np.inf,
                 max=np.inf,
                 increment=0,
                 log_increment=False,  # if True, the widget has log increment
                 **kwargs):
        self.min = min
        self.max = max
        self.increment = increment
        self.log_increment = log_increment
        BaseProperty.__init__(self, **kwargs)

    def _create_widget(self, module, widget_name=None):
        widget = BaseProperty._create_widget(self, module,
                                             widget_name=widget_name)
        return widget

    def validate_and_normalize(self, obj, value):
        """
        Saturates value with min and max.
        """
        if value is None:  # setting a number to None essentially calls setup()
            value = self.get_value(obj)
        return max(min(value, self.max), self.min)


class IntProperty(NumberProperty):
    def __init__(self,
                 min=-np.inf,
                 max=np.inf,
                 increment=1,
                 log_increment=False,  # if True, the widget has log increment
                 **kwargs):
        super(IntProperty, self).__init__(min=min,
                                          max=max,
                                          increment=increment,
                                          log_increment=log_increment,
                                          **kwargs)

    def validate_and_normalize(self, obj, value):
        """
        Accepts float, but rounds to integer
        """
        if value is None:  # setting a number to None essentially calls setup()
            value = self.get_value(obj)
        return NumberProperty.validate_and_normalize(self,
                                                     obj,
                                                     int(round(value)))


class IntRegister(BaseRegister, IntProperty):
    """
    Register for integer values encoded on less than 32 bits.
    """
    def __init__(self, address, bits=32, bitmask=None, **kwargs):
        self.bits = bits
        self.size = int(np.ceil(float(self.bits) / 32))
        BaseRegister.__init__(self, address=address, bitmask=bitmask)
        if not 'min' in kwargs: kwargs['min'] = 0
        if not 'max' in kwargs: kwargs['max'] = 2**self.bits-1
        IntProperty.__init__(self,
                             **kwargs)

    def to_python(self, obj, value):
        return int(value)

    def from_python(self, obj, value):
        return int(value)


class ConstantIntRegister(IntRegister):
    """
    Implements an int register that only interacts with the FPGA once and
    subsequently returns the first read value from python memory.
    """
    def get_value(self, obj):
        try:
            return getattr(obj, '_' + self.name)
        except AttributeError:
            value = super(ConstantIntRegister, self).get_value(obj)
            setattr(obj, '_' + self.name, value)
            return value


class LongRegister(IntRegister):
    """Interface for register of python type int/long with arbitrary length 'bits' (effectively unsigned)"""
    def get_value(self, obj):
        values = obj._reads(self.address, self.size)
        value = int(0)
        for i in range(self.size):
            value += int(values[i]) << (32 * i)
        if self.bitmask is None:
            return self.to_python(obj, value)
        else:
            return (self.to_python(obj, value) & self.bitmask)

    def set_value(self, obj, val):
        val = self.from_python(obj, val)
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


class FloatProperty(NumberProperty):
    """
    An attribute for a float value.
    """
    _widget_class = FloatAttributeWidget
    default = 0.0

    def validate_and_normalize(self, obj, value):
        """
        Try to convert to float, then saturates with min and max
        """
        return NumberProperty.validate_and_normalize(self,
                                                     obj,
                                                     float(value))


class ComplexProperty(FloatProperty):
    _widget_class = ComplexAttributeWidget
    def validate_and_normalize(self, obj, val):
        val = complex(val)
        re = super(ComplexProperty, self).validate_and_normalize(obj, val.real)
        im = super(ComplexProperty, self).validate_and_normalize(obj, val.imag)
        return complex(re, im)


class FloatRegister(IntRegister, FloatProperty):
    """Implements a fixed point register, seen like a (signed) float from python"""
    def __init__(self, address,
                 bits=14,  # total number of bits to represent on fpga
                 bitmask=None,
                 norm=1.0,  # fpga value corresponding to 1 in python
                 signed=True,  # otherwise unsigned
                 invert=False,  # if False: FPGA=norm*python, if True: FPGA=norm/python
                 **kwargs):
        IntRegister.__init__(self, address=address, bits=bits, bitmask=bitmask)
        self.invert = invert
        self.signed = signed
        self.norm = float(norm)
        if 'increment' not in kwargs:
            kwargs['increment'] = 1.0/self.norm
        if 'max' not in kwargs:
            kwargs['max'] = (float(2 ** (self.bits - int(self.signed)) - 1) / self.norm)
        if 'min' not in kwargs:
            if self.signed:
                kwargs['min'] = - float(2 ** (self.bits - int(self.signed))) / self.norm
            else:
                kwargs['min'] = 0
        FloatProperty.__init__(self, **kwargs)

    def to_python(self, obj, value):
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

    def from_python(self, obj, value):
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

    def validate_and_normalize(self, obj, value):
        """
        For unsigned registers, takes the absolute value of the given value.
        Rounds to the nearest value authorized by the register granularity,
        then does the same as FloatProperty (==NumberProperty).
        """
        if not self.signed:
            value = abs(value)
        return FloatProperty.validate_and_normalize(self, obj,
                                round(value/self.increment)*self.increment)


class GainRegister(FloatRegister):
    """
    A register used mainly for gains, that replaces round-off to zero by
    round-off to the lowest-possible value.
    """
    avoid_round_off_to_zero = True

    def validate_and_normalize(self, obj, value):
        rounded_value = FloatRegister.validate_and_normalize(self, obj, value)
        if rounded_value == 0 and value != 0:  # value was rounded off to zero
            if self.avoid_round_off_to_zero:
                rounded_value = FloatRegister.validate_and_normalize(
                    self, obj, np.abs(self.increment)*np.sign(value))
                obj._logger.warning("Avoided rounding value %.1e of the "
                                    "gain register %s to zero. Setting it to %.1e "
                                    "instead. ", value, self.name, rounded_value)
            else:
                obj._logger.warning("Rounding value %.1e of the "
                                    "gain register %s to zero. ", value, self.name)
        if value > self.max or value < self.min:
            obj._logger.warning("Requested gain for %s.%s is outside the "
                                "bounds allowed by the hardware. Desired "
                                "gain of %.1e is capped to %.1e. ",
                                obj.name, self.name, value, rounded_value)
        return rounded_value


class FrequencyProperty(FloatProperty):
    """
    An attribute for frequency values
    Same as FloatAttribute, except it cannot become negative.
    """
    def __init__(self, **kwargs):
        if 'min' not in kwargs:
            kwargs['min'] = 0
        FloatProperty.__init__(self, **kwargs)


class FrequencyRegister(FloatRegister, FrequencyProperty):
    """Registers that contain a frequency as a float in units of Hz"""
    # attention: no bitmask can be defined for frequencyregisters
    CLOCK_FREQUENCY = 125e6

    def __init__(self, address, **kwargs):
        FloatRegister.__init__(self, address, **kwargs)
        self.min = 0
        self.max = self.CLOCK_FREQUENCY / 2.0
        self.increment = self.CLOCK_FREQUENCY / 2 ** self.bits

    def from_python(self, obj, value):
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

    def to_python(self, obj, value):
        return 125e6 / 2 ** self.bits * float(
            value) * obj._frequency_correction

    def validate_and_normalize(self, obj, value):
        """
        Same as FloatRegister, except the value should be positive.
        """
        return FrequencyProperty.validate_and_normalize(self, obj,
                        FloatRegister.validate_and_normalize(self, obj, value))


class PhaseProperty(FloatProperty):
    """
    An attribute to represent a phase
    """
    def validate_and_normalize(self, obj, value):
        """
        Rejects anything that is not float, and takes modulo 360
        """
        return FloatProperty.validate_and_normalize(self,
                                                    obj,
                                                    value % 360.)


class PhaseRegister(FloatRegister, PhaseProperty):
    """Registers that contain a phase as a float in units of degrees."""
    def __init__(self, address, bits=32, bitmask=None, invert=False, **kwargs):
        FloatRegister.__init__(self, address=address, bits=bits,
                               bitmask=bitmask, invert=invert)
        PhaseProperty.__init__(self, increment=360. / 2 ** bits, **kwargs)

    def from_python(self, obj, value):
        if self.invert:
            value = float(value) * (-1)
        return int(round(float(value) / 360 * 2 ** self.bits) % 2 ** self.bits)

    def to_python(self, obj, value):
        phase = float(value) / 2 ** self.bits * 360
        if self.invert:
            phase *= -1
        return phase % 360.0

    def validate_and_normalize(self, obj, value):
        """
        Rounds to nearest authorized register value and take modulo 360
        """
        return ((int(round(float(value) / 360 * 2 ** self.bits)) / 2 ** self.bits) * 360.) % 360.0


class FilterProperty(BaseProperty):
    """
    An attribute for a list of bandwidth. Each bandwidth has to be chosen in a list given by
    self.valid_frequencies(module) (evaluated at runtime). If floats are provided, they are normalized to the
    nearest values in the list. Individual floats are also normalized to a singleton.
    The number of elements in the list are also defined at runtime.
    A property for a list of float values to be chosen in valid_frequencies(module).
    """
    _widget_class = FilterAttributeWidget

    def validate_and_normalize(self, obj, value):
        """
        Returns a list with the closest elements in module.valid_frequencies
        """
        if not np.iterable(value):
            value = [value]
        value = [min([opt for opt in self.valid_frequencies(obj)],
                      key=lambda x: abs(x - val)) for val in value]
        if len(value) == 1:
            return value[0]
        else:
            return value

    def get_value(self, obj):
        if not hasattr(obj, '_' + self.name):
            # choose any value in the options as default.
            default = self.valid_frequencies(obj)[0]
            setattr(obj, '_' + self.name, default)
        return getattr(obj, '_' + self.name)

    def set_value(self, obj, value):
        return BaseProperty.set_value(self, obj, value)

    def valid_frequencies(self, module):
        raise NotImplementedError("this is a baseclass, your derived class "
                                  "must implement the following function")

    def refresh_options(self, module):
        module._signal_launcher.refresh_filter_options.emit(self.name)


class FilterRegister(BaseRegister, FilterProperty):
    """
    Interface for up to 4 low-/highpass filters in series (filter_block.v)
    """
    _widget_class = FilterAttributeWidget

    def __init__(self, address, filterstages, shiftbits, minbw, **kwargs):
        self.filterstages = filterstages
        self.shiftbits = shiftbits
        self.minbw = minbw
        BaseRegister.__init__(self, address=address)
        FilterProperty.__init__(self, **kwargs)

    def read_and_save(self, obj, attr_name):
        # save the value of constants saved in the fpga upon first execution
        # in order to only read the corresponding register once
        var_name = "_" + self.name + "_" + attr_name
        if not hasattr(obj, var_name):
            setattr(obj, var_name, obj._read(getattr(self, attr_name)))
        return getattr(obj, var_name)

    def _FILTERSTAGES(self, obj):
        return self.read_and_save(obj, "filterstages")

    def _SHIFTBITS(self, obj):
        return self.read_and_save(obj, "shiftbits")

    def _MINBW(self, obj):
        return self.read_and_save(obj, "minbw")

    def _MAXSHIFT(self, obj):
        def clog2(x):
            """ mirrors the function clog2 in verilog code """
            if x < 2:
                return 1
            elif x > 2**32:
                return -1
            elif x > 2**31:
                return 32
            else:
                return int(np.floor(np.log2(float(x))))+1
        return clog2(125000000.0/float(self._MINBW(obj)))

    #def _ALPHABITS(self, obj):
    #    return int(np.ceil(np.log2(125000000.0 / self._MINBW(obj))))

    def valid_frequencies(self, obj):
        """ returns a list of all valid filter cutoff frequencies"""
        #valid_bits = range(0, self._MAXSHIFT(obj)-1)  # this is possible
        valid_bits = range(0, self._MAXSHIFT(obj)-2)  # this gives reasonable results (test_filter)
        pos = list([self.to_python(obj, b | 0x1 << 7) for b in valid_bits])
        pos = [val if not np.iterable(val) else val[0] for val in pos]
        neg = [-val for val in reversed(pos)]
        valid_frequencies = neg + [0] + pos
        if obj is not None and not hasattr(obj.__class__,
                                           self.name+'_options') and not hasattr(obj, self.name+'_options'):
            setattr(obj, self.name+'_options', valid_frequencies)
        return valid_frequencies

    # empirical correction factors for the cutoff frequencies in order to be
    # able to accurately model implemented bandwidth with an analog
    # butterworth filter. Works well up to 5 MHz. See unittest test_inputfilter
    correction_factors = {0.5: 0.7,
                          0.25: 1.65,
                          0.125: 1.17,
                          0.0625: 1.08,
                          0.03125: 1.04,
                          0.015625: 1.02,
                          0.0078125: 1.01,
                          0.001953125: 1.0,
                          0.00390625: 1.0}

    def to_python(self, obj, value):
        """
        returns a list of bandwidths for the low-pass filter cascade before the module
        negative bandwidth stands for high-pass instead of lowpass, 0 bandwidth for bypassing the filter
        """
        filter_shifts = value
        bandwidths = []
        for i in range(self._FILTERSTAGES(obj)):
            v = (filter_shifts >> (i * 8)) & 0xFF
            shift = v & (2 ** self._SHIFTBITS(obj) - 1)
            filter_on = ((v >> 7) == 0x1)
            highpass = (((v >> 6) & 0x1) == 0x1)
            if filter_on:
                # difference equation is
                # y[n] = (1-alpha)*y[n-1] + alpha*x[n]
                alpha = float(2 ** shift) / (2 ** self._MAXSHIFT(obj))
                # old formula
                #bandwidth = alpha * 125e6 / 2 / np.pi
                # new, more correct formula (from Oppenheim-Schafer p. 70)
                bandwidth = -np.log(1.0-alpha)/2.0/np.pi*125e6
                # here comes a nasty bugfix to make it work (see issue 242)
                if alpha in self.correction_factors:
                    bandwidth *= self.correction_factors[alpha]
                if highpass:
                    bandwidth *= -1.0
            else:
                bandwidth = 0
            bandwidths.append(bandwidth)
        if len(bandwidths) == 1:
            return bandwidths[0]
        else:
            return bandwidths

    def from_python(self, obj, value):
        try:
            v = list(value)[:self._FILTERSTAGES(obj)]
        except TypeError:
            v = list([value])[:self._FILTERSTAGES(obj)]
        filter_shifts = 0
        for i in range(self._FILTERSTAGES(obj)):
            if len(v) <= i:
                bandwidth = 0
            else:
                bandwidth = float(v[i])
            if bandwidth == 0:
                continue
            else:
                # old formula
                #alpha = np.abs(bandwidth)*2*np.pi/125e6
                # new formula
                alpha = 1.0 - np.exp(-np.abs(bandwidth)*2.0*np.pi/125e6)
                if alpha in self.correction_factors:
                    bandwidth /= self.correction_factors[alpha]
                    alpha = 1.0 - np.exp(-np.abs(bandwidth)*2.0*np.pi/125e6)
                shift = int(np.round(np.log2(alpha*(2**self._MAXSHIFT(obj)))))
                if shift < 0:
                    shift = 0
                elif shift > (2**self._SHIFTBITS(obj) - 1):
                    shift = (2**self._SHIFTBITS(obj) - 1)
                shift += 2**7  # turn this filter stage on
                if bandwidth < 0:
                    shift += 2**6  # turn this filter into a highpass
                filter_shifts += shift * 2**(8*i)
        return filter_shifts


class AttributeList(list):
    """
    A list of attributes.

    This class is not an attribute/property by itself, but is the object
    returned by AttributeListProperty that correctly extends list methods to
    communicate a change in the list throughout pyrpl.

    When a list-specific operation is performed that alters the values,
    the AttributeListProperty object is informed about this and will ensure
    the correct propagation of the signal.
    """
    def __init__(self, parent, module, *args, **kwargs):
        self._parent = parent
        self._module = module
        super(AttributeList, self).__init__(*args, **kwargs)

    # insert, __setitem__, and __delitem__ completely describe the behavior
    def insert(self, index, new=None):
        if new is None:
            new = self._parent.default_element or self._parent.element_cls.default
        new = self._parent.validate_and_normalize_element(self._module, new)
        super(AttributeList, self).insert(index, new)
        self._parent.list_changed(self._module, "insert", index, new)
        self.selected = index

    def __setitem__(self, index, value):
        # rely on parent's validate_and_normalize function
        value = self._parent.validate_and_normalize_element(self._module, value)
        # set value
        super(AttributeList, self).__setitem__(index, value)
        self._parent.list_changed(self._module, "setitem", index, value)
        self.selected = index

    def __delitem__(self, index=-1):
        # unselect if selected
        if self.selected == self._get_unique_index(index):
            self.selected = None
        # remove and send message
        super(AttributeList, self).pop(index)
        self._parent.list_changed(self._module, "delitem", index)

    @property
    def selected(self):
        if not hasattr(self, '_selected'):
            self._selected = None
        return self._selected

    @selected.setter
    def selected(self, index):
        # old = self.selected
        self._selected = self._get_unique_index(index)
        self._parent.list_changed(self._module, 'select', self.selected)

    def _get_unique_index(self, index):
        try:
            return self.index(self[index])
        except:
            return None

    def select(self, value):
        """ selects the element with value, or None if it does not exist """
        try:
            self.selected = self.index(value)
        except IndexError:
            self.selected = None

    # other convenience functions that are based on above axioms
    def append(self, new=None):
        self.insert(self.__len__(), new)

    def extend(self, iterable=[]):
        for i in iterable:
            self.append(i)

    def pop(self, index=-1):
        # get attributes
        item = self[index]
        self.__delitem__(index)
        return item

    def remove(self, value):
        self.__delitem__(self.index(value))

    def clear(self):
        while len(self) > 0:
            self.__delitem__()

    def copy(self):
        return list(self)

    def sort(self, key=None, reverse=False):
        sorted = self.copy().sort(key=key, reverse=reverse)
        for i, v in enumerate(sorted):
            self[i] = v

    def reverse(self):
        reversed = self.copy()
        reversed.reverse()
        for i, v in enumerate(reversed):
            self[i] = v


class BasePropertyListProperty(BaseProperty):
    """
    An arbitrary length list of items that behave like BaseProperty.

    A derived class FloatPropertyListProperty(BasePropertyListProperty)
    will behave as a list of FloatProperty-like items.
    """
    default = []
    _widget_class = BasePropertyListPropertyWidget

    def __init__(self, *args, **kwargs):
        """
        default is the default list
        default_element: default new element
        """
        self.default_element = kwargs.pop('default_element', None)
        super(BasePropertyListProperty, self).__init__(*args, **kwargs)

    @property
    def element_cls(self):
        """ the class of the elements of the list """
        return super(BasePropertyListProperty, self)

    def validate_and_normalize(self, obj, value):
        """
        Converts the value into a list.
        """
        return list(value)

    def validate_and_normalize_element(self, obj, val):
        return self.element_cls.validate_and_normalize(obj, val)

    def get_value(self, obj):
        if not hasattr(obj, '_' + self.name):
            # make a new AttributeList, pass to it the instance of obj
            value = AttributeList(self, obj, self.default)
            setattr(obj, '_' + self.name, value)
        return getattr(obj, '_' + self.name)

    def set_value(self, obj, val):
        current = self.get_value(obj)
        try:  # block repetitive calls to setup
            call_setup, self.call_setup = self.call_setup, False
            # replace the already existing list elements and append new ones
            for i, v in enumerate(val):
                try:
                    current[i] = v
                except IndexError:
                    current.append(v)
            # remove the trailing items
            while len(current) > len(val):
                current.pop()
        finally:
            self.call_setup = call_setup

    def list_changed(self, module, operation, index, value=None):
        if operation == 'select':
            # only launch signal in this case, do not call setup
            # value can be None in this case, as it is not used
            if value is None:
                value = self.get_value(module)
            self.launch_signal(module, value, appendix=[operation, index, value])
        else:
            # launches signal and calls setup()
            self.value_updated(module, appendix=[operation, index, value])


class FloatAttributeListProperty(BasePropertyListProperty, FloatProperty):
    pass


class ComplexAttributeListProperty(BasePropertyListProperty, ComplexProperty):
    pass


class PWMRegister(FloatRegister):
    """
    FloatRegister that defines the PWM voltage similar to setting a float.
    """
    # See FPGA code for a more detailed description on how the PWM works
    def __init__(self, address, CFG_BITS=24, PWM_BITS=8, **kwargs):
        self.CFG_BITS = int(CFG_BITS)
        self.PWM_BITS = int(PWM_BITS)
        FloatRegister.__init__(self, address=address, bits=14, norm=1, **kwargs)
        self.min = 0   # voltage of pwm outputs ranges from 0 to 1.8 volts
        self.max = 1.8
        self.increment = (self.max-self.min)/2**(self.bits-1)  # actual resolution is 14 bits (roughly 0.1 mV incr.)

    def to_python(self, obj, value):
        value = int(value)
        pwm = float(value >> (self.CFG_BITS - self.PWM_BITS) & (2 ** self.PWM_BITS - 1))
        mod = value & (2 ** (self.CFG_BITS - self.PWM_BITS) - 1)
        postcomma = float(bin(mod).count('1')) / (self.CFG_BITS - self.PWM_BITS)
        voltage = 1.8 * (pwm + postcomma) / 2 ** self.PWM_BITS
        if voltage > 1.8:
            logger.error("Readout value from PWM (%h) yields wrong voltage %f",
                         value, voltage)
        return voltage

    def from_python(self, obj, value):
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


class StringProperty(BaseProperty):
    """
    An attribute for string (there is no corresponding StringRegister).
    """
    _widget_class = StringAttributeWidget
    default = ""

    def validate_and_normalize(self, obj, value):
        """
        Convert argument to string
        """
        return str(value)


class TextProperty(StringProperty):
    """
    Same as StringProperty, but the gui displays it as multi-line text.
    """
    _widget_class = TextAttributeWidget


class SelectProperty(BaseProperty):
    """
    An attribute for a multiple choice value.

    The options can be specified at the object creation as a list or an
    (ordered) dict, or as a callable with one argument (which is None or the
    module that contains this attribute, depending on when the call is made).
    Options can be specified at attribute creation, but it can also be updated
    later on a per-module basis using change_options(new_options). If
    options are callable, they are evaluated every time they are needed.
    """
    _widget_class = SelectAttributeWidget
    default = None

    def __init__(self,
                 options=[],
                 **kwargs):
        self.default_options = options
        BaseProperty.__init__(self, **kwargs)

    @property
    def __doc__(self):
        # Append available options to docstring
        return self.doc + "\r\nOptions:\r\n" + str(list(self.options(None)))

    @__doc__.setter
    def __doc__(self, value):
        self.doc = value

    def get_default(self, instance):
        """ returns the default value. default is pre-defined value
        if that is not a valid option. Otherwise the first valid option
        is taken, and if that is not possible (no options), None is taken. """
        default = self.default  # internal default
        # at startup, we cannot access the instance, so we must continue without it
        if instance is not None:
            # make sure default is stored in the instance, such that it can be easily modified
            if not hasattr(instance, '_' + self.name + '_' + 'default'):
                setattr(instance, '_' + self.name + '_' + 'default', default)
            default = getattr(instance, '_' + self.name + '_' + 'default')
        # make sure default is a valid option
        options = self.options(instance)
        if not default in options:
            # if not valid, default default is the first options
            default = list(options)[0]
        # if no options are availbale, fall back to None
        if default is None:
            logger.warning("Default of SelectProperty %s "
                           "is None. ", self.name)
        return default

    def options(self, instance=None):
        """
        options are evaluated at run time. options may be callable with instance as optional argument.
        """
        options = self.default_options
        # at startup, we cannot access the instance, so we must continue without it
        if instance is not None:
            # make sure default is stored in the instance, such that it can be easily modified
            if not hasattr(instance, '_' + self.name + '_' + 'options'):
                setattr(instance, '_' + self.name + '_' + 'options', options)
            options = getattr(instance, '_' + self.name + '_' + 'options')
        if callable(options):
            try:
                options = options(instance)
            except (TypeError, AttributeError):
                try:
                    options = options()
                except (TypeError, AttributeError):
                    options = OrderedDict()
        if not hasattr(options, "keys"):
            options = OrderedDict([(v, v) for v in options])
        if len(options) == 0:
            logger.debug("SelectProperty %s of module %s has no options!", self.name, instance)
            options = {None: None}
        # check whether options keys have changed w.r.t. last time and emit a signal in that
        # case. Also create a list of valid options in the parent module called
        # self.name+'_options'.
        if instance is not None:
            try:
                lastoptions = getattr(instance, '_' + self.name + '_lastoptions')
            except AttributeError:
                lastoptions = None
            if options != lastoptions:
                setattr(instance, '_' + self.name + '_lastoptions', options)
                # save the keys for the user convenience
                setattr(instance, self.name + '_options', list(options.keys()))
                instance._signal_launcher.change_options.emit(self.name,
                                                              list(options))
        # return the actual options
        return options

    def change_options(self, instance, new_options):
        """
        Changes the possible options acceptable by the Attribute:

        - New validation takes effect immediately (otherwise a script
          involving 1. changing the options / 2. selecting one of the
          new options could not be executed at once)
        - Update of the ComboxBox is performed behind a signal-slot
          mechanism to be thread-safe
        - If the current value is not in the new_options, then value
          is changed to some available option
        """
        setattr(instance, '_' + self.name + '_' + 'options', new_options)
        # refresh default options in case options(None) is called (no instance in argument)
        # this also triggers the signal emission in the method options()
        self.default_options = self.options(instance)

    def validate_and_normalize(self, obj, value):
        options = self.options(obj)
        if not (value in options):
            msg = "Value '%s' is not an option for SelectAttribute %s of " \
                  "module %s with options %s" \
                  % (value, self.name, obj.name, options)
            if self.ignore_errors:
                value = self.get_default(obj)
                logger.warning(msg + ". Picking an arbitrary value %s instead."
                               % str(value))
            else:
                logger.error(msg)
                raise ValueError(msg)
        return value

    def get_value(self, obj):
        if not hasattr(obj, '_' + self.name):
            setattr(obj, '_' + self.name, self.get_default(obj))
        value = getattr(obj, '_' + self.name)
        # make sure the value is a valid option
        value = self.validate_and_normalize(obj, value)
        return value

    def set_value(self, obj, value):
        BaseProperty.set_value(self, obj, value)


class SelectRegister(BaseRegister, SelectProperty):
    """
    Implements a selection register, such as for multiplexers.

    The options must be a dict, where the keys indicate the available
    options and the values indicate the corresponding fpga register values.
    If different keys point to the same register value, the keys are
    nevertheless distinguished (allows implementing aliases that may vary
    over time if options is a callable object). """
    def __init__(self, address,
                 bitmask=None,
                 options={},
                 **kwargs):
        BaseRegister.__init__(self, address=address, bitmask=bitmask)
        SelectProperty.__init__(self, options=options, **kwargs)

    def get_default(self, obj):
        default = SelectProperty.get_default(self, obj)
        if default is None and obj is not None:
            # retrieve default value from FPGA if nothing more reasonable is available
            value = BaseRegister.get_value(self, obj)
            for k, v in self.options(obj).items():
                if v == value:
                    default = k
                    break
        return default

    def get_value(self, obj):
        value = SelectProperty.get_value(self, obj)
        # make sure the register value corresponds to the selected option
        expected_value = self.options(obj)[value]
        raw_value = BaseRegister.get_value(self, obj)
        if raw_value != expected_value:
            obj._logger.warning("Register %s of module %s has value %s, "
                                "which does not correspond to selected "
                                "option %s. Setting to '%s'. ",
                                self.name, obj.name,
                                raw_value, expected_value, value)
            BaseRegister.set_value(self, obj, expected_value)
        return value

    def set_value(self, obj, value):
        SelectProperty.set_value(self, obj, value)
        BaseRegister.set_value(self, obj, self.options(obj)[value])

    def to_python(self, obj, value):
        return int(value)

    def from_python(self, obj, value):
        return int(value)


class ProxyProperty(BaseProperty):
    """
    An attribute that is a proxy to another attribute.

    This attribute essentially behaves like the one that is reached by
    instance.path_to_target, always staying in synch.
    """
    def __init__(self,
                 path_to_target,
                 **kwargs):
        self.path_to_target = path_to_target
        lastpart = path_to_target.split('.')[-1]
        self.target_attribute = lastpart
        self.path_to_target_module = path_to_target[:-(len(lastpart)+1)] #+1 for the dot
        self.path_to_target_descriptor = self.path_to_target_module \
                                         + '.__class__.' \
                                         + lastpart
        BaseProperty.__init__(self, **kwargs)

    def _target_to_proxy(self, obj, target):
        """ override this function to implement conversion between target
        and proxy"""
        return target

    def _proxy_to_target(self, obj, proxy):
        """ override this function to implement conversion between target
        and proxy"""
        return proxy

    def __get__(self, instance, owner):
        if instance is None:
            return self
        self.instance = instance
        # dangerous, but works because we only call __getattribute__
        # immediately after __set__ or __get__
        self.connect_signals(instance)
        return self._target_to_proxy(instance,
                                     recursive_getattr(instance,
                                                       self.path_to_target))

    def __set__(self, obj, value):
        self.instance = obj
        self.connect_signals(obj)
        recursive_setattr(obj,
                          self.path_to_target,
                          self._proxy_to_target(obj, value))

    def __getattribute__(self, item):
        try:
            return BaseProperty.__getattribute__(self, item)
        except AttributeError:
            attr = recursive_getattr(self.instance,
                                     self.path_to_target_descriptor + '.' + item)
            #if callable(attr):
            #    return partial(attr, self.instance)
            #else:
            return attr

    # special functions for SelectProperties, which transform the argument
    # 'obj' from the hosting module to the target module to avoid redundant
    # saving of options
    def options(self, obj):
        if obj is None:
            obj = self.instance
        module = recursive_getattr(obj, self.path_to_target_module)
        options = recursive_getattr(obj, self.path_to_target_descriptor +
                                    '.options')(module)
        return OrderedDict([(self._target_to_proxy(obj, k), v)
                            for k, v in options.items()])

    def change_options(self, obj, new_options):
        if obj is None:
            obj = self.instance
        module = recursive_getattr(obj, self.path_to_target_module)
        return recursive_getattr(obj, self.path_to_target_descriptor + '.change_options')(module, new_options)

    def __repr__(self):
        try:
            targetdescr = " (target: " \
                          + recursive_getattr(self.instance,
                                              self.path_to_target_descriptor).__repr__() \
                          + ")"
        except:
            targetdescr = ""
        return super(ProxyProperty, self).__repr__() + targetdescr

    def connect_signals(self, instance):
        """ function that takes care of forwarding signals from target to
        signal_launcher of proxy module """
        if hasattr(instance, '_' + self.name + '_connected'):
            return  # skip if connection has already been set up
        else:
            module = recursive_getattr(instance, self.path_to_target_module)

            def forward_update_attribute_by_name(name, value):
                """ forward the signal, but change attribute name """
                if name == self.target_attribute:
                    instance._signal_launcher.update_attribute_by_name.emit(
                        self.name, [self._target_to_proxy(instance,
                                                          value[0])])
                    if self.call_setup:
                        instance.setup()
            module._signal_launcher.update_attribute_by_name.connect(
                forward_update_attribute_by_name)

            def forward_change_options(name, new_options):
                """ forward the signal, but change attribute name """
                if name == self.target_attribute:
                    # update local list of options
                    setattr(instance, self.name + '_options', new_options)
                    # forward the signal
                    instance._signal_launcher.change_options.emit(
                        self.name, new_options)
            module._signal_launcher.change_options.connect(
                forward_change_options)

            # remember that we are now connected
            setattr(instance, '_' + self.name + '_connected', True)

    def _create_widget(self, module, widget_name=None, **kwargs):
        target_module = recursive_getattr(module, self.path_to_target_module)
        target_descriptor = recursive_getattr(module, self.path_to_target_descriptor)
        if widget_name is None:
            widget_name = self.name
        #return recursive_getattr(module,
        #                         self.path_to_target_descriptor +
        #                         '._create_widget')(target_module,
        #                                            widget_name=widget_name,
        #                                            **kwargs)
        self._widget_class = recursive_getattr(module,
                                 self.path_to_target_descriptor +
                                 '._widget_class')
        try:  # try to make a widget for proxy
            return recursive_getattr(module,
                                 self.path_to_target_descriptor +
                                 '.__class__._create_widget')(self, module,
                                                    #widget_name=widget_name,
                                                    **kwargs)
        except:  # make a renamed widget for target
            return recursive_getattr(module,
                                     self.path_to_target_descriptor +
                                     '.__class__._create_widget')(target_descriptor, target_module,
                                                                  widget_name=widget_name,
                                                                  **kwargs)


class ModuleAttribute(BaseProperty):
    """
    This is the base class for handling submodules of a module.

    The actual implementation is found in module_attributes.ModuleProperty.
    This object is only used inside the Module class
    """

class CurveSelectProperty(SelectProperty):
    """
    An attribute to select a curve from all available ones.

    The curve object is loaded to instance._name_object, where 'name' stands
    for the name of this attribute. The property can be set by either passing
    a CurveDB object, or a curve id.
    """
    def __init__(self,
                 no_curve_first=False,
                 show_childs=False,
                 **kwargs):
        self.no_curve_first = no_curve_first
        self.show_childs = show_childs
        SelectProperty.__init__(self, options=self._default_options, **kwargs)

    def _default_options(self):
        if self.no_curve_first:
            return [-1] + [curve.pk for curve in CurveDB.all()]
        else:
            return [curve.pk for curve in CurveDB.all()] + [-1]
        #return OrderedDict([(k, k) for k in (CurveDB.all()) + [-1]])

    def validate_and_normalize(self, obj, value):
        # returns none or a valid curve corresponding to the given curve or id
        if isinstance(value, CurveDB):
            value = value.pk
        try:
            pk = int(value)
        except:
            pk = -1
        return pk

    def set_value(self, obj, pk):
        SelectProperty.set_value(self, obj, pk)
        try:
            curve = CurveDB.get(pk)
        except:
            curve = None
        setattr(obj, '_' + self.name + '_object', curve)


class CurveProperty(CurveSelectProperty):
    """ property for a curve whose widget plots the corresponding curve.

    Unfortunately, the widget does not allow to select the curve,
    i.e. selection must be implemented with another CurveSelectProperty.
    """
    _widget_class = CurveAttributeWidget


class CurveSelectListProperty(CurveSelectProperty):
    """ same as above, but widget is a list to select from """
    _widget_class = CurveSelectAttributeWidget


class Plotter(BaseProperty):
    """ property for plotting in the GUI window.

    passing a value, list of values, or a dict of color-value pairs
    results in plotting the values as a function of time in the GUI
    """
    _widget_class = PlotAttributeWidget
    def __init__(self, legend="value"):
        self.legend = legend
        super(Plotter, self).__init__()


class DataProperty(BaseProperty):
    """
    Property for a dataset (real or complex), that can be plotted.
    """
    _widget_class = DataAttributeWidget
