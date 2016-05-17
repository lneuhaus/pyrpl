###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#    Copyright (C) 2014-2016  Leonhard Neuhaus  (neuhaus@spectro.jussieu.fr)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################


import numpy as np
import time
from time import sleep
import sys

from registers import *
from bijection import Bijection

class BaseModule(object):
    
    # factor to manually compensate 125 MHz oscillator frequency error
    # real_frequency = 125 MHz * _frequency_correction
    _frequency_correction = 1.0
    
    def help(self, register=''):
        """returns the docstring of the specified register name
        
           if register is an empty string, all available docstrings are returned"""
        if register:
            return type(self).__dict__[register].__doc__
        else:
            string = ""
            for key in type(self).__dict__.keys():
                if isinstance( type(self).__dict__[key], Register):
                    docstring = self.help(key)
                    if not docstring.startswith('_'): # mute internal registers
                        string += key + ": " + docstring + '\r\n\r\n'
            return string
        
    def __init__(self, client, addr_base=0x40000000):
        """ Creates the prototype of a RedPitaya Module interface

        arguments: client must be a viable redpitaya memory client
                   addr_base is the base address of the module, such as 0x40300000
                   for the PID module
        """
        self._client = client
        self._addr_base = addr_base
        self.__doc__ = "Available registers: \r\n\r\n"+self.help()

    def _reads(self, addr, length):
        return self._client._reads(self._addr_base + addr, length)

    def _writes(self, addr, values):
        self._client._writes(self._addr_base + addr, values)

    def _read(self, addr):
        return int(self._reads(addr, 1)[0])

    def _write(self, addr, value):
        self._writes(addr, [int(value)])
    
    def _to_pyint(self, v, bitlength=14):
        v = v & (2**bitlength - 1)
        if v >> (bitlength - 1):
            v = v - 2**bitlength
        return int(v)

    def _from_pyint(self, v, bitlength=14):
        v = int(v)
        if v < 0:
            v = v + 2**bitlength
        v = (v & (2**bitlength - 1))
        return np.uint32(v)
    
    
class HK(BaseModule):
    def __init__(self, client):
        super(HK, self).__init__(client, addr_base=0x40000000)
    
    id = SelectRegister(0x0, doc="device ID", options={"prototype0": 0, "release1": 1})
    digital_loop = Register(0x0C, doc="enables digital loop")
    expansion_P = [IORegister(0x20, 0x18, 0x10, bit=i, outputmode=True,
                             doc="positive digital io") for i in range(8)]
    expansion_N = [IORegister(0x24, 0x1C, 0x14, bit=i, outputmode=True,
                             doc="positive digital io") for i in range(8)]
    led = Register(0x30,doc="LED control with bits 1:8")
    # another option: access led as array of bools
    # led = [BoolRegister(0x30,bit=i,doc="LED "+str(i)) for i in range(8)]

class AMS(BaseModule):
    """mostly deprecated module. do not use without understanding!!!"""
    def __init__(self, client):
        super(AMS, self).__init__(client, addr_base=0x40400000)
    
    @property
    def pwm_full(self):
        """PWM full variable from FPGA code"""
        return float(156.0)
        # return 249 #also works fine!!

    def to_dac(self, pwmvalue, bitselect):
        """
        PWM value (100% == 156)
        Bit select for PWM repetition which have value PWM+1
        """
        return ((pwmvalue & 0xFF) << 16) + (bitselect & 0xFFFF)

    def rel_to_dac(self, v):
        v = np.long(np.round(v * (17 * (self.pwm_full + 1) - 1)))
        return self.to_dac(v // 17, (2**(v % 17)) - 1)

    def rel_to_dac_debug(self, v):
        """max value = 1.0, min=0.0"""
        v = np.long(np.round(v * (17 * (self.pwm_full + 1) - 1)))
        return (v // 17, (2**(v % 17)) - 1)

    def setdac0(self, pwmvalue, bitselect):
        self._write(0x20, self.to_dac(pwmvalue, bitselect))

    def setdac1(self, pwmvalue, bitselect):
        self._write(0x24, self.to_dac(pwmvalue, bitselect))

    def setdac2(self, pwmvalue, bitselect):
        self._write(0x28, self.to_dac(pwmvalue, bitselect))

    def setdac3(self, pwmvalue, bitselect):
        self._write(0x2C, self.to_dac(pwmvalue, bitselect))

    def reldac0(self, v):
        """max value = 1.0, min=0.0"""
        self._write(0x20, self.rel_to_dac(v))

    def reldac1(self, v):
        """max value = 1.0, min=0.0"""
        self._write(0x24, self.rel_to_dac(v))

    def reldac2(self, v):
        """max value = 1.0, min=0.0"""
        self._write(0x28, self.rel_to_dac(v))

    def reldac3(self, v):
        """max value = 1.0, min=0.0"""
        self._write(0x2C, self.rel_to_dac(v))


class Scope(BaseModule):
    data_length = 2**14

    def __init__(self, client):
        super(Scope, self).__init__(client, addr_base=0x40100000)
        # dsp multiplexer channels for scope and asg are the same by default
        self._ch1 = DspModule(client, module='asg1')
        self._ch2 = DspModule(client, module='asg2')
        self.inputs = self._ch1.inputs

    @property
    def input1(self):
        return self._ch1.input

    @input1.setter
    def input1(self, v):
        self._ch1.input = v

    @property
    def input2(self):
        return self._ch2.input

    @input2.setter
    def input2(self, v):
        self._ch2.input = v

    reset_writestate_machine = BoolRegister(0x0, 1, 
                            doc="Set to True to reset writestate machine. \
                            Automatically goes back to false. ")
    
    trigger_armed = BoolRegister(0x0, 0, "Set to True to arm trigger")
    
    def sw_trig(self):
        self.trigger_source = "immediately"
    
    _trigger_sources = {"off": 0,
                        "immediately": 1, 
                        "ch1_positive_edge": 2,
                        "ch1_negative_edge": 3, 
                        "ch2_positive_edge": 4,
                        "ch2_negative_edge": 5,
                        "ext_positive_edge": 6, #DIO0_P pin
                        "ext_negative_edge": 7, #DIO0_P pin
                        "asg_positive_edge": 8, 
                        "asg_negative_edge": 9}
    
    trigger_sources = _trigger_sources.keys() # help for the user
    
    trigger_source = SelectRegister(0x4, doc="Trigger source", 
                                    options=_trigger_sources)
    
    threshold_ch1 = FloatRegister(0x8, bits=14, norm=2**13, 
                                  doc="ch1 trigger threshold [volts]")
    
    threshold_ch2 = FloatRegister(0xC, bits=14, norm=2**13, 
                                  doc="ch1 trigger threshold [volts]")
    
    trigger_delay = Register(0x10, doc="trigger delay [samples]")
    
    _decimations = {2**0: 2**0,
                    2**3: 2**3,
                    2**6: 2**6,
                    2**10: 2**10,
                    2**13: 2**13,
                    2**16: 2**16}
    
    decimations = _decimations.keys() # help for the user
    
    decimation = SelectRegister(0x14, doc="decimation factor", 
                                options=_decimations)
    
    _write_pointer_current = Register(0x18, 
                            doc="current write pointer position [samples]")
    
    _write_pointer_trigger = Register(0x1C, 
                            doc="write pointer when trigger arrived [samples]")
    
    hysteresis_ch1 = FloatRegister(0x20, bits=14, norm=2**13, 
                                   doc="hysteresis for ch1 trigger [volts]")
    
    hysteresis_ch2 = FloatRegister(0x24, bits=14, norm=2**13, 
                                   doc="hysteresis for ch2 trigger [volts]")
    
    average = BoolRegister(0x28,0,
              doc="Enables averaging during decimation if set to True")
    
    # equalization filter not implemented here
    
    adc1 = FloatRegister(0x154, bits=14, norm=2**13, 
                         doc="ADC1 current value [volts]")
    
    adc2 = FloatRegister(0x158, bits=14, norm=2**13, 
                         doc="ADC2 current value [volts]")
    
    dac1 = FloatRegister(0x164, bits=14, norm=2**13, 
                         doc="DAC1 current value [volts]")
    
    dac2 = FloatRegister(0x168, bits=14, norm=2**13, 
                         doc="DAC2 current value [volts]")
    
    ch1_point = FloatRegister(0x10000, bits=14, norm=2**13, 
                              doc="1 sample of ch1 data [volts]")
    
    ch2_point = FloatRegister(0x20000, bits=14, norm=2**13, 
                              doc="1 sample of ch2 data [volts]")
    
    @property
    def rawdata_ch1(self):
        """raw data from ch1"""
        # return np.array([self.to_pyint(v) for v in self._reads(0x10000,
        # self.data_length)],dtype=np.int32)
        x = np.array(self._reads(0x10000, self.data_length), dtype=np.int16)
        x[x >= 2**13] -= 2**14
        return x
    @property
    def rawdata_ch2(self):
        """raw data from ch2"""
        # return np.array([self.to_pyint(v) for v in self._reads(0x20000,
        # self.data_length)],dtype=np.int32)
        x = np.array(self._reads(0x20000, self.data_length), dtype=np.int32)
        x[x >= 2**13] -= 2**14
        return x

    @property
    def data_ch1(self):
        """ acquired (normalized) data from ch1"""
        return np.array(
                    np.roll(self.rawdata_ch1, -(self._write_pointer_trigger + 1)),
                    dtype = np.float)/2**13
    @property
    def data_ch2(self):
        """ acquired (normalized) data from ch2"""
        return np.array(
                    np.roll(self.rawdata_ch2, -(self._write_pointer_trigger + 1)),
                    dtype = np.float)/2**13

    @property
    def data_ch1_current(self):
        """ (unnormalized) data from ch1 while acquisition is still running"""
        return np.array(
                    np.roll(self.rawdata_ch1, -(self._write_pointer_current + 1)),
                    dtype = np.float)/2**13

    @property
    def data_ch2_current(self):
        """ (unnormalized) data from ch2 while acquisition is still running"""
        return np.array(
                    np.roll(self.rawdata_ch2, -(self._write_pointer_current + 1)),
                    dtype = np.float)/2**13
    
    
    @property
    def times(self):
        return np.linspace(0.0, 8e-9*self.decimation*self.data_length,
                           self.data_length,endpoint=False)

    def setup(self, duration=1.0, trigger_source="immediately", average=True):
        """sets up the scope for a new trace aquision including arming the trigger

        duration: the minimum duration in seconds to be recorded
        trigger_source: the trigger source. see the options for the parameter separately
        average: use averaging or not when sampling is not performed at full rate.
                 similar to high-resolution mode in commercial scopes"""
        self.reset_writestate_machine = True
        self.trigger_delay = self.data_length
        self.average = average
        self.duration = duration
        self.trigger_source = trigger_source
        self.trigger_armed = True

    @property
    def sampling_time(self):
        return 8e-9 * float(self.decimation)

    @sampling_time.setter
    def sampling_time(self, v):
        """sets or returns the time separation between two subsequent points of a scope trace
        the rounding makes sure that the actual value is shorter or equal to the set value"""
        tbase = 8e-9
        factors = [65536, 8192, 1024, 64, 8, 1]
        for f in factors:
            if v >= tbase * float(f):
                self.decimation = f
                return
        self.decimation = 1
        print "Desired sampling time impossible to realize"

    @property
    def duration(self):
        return self.sampling_time * float(self.data_length)

    @duration.setter
    def duration(self, v):
        """sets returns the duration of a full scope sequence
        the rounding makes sure that the actual value is longer or equal to the set value"""
        v = float(v) / self.data_length
        tbase = 8e-9
        factors = [1, 8, 64, 1024, 8192, 65536]
        for f in factors:
            if v <= tbase * float(f):
                self.data_decimation = f
                return
        self.data_decimation = 65536
        print "Desired duration too long to realize"

# ugly workaround, but realized too late that descriptors have this limit
def make_asg(channel=1):
    if channel == 1:
        set_BIT_OFFSET = 0
        set_VALUE_OFFSET = 0x00
        set_DATA_OFFSET = 0x10000
    else:
        set_DATA_OFFSET = 0x20000
        set_VALUE_OFFSET = 0x20
        set_BIT_OFFSET = 16
    
    class Asg(BaseModule):
        _DATA_OFFSET = set_DATA_OFFSET
        _VALUE_OFFSET = set_VALUE_OFFSET
        _BIT_OFFSET = set_BIT_OFFSET
        
        def __init__(self, client):
            super(Asg, self).__init__(client, addr_base=0x40200000)
            self._counter_wrap = 0x3FFFFFFF # correct value unless you know better
            self._frequency_correction = 1.0
            if self._BIT_OFFSET == 0:
                self._dsp = DspModule(client, module='asg1')
            else:
                self._dsp = DspModule(client, module='asg2')
            self.outputs = self._dsp.outputs
        @property
        def output(self):
            return self._dsp.output
    
        @output.setter
        def output(self, v):
            self._dsp.output = v
    
        data_length = 2**14
        
        on = BoolRegister(0x0, 7+_BIT_OFFSET, doc='turns the output on or off', invert=True)
    
        sm_reset = BoolRegister(0x0, 6+_BIT_OFFSET, doc='resets the state machine')
        
        #formerly: onetimetrigger
        periodic = BoolRegister(0x0, 5+_BIT_OFFSET, invert=True,
                        doc='if False, fgen stops after performing one full waveform at its last value.')
        
        _sm_wrappointer = BoolRegister(0x0, 4+_BIT_OFFSET, 
                        doc='If False, fgen starts from data[0] value after each cycle. If True, assumes that data is periodic and jumps to the naturally next index after full cycle.')
        
        _trigger_sources = {"off": 0 << _BIT_OFFSET,
                            "immediately": 1 << _BIT_OFFSET,
                            "ext_positive_edge": 2 << _BIT_OFFSET, #DIO0_P pin
                            "ext_negative_edge": 3 << _BIT_OFFSET, #DIO0_P pin
                            "advanced_trigger": 4 << _BIT_OFFSET} #4-advanced trigger from DIO0_P pin (output gated on trigger with hysteresis of advanced_trigger_delay in seconds)
        
        trigger_sources = _trigger_sources.keys()
        
        trigger_source = SelectRegister(0x0, bitmask=0x0007<<_BIT_OFFSET, 
                                        options=_trigger_sources, 
                                        doc="trigger source for triggered output")
        
        # offset is stored in bits 31:16 of the register. 
        # This adaptaion to FloatRegister is a little subtle but should work nonetheless 
        offset = FloatRegister(0x4+_VALUE_OFFSET, bits=14+16, bitmask=0x3FFF<<16, 
                               norm=2**16*2**13, doc="output offset [volts]")
        
        scale = FloatRegister(0x4+_VALUE_OFFSET, bits=14, bitmask=0x3FFF, 
                              norm=2**13, signed=False,  
                              doc="amplitude of output waveform [volts]")
        
        start_phase = PhaseRegister(0xC+_VALUE_OFFSET, bits=30, 
                        doc="Phase at which to start triggered waveforms [degrees]")
    
        frequency = FrequencyRegister(0x10+_VALUE_OFFSET, bits=30, 
                                      doc="Frequency of the output waveform [Hz]")
        
        firstpoint = FloatRegister(_DATA_OFFSET, bits=14, norm=2**13, 
                                doc="First value in output table [volts]")
        
        lastpoint = FloatRegister(_DATA_OFFSET+0x4*(data_length-1), 
                                  bits=14, norm=2**13, 
                                  doc="Last value in output table [volts]")
    
        _counter_wrap = Register(0x8+_VALUE_OFFSET, 
                                doc="Raw phase value where counter wraps around. To be set to 2**16*(2**14-1) = 0x3FFFFFFF in virtually all cases. ") 
    
        _counter_step = Register(0x10+_VALUE_OFFSET,doc="""Each clock cycle the counter_step is increases the internal counter modulo counter_wrap.
            The current counter step rightshifted by 16 bits is the index of the value that is chosen from the data table.
            """)
        
        _start_offset = Register(0xC, 
                        doc="counter offset for trigged events = phase offset ")
    
        def trig(self):
            self.start_phase = 0
            self.trigger_source = "immediately"
            self.trigger_source = "off"
    
        @property
        def data(self):
            """array of 2**14 values that define the output waveform. 
            
            Values should lie between -1 and 1 such that the peak output amplitude is self.scale"""
            x = np.array(
                self._reads(_DATA_OFFSET, self.data_length),
                         dtype=np.int32)
            x[x >= 2**13] -= 2**14
            return np.array(x, dtype=np.float)/2**13
    
        @data.setter
        def data(self, data):
            """array of 2**14 values that define the output waveform. 
            
            Values should lie between -1 and 1 such that the peak output amplitude is self.scale"""
            data = np.array(np.round((2**13-1)*data), dtype=np.int32)
            data[data >= 2**13] = 2**13 - 1
            data[data < 0] += 2**14
            #values that are still negativeare set to maximally negatuve
            data[data < 0] = -2**13 
            self._writes(_DATA_OFFSET, np.array(data, dtype=np.uint32))
    
        def setup(self, frequency=1, amplitude=1.0, periodic=True, offset=0, 
                           waveform="cos", trigger_source=None):
            """sets up the function generator. 
            
            waveform must be one of ['cos', 'ramp', 'DC', 'halframp']. 
            amplitude and offset in volts, frequency in Hz. 
            periodic = False outputs only one period. 
            if trigger_source is None, it should be set manually """
            self.on = False
            self.sm_reset = True
            self.trigger_source = 'off'
            self.scale = amplitude
            self.offset = offset
            
            if waveform == 'cos':
                x = np.linspace(0, 2*np.pi, self.data_length, endpoint=False)
                y = np.cos(x)
            elif waveform == 'ramp':
                y = np.linspace(-1.0,3.0, self.data_length, endpoint=False)
                y[self.data_length//2:] = -1*y[:self.data_length//2]
            elif waveform == 'halframp':
                y = np.linspace(-1.0,1.0, self.data_length, endpoint=False)
            elif waveform == 'DC':
                y = np.zeros(self.data_length)
    
            self.start_phase = 0
            self._counter_wrap = 2**16 * (2**14 - 1)
            self.frequency = frequency
            self.periodic = periodic
            self._sm_wrappointer = True
            self.on = True
            self.sm_reset = False
            if trigger_source is not None:
                self.trigger_source = trigger_source
    
        #advanced trigger - added functionality
        scopetriggerphase = PhaseRegister(0x114+_VALUE_OFFSET, bits=14, 
                       doc="phase of ASG ch1 at the moment when the last scope trigger occured [degrees]")
            
        advanced_trigger_reset = BoolRegister(0x0, 9+16, doc='resets the fgen advanced trigger')
        advanced_trigger_autorearm = BoolRegister(0x0, 11+16, doc='autorearm the fgen advanced trigger after a trigger event? If False, trigger needs to be reset with a sequence advanced_trigger_reset=True...advanced_trigger_reset=False after each trigger event.')
        advanced_trigger_invert = BoolRegister(0x0, 10+16, doc='inverts the trigger signal for the advanced trigger if True')
        
        advanced_trigger_delay = LongRegister(0x118+0x20, bits=64, doc='delay of the advanced trigger - 1 [cycles]') 
    
        def enable_advanced_trigger(self, frequency, amplitude, duration,
                                    invert=False, autorearm=False):
            self.setup(
                frequency=frequency,
                amplitude=amplitude,
                periodic=False,
                offset=0)
            self.advanced_trigger_reset = True
            self.advanced_trigger_autorearm = autorearm
            self.advanced_trigger_invert = invert
            self.advanced_trigger_delay = np.round(duration/8e-9)
            self.sm_reset = False
            self.trigger_source = 'advanced_trigger'
            self.output_zero = False
            self.advanced_trigger_reset = False
    
        def disable_advanced_trigger(self):
            self.advanced_trigger_reset = True
            self.trigger_source = 'immediately'
            self.sm_reset = True
            self.output_zero = True
    
    return Asg
    
Asg1 = make_asg(channel=1)
Asg2 = make_asg(channel=2)


class DspModule(BaseModule):
    _inputs = dict(
        pid0=0,
        pid1=1,
        pid2=2,
        pid3=3,
        iir=4,
        iq0=5,
        iq1=6,
        iq2=7,
        asg1=8,
        asg2=9,
        # scope1 = 8, #same as asg1 by design
        # scope2 = 9, #same as asg2 by design
        adc1=10,
        adc2=11,
        dac1=12,
        dac2=13)
    inputs = _inputs.keys()
    
    _outputs = dict(
        off=0,
        out1=1,
        out2=2,
        both=3)
    outputs = _outputs.keys()
    
    input = SelectRegister(0x0, options=_inputs, 
                           doc="selects the input signal of the module")
    
    output = SelectRegister(0x4, options=_outputs, 
                            doc="selects to which analog output the module \
                            signal is sent directly")    

    output_saturated = SelectRegister(0x8, options=_outputs, 
                                      doc = "tells you which output \
                                      is currently in saturation")

    def __init__(self, client, module='pid0'):
        self.number = self._inputs[module]
        super(DspModule, self).__init__(client,
            addr_base=0x40300000+self.number*0x10000)
    


class FilterModule(DspModule):

    @property
    def _FILTERSTAGES(self):
        return self._read(0x220)

    @property
    def _SHIFTBITS(self):
        return self._read(0x224)

    @property
    def _MINBW(self):
        return self._read(0x228)

    @property
    def _ALPHABITS(self):
        return int(np.ceil(np.log2(125000000 / self._MINBW)))

    @property
    def _filter_shifts(self):
        v = self._read(0x120)
        return v

    @_filter_shifts.setter
    def _filter_shifts(self, val):
        self._write(0x120, val)

    @property
    def inputfilter(self):
        """returns a list of bandwidths for the low-pass filter cascade before the module
           negative bandwidth stands for high-pass instead of lowpass, 0 bandwidth for bypassing the filter
        """
        filter_shifts = self._filter_shifts
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

    @inputfilter.setter
    def inputfilter(self, v):
        filterstages = self._FILTERSTAGES
        try:
            v = list(v)[:filterstages]
        except TypeError:
            v = list([v])[:filterstages]
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
        self._filter_shifts = filter_shifts


class Pid(FilterModule):
    _PSR = 12 # Register(0x200)

    _ISR = 32 # Register(0x204)
    
    _DSR = 10 # Register(0x208)
    
    _GAINBITS = 24 #Register(0x20C)

    @property
    def ival(self):
        return float(self._to_pyint(self._read(0x100), bitlength=32))/2**13
    
    @ival.setter
    def ival(self, v):
        """set the value of the register holding the integrator's sum [volts]"""
        return self._write(0x100, self._from_pyint(int(round(v*2**13)), bitlength=16))
    
    setpoint = FloatRegister(0x104, bits=14, norm=2**13, 
                             doc="pid setpoint [volts]")
    
    p = FloatRegister(0x108, bits=_GAINBITS, norm=2**_PSR, 
                             doc="pid proportional gain [1]")
    i = FloatRegister(0x10C, bits=_GAINBITS, norm=2**_ISR * 2.0 * np.pi * 8e-9, 
                             doc="pid integral unity-gain frequency [Hz]")
    
    @property
    def d(self):
        d = float(self._read(0x110))
        if d == 0:
            return d
        else:
            return (2**self._DSR / (2.0 * np.pi * 8e-9)) / float(d)
    @d.setter
    def d(self, v):
        "unity-gain frequency of the differentiator. turn off by setting to 0."
        if v == 0:
            w = 0
        else:
            w = (2**self._DSR / (2.0 * np.pi * 8e-9)) / float(v)
        self.write(0x110,int(w))
        
    @property
    def proportional(self):
        return self.p

    @property
    def integral(self):
        return self.i

    @property
    def derivative(self):
        return self.d

    @property
    def reg_integral(self):
        return self.ival

    @proportional.setter
    def proportional(self, v):
        self.p = v

    @integral.setter
    def integral(self, v):
        self.i = v

    @derivative.setter
    def derivative(self, v):
        self.d = v

    @reg_integral.setter
    def reg_integral(self, v):
        self.ival = v


class IQ(FilterModule):
    _output_signals = dict(
        quadrature=0,
        output_direct=1,
        pfd=2,
        off=3)
    output_signals = _output_signals.keys()
    output_signal = SelectRegister(0x10C, options=_output_signals,
                           doc = "Signal to send back to DSP multiplexer")
    
    
    _QUADRATUREFILTERSTAGES = Register(0x230)
    
    _QUADRATUREFILTERSHIFTBITS = Register(0x234)
    
    _QUADRATUREFILTERMINBW = Register(0x238)

    @property
    def _QUADRATUREFILTERALPHABITS(self):
        return int(np.ceil(np.log2(125000000 / self._QUADRATUREFILTERMINBW)))
    
    _quadraturefilter_shifts = Register(0x124)

    @property
    def bandwidth(self):
        """returns a list of bandwidths for the low-pass filter cascade applied to the two quadratures
           negative bandwidth stands for high-pass instead of lowpass, 0 bandwidth for bypassing the filter
        """
        filter_shifts = self._quadraturefilter_shifts
        shiftbits = self._QUADRATUREFILTERSHIFTBITS
        alphabits = self._QUADRATUREFILTERALPHABITS
        bandwidths = []
        for i in range(self._QUADRATUREFILTERSTAGES):
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

    @bandwidth.setter
    def bandwidth(self, v):
        filterstages = self._QUADRATUREFILTERSTAGES
        try:
            v = list(v)[:filterstages]
        except TypeError:
            v = list([v])[:filterstages]
        filter_shifts = 0
        shiftbits = self._QUADRATUREFILTERSHIFTBITS
        alphabits = self._QUADRATUREFILTERALPHABITS
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
        self._quadraturefilter_shifts = filter_shifts
    
    on = BoolRegister(0x100, 0, 
                      doc="If set to False, turns off the module, e.g. to \
                      re-synchronize the phases")
    
    on = BoolRegister(0x100, 1, 
                      doc="If True: Turns on the PFD module,\
                        if False: turns it off and resets integral")

    _LUTSZ = Register(0x200)
    _LUTBITS = Register(0x204)
    _PHASEBITS = 32 #Register(0x208)
    _GAINBITS = 18 #Register(0x20C)
    _SIGNALBITS = 14 #Register(0x210)
    _LPFBITS = 24 #Register(0x214)
    _SHIFTBITS = 8 #Register(0x218)
    
    pfd_integral = FloatRegister(0x150, bits=_SIGNALBITS, norm=_SIGNALBITS,
                                 doc = "value of the pfd integral [volts]")
    
    phase = PhaseRegister(0x104, bits=_PHASEBITS,
                          doc="Phase shift between modulation \
                          and demodulation [degrees]")
    
    frequency = FrequencyRegister(0x108, bits=_PHASEBITS,
                                  doc="frequency of iq demodulation [Hz]")

    _g1 = FloatRegister(0x110, bits=_GAINBITS, norm=2**_SHIFTBITS, 
                        doc="gain1 of iq module [volts]")
    
    _g2 = FloatRegister(0x114, bits=_GAINBITS, norm=2**_SHIFTBITS, 
                        doc="gain2 of iq module [volts]")
    amplitude = FloatRegister(0x114, bits=_GAINBITS, norm = 2**_SHIFTBITS*4, 
                        doc="amplitude of coherent modulation [volts]")

    _g3 = FloatRegister(0x118, bits=_GAINBITS, norm = 2**_SHIFTBITS, 
                        doc="gain3 of iq module [volts]")
    quadrature_factor = FloatRegister(0x118, 
                                      bits=_GAINBITS, 
                                      norm = 1.0, #2**_SHIFTBITS,  
                        doc="amplification factor of demodulated signal [a.u.]")
    
    _g4 = FloatRegister(0x11C, bits=_GAINBITS, norm = 2**_SHIFTBITS, 
                        doc="gain4 of iq module [volts]")
    
    @property
    def gain(self):
        return self._g1 * 0.039810

    @gain.setter
    def gain(self, v):
        self._g1 = float(v) / 0.039810
        self._g4 = float(v) / 0.039810

    def set(
            self,
            frequency,
            bandwidth=[0],
            gain=1.0,
            phase=0,
            Q=None,
            inpuacbandwidth=50.,
            amplitude=0.0,
            inputport=1,
            outputport=1):
        self.on = False
        self.frequency = frequency
        if Q is None:
            self.bandwidth = bandwidth
        else:
            self.bandwidth = self.frequency / Q / 2
        self.gain = gain
        self.phase = phase
        self.inputfilter = -acbandwidth
        self.amplitude = amplitude
        self.input = input
        self.output = output
        self.pfd_select = False
        self.on = True

    na_averages = Register(0x130, 
                    doc='number of cycles to perform na-averaging over')
    na_sleepcycles = Register(0x130, 
                    doc='number of cycles to wait before starting to average')

    @property
    def nadata(self):
        a, b, c, d = self._reads(0x140, 4)
        if not (
            (a >> 31 == 0) and (b >> 31 == 0) 
            and (c >> 31 == 0) and (d >> 31 == 0)):
            print "Averaging not finished. Impossible to estimate value"
            return 0 / 0
        sum = np.complex128(self._to_pyint(a,bitlength=31)) 
            + np.complex128(self._to_pyint(b,bitlength=31) * 2**31) 
            + 1j * np.complex128(self._to_pyint(c, bitlength=31)) 
            + 1j * np.complex128(self._to_pyint(d, bitlength=31) * 2**31)
        return sum / float(self.na_averages)

    # formula to estimate the na measurement time
    def na_time(self, points=1001, rbw=100, avg=1.0, sleeptimes=0.5):
        return float(avg + sleeptimes) * points / rbw 
    
    def na_trace(
            self,
            start=0,
            stop=100e3,
            points=1001,
            rbw=100,
            avg=1.0,
            amplitude=1.0,
            input=1,
            output=1,
            acbandwidth=0.0,
            sleeptimes=0.5,
            logscale=False,
            raw=False):
        # sleeptimes*1/rbw is the stall time after changing frequency before
        # averaging the quadratures
        # obtained by measuring transfer function with bnc cable
        unityfactor = 0.23094044589192711
        if rbw < 1 / 34.0:
            print "Sorry, no less than 1/34s bandwidth possible with 32 bit resolution"
        # if self.constants["verbosity"]:
        print "Estimated acquisition time:", self.na_time(points=points, rbw=rbw, avg=avg, sleeptimes=sleeptimes), "s"
        if logscale:
            x = np.logspace(
                np.log10(start),
                np.log10(stop),
                points,
                endpoint=True)
        else:
            x = np.linspace(start, stop, points, endpoint=True)
        y = np.zeros(points, dtype=np.complex128)
        self.set(frequency=x[0], bandwidth=rbw, gain=0, phase=0,
                 acbandwidth=acbandwidth,
                 amplitude=amplitude,
                 input=input, output=output)
        self.na_averages = np.int(np.round(125e6 / rbw * avg))
        self.na_sleepcycles = np.int(np.round(125e6 / rbw * sleeptimes))
        for i in range(points):
            self.frequency = x[i]
            sleep(1.0 / rbw * (avg + sleeptimes))
            x[i] = self.frequency
            y[i] = self.nadata
        amplitude = self.amplitude
        self.amplitude = 0
        if amplitude == 0:
            amplitude = 1.0  # avoid division by zero
        if raw:
            rescale = 2.0**(-self._LPFBITS) / amplitude
        else:
            rescale = 2.0**(-self._LPFBITS) / amplitude / unityfactor
        y *= rescale
        # in zero-span mode, change x-axis to approximate time. Time is very
        # rudely approximated here..
        if start == stop:
            x = np.linspace(
                0,
                self.na_time(
                    points=points,
                    rbw=rbw,
                    avg=avg,
                    sleeptimes=sleeptimes),
                points,
                endpoint=False)
        return x, y

    def na_trace_stabilized(
            self,
            start=0,
            stop=100e3,
            points=1001,
            rbw=100,
            avg=1.0,
            stabilized=0.1,
            amplitude=0.1,
            maxamplitude=1.0,
            input=1,
            output=1,
            acbandwidth=50.0,
            sleeptimes=0.5,
            logscale=False,
            raw=False):
        """takes a NA trace with stabilized drive amplitude such that the return voltage remains close to the specified value of "stabilized"
            maxamplitude is the maximum allowed output amplitude, amplitude the one for the first point"""
        # sleeptimes*1/rbw is the stall time after changing frequency before
        # averaging the quadratures
        # obtained by measuring transfer function with bnc cable. nominally 1/4
        unityfactor = 0.23094044589192711
        if rbw < self._QUADRATUREFILTERMINBW:
            print "Sorry, no less than 1/34s bandwidth possible with 32 bit resolution. change the code to allow for more bits"
        # if self.constants["verbosity"]:
        print "Estimated acquisition time:", self.na_time(points=points, rbw=rbw, avg=avg, sleeptimes=sleeptimes), "s"
        if logscale:
            x = np.logspace(
                np.log10(start),
                np.log10(stop),
                points,
                endpoint=True)
        else:
            x = np.linspace(start, stop, points, endpoint=True)
        y = np.zeros(points, dtype=np.complex128)
        z = np.zeros(points, dtype=np.complex128)

        self.set(frequency=x[0], bandwidth=rbw, gain=0, phase=0,
                 acbandwidth=acbandwidth,
                 amplitude=amplitude,
                 input=input, output=output)
        self.na_averages = np.int(np.round(125e6 / rbw * avg))
        self.na_sleepcycles = np.int(np.round(125e6 / rbw * sleeptimes))

        if raw:
            rescale = 2.0**(-self._LPFBITS)
        else:
            rescale = 2.0**(-self._LPFBITS) / unityfactor

        for i in range(points):
            self.iq_frequency = x[i]
            sleep(1.0 / rbw * (avg + sleeptimes))
            x[i] = self.iq_frequency
            y[i] = self.iq_nadata
            amplitude = self.amplitude
            z[i] = amplitude
            if amplitude == 0:
                y[i] *= rescale  # avoid division by zero
            else:
                y[i] *= float(rescale / float(amplitude))
            amplitude = stabilized / np.abs(y[i])
            if amplitude > maxamplitude:
                amplitude = maxamplitude
            self.amplitude = amplitude

        self.amplitude = 0
        # in zero-span mode, change x-axis to approximate time. Time is very
        # rudely approximated here..
        if start == stop:
            x = np.linspace(
                0,
                self.na_time(
                    points=points,
                    rbw=rbw,
                    avg=avg,
                    sleeptimes=sleeptimes),
                points,
                endpoint=False)
        return x, y, z


class IIR(DspModule):
    iir_channel = 0
    iir_invert = True  # invert denominator coefficients to convert from scipy notation to
    # the implemented notation (following Oppenheim and Schaefer: DSP)
    
    _IIRBITS = Register(0x200)
    _IIRSHIFT = Register(0x204)
    _IIRSTAGES = Register(0x208)
    
    def iir_datalength(self):
        return 2 * 4 * self._IIRSTAGES
    
    iir_loops = Register(0x100, 
                         doc="Decimation factor of IIR w.r.t. 125 MHz. \
                         Must be at least 3. ")

    @property
    def iir_rawdata(self):
        l = self.iir_datalength
        return self._reads(0x8000, 1024)

    @iir_rawdata.setter
    def iir_rawdata(self, v):
        l = self.iir_datalength
        return self._write(0x8000, v)
    
    on = BoolRegister(0x104, 0, doc="IIR is on")
    reset = BoolRegister(0x104, 0, doc="IIR is on", invert=True)
    
    shortcut = BoolRegister(0x104, 1, doc="IIR is bypassed")
    copydata = BoolRegister(0x104, 2, 
                        doc="If True: coefficients are updated from memory")
    iir_overflow = Register(0x108, 
                            doc="Bitmask for various overflow conditions")

    @property
    def iir_rawcoefficients(self):
        data = np.array([v for v in self._reads(
            0x28000 + self.iir_channel * 0x1000, 8 * self.iir_loops)])
        #data = data[::2]*2**32+data[1::2]
        return data

    @iir_rawcoefficients.setter
    def iir_rawcoefficients(self, v):
        pass

    def from_double(self, v, bitlength=64, shift=0):
        print v
        v = int(np.round(v * 2**shift))
        v = v & (2**bitlength - 1)
        hi = (v >> 32) & ((1 << 32) - 1)
        lo = (v >> 0) & ((1 << 32) - 1)
        print hi, lo
        return hi, lo

    def to_double(self, hi, lo, bitlength=64, shift=0):
        print hi, lo
        hi = int(hi) & ((1 << (bitlength - 32)) - 1)
        lo = int(lo) & ((1 << 32) - 1)
        v = int((hi << 32) + lo)
        if v >> (bitlength - 1) != 0:  # sign bit is set
            v = v - 2**bitlength
        print v
        v = np.float64(v) / 2**shift
        return v

    @property
    def iir_coefficients(self):
        l = self.iir_loops
        if l == 0:
            return np.array([])
        elif l > self._IIRSTAGES:
            l = self._IIRSTAGES
        data = np.array([v for v in self._reads(
            0x28000 + self.iir_channel * 0x1000, 8 * l)])
        coefficients = np.zeros((l, 6), dtype=np.float64)
        bitlength = self._IIRBITS
        shift = self._IIRSHIFT
        for i in range(l):
            for j in range(6):
                if j == 2:
                    coefficients[i, j] = 0
                elif j == 3:
                    coefficients[i, j] = 1.0
                else:
                    if j > 3:
                        k = j - 2
                    else:
                        k = j
                    coefficients[
                        i,
                        j] = self.to_double(
                        data[
                            i * 8 + 2 * k + 1],
                        data[
                            i * 8 + 2 * k],
                        bitlength=bitlength,
                        shift=shift)
                    if j > 3 and self.iir_invert:
                        coefficients[i, j] *= -1
        return coefficients

    @iir_coefficients.setter
    def iir_coefficients(self, v):
        v = np.array([vv for vv in v], dtype=np.float64)
        l = len(v)
        if l > self._IIRSTAGES:
            print "Error: Filter contains too many sections to be implemented"
        bitlength = self._IIRBITS
        shift = self._IIRSHIFT
        data = np.zeros(self.iir_stages * 8, dtype=np.uint32)
        for i in range(l):
            for j in range(6):
                if j == 2:
                    if v[i, j] != 0:
                        print "Attention: b_2 (" + str(i) + ") is not zero but " + str(v[i, j])
                elif j == 3:
                    if v[i, j] != 1:
                        print "Attention: a_0 (" + str(i) + ") is not one but " + str(v[i, j])
                else:
                    if j > 3:
                        k = j - 2
                        if self.iir_invert:
                            v[i, j] *= -1
                    else:
                        k = j
                    hi, lo = self.from_double(
                        v[i, j], bitlength=bitlength, shift=shift)
                    data[i * 8 + k * 2 + 1] = hi
                    data[i * 8 + k * 2] = lo  # np.uint32(lo&((1<<32)-1))
        data = [int(d) for d in data]
        self._writes(0x28000 + 0x10000 * self.iir_channel, data)

    def iir_unity(self):
        c = np.zeros((self.iir_stages, 6), dtype=np.float64)
        c[0, 0] = 1.0
        c[:, 3] = 1.0
        self.iir_coefficients = c
        self.iir_loops = 1

    def iir_zero(self):
        c = np.zeros((self.iir_stages, 6), dtype=np.float64)
        c[:, 3] = 1.0
        self.iir_coefficients = c
        self.iir_loops = 1
