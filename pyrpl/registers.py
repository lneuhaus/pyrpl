import numpy as np
import sys
#way to represent the smallest positive value
#needed to set floats to minimum count above zero
epsilon = sys.float_info.epsilon

from bijection import Bijection

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
        if self.bitmask is None:
            return self.to_python(obj._read(self.address))
        else:
            return self.to_python(obj._read(self.address)&self.bitmask)
    
    def __set__(self, obj, val):
        if self.bitmask is None:
            obj._write(self.address,self.from_python(val))
        else:
            act = obj._read(self.address)
            new = act&(~self.bitmask)|(int(self.from_python(val))&self.bitmask)
            obj._write(self.address,new)
            
class LongRegister(Register):
    """Interface for register of python type int/long with arbitrary length 'bits' (effectively unsigned)"""
    def __init__(self, address, bits=64, **kwargs):
        super(LongRegister,self).__init__(address=address, **kwargs)
        self.bits = bits
        self.size = (32+bits-bits%32)/32

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
        self.direction = BoolRegister(direction_address,bit=bit, **kwargs)
        self.direction = outputmode #set output direction
        
        
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
                 **kwargs):
        super(FloatRegister,self).__init__(address=address, **kwargs)
        self.bits = bits
        self.norm = float(norm)
        self.signed = signed
        
    def to_python(self, value):
        # 2's complement
        if self.signed:
            if value >= 2**(self.bits-1):
                value -= 2**self.bits
        # normalization
        return float(value)/self.norm
    
    def from_python(self, value):
        # round and normalize
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
    
