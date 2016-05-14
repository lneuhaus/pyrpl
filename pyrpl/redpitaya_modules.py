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


class BaseModule(object):
    _frequency_correction = 1.0
    # fundamental functionality to read and write unsigned integer (32 bits
    # wide) arrays

    def __init__(self, client, addr_base=None):
        """ Creates the prototype of a RedPitaya Module interface

        arguments: client must be a viable redpitaya memory client
                   addr_base is the base address of the module, such as 0x40300000
                   for the PID module
        """
        self._client = client
        self._addr_base = addr_base

    def reads(self, addr, length):
        return self._client.reads(self._addr_base + addr, length)

    def writes(self, addr, values):
        self._client.writes(self._addr_base + addr, values)

    # derived functions
    def read(self, addr):
        return self.reads(addr, 1)[0]

    def write(self, addr, value):
        self.writes(addr, [value])

    def setbit(self, addr, bitnumber):
        v = self.read(addr) | (0x00000001 << bitnumber)
        self.write(addr, v)
        return v

    def clrbit(self, addr, bitnumber):
        v = self.read(addr) & (~(0x00000001 << bitnumber))
        self.write(addr, v)
        return v

    def changebit(self, addr, bitnumber, v):
        if v:
            return self.setbit(addr, bitnumber)
        else:
            return self.clrbit(addr, bitnumber)

    def bitstate(self, addr, bitnumber):
        return bool(self.read(addr) & (0x00000001 << bitnumber))

    def to_pyint(self, v, bitlength=14):
        v = v & (2**bitlength - 1)
        if v >> (bitlength - 1):
            v = v - 2**bitlength
        return np.int32(v)

    def from_pyint(self, v, bitlength=14):
        v = int(v)
        if v < 0:
            v = v + 2**bitlength
        v = (v & (2**bitlength - 1))
        return np.uint32(v)


class HK(BaseModule):

    def __init__(self, client):
        super(HK, self).__init__(client, addr_base=0x40000000)

    @property
    def id(self):
        r = self.read(0x0)
        if r == 0:
            return "prototype0"
        elif r == 1:
            return "release1"
        else:
            return "unknown"

    @property
    def digital_loop(self):
        return self.bitstate(0x0C, 0)

    @digital_loop.setter
    def digital_loop(self, v):
        self.changebit(0x0C, 0, v)

    @property
    def expansion_P_direction(self):
        return self.read(0x10)

    @expansion_P_direction.setter
    def expansion_P_direction(self, v):
        v = v & 0xFF
        self.write(0x10, v)

    @property
    def expansion_P(self):
        return self.read(0x18)

    @expansion_P.setter
    def expansion_P(self, v):
        v = v & 0xFF
        self.write(0x18, v)

    @property
    def do6p(self):
        self.expansion_P_direction = self.expansion_P_direction | 0b01000000
        return self.bitstate(0x18, 6)

    @do6p.setter
    def do6p(self, v):
        self.expansion_P_direction = self.expansion_P_direction | 0b01000000
        return self.changebit(0x18, 6, v)

    @property
    def do7p(self):
        self.expansion_P_direction = self.expansion_P_direction | 0b10000000
        return self.bitstate(0x18, 7)

    @do7p.setter
    def do7p(self, v):
        self.expansion_P_direction = self.expansion_P_direction | 0b10000000
        return self.changebit(0x18, 7, v)

    @property
    def led(self):
        return self.read(0x30)

    @led.setter
    def led(self, v):
        self.write(0x30, v)
    #@property
    # def expansion_N_direction(self):
    #    return self.read(0x14)
    #
    # @property
    # def expansion_N_direction(self):
    #    return self.read(0x14)

    @property
    def advanced_trigger_delay(self):
        """ counter offset for trigged events = phase offset """
        v = self.reads(0x40, 2)
        return 8e-9 * (np.int(v[1]) * 2**32 + np.int(v[0]) + 1)

    @advanced_trigger_delay.setter
    def advanced_trigger_delay(self, v):
        v = np.round(v / 8e-9 - 1.0)
        mv = (int(v) >> 32) & 0x00000000FFFFFFFF
        lv = int(v) & 0x00000000FFFFFFFF
        self.write(0x44, mv)
        self.write(0x40, lv)

    @property
    def advanced_trigger_on(self):
        """ counter offset for trigged events = phase offset """
        v = self.read(0x48)
        return not (v & 0b1)

    @advanced_trigger_on.setter
    def advanced_trigger_on(self, v):
        if not v:
            self.write(0x48, 0x01)
        else:
            self.write(0x48, 0x00)


