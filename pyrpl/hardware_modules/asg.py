from pyrpl.attributes import SelectAttribute, BoolRegister, FloatRegister, SelectRegister, \
                             IntRegister, LongRegister, PhaseRegister, FrequencyRegister, FloatAttribute
from pyrpl.modules import HardwareModule
from pyrpl.module_widgets import AsgWidget
from . import DspModule


import numpy as np


class OutputDirectAttribute(SelectAttribute):
    def get_value(self, instance, owner):
        if instance is None:
            return self
        else:
            return instance._dsp.output_direct

    def set_value(self, instance, val):
        instance._dsp.output_direct = val
        return val


class WaveformAttribute(SelectAttribute):
    def get_value(self, instance, owner):
        return instance._waveform

    def set_value(self, instance, waveform):
        waveform = waveform.lower()
        if not waveform in instance.waveforms:
            raise ValueError("waveform shourd be one of " + instance.waveforms)
        else:
            if not waveform == 'noise':
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
            elif waveform == 'dc':
                y = np.zeros(instance.data_length)
            elif waveform == 'noise':
                instance._rmsamplitude = instance.amplitude
                y = np.random.normal(loc=0.0, scale=instance._rmsamplitude,
                                     size=instance.data_length)
                instance.amplitude = 1.0  # this may be confusing to the user..
                instance.random_phase = True
            else:
                y = instance.data
                instance._logger.error(
                    "Waveform name %s not recognized. Specify waveform manually" % waveform)
            instance.data = y
            instance._waveform = waveform
        return waveform


class AsgOffsetAttribute(FloatAttribute):
    def __init__(self):
        super(AsgOffsetAttribute, self).__init__(default=0,
                                                 increment=1./2**13,
                                                 min=-1.,
                                                 max=1.,
                                                 doc="output offset [volts]")

    def set_value(self, instance, val):
        instance._offset_masked = val
        return val

    def get_value(self, instance, owner):
        return instance._offset_masked


# ugly workaround, but realized too late that descriptors have this limit
def make_asg(channel=1):
    if channel == 1:
        set_BIT_OFFSET = 0
        set_VALUE_OFFSET = 0x00
        set_DATA_OFFSET = 0x10000
        set_default_output_direct = 'off'
        set_name = 'asg1'
    else:
        set_DATA_OFFSET = 0x20000
        set_VALUE_OFFSET = 0x20
        set_BIT_OFFSET = 16
        set_default_output_direct = 'off'
        set_name = 'asg2'

    class Asg(HardwareModule):
        widget_class = AsgWidget
        gui_attributes = ["waveform",
                          "amplitude",
                          "offset",
                          "frequency",
                          "trigger_source",
                          "output_direct"]
        setup_attributes = gui_attributes

        _DATA_OFFSET = set_DATA_OFFSET
        _VALUE_OFFSET = set_VALUE_OFFSET
        _BIT_OFFSET = set_BIT_OFFSET
        default_output_direct = set_default_output_direct
        output_directs = None
        name = set_name

        def __init__(self, client, name, parent):
            super(Asg, self).__init__(client,
                                      addr_base=0x40200000,
                                      parent=parent,
                                      name=name)
            self._counter_wrap = 0x3FFFFFFF  # correct value unless you know better
            self._writtendata = np.zeros(self.data_length)
            if self._BIT_OFFSET == 0:
                self._dsp = DspModule(client, name='asg1', parent=parent)
            else:
                self._dsp = DspModule(client, name='asg2', parent=parent)
            self.output_directs = self._dsp.output_directs
            self.waveform = 'sin'
            self.trigger_source = 'immediately'
            self.output_direct = self.default_output_direct

        output_direct = OutputDirectAttribute(DspModule._output_directs)

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
                                    doc="Raw phase value where counter wraps around. To be set to 2**16*(2**14-1) = 0x3FFFFFFF in virtually all cases. ")

        # register trig_a/b_src
        _trigger_sources = {"off": 0 << _BIT_OFFSET,
                            "immediately": 1 << _BIT_OFFSET,
                            "ext_positive_edge": 2 << _BIT_OFFSET,  # DIO0_P pin
                            "ext_negative_edge": 3 << _BIT_OFFSET,  # DIO0_P pin
                            "ext_raw": 4 << _BIT_OFFSET,  # 4- raw DIO0_P pin
                            "high": 5 << _BIT_OFFSET}  # 5 - constant high

        trigger_sources = _trigger_sources.keys()

        trigger_source = SelectRegister(0x0, bitmask=0x0007 << _BIT_OFFSET,
                                        options=_trigger_sources,
                                        doc="trigger source for triggered output")

        # offset is stored in bits 31:16 of the register.
        # This adaptation to FloatRegister is a little subtle but should work nonetheless
        _offset_masked = FloatRegister(0x4 + _VALUE_OFFSET, bits=14 + 16, bitmask=0x3FFF << 16,
                                       norm=2 ** 16 * 2 ** 13, doc="output offset [volts]") # masked offset is hidden
                                                                                            # behind AsgOffsetAttribute
                                                                                            # to have the correct
                                                                                            # increments and so on.
        offset = AsgOffsetAttribute()

        # formerly scale
        amplitude = FloatRegister(0x4 + _VALUE_OFFSET, bits=14, bitmask=0x3FFF,
                                  norm=2.**13, signed=False,
                                  doc="amplitude of output waveform [volts]")
        """FloatRegister(0x4 + _VALUE_OFFSET, bits=14, bitmask=0x3FFF,
                                  norm=2 ** 13, signed=False,
                                  doc="amplitude of output waveform [volts]")"""

        start_phase = PhaseRegister(0xC + _VALUE_OFFSET, bits=30,
                                    doc="Phase at which to start triggered waveforms [degrees]")

        frequency = FrequencyRegister(0x10 + _VALUE_OFFSET, bits=30,
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
                                        'white noise. If false, asg behaves normally. ')

        waveforms = ['sin', 'cos', 'ramp', 'halframp', 'dc', 'noise']

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
            return np.array(x, dtype=np.float) / 2 ** 13

        @data.setter
        def data(self, data):
            """array of 2**14 values that define the output waveform.

            Values should lie between -1 and 1 such that the peak output
            amplitude is self.amplitude"""
            data = np.array(np.round((2 ** 13 - 1) * data), dtype=np.int32)
            data[data >= 2 ** 13] = 2 ** 13 - 1
            data[data < 0] += 2 ** 14
            # values that are still negativeare set to maximally negatuve
            data[data < 0] = -2 ** 13
            data = np.array(data, dtype=np.uint32)
            self._writes(self._DATA_OFFSET, data)
            # memorize the data on host PC since we have disabled readback from fpga
            self._writtendata = data

        def setup(self,
                  waveform=None,
                  frequency=None,
                  amplitude=None,
                  offset=None,
                  start_phase=0,
                  trigger_source=None,
                  output_direct=None,
                  cycles_per_burst=None,
                  bursts=None,
                  delay_between_bursts=None):
            """
            Sets up the function generator.

            Parameters
            ----------
            waveform: str
                must be one of ['sin', cos', 'ramp', 'DC', 'halframp']
            frequency: float
                waveform frequency in Hz.
            amplitude: float
                amplitude of the waveform in Volts. Between 0 and 1.
            offset: float
            start_phase: float
                the phase of the waveform where the function generator starts.
            trigger_source: str
                must be one of self.trigger_sources
            output_direct: str
                must be one of self.outputs_direct
            cycles_per_burst: int
                number of repetitions of the waveform per burst. 0 = infinite.
                by default, only 1 burst is executed. Maximum 2**32-1.
            bursts: int
                number of bursts to output - 1, i.e. 0 = one burst sequence.
                Each burst consists of cycles_per_burst full periods of the
                waveform and a delay of delay_between_bursts. If delay=0, any
                setting of bursts other than zero outputs infinitely many
                cycles. That is, if you do not want a delay, leave bursts=0
                and define the number of periods to output with
                cycles_per_burst. Maximum 2**16-1
            delay_between_bursts: int
                delay between bursts in multiples of 1 microseconds. Maximum
                2**32-1 us.

            Returns
            -------
            None
            """

            if waveform is None:
                waveform = self.waveform
            if frequency is None:
                frequency = self.frequency
            if amplitude is None:
                amplitude = self.amplitude
            if offset is None:
                offset = self.offset
            if trigger_source is None:
                trigger_source = self.trigger_source
            if output_direct is None:
                output_direct = self.output_direct
            if cycles_per_burst is None:
                cycles_per_burst = self.cycles_per_burst
            if bursts is None:
                bursts = self.bursts
            if delay_between_bursts is None:
                delay_between_bursts = self.delay_between_bursts

            self.on = False
            self.sm_reset = True
            self.trigger_source = 'off'
            self.amplitude = amplitude
            self.offset = offset
            self.output_direct = output_direct
            self.waveform = waveform
            self.start_phase = start_phase
            self._counter_wrap = 2 ** 16 * (
            2 ** 14) - 1  # Bug found on 2016/11/2 (Samuel) previously 2**16 * (2**14 - 1)
            # ===> asg frequency was too fast by 1./2**16
            self.frequency = frequency
            self._sm_wrappointer = True
            self.cycles_per_burst = cycles_per_burst
            self.bursts = bursts
            self.delay_between_bursts = delay_between_bursts
            self.sm_reset = False
            self.on = True
            if trigger_source is not None:
                self.trigger_source = trigger_source

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


Asg1 = make_asg(channel=1)
Asg2 = make_asg(channel=2)
