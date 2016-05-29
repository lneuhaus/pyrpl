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
import matplotlib.pyplot as plt
import logging

from .registers import *
from .bijection import Bijection
import .iir

class TimeoutError(ValueError):
    pass
class NotReadyError(ValueError):
    pass

class BaseModule(object):
    
    # factor to manually compensate 125 MHz oscillator frequency error
    # real_frequency = 125 MHz * _frequency_correction
    _frequency_correction = 1.0

    # prevent the user from setting a nonexisting attribute
    def __setattr__(self, name, value):
        if hasattr(self,name) or name.startswith('_'):
            super(BaseModule, self).__setattr__(name, value)
        else:
            raise ValueError("New module attributes may not be set at runtime. Attribute "
                             +name+" is not defined in class "+self.__class__.__name__)
    
    def help(self, register=''):
        """returns the docstring of the specified register name
        
           if register is an empty string, all available docstrings are returned"""
        if register:
            string = type(self).__dict__[register].__doc__
            return string
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
        self._logger = logging.getLogger(name=__name__)
        self._client = client
        self._addr_base = addr_base
        self.__doc__ = "Available registers: \r\n\r\n"+self.help()

    def _reads(self, addr, length):
        return self._client.reads(self._addr_base + addr, length)

    def _writes(self, addr, values):
        self._client.writes(self._addr_base + addr, values)

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


class Scope(BaseModule):
    data_length = 2**14
    inputs = None
    
    def __init__(self, client):
        super(Scope, self).__init__(client, addr_base=0x40100000)
        # dsp multiplexer channels for scope and asg are the same by default
        self._ch1 = DspModule(client, module='asg1')
        self._ch2 = DspModule(client, module='asg2')
        self.inputs = self._ch1.inputs
        self._setup_called = False

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

    _reset_writestate_machine = BoolRegister(0x0, 1, 
                            doc="Set to True to reset writestate machine. \
                            Automatically goes back to false. ")
    
    _trigger_armed = BoolRegister(0x0, 0, doc="Set to True to arm trigger")
    
    _trigger_sources = {"off": 0,
                        "immediately": 1, 
                        "ch1_positive_edge": 2,
                        "ch1_negative_edge": 3, 
                        "ch2_positive_edge": 4,
                        "ch2_negative_edge": 5,
                        "ext_positive_edge": 6, #DIO0_P pin
                        "ext_negative_edge": 7, #DIO0_P pin
                        "asg1": 8, 
                        "asg2": 9}
    
    trigger_sources = _trigger_sources.keys() # help for the user
    
    _trigger_source = SelectRegister(0x4, doc="Trigger source", 
                                    options=_trigger_sources)
    
    def sw_trig(self):
        self.trigger_source = "immediately"
    
    @property
    def trigger_source(self):
        if hasattr(self,"_trigger_source_memory"):
            return self._trigger_source_memory
        else:
            self._trigger_source_memory = self._trigger_source
            return self._trigger_source_memory
        
    @trigger_source.setter
    def trigger_source(self, val):
        self._trigger_source = val
        self._trigger_source_memory = val
        
    _trigger_debounce = Register(0x90, doc="Trigger debounce time [cycles]")

    trigger_debounce = FloatRegister(0x90, bits=20, norm=125e6, 
                                     doc = "Trigger debounce time [s]")
    
    threshold_ch1 = FloatRegister(0x8, bits=14, norm=2**13, 
                                  doc="ch1 trigger threshold [volts]")
    
    threshold_ch2 = FloatRegister(0xC, bits=14, norm=2**13, 
                                  doc="ch1 trigger threshold [volts]")
    
    _trigger_delay = Register(0x10, doc="trigger delay [samples]")

    @property
    def trigger_delay(self):
        return (self._trigger_delay - self.data_length//2)*self.sampling_time
    
    @trigger_delay.setter
    def trigger_delay(self, delay):
        delay = int(np.round(delay/self.sampling_time)) + self.data_length//2
        if delay <= 0:
            delay = 1 # bug in scope code: 0 does not work
        elif delay > self.data_length-1:
            delay = self.data_length-1
        self._trigger_delay = delay

    _trigger_delay_running = BoolRegister(0x0, 2, doc="trigger delay running (register adc_dly_do)")

    _adc_we_keep = BoolRegister(0x0, 3, doc="Scope resets trigger automatically (adc_we_keep)")

    _adc_we_cnt = Register(0x2C, doc="Number of samles that have passed since trigger was armed (adc_we_cnt)")
   
    current_timestamp = LongRegister(0x15C,
                                     bits=64,
                                     doc="An absolute counter " \
                                         + "for the time [cycles]")    

    trigger_timestamp = LongRegister(0x164,
                                     bits=64,
                                     doc= "An absolute counter " \
                                         +"for the trigger time [cycles]")
    
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
    
    voltage1 = FloatRegister(0x154, bits=14, norm=2**13, 
                         doc="ADC1 current value [volts]")
    
    voltage2 = FloatRegister(0x158, bits=14, norm=2**13, 
                         doc="ADC2 current value [volts]")
    
    dac1 = FloatRegister(0x164, bits=14, norm=2**13, 
                         doc="DAC1 current value [volts]")
    
    dac2 = FloatRegister(0x168, bits=14, norm=2**13, 
                         doc="DAC2 current value [volts]")
    
    ch1_firstpoint = FloatRegister(0x10000, bits=14, norm=2**13, 
                              doc="1 sample of ch1 data [volts]")
    
    ch2_firstpoint = FloatRegister(0x20000, bits=14, norm=2**13, 
                              doc="1 sample of ch2 data [volts]")
    
    @property
    def _rawdata_ch1(self):
        """raw data from ch1"""
        # return np.array([self.to_pyint(v) for v in self._reads(0x10000,
        # self.data_length)],dtype=np.int32)
        x = np.array(self._reads(0x10000, self.data_length), dtype=np.int16)
        x[x >= 2**13] -= 2**14
        return x

    @property
    def _rawdata_ch2(self):
        """raw data from ch2"""
        # return np.array([self.to_pyint(v) for v in self._reads(0x20000,
        # self.data_length)],dtype=np.int32)
        x = np.array(self._reads(0x20000, self.data_length), dtype=np.int32)
        x[x >= 2**13] -= 2**14
        return x

    @property
    def _data_ch1(self):
        """ acquired (normalized) data from ch1"""
        return np.array(
                    np.roll(self._rawdata_ch1, -(self._write_pointer_trigger + self._trigger_delay + 1)),
                    dtype = np.float)/2**13
    @property
    def _data_ch2(self):
        """ acquired (normalized) data from ch2"""
        return np.array(
                    np.roll(self._rawdata_ch2, -(self._write_pointer_trigger + self._trigger_delay + 1)),
                    dtype = np.float)/2**13

    @property
    def _data_ch1_current(self):
        """ (unnormalized) data from ch1 while acquisition is still running"""
        return np.array(
                    np.roll(self._rawdata_ch1, -(self._write_pointer_current + 1)),
                    dtype = np.float)/2**13

    @property
    def _data_ch2_current(self):
        """ (unnormalized) data from ch2 while acquisition is still running"""
        return np.array(
                    np.roll(self._rawdata_ch2, -(self._write_pointer_current + 1)),
                    dtype = np.float)/2**13
    
    @property
    def times(self):
        #duration = 8e-9*self.decimation*self.data_length
        #endtime = duration*
        duration = self.duration
        trigger_delay = self.trigger_delay
        return np.linspace(trigger_delay - duration/2.,
                           trigger_delay + duration/2.,
                           self.data_length,endpoint=False)

    def setup(self,
              duration=None,
              trigger_source=None,
              average=None,
              threshold=None,
              hysteresis=None,
              trigger_delay=None):
        """sets up the scope for a new trace aquision including arming the trigger

        duration: the minimum duration in seconds to be recorded
        trigger_source: the trigger source. see the options for the parameter separately
        average: use averaging or not when sampling is not performed at full rate.
                 similar to high-resolution mode in commercial scopes

        if a parameter is None, the current attribute value is used"""
        self._setup_called = True
        self._reset_writestate_machine = True
        if average is not None:
            self.average = average
        if duration is not None:
            self.duration = duration
        if trigger_source is not None:
            self.trigger_source = trigger_source
        else:
            self.trigger_source = self.trigger_source
        if threshold is not None:
            self.threshold_ch1 = threshold
            self.threshold_ch2 = threshold
        if hysteresis is not None:
            self.hysteresis_ch1 = hysteresis
            self.hysteresis_ch2 = hysteresis
        if trigger_delay is not None:
            self.trigger_delay = trigger_delay
        self._trigger_armed = True
        if self.trigger_source == 'immediately':
            self.sw_trig()

    def curve_ready(self):
        """
        Returns True if trigger has been triggered
        """
        return (not self._trigger_armed) and self._setup_called

    def _get_ch(self, ch):
        if not ch in [1,2]:
            raise ValueError("channel should be 1 or 2, got " + str(ch))
        return self._data_ch1 if ch==1 else self._data_ch2
    
    def curve(self, ch=1, trigger_timeout=1.):
        """
        Takes a curve from channel ch as soon as the trigger is valid.
        If no trigger occurs after timeout seconds, raises TimeoutError.
        If trigger_timeout <= 0, then no check for trigger is done and
        the data from the buffer is returned directly.
        """
        if not self._setup_called:
            raise NotReadyError("setup has never been called")
        SLEEP_TIME = 0.001
        total_sleep = 0
        if trigger_timeout>0:
            while(total_sleep<trigger_timeout):
                if self.curve_ready():
                    return self._get_ch(ch)
                total_sleep+=SLEEP_TIME
                sleep(SLEEP_TIME)
        else:
            return self._get_ch(ch)
        raise TimeoutError("scope wasn't trigged within timeout")

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
        self._logger.error("Desired sampling time impossible to realize")

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
                self.decimation = f
                return
        self.decimation = 65536
        self._logger.error("Desired duration too long to realize")


# ugly workaround, but realized too late that descriptors have this limit
def make_asg(channel=1):
    if channel == 1:
        set_BIT_OFFSET = 0
        set_VALUE_OFFSET = 0x00
        set_DATA_OFFSET = 0x10000
        set_default_output_direct = 'out1'
    else:
        set_DATA_OFFSET = 0x20000
        set_VALUE_OFFSET = 0x20
        set_BIT_OFFSET = 16
        set_default_output_direct = 'out2'
    
    class Asg(BaseModule):
        _DATA_OFFSET = set_DATA_OFFSET
        _VALUE_OFFSET = set_VALUE_OFFSET
        _BIT_OFFSET = set_BIT_OFFSET
        default_output_direct = set_default_output_direct
        output_directs = None
        
        def __init__(self, client):
            super(Asg, self).__init__(client, addr_base=0x40200000)
            self._counter_wrap = 0x3FFFFFFF # correct value unless you know better
            self._frequency_correction = 1.0
            if self._BIT_OFFSET == 0:
                self._dsp = DspModule(client, module='asg1')
            else:
                self._dsp = DspModule(client, module='asg2')
            self.output_directs = self._dsp.output_directs
        @property
        def output_direct(self):
            return self._dsp.output_direct
    
        @output_direct.setter
        def output_direct(self, v):
            self._dsp.output_direct = v
    
        data_length = 2**14

        # register set_a_zero
        on = BoolRegister(0x0, 7+_BIT_OFFSET, doc='turns the output on or off', invert=True)

        # register set_a_rst
        sm_reset = BoolRegister(0x0, 6+_BIT_OFFSET, doc='resets the state machine')
        
        # register set_a/b_once
        periodic = BoolRegister(0x0, 5+_BIT_OFFSET, invert=True,
                        doc='if False, fgen stops after performing one full waveform at its last value.')
        
        # register set_a/b_wrap
        _sm_wrappointer = BoolRegister(0x0, 4+_BIT_OFFSET, 
                        doc='If False, fgen starts from data[0] value after each cycle. If True, assumes that data is periodic and jumps to the naturally next index after full cycle.')

        # register set_a_rgate
        _counter_wrap = Register(0x8+_VALUE_OFFSET, 
                                doc="Raw phase value where counter wraps around. To be set to 2**16*(2**14-1) = 0x3FFFFFFF in virtually all cases. ") 
    
        # register trig_a/b_src
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
                self._reads(self._DATA_OFFSET, self.data_length),
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
            self._writes(self._DATA_OFFSET, np.array(data, dtype=np.uint32))
    
        def setup(self, 
                  waveform='cos', 
                  frequency=1, 
                  amplitude=1.0, 
                  start_phase=0, 
                  periodic=True, 
                  offset=0, 
                  trigger_source='immediately',
                  output_direct = default_output_direct):
            """sets up the function generator. 
            
            waveform must be one of ['cos', 'ramp', 'DC', 'halframp']. 
            amplitude and offset in volts, frequency in Hz. 
            periodic = False outputs only one period. 
            start_phase is the start phase in degrees
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
            else: 
                y = self.data
                self._logger.error("Waveform name %s not recognized. Specify waveform manually"%waveform)
            self.data = y
            
            self.start_phase = start_phase
            self._counter_wrap = 2**16 * (2**14 - 1)
            self.frequency = frequency
            self.periodic = periodic
            self._sm_wrappointer = True
            self.sm_reset = False
            self.on = True
            if trigger_source is not None:
                self.trigger_source = trigger_source
        
        
        #advanced trigger - added functionality
        scopetriggerphase = PhaseRegister(0x114+_VALUE_OFFSET, bits=14, 
                       doc="phase of ASG ch1 at the moment when the last scope trigger occured [degrees]")
            
        advanced_trigger_reset = BoolRegister(0x0, 9+_BIT_OFFSET, doc='resets the fgen advanced trigger')
        advanced_trigger_autorearm = BoolRegister(0x0, 11+_BIT_OFFSET, doc='autorearm the fgen advanced trigger after a trigger event? If False, trigger needs to be reset with a sequence advanced_trigger_reset=True...advanced_trigger_reset=False after each trigger event.')
        advanced_trigger_invert = BoolRegister(0x0, 10+_BIT_OFFSET, doc='inverts the trigger signal for the advanced trigger if True')
        
        advanced_trigger_delay = LongRegister(0x118+_VALUE_OFFSET, bits=64, doc='delay of the advanced trigger - 1 [cycles]') 
    
        def enable_advanced_trigger(self, frequency, amplitude, duration,
                                    invert=False, autorearm=False):
            self.setup(
                frequency=frequency,
                amplitude=amplitude,
                periodic=False,
                offset=0,
                trigger_source = None)
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
        adc1=10, #same as asg
        adc2=11,
        dac1=12,
        dac2=13,
        off=15)
    inputs = _inputs.keys()
    
    _output_directs = dict(
        off=0,
        out1=1,
        out2=2,
        both=3)
    output_directs = _output_directs.keys()
    
    input = SelectRegister(0x0, options=_inputs, 
                           doc="selects the input signal of the module")
    
    output_direct = SelectRegister(0x4, options=_output_directs, 
                            doc="selects to which analog output the module \
                            signal is sent directly")    

    out1_saturated = BoolRegister(0x8,0,doc="True if out1 is saturated")
    
    out2_saturated = BoolRegister(0x8,1,doc="True if out2 is saturated")

    def __init__(self, client, module='pid0'):
        self._number = self._inputs[module]
        super(DspModule, self).__init__(client,
            addr_base=0x40300000+self._number*0x10000)

class AuxOutput(DspModule):
    """Auxiliary outputs. PWM0-3 correspond to pins 17-20 on E2 connector.
    
    See  http://wiki.redpitaya.com/index.php?title=Extension_connectors
    to find out where to connect your output device to the board. 
    Outputs are 0-1.8V, but we will map this to -1 to 1 V internally to
    guarantee compatibility with other modules. So setting a pwm voltage 
    to '-1V' means you'll measure 0V, setting it to '+1V' you'll find 1.8V.
    
    Usage: 
    pwm0 = AuxOutput(output='pwm0')
    pwm0.input = 'pid0'
    Pid(client, module='pid0').ival = 0 # -> outputs 0.9V on PWM0
    
    Make sure you have an analog low-pass with cutoff of at most 1 kHz
    behind the output pin, and possibly an output buffer for proper 
    performance. Only recommended for temperature control or other 
    slow actuators. Big noise peaks are expected around 480 kHz.  
    
    Currently, only pwm0 and pwm1 are available.
    """
    def __init__(self, client, output='pwm0'):
        pwm_to_module = dict(pwm0 = 'adc1', pwm1='adc2')
        # future options: , pwm2 = 'dac1', pwm3='dac2')
        super(AuxOutput, self).__init__(client,module=pwm_to_module[output])
    output_direct = None
    output_directs = None
    _output_directs = None

class FilterModule(DspModule):
    inputfilter = FilterRegister(0x120, 
                                 filterstages=0x220,
                                 shiftbits=0x224,
                                 minbw=0x228,
                                 doc="Input filter bandwidths [Hz]."\
                                 "0 = off, negative bandwidth = highpass")

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
    
    min_voltage = FloatRegister(0x124, bits=14, norm=2**13, 
                             doc="minimum output signal [volts]")
    max_voltage = FloatRegister(0x128, bits=14, norm=2**13, 
                             doc="maximum output signal [volts]")
    
    p = FloatRegister(0x108, bits=_GAINBITS, norm=2**_PSR, 
                             doc="pid proportional gain [1]")
    i = FloatRegister(0x10C, bits=_GAINBITS, norm=2**_ISR * 2.0 * np.pi * 8e-9, 
                             doc="pid integral unity-gain frequency [Hz]")
    d = FloatRegister(0x110, bits=_GAINBITS, norm=2**_DSR/(2.0*np.pi*8e-9),
                     invert=True, 
                     doc="pid derivative unity-gain frequency [Hz]. Off when 0.")
    
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
    
    bandwidth = FilterRegister(0x124, 
                               filterstages=0x230,
                               shiftbits=0x234,
                               minbw=0x238,
                               doc="Quadrature filter bandwidths [Hz]."\
                                    "0 = off, negative bandwidth = highpass")
    
    on = BoolRegister(0x100, 0, 
                      doc="If set to False, turns off the module, e.g. to \
                      re-synchronize the phases")
    
    pfd_on = BoolRegister(0x100, 1, 
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
                                      norm = 2**_SHIFTBITS,  
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
        
    def setup(
            self,
            frequency,
            bandwidth=[0],
            gain=1.0,
            phase=0,
            Q=None,
            acbandwidth=50.,
            amplitude=0.0,
            input='adc1',
            output_direct='out1',
            output_signal='quadrature', 
            quadrature_factor=1.0):
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
        self.output_direct = output_direct
        self.output_signal = output_signal
        self.quadrature_factor = quadrature_factor
        self.on = True

    _na_averages = Register(0x130, 
                    doc='number of cycles to perform na-averaging over')
    _na_sleepcycles = Register(0x130, 
                    doc='number of cycles to wait before starting to average')

    @property
    def _nadata(self):
        attempt = 0
        a, b, c, d = self._reads(0x140, 4)
        while not ((a >> 31 == 0) and (b >> 31 == 0) 
                   and (c >> 31 == 0) and (d >> 31 == 0)):
            a, b, c, d = self._reads(0x140, 4)
            attempt += 1
            if attempt > 10:
                raise Exception("Trying to recover NA data while averaging is not finished. Some setting is wrong. ")
        sum = np.complex128(self._to_pyint(int(a)+(int(b)<<31),bitlength=62)) \
            + np.complex128(self._to_pyint(int(c)+(int(d)<<31), bitlength=62))*1j  
        return sum / float(self._na_averages)
    
    def na_trace(
            self,
            start=0,     # start frequency
            stop=100e3,  # stop frequency
            points=1001, # number of points
            rbw=100,     # resolution bandwidth, can be a list of 2 as well for second-order
            avg=1.0,     # averages
            amplitude=0.1, #output amplitude in volts
            input='adc1', # input signal
            output_direct='off', # output signal
            acbandwidth=0, # ac filter bandwidth, 0 disables filter, negative values represent lowpass
            sleeptimes=0.5, # wait sleeptimes/rbw for quadratures to stabilize
            logscale=False, # make a logarithmic frequency sweep
            stabilize=None, # if a float, output amplitude is adjusted dynamically so that input amplitude [V]=stabilize 
            maxamplitude=1.0, # amplitude can be limited
            ): 
        if logscale:
            x = np.logspace(
                np.log10(start),
                np.log10(stop),
                points,
                endpoint=True)
        else:
            x = np.linspace(start, stop, points, endpoint=True)
        y = np.zeros(points, dtype=np.complex128)
        amplitudes = np.zeros(points, dtype=np.float64)
        # preventive saturation
        maxamplitude = abs(maxamplitude)
        amplitude = abs(amplitude)
        if abs(amplitude)>maxamplitude:
            amplitude = maxamplitude
        self.setup(frequency=x[0], 
                 bandwidth=rbw, 
                 gain=0, 
                 phase=0,
                 acbandwidth=-np.array(acbandwidth),
                 amplitude=0,
                 input=input, 
                 output_direct=output_direct,
                 output_signal='output_direct')
        # take the discretized rbw (only using first filter cutoff)
        rbw = self.bandwidth[0]
        self._logger.info("Estimated acquisition time: %.1f s", float(avg + sleeptimes) * points / rbw)
        sys.stdout.flush() # make sure the time is shown        
        # setup averaging
        self._na_averages = np.int(np.round(125e6 / rbw * avg))
        self._na_sleepcycles = np.int(np.round(125e6 / rbw * sleeptimes))
        # compute rescaling factor
        rescale = 2.0**(-self._LPFBITS)*4.0 # 4 is artefact of fpga code
        # obtained by measuring transfer function with bnc cable - could replace the inverse of 4 above
        #unityfactor = 0.23094044589192711
        try:
            self.amplitude = amplitude # turn on NA inside try..except block
            for i in range(points):
                self.frequency = x[i] #this triggers the NA acquisition
                sleep(1.0 / rbw * (avg + sleeptimes))
                x[i] = self.frequency # get the actual (discretized) frequency
                y[i] = self._nadata
                amplitudes[i] = self.amplitude
                #normalize immediately
                if amplitudes[i] == 0:
                    y[i] *= rescale  # avoid division by zero
                else:
                    y[i] *= rescale / self.amplitude
                # set next amplitude if it has to change
                if stabilize is not None:
                    amplitude = stabilize / np.abs(y[i])
                if amplitude > maxamplitude:
                    amplitude = maxamplitude
                self.amplitude = amplitude
        # turn off the NA output, even in the case of exception (e.g. KeyboardInterrupt)
        except:
            self.amplitude = 0
            self._logger.info("NA output turned off due to an exception")
            raise
        else:
            self.amplitude = 0
        # in zero-span mode, change x-axis to approximate time. Time is very
        # rudely approximated here..
        if start == stop:
            x = np.linspace(
                0,
                1.0 / rbw * (avg + sleeptimes),
                points,
                endpoint=False)
        if stabilize is None:
            return x, y
        else:
            return x,y,amplitudes


class IIR(DspModule):
    # invert denominator coefficients to convert from scipy notation to
    # the fpga-implemented notation (following Oppenheim and Schaefer: DSP)
    _invert = True
    
    _IIRBITS = Register(0x200)
    
    _IIRSHIFT = Register(0x204)

    _IIRSTAGES = Register(0x208)
        
    loops = Register(0x100, doc="Decimation factor of IIR w.r.t. 125 MHz. "\
                                +"Must be at least 3. ")

    on = BoolRegister(0x104, 0, doc="IIR is on")
    
    shortcut = BoolRegister(0x104, 1, doc="IIR is bypassed")
    
    copydata = BoolRegister(0x104, 2, 
                doc="If True: coefficients are being copied from memory")
    
    overflow = Register(0x108, 
                            doc="Bitmask for various overflow conditions")

    def _from_double(self, v, bitlength=64, shift=0):
        v = int(np.round(v * 2**shift))
        v = v & (2**bitlength - 1)
        hi = (v >> 32) & ((1 << 32) - 1)
        lo = (v >> 0) & ((1 << 32) - 1)
        return hi, lo

    def _to_double(self, hi, lo, bitlength=64, shift=0):
        hi = int(hi) & ((1 << (bitlength - 32)) - 1)
        lo = int(lo) & ((1 << 32) - 1)
        v = int((hi << 32) + lo)
        if v >> (bitlength - 1) != 0:  # sign bit is set
            v = v - 2**bitlength
        v = np.float64(v) / 2**shift
        return v

    @property
    def coefficients(self):
        l = self.loops
        if l == 0:
            return np.array([])
        elif l > self._IIRSTAGES:
            l = self._IIRSTAGES
        # data = np.array([v for v in self._reads(0x8000, 8 * l)])
        # coefficient readback has been disabled to save FPGA resources.
        if hasattr(self,'_writtendata'):
            data = self._writtendata
        else:
            raise ValueError("Readback of coefficients not enabled. " \
                             +"You must set coefficients before reading it.")
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
                    coefficients[i, j] = self._to_double(
                        data[i * 8 + 2 * k + 1],
                        data[i * 8 + 2 * k],
                        bitlength=bitlength,
                        shift=shift)
                    if j > 3 and self._invert:
                        coefficients[i, j] *= -1
        return coefficients

    @coefficients.setter
    def coefficients(self, v):
        bitlength = self._IIRBITS
        shift = self._IIRSHIFT
        stages = self._IIRSTAGES
        v = np.array([vv for vv in v], dtype=np.float64)
        l = len(v)
        if l > stages:
            raise Exception(
                "Error: Filter contains too many sections to be implemented")
        data = np.zeros(stages * 8, dtype=np.uint32)
        for i in range(l):
            for j in range(6):
                if j == 2:
                    if v[i, j] != 0:
                        self._logger.warning("Attention: b_2 (" + str(i) \
                            + ") is not zero but " + str(v[i, j]))
                elif j == 3:
                    if v[i, j] != 1:
                        self._logger.warning("Attention: a_0 (" + str(i) \
                            + ") is not one but " + str(v[i, j]))
                else:
                    if j > 3:
                        k = j - 2
                        if self._invert:
                            v[i, j] *= -1
                    else:
                        k = j
                    hi, lo = self._from_double(
                        v[i, j], bitlength=bitlength, shift=shift)
                    data[i * 8 + k * 2 + 1] = hi
                    data[i * 8 + k * 2] = lo
        data = [int(d) for d in data]
        self._writes(0x8000, data)
        self._writtendata = data

    def _setup_unity(self):
        """sets the IIR filter transfer function unity"""
        c = np.zeros((self._IIRSTAGES, 6), dtype=np.float64)
        c[0, 0] = 1.0
        c[:, 3] = 1.0
        self.coefficients = c
        self.loops = 1

    def _setup_zero(self):
        """sets the IIR filter transfer function zero"""
        c = np.zeros((self._IIRSTAGES, 6), dtype=np.float64)
        c[:, 3] = 1.0
        self.coefficients = c
        self.loops = 1

    def setup(
            self,
            z,
            p,
            g=1.0,
            input='adc1',
            output_direct='off',
            loops=None,
            plot=False,
            #save=False,
            turn_on=True,
            tol=1e-3):
        """Setup an IIR filter
        
        the transfer function of the filter will be (k ensures DC-gain = g):

                  (s-2*pi*z[0])*(s-2*pi*z[1])...
        H(s) = k*-------------------
                  (s-2*pi*p[0])*(s-2*pi*p[1])...
        
        parameters
        --------------------------------------------------
        z:             list of zeros in the complex plane, maximum 16
        p:             list of zeros in the complex plane, maxumum 16
        g:             DC-gain
        input:         input signal
        output_direct: send directly to an analog output?
        loops:         clock cycles per loop of the filter. must be at least 3 and at most 255. set None for autosetting loops
        turn_on:       automatically turn on the filter after setup
        plot:          if True, plots the theoretical and implemented transfer functions
        tol:           tolerance for matching conjugate poles or zeros into pairs, 1e-3 is okay

        returns:       data to be passed to iir.bodeplot to plot the realized transfer function
        """
        if self._IIRSTAGES == 0:
            raise Exception(
                "Error: This FPGA bitfile does not support IIR filters! "\
                +"Please use an IIR version!")
        self.on = False
        self.shortcut = False
        self.copydata = False
        iirbits = self._IIRBITS
        iirshift = self._IIRSHIFT
        # pre-scale coefficients
        z = [zz * 2 * np.pi for zz in z]
        p = [pp * 2 * np.pi for pp in p]
        k = g
        for pp in p:
            if pp != 0:
                k *= np.abs(pp)
        for zz in z:
            if zz != 0:
                k /= np.abs(zz)
        sys = (z,p,k)
        # try to find out how many loops must be done
        preliminary_loops = int(max([len(p), len(z)])+1) / 2
        c = iir.get_coeff(sys, dt=preliminary_loops * 8e-9,
                          totalbits=iirbits, shiftbits=iirshift,
                          tol=tol, finiteprecision=False)
        minimum_loops = len(c)
        if minimum_loops < 3:
            minimum_loops = 3
        if minimum_loops > self._IIRSTAGES:
            raise Exception("Error: desired filter order is too high to "\
                            +"be implemented.")
        if loops is None:
            loops = 3
        elif loops > 255:
            loops = 255
        loops = max([loops, minimum_loops])
        # transform zeros and poles into coefficients
        dt = loops * 8e-9 / self._frequency_correction
        c = iir.get_coeff(sys, dt=dt,
                          totalbits=iirbits, shiftbits=iirshift,
                          tol=tol, finiteprecision=False)
        self.coefficients = c
        self.loops = loops
        f = np.array(self.coefficients)
        # load the coefficients into the filter - all simultaneously
        self.copydata = True
        self.copydata = False
        self.on = turn_on
        # Diagnostics here
        if plot: # or save:
            if isinstance(plot, int):
                plt.figure(plot)
            else:
                plt.figure()
        tfs = iir.psos2plot(c, sys, n=2**16, maxf=5e6, dt=dt,
                name="discrete system (dt=" + str(int(dt * 1e9)) + "ns)",
                plot=False)
        tfs += iir.psos2plot(f, None, n=2**16, maxf=5e6,
                dt=dt, name="implemented system",plot=False)
            
        #if save:
        #    if not plot:
        #        plt.close()
        #    curves = list()
        #    for tf in tfs:
        #        w, h, name = tf
        #        curve = CurveDB.create(w, h)
        #        curve.name = name
        #        z, p, k = sys
        #        curve.params["iir_loops"] = loops
        #        curve.params["iir_zeros"] = str(z)
        #        curve.params["iir_poles"] = str(p)
        #        curve.params["iir_k"] = k
        #        curve.save()
        #        curves.append(curve)
        #    for curve in curves[:-1]:
        #        curves[-1].add_child(curve)
        self._logger.info("IIR filter ready")
        self._logger.info("Maximum deviation from design coefficients: %f", max((f[0:len(c)] - c).flatten()))
        self._logger.info("Overflow pattern: %s", bin(self.overflow))
        #        if save:
        #            return f, curves[-1]
        #        else:
        #            return f
        if plot:
            iir.bodeplot(tfs, xlog=True)
        return tfs

# current work pointer: here

class AMS(BaseModule):
    """mostly deprecated module (redpitaya has removed adc support). 
    only here for dac2 and dac3"""
    def __init__(self, client):
        super(AMS, self).__init__(client, addr_base=0x40400000)        
    dac0 = PWMRegister(0x20, doc="PWM output 0 [V]")
    dac1 = PWMRegister(0x24, doc="PWM output 1 [V]")
    dac2 = PWMRegister(0x28, doc="PWM output 2 [V]")
    dac3 = PWMRegister(0x2C, doc="PWM output 3 [V]")
