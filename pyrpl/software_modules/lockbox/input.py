from __future__ import division
import scipy
import numpy as np
import logging
from ...attributes import SelectProperty, FloatProperty, FrequencyProperty, \
    PhaseProperty, FilterProperty, FrequencyRegister, ProxyProperty
from ...widgets.module_widgets import LockboxInputWidget
from ...hardware_modules.dsp import DSP_INPUTS, InputSelectProperty, all_inputs
from ...pyrpl_utils import time, recursive_getattr
from ...module_attributes import ModuleProperty
from ...software_modules.lockbox import LockboxModule, LockboxModuleDictProperty
from ...modules import SignalModule
from ...software_modules.module_managers import InsufficientResourceError

logger = logging.getLogger(__name__)


class CalibrationData(LockboxModule):
    """ class to hold the calibration data of an input signal """
    _setup_attributes = ["min", "max", "mean", "rms", "_analog_offset", "_asg_phase"]
    _gui_attributes = []
    min = FloatProperty(doc="min of the signal in V over a lockbox sweep")
    max = FloatProperty(doc="max of the signal in V over a lockbox sweep")
    mean = FloatProperty(doc="mean of the signal in V over a lockbox sweep")
    rms = FloatProperty(min=0, max=2, doc="rms of the signal in V over a "
                                          "lockbox sweep")
    _analog_offset = FloatProperty(default=0.0, doc="analog offset of the signal")
    _analog_offset_rms = FloatProperty(default=0.0, doc="rms of the analog offset of the signal")
    _asg_phase = PhaseProperty(doc="Phase of the asg when error signal is centered "
                                   "in calibration. Not used by all signals. ")

    @property
    def amplitude(self):
        """ small helper function for expected signal """
        return 0.5 * (self.max - self.min)

    @property
    def peak_to_peak(self):
        """ small helper function for expected signal """
        return self.max - self.min

    @property
    def offset(self):
        """ small helper function for expected signal """
        return 0.5 * (self.max + self.min)

    def get_stats_from_curve(self, curve):
        """
        gets the mean, min, max, rms value of curve (into the corresponding
        self's attributes).
        """
        if curve is None:
            self.logger.warning("Curve object for calibration is None. No calibration will be performed.")
        else:
            self.mean = curve.mean()
            self.rms = curve.std()
            self.min = curve.min()
            self.max = curve.max()


class Signal(LockboxModule, SignalModule):
    """
    represention of a physial signal. Can be either an imput or output signal.
    """
    _widget = None
    calibration_data = ModuleProperty(CalibrationData)

    def signal(self):
        """ derived class should define this method which yields the scope-
        compatible signal that can be used to monitor this signal"""
        raise ValueError("Please define the method 'signal()' if the Signal "
                         "%s to return a valid scope-compatible input.",
                         self.name)
        return 'off'

    def get_analog_offset(self, duration=1.0):
        """ function to acquire the analog offset of the signal (with nothing connected).
         This offset is subtracted from all raw signals"""
        # make sure the lockbox is unlocked, just in case
        self.lockbox.unlock()
        # sample the input with a rather long duration to get a good average
        self.stats(t=duration)
        current_residual_offset, current_rms = self.mean, self.rms
        last_offset = self.calibration_data._analog_offset
        # current_residual_offset = current_offset - last_offset
        current_offset = last_offset + current_residual_offset
        self.calibration_data._analog_offset = current_offset
        self.calibration_data._analog_offset_rms = current_rms
        self._logger.info("Calibrated analog offset of signal %s. "
                          "Old value: %s, new value: %s, difference: %s. "
                          "Rms of the measurement: %s.",
                          self.name,
                          last_offset,
                          self.calibration_data._analog_offset,
                          current_residual_offset,
                          current_rms)

    ##################################################
    # Sampler routines for diagnostics of the signal #
    ##################################################
    @property
    def sampler_time(self):
        """ specifies the duration over which to sample a signal """
        if hasattr(self, '_sampler_time') and self._sampler_time is not None:
            return self._sampler_time
        elif hasattr(self.lockbox, '_sampler_time') and self.lockbox._sampler_time is not None:
            return self.lockbox._sampler_time
        else:
            return 0.01

    def stats(self, t=None):
        """
        returns a tuple containing the mean, rms, max, and min of the signal.
        """
        # generate new samples for mean, rms, max, min if
        # a) executed for the first time,
        # b) nonstandard sampler time
        # c) last sample older than sampler time
        # Point c) ensures that we can call stats several times in
        # immediate succession, e.g. to get mean and rms
        if not hasattr(self, '_lasttime') or t is not None or \
                time() - self._lasttime >= self.sampler_time:
            # choose sampler time
            if t is None:
                t = self.sampler_time
            # get fresh data
            self._lastmean, self._lastrms, self._lastmax, self._lastmin\
                = self.pyrpl.rp.sampler.stats(self.signal(), t=t)
            # subtract analog offset from all non-relative values
            self._lastmean -= self.calibration_data._analog_offset
            self._lastmax -= self.calibration_data._analog_offset
            self._lastmin -= self.calibration_data._analog_offset
            # save a timestamp and the employed sampler time
            self._lasttime = time()
            self._lastt = t
        return self._lastmean, self._lastrms, self._lastmax, self._lastmin

    @property
    def mean(self):
        # get fresh data
        mean, rms, max, min= self.stats()
        # compute relative quantity
        return mean

    @property
    def rms(self):
        # get fresh data
        mean, rms, max, min= self.stats()
        # compute relative quantity
        return rms

    @property
    def max(self):
        # get fresh data
        mean, rms, max, min= self.stats()
        # compute relative quantity
        return max

    @property
    def min(self):
        # get fresh data
        mean, rms, max, min= self.stats()
        # compute relative quantity
        return min

    @property
    def relative_mean(self):
        """
        returns the ratio between the measured mean value and the expected one.
        """
        # compute relative quantity
        return self.mean / self.calibration_data.amplitude

    @property
    def relative_rms(self):
        """
        returns the ratio between the measured rms value and the expected mean.
        """
        # compute relative quantity
        return self.rms / self.calibration_data.amplitude

    def diagnostics(self, duration = 1.0):
        """
        example code for lock diagnostics:

        Parameters
        ----------
        duration: duration over which to average

        Returns
        -------
        relative rms of the signal, normalized by
        """
        # samples the input over duration
        self.stats(t=duration)
        return self.relative_rms


