from __future__ import division
import scipy
import numpy as np
import logging
from ....attributes import SelectAttribute, SelectProperty, FloatProperty, FrequencyProperty, PhaseProperty, \
    FilterProperty, FrequencyRegister
from ....widgets.module_widgets import LockboxInputWidget
from ....hardware_modules.dsp import DSP_INPUTS
from ....pyrpl_utils import time
from ....module_attributes import ModuleProperty
from .. import LockboxModule, LockboxModuleDictProperty

logger = logging.getLogger(__name__)


class CalibrationData(LockboxModule):
    """ class to hold the calibration data of an input signal """
    _setup_attributes = ["min", "max", "mean", "rms"]
    _gui_attributes = []
    min = FloatProperty(doc="min of the signal in V over a lockbox sweep")
    max = FloatProperty(doc="max of the signal in V over a lockbox sweep")
    mean = FloatProperty(doc="mean of the signal in V over a lockbox sweep")
    rms = FloatProperty(min=0, max=2, doc="rms of the signal in V over a "
                                          "lockbox sweep")

    @property
    def amplitude(self):
        """ small helper function for expected signal """
        return 0.5 * (self.max - self.min)


    @property
    def offset(self):
        """ small helper function for expected signal """
        return 0.5 * (self.max + self.min)

    def get_stats_from_curve(self, curve):
        """
        gets the mean, min, max, rms value of curve (into the corresponding
        self's attributes).
        """
        self.mean = curve.mean()
        self.rms = curve.std()
        self.min = curve.min()
        self.max = curve.max()


class Signal(LockboxModule):
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
        return self.mean / self.expected_amplitude

    @property
    def relative_rms(self):
        """
        returns the ratio between the measured rms value and the expected mean.
        """
        # compute relative quantity
        return self.rms / self.expected_amplitude


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


    # input_signal selects the input signal of the module from DSP modules and logical signals of the lockbox
    input_signal = SelectProperty(options=(lambda instance:
                                        list(DSP_INPUTS.keys()) +
                                        list(instance.lockbox.signals.keys())),
                 doc="the dsp module or lockbox signal used as input signal")

    def _input_signal_dsp_module(self):
        """ returns the dsp signal corresponding to input_signal"""
        signal = self.input_signal
        try:
            signal = self.lockbox.signals[self.input_signal].signal()
        except:  # do not insist on this to work. if it fails, just return the direct value of input_channel
            pass
        return signal

    def signal(self):
        """ returns the signal corresponding to this module that can be used to connect the signal to other modules.
        By default, this is the direct input signal. """
        return self._input_signal_dsp_module()

    def sweep_acquire(self):
        """
        returns an experimental curve in V obtained from a sweep of the
        lockbox.
        """
        self.lockbox.sweep()
        with self.pyrpl.scopes.pop(self.name) as scope:
            if "sweep" in scope.states:
                scope.load_state("sweep")
            else:
                scope.setup(input1=self.signal(),
                            input2=self.lockbox.outputs[self.lockbox.default_sweep_output].pid.output_direct,
                            trigger_source=self.lockbox.asg.name,
                            duration=2. / self.lockbox.asg.frequency,
                            ch1_active=True,
                            ch2_active=False,
                            average=True,
                            running_state='running_continuous',
                            rolling_mode=False)
                scope.save_state("autosweep")
            curve1, curve2 = scope.curve(timeout=1. / self.lockbox.asg.frequency + scope.duration)
        return curve1

    def calibrate(self):
        """
        This function should be reimplemented to measure whatever property of
        the curve is needed by expected_signal.
        """
        curve = self.sweep_acquire()
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
        of the variable.
        """
        return scipy.misc.derivative(self.expected_signal,
                                     variable,
                                     dx=1e-9,
                                     n=1,  # first derivative
                                     order=3)

    # temporarily broken
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

    def _init_module(self):
        """
        lockbox is the lockbox instance to which this input belongs.
        """
        self.parameters = dict()
        self.plot_range = np.linspace(-5, 5, 200)
        self._lasttime = -1e10

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
    def calibrate(self):
        pass


class IqFrequencyProperty(FrequencyProperty):
    def __init__(self, **kwargs):
        super(IqFrequencyProperty, self).__init__(**kwargs)
        self.max = FrequencyRegister.CLOCK_FREQUENCY / 2.0

    def set_value(self, instance, value):
        super(IqFrequencyProperty, self).set_value(instance, value)
        instance.iq.frequency = value
        return value


class IqAmplitudeProperty(FloatProperty):
    def set_value(self, instance, value):
        super(IqAmplitudeProperty, self).set_value(instance, value)
        instance.iq.amplitude = value
        return value


class IqPhaseProperty(PhaseProperty):
    def set_value(self, instance, value):
        super(IqPhaseProperty, self).set_value(instance, value)
        instance.iq.phase = value
        return value


class IqModOutputProperty(SelectProperty):
    def set_value(self, instance, value):
        super(IqModOutputProperty, self).set_value(instance, value)
        instance.iq.output_direct = value
        return value


class IqQuadratureFactorProperty(FloatProperty):
    def set_value(self, instance, value):
        super(IqQuadratureFactorProperty, self).set_value(instance, value)
        instance.iq.quadrature_factor = value
        return value

class IqFilterProperty(FilterProperty):
    def set_value(self, instance, val):
        try:
            val = list(val)
        except:
            val = [val, val]  # preferentially choose second order filter
        instance.iq.bandwidth = val
        super(IqFilterProperty, self).set_value(instance, val)
        return val

    def valid_frequencies(self, module):
        # only allow the low-pass filter options (exclude negative high-pass options)
        return [v for v in module.iq.__class__.bandwidth.valid_frequencies(module.iq) if v >= 0]

class InputIq(InputDirect):
    """ Base class for demodulated signals. A derived class must implement
    the method expected_signal (see InputPdh in fabryperot.py for example)"""
    _gui_attributes = ['mod_freq',
                       'mod_amp',
                       'mod_phase',
                       'quadrature_factor',
                       'mod_output',
                       'bandwidth']
    _setup_attributes = _gui_attributes

    mod_freq = IqFrequencyProperty()
    mod_amp = IqAmplitudeProperty()
    mod_phase = IqPhaseProperty()
    quadrature_factor = IqQuadratureFactorProperty()
    mod_output = IqModOutputProperty(['out1', 'out2'])
    bandwidth = IqFilterProperty()

    def _init_module(self):
        super(InputIq, self)._init_module()
        self._iq = None
        self.setup()

    def _clear(self):
        self.pyrpl.iqs.free(self.iq)
        super(InputIq, self)._clear()

    def signal(self):
        return self.iq

    @property
    def iq(self):
        if self._iq is None:
            self._iq = self.pyrpl.iqs.pop(self.name)
        return self._iq

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
                      acbandwidth=self.mod_freq/100.0,
                      quadrature_factor=self.quadrature_factor,
                      output_signal='quadrature',
                      output_direct=self.mod_output)