class AMS(BaseModule):

    def __init__(self, client):
        super(AMS, self).__init__(client, addr_base=0x40400000)

    @property
    def temp(self):
        ADC_FULL_RANGE_CNT = 0xfff
        raw = self.read(0x30)
        return float(raw) * 503.975 / float(ADC_FULL_RANGE_CNT) - 273.15

    def from_xadc(self, v):
        # need to check in what convention data come, i.e. if 2's complement or (as the memory map suggests) unsinged int
        #        return self.to_pyint(v,bitlength=12)
        return v & (2**12 - 1)

    @property
    def aif0(self):
        return self.from_xadc(self.read(0x0))

    @property
    def aif1(self):
        return self.from_xadc(self.read(0x4))

    @property
    def aif2(self):
        return self.from_xadc(self.read(0x8))

    @property
    def aif3(self):
        return self.from_xadc(self.read(0xC))

    @property
    def aif4(self):
        """this is the 5V power supply"""
        return self.from_xadc(self.read(0x10))

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
        self.write(0x20, self.to_dac(pwmvalue, bitselect))

    def setdac1(self, pwmvalue, bitselect):
        self.write(0x24, self.to_dac(pwmvalue, bitselect))

    def setdac2(self, pwmvalue, bitselect):
        self.write(0x28, self.to_dac(pwmvalue, bitselect))

    def setdac3(self, pwmvalue, bitselect):
        self.write(0x2C, self.to_dac(pwmvalue, bitselect))

    def reldac0(self, v):
        """max value = 1.0, min=0.0"""
        self.write(0x20, self.rel_to_dac(v))

    def reldac1(self, v):
        """max value = 1.0, min=0.0"""
        self.write(0x24, self.rel_to_dac(v))

    def reldac2(self, v):
        """max value = 1.0, min=0.0"""
        self.write(0x28, self.rel_to_dac(v))

    def reldac3(self, v):
        """max value = 1.0, min=0.0"""
        self.write(0x2C, self.rel_to_dac(v))

    @property
    def vccpint(self):
        return self.from_xadc(self.read(0x34))

    @property
    def vccpaux(self):
        return self.from_xadc(self.read(0x38))

    @property
    def vccbram(self):
        return self.from_xadc(self.read(0x3C))

    @property
    def vccint(self):
        return self.from_xadc(self.read(0x40))

    @property
    def vccaux(self):
        return self.from_xadc(self.read(0x44))

    @property
    def vccddr(self):
        return self.from_xadc(self.read(0x48))


