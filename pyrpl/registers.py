from bijection import Bijection
import sys

#way to represent the smallest positive value
#needed to set floats to minimum count above zero
epsilon = sys.float_info.epsilon


#docstring does not work yet, see: 
#http://stackoverflow.com/questions/37255109/python-docstring-for-descriptors
#for now there is a workaround: call Module.help(register)
class Register(object):
    """Interface for basic register of type int"""
    def __init__(self, address, doc=""):
        self.address = address
        self.__doc__ = doc
    
    def to_python(self, value):
        return value
    
    def from_python(self, value):
        return value
    
    def __get(self, obj, objtype=None):
        return self.to_python(obj._read(self.address))
    
    def __set__(self, obj, val):
        obj._write(self.from_python(self.address,val))

class BoolRegister(Register):
    """Inteface for boolean values, 1: True, 0: False"""
    def __init__(self, address, bit=0, doc="", invert=False):
        super(BoolRegister,self).__init__(address=address, doc=doc)
        self.bit = bit
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
    def __init__(self, read_address, write_address, direction_address, outputmode=True, bit=0, doc=""):
        if outputmode:
            address = write_address
        else:
            address = read_address
        super(BoolRegister,self).__init__(address=address, bit=bit, doc=doc)
        self.direction = BoolRegister(direction_address,bit=bit,
                                      doc=doc+" direction")
        self.direction = outputmode #set output direction
        
        
class SelectRegister(Register):
    """Implements a selection, such as for multiplexers"""
    def __init__(self, address, 
                 options={}, 
                 doc=""):
        super(SelectRegister,self).__init__(address=address, doc=doc+"\n\n"+str(options))
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
                 doc=""):
        super(FloatRegister,self).__init__(address=address, doc=doc)
        self.bits = bits
        self.norm = float(norm)
        
    def to_python(self, value):
        # 2's complement
        if value >= 2**(self.bits-1):
            value -= 2**self.bits
        # normalization
        return float(value)/self.norm
    
    def from_python(self, value):
        # make sure small float values are not rounded to zero
        if (value == epsilon):
            value = 1
        elif (value == -epsilon):
            value = -1
        else:
            # round and normalize
            value = int(round(value*self.norm)) 
        # 2's complement
        if (value < 0):
            value += 2**self.bits
        # saturation
        if (value >= 2**(self.bits-1)):
            value = (2**self.bits-1)-1
        elif (value < 2**(self.bits-1)):
            value = -2**(self.bits-1)
        return value

class PhaseRegister(FloatRegister):
    """Registers that contain a phase as a float in units of degrees."""
    """Registers that contain a frequency as a float in units of Hz"""
    def __init__(self, address, 
             bits=32, #total number of bits to represent on fpga
             doc=""):
        super(PhaseRegister,self).__init__(address=address, doc=doc)
        self.bits = bits
        
    def from_python(self, value):
        # make sure small float values are not rounded to zero
        return int(round((float(value)%360)/360*2**self.bits)) 
        
    def to_python(self, value):
        return float(value)/2**self.bits*360
    
class FrequencyRegister(Register):
    """Registers that contain a frequency as a float in units of Hz"""
    def __init__(self, address, 
             bits=32, #total number of bits to represent on fpga
             doc=""):
        super(FrequencyRegister,self).__init__(address=address, doc=doc)
        self.bits = bits
        
    def __get(self, obj, objtype=None):
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
    