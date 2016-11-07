"""
The most important Attributes are Registers (see attributes.py for a presentation of Attributes in general).
Register are parameters that are stored directly on the RedPitaya.

The Attribute descriptor needs to possess a client to communicate with the redpitaya, and an address to find the data
on the redpitaya:
  - the address is part of the Register.
  - the client is part of the Module instance.
This way, several redpitayas can be interfaced, as long as they have the same internal architectures.
"""

import numpy as np
import sys
import logging

logger = logging.getLogger(name=__name__)

# way to represent the smallest positive value
# needed to set floats to minimum count above zero
epsilon = sys.float_info.epsilon

from pyrpl.attributes import BaseAttribute, IntAttribute, PhaseAttribute, FloatAttribute, StringAttribute, BoolAttribute, \
                        SelectAttribute
from pyrpl.bijection import Bijection
from pyrpl.attribute_widgets import BoolRegisterWidget, FloatRegisterWidget, FilterRegisterWidget, IntRegisterWidget, \
    PhaseRegisterWidget, FrequencyRegisterWidget, SelectRegisterWidget, StringRegisterWidget


# docstring does not work yet, see:
# http://stackoverflow.com/questions/37255109/python-docstring-for-descriptors
# for now there is a workaround: call Module.help(register)
class BaseRegister(object):
    """Registers implement the necessary read/write logic for storing an attribute on the redpitaya.
    Interface for basic register of type int"""
    def __init__(self, address, doc="", bitmask=None):
        self.address = address
        self.__doc__ = doc
        self.bitmask = bitmask

    def get_value(self, obj, objtype=None):
        if obj is None:
            return self # allows to access the descriptor by calling class.Register
            # see http://nbviewer.jupyter.org/urls/gist.github.com/ChrisBeaumont/5758381/raw/descriptor_writeup.ipynb
        self.parent = obj  #store obj in memory
        if self.bitmask is None:
            return self.to_python(obj._read(self.address), obj)
        else:
            return self.to_python(obj._read(self.address) & self.bitmask, obj)
    
    def set_value(self, obj, val):
        # self.parent = obj  #store obj in memory<-- very bad practice: there is one Register for the class
        # and potentially many obj instances (think of having 2 redpitayas in the same python session), then
        # _read should use different clients depending on which obj is calling...)

        if self.bitmask is None:
            obj._write(self.address, self.from_python(val, obj))
        else:
            act = obj._read(self.address)
            new = act&(~self.bitmask)|(int(self.from_python(val, obj))&self.bitmask)
            obj._write(self.address, new)

    def _writes(self, obj, addr, v):
        return obj._writes(addr, v)
    
    def _reads(self, obj, addr, l):
        return obj._reads(addr, l)

    def _write(self, obj, addr, v):
        return obj._write(addr, v)
    
    def _read(self, obj, addr):
        return obj._read(addr)


class IntRegister(BaseRegister, IntAttribute):
    def to_python(self, value, obj):
        return int(value)

    def from_python(self, value, obj):
        return int(value)


class LongRegister(BaseRegister, IntAttribute):
    """Interface for register of python type int/long with arbitrary length 'bits' (effectively unsigned)"""
    def __init__(self, address, bits=64, **kwargs):
        super(LongRegister,self).__init__(address=address, **kwargs)
        IntAttribute.__init__(self, increment=1)
        self.bits = bits
        self.size = int(np.ceil(float(self.bits)/32))

    def get_value(self, obj, objtype=None):
        if obj is None:
            return self
        values = obj._reads(self.address, self.size)
        value = int(0)
        for i in range(self.size):
            value += int(values[i]) << (32*i)
        if self.bitmask is None:
            return self.to_python(value)
        else:
            return (self.to_python(value) & self.bitmask)
    
    def set_value(self, obj, val):
        val = self.from_python(val)
        values = np.zeros(self.size, dtype=np.uint32)
        if self.bitmask is None:
            for i in range(self.size):
                values[i] = (val >> (32*i)) & 0xFFFFFFFF
        else:
            act = obj._reads(self.address, self.size)
            for i in range(self.size):
                localbitmask = (self.bitmask >> 32*i) & 0xFFFFFFFF
                values[i] = ((val >> (32*i)) & localbitmask) | \
                            (int(act[i]) & (~localbitmask))
        obj._writes(self.address, values)
            

class BoolRegister(BaseRegister, BoolAttribute):
    """Inteface for boolean values, 1: True, 0: False.
    invert=True inverts the mapping"""
    def __init__(self, address, bit=0, invert=False, **kwargs):
        super(BoolRegister, self).__init__(address=address, **kwargs)
        BoolAttribute.__init__(self)
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
            v = self._read(self.address) | (1 << self.bit)
        else:
            v = self._read(self.direction_address) & (~(1 << self.bit))
        obj._write(self.direction_address, v)
    
    def get_value(self, obj, objtype=None):
        if obj is None:
            return self
        self.parent = obj  # store obj in memory
        self.direction(obj)
        return super(IORegister, self).__get__(obj=obj, objtype=objtype)

    def set_value(self, obj, val):
        self.parent = obj  # store obj in memory
        self.direction(obj)
        return super(IORegister, self).__set__(obj=obj, val=val)