class Scope(BaseModule):
    data_length = 2**14

    def __init__(self, client):
        super(Scope, self).__init__(client, addr_base=0x40100000)
        # dsp multiplexer channels for scope and asg are the same by default
        self._ch1 = DSPModule(client, number='asg1')
        self._ch2 = DSPModule(client, number='asg2')

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

    def reset_writestate_machine(self, v=True):
        if v:
            self.setbit(0x0, 1)
        else:
            self.clrbit(0x0, 1)

    def arm_trigger(self, v=True):
        if v:
            self.setbit(0x0, 0)
        else:
            self.clrbit(0x0, 0)

    def sw_trig(self):
        self.trigger_source = 1

    @property
    def trigger_source(self):
        """Trigger source:
        1-trig immediately
        2-ch A threshold positive edge
        3-ch A threshold negative edge
        4-ch B threshold positive edge
        5-ch B threshold negative edge
        6-external trigger positive edge - DIO0_P pin
        7-external trigger negative edge
        8-arbitrary wave generator application positive edge
        9-arbitrary wave generator application negative edge
        """
        return self.read(0x4) & 0xF

    @trigger_source.setter
    def trigger_source(self, v):
        v = v & 0xF
        self.write(0x4, v)

    @property
    def threshold_ch1(self):
        return self.to_pyint(self.read(0x8), bitlength=14)

    @threshold_ch1.setter
    def threshold_ch1(self, v):
        self.write(0x8, self.from_pyint(v, bitlength=14))

    @property
    def threshold_ch2(self):
        return self.to_pyint(self.read(0xC), bitlength=14)

    @threshold_ch2.setter
    def threshold_ch2(self, v):
        self.write(0xC, self.from_pyint(v, bitlength=14))

    @property
    def trigger_delay(self):
        """must be strictly above 0, else some functionality bugs, i.e. software trigger"""
        return np.uint32(self.read(0x10))

    @trigger_delay.setter
    def trigger_delay(self, v):
        self.write(0x10, self.from_pyint(v, bitlength=32))

    @property
    def data_decimation(self):
        """
        Data decimation, supports only this values:
        1,8, 64,1024,8192,65536.
        If other value is written data will NOT be correct.
        """
        return self.read(0x14)

    @data_decimation.setter
    def data_decimation(self, v):
        self.write(0x14, v)

    @property
    def write_pointer_current(self):
        return np.int32(self.read(0x18) & (2**14 - 1))

    @property
    def write_pointer_trigger(self):
        return np.int32(self.read(0x1C) & (2**14 - 1))

    @property
    def hysteresis_ch1(self):
        """
        Ch A threshold hysteresis. Value must be outside to enable trigger again.
        """
        return self.to_pyint(self.read(0x20), bitlength=14)

    @hysteresis_ch1.setter
    def hysteresis_ch1(self, v):
        """
        Ch A threshold hysteresis. Value must be outside to enable trigger again.
        """
        self.write(0x20, self.from_pyint(v, bitlength=14))

    @property
    def hysteresis_ch2(self):
        """
        Ch B threshold hysteresis. Value must be outside to enable trigger again.
        """
        return self.to_pyint(self.read(0x24), bitlength=14)

    @hysteresis_ch2.setter
    def hysteresis_ch2(self, v):
        """
        Ch B threshold hysteresis. Value must be outside to enable trigger again.
        """
        self.write(0x24, self.from_pyint(v, bitlength=14))

    @property
    def average(self):
        """
        Enable signal average at decimation
        """
        return self.bitstate(0x28, 0)

    @average.setter
    def average(self, v):
        self.changebit(0x28, 0, v)

    # equalization filter not implemented here

    @property
    def rawdata_ch1(self):
        # return np.array([self.to_pyint(v) for v in self.reads(0x10000,
        # self.data_length)],dtype=np.int32)
        x = np.array(self.reads(0x10000, self.data_length), dtype=np.int16)
        x[x >= 2**13] -= 2**14
        return x

    @property
    def rawdata_ch2(self):
        # return np.array([self.to_pyint(v) for v in self.reads(0x20000,
        # self.data_length)],dtype=np.int32)
        x = np.array(self.reads(0x20000, self.data_length), dtype=np.int32)
        x[x >= 2**13] -= 2**14
        return x

    @property
    def data_ch1(self):
        return np.roll(self.rawdata_ch1, -(self.write_pointer_trigger + 1))

    @property
    def data_ch2(self):
        return np.roll(self.rawdata_ch2, -(self.write_pointer_trigger + 1))

    @property
    def data_ch1_current(self):
        return np.roll(self.rawdata_ch1, -(self.write_pointer_current + 1))

    @property
    def data_ch2_current(self):
        return np.roll(self.rawdata_ch2, -(self.write_pointer_current + 1))

    @property
    def adc1(self):
        return self.to_pyint(self.read(0x154))

    @property
    def adc2(self):
        return self.to_pyint(self.read(0x158))

    @property
    def dac1(self):
        return self.to_pyint(self.read(0x164))

    @property
    def dac2(self):
        return self.to_pyint(self.read(0x168))

    @property
    def onedata_ch1(self):
        return self.to_pyint(self.read(0x10000))

    @property
    def onedata_ch2(self):
        return self.to_pyint(self.read(0x20000))

    @property
    def times(self):
        return np.linspace(
            0.0,
            8e-9 *
            self.data_decimation *
            float(
                self.data_length),
            self.data_length,
            endpoint=False)

    def setup(self, duration=1.0, trigger_source=1, average=True):
        """sets up the scope for a new trace aquision including arming the trigger

        duration: the minimum duration in seconds to be recorded
        trigger_source: the trigger source. see the options for the parameter separately
        average: use averaging or not when sampling is not performed at full rate.
                 similar to high-resolution mode in commercial scopes"""
        self.reset_writestate_machine()
        self.trigger_delay = self.data_length
        # self.arm_trigger(v=False)
        self.average = average
        self.frequency = frequency
        self.trigger_source = trigger_source
        # self.reset_writestate_machine(v=False)
        self.arm_trigger()

    def arm(self, frequency=None, trigger_source=1, trigger_delay=None):
        if not frequency is None:
            self.frequency = frequency
        if trigger_delay is None:
            self.trigger_delay = self.data_length
        else:
            # *self.data_length))
            self.trigger_delay = np.int(np.round(trigger_delay))
        self.trigger_source = trigger_source
        self.arm_trigger()

    @property
    def frequency(self):
        return 1.0 / self.duration

    @frequency.setter
    def frequency(self, v):
        """
        sets up the scope so that it resolves at least a full oscillation at this frequency.
        The actual inverse record length should be found by performing a read-out of this value after setting it.
        """
        fbase = 125e6 / float(2**14)
        factors = [1, 8, 64, 1024, 8192, 65536, 65537]
        for f in factors:
            if v > fbase / float(f):
                self.data_decimation = f
                break
            if f == 65537:
                self.data_decimation = 65536
                print "Frequency too low: Impossible to sample the entire waveform"

    @property
    def sampling_time(self):
        return 8e-9 * float(self.data_decimation)

    @sampling_time.setter
    def sampling_time(self, v):
        """sets or returns the time separation between two subsequent points of a scope trace
        the rounding makes sure that the actual value is shorter or equal to the set value"""
        tbase = 8e-9
        factors = [65536, 8192, 1024, 64, 8, 1]
        for f in factors:
            if v >= tbase * float(f):
                self.data_decimation = f
                return
        self.data_decimation = 1
        print "Desired sampling time impossible to realize"

    @property
    def duration(self):
        return self.duration_per_sample * float(self.data_length)

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


