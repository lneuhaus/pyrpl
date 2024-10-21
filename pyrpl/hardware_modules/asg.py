"""
There are two Arbitrary Signal Generator modules: asg1 and asg2. For
these modules, any waveform composed of :math:`2^{14}` programmable
points is sent to the output with arbitrary frequency and start phase
upon a trigger event.

.. code:: ipython3

    asg = r.asg1 # make a shortcut
    print "Trigger sources:", asg.trigger_sources
    print "Output options: ", asg.output_directs

Let's set up the ASG to output a sawtooth signal of amplitude 0.8 V
(peak-to-peak 1.6 V) at 1 MHz on output 2:

.. code:: python

    asg.output_direct = 'out2'
    asg.setup(waveform='halframp', frequency=20e4, amplitude=0.8, offset=0, trigger_source='immediately')
"""

import numpy as np
from collections import OrderedDict
from ..attributes import BoolRegister, FloatRegister, SelectRegister, SelectProperty, \
                             IntRegister, LongRegister, PhaseRegister, FrequencyRegister, FloatProperty
from ..modules import HardwareModule, SignalModule
from ..widgets.module_widgets import AsgWidget
from . import all_output_directs, dsp_addr_base


class WaveformAttribute(SelectProperty):
    default = 'sin'
    #def get_value(self, instance):
    #    return instance._waveform

    def set_value(self, instance, waveform):
        waveform = waveform.lower()
        if not waveform in instance.waveforms:
            raise ValueError("waveform shourd be one of " + instance.waveforms)
        else:
            if waveform == 'noise':
                # current amplitude becomes rms amplitude
                rmsamplitude = instance.amplitude
                # set alrady to noise to switch behavior of amplitude
                instance._waveform = 'noise'
                # amplitude now deals with the settings
                # (fpga amplitude to max, saving of rmsamplitude,
                # filling of correctly scaled data)
                instance.amplitude = rmsamplitude
                instance.random_phase = True
                # can return already now
                return waveform
            else:
                instance.random_phase = False
                instance._rmsamplitude = 0
            if waveform == 'sin':
                x = np.linspace(0, 2 * np.pi, instance.data_length,
                                endpoint=False)
                y = np.sin(x)
            elif waveform == 'cos':
                x = np.linspace(0, 2 * np.pi, instance.data_length,
                                endpoint=False)
                y = np.cos(x)
            elif waveform == 'ramp':
                y = np.linspace(-1.0, 3.0, instance.data_length,
                                endpoint=False)
                y[instance.data_length // 2:] = -1 * y[:instance.data_length // 2]
            elif waveform == 'halframp':
                y = np.linspace(-1.0, 1.0, instance.data_length,
                                endpoint=False)
            elif waveform == 'square':
                y = np.ones(instance.data_length)
                y[len(y)//2:] = -1.0
            elif waveform == 'dc':
                y = np.zeros(instance.data_length)
            else:
                y = instance.data
                instance._logger.error(
                    "Waveform name %s not recognized. Specify waveform manually" % waveform)
            instance.data = y
            instance._waveform = waveform
        return waveform


class AsgAmplitudeAttribute(FloatRegister):
    """ workaround to make rms amplitude work"""
    def get_value(self, obj):
        if obj.waveform == 'noise':
            return obj._rmsamplitude
        else:
            return super(AsgAmplitudeAttribute, self).get_value(obj)

    def set_value(self, obj, val):
        if obj.waveform == 'noise':
            # internally memorize the amplitude as it is not directly
            # stored in the fpga (see set_value(obj, 1.0) call below)
            obj._rmsamplitude = val
            # fill normal-distributed data into data memory
            obj.data = obj._noise_distribution()
            # multiplier set to 1.0 to benefit from full available resolution
            super(AsgAmplitudeAttribute, self).set_value(obj, 1.0)
        else:
            super(AsgAmplitudeAttribute, self).set_value(obj, val)



class AsgOffsetAttribute(FloatProperty):
    def __init__(self, **kwargs):
        super(AsgOffsetAttribute, self).__init__(**kwargs)

    def set_value(self, instance, val):
        instance._offset_masked = val

    def get_value(self, obj):
        return obj._offset_masked


# ugly workaround, but realized too late that descriptors have this limit
def make_asg(channel=0):
    if channel == 0:
        set_BIT_OFFSET = 0
        set_VALUE_OFFSET = 0x00
        set_DATA_OFFSET = 0x10000
        set_default_output_direct = 'off'
    else:
        set_DATA_OFFSET = 0x20000
        set_VALUE_OFFSET = 0x20
        set_BIT_OFFSET = 16
        set_default_output_direct = 'off'

    class Asg(HardwareModule, SignalModule):
        _widget_class = AsgWidget
        _gui_attributes = ["waveform",
                           "amplitude",
                           "offset",
                           "frequency",
                           "trigger_source",
                           "output_direct",
                           "start_phase"]
        _setup_attributes = _gui_attributes + ["cycles_per_burst"]

        _DATA_OFFSET = set_DATA_OFFSET
        _VALUE_OFFSET = set_VALUE_OFFSET
        _BIT_OFFSET = set_BIT_OFFSET
        default_output_direct = set_default_output_direct

        # previously 2 ** 16 * (2 ** 14 - 1), was too slow by 2**-16
        # the bottom value is also the fpga default
        _default_counter_wrap = 2 ** 16 * (2 ** 14) - 1

        output_directs = None
        addr_base = 0x40200000

        def __init__(self, parent, name=None):
            super(Asg, self).__init__(parent, name=name)
            self._counter_wrap = self._default_counter_wrap
            self._writtendata = np.zeros(self.data_length)

        @property
        def output_directs(self):
            return all_output_directs(self).keys()

        output_direct = SelectRegister(
            - addr_base + dsp_addr_base('asg0' if _BIT_OFFSET == 0 else 'asg1') + 0x4,
                    options=all_output_directs,
                    doc="selects the direct output of the module")

        data_length = 2 ** 14

        # register set_a_zero
        on = BoolRegister(0x0, 7 + _BIT_OFFSET, doc='turns the output on or off', invert=True)

        # register set_a_rst
        sm_reset = BoolRegister(0x0, 6 + _BIT_OFFSET, doc='resets the state machine')

        # register set_a/b_once
        # deprecated since redpitaya v0.94
        periodic = BoolRegister(0x0, 5 + _BIT_OFFSET, invert=True,
                                doc='if False, fgen stops after performing one full waveform at its last value.')

        # register set_a/b_wrap
        _sm_wrappointer = BoolRegister(0x0, 4 + _BIT_OFFSET,
                                       doc='If False, fgen starts from data[0] value after each cycle. If True, assumes that data is periodic and jumps to the naturally next index after full cycle.')

        # register set_a_rgate
        _counter_wrap = IntRegister(0x8 + _VALUE_OFFSET,
                                    bits=32,
                                    doc="Raw phase value where counter wraps around. To be set to 2**16*(2**14-1) = 0x3FFFFFFF in virtually all cases. ")

        # register trig_a/b_src
        _trigger_sources = OrderedDict([
            ("off", 0 << _BIT_OFFSET),
            ("immediately", 1 << _BIT_OFFSET),
            ("ext_positive_edge", 2 << _BIT_OFFSET),  # DIO0_P pin
            ("ext_negative_edge", 3 << _BIT_OFFSET),  # DIO0_P pin
            ("ext_raw", 4 << _BIT_OFFSET),  # 4- raw DIO0_P pin
            ("high", 5 << _BIT_OFFSET)  # 5 - constant high
            ])
        trigger_sources = _trigger_sources.keys()

        trigger_source = SelectRegister(0x0, bitmask=0x0007 << _BIT_OFFSET,
                                        default='off',
                                        options=_trigger_sources,
                                        doc="trigger source for triggered "
                                            "output",
                                        call_setup=True)

        # offset is stored in bits 31:16 of the register.
        # This adaptation to FloatRegister is a little subtle but should work nonetheless
        _offset_masked = FloatRegister(0x4 + _VALUE_OFFSET, bits=14 + 16, bitmask=0x3FFF << 16,
                                       norm=2 ** 16 * 2 ** 13, doc="output offset [volts]") # masked offset is hidden
                                                                                            # behind AsgOffsetAttribute
                                                                                            # to have the correct
                                                                                            # increments and so on.
        offset = AsgOffsetAttribute(default=0,
                                    increment=1./2**13,
                                    min=-1.,
                                    max=1.,
                                    doc="output offset [volts]")

        # formerly scale
        amplitude = AsgAmplitudeAttribute(0x4 + _VALUE_OFFSET, bits=14, bitmask=0x3FFF,
                                  norm=2.**13, signed=False,
                                  max=1.0,  # Internal fpga max is 2.0 V
                                  # i.e. it is possible to define waveforms
                                  # with smaller values and then boost them,
                                  #  but there is no real interest to do so.
                                  doc="amplitude of output waveform [volts]")

        start_phase = PhaseRegister(0xC + _VALUE_OFFSET, bits=30,
                                    doc="Phase at which to start triggered waveforms [degrees]")

        frequency = FrequencyRegister(0x10 + _VALUE_OFFSET, bits=30,
                                      log_increment=True,
                                      doc="Frequency of the output waveform [Hz]")

        _counter_step = IntRegister(0x10 + _VALUE_OFFSET, doc="""Each clock cycle the counter_step is increases the internal counter modulo counter_wrap.
            The current counter step rightshifted by 16 bits is the index of the value that is chosen from the data table.
            """)

        _start_offset = IntRegister(0xC,
                                    doc="counter offset for trigged events = phase offset ")

        # novel burst / pulsed mode parameters
        cycles_per_burst = IntRegister(0x18 + _VALUE_OFFSET,
                                       doc="Number of repeats of table readout. 0=infinite. 32 "
                                           "bits.")

        bursts = IntRegister(0x1C + _VALUE_OFFSET,
                             doc="Number of bursts (1 burst = 'cycles' periods of "
                                 "waveform + delay_between_bursts. 0=disabled")

        delay_between_bursts = IntRegister(0x20 + _VALUE_OFFSET,
                                           doc="Delay between repetitions [us]. Granularity=1us")

        random_phase = BoolRegister(0x0, 12 + _BIT_OFFSET,
                                    doc='If True, the phase of the asg will be '
                                        'pseudo-random with a period of 2**31-1 '
                                        'cycles. This is used for the generation of '
                                        'white noise. If false, asg behaves '
                                        'normally. ')

        def _noise_distribution(self):
            """
            returns an array of data_length samples of a Gaussian
            distribution with rms=self._rmsamplitude
            """
            if self._rmsamplitude == 0:
                return np.zeros(self.data_length)
            else:
                return np.random.normal(loc=0.0,
                                        scale=self._rmsamplitude,
                                        size=self.data_length)

        @property
        def _noise_V2_per_Hz(self):
            return self._rmsamplitude**2/(125e6*self._frequency_correction/2)

        waveforms = ['sin', 'cos', 'ramp', 'halframp', 'square', 'dc',
                     'noise']

        waveform = WaveformAttribute(waveforms)

        def trig(self):
            self.start_phase = 0
            self.trigger_source = "immediately"
            self.trigger_source = "off"

        @property
        def data(self):
            """array of 2**14 values that define the output waveform.

            Values should lie between -1 and 1 such that the peak output
            amplitude is self.amplitude """
            if not hasattr(self, '_writtendata'):
                self._writtendata = np.zeros(self.data_length, dtype=np.int32)
            x = np.array(self._writtendata, dtype=np.int32)

            # data readback disabled for fpga performance reasons
            # x = np.array(
            #    self._reads(self._DATA_OFFSET, self.data_length),
            #             dtype=np.int32)
            x[x >= 2 ** 13] -= 2 ** 14
            return np.array(x, dtype=float) / 2 ** 13

        @data.setter
        def data(self, data):
            """array of 2**14 values that define the output waveform.

            Values should lie between -1 and 1 such that the peak output
            amplitude is self.amplitude"""
            data = np.array(np.round((2 ** 13 - 1) * data), dtype=np.int32)
            data[data >= 2 ** 13] = 2 ** 13 - 1
            data[data < 0] += 2 ** 14
            # values that are still negativeare set to maximally negative
            data[data < 0] = -2 ** 13
            data = np.array(data, dtype=np.uint32)
            self._writes(self._DATA_OFFSET, data)
            # memorize the data on host PC since we have disabled readback from fpga
            self._writtendata = data

        def _setup(self):
            """
            Sets up the function generator. (just setting attributes is ok).
            """
            self.on = False
            self.sm_reset = True
            self._counter_wrap = self._default_counter_wrap
            self._sm_wrappointer = True
            self.waveform = self.waveform
            self.sm_reset = False
            self.on = True

        # advanced trigger - alpha version functionality
        scopetriggerphase = PhaseRegister(0x114 + _VALUE_OFFSET, bits=14,
                                          doc="phase of ASG ch1 at the moment when the last scope "
                                              "trigger occured [degrees]")

        advanced_trigger_reset = BoolRegister(0x0, 9 + _BIT_OFFSET,
                                              doc='resets the fgen advanced trigger')
        advanced_trigger_autorearm = BoolRegister(0x0, 11 + _BIT_OFFSET,
                                                  doc='autorearm the fgen advanced trigger after a trigger event? If False, trigger needs to be reset with a sequence advanced_trigger_reset=True...advanced_trigger_reset=False after each trigger event.')
        advanced_trigger_invert = BoolRegister(0x0, 10 + _BIT_OFFSET,
                                               doc='inverts the trigger signal for the advanced trigger if True')

        advanced_trigger_delay = LongRegister(0x118 + _VALUE_OFFSET, bits=64,
                                              doc='delay of the advanced trigger - 1 [cycles]')

        def enable_advanced_trigger(self,
                                    frequency,
                                    amplitude,
                                    duration,
                                    invert=False,
                                    autorearm=False,
                                    output_direct='out1'):
            self.advanced_trigger_reset = True
            self.advanced_trigger_autorearm = autorearm
            self.advanced_trigger_invert = invert
            self.advanced_trigger_delay = int(np.round(duration / 8e-9))
            self.setup(
                waveform="sin",
                frequency=frequency,
                amplitude=amplitude,
                offset=0,
                periodic=True,
                trigger_source='advanced_trigger',
                output_direct=output_direct)
            self.advanced_trigger_reset = False

        def disable_advanced_trigger(self):
            self.on = False
            self.advanced_trigger_reset = True
            self.trigger_source = 'immediately'
            self.sm_reset = True

    return Asg


Asg0 = make_asg(channel=0)
Asg1 = make_asg(channel=1)
