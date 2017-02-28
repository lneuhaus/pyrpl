import logging
import sys
from time import sleep

from ..attributes import FilterAttribute
from ..attributes import FloatProperty, SelectProperty, FrequencyProperty, \
                        LongProperty, BoolProperty, StringProperty
from ..hardware_modules import DspModule
from ..widgets.module_widgets import NaWidget

from . import SoftwareModule
from ..modules import SignalLauncher

from PyQt4 import QtCore, QtGui
import numpy as np

# timeit.default_timer() is THE precise timer to use (microsecond precise vs
# milliseconds for time.time()).
# see
# http://stackoverflow.com/questions/85451/python-time-clock-vs-time-time-accuracy
import timeit

APP = QtGui.QApplication.instance()


class NaAcBandwidth(FilterAttribute):
    def valid_frequencies(selfself, instance):
        return [freq for freq
                in instance.iq._valid_inputfilter_frequencies(instance.iq)
                if freq >= 0]

    def get_value(self, instance, owner):
        if instance is None:
            return self
        return -instance.iq.inputfilter

    def set_value(self, instance, value):
        instance.iq.inputfilter = [-value[0]]
        return value


class RbwAttribute(FilterAttribute):
    def get_value(self, instance, owner):
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


class NaStateProperty(StringProperty):
    """
    This property is the "master" attribute controlling asynchronous
    data_acquisition of the na.
    Changing its value to one of the following will autoomatically launch the
    corresponding acquisition;
      - 'running_continuous': infinite frequency scans averaged together
      - 'running_single': single frequency scan (goes to paused_single when done)
      - 'paused_single'
      - 'paused_continuous'
      - 'stopped': no way to resume on the same averages when stopped
    """
    def set_value(self, module, val):
        old_val = module.running_state
        if val in ['running_continuous', 'running_single']:
            if old_val=="stopped":
                module.iq.output_direct = module.output_direct
                module._signal_launcher.run()
            else:
                module.iq.output_direct = module.output_direct
                module.iq.frequency = module.iq.frequency # reset na
                # accumulator
                module._signal_launcher.resume()
        if val in ['paused_continuous', 'paused_single']:
            module._signal_launcher.pause()
            module.iq.output_direct = 'off'
        if val in ["stopped"]:
            if hasattr(module, 'value_generator'):
                module.values_generator.close() # closing the generator triggers the
                                                # finally block
                # Otherwise, the "finally" block is executed when the generator gets
                # deleted (__del__): in practice, this happens at the next call of
                # setup() ---> Very naughty situation...
            module.iq.output_direct = 'off' # Not sure why this is needed in addition
                                            # to close
        super(NaStateProperty, self).set_value(module, val)


class LogScaleProperty(BoolProperty):
    def set_value(self, module, val):
        super(LogScaleProperty, self).set_value(module, val)
        module._signal_launcher.x_log_toggled.emit()


class SignalLauncherNA(SignalLauncher):
    """
    The timers for asynchronous data acquisition are controlled
    inside this class
    """
    point_updated = QtCore.pyqtSignal(int)
    # This signal is emitted when a point needs to be updated (added/changed)
    # The argument is the index of the point as found in module.y_averaged
    autoscale = QtCore.pyqtSignal()
    scan_finished = QtCore.pyqtSignal()
    clear_curve = QtCore.pyqtSignal()
    x_log_toggled = QtCore.pyqtSignal()

    def __init__(self, module):
        super(SignalLauncherNA, self).__init__(module)
        self.datas = [None, None]
        self.timer_point = QtCore.QTimer()
        self.timer_point.setSingleShot(True)
        self.timer_point.timeout.connect(self.module._run_next_point)
        self.timer_point.start()

    def kill_timers(self):
        """
        kill all timers
        """
        self.timer_point.stop()

    def run(self):
        self.module.setup()
        self.module._setup_averaging()
        self.module._prepare_for_next_point()
        self.clear_curve.emit()
        self.timer_point.start()

    def resume(self):
        self.timer_point.start()

    def pause(self):
        self.timer_point.stop()

    def connect_widget(self, widget):
        super(SignalLauncherNA, self).connect_widget(widget)
        #self.autoscale.connect(widget.autoscale)
        self.point_updated.connect(widget.update_point)
        #self.scan_finished.connect(widget.scan_finished)
        #self.clear_curve.connect(widget.clear_curve)
        #self.x_log_toggled.connect(widget.x_log_toggled)


class NetworkAnalyzer(SoftwareModule):
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
    _section_name = 'na'
    _widget_class = NaWidget
    _setup_attributes = ["input",
                         "acbandwidth",
                         "output_direct",
                         "start_freq",
                         "stop_freq",
                         "rbw",
                         "points",
                         "amplitude",
                         "logscale",
                         "infer_open_loop_tf",
                         "avg",
                         "curve_name",
                         "running_state"]
    _gui_attributes = _setup_attributes + ["running_state"]
    _callback_attributes = [a for a in _gui_attributes
                            if a not in ['running_state', 'curve_name']]
    data = None
    _signal_launcher = SignalLauncherNA
    PRETRACE_POINTS = 2

    def _init_module(self):
        self.start_freq = 200
        self.stop_freq = 50000
        self.points = 1001
        self.rbw = 200
        self.avg = 1
        self.amplitude = 0.01
        self.input = 'in1'
        self.output_direct = 'off'
        self.acbandwidth = 0
        self.sleeptimes = 0.5
        self.logscale = False
        self.infer_open_loop_tf = False
        self.curve_name = 'na_curve'
        self._is_setup = False
        self.time_per_point = self._time_per_point()
        self.current_averages = 0
        self.time_last_point = 0
        self.running_state = 'stopped'

    input = SelectProperty(DspModule.inputs)
    output_direct = SelectProperty(DspModule.output_directs)
    start_freq = FrequencyProperty()
    stop_freq = FrequencyProperty()
    rbw = RbwAttribute()
    amplitude = FloatProperty(min=0, max=1, increment=1. / 2 ** 14)
    points = LongProperty(min=1, max=1e8)
    logscale = LogScaleProperty()
    infer_open_loop_tf = BoolProperty()
    avg = LongProperty(min=1)
    curve_name = StringProperty()
    acbandwidth = NaAcBandwidth(
        doc="Bandwidth of the input high-pass filter of the na.")
    running_state = NaStateProperty()

    def _callback(self):
        """
        Whenever a setup_attribute is touched, stop the acquisition immediately.
        """
        if self.running_state in ['running_single', 'running_continuous',
                                  'paused_single', 'paused_continuous']:
            print("stopping because callback")
            self.stop()

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

    def _setup(self):
        """
        Sets up the network analyzer for a run.
        """
        self._is_setup = True

        if self.logscale:
            self.x = np.logspace(
                np.log10(self.start_freq),
                np.log10(self.stop_freq),
                self.points,
                endpoint=True)
        else:
            self.x = np.linspace(self.start_freq,
                                 self.stop_freq,
                                 self.points,
                                 endpoint=True)
        for index, val in enumerate(self.x):
            self.x[index] = self.iq.__class__.frequency.\
                validate_and_normalize(val, self) # retrieve the real freqs...
        # preventive saturation
        amplitude = abs(self.amplitude)
        self.iq.setup(frequency=self.x[0],
                      bandwidth=self.rbw,
                      gain=0,
                      phase=0,
                      acbandwidth=self.acbandwidth,
                      amplitude=amplitude,
                      input=self.input,
                      output_direct=self.output_direct,
                      output_signal='output_direct')
        # setup averaging
        self.iq._na_averages = np.int(np.round(125e6 / self.rbw * self.avg))
        self._cached_na_averages = self.iq._na_averages
        self.iq._na_sleepcycles = np.int(
            np.round(125e6 / self.rbw * self.sleeptimes))
        # time_per_point is calculated at setup for speed reasons
        self.time_per_point = self._time_per_point()
        # compute rescaling factor of raw data
        # 4 is artefact of fpga code
        self._rescale = 2.0 ** (-self.iq._LPFBITS) * 4.0
        # number of "dead_points" at the beginning of the scans.
        self.current_point = - self.PRETRACE_POINTS
        # to avoid reading it at every single point
        self.iq.frequency = self.x[0]  # this triggers the NA acquisition
        self.time_last_point = timeit.default_timer()
        # pre-calculate transfer_function values for speed
        self._tf_values = self.transfer_function(self.x)
        self.values_generator = self._values()
        self.iq.on = True
        # Warn the user if time_per_point is too small:
        # < 1 ms measurement time will make acquisition inefficient.
        if self.time_per_point < 0.001:
            self._logger.info("Time between successive points is %.1f ms."
                              " You should increase 'avg' to at least %i "
                              "for efficient acquisition.",
                              self.time_per_point * 1000, self.avg*0.001/self.time_per_point)

    def _run_next_point(self):
        if self.running_state in ['running_continuous',
                                  'running_single']:
            cur = self.current_point
            try:
                result = next(self.values_generator)
            except StopIteration: # end of scan
                self.current_averages += 1
                if self.running_state == 'running_continuous':
                    # reset acquistion without resetting averaging
                    self.setup()
                    self._signal_launcher.timer_point.start()
                else:
                    self.pause()
                    # gives the opportunity to average other scans with
                    # this one by calling run_continuous()
                self._signal_launcher.scan_finished.emit()
            else: # Scan not ended
                if result is None: # PRETRACE_POINT, disregard and just
                                   # relaunch timer for next point
                    self._signal_launcher.timer_point.start()
                else: # standard point in the middle of the scan
                      # fill in self.y_current_scan, self.current_averages, self.x
                      # launch signal to display point, and restart timer
                    x, y, amp = result
                    self.y_current_scan[cur] = y
                    self.y_averaged[cur] = (self.y_averaged[cur]
                        * self.current_averages + y) \
                        / (self.current_averages + 1)
                    self.x[cur] = x

                    self._signal_launcher.point_updated.emit(self.current_point)
                    self._signal_launcher.timer_point.start()

    def _time_per_point(self):
        return float(self.iq._na_sleepcycles + self.iq._na_averages) \
               / (125e6 * self.iq._frequency_correction)

    def _setup_averaging(self):
        self.current_averages = 0
        self.current_attributes = self.get_setup_attributes()
        self.y_current_scan = np.zeros(self.points, dtype=complex)
        self.y_averaged = np.zeros(self.points, dtype=complex)
        self._signal_launcher.timer_point.setInterval(self.time_per_point*1000)

    @property
    def last_valid_point(self):
        return self.points - 1 if self.current_averages>0 else self.current_point

    @property
    def current_freq(self):
        """
        current frequency during the scan
        """
        return self.iq.frequency

    def _get_current_point(self):
        """
        This function fetches the current point on the redpitaya.
        The function blocks until the time since the last point has reached
        time_per_point.
        Returns: - None if the point is a PRETRACE_POINT to be discarded
                 - A triplet containing (x, y , amp) otherwise
        """
        if self.current_point < 0:
            # if this is a PRETRACE_POINT at the beginning of the trace, disregard the value
            # get the actual point's (discretized) frequency
            return None
        else:
            x = self.x[self.current_point]
            tf = self._tf_values[self.current_point]
            while True:
                # make sure enough time was left for data to accumulate in
                # the iq register...
                # compute remaining time for acquisition
                passed_duration = timeit.default_timer() - self.time_last_point
                #DO NOT USE time.time(). This gets updated only every 1 ms or so.
                remaining_duration = self.time_per_point - passed_duration
                if remaining_duration >= 0.002:
                    # sleeping in the ms range becomes inaccurate, in this case, we
                    # will just continuously check if enough time has passed. For
                    # averaging times longer than 2 ms, a 1 ms error in the sleep
                    # time is only a 50 % error, but less CPU intensive.
                    # see http://stackoverflow.com/questions/1133857/how-accurate-is-pythons-time-sleep
                    sleep(remaining_duration)
                # exit the loop when enough time has passed.
                if remaining_duration < 0:
                    break
            ##################################################
            # to remove once we are convinced it's clean...
            if self.current_point < 5:
                if self.current_point<0:
                    raise ValueError('current point is: ' + str(self.current_point))
                self._logger.debug("NA is currently reading point %s",
                                     self.current_point)
            ###################################################
            # only one read operation per point is this one
            y = self.iq._nadata_total/self._cached_na_averages
            amp = self.amplitude  # get amplitude for normalization
            if amp == 0:  # normalize immediately
                y *= self._rescale  # avoid division by zero
            else:
                y *= self._rescale / amp
            # correct for network analyzer transfer function (AC-filter and delay)
            y /= tf
            return x, y, amp

    def _prepare_for_next_point(self):
        """
        Sets everything for next point
        """
        self.current_point += 1
        if self.current_point < self.points:
            # writing to iq.frequency triggers the acquisition
            # negative index means "PRETRACE_POINT"--> acquire with start_freq
            self.iq.frequency = self.x[max(self.current_point, 0)]
        #else:
        #    # turn off the modulation when done
        #    self.iq.amplitude = 0
        # check averaging time from now
        self.time_last_point = timeit.default_timer()

    def _values(self):
        """
        Returns
        -------
        A generator of successive values for the na curve.
        The generator can be used in a for loop:
        for val in na.values():
            print val
        or individual values can be fetched successively by calling
        values = na.values()
        val1 = next(values) # avoid values.next() as it doesn't work with python 3
        val2 = next(values)

        values are made of a triplet (freq, complex_response, amplitude)
        """
        try:
            while self.current_point < self.points:
                    result = self._get_current_point()
                    self._prepare_for_next_point()
                    if result is not None:
                        x, y, amp = result
                        self.threshold_hook(y)  # call a hook function for the user
                        # replace frequency axis by time in zerospan mode:
                        if self.start_freq == self.stop_freq:
                            x = timeit.default_timer()
                        yield (x, y, amp)
                    else:
                        yield None
        except Exception as e:
            self.iq._logger.info("NA output turned off due to an exception")
            raise e
        finally:
            self.iq.on = False

    def curve(self, **kwds):  # amplitude can be limited
        """
        High level function: this sets up the na and acquires a curve. See
        setup for the explanation of parameters. Contrary to functions
        starting with 'run_', here, the acquisition is blocking.

        Returns
        -------
        (array of frequencies, array of complex ampl, array of amplitudes)
        """
        self.setup(**kwds)
        xs = np.zeros(self.points, dtype=float)
        ys = np.zeros(self.points, dtype=complex)
        amps = np.zeros(self.points, dtype=float)

        self._logger.info("Estimated acquisition time: %.1f s",
                          self.time_per_point * (self.points+1))
        sys.stdout.flush()  # make sure the time is shown immediately

        # set pseudo-acquisition of first point to supress transient effects
        self.iq.amplitude = self.amplitude
        self.iq.frequency = self.start_freq
        # sleep(self.time_per_point)
        for index in range(self.PRETRACE_POINTS):
            # "burn" the first PRETRACE_POINTS
            assert(next(self.values_generator) is None)
        for index, (x, y, amp) in enumerate(self.values_generator):
            xs[index] = x
            ys[index] = y
            amps[index] = amp
        return xs, ys, amps

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

    def save_curve(self):
        """
        Saves the curve that is currently displayed in the gui in the db_system. Also, returns the curve.
        """
        self.current_attributes['name'] = self.current_attributes['curve_name']
        return self._save_curve(x_values=self.x,
                                y_values=self.y_averaged,
                                **self.current_attributes)

    def run_continuous(self):
        """
        Launch a continuous acquisition where successive chunks are averaged with each others. The result is averaged
        in self.y
        """
        self.running_state = "running_continuous"

    def run_single(self):
        """
        Acquires a single scan. The result, once available, will be in self.x, self.y
        """
        self.running_state = "running_single"

    def pause(self):
        """
        Pauses the current acquistion. The acquisition can be resumed later
        """
        if self.running_state == "running_continuous":
            self.running_state = "paused_continuous"
        if self.running_state == "running_single":
            self.running_state = "paused_single"

    def stop(self):
        """
        Stops definitively the acquisition (next call to run_continuous will
        restart from 0)
        """
        self.running_state = 'stopped'

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
