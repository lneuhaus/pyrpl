from copy import copy

import numpy as np
from PyQt4 import QtGui

from ..async_utils import PyrplFuture, MainThreadTimer, CancelledError
from ..attributes import FloatProperty, SelectProperty, FrequencyProperty, \
                         IntProperty, BoolProperty, FilterProperty, SelectProperty, \
                         ProxyProperty
from ..hardware_modules import all_inputs, all_output_directs, InputSelectProperty
from ..acquisition_module import AcquisitionModule
from ..widgets.module_widgets import NaWidget

# timeit.default_timer() is THE precise timer to use (microsecond precise vs
# milliseconds for time.time()).
# see
# http://stackoverflow.com/questions/85451
# /python-time-clock-vs-time-time-accuracy
import timeit

APP = QtGui.QApplication.instance()


class NaAcBandwidth(FilterProperty):
    def valid_frequencies(self, instance):
        return [freq for freq
                in instance.iq._valid_inputfilter_frequencies(instance.iq)
                if freq >= 0]

    def get_value(self, instance):
        if instance is None:
            return self
        return -instance.iq.inputfilter

    def set_value(self, instance, value):
        instance.iq.inputfilter = [-value[0]]
        return value


class RbwAttribute(FilterProperty):
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

    def valid_frequencies(self, module):
        return module.iq.__class__.bandwidth.valid_frequencies(module.iq)


class LogScaleProperty(BoolProperty):
    def set_value(self, module, val):
        super(LogScaleProperty, self).set_value(module, val)
        module._signal_launcher.x_log_toggled.emit()


class NaPointFuture(PyrplFuture):
    """
    Future object for a NetworkAnalyzer point.
    """

    def __init__(self, module, point_index, min_delay_ms=0):
        self._module = module
        self.point_index = point_index
        self._min_delay_ms = min_delay_ms
        super(NaPointFuture, self).__init__()
        self._init_timer()

    def _init_timer(self):
        self._module._start_point_acquisition(self.point_index)
        if self._min_delay_ms == 0:
            # make sure 1st instrument interrogation occurs before time
            delay = self._module._remaining_time() * 1000 - 1
        else:
            # 1 ms loss due to timer inaccuracy is acceptable
            delay = max(self._min_delay_ms,
                        self._module._remaining_time() * 1000)

        self._timer = MainThreadTimer(max(0, delay))
        self._timer.timeout.connect(self._set_data_as_result)
        self._timer.start()

    def _set_data_as_result(self):
        if not self.done(): # if point was cancelled, leave the loop.
            point = self._module._get_point(self.point_index)
            if point is not None:
                self.set_result(point)
            else:
                self._timer.setInterval(self._min_delay_ms)
                self._timer.start()

    def set_exception(self, exception):
        self._timer.stop()
        super(NaPointFuture, self).set_exception(exception)

    def cancel(self):
        self._timer.stop()
        super(NaPointFuture, self).cancel()


class NaCurveFuture(PyrplFuture):
    N_POINT_BENCHMARK = 100 #  update measured_time_per_point every 100 points

    def __init__(self, module, min_delay_ms, autostart=True):
        self._module = module
        self._min_delay_ms = min_delay_ms
        self.current_point = 0
        self.current_avg  = 1
        self.n_points = self._module.points
        self._paused = True
        self._fut = None
        self.never_started = True
        super(NaCurveFuture, self).__init__()
        self._module._start_acquisition()
        self.data_x = copy(self._module.data_x)  # In case of saving latter.
        self.data_avg = np.zeros(self.n_points,
                                 dtype=np.complex)
        self.data_amp = np.zeros(self.n_points)
        # self.start()
        self._reset_benchmark()
        self.measured_time_per_point = np.nan  #  measured over last scan
        if autostart:
            self.start()

    def start(self):
        self._module.iq.output_direct = self._module.output_direct
        if self.never_started:
            self._module._emit_signal_by_name("clear_curve")
            self.never_started = False
        self._paused = False
        self._setup_next_point()

    def _setup_next_point(self):
        self._fut = self._module._new_point_future(self.current_point,
                                                   self._min_delay_ms)
        self._fut.add_done_callback(self._new_point_arrived)

    def pause(self):
        self._module.iq.output_direct = 'off'  #  switch off iq when paused
        self._paused = True
        if self._fut is not None:
            self._fut.cancel()

    def _reset_benchmark(self):
        self._last_time_benchmark = timeit.default_timer()
        self._current_points_benchmark = 0

    def _update_benchmark(self):
        self._current_points_benchmark += 1
        if self._current_points_benchmark >= self.N_POINT_BENCHMARK:
            current_time = timeit.default_timer()
            self.measured_time_per_point = \
    (current_time - self._last_time_benchmark)/self._current_points_benchmark
            self._reset_benchmark()

    def _new_point_arrived(self, point):
        if self._paused:
            return
        self._update_benchmark()
        try:
            point = point.result()
        except CancelledError:
            self._point_cancelled()
            return #  exit the loop (could be restarted latter for RunFuture)
        self._add_point(point)
        self.current_point+=1
        if self.current_point==self.n_points:
            self._scan_finished()
        else:
            self._setup_next_point()

    def cancel(self):
        self.pause()
        super(NaCurveFuture, self).cancel()

    # These methods behave differently in the derived class RunFuture:
    # ----------------------------------------------------------------
    #  1. points are averaged and not overwritten.
    #  2. Each point sends an update signal to the gui.
    #  3. A point cancelled doesn't mean the Future is cancelled (can be
    # restarted if the state is paused.)
    #  4. When the scan is finished, start a new scan over.

    def _add_point(self, point):
        y, amp = point
        self.data_avg[self.current_point] = y
        self.data_amp[self.current_point] = amp

    def _point_cancelled(self):
        self.cancel() #  if a point is cancelled during a curve, cancel the
        # curve

    def _scan_finished(self):
        self.set_result(self.data_avg)