class InputSignal(Signal):
    """
    A Signal that corresponds to an inputsignal of the DSPModule inside the
    RedPitaya. Moreover, the signal should provide a function to convert the
    measured voltage into the value of the model's physical variable in
    *unit*. The signal can be calibrated by taking a curve while scanning
    an output.

    module attributes (see BaseModule):
    -----------------------------------
    - input_channel: the redpitaya dsp input representing the signal
    - min: min of the signal in V over a lockbox sweep
    - max: max of the signal in V over a lockbox sweep
    - mean: mean of the signal in V over a lockbox sweep
    - rms: rms of the signal in V over a lockbox sweep

    public methods:
    ---------------
    - acquire(): returns an experimental curve in V obtained from a sweep of
    the lockbox.
    - calibrate(): acquires a curve and determines all constants needed by
    expected_signal
    - expected_signal(variable): to be reimplemented in concrete derived class:
    Returns the value of the expected signal in V, depending on the variable
    value.
    - expected_slope: returns the slope of the expected signal wrt variable at
    a given value of the variable.
    - relative_mean(self): returns the ratio between the measured mean value
    and the expected one.
    - relative_rms(self): returns the ratio between the measured rms value and
    the expected mean.
    - variable(): Estimates the model variable from the current value of
    the input.
    """
    _setup_attributes = ["input_signal"]
    _gui_attributes = ["input_signal"]
    _widget_class = LockboxInputWidget
    plot_range = np.linspace(-5, 5, 200)  # range of setpoint values over which to plot signal

    input_signal = InputSelectProperty(call_setup=True,
                                       doc="the dsp module or lockbox "
                                            "signal used as input signal")

    def __init__(self, parent, name=None):
        # self.parameters = dict()
        self._lasttime = -1e10
        super(InputSignal, self).__init__(parent, name=name)

    def _input_signal_dsp_module(self):
        """ returns the dsp signal corresponding to input_signal"""
        signal = self.input_signal
        # problem arises if there is a long loop of logical signals -> iterate
        for i in range(5):  # try at most 5 hierarchy levels
            try:
                signal = recursive_getattr(self.pyrpl, signal).signal()
            except:  # do not insist on this to work as signal may be a str
                pass
            if signal in DSP_INPUTS:
                return signal
        # no break ever occured
        self._logger.warning("Input signal of input %s cannot be traced "
                             "to a valid dsp input (it yields %s). Input "
                             "will be turned 'off'.",
                             self.name, signal)
        return 'off'


    def signal(self):
        """ returns the signal corresponding to this module that can be used to connect the signal to other modules.
        By default, this is the direct input signal. """
        return self._input_signal_dsp_module()

    def sweep_acquire(self):
        """
        returns an experimental curve in V obtained from a sweep of the
        lockbox.
        """
        try:
            with self.pyrpl.scopes.pop(self.name) as scope:
                self.lockbox._sweep()
                if "sweep" in scope.states:
                    scope.load_state("sweep")
                else:
                    scope.setup(input1=self.signal(),
                                input2=self.lockbox.outputs[self.lockbox.default_sweep_output].pid.output_direct,
                                trigger_source=self.lockbox.asg.name,
                                trigger_delay=0,
                                duration=1./self.lockbox.asg.frequency,
                                ch1_active=True,
                                ch2_active=True,
                                average=True,
                                trace_average=1,
                                running_state='stopped',
                                rolling_mode=False)
                    scope.save_state("autosweep")
                curve1, curve2 = scope.curve(timeout=1./self.lockbox.asg.frequency+scope.duration)
                times = scope.times
                curve1 -= self.calibration_data._analog_offset
                return curve1, times
        except InsufficientResourceError:
            # scope is blocked
            self._logger.warning("No free scopes left for sweep_acquire. ")
            return None, None

    def calibrate(self, autosave=False):
        """
        This function should be reimplemented to measure whatever property of
        the curve is needed by expected_signal.
        """
        curve, times = self.sweep_acquire()
        if curve is None:
            self._logger.warning('Aborting calibration because no scope is available...')
            return None
        self.calibration_data.get_stats_from_curve(curve)
        # log calibration values
        self._logger.info("%s calibration successful - Min: %.3f  Max: %.3f  Mean: %.3f  Rms: %.3f",
                          self.name,
                          self.calibration_data.min,
                          self.calibration_data.max,
                          self.calibration_data.mean,
                          self.calibration_data.rms)
        # update graph in lockbox
        self.lockbox._signal_launcher.input_calibrated.emit([self])
        # save data if desired
        if autosave:
            params = self.calibration_data.setup_attributes
            params['name'] = self.name+"_calibration"
            newcurve = self._save_curve(times, curve, **params)
            self.calibration_data.curve = newcurve
            return newcurve
        else:
            return None

    def expected_signal(self, variable):
        """
        Returns the value of the expected signal in V, depending on the
        setpoint value "variable".
        """
        raise NotImplementedError("Formula relating variable and parameters to output should be implemented in derived "
                                  "class")

    def expected_slope(self, variable):
        """
        Returns the slope of the expected signal wrt variable at a given value
        of the variable. May be overwritten by a more efficient (analytical) method
        in a derived class.
        """
        return scipy.misc.derivative(self.expected_signal,
                                     variable,
                                     dx=1e-9,
                                     n=1,  # first derivative
                                     order=3)

    def is_locked(self, loglevel=logging.INFO):
        """ returns whether the input is locked at the current stage """
        # supposed to be locked at this value
        setpoint = self.lockbox.current_stage.setpoint
        # current values
        actmean, actrms = self.mean, self.rms
        # get max, min of acceptable error signals
        error_threshold = self.lockbox.is_locked_threshold
        min = self.expected_signal(setpoint-error_threshold)
        max = self.expected_signal(setpoint+error_threshold)
        startslope = self.expected_slope(setpoint - error_threshold)
        stopslope = self.expected_slope(setpoint + error_threshold)
        # no guarantee that min<max
        if max < min:
            # swap them in this case
            max, min = min, max
        # now min < max
        # if slopes have unequal signs, the signal has a max/min in the
        # interval
        if startslope*stopslope <= 0:
            if startslope > stopslope:  # maximum in between, ignore upper limit
                max = np.inf
            elif startslope < stopslope:  # minimum, ignore lower limit
                min = -np.inf
        if actmean > max or actmean < min:
            self._logger.log(loglevel,
                             "Not locked at stage %s: "
                             "input %s value of %.2f +- %.2f (setpoint %.2f)"
                             "is not in error interval [%.2f, %.2f].",
                             self.lockbox.current_stage.name,
                             self.name,
                             actmean,
                             actrms,
                             self.expected_signal(setpoint),
                             min,
                             max)
            return False
        # lock seems ok
        self._logger.log(loglevel,
                         "Locked at stage %s: "
                         "input %s value is %.2f +- %.2f (setpoint %.2f).",
                         self.lockbox.current_stage.name,
                         self.name,
                         actmean,
                         actrms,
                         self.expected_signal(setpoint))
        return True


    # inverse is temporarily broken
    #
    # def inverse(self, func, y, x0, args=()):
    #     """
    #     Finds a solution x to the equation y = func(x) in the vicinity of x0.
    #
    #     Parameters
    #     ----------
    #     func: function
    #         the function
    #     y: float or np.array(,dtype=float)
    #         the desired value of the function
    #     x0: float
    #         the starting point for the search
    #     args: tuple
    #         optional arguments to pass to func
    #
    #     Returns
    #     -------
    #     x: float
    #         the solution. None if no inverse could be found.
    #     """
    #     try:
    #         inverse = [self._inverse(self.expected_signal, yy, x0, args=args) for yy in y]
    #         if len(inverse) == 1:
    #             return inverse[0]
    #         else:
    #             return inverse
    #     except TypeError:
    #         def myfunc(x, *args):
    #             return func(x, *args) - y
    #         solution, infodict, ier, mesg = scipy.optimize.fsolve(
    #                      myfunc,
    #                      x0,
    #                      args=args,
    #                      xtol=1e-6,
    #                      epsfcn=1e-8,
    #                      fprime=self.__getattribute__(func.__name__+'_slope'),
    #                      full_output=True)
    #         if ier == 1:  # means solution was found
    #             return solution[0]
    #         else:
    #             return None
    #
    # def variable(self):
    #     """
    #     Estimates the model variable from the current value of the input.
    #     """
    #     curve = self.sweep_acquire()
    #     act = curve.mean()
    #     set = self.lockbox.setpoint
    #     variable = self.inverse(act, set)
    #     if variable is not None:
    #         return variable
    #     else:
    #         logger.warning("%s could not be estimated. Run a calibration!",
    #                        self._variable)
    #         return None


    def _create_widget(self):
        widget = super(InputSignal, self)._create_widget()
        try:
            self.update_graph()
        except:
            pass
        return widget


class InputDirect(InputSignal):
    def expected_signal(self, x):
        return x


class InputFromOutput(InputDirect):
    def calibrate(self, autosave=False):
        """ no need to calibrate this """
        pass

    input_signal = InputSelectProperty(
        options=(lambda instance:
            ['lockbox.outputs.'+k for k in instance.lockbox.outputs.keys()]),
        doc="lockbox signal used as input")

    def is_locked(self, loglevel=logging.INFO):
        """ this is mainly used for coarse locking where significant
        effective deviations from the setpoint (in units of setpoint_variable)
        may occur. We therefore issue a warning and return True if is_locked is
        based on this output. """
        inputdsp = self.lockbox.signals[self.input_signal.split('.')[-1]].pid.input
        forwarded_input = None
        for inp in self.lockbox.inputs:
            if inp.signal() == inputdsp:
                forwarded_input = inp
                break
        if forwarded_input is not None:
            self._logger.debug("is_locked() for InputFromOutput '%s' is "
                               "forwarded to is_locked() of input signal '%s'.",
                               self.name, forwarded_input.name)
            return forwarded_input.is_locked(loglevel=loglevel)
        else:
            self._logger.warning("is_locked() for InputFromOutput '%s' is not "
                               "implemented. No input for forwarding found.",
                               self.name)
            return True

    def expected_signal(self, setpoint):
        """ it is assumed that the output has the linear relationship between
        setpoint change in output_unit per volt from the redpitaya, which
        is configured in the output parameter 'dc_gain'. We only need to
        convert units to get the output voltage bringing about a given
        setpoint difference. """
        # An example:
        # The configured output gain is 'output.dc_gain' nm/V.
        # setpoint_unit is cavity 'linewidth', the latter given by
        # 'lockbox._setpopint_unit_in_unit('nm')' (in nm).
        # Therefore, the output voltage corresponding to a change of
        # one linewidth is given (in V) by:
        # lockbox._setpopint_unit_in_unit('nm')/output.dc_gain
        output = self.lockbox.signals[self.input_signal.split('.')[-1]]
        output_unit = output.unit.split('/')[0]
        setpoint_in_output_unit = \
            setpoint * self.lockbox._setpoint_unit_in_unit(output_unit)
        return setpoint_in_output_unit / output.dc_gain


class IqQuadratureFactorProperty(FloatProperty):
    """ this is a direct link to quadrature_factor because we want to
    benefit from its validate_and_normalize function"""
    def set_value(self, instance, value):
        instance.iq.quadrature_factor = value
        return value

    def get_value(self, obj):
        return obj.iq.quadrature_factor


class IqFilterProperty(FilterProperty):
    def set_value(self, instance, val):
        try:
            val = list(val)
        except:
            val = [val, val]  # preferentially choose second order filter
        instance.iq.bandwidth = val
        super(IqFilterProperty, self).set_value(instance,
                                                self.get_value(instance))
        return val

    def get_value(self, instance):
        return instance.iq.bandwidth

    def valid_frequencies(self, module):
        # only allow the low-pass filter options (exclude negative high-pass options)
        return [v for v in module.iq.__class__.bandwidth.valid_frequencies(module.iq) if v >= 0]


class InputIq(InputSignal):
    """ Base class for demodulated signals. A derived class must implement
    the method expected_signal (see InputPdh in fabryperot.py for example)"""
    _gui_attributes = ['mod_freq',
                       'mod_amp',
                       'mod_phase',
                       'mod_output',
                       'bandwidth',
                       'quadrature_factor']
    _setup_attributes = _gui_attributes

    @property
    def acbandwidth(self):
        return self.mod_freq / 128.0

    # mod_freq = ProxyProperty("iq.frequency")
    # mod_amp = ProxyProperty("iq.amplitude")
    # mod_phase = ProxyProperty("iq.phase")
    # mod_output = ProxyProperty("iq.output_direct")
    # quadrature_factor = ProxyProperty("iq.quadrature_factor")
    # bandwidth = ProxyProperty("iq.bandwidth")

    mod_freq = FrequencyProperty(min=0.0,
                                 max = FrequencyRegister.CLOCK_FREQUENCY / 2.0,
                                 default = 0.0,
                                 call_setup = True)
    mod_amp = FloatProperty(min=-1, max=1, default=0.0, call_setup=True)
    mod_phase = PhaseProperty(call_setup=True)
    mod_output = SelectProperty(['out1', 'out2'], call_setup=True)
    quadrature_factor = IqQuadratureFactorProperty(call_setup=True)
    bandwidth = IqFilterProperty(call_setup=True)

    @property
    def iq(self):
        if not hasattr(self, '_iq') or self._iq is None:
            self._iq = self.pyrpl.iqs.pop(self.name)
        return self._iq

    def signal(self):
        return self.iq.name

    def _clear(self):
        self.pyrpl.iqs.free(self.iq)
        self._iq = None
        super(InputIq, self)._clear()

    def _setup(self):
        """
        setup a PDH error signal using the attribute values
        """
        self.iq.setup(frequency=self.mod_freq,
                      amplitude=self.mod_amp,
                      phase=self.mod_phase,
                      input=self._input_signal_dsp_module(),
                      gain=0,
                      bandwidth=self.bandwidth,
                      acbandwidth=self.acbandwidth,
                      quadrature_factor=self.quadrature_factor,
                      output_signal='quadrature',
                      output_direct=self.mod_output)