class SelectRegister(BaseRegister, SelectAttribute):
    """Implements a selection, such as for multiplexers"""
    def __init__(self, address, 
                 options={},
                 doc="",
                 **kwargs):
        super(SelectRegister, self).__init__(
                                    address=address,
                                    doc=doc+"\r\nOptions:\r\n"+str(options),
                                    **kwargs)
        SelectAttribute.__init__(self, options)
        self._options = Bijection(options)
        
    def to_python(self, value, obj):
        return self._options.inverse[value]
    
    def from_python(self, value, obj):
        return self._options[value]


class FloatRegister(BaseRegister, FloatAttribute):
    """Implements a fixed point register, seen like a (signed) float from python"""
    def __init__(self, address, 
                 bits=14, #total number of bits to represent on fpga
                 norm=1,  #fpga value corresponding to 1 in python
                 signed=True, #otherwise unsigned
                 invert=False, # if False: FPGA=norm*python, if True: FPGA=norm/python
                 **kwargs):
        super(FloatRegister, self).__init__(address=address, **kwargs)
        #if invert:
        #    raise NotImplementedError("increment not implemented for inverted registers")#return self.norm/2**self.bits
        #else:
        increment = 1./norm
        FloatAttribute.__init__(self, increment=increment, min=-norm, max=norm)
        self.bits = bits
        self.norm = float(norm)
        self.invert = invert
        self.signed = signed

    def to_python(self, value, obj):
        # 2's complement
        if self.signed:
            if value >= 2**(self.bits-1):
                value -= 2**self.bits
        # normalization
        if self.invert:
            if value == 0:
                return float(0)
            else:
                return 1.0/float(value)/self.norm
        else:
            return float(value)/self.norm
    
    def from_python(self, value, obj):
        # round and normalize
        if self.invert:
            if value == 0:
                v = 0
            else:
                v = int(round(1.0/float(value)*self.norm))
        else:
            v = int(round(float(value)*self.norm)) 
        # make sure small float values are not rounded to zero
        if ( v==0 and value > 0):
            v = 1
        elif (v == 0 and value < 0):
            v = -1
        if self.signed:
            # saturation
            if (v >= 2**(self.bits-1)):
                v = 2**(self.bits-1)-1
            elif (v < -2**(self.bits-1)):
                v = -2**(self.bits-1)
            # 2's complement
            if (v < 0):
                v += 2**self.bits
        else:
            v = abs(v) #take absolute value
            #unsigned saturation
            if v >= 2**self.bits:
                v = 2**self.bits-1
        return v


class PhaseRegister(FloatRegister, PhaseAttribute):
    """Registers that contain a phase as a float in units of degrees."""
    """Registers that contain a frequency as a float in units of Hz"""
    def __init__(self, address, bits=32, **kwargs):
        super(PhaseRegister,self).__init__(address=address, bits=bits, **kwargs)
        PhaseAttribute.__init__(self, increment=360./2**bits)

    def from_python(self, value, obj):
        # make sure small float values are not rounded to zero
        if self.invert:
            value = float(value)*(-1)
        return int(round((float(value)%360)/360*2**self.bits)% 2**self.bits)

    def to_python(self, value, obj):
        phase = float(value)/2**self.bits*360
        if self.invert:
            phase *= -1
        return phase%360.0


class FrequencyRegister(FloatRegister, FloatAttribute):
    """Registers that contain a frequency as a float in units of Hz"""
    # attention: no bitmask can be defined for frequencyregisters
    CLOCK_FREQUENCY = 125e6

    def __init__(self, address, 
             bits=32, #total number of bits to represent on fpga
             **kwargs):
        super(FrequencyRegister,self).__init__(address=address, bits=bits, **kwargs)
        if self.invert:
            raise NotImplementedError("Increment not implemented for inverted registers")
        increment = self.CLOCK_FREQUENCY/2**self.bits #*obj._frequency_correction
        FloatAttribute.__init__(self, increment=increment, min=0, max=self.CLOCK_FREQUENCY*0.5)

    def get_value(self, obj, objtype=None):
        if obj is None:
            return self
        return self.to_python(obj._read(self.address), obj)

    def set_value(self, obj, val):
        obj._write(self.address,self.from_python(val, obj))

    def from_python(self, value, obj):
        # make sure small float values are not rounded to zero
        value = abs(float(value)/obj._frequency_correction)
        if (value == epsilon):
            value = 1
        else:
            # round and normalize
            value = int(round(value/self.CLOCK_FREQUENCY*2**self.bits)) # Seems correct (should not be 2**bits -1): 125 MHz
                                                         # out of reach because 2**bits is out of reach
        return value
    
    def to_python(self, value, obj):
        return 125e6/2**self.bits*float(value)*obj._frequency_correction # Seems correct (should not be 2**bits -1): 125 MHz
                                                                    # out of reach because 2**bits is out of reach


class FilterRegister(BaseRegister, BaseAttribute):
    """
    Interface for up to 4 low-/highpass filters in series (filter_block.v)
    """
    widget_class = FilterRegisterWidget

    def __init__(self, address,  filterstages, shiftbits, minbw, **kwargs):
        super(FilterRegister,self).__init__(address=address, **kwargs)
        self.filterstages = filterstages
        self.shiftbits = shiftbits
        self.minbw = minbw

    def _FILTERSTAGES(self, obj):
        return obj._read(self.filterstages)

    def _SHIFTBITS(self, obj):
        return obj._read(self.shiftbits)

    def _MINBW(self, obj):
        return obj._read(self.minbw)

    def _ALPHABITS(self, obj):
        return int(np.ceil(np.log2(125000000 / self._MINBW(obj))))

    def valid_frequencies(self, obj):
        """ returns a list of all valid filter cutoff frequencies"""
        valid_bits = range(0, 2**self._SHIFTBITS(obj))
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
            shift = v & (2**shiftbits - 1)
            filter_on = ((v >> 7) == 0x1)
            highpass = (((v >> 6) & 0x1) == 0x1)
            if filter_on:
                bandwidth = float(2**shift) / \
                    (2**alphabits) * 125e6 / 2 / np.pi
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
                            (2**alphabits) * 2 * np.pi / 125e6)))
                if shift < 0:
                    shift = 0
                elif shift > (2**shiftbits - 1):
                    shift = (2**shiftbits - 1)
                shift += 2**7  # turn this filter stage on
                if bandwidth < 0:
                    shift += 2**6  # turn this filter into a highpass
                filter_shifts += (shift) * 2**(8 * i)
        return filter_shifts


#    def create_widget(self, name, parent):
#        """
#        returns a widget to control the register
#        """

#        self.widget = FilterRegisterWidget(name, parent)
#        return self.widget


class PWMRegister(BaseRegister, BaseAttribute):
    # FloatRegister that defines the PWM voltage similar to setting a float
    # see FPGA code for more detailed description on how the PWM works
    def __init__(self, address, CFG_BITS=24, PWM_BITS=8, **kwargs):
        super(PWMRegister,self).__init__(address=address, **kwargs)
        self.CFG_BITS = int(CFG_BITS)
        self.PWM_BITS = int(PWM_BITS)

    def to_python(self, value, obj):
        value = int(value)
        pwm = float(value>>(self.CFG_BITS-self.PWM_BITS)&(2**self.PWM_BITS-1))
        mod = value & (2**(self.CFG_BITS-self.PWM_BITS)-1)
        postcomma = float(bin(mod).count('1'))/(self.CFG_BITS-self.PWM_BITS)
        voltage = 1.8 * (pwm + postcomma) / 2**self.PWM_BITS
        if voltage > 1.8:
            logger.error("Readout value from PWM (%h) yields wrong voltage %f",
                         value, voltage)
        return voltage
           
    def from_python(self, value, obj):
        # here we don't bother to minimize the PWM noise
        # room for improvement is in the low -> towrite conversion
        value = 0 if (value < 0) else float(value)/1.8*(2**self.PWM_BITS)
        high = np.floor(value)
        if (high >= 2**self.PWM_BITS):
            high = 2**self.PWM_BITS-1
        low = int(np.round((value-high)*(self.CFG_BITS-self.PWM_BITS)))
        towrite = int(high)<<(self.CFG_BITS-self.PWM_BITS)
        towrite += ((1<<low)-1)&((1<<self.CFG_BITS)-1)
        return towrite


class BaseProperty(object):
    """
    A Property is a special type of attribute that is not mapping a fpga value, but rather an attribute _attr_name
    of the module. This is used mainly in SoftwareModules
    """

    def get_value(self, obj, obj_type):
        if obj is None:
            return self
        if not hasattr(obj, '_' + self.name):
            setattr(obj, '_' + self.name, self.default)
        return getattr(obj, '_' + self.name)

    def set_value(self, obj, val):
        setattr(obj, '_' + self.name, val)
        return val # maybe better with getattr... but more expensive


class SelectProperty(SelectAttribute, BaseProperty): pass


class StringProperty(StringAttribute, BaseProperty):
    default = ""


class PhaseProperty(PhaseAttribute, BaseProperty):
    default = 0


class FloatProperty(FloatAttribute, BaseProperty):
    default = 0.


class LongProperty(IntAttribute, BaseProperty):
    default = 0


class BoolProperty(BoolAttribute, BaseProperty):
    default = False