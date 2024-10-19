from copy import copy

import numpy as np
from qtpy import QtWidgets
import logging

from ..async_utils import wait, ensure_future, sleep_async #PyrplFuture,
# MainThreadTimer,
# CancelledError, sleep
from ..attributes import FloatProperty, SelectProperty, FrequencyProperty, \
                         IntProperty, BoolProperty, FilterProperty, SelectProperty, \
                         ProxyProperty
from ..hardware_modules import all_inputs, all_output_directs, InputSelectProperty
from ..modules import SignalModule
from ..acquisition_module import AcquisitionModule
from ..widgets.module_widgets import NaWidget
from ..hardware_modules.iq import Iq

# timeit.default_timer() is THE precise timer to use (microsecond precise vs
# milliseconds for time.time()). see
# http://stackoverflow.com/questions/85451/python-time-clock-vs-time-time-accuracy
import timeit


class NaAcBandwidth(FilterProperty):
    def valid_frequencies(self, obj):
        return [-freq for freq
                in obj.iq.inputfilter_options
                if freq <= 0]

    def get_value(self, obj):
        if obj is None:
            return self
        return -obj.iq.inputfilter

    def set_value(self, obj, value):
        if isinstance(value, list):
            value = value[0]
        obj.iq.inputfilter = -value
        return value


class NaAmplitudeProperty(FloatProperty):
    def validate_and_normalize(self, obj, value):
        return obj.iq.__class__.amplitude.validate_and_normalize(obj.iq, abs(value))


class RbwAttribute(FilterProperty):
    """"
    def get_value(self, instance):
        if instance is None:
            return self
        return instance.iq.bandwidth[0]

    def set_value(self, instance, val):
        try:
            val = list(val)
        except:
            val = [val, val]  # preferentially choose second order filter
        instance.iq.bandwidth = val
        return val
    """
    def valid_frequencies(self, obj):
        return [freq for freq in obj.iq.bandwidths if freq > 0]


class LogScaleProperty(BoolProperty):
    def set_value(self, module, val):
        super(LogScaleProperty, self).set_value(module, val)
        module._signal_launcher.x_log_toggled.emit()


class NetworkAnalyzer(AcquisitionModule, SignalModule):
    """
    Using an IQ module, the network analyzer can measure the complex coherent
    response between an output and any signal in the redpitaya.

    Three example ways on how to use the NetworkAnalyzer:

    - Example 1::

          r = RedPitaya("1.1.1.1")
          na = NetworkAnalyzer(r)
          curve = na.curve(start=100, stop=1000, rbw=10...)

    - Example 2::

          na.start = 100
          na.stop = 1000
          curve = na.curve(rbw=10)

    - Example 3::

          na.setup(start=100, stop=1000, ...)
          for freq, response, amplitude in na.values():
              print response
    """
    AUTO_AMP_AVG = 20
    _widget_class = NaWidget
    _gui_attributes = ["input",
                       "output_direct",
                       "acbandwidth",
                       "start_freq",
                       "stop_freq",
                       "rbw",
                       "average_per_point",
                       "points",
                       "amplitude",
                       "logscale",
                       "auto_bandwidth",
                       "q_factor_min",
                       "auto_amplitude",
                       "target_dbv",
                       "auto_amp_min",
                       "auto_amp_max"]
    _setup_attributes = _gui_attributes
    trace_average = IntProperty(doc="number of curves to average in single mode. In "
                                "continuous mode, a decaying average with a "
                                "characteristic memory of 'trace_average' "
                                "curves is performed.",
                                default=10,
                                min=1)
    input = InputSelectProperty(default='networkanalyzer',
                                call_setup=True,
                                ignore_errors=True)
    auto_bandwidth = BoolProperty(default=False,
                                  call_setup=True,
                                  doc="Dynamically change the bandwidth at low frequency"
                                      "based on q_factor_min")
    q_factor_min = FloatProperty(default=10,
                                 call_setup=True,
                                 doc="When auto_bandwidth is on, the bandwidth is updated"
                                     "at low frequency to make sure it is never larger"
                                     "than frequency/q_factor_min"
                                 )
    auto_amplitude = BoolProperty(default=False,
                                 call_setup=True)
    auto_amp_min = FloatProperty(default=0.0001,
                                 call_setup=True)
    auto_amp_max = FloatProperty(default=1.,
                                 call_setup=True)
    target_dbv = FloatProperty(default=-80,
                               call_setup=True)


    #input = ProxyProperty('iq.input')
    output_direct = SelectProperty(options=all_output_directs,
                                   default='off',
                                   call_setup=True)
    start_freq = FrequencyProperty(default=1e3, call_setup=True, min=Iq.frequency.increment)
    stop_freq = FrequencyProperty(default=1e6, call_setup=True, min=Iq.frequency.increment)
    rbw = RbwAttribute(default=500.0, call_setup=True)
    average_per_point = IntProperty(min=1, default=1, call_setup=True)
    amplitude = NaAmplitudeProperty(default=0.1,
                                    min=0,
                                    max=1,
                                    call_setup=True)
    points = IntProperty(min=1, max=1e8, default=1001, call_setup=True)
    logscale = LogScaleProperty(default=True, call_setup=True)
    acbandwidth = NaAcBandwidth(
        default=50.0,
        doc="Bandwidth of the input high-pass filter of the na.",
        call_setup=True)

    def __init__(self, parent, name=None):
        self.sleeptimes = 0.5
        self._time_last_point = None
        self._current_bandwidth = -1
        self.measured_time_per_point = np.nan
        self.amplitude_list = None
        #self._data_x = None
        super(NetworkAnalyzer, self).__init__(parent, name=name)

    def _load_setup_attributes(self):
        super(NetworkAnalyzer, self)._load_setup_attributes()
        if self.running_state in ["running_continuous", "running_single"]:
            self._logger.warning("Network analyzer is currently in the "
                                 "'running' state, i.e. it is performing a "
                                 "measurement. If this is not desired, "
                                 "please call network_analyzer.stop() or "
                                 "click the corresponding GUI button!")

    @property
    def iq(self):
        """
        underlying iq module.
        """
        if not hasattr(self, '_iq'):
            self._iq = self.pyrpl.iqs.pop(owner=self.name)
            # initialize iq options
            self.iq.bandwidth = [self.__class__.rbw.default, self.__class__.rbw.default]
            self.iq.inputfilter = -self.__class__.acbandwidth.default
        return self._iq

    @property
    def output_directs(self):
        return self.iq.output_directs

    @property
    def inputs(self):
        return self.iq.inputs

    def _time_per_point(self):
        return float(self.iq._na_sleepcycles + self.iq._na_averages) \
               / (125e6 * self.iq._frequency_correction)

    def signal(self):
        return self.iq.signal()

    @property
    def current_freq(self):
        """
        current frequency during the scan
        """
        return self.iq.frequency

    # delay observed with measurements of the na transfer function
    # expected is something between 3 and 4, so it is okay
    _delay = 3.0

    def transfer_function(self, frequencies, extradelay=0):
        """
        Returns a complex np.array containing the transfer function of the
        current IQ module setting for the given frequency array. The given
        transfer function is only relevant if the module is used as a
        bandpass filter, i.e. with the setting (gain != 0). If extradelay = 0,
        only the default delay is taken into account, i.e. the propagation
        delay from input to output_signal.

        Parameters
        ----------
        frequencies: np.array or float
            Frequencies to compute the transfer function for
        extradelay: float
            External delay to add to the transfer function (in s). If zero,
            only the delay for internal propagation from input to
            output_signal is used. If the module is fed to analog inputs and
            outputs, an extra delay of the order of 200 ns must be passed as
            an argument for the correct delay modelisation.

        Returns
        -------
        tf: np.array(..., dtype=complex)
            The complex open loop transfer function of the module.
        """
        module_delay = self._delay
        frequencies = np.array(np.array(frequencies, dtype=np.float),
                               dtype=complex)
        tf = np.array(frequencies*0, dtype=complex) + 1.0
        # input filter modelisation
        f = self.iq.inputfilter  # no for loop here because only one filter
        # stage
        if f > 0:  # lowpass
            tf /= (1.0 + 1j * frequencies / f)
            module_delay += 2  # two cycles extra delay per lowpass
        elif f < 0:  # highpass
            tf /= (1.0 + 1j * f / frequencies)
            module_delay += 1  # one cycle extra delay per highpass
        # add delay
        delay = module_delay * 8e-9 / self.iq._frequency_correction + \
                extradelay
        tf *= np.exp(-1j * delay * frequencies * 2 * np.pi)
        # add delay from phase (incorrect formula or missing effect...)
        return tf

    def threshold_hook(self, current_val):  # goes in the module...
        """
        A convenience function to stop the run upon some condition
        (such as reaching of a threshold. current_val is the complex amplitude
        of the last data point).

        To be overwritten in derived class...
        Parameters
        ----------
        current_val

        Returns
        -------

        """
        pass

    # Concrete implementation of AcquisitionModule methods and attributes:
    # --------------------------------------------------------------------
    MIN_DELAY_SINGLE_MS = 0
    MIN_DELAY_CONTINUOUS_MS = 0
    # na should be as fast as possible

    def is_zero_span(self):
        """
        Returns true if start_freq is the same as stop_freq.
        """
        return self.start_freq==self.stop_freq

    async def _ramp_iq_amp_async(self, new_val):
        amp_start = self.iq.amplitude
        for amp in np.linspace(amp_start, new_val, 30):
            self.iq.amplitude = amp
            await sleep_async(0.01)


    async def _start_point_acquisition(self, index):
        if self.is_zero_span():
            # in zero span, data_x are time, not frequency
            frequency = self.start_freq
        else:
            # normal frequency sweep, get frequency from data_x-array
            frequency = self.frequencies[index]
        if self.auto_bandwidth: # RBW should be updated if needed
            if self.auto_rbw_value(frequency) > self._current_bandwidth + 0.001: # avoid rounding problems
                self._current_bandwidth*=2
                self.iq.bandwidth = [self._current_bandwidth, self._current_bandwidth]

                new_sleep_cycles = np.int(
                    np.round(125e6 / self._current_bandwidth * self.sleeptimes))
                self.iq._na_sleepcycles = new_sleep_cycles
                new_na_averages = np.int(np.round(125e6 / self._current_bandwidth *
                                                       self.average_per_point))
                self.iq._na_averages = new_na_averages
                self._cached_na_averages = new_na_averages

                self.time_per_point = float(new_sleep_cycles + new_na_averages) \
                                            / (125e6 * self.iq._frequency_correction)
        if self.auto_amplitude:
            if self.current_avg==0: # need to determine next amp
                if index<=self.AUTO_AMP_AVG: # use user-defined amplitude
                    self.iq.amplitude = self.amplitude
                    self.amplitude_list[index] = self.iq.amplitude
                else:
                    last_ratio = np.abs(np.mean(self.data_avg[index - self.AUTO_AMP_AVG:index]))
                    target_v = 10**(self.target_dbv/20)
                    next_amp = target_v/last_ratio
                    last_amp = self.amplitude_list[index - 1]
                    if next_amp/last_amp>2:
                        if last_amp*2 <= self.auto_amp_max:
                            await self._ramp_iq_amp_async(self.iq.amplitude*2)
                            self.amplitude_list[index] = self.iq.amplitude
                        else:
                            self.amplitude_list[index] = last_amp
                    elif next_amp/last_amp<0.5:
                        if last_amp/2 >= self.auto_amp_min:
                            await self._ramp_iq_amp_async(self.iq.amplitude/2)
                            self.amplitude_list[index] = self.iq.amplitude
                        else:
                            self.amplitude_list[index] = last_amp
                    else:
                        self.amplitude_list[index] = last_amp  # keep the same amplitude
            else:
                if index == 0:
                    last_index = -1
                else:
                    last_index = index -1
                if abs(self.amplitude_list[last_index] - self.amplitude_list[index])>1e-6:
                    await self._ramp_iq_amp_async(self.amplitude_list[index])



        # last point to determine amplitude
        #    self.amplitude_list[inde]

        self.iq.frequency = frequency
        self._time_last_point = timeit.default_timer()
        # regular print output for travis workaround
        #self._logger.debug("Acquiring first NA point at frequency %.1f Hz..", frequency)
        # replaced above command by the following two due to suppression of multiple logger warnings
        if self._logger.getEffectiveLevel() <= 10:
            try:
                delay = self._time_last_point - self._lastprinttime
                self._lastpointnumber += 1
            except:
                delay = 999.0
                self._lastpointnumber = 0
            if self._lastpointnumber < 100 or delay >= 10.0:
            #if True:  # above if-statement does not work correctly on travis, e.g. stops printing after laspointnumber 66
                print("Acquiring new NA point #%d at frequency %.1f Hz after "
                      "delay of %f" % (self._lastpointnumber, frequency, delay))
                self._lastprinttime = self._time_last_point

    def _get_point(self, index):
        # get the actual point's (discretized)
        # frequency
        # only one read operation per point
        y = self.iq._nadata_total / self._cached_na_averages

        tf = self._tf_values[index]

        amp = self.iq.amplitude  # get amplitude for normalization
        if amp == 0:  # normalize immediately
            y *= self._rescale  # avoid division by zero
        else:
            y *= self._rescale / amp
        # correct for network analyzer transfer function (AC-filter and
        # delay)
        y /= tf
        return y, amp

    def take_ringdown(self, frequency, rbw=1000, points=1000, trace_average=1):
        self.start_freq = frequency
        self.stop_freq = frequency
        self.rbw = rbw
        self.points = points
        self.trace_average = trace_average
        curve = self.single_async()
        sleep_async(0.1)
        self.iq.output_direct = "off"
        self._time_first_point=timeit.default_timer()
        res = curve.await_result()
        x = self._run_future.data_x - self._time_first_point
        return [x, res]

    def auto_rbw_value(self, freq):
        """
        if freq/q is smaller than rbw, use it instead.
        Also, round to the smallest non-zero rbw
        """
        desired_val = min(max(freq / self.q_factor_min, 1.186), self.rbw)
        valid_bws = self.iq.bandwidth_options
        return valid_bws[np.argmin(np.abs(np.array(valid_bws) - desired_val))]

    def _start_trace_acquisition(self):
        """
        For the NA, resuming (from pause to start for instance... should
        not setup the instrument again, otherwise, this would restart at
        the beginning of the curve)
        Moreover, iq is disabled even when na is just paused.
        :return:
        """
        # super(NAAcquisitionManager, self)._start_acquisition()
#        x = self._data_x if not self.is_zero_span() else  \
#                                        self.start_freq*np.ones(self.points)

        self.iq.amplitude = 0 # Set the amplitude at 0 before anything else to avoid glitch
        if self.auto_bandwidth:
            self._current_bandwidth = self.auto_rbw_value(self.frequencies[0]) # smallest non-zero bandwidth
        else:
            self._current_bandwidth = self.rbw

        self.iq.setup(frequency=self.frequencies[0],
                      bandwidth=[self._current_bandwidth, self._current_bandwidth],
                      gain=0,
                      phase=0,
                      acbandwidth=self.acbandwidth,
                      input=self.input,
                      output_direct=self.output_direct,
                      output_signal='output_direct')
        self._current_bandwidth = self.iq.bandwidth[0]

        # setup averaging
        self.iq._na_averages = np.int(np.round(125e6 / self._current_bandwidth *
                                               self.average_per_point))
        self._cached_na_averages = self.iq._na_averages
        self.iq._na_sleepcycles = np.int(
            np.round(125e6 / self._current_bandwidth * self.sleeptimes))
        # time_per_point is calculated at setup for speed reasons
        self.time_per_point = self._time_per_point()
        self._time_first_point = None # for 0-span mode, we need to record
        # times
        # compute rescaling factor of raw data
        # 4 is artefact of fpga code
        self._rescale = 2.0 ** (-self.iq._LPFBITS) * 4.0
        # to avoid reading it at every single point
        self.iq.frequency = self.frequencies[0]  # this triggers the NA acquisition
        self.iq.amplitude = self.amplitude  # Set the amplitude to non-zero at the last moment to avoid glitch
        if self.auto_amplitude:
            self.amplitude_list = np.zeros(self.points)
        else:
            self.amplitude_list = self.iq.amplitude
        self._time_last_point = timeit.default_timer()
        # pre-calculate transfer_function values for speed
        self._tf_values = self.transfer_function(self.frequencies)
        self.iq.on = True
        # Warn the user if time_per_point is too small:
        # < 1 ms measurement time will make acquisition inefficient.
        if self.time_per_point < 0.001:
            self._logger.info("Time between successive points is %.1f ms."
                              " You should increase 'average_per_point' to "
                              "at least %i for efficient acquisition.",
                              self.time_per_point * 1000,
                              self.average_per_point * 0.001 / self.time_per_point)

    def _stop_acquisition(self):
        """
        Stop the iq.
        """
        self.iq.amplitude = 0

    def _data_ready(self):
        return self._remaining_time()<=0

    async def _point_async(self, index, min_delay_ms):
        if self.running_state == 'paused':
            await self._resume_event.wait()
        await self._start_point_acquisition(index)
        await self._data_ready_async(min_delay_ms)
        return self._get_point(index)

    async def _trace_async(self, min_delay_ms):
        if self.current_point==0:
            self._start_trace_acquisition()
        else:
            self.iq.amplitude = self.amplitude # go from pause to resume
        while (self.current_point<self.points):
            if self._last_time_benchmark is not None:
                new_time = timeit.default_timer()
                self.measured_time_per_point = \
                    new_time - self._last_time_benchmark
            self._last_time_benchmark = timeit.default_timer()
            if self.running_state in ["paused_continuous", "paused_single"]:
                await self._resume_event.wait()
                self.iq.amplitude = self.amplitude
            y, amp = await self._point_async(self.current_point, min_delay_ms)
            if self.is_zero_span():
                now = timeit.default_timer()
                if self._time_first_point is None:
                    self._time_first_point = now
                self.data_x[self.current_point] = now - self._time_first_point

            self._emit_signal_by_name("update_point", self.current_point)

            self.data_avg[self.current_point] = (self.data_avg[self.current_point]*(self.current_avg) \
                                 + y)/(self.current_avg + 1)
            self.current_point+=1
        self.current_avg = min(self.current_avg + 1, self.trace_average)
        self._emit_signal_by_name("scan_finished")
        self.current_point = 0
        return self.data_avg

    async def _single_async(self):
        self._prepare_averaging()
        return await self._do_average_single_async()

    async def _do_average_single_async(self):
        self._running_state = 'running_single'
        #self.iq.amplitude = self.amplitude  # Amplitude is already set in self._trace_async (avoid glitch)
        while self.current_avg < self.trace_average:
            await self._trace_async(0)
        self._free_up_resources()
        self._running_state = 'stopped'
        return self.data_avg

    async def _do_average_continuous_async(self):
        self._running_state = 'running_continuous'
        # self.iq.amplitude = self.amplitude # Amplitude is already set in self._trace_async (avoid glitch)
        while (self.running_state != 'stopped'):
            await self._trace_async(0)

    async def _continuous_async(self):
        self._prepare_averaging()
        await self._do_average_continuous_async()


    @property
    def frequencies(self):
        """
        Since calculating frequency (normalized to fit in the hardware) might
        be long, we cash the result.
        """
        if self._frequencies is None:
            self._frequencies = self._get_frequencies()
        return self._frequencies

    def _get_frequencies(self):
        if self.is_zero_span():
            return self.iq.__class__.frequency.validate_and_normalize(self,
                                                self.start_freq)*np.ones(
                                                                self.points)

        if self.logscale:
            raw_values = np.logspace(
                np.log10(self.start_freq),
                np.log10(self.stop_freq),
                         self.points,
                         endpoint=True)
        else:
            raw_values = np.linspace(self.start_freq,
                               self.stop_freq,
                               self.points,
                               endpoint=True)
        values = np.zeros(len(raw_values))
        for index, val in enumerate(raw_values):
            values[index] = self.iq.__class__.frequency. \
                validate_and_normalize(self, val)  # retrieve the real freqs...
        return values

    def _remaining_time(self):
        """Remaining time in seconds until current point is ready"""
        # implement here the extra waiting at the beginning
        if self.current_point==0:
            time_per_point = 3*self.time_per_point
        else:
            time_per_point = self.time_per_point
        return time_per_point - (timeit.default_timer() -
                                      self._time_last_point)

    def _prepare_averaging(self):
        super(NetworkAnalyzer, self)._prepare_averaging()
        self._last_time_benchmark = None
        self.current_point = 0
        self.data_x = self.frequencies if not self.is_zero_span() else \
            np.nan*np.ones(self.points) # Will be filled during acquisition
        self.data_avg = np.zeros(self.points,      # np.empty can create nan
                                 dtype=complex) #and nan*current_avg = nan
                                                   # even if current_avg = 0

    @property
    def last_valid_point(self):
        if self.current_avg>=1:
            return self.points - 1
        else:
            return self.current_point

    def _setup(self):
        #self._update_data_x()  # precalculate frequency values
        self._frequencies = None # forget precalculated frequencies
        super(NetworkAnalyzer, self)._setup()

    # overwrite default behavior to return only valid points

    def _free_up_resources(self):
        self.iq.amplitude = 0

    @property
    def last_valid_point(self):
        return self.current_point if \
            self.current_avg<=1 else self.points