class NaRunFuture(NaCurveFuture):
    def __init__(self, module, min_delay_ms):
        super(NaRunFuture, self).__init__(module,
                                          min_delay_ms,
                                          autostart=False)
        self._run_continuous = False

    def pause(self):
        self._paused = True

    def _add_point(self, point):
        y, amp = point
        index = self.current_point
        self.data_avg[index] = (self.data_avg[index]*(self.current_avg - 1) + \
                               y)/self.current_avg
        self.data_amp[index] = amp
        self._module._emit_signal_by_name("update_point", index)

    def _point_cancelled(self):
        # If a point is cancelled during the run, for instance the user
        # pressed pause, the acquisition can be restarted latter.
        pass

    def _scan_finished(self):
        # launch this signal before current_point goes back to 0...
        self._module._emit_signal_by_name("scan_finished")
        if self._run_continuous or self.current_avg<self._module.avg:
            self._module._start_acquisition()
            # restart scan from the beginning.
            self.current_point = 0
            self.start()
        if not self._run_continuous and self.current_avg == self._module.avg:
            self.set_result(self.data_avg)
            #  in case the user wants to move on with running_continuous mode
            self.current_point = 0
            self._module.running_state = "paused"
        self.current_avg = min(self.current_avg + 1, self._module.avg)

    def _set_run_continuous(self):
        self._run_continuous = True
        self._min_delay_ms = self._module.MIN_DELAY_CONTINUOUS_MS


class NetworkAnalyzer(AcquisitionModule):
    """
    Using an IQ module, the network analyzer can measure the complex coherent
    response between an output and any signal in the redpitaya.

    2 ways to use the NetworkAnalyzer:
      exemple 1:
            r = RedPitaya("1.1.1.1")
            na = NetworkAnalyzer(r)
            curve = na.curve(start=100, stop=1000, rbw=10...)
      exemple 2:
            na.start = 100
            na.stop = 1000
            curve = na.curve(rbw=10)
      exemple 3:
            na.setup(start=100, stop=1000, ...)
            for freq, response, amplitude in na.values():
                print response
    """
    _widget_class = NaWidget
    _gui_attributes = ["input",
                       "acbandwidth",
                       "output_direct",
                       "start_freq",
                       "stop_freq",
                       "rbw",
                       "avg_per_point",
                       "points",
                       "amplitude",
                       "logscale",
                       "infer_open_loop_tf"]
    _setup_attributes = _gui_attributes + ['running_state']
    # _callback_attributes = _gui_attributes
    input = InputSelectProperty(call_setup=True)
    #input = ProxyProperty('iq.input')
    output_direct = SelectProperty(all_output_directs, call_setup=True)
    start_freq = FrequencyProperty(call_setup=True)
    stop_freq = FrequencyProperty(call_setup=True)
    rbw = RbwAttribute(default=1000, call_setup=True)
    avg_per_point = IntProperty(min=1, default=1, call_setup=True)
    amplitude = FloatProperty(min=0,
                              max=1,
                              increment=1. / 2 ** 14,
                              call_setup=True)
    points = IntProperty(min=1, max=1e8, default=1001, call_setup=True)
    logscale = LogScaleProperty(call_setup=True)
    infer_open_loop_tf = BoolProperty()
    acbandwidth = NaAcBandwidth(
        doc="Bandwidth of the input high-pass filter of the na.",
        call_setup=True)

    def _init_module(self):
        # to remove once order is fixed
        self._setup_attributes.remove('running_state')
        self._setup_attributes.append('running_state')

        self.sleeptimes = 0.5
        self.rbw = 200
        self.start_freq = 200
        self.stop_freq = 50000
        self.points = 1001

        self.avg_per_point = 1
        self.amplitude = 0.01
        self.input = 'in1'
        self.output_direct = 'off'
        self.acbandwidth = 0
        self.logscale = False
        self.infer_open_loop_tf = False
        self.curve_name = 'na_curve'
        self._is_setup = False
        self.time_per_point = self._time_per_point()
        #self.current_averages = 0
        self._time_last_point = 0
        self._update_data_x()
        super(NetworkAnalyzer, self)._init_module()

    @property
    def iq(self):
        """
        underlying iq module.
        """
        if not hasattr(self, '_iq'):
            self._iq = self.pyrpl.iqs.pop(owner=self.name)
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
        tf: np.array(..., dtype=np.complex)
            The complex open loop transfer function of the module.
        """
        module_delay = self._delay
        frequencies = np.array(np.array(frequencies, dtype=np.float),
                               dtype=np.complex)
        tf = np.array(frequencies*0, dtype=np.complex) + 1.0
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

    _curve_future_cls = NaCurveFuture
    _run_future_cls = NaRunFuture

    def _new_run_future_obsolete(self):
        assert self.running_state in ["running_single",
                                      "running_continuous"], \
                                     "Run future cannot be created in " \
                                     "state %s"%self.running_state

        self._run_future.cancel()
        if self.running_state == "running_continuous":
            self._run_future = NaRunFuture(self,
                                min_delay_ms=self.MIN_DELAY_CONTINUOUS_MS)
            self._run_future._set_run_continuous()
        if self.running_state == "running_single":
            self._run_future = NaRunFuture(self,
                                    min_delay_ms=self.MIN_DELAY_SINGLE_MS)

    def _get_new_curve_future(self, min_delay_ms):
        return NaCurveFuture(self, min_delay_ms)

    def _new_point_future(self, index, min_delay_ms):
        if hasattr(self, "_point_future"): #  for _init_module
            self._point_future.cancel()
        self._point_future = NaPointFuture(self, index, min_delay_ms)
        return self._point_future

    def _start_point_acquisition(self, index):
        #if self.current_point < self.points:
            # writing to iq.frequency triggers the acquisition
            # negative index means "PRETRACE_POINT"--> acquire with start_freq
        self.iq.frequency = self.data_x[index]
        self._time_last_point = timeit.default_timer()

    def _get_point(self, index):
        # get the actual point's (discretized)
        # frequency
        if self._remaining_time()>0:
            return None
        # only one read operation per point
        y = self.iq._nadata_total / self._cached_na_averages

        x = self.data_x[index]
        tf = self._tf_values[index]

        amp = self.amplitude  # get amplitude for normalization
        if amp == 0:  # normalize immediately
            y *= self._rescale  # avoid division by zero
        else:
            y *= self._rescale / amp
        # correct for network analyzer transfer function (AC-filter and
        # delay)
        y /= tf
        return y, amp

    def _start_acquisition(self):
        """
        For the NA, resuming (from pause to start for instance... should
        not setup the instrument again, otherwise, this would restart at
        the beginning of the curve)
        Moreover, iq is disabled even when na is just paused.
        :return:
        """
        # super(NAAcquisitionManager, self)._start_acquisition()
        self._update_data_x()
        x = self.data_x
        # preventive saturation
        amplitude = abs(self.amplitude)
        self.iq.setup(frequency=x[0],
                      bandwidth=self.rbw,
                      gain=0,
                      phase=0,
                      acbandwidth=self.acbandwidth,
                      amplitude=amplitude,
                      input=self.input,
                      output_direct=self.output_direct,
                      output_signal='output_direct')
        # setup averaging
        self.iq._na_averages = np.int(np.round(125e6 / self.rbw *
                                               self.avg_per_point))
        self._cached_na_averages = self.iq._na_averages
        self.iq._na_sleepcycles = np.int(
            np.round(125e6 / self.rbw * self.sleeptimes))
        # time_per_point is calculated at setup for speed reasons
        self.time_per_point = self._time_per_point()
        # compute rescaling factor of raw data
        # 4 is artefact of fpga code
        self._rescale = 2.0 ** (-self.iq._LPFBITS) * 4.0
        # to avoid reading it at every single point
        self.iq.frequency = x[0]  # this triggers the NA acquisition
        self._time_last_point = timeit.default_timer()
        # pre-calculate transfer_function values for speed
        self._tf_values = self.transfer_function(x)
        self.iq.on = True
        # Warn the user if time_per_point is too small:
        # < 1 ms measurement time will make acquisition inefficient.
        if self.time_per_point < 0.001:
            self._logger.info("Time between successive points is %.1f ms."
                              " You should increase 'avg_per_point' to at "
                              "least %i "
                              "for efficient acquisition.",
                              self.time_per_point * 1000,
                              self.avg_per_point * 0.001 / self.time_per_point)

    def _stop_acquisition(self):
        """
        Stop the iq.
        """
        self.iq.output_direct = 'off'

    @property
    def data_x(self):
        return self._data_x

    def _update_data_x(self):
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
        self._data_x = values

    def _remaining_time(self):
        """Remaining time in seconds until current point is ready"""
        # implement here the extra waiting at the beginning
        if self.current_point==0:
            time_per_point = 3*self.time_per_point
        else:
            time_per_point = self.time_per_point
        return time_per_point - (timeit.default_timer() -
                                      self._time_last_point)

    # Shortcut to the RunFuture data (for plotting):
    # ----------------------------------------------

    @property
    def last_valid_point(self):
        if self.current_avg>1:
            return self.points - 1
        else:
            return self.current_point

    @property
    def current_point(self):
        return self._run_future.current_point

    @property
    def measured_time_per_point(self):
        return self._run_future.measured_time_per_point