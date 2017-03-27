import time

from pyrpl.acquisition_module import AcquisitionModule
from . import DSP_INPUTS, DspModule, DspInputAttribute
from ..async_utils import MainThreadTimer, PyrplFuture
from ..module_attributes import *
from ..modules import HardwareModule
from ..pyrpl_utils import time
from ..widgets.module_widgets import ScopeWidget

logger = logging.getLogger(name=__name__)


data_length = 2**14

class DurationAttribute(SelectAttribute):
    def get_value(self, instance, owner):
        if instance is None:
            return self
        return instance.sampling_time * float(instance.data_length)

    def validate_and_normalize(self, value, module):
        # gets next value, to be replaced with next-higher value
        value = float(value)
        return min([opt for opt in self.options(module)],
                   key=lambda x: abs(x - value))

    def set_value(self, instance, value):
        """sets returns the duration of a full scope sequence the rounding
        makes sure that the actual value is longer or equal to the set value"""
        instance.sampling_time = float(value) / instance.data_length


class DecimationRegister(SelectRegister):
    """
    Carreful: changing decimation changes duration and sampling_time as well
    """

    def set_value(self, instance, value):
        super(DecimationRegister, self).set_value(instance, value)
        instance.__class__.duration.value_updated(instance, instance.duration)
        instance.__class__.sampling_time.value_updated(instance,
                                                       instance.sampling_time)
        # instance.setup()
        # instance._decimation_changed() # acquisition_manager needs to be
        # warned because that could have changed _is_rolling_mode_active()


class SamplingTimeAttribute(SelectAttribute):
    def get_value(self, instance, owner):
        if instance is None:
            return self
        return 8e-9 * float(instance.decimation)

    def validate_and_normalize(self, value, module):
        # gets next value, to be replaced with next-lower value
        value = float(value)
        return min([opt for opt in self.options(module)],
                   key=lambda x: abs(x - value))

    def set_value(self, instance, value):
        """sets or returns the time separation between two subsequent
        points of a scope trace the rounding makes sure that the actual
        value is shorter or equal to the set value"""
        instance.decimation = float(value) / 8e-9


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
            # passing between immediately and other sources possibly
            # requires trigger delay change
            instance.trigger_delay = instance._trigger_delay_memory


class TriggerDelayAttribute(FloatAttribute):
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


class DspInputAttributeScope(DspInputAttribute):
    """
    Same as DspInput, except that it sets the value to instance._ch[
    index].input instead of instance.input
    """

    def __init__(self, ch=1, **kwds):
        super(DspInputAttributeScope, self).__init__(**kwds)
        self.register = '_ch%d.input'


class ContinuousRollingFuture(PyrplFuture):
    DELAY_ROLLING_MODE_MS = 20
    current_avg = 1  # no averaging in rolling mode

    def __init__(self, module):
        super(ContinuousRollingFuture, self).__init__()
        self._module = module
        self._timer = MainThreadTimer(self.DELAY_ROLLING_MODE_MS)
        self._timer.timeout.connect(self._get_rolling_curve)

    def _get_rolling_curve(self):
        if not self._module._is_rolling_mode_active():
            return
        if not self._module.running_state == "running_continuous":
            return
        data_x, datas = self._module._get_rolling_curve()
        # no setup in rolling mode
        self._module._emit_signal_by_name('display_curve', [data_x,
                                                            datas])
        self.data_avg = datas
        self.data_x = data_x
        self._timer.start()  # restart timer in rolling_mode

    def start(self):
        self._module._start_acquisition_rolling_mode()
        # rolling_mode requires to disable the trigger
        self._timer.start()

    def pause(self):
        self._timer.stop()

    def _set_run_continuous(self):
        """
        Dummy function: ContinuousRollingFuture instance is always
        "_run_continuous"
        """
        pass

class Scope(HardwareModule, AcquisitionModule):
    addr_base = 0x40100000
    name = 'scope'
    _widget_class = ScopeWidget
    # run = ModuleProperty(ScopeAcquisitionManager)
    _gui_attributes = ["input1",
                       "input2",
                       "duration",
                       "average",
                       "trigger_source",
                       "trigger_delay",
                       "threshold_ch1",
                       "threshold_ch2",
                       "ch1_active",
                       "ch2_active"]  # running_state last for proper
    # acquisition setup
    _setup_attributes = _gui_attributes + ["rolling_mode", "running_state"]
    # changing these resets the acquisition and autoscale (calls setup())
    # _callback_attributes = ["rolling_mode", "decimation", "trigger_delay"]

    data_length = data_length  # to use it in a list comprehension

    rolling_mode = BoolProperty(doc="In rolling mode, the curve is "
                                    "continuously acquired and "
                                    "translated from the right to the "
                                    "left of the screen while new "
                                    "data arrive.",
                                call_setup=True)

    inputs = None
    input1 = DspInputAttributeScope(1)
    input2 = DspInputAttributeScope(2)

    _reset_writestate_machine = BoolRegister(0x0, 1,
                                             doc="Set to True to reset "
                                                 "writestate machine. "
                                                 "Automatically goes back "
                                                 "to false.")

    _trigger_armed = BoolRegister(0x0, 0, doc="Set to True to arm trigger")

    _trigger_sources = {"off": 0,
                        "immediately": 1,
                        "ch1_positive_edge": 2,
                        "ch1_negative_edge": 3,
                        "ch2_positive_edge": 4,
                        "ch2_negative_edge": 5,
                        "ext_positive_edge": 6,  # DIO0_P pin
                        "ext_negative_edge": 7,  # DIO0_P pin
                        "asg0": 8,
                        "asg1": 9,
                        "dsp": 10} #dsp trig module trigger

    trigger_sources = sorted(_trigger_sources.keys())  # help for the user

    _trigger_source = SelectRegister(0x4, doc="Trigger source",
                                     options=_trigger_sources)

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

    trigger_delay = TriggerDelayAttribute("trigger_delay",
                                          min=-10,
                                          max=8e-9 * 2 ** 30,
                                          doc="delay between trigger and "
                                              "acquisition start.\n"
                                              "negative values down to "
                                              "-duration are allowed for "
                                              "pretrigger",
                                          call_setup=True)

    _trigger_delay_running = BoolRegister(0x0, 2,
                                          doc="trigger delay running ("
                                              "register adc_dly_do)")

    _adc_we_keep = BoolRegister(0x0, 3,
                                doc="Scope resets trigger automatically ("
                                    "adc_we_keep)")

    _adc_we_cnt = IntRegister(0x2C, doc="Number of samles that have passed "
                                        "since trigger was armed (adc_we_cnt)")

    current_timestamp = LongRegister(0x15C,
                                     bits=64,
                                     doc="An absolute counter "
                                         + "for the time [cycles]")

    trigger_timestamp = LongRegister(0x164,
                                     bits=64,
                                     doc="An absolute counter "
                                         + "for the trigger time [cycles]")

    _decimations = {2 ** n: 2 ** n for n in range(0, 17)}

    decimations = sorted(_decimations.keys())  # help for the user

    sampling_times = [8e-9 * dec for dec in decimations]

    # price to pay for Python 3 compatibility: list comprehension workaround
    # cf. http://stackoverflow.com/questions/13905741
    durations = [st * data_length for st in sampling_times]

    decimation = DecimationRegister(0x14, doc="decimation factor",
                                    # customized to update duration and
                                    # sampling_time
                                    options=_decimations,
                                    call_setup=True)

    _write_pointer_current = IntRegister(0x18,
                                         doc="current write pointer "
                                             "position [samples]")

    _write_pointer_trigger = IntRegister(0x1C,
                                         doc="write pointer when trigger "
                                             "arrived [samples]")

    hysteresis_ch1 = FloatRegister(0x20, bits=14, norm=2 ** 13,
                                   doc="hysteresis for ch1 trigger [volts]")

    hysteresis_ch2 = FloatRegister(0x24, bits=14, norm=2 ** 13,
                                   doc="hysteresis for ch2 trigger [volts]")

    average = BoolRegister(0x28, 0,
                           doc="Enables averaging during decimation if set "
                               "to True")

    # equalization filter not implemented here

    voltage_in1 = FloatRegister(0x154, bits=14, norm=2 ** 13,
                                doc="in1 current value [volts]")

    voltage_in2 = FloatRegister(0x158, bits=14, norm=2 ** 13,
                                doc="in2 current value [volts]")

    voltage_out1 = FloatRegister(0x164, bits=14, norm=2 ** 13,
                                 doc="out1 current value [volts]")

    voltage_out2 = FloatRegister(0x168, bits=14, norm=2 ** 13,
                                 doc="out2 current value [volts]")

    ch1_firstpoint = FloatRegister(0x10000, bits=14, norm=2 ** 13,
                                   doc="1 sample of ch1 data [volts]")

    ch2_firstpoint = FloatRegister(0x20000, bits=14, norm=2 ** 13,
                                   doc="1 sample of ch2 data [volts]")

    pretrig_ok = BoolRegister(0x16c, 0,
                              doc="True if enough data have been acquired "
                                  "to fill the pretrig buffer")

    sampling_time = SamplingTimeAttribute(options=sampling_times)

    duration = DurationAttribute(durations)

    ch1_active = BoolProperty(default=True,
                              doc="should ch1 be displayed in the gui?")

    ch2_active = BoolProperty(default=True,
                              doc="should ch2 be displayed in the gui?")

    def _init_module(self):
        # dsp multiplexer channels for scope and asg are the same by default
        self._ch1 = DspModule(self._rp, name='asg0')  # the scope inputs and
        #  asg outputs have the same id
        self._ch2 = DspModule(self._rp, name='asg1')  # check fpga code
        # dsp_modules to understand
        self.inputs = self._ch1.inputs
        self._setup_called = False
        self._trigger_source_memory = 'off'  # "immediately" #fixes bug with
        # trigger_delay for 'immediate' at startup
        self._trigger_delay_memory = 0

        super(Scope, self)._init_module()  # _init_module of AcquisitionModule



    def _ownership_changed(self, old, new):
        """
        If the scope was in continuous mode when slaved, it has to stop!!
        """
        if new is not None:
            self.stop()

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
            np.roll(self._rawdata_ch1, - (self._write_pointer_trigger +
                                          self._trigger_delay + 1)),
            dtype=np.float) / 2 ** 13

    @property
    def _data_ch2(self):
        """ acquired (normalized) data from ch2"""
        return np.array(
            np.roll(self._rawdata_ch2, - (self._write_pointer_trigger +
                                          self._trigger_delay + 1)),
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

    def wait_for_pretrigger(self):
        """ sleeps until scope trigger is ready (buffer has enough new data)"""
        while not self.pretrig_ok:
            time.sleep(0.001)

    def curve_ready(self):
        """
        Returns True if new data is ready for transfer
        """
        return (not self._trigger_armed) and \
               (not self._trigger_delay_running) and self._setup_called

    def _curve_acquiring(self):
        """
        Returns True if data is in the process of being acquired
        """
        return (self._trigger_armed or self._trigger_delay_running) \
            and self._setup_called

    def _get_ch(self, ch):
        if ch not in [1, 2]:
            raise ValueError("channel should be 1 or 2, got " + str(ch))
        return self._data_ch1 if ch == 1 else self._data_ch2

    # Concrete implementation of AcquisitionModule methods
    # ----------------------------------------------------

    @property
    def data_x(self):
        return self.times

    def _get_curve(self):
        """
        Simply pack together channel 1 and channel 2 curves in a numpy array
        """
        return np.array((self._get_ch(1), self._get_ch(2)))

    def _remaining_time(self):
        """
        :returns curve duration - ellapsed duration since last setup() call.
        """
        return self.duration - (time() - self._last_time_setup)

    def _data_ready(self):
        """
        :return: True if curve is ready in the hardware, False otherwise.
        """
        return self.curve_ready()

    def _start_acquisition(self):
        autosave_backup = self._autosave_active
        self._autosave_active = False  # Don't save anything in config file
        # during setup!! # maybe even better in
        # BaseModule ??
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
        self._autosave_active = autosave_backup
        self._last_time_setup = time()

    # Rolling_mode related methods:
    # -----------------------------

    def _rolling_mode_allowed(self):
        """
        Only if duration larger than 0.1 s
        """
        return self.duration > 0.1

    def _is_rolling_mode_active(self):
        """
        Rolling_mode property evaluates to True and duration larger than 0.1 s
        """
        return self.rolling_mode and self._rolling_mode_allowed()

    def _get_ch_no_roll(self, ch):
        if ch not in [1, 2]:
            raise ValueError("channel should be 1 or 2, got " + str(ch))
        return self._rawdata_ch1 * 1. / 2 ** 13 if ch == 1 else \
            self._rawdata_ch2 * 1. / 2 ** 13

    def _get_rolling_curve(self):
        datas = np.zeros((2, len(self.times)))
        # Rolling mode
        wp0 = self._write_pointer_current  # write pointer
        # before acquisition
        times = self.times
        times -= times[-1]

        for ch, active in (
                (0, self.ch1_active),
                (1, self.ch2_active)):
            if active:
                datas[ch] = self._get_ch_no_roll(ch + 1)
        wp1 = self._write_pointer_current  # write pointer after
        #  acquisition
        for index, active in [(0, self.ch1_active),
                              (1, self.ch2_active)]:
            if active:
                data = datas[index]
                to_discard = (
                                 wp1 - wp0) % self.data_length  # remove
                #  data that have been affected during acq.
                data = np.roll(data, self.data_length - wp0)[
                       to_discard:]
                data = np.concatenate([[np.nan] * to_discard, data])
                datas[index] = data
        return times, datas

    def _start_acquisition_rolling_mode(self):
        self._start_acquisition()
        self._trigger_source = 'off'
        self._trigger_armed = True

    # Custom behavior of AcquisitionModule methods for scope:
    # -------------------------------------------------------

    def save_curve(self):
        """
        Saves the curve(s) that is (are) currently displayed in the gui in
        the db_system. Also, returns the list [curve_ch1, curve_ch2]...
        """
        d = self.setup_attributes
        curves = [None, None]
        for ch, active in [(0, self.ch1_active),
                           (1, self.ch2_active)]:
            if active:
                d.update({'ch': ch,
                          'name': self.curve_name + ' ch' + str(ch + 1)})
                curves[ch] = self._save_curve(self._run_future.data_x,
                                              self._run_future.data_avg[ch],
                                              **d)
        return curves

    def _new_run_future(self):
        # acquisition is done by a custom Future in rolling_mode to avoid
        # averaging
        if self._is_rolling_mode_active() and self.running_state == \
                "running_continuous":
            self._run_future.cancel()
            self._run_future = ContinuousRollingFuture(self)
        else:
            super(Scope, self)._new_run_future()