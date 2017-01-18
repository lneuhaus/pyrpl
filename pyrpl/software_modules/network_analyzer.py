import logging
import sys
from time import sleep, time

from ..attributes import FilterAttribute
from ..attributes import FloatProperty, SelectProperty, FrequencyProperty, \
                        LongProperty, BoolProperty, StringProperty
from ..hardware_modules import DspModule # just to get the
from ..widgets.module_widgets import NaWidget

from . import SoftwareModule
from ..modules import GuiUpdater

from PyQt4 import QtCore, QtGui
import numpy as np


class NaAcBandwidth(FilterAttribute):
    def valid_frequencies(selfself, instance):
        return [freq for freq in instance.iq._valid_inputfilter_frequencies(instance.iq) if freq>=0]

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
    def set_value(self, module, val):
        old_val = module.state
        super(NaStateProperty, self).set_value(module, val)
        if val in ['running_continuous', 'running_single']:
            if old_val=="stopped":
                module.gui_updater.run()
            else:
                module.gui_updater.resume()
        if val in ['paused_continuous', 'paused_single', "stopped"]:
            module.gui_updater.pause()

"""
class RunningContinuousProperty(BoolProperty):
    def set_value(self, module, val):
        super(RunningContinuousProperty, self).set_value(module, val)
        if val:
            module.gui_updater.run()
        else:
            module.gui_updater.stop()
"""

class GuiUpdaterNA(GuiUpdater):
    point_updated = QtCore.pyqtSignal(int) # This signal is emitted when a point needs to be updated (added/changed)
    # The argument is the index of the point as found in module.y_averaged
    autoscale = QtCore.pyqtSignal()
    scan_finished = QtCore.pyqtSignal()

    def __init__(self, module):
        super(GuiUpdaterNA, self).__init__(module)
        self.datas = [None, None]
        self.timer_point = QtCore.QTimer()
        self.timer_point.setSingleShot(True)
        self.timer_point.timeout.connect(self.next_point)
        self.timer_point.start()

    def next_point(self):
        x, y, amp = self.module.get_current_point()
        cur = self.module.current_point
        self.module.y_current_scan[cur] = y
        self.module.y_averaged[cur] = (self.module.y_averaged[cur] * self.module.current_averages + y) \
                         / (self.module.current_averages + 1)
        self.module.x[cur] = x
        self.module.threshold_hook(y)
        if(self.module.current_point+1<self.module.points): # next point is still in the scan range
            self.module.prepare_for_next_point()
            self.point_updated.emit(self.module.current_point)
            self.timer_point.start()
        else: # end of scan
            self.module.current_averages += 1
            if self.module.state=='running_continuous':
                self.module.setup() # reset acquistion without resetting averaging
                self.timer_point.start()
            else:
                self.module.pause()
            self.scan_finished.emit()

    def run(self):
        self.module.setup()
        self.module.setup_averaging()
        self.module.prepare_for_next_point()
        self.timer_point.start()

    def resume(self):
        self.timer_point.start()

    def pause(self):
        self.timer_point.stop()

    def connect_widget(self, widget):
        super(GuiUpdaterNA, self).connect_widget(widget)
        self.autoscale.connect(widget.autoscale)
        self.point_updated.connect(widget.update_point)
        self.scan_finished.connect(widget.scan_finished)


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
    section_name = 'na'
    widget_class = NaWidget
    callback_attributes = ["input", # stops acquisition when one of these is changed
                          "acbandwidth",
                          "output_direct",
                          "start_freq",
                          "stop_freq",
                          "rbw",
                          "points",
                          "amplitude",
                          "logscale",
                          "infer_open_loop_tf",
                          "avg"]
    gui_attributes = callback_attributes + ["curve_name",
                                            "state"]
    setup_attributes = [attr for attr in gui_attributes if attr!='state']
    data = None

    def init_module(self):
        self.gui_updater = GuiUpdaterNA(self)
        self._logger = logging.getLogger(__name__)
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
        # possibly a bugfix:
        self.time_per_point = max(1.0 / self.rbw * (self.avg + self.sleeptimes), 1e-3)
        self.current_averages = 0
        self.time_last_point = 0
        self.state = 'stopped'

    input = SelectProperty(DspModule.inputs)
    output_direct = SelectProperty(DspModule.output_directs)
    start_freq = FrequencyProperty()
    stop_freq = FrequencyProperty()
    rbw = RbwAttribute()
    amplitude = FloatProperty(min=0, max=1, increment=1. / 2 ** 14)
    points = LongProperty(min=1, max=1e8)
    logscale = BoolProperty()
    infer_open_loop_tf = BoolProperty()
    avg = LongProperty(min=1)
    curve_name = StringProperty()
    acbandwidth = NaAcBandwidth(doc="Bandwidth of the input high-pass filter of the na.")
    state = NaStateProperty()

    def callback(self):
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
                np.log10(self.start),
                np.log10(self.stop),
                self.points,
                endpoint=True)
        else:
            self.x = np.linspace(self.start_freq, self.stop_freq, self.points, endpoint=True)
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
        # time_per_point is calculated at setup for speed reasons
        self.time_per_point = max(1.0 / self.rbw * (self.avg + self.sleeptimes), 1e-3)
        # setup averaging
        self.iq._na_averages = np.int(np.round(125e6 / self.rbw * self.avg))
        self.iq._na_sleepcycles = np.int(np.round(125e6 / self.rbw * self.sleeptimes))
        # compute rescaling factor of raw data
        self._rescale = 2.0 ** (-self.iq._LPFBITS) * 4.0  # 4 is artefact of fpga code
        self.current_point = -1
        self.iq.frequency = self.x[0]  # this triggers the NA acquisition
        self.time_last_point = time()
        self.values_generator = self.values()

    def setup_averaging(self):
        self.current_averages = 0
        self.current_attributes = self.get_setup_attributes()
        self.y_current_scan = np.zeros(self.points, dtype=complex)
        self.y_averaged = np.zeros(self.points, dtype=complex)
        self.gui_updater.timer_point.setInterval(self.time_per_point)

    @property
    def last_valid_point(self):
        return self.points - 1 if self.current_averages>0 else self.current_point

    @property
    def current_freq(self):
        """
        current frequency during the scan
        """
        return self.iq.frequency

    def get_current_point(self):
        """
        This function fetches the current point on the redpitaya.
        The function blocks until the time since the last point has reached
        time_per_point
        """
        # get the actual point's (discretized) frequency
        x = self.iq.frequency
        tf = self.transfer_function(x)
        # compute remaining time for acquisition
        passed_duration = time() - self.time_last_point
        remaining_duration = self.time_per_point - passed_duration
        if remaining_duration >= 0:
            sleep(remaining_duration)
        y = self.iq._nadata
        # get amplitude for normalization
        amp = self.amplitude
        # normalize immediately
        if amp == 0:
            y *= self._rescale  # avoid division by zero
        else:
            y *= self._rescale / amp
        # correct for network analyzer transfer function (AC-filter and delay)
        y /= tf
        return x, y, amp

    def prepare_for_next_point(self):
        """
        Sets everything for next point
        """
        self.current_point += 1
        if self.current_point < self.points:
            # writing to iq.frequency triggers the acquisition
            self.iq.frequency = self.x[self.current_point]
        else:
            # turn off the modulation when done
            self.iq.amplitude = 0
        self.time_last_point = time()  # check averaging time from now

    def values(self):
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
            #for point in xrange(self.points):
            while self.current_point < self.points:
                #self.current_point = point
                x, y, amp = self.get_current_point()
                # replace frequency axis by time in zerospan mode:
                if self.start == self.stop:
                    x = time()
                self.prepare_for_next_point(y)
                yield (x, y, amp)
        except Exception as e:
            self.iq._logger.info("NA output turned off due to an exception")
            raise e
        finally:
            self.iq.amplitude = 0
            self.iq.frequency = self.x[0]

    def curve(self, **kwds):  # amplitude can be limited
        """
        High level function: this sets up the na and acquires a curve. See setup for the explanation of parameters.

        Returns
        -------
        (array of frequencies, array of complex ampl, array of amplitudes)
        """

        self._setup(**kwds)
        #if not self._setup:
        #    raise NotReadyError("call setup() before first curve")
        xs = np.zeros(self.points, dtype=float)
        ys = np.zeros(self.points, dtype=complex)
        amps = np.zeros(self.points, dtype=float)

        self._logger.info("Estimated acquisition time: %.1f s",
                          self.time_per_point * (self.points+1))
        sys.stdout.flush()  # make sure the time is shown immediately

        # set pseudo-acquisition of first point to supress transient effects
        self.iq.amplitude = self.amplitude
        self.iq.frequency = self.start
        sleep(self.time_per_point)

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
        return self._save_curve(x_values=self.x,
                                y_values=self.y_averaged,
                                **self.current_attributes)

    def run_continuous(self):
        """
        Launch a continuous acquisition where successive chunks are averaged with each others. The result is averaged
        in self.y
        """
        self.state = "running_continuous"

    def run_single(self):
        """
        Acquires a single scan. The result, once available, will be in self.x, self.y
        """
        self.state = "running_single"

    def pause(self):
        """
        Pauses the current acquistion. The acquisition can be resumed later
        """
        if self.state == "running_continuous":
            self.state = "paused_continuous"
        if self.state == "running_single":
            self.state = "paused_single"

    def stop(self):
        """
        Stops definitely the acquisition (next call to run_continuous will restart from 0)
        """
        self.state = 'stopped'

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