import numpy as np
import sys
import logging
logger = logging.getLogger(name=__name__)

#way to represent the smallest positive value
#needed to set floats to minimum count above zero
epsilon = sys.float_info.epsilon

from .bijection import Bijection

#docstring does not work yet, see: 
#http://stackoverflow.com/questions/37255109/python-docstring-for-descriptors
#for now there is a workaround: call Module.help(register)
class Register(object):
    """Interface for basic register of type int"""
    def __init__(self, address, doc="", bitmask=None):
        self.address = address
        self.__doc__ = doc
        self.bitmask = bitmask
    
    def to_python(self, value):
        return int(value)
    
    def from_python(self, value):
        return int(value)
    
    def __get__(self, obj, objtype=None):
        self.parent = obj #store obj in memory
        if self.bitmask is None:
            return self.to_python(obj._read(self.address))
        else:
            return self.to_python(obj._read(self.address)&self.bitmask)
    
    def __set__(self, obj, val):
        self.parent = obj #store obj in memory
        if self.bitmask is None:
            obj._write(self.address,self.from_python(val))
        else:
            act = obj._read(self.address)
            new = act&(~self.bitmask)|(int(self.from_python(val))&self.bitmask)
            obj._write(self.address,new)
    
    def _writes(self, addr, v):
        return self.parent._writes(addr,v)
    
    def _reads(self, addr, l):
        return self.parent._reads(addr,l)

    def _write(self, addr, v):
        return self.parent._write(addr,v)
    
    def _read(self, addr):
        return self.parent._read(addr)
    
    
class LongRegister(Register):
    """Interface for register of python type int/long with arbitrary length 'bits' (effectively unsigned)"""
    def __init__(self, address, bits=64, **kwargs):
        super(LongRegister,self).__init__(address=address, **kwargs)
        self.bits = bits
        self.size = int((32+bits-bits%32)/32)

    def __get__(self, obj, objtype=None):
        values = obj._reads(self.address, self.size)
        value = long(0)
        for i in range(self.size):
            value += int(values[i])<<(32*i)
        if self.bitmask is None:
            return self.to_python(value)
        else:
            return (self.to_python(value)&self.bitmask)
    
    def __set__(self, obj, val):
        val = self.from_python(val)
        values = np.zeros(self.size,dtype=np.uint32)
        if self.bitmask is None:
            for i in range(self.size):
                values[i] = (val>>(32*i))&0xFFFFFFFF
        else:
            act = obj._reads(self.address, self.size)
            for i in range(self.size):
                localbitmask = (self.bitmask>>32*i)&0xFFFFFFFF
                values[i] = ((val>>(32*i))&localbitmask)|(int(act[i])&(~localbitmask))
        obj._writes(self.address,val)
            
class BoolRegister(Register):
    """Inteface for boolean values, 1: True, 0: False. invert=True inverts the mapping"""
    def __init__(self, address, bit=0, invert=False, **kwargs):
        super(BoolRegister,self).__init__(address=address, **kwargs)
        self.bit = bit
        assert type(invert)==bool
        self.invert = invert
        
    def to_python(self, value):
        value = bool((value>>self.bit)&1)
        if self.invert:
            value = not value
        return value
    
    def __set__(self, obj, val):
        if self.invert:
            val = not val
        if val:
            v = obj._read(self.address)|(1<<self.bit)
        else:
            v = obj._read(self.address)&(~(1<<self.bit))
        obj._write(self.address,v)

class IORegister(BoolRegister):
    """Interface for digital outputs
    
    if argument outputmode is True, output mode is set, else input mode"""
    def __init__(self, read_address, write_address, direction_address, 
                 outputmode=True, bit=0, **kwargs):
        if outputmode:
            address = write_address
        else:
            address = read_address
        super(IORegister,self).__init__(address=address, bit=bit, **kwargs)
        self.direction_address = direction_address
        #self.direction = BoolRegister(direction_address,bit=bit, **kwargs)
        self.outputmode = outputmode #set output direction
    
    def direction(self, v=None):
        if v is None:
            v = self.outputmode
        if v:
            v = self._read(self.address)|(1<<self.bit)
        else:
            v = self._read(self.direction_address)&(~(1<<self.bit))
        self._write(self.direction_address,v)
    
    def to_python(self, value):
        self.direction()
        return value

    def fom_python(self, value):
        self.direction()
        return value
    
class SelectRegister(Register):
    """Implements a selection, such as for multiplexers"""
    def __init__(self, address, 
                 options={}, 
                 doc="",
                 **kwargs):
        super(SelectRegister,self).__init__(address=address, doc=doc+"\r\nOptions:\r\n"+str(options), **kwargs)
        self.options = Bijection(options)
        
    def to_python(self, value):
        return self.options.inverse[value]
    
    def from_python(self, value):
        return self.options[value]


class FloatRegister(Register):
    """Implements a fixed point register, seen like a (signed) float from python"""
    def __init__(self, address, 
                 bits=14, #total number of bits to represent on fpga
                 norm=1,  #fpga value corresponding to 1 in python
                 signed=True, #otherwise unsigned
                 invert=False, # if False: FPGA=norm*python, if True: FPGA=norm/python
                 **kwargs):
        super(FloatRegister,self).__init__(address=address, **kwargs)
        self.bits = bits
        self.norm = float(norm)
        self.invert = invert
        self.signed = signed
        
    def to_python(self, value):
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
    
    def from_python(self, value):
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

class PhaseRegister(FloatRegister):
    """Registers that contain a phase as a float in units of degrees."""
    """Registers that contain a frequency as a float in units of Hz"""
    def __init__(self, address, bits=32, **kwargs):
        super(PhaseRegister,self).__init__(address=address, bits=bits, **kwargs)
        
    def from_python(self, value):
        # make sure small float values are not rounded to zero
        return int(round((float(value)%360)/360*2**self.bits)) 
        
    def to_python(self, value):
        return float(value)/2**self.bits*360
    
class FrequencyRegister(FloatRegister):
    """Registers that contain a frequency as a float in units of Hz"""
    # attention: no bitmask can be defined for frequencyregisters
    def __init__(self, address, 
             bits=32, #total number of bits to represent on fpga
             **kwargs):
        super(FrequencyRegister,self).__init__(address=address, bits=bits, **kwargs)
        
    def __get__(self, obj, objtype=None):
        return self.to_python(obj._read(self.address), obj._frequency_correction)

    def __set__(self, obj, val):
        obj._write(self.address,self.from_python(val, obj._frequency_correction))

    def from_python(self, value, frequency_correction):
        # make sure small float values are not rounded to zero
        value = abs(float(value)/frequency_correction)
        if (value == epsilon):
            value = 1
        else:
            # round and normalize
            value = int(round(value/125e6*2**self.bits)) 
        return value
    
    def to_python(self, value, frequency_correction):
        return 125e6/2**self.bits*float(value)*frequency_correction
    

class FilterRegister(Register):
    """Interface for up to 4 low-/highpass filters in series (filter_block.v)"""
    def __init__(self, address,  filterstages, shiftbits, minbw, **kwargs):
        super(FilterRegister,self).__init__(address=address, **kwargs)
        self.filterstages = filterstages
        self.shiftbits = shiftbits
        self.minbw = minbw
    
    @property
    def _FILTERSTAGES(self):
        return self._read(self.filterstages)
    
    @property
    def _SHIFTBITS(self):
        return self._read(self.shiftbits)
    
    @property
    def _MINBW(self):
        return self._read(self.minbw)
        
    @property
    def _ALPHABITS(self):
        return int(np.ceil(np.log2(125000000 / self._MINBW)))

    def to_python(self, value):
        """returns a list of bandwidths for the low-pass filter cascade before the module
           negative bandwidth stands for high-pass instead of lowpass, 0 bandwidth for bypassing the filter
        """
        filter_shifts = value
        shiftbits = self._SHIFTBITS
        alphabits = self._ALPHABITS
        bandwidths = []
        for i in range(self._FILTERSTAGES):
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
    
    def from_python(self, value):
        filterstages = self._FILTERSTAGES
        try:
            v = list(value)[:filterstages]
        except TypeError:
            v = list([value])[:filterstages]
        filter_shifts = 0
        shiftbits = self._SHIFTBITS
        alphabits = self._ALPHABITS
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
    

class PWMRegister(Register):
    # FloatRegister that defines the PWM voltage similar to setting a float
    # see FPGA code for more detailed description on how the PWM works
    def __init__(self, address, CFG_BITS=24, PWM_BITS=8, **kwargs):
        super(PWMRegister,self).__init__(address=address, **kwargs)
        self.CFG_BITS = int(CFG_BITS)
        self.PWM_BITS = int(PWM_BITS)

    def to_python(self, value):
        value = int(value)
        pwm = float(value>>(self.CFG_BITS-self.PWM_BITS)&(2**self.PWM_BITS-1))
        mod = value & (2**(self.CFG_BITS-self.PWM_BITS)-1)
        postcomma = float(bin(mod).count('1'))/(self.CFG_BITS-self.PWM_BITS)
        voltage = 1.8 * (pwm + postcomma) / 2**self.PWM_BITS
        if voltage > 1.8:
            logger.error("Readout value from PWM (%h) yields wrong voltage %f",
                         value, voltage)
        return voltage
           
    def from_python(self, value):
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