class ASG(BaseModule):

    def __init__(self, client, channel='A'):
        super(ASG, self).__init__(client, addr_base=0x40200000)
        self._frequency_correction = 1.0
        self.data_length = 2**14
        if channel == 'B':
            self.data_offset = 0x20000
            self.value_offset = 0x20
            self.bit_offset = 16
        else:  # this includes channel A
            self.data_offset = 0x10000
            self.value_offset = 0x00
            self.bit_offset = 0

    @property
    def scopetrigger_phase(self):
        """ phase in degrees of the function generator at the moment when the last scope trigger occured"""
        return np.float(
            self.to_pyint(
                self.read(
                    0x114 + self.value_offset),
                bitlength=14)) / 2**14 * 360.0

    @property
    def output_zero(self):
        return self.bitstate(0x0, self.bit_offset + 7)

    @output_zero.setter
    def output_zero(self, v):
        self.changebit(0x0, self.bit_offset + 7, v)

    @property
    def sm_reset(self):
        return self.bitstate(0x0, self.bit_offset + 6)

    @sm_reset.setter
    def sm_reset(self, v):
        self.changebit(0x0, self.bit_offset + 6, v)

    @property
    def advanced_trigger_reset(self):
        return self.bitstate(0x0, self.bit_offset + 9)

    @advanced_trigger_reset.setter
    def advanced_trigger_reset(self, v):
        self.changebit(0x0, self.bit_offset + 9, v)

    @property
    def advanced_trigger_autorearm(self):
        """ should the trigger remain armed after one trigger event?
        If not, the trigger needs to be reset with a advanced_trigger_reset=True - ..=False sequence for the next event"""
        return self.bitstate(0x0, self.bit_offset + 11)

    @advanced_trigger_autorearm.setter
    def advanced_trigger_autorearm(self, v):
        self.changebit(0x0, self.bit_offset + 11, v)

    @property
    def advanced_trigger_invert(self):
        return self.bitstate(0x0, self.bit_offset + 10)

    @advanced_trigger_invert.setter
    def advanced_trigger_invert(self, v):
        self.changebit(0x0, self.bit_offset + 10, v)

    @property
    def advanced_trigger_delay(self):
        """ counter offset for trigged events = phase offset """
        v = self.reads(self.value_offset + 0x118, 2)
        return 8e-9 * (np.int(v[1]) * 2**32 + np.int(v[0]) + 1)

    @advanced_trigger_delay.setter
    def advanced_trigger_delay(self, v):
        v = np.round(v / 8e-9 - 1.0)
        mv = (int(v) >> 32) & 0x00000000FFFFFFFF
        lv = int(v) & 0x00000000FFFFFFFF
        self.write(self.value_offset + 0x11C, mv)
        self.write(self.value_offset + 0x118, lv)

    def enable_advanced_trigger(
            self,
            frequency,
            amplitude,
            duration,
            invert=False,
            autorearm=False):
        self.setup_cosine(
            frequency=frequency,
            amplitude=amplitude,
            onetimetrigger=False,
            offset=0,
            data=True)
        self.advanced_trigger_reset = True
        self.advanced_trigger_autorearm = autorearm
        self.advanced_trigger_invert = invert
        self.advanced_trigger_delay = duration
        self.sm_reset = False
        self.trigger_source = 4
        self.output_zero = False
        self.advanced_trigger_reset = False

    def disable_advanced_trigger(self):
        self.advanced_trigger_reset = True
        self.trigger_source = 1
        self.sm_reset = True
        self.output_zero = True

    @property
    def sm_onetimetrigger(self):
        return self.bitstate(0x0, self.bit_offset + 5)

    @sm_onetimetrigger.setter
    def sm_onetimetrigger(self, v):
        self.changebit(0x0, self.bit_offset + 5, v)

    @property
    def sm_wrappointer(self):
        return self.bitstate(0x0, self.bit_offset + 4)

    @sm_wrappointer.setter
    def sm_wrappointer(self, v):
        self.changebit(0x0, self.bit_offset + 4, v)

    @property
    def trigger_source(self):
        """
        1-trig immediately
        2-external trigger positive edge - DIO0_P pin
        3-external trigger negative edge
        4-advanced trigger from DIO0_P pin (output gated on trigger with hysteresis of advanced_trigger_delay in seconds)
        """
        v = self.read(0x0)
        return (v >> self.bit_offset) & 0x07

    @trigger_source.setter
    def trigger_source(self, v):
        v = v & 0x7
        v = v << self.bit_offset
        mask = ~(0x7 << self.bit_offset)
        v = (self.read(0x0) & mask) | v
        self.write(0x0, v)

    @property
    def offset(self):
        v = self.read(self.value_offset + 0x4)
        v = (v >> 16) & 0x00003FFF
        if (v & 2**13):
            v = v - 2**14
        return int(v)

    @offset.setter
    def offset(self, v):
        v = self.from_pyint(v, 14) * 2**16 + self.scale
        self.write(self.value_offset + 0x4, v)

    @property
    def scale(self):
        """
        Amplitude scale. 0x2000 == multiply by 1. Unsigned
        """
        v = self.read(self.value_offset + 0x4)
        v = v & 0x00003FFF
        return int(v)

    @scale.setter
    def scale(self, v):
        if v >= 2**14:
            v = 2**14 - 1
        if v < 0:
            v = 0
        v = int(v) + (self.offset * 2**16)
        self.write(self.value_offset + 0x4, v)

    @property
    def counter_wrap(self):
        """
        typically this value is set to
        2**16*(2**14-1)
        in order to exploit the full data buffer
        """
        v = self.read(self.value_offset + 0x8)
        return v & 0x3FFFFFFF

    @counter_wrap.setter
    def counter_wrap(self, v):
        v = v & 0x3FFFFFFF
        self.write(self.value_offset + 0x8, v)

    @property
    def counter_step(self):
        """Each clock cycle the counter_step is increases the internal counter modulo counter_wrap.
        The current counter step rightshifted by 16 bits is the index of the value that is chosen from the data table.
        """
        v = self.read(self.value_offset + 0x10)
        return v & 0x3FFFFFFF

    @counter_step.setter
    def counter_step(self, v):
        v = v & 0x3FFFFFFF
        self.write(self.value_offset + 0x10, v)

    @property
    def start_offset(self):
        """ counter offset for trigged events = phase offset """
        v = self.read(self.value_offset + 0x0C)
        return v & 0x3FFFFFFF

    @start_offset.setter
    def start_offset(self, v):
        v = v & 0x3FFFFFFF
        self.write(self.value_offset + 0x0C, v)

    @property
    def full_timescale(self):
        """not sure if there is an offset for counter_wrap, need to check code"""
        return 8e-9 * float(self.counter_wrap + 2**16) / \
            float(self.counter_step)

    @property
    def max_index(self):
        return self.counter_wrap >> 16

    @property
    def data(self):
        x = np.array(
            self.reads(
                self.data_offset,
                self.data_length),
            dtype=np.int32)
        x[x >= 2**13] -= 2**14
        return x

    @data.setter
    def data(self, data):
        data = np.array(data, dtype=np.int32)
        data[data >= 2**13] = 2**13 - 1
        data[data < 0] += 2**14
        self.writes(self.data_offset, np.array(data, dtype=np.uint32))

    @property
    def onedata(self):
        return self.to_pyint(self.read(self.data_offset))

    @onedata.setter
    def onedata(self, v):
        self.write(self.data_offset, self.from_pyint(v))

    @property
    def lastpoint(self):
        """the last point before the output jumps back to the zero/wrapped index value"""
        step = self.counter_step
        if step == 0:
            return 0
        else:
            return self.counter_wrap / step

    @property
    def frequency(self):
        return float(self.counter_step) / float(self.counter_wrap + \
                     2**16) / 8e-9 * self._frequency_correction

    @frequency.setter
    def frequency(self, v):
        v = float(v) / self._frequency_correction
        self.counter_step = np.long(
            np.round(float(v) * 8e-9 * (float(self.counter_wrap + 2**16))))

    def setup_cosine(
            self,
            frequency=1,
            amplitude=1.0,
            onetimetrigger=False,
            offset=0,
            data=True):
        # corresponds to 2Vpp sine
        self.mode = "cosine"
        self.output_zero = True
        self.sm_reset = True
        self.trigger_source = 0
        self.scale = int(amplitude * 2**13)
        self.offset = offset

        if data:
            self.data = np.array(np.round(-(2**13 - 1) * np.cos(
                np.linspace(0, 2.0 * np.pi, 2**14, endpoint=False))), dtype=np.int32)
        self.start_offset = 0
        self.counter_wrap = 2**16 * (2**14 - 1)
        self.frequency = frequency

        self.sm_onetimetrigger = onetimetrigger
        self.sm_wrappointer = True
        self.output_zero = False
        self.sm_reset = False

    def setup_ramp(
            self,
            frequency=1,
            amplitude=1.0,
            onetimetrigger=False,
            offset=0,
            data=True):
        # corresponds to 2Vpp sine
        self.mode = "cosine"
        self.output_zero = True
        self.sm_reset = True
        self.trigger_source = 0
        self.scale = int(amplitude * 2**13)
        self.offset = offset

        def ramp(phase):
            return np.abs((phase / np.pi) % 2.0 - 1.0) * 2.0 - 1.0
        if data:
            self.d = np.zeros(2**14, dtype=np.long)
            for i in range(len(self.d)):
                self.d[i] = np.long(
                    np.round(-(2**13 - 1) * ramp((float(i) / 2**14) * 2 * np.pi)))
            self.data = self.d

        self.start_offset = 0
        self.counter_wrap = 2**16 * (2**14 - 1)
        self.frequency = frequency

        self.sm_onetimetrigger = onetimetrigger
        self.sm_wrappointer = True
        self.output_zero = False
        self.sm_reset = False

    def setup_halframp(
            self,
            frequency=1,
            amplitude=1.0,
            onetimetrigger=False,
            offset=0,
            data=True):
        # corresponds to 2Vpp sine
        self.mode = "cosine"
        self.output_zero = True
        self.sm_reset = True
        self.trigger_source = 0
        self.scale = int(amplitude * 2**13)
        self.offset = offset
        if data:
            self.d = np.zeros(2**14, dtype=np.long)
            for i in range(len(self.d)):
                self.d[i] = np.long(i - 2**13)
            self.data = self.d

        self.start_offset = 0
        self.counter_wrap = 2**16 * (2**14 - 1)
        self.frequency = frequency

        self.sm_onetimetrigger = onetimetrigger
        self.sm_wrappointer = True
        self.output_zero = False
        self.sm_reset = False

    def setup_offset(self, offset=0):
        self.mode = "DC"
        # corresponds to 2Vpp sine
        self.sm_reset = True
        self.trigger_source = 0
        self.scale = 0
        self.offset = 0

        self.d = np.zeros(2**14, dtype=np.long)
        self.data = self.d

        self.start_offset = 0
        self.counter_wrap = 2**16 * (2**14 - 1)
        self.frequency = frequency

        self.sm_onetimetrigger = onetimetrigger
        self.sm_wrappointer = True
        self.output_zero = False
        self.sm_reset = False

    def trig(self, frequency=None):
        if not frequency is None:
            self.frequency = frequency
        self.start_offset = 0
        self.trigger_source = 1
        self.trigger_source = 0

    @property
    def dio_override(self):
        v = self.read(0x40)
        v = (v >> self.bit_offset) & 0x0000FF
        return v

    @dio_override.setter
    def dio_override(self, v):
        v = v << self.bit_offset | (
            self.read(0x40) & (~(0xFF << self.bit_offset)))
        self.write(0x40, v)


