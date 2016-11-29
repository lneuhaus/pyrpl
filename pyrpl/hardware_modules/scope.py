from ..errors import NotReadyError, TimeoutError
from ..attributes import FloatAttribute, SelectAttribute, BoolRegister, \
    FloatRegister, SelectRegister, \
                             StringProperty, IntRegister, LongRegister
from ..modules import HardwareModule
from ..widgets.module_widgets import ScopeWidget

from . import DSP_INPUTS, DspModule, DspInputAttribute

import numpy as np
import time

# data_length must be defined outside of class body for python 3
# compatibility since otherwise it is not available in the class level
# namespace
data_length = 2 ** 14


class TriggerDelay(FloatAttribute):
    # def __init__(self, attr_name, doc=""):
    #   super(TriggerDelay, self).__init__(attr_name, 0.001, doc=doc)

    def get_value(self, obj, obj_type):
        if obj is None:
            return self
        return (obj._trigger_delay - obj.data_length // 2) * obj.sampling_time

    def set_value(self, obj, delay):
        # memorize the setting
        obj._trigger_delay_memory = delay
        # convert float delay into counts
        delay = int(np.round(delay / obj.sampling_time)) + obj.data_length // 2
        # in mode "immediately", trace goes from 0 to duration,
        # but trigger_delay_memory is not overwritten
        if obj.trigger_source == 'immediately':
            obj._trigger_delay = obj.data_length
            return delay
        if delay <= 0:
            delay = 1  # bug in scope code: 0 does not work
        elif delay > 2 ** 32 - 1:  # self.data_length-1:
            delay = 2 ** 32 - 1  # self.data_length-1
        obj._trigger_delay = delay
        return delay


class DurationAttribute(SelectAttribute):
    def get_value(self, instance, owner):
        if instance is None:
            return self
        return instance.sampling_time * float(instance.data_length)

    def set_value(self, instance, value):
        """sets returns the duration of a full scope sequence
        the rounding makes sure that the actual value is longer or equal to the set value"""
        value = float(value) / instance.data_length
        tbase = 8e-9
        for d in instance.decimations:
            if value <= tbase * float(d):
                instance.decimation = d
                return
        instance.decimation = max(instance.decimations)
        instance._logger.error("Desired duration too long to realize")


class DecimationRegister(SelectRegister):
    """
    Carreful: changing decimation changes duration and sampling_time as well
    """
    def set_value(self, instance, value):
        super(DecimationRegister, self).set_value(instance, value)
        instance.__class__.duration.set_value_gui_config(instance, instance.duration)
        instance.__class__.sampling_time.set_value_gui_config(instance, instance.sampling_time)


class SamplingTimeAttribute(SelectAttribute):
    def get_value(self, instance, owner):
        if instance is None:
            return self
        return 8e-9 * float(instance.decimation)

    def set_value(self, instance, value):
        """sets or returns the time separation between two subsequent points of a scope trace
        the rounding makes sure that the actual value is shorter or equal to the set value"""
        tbase = 8e-9
        for d in reversed(instance.decimations):
            if value >= tbase * d:
                instance.decimation = d
                return
        instance.decimation = min(instance.decimations)
        self._logger.error("Desired sampling time impossible to realize")


class TriggerSourceAttribute(SelectAttribute):
    def get_value(self, instance, owner):
        if instance is None:
            return self
        if hasattr(instance, "_trigger_source_memory"):
            return instance._trigger_source_memory
        else:
            instance._trigger_source_memory = instance._trigger_source
            return instance._trigger_source_memory

    def set_value(self, instance, value):
        # if isinstance(value, HardwareModule):
        #   value = value.name
        instance._trigger_source = value
        if instance._trigger_source_memory != value:
            instance._trigger_source_memory = value
            # passing between immediately and other sources possibly requires trigger delay change
            instance.trigger_delay = instance._trigger_delay_memory


class DspInputAttributeScope(DspInputAttribute):
    """
    Same as DspInput, except that it sets the value to instance._ch[index].input instead of instance.input
    """
    def __init__(self, ch=1, doc=""):
        options = DSP_INPUTS.keys()
        super(DspInputAttributeScope, self).__init__(options=options, doc=doc)
        self.ch = ch

    def get_value(self, instance, owner):
        if instance is None:
            return self
        ch = getattr(instance, '_ch' + str(self.ch))
        return ch.input

    def set_value(self, instance, value):
        ch = getattr(instance, '_ch' + str(self.ch))
        setattr(ch, 'input', value)
        return value


class Scope(HardwareModule):
    name = 'scope'
    addr_base = 0x40100000
    widget_class = ScopeWidget
    gui_attributes = ["input1",
                      "input2",
                      "duration",
                      "average",
                      "trigger_source",
                      "trigger_delay",
                      "threshold_ch1",
                      "threshold_ch2",
                      "curve_name"]
    setup_attributes = gui_attributes
    name = 'scope'
    data_length = data_length  # see definition and explanation above
    inputs = None

    def init_module(self):
        # dsp multiplexer channels for scope and asg are the same by default
        self._ch1 = DspModule(self._rp, name='asg1')
        self._ch2 = DspModule(self._rp, name='asg2')
        self.inputs = self._ch1.inputs
        self._setup_called = False
        self._trigger_source_memory = "immediately"
        self._trigger_delay_memory = 0

    input1 = DspInputAttributeScope(1)
    input2 = DspInputAttributeScope(2)

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
                        "ext_positive_edge": 6,  # DIO0_P pin
                        "ext_negative_edge": 7,  # DIO0_P pin
                        "asg1": 8,
                        "asg2": 9}

    curve_name = StringProperty('curve_name')

    trigger_sources = sorted(_trigger_sources.keys())  # help for the user

    _trigger_source = SelectRegister(0x4, doc="Trigger source",
                                     options=_trigger_sources)

    def set_state(self, dic):
        super(Scope, self).set_state(dic)
        self.setup()

    trigger_source = TriggerSourceAttribute(_trigger_sources.keys())

    _trigger_debounce = IntRegister(0x90, doc="Trigger debounce time [cycles]")

    trigger_debounce = FloatRegister(0x90, bits=20, norm=125e6,
                                     doc="Trigger debounce time [s]")

    threshold_ch1 = FloatRegister(0x8, bits=14, norm=2 ** 13,
                                  doc="ch1 trigger threshold [volts]")

    threshold_ch2 = FloatRegister(0xC, bits=14, norm=2 ** 13,
                                  doc="ch1 trigger threshold [volts]")

    _trigger_delay = IntRegister(0x10,
                                 doc="number of decimated data after trigger "
                                     "written into memory [samples]")

    trigger_delay = TriggerDelay("trigger_delay", min=-10, max=8e-9*2**30, doc="delay between trigger and acquisition start.\n"
                                                      "negative values down to -duration are allowed for pretrigger")

    _trigger_delay_running = BoolRegister(0x0, 2,
                                          doc="trigger delay running (register adc_dly_do)")

    _adc_we_keep = BoolRegister(0x0, 3,
                                doc="Scope resets trigger automatically (adc_we_keep)")

    _adc_we_cnt = IntRegister(0x2C, doc="Number of samles that have passed since "
                                        "trigger was armed (adc_we_cnt)")

    current_timestamp = LongRegister(0x15C,
                                     bits=64,
                                     doc="An absolute counter " \
                                         + "for the time [cycles]")

    trigger_timestamp = LongRegister(0x164,
                                     bits=64,
                                     doc="An absolute counter " \
                                         + "for the trigger time [cycles]")

    _decimations = {2 ** n: 2 ** n for n in range(0, 17)}

    decimations = sorted(_decimations.keys())  # help for the user

    sampling_times = [8e-9 * dec for dec in decimations]

    # price to pay for Python 3 compatibility: list comprehension workaround
    # cf. http://stackoverflow.com/questions/13905741/accessing-class-variables-from-a-list-comprehension-in-the-class-definition
    durations = [st * data_length for st in sampling_times]

    decimation = DecimationRegister(0x14, doc="decimation factor", # customized to update duration and sampling_time
                                options=_decimations)

    _write_pointer_current = IntRegister(0x18,
                                         doc="current write pointer position [samples]")

    _write_pointer_trigger = IntRegister(0x1C,
                                         doc="write pointer when trigger arrived [samples]")

    hysteresis_ch1 = FloatRegister(0x20, bits=14, norm=2 ** 13,
                                   doc="hysteresis for ch1 trigger [volts]")

    hysteresis_ch2 = FloatRegister(0x24, bits=14, norm=2 ** 13,
                                   doc="hysteresis for ch2 trigger [volts]")

    average = BoolRegister(0x28, 0,
                           doc="Enables averaging during decimation if set to True")

    # equalization filter not implemented here

    voltage1 = FloatRegister(0x154, bits=14, norm=2 ** 13,
                             doc="ADC1 current value [volts]")

    voltage2 = FloatRegister(0x158, bits=14, norm=2 ** 13,
                             doc="ADC2 current value [volts]")

    dac1 = FloatRegister(0x164, bits=14, norm=2 ** 13,
                         doc="DAC1 current value [volts]")

    dac2 = FloatRegister(0x168, bits=14, norm=2 ** 13,
                         doc="DAC2 current value [volts]")

    ch1_firstpoint = FloatRegister(0x10000, bits=14, norm=2 ** 13,
                                   doc="1 sample of ch1 data [volts]")

    ch2_firstpoint = FloatRegister(0x20000, bits=14, norm=2 ** 13,
                                   doc="1 sample of ch2 data [volts]")

    pretrig_ok = BoolRegister(0x16c, 0,
                              doc="True if enough data have been acquired to fill " + \
                                  "the pretrig buffer")

    sampling_time = SamplingTimeAttribute(options=sampling_times)

    duration = DurationAttribute(durations)

    def ownership_changed(self, old, new):
        """
        If the scope was in continuous mode when slaved, it has to stop!!
        """

        if new is not None:
            if self.widget is not None:
                self.widget.stop()

    @property
    def _rawdata_ch1(self):
        """raw data from ch1"""
        # return np.array([self.to_pyint(v) for v in self._reads(0x10000,
        # self.data_length)],dtype=np.int32)
        x = np.array(self._reads(0x10000, self.data_length), dtype=np.int16)
        x[x >= 2 ** 13] -= 2 ** 14
        return x

    @property
    def _rawdata_ch2(self):
        """raw data from ch2"""
        # return np.array([self.to_pyint(v) for v in self._reads(0x20000,
        # self.data_length)],dtype=np.int32)
        x = np.array(self._reads(0x20000, self.data_length), dtype=np.int16)
        x[x >= 2 ** 13] -= 2 ** 14
        return x

    @property
    def _data_ch1(self):
        """ acquired (normalized) data from ch1"""
        return np.array(
            np.roll(self._rawdata_ch1, -(self._write_pointer_trigger + self._trigger_delay + 1)),
            dtype=np.float) / 2 ** 13

    @property
    def _data_ch2(self):
        """ acquired (normalized) data from ch2"""
        return np.array(
            np.roll(self._rawdata_ch2, -(self._write_pointer_trigger + self._trigger_delay + 1)),
            dtype=np.float) / 2 ** 13

    @property
    def _data_ch1_current(self):
        """ (unnormalized) data from ch1 while acquisition is still running"""
        return np.array(
            np.roll(self._rawdata_ch1, -(self._write_pointer_current + 1)),
            dtype=np.float) / 2 ** 13

    @property
    def _data_ch2_current(self):
        """ (unnormalized) data from ch2 while acquisition is still running"""
        return np.array(
            np.roll(self._rawdata_ch2, -(self._write_pointer_current + 1)),
            dtype=np.float) / 2 ** 13

    @property
    def times(self):
        # duration = 8e-9*self.decimation*self.data_length
        # endtime = duration*
        duration = self.duration
        trigger_delay = self.trigger_delay
        return np.linspace(trigger_delay - duration / 2.,
                           trigger_delay + duration / 2.,
                           self.data_length, endpoint=False)

    def _setup(self):
        """
        sets up the scope for a new trace acquisition including arming the trigger.
        In case trigger_source is set to "immediately", trigger_delay is disregarded and
        trace starts at t=0
        """
        self._setup_called = True
        self._reset_writestate_machine = True
        # trigger logic - set source
        self.trigger_source = self.trigger_source
        # arm trigger
        self._trigger_armed = True
        # mode 'immediately' must receive software trigger after arming to
        # start acquisition. The software trigger must occur after
        # pretrig_ok, but we do not need to worry about this because it is
        # taken care of in the trigger_source setter in this class (the
        # trigger_delay section of it).
        if self.trigger_source == 'immediately':
            # self.wait_for_pretrig_ok()
            self.trigger_source = self.trigger_source

    def setup_old(self,
              duration=None,
              trigger_source=None,
              average=None,
              threshold_ch1=None, # for consistency between setup function and setup_attributes
              threshold_ch2=None, # I don't use a single threshold
              hysteresis=None,
              trigger_delay=None,
              input1=None,
              input2=None):
        """sets up the scope for a new trace acquisition including arming the trigger

        duration: the minimum duration in seconds to be recorded
        trigger_source: the trigger source. see the options for the parameter separately
        average: use averaging or not when sampling is not performed at full rate.
                 similar to high-resolution mode in commercial scopes
        threshold: Trigger threshold in V
        hysteresis: signal hysteresis needed to enable trigger in V.
                    Should be larger than the rms-noise of the signal
        trigger_delay: trigger_delay in s
        input1/2: set the inputs of channel 1/2

        if a parameter is None, the current attribute value is used

        In case trigger_source is set to "immediately", trigger_delay is disregarded and
        trace starts at t=0
        """

        self._setup_called = True
        self._reset_writestate_machine = True
        if average is not None:
            self.average = average
        if duration is not None:
            self.duration = duration
        if threshold_ch1 is not None:
            self.threshold_ch1 = threshold_ch1
        if threshold_ch2 is not None:
            self.threshold_ch2 = threshold_ch2
        if hysteresis is not None:
            self.hysteresis_ch1 = hysteresis
            self.hysteresis_ch2 = hysteresis
        if input1 is not None:
            self.input1 = input1
        if input2 is not None:
            self.input2 = input2
        if trigger_delay is not None:
            self.trigger_delay = trigger_delay

        # trigger logic - set source
        if trigger_source is None:
            self.trigger_source = self.trigger_source
        else:
            self.trigger_source = trigger_source
        # arm trigger
        self._trigger_armed = True
        # mode 'immediately' must receive software trigger after arming to
        # start acquisition. The software trigger must occur after
        # pretrig_ok, but we do not need to worry about this because it is
        # taken care of in the trigger_source setter in this class (the
        # trigger_delay section of it).
        if self.trigger_source == 'immediately':
            # self.wait_for_pretrig_ok()
            self.trigger_source = self.trigger_source

            # if self.trigger_source == 'immediately':
            #    self.wait_for_pretrig_ok()
            #    self.trigger_source = 'immediately'# write state machine

    def wait_for_pretrigger(self):
        """ sleeps until scope trigger is ready (buffer has enough new data) """
        while not self.pretrig_ok:
            time.sleep(0.001)

    def curve_ready(self):
        """
        Returns True if new data is ready for transfer
        """
        return (not self._trigger_armed) \
               and (not self._trigger_delay_running) \
               and self._setup_called

    def _get_ch(self, ch):
        if not ch in [1, 2]:
            raise ValueError("channel should be 1 or 2, got " + str(ch))
        return self._data_ch1 if ch == 1 else self._data_ch2

    def _get_ch_no_roll(self, ch):
        if not ch in [1, 2]:
            raise ValueError("channel should be 1 or 2, got " + str(ch))
        return self._rawdata_ch1 * 1. / 2 ** 13 if ch == 1 else self._rawdata_ch2 * 1. / 2 ** 13

    def curve(self, ch=1, timeout=1.):
        """
        Takes a curve from channel ch:
            If timeout>0: runs until data is ready or timeout expires
            If timeout<=0: returns immediately the current buffer without
            checking for trigger status.
        """
        if not self._setup_called:
            raise NotReadyError("setup has never been called")
        SLEEP_TIME = 0.001
        total_sleep = 0
        if timeout > 0:
            while (total_sleep < timeout):
                if self.curve_ready():
                    return self._get_ch(ch)
                total_sleep += SLEEP_TIME
                time.sleep(SLEEP_TIME)
            raise TimeoutError("Scope wasn't trigged during timeout")
        else:
            return self._get_ch(ch)

    ### unfunctional so far
    def spectrum(self,
                 center,
                 span,
                 avg,
                 input="adc1",
                 window="flattop",
                 acbandwidth=50.0,
                 iq='iq2'):
        points_per_bw = 10
        iq_module = self.configure_signal_chain(input, iq)
        iq_module.frequency = center
        bw = span * points_per_bw / self.data_length
        self.duration = 1. / bw
        self._rp.iq2.bandwidth = [span, span]
        self.setup(trigger_source='immediately',
                   average=False,
                   trigger_delay=0)
        y = self.curve()
        return y

    def configure_signal_chain(self, input, iq):
        iq_module = getattr(self._rp, iq)
        iq_module.input = input
        iq_module.output_signal = 'quadrature'
        iq_module.quadrature_factor = 1.0
        self.input1 = iq
        return iq_module