class DspModule(BaseModule):
    _signal = dict(
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

    _output = dict(
        off=0,
        out1=1,
        out2=2,
        both=3)

    def __init__(self, client, number=0):
        self._get_signal(number)
        self.number = number % 16
        super(
            DspModule,
            self).__init__(
            client,
            addr_base=0x40300000 +
            self.number *
            0x10000)

    @property
    def signals(self):
        return list(self._signal.keys())

    def _get_signal(self, number=0):
        if isinstance(number, str):
            return number
        for signal, signalnumber in self._signal.iteritems():
            if number == signalnumber:
                return signal
        return None

    def _get_number(self, signal="pid0"):
        if isinstance(signal, int):
            return signal
        if signal in self._signal.keys():
            return self._signal[signal]
        return None

    def _get_output(self, number=1):
        if isinstance(number, str):
            return number
        for signal, signalnumber in self._output.iteritems():
            if number == signalnumber:
                return signal
        return None

    def _get_outputnumber(self, signal="out1"):
        if isinstance(signal, int):
            return signal
        if signal in self._output.keys():
            return self._output[signal]
        return None

    @property
    def input(self):
        return self._get_signal(self.read(0x0))

    @input.setter
    def input(self, signal):
        self.write(0x0, self._get_number(signal))

    @property
    def output(self):
        return self._get_output(self.read(0x4))

    @output.setter
    def output(self, signal):
        self.write(0x4, self._get_outputnumber(signal))

    @property
    def dac_saturated(self):
        return self._get_output(self.read(0x8))


class FilterModule(DspModule):

    @property
    def _FILTERSTAGES(self):
        return self.read(0x220)

    @property
    def _SHIFTBITS(self):
        return self.read(0x224)

    @property
    def _MINBW(self):
        return self.read(0x228)

    @property
    def _ALPHABITS(self):
        return int(np.ceil(np.log2(125000000 / self._MINBW)))

    @property
    def _filter_shifts(self):
        v = self.read(0x120)
        return v

    @_filter_shifts.setter
    def _filter_shifts(self, val):
        self.write(0x120, val)

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

    @property
    def ival(self):
        return self.to_pyint(self.read(0x100), bitlength=32)

    @ival.setter
    def ival(self, v):
        """set the value of the register holding the integrator's sum"""
        return self.write(0x100, self.from_pyint(v, bitlength=16))

    @property
    def setpoint(self):
        return self.to_pyint(self.read(0x104), bitlength=14)

    @setpoint.setter
    def setpoint(self, v):
        return self.write(0x104, self.from_pyint(v, bitlength=14))

    @property
    def _p(self):
        return self.to_pyint(self.read(0x108), bitlength=self._GAINBITS)

    @_p.setter
    def _p(self, v):
        return self.write(0x108, self.from_pyint(v, bitlength=self._GAINBITS))

    @property
    def _i(self):
        return self.to_pyint(self.read(0x10C), bitlength=self._GAINBITS)

    @_i.setter
    def _i(self, v):
        return self.write(0x10C, self.from_pyint(v, bitlength=self._GAINBITS))

    @property
    def _d(self):
        return self.to_pyint(self.read(0x110), bitlength=self._GAINBITS)

    @_d.setter
    def _d(self, v):
        return self.write(0x110, self.from_pyint(v, bitlength=self._GAINBITS))

    @property
    def p(self):
        return float(self._p) / 2**self._PSR

    @p.setter
    def p(self, v):
        "proportional gain from input to output"
        self._p = float(v) * 2**self._PSR

    @property
    def i(self):
        return float(self._i) / (2**self._ISR * 2.0 * np.pi * 8e-9)

    @i.setter
    def i(self, v):
        "unity-gain frequency of the integrator"
        self._i = float(v) * 2**self._ISR * 2.0 * np.pi * 8e-9

    @property
    def d(self):
        d = float(self._d)
        if d == 0:
            return d
        else:
            return (2**self._DSR / (2.0 * np.pi * 8e-9)) / float(d)

    @d.setter
    def d(self, v):
        "unity-gain frequency of the differentiator. turn off by setting to 0."
        if v == 0:
            self._d = 0
        else:
            self._d = (2**self._DSR / (2.0 * np.pi * 8e-9)) / float(v)

    @property
    def _PSR(self):
        return self.read(0x200)

    @property
    def _ISR(self):
        return self.read(0x204)

    @property
    def _DSR(self):
        return self.read(0x208)

    @property
    def _GAINBITS(self):
        return self.read(0x20C)

    # renaming of a number of functions for compatibility with oder code
    @property
    def pidnumber(self):
        return self.number

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
    _output_select = dict(
        quadrature=0,
        output_direct=1,
        pfd=2,
        off=3)

    def _get_output_select(self, number=1):
        if isinstance(number, str):
            return number
        for signal, signalnumber in self._output_select.iteritems():
            if number == signalnumber:
                return signal
        return None

    def _get_output_selectnumber(self, signal="quadrature"):
        if isinstance(signal, int):
            return signal
        if signal in self._output_select.keys():
            return self._output_select[signal]
        return None

    @property
    def output_select(self):
        return self._get_output_select(self.read(0x10C))

    @output_select.setter
    def output_select(self, signal):
        self.write(0x10C, self._get_output_selectnumber(signal))

    @property
    def _QUADRATUREFILTERSTAGES(self):
        return self.read(0x230)

    @property
    def _QUADRATUREFILTERSHIFTBITS(self):
        return self.read(0x234)

    @property
    def _QUADRATUREFILTERMINBW(self):
        return self.read(0x238)

    @property
    def _QUADRATUREFILTERALPHABITS(self):
        return int(np.ceil(np.log2(125000000 / self._QUADRATUREFILTERMINBW)))

    @property
    def _quadraturefilter_shifts(self):
        v = self.read(0x124)
        return v

    @_quadraturefilter_shifts.setter
    def _quadraturefilter_shifts(self, val):
        self.write(0x124, val)

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

    @property
    def on(self):
        return self.bitstate(0x100, 0)

    @on.setter
    def on(self, val):
        self.changebit(0x100, 0, val)

    @property
    def pfd_on(self):
        return self.bitstate(0x100, 1)

    @pfd_on.setter
    def pfd_on(self, val):
        self.changebit(0x100, 1, val)

    @property
    def _LUTSZ(self):
        return self.read(0x200)

    @property
    def _LUTBITS(self):
        return self.read(0x204)

    @property
    def _PHASEBITS(self):
        return self.read(0x208)

    @property
    def _GAINBITS(self):
        return self.read(0x20C)

    @property
    def _SIGNALBITS(self):
        return self.read(0x210)

    @property
    def _LPFBITS(self):
        return self.read(0x214)

    @property
    def _SHIFTBITS(self):
        return self.read(0x218)

    @property
    def pfd_integral(self):
        return self.to_pyint(self.read(0x150))

    @property
    def _start_phase(self):
        return self.read(0x104)

    @_start_phase.setter
    def _start_phase(self, v):
        self.write(0x104, v)

    @property
    def _shift_phase(self):
        return self.read(0x108)

    @_shift_phase.setter
    def _shift_phase(self, v):
        self.write(0x108, v)

    @property
    def startphase_deg(self):
        return float(self._start_phase) / (2**self._PHASEBITS) * 360.0

    @startphase_deg.setter
    def startphase_deg(self, v):
        self._start_phase = int(
            np.round(
                (2**self._PHASEBITS) *
                float(v) /
                360.0))

    @property
    def _g1(self):
        return float(self.to_pyint(self.read(0x110), bitlength=self._GAINBITS))

    @_g1.setter
    def _g1(self, v):
        v = int(np.round(v))
        self.write(0x110, self.from_pyint(v, bitlength=self._GAINBITS))

    @property
    def _g2(self):
        return float(self.to_pyint(self.read(0x114), bitlength=self._GAINBITS))

    @_g2.setter
    def _g2(self, v):
        v = int(np.round(v))
        self.write(0x114, self.from_pyint(v, bitlength=self._GAINBITS))

    @property
    def _g3(self):
        return float(self.to_pyint(self.read(0x118), bitlength=self._GAINBITS))

    @_g3.setter
    def _g3(self, v):
        v = int(np.round(v))
        self.write(0x118, self.from_pyint(v, bitlength=self._GAINBITS))

    @property
    def _g4(self):
        return float(self.to_pyint(self.read(0x11C), bitlength=self._GAINBITS))

    @_g4.setter
    def _g4(self, v):
        v = int(np.round(v))
        self.write(0x11C, self.from_pyint(v, bitlength=self._GAINBITS))

    @property
    def _maxgain(self):
        maxvalue = 2**(self._GAINBITS - 1) - 1
        unityvalue = 2**self._SHIFTBITS
        return float(maxvalue) / float(unityvalue)

    @property
    def _rawgain(self):
        return float(self._g1) / 2**self._SHIFTBITS

    @_rawgain.setter
    def _rawgain(self, v):
        maxvalue = 2**(self._GAINBITS - 1) - 1
        unityvalue = 2**self._SHIFTBITS
        g = int(np.round(float(v) * float(unityvalue)))
        if g > maxvalue:
            print "Reducing gain ", g, " to maximum allowed value of ", maxvalue, " for iq-channel ", self.iq_channel
            g = maxvalue
        self._g1 = g
        self._g4 = g

    @property
    def gain(self):
        return self._rawgain * 0.039810

    @gain.setter
    def gain(self, v):
        self._rawgain = float(v) / 0.039810

    @property
    def amplitude(self):
        return float(self._g2) / 2**self._SHIFTBITS / \
            4.0  # same factor as in the setter

    @amplitude.setter
    def amplitude(self, v):
        """v is output signal amplitude in Volts at 50 Ohm output impedance. Cannot be larger than 0.5V"""
        v = float(
            v) * 4.0  # experimentally found factor (could probably be calculated as well)
        maxvalue = 2**(self._GAINBITS - 1) - 1
        unityvalue = 2**self._SHIFTBITS
        g = int(np.round(float(v) * float(unityvalue)))
        if g > maxvalue:
            print "Reducing gain ", g, " to maximum allowed value of ", maxvalue, " for iq-channel ", self.iq_channel
            g = maxvalue
        self._g2 = g

    @property
    def phase(self):
        return self.startphase_deg

    @phase.setter
    def phase(self, v):
        self.startphase_deg = v

    @property
    def frequency(self):
        return 125e6 * float(self._shift_phase) / \
            (2**self._PHASEBITS) * self._frequency_correction

    @frequency.setter
    def frequency(self, v):
        v = float(v) / self._frequency_correction
        self._shift_phase = int(
            np.round(float(v) / 125e6 * (2**self._PHASEBITS)))

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

    @property
    def na_averages(self):
        return self.read(0x130)

    @na_averages.setter
    def na_averages(self, v):
        return self.write(0x130, int(v))

    @property
    def na_sleepcycles(self):
        return self.read(0x134)

    @na_sleepcycles.setter
    def na_sleepcycles(self, v):
        return self.write(0x134, int(v))

    @property
    def nadata(self):
        a, b, c, d = self.reads(0x140, 4)
        if not (
            (a >> 31 == 0) and (
                b >> 31 == 0) and (
                c >> 31 == 0) and (
                d >> 31 == 0)):
            print "Averaging not finished. Impossible to estimate value"
            return 0 / 0
        sum = np.complex128(self.to_pyint(a,
                                          bitlength=31)) + np.complex128(self.to_pyint(b,
                                                                                       bitlength=31) * 2**31) + 1j * np.complex128(self.to_pyint(c,
                                                                                                                                                 bitlength=31)) + 1j * np.complex128(self.to_pyint(d,
                                                                                                                                                                                                   bitlength=31) * 2**31)
        return sum / float(self.iq_na_averages)

    # formula to estimate the na measurement time
    def na_time(self, points=1001, rbw=100, avg=1.0, sleeptimes=0.5):
        return float(avg + sleeptimes) * points / rbw  # +5*5ms*points

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

    @property
    def quadrature_factor(self):
        return self._g3

    @quadrature_factor.setter
    def quadrature_factor(self, v):
        self._g3 = v


class IIR(DspModule):
    iir_channel = 0
    iir_invert = True  # invert denominator coefficients to convert from scipy notation to
    # the implemented notation (following Oppenheim and Schaefer: DSP)

    @property
    def _IIRBITS(self):
        return self.read(0x200)

    @property
    def _IIRSHIFT(self):
        return self.read(0x204)

    @property
    def _IIRSTAGES(self):
        return self.read(0x208)

    @property
    def iir_datalength(self):
        return 2 * 4 * self._IIRSTAGES

    @property
    def iir_loops(self):
        v = self.read(0x100)
        if v < 3:
            print "WARNING: iir_loops must be at least 3 for proper filter behaviour."
        return v

    @iir_loops.setter
    def iir_loops(self, v):
        return self.write(0x100, int(v))

    @property
    def iir_rawdata(self):
        l = self.iir_datalength
        return self.reads(0x8000, 1024)

    @iir_loops.setter
    def iir_rawdata(self, v):
        l = self.iir_datalength
        return self.write(0x8000, v)

    @property
    def iir_reset(self):
        return not self.iir_on

    @iir_reset.setter
    def iir_reset(self, v):
        self.iir_on = not v

    @property
    def iir_on(self):
        return self.bitstate(0x104, 0)

    @iir_on.setter
    def iir_on(self, v):
        self.changebit(0x104, 0, v)

    @property
    def iir_shortcut(self):
        return self.bitstate(0x104, 1)

    @iir_shortcut.setter
    def iir_shortcut(self, v):
        self.changebit(0x104, 1, v)

    @property
    def iir_copydata(self):
        return self.bitstate(0x104, 2)

    @iir_copydata.setter
    def iir_copydata(self, v):
        self.changebit(0x104, 2, v)

    @property
    def iir_overflow(self):
        return self.read(0x108)

    @property
    def iir_rawcoefficients(self):
        data = np.array([v for v in self.reads(
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
        data = np.array([v for v in self.reads(
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
        self.writes(0x28000 + 0x10000 * self.iir_channel, data)

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
