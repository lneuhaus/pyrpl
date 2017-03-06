from __future__ import division
from . import Signal
from ....attributes import SelectAttribute, SelectProperty, FloatProperty, FrequencyProperty, PhaseProperty, \
    FilterProperty, FrequencyRegister
from ....widgets.module_widgets import LockboxInputWidget
from ....hardware_modules.dsp import DSP_INPUTS
from ....pyrpl_utils import time
import scipy
import numpy as np
import logging

logger = logging.getLogger(__name__)


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
    _section_name = 'input'  # name of the input
    _setup_attributes = ["input_channel", "min", "max", "mean", "rms"]
    _gui_attributes = ["input_channel"]
    input_channel = SelectProperty(options=sorted(DSP_INPUTS.keys()),
                                   doc="the redpitaya dsp input representing "
                                       "the signal"
                                   )  # ['in1', 'in2']) # adc
    # Is it desirable to be allowed to select any internal signal?
    model_cls = None  # Model class to which this input belongs.
    _widget_class = LockboxInputWidget
    min = FloatProperty(doc="min of the signal in V over a lockbox sweep")
    max = FloatProperty(doc="max of the signal in V over a lockbox sweep")
    mean = FloatProperty(doc="mean of the signal in V over a lockbox sweep")
    rms = FloatProperty(min=0, max=2, doc="rms of the signal in V over a "
                                          "lockbox sweep")

    """
    def __init__(self, model):
        self.model = model
        super(InputSignal, self).__init__(model)
    """

    def _init_module(self):
        """
        lockbox is the lockbox instance to which this input belongs.
        """
        self.parameters = dict()
        self.plot_range = np.linspace(-5, 5, 200)
        self._lasttime = -1e10

#    @property
#    def c(self):
#        # inputs are in extra section 'inputs' for better visibility
#        return super(InputSignal, self).c._get_or_create('inputs.'+self.name)

    @property
    def model(self):
        return self.parent.model

    def acquire(self):
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
                            input2=self.lockbox._get_output(
                                self.lockbox.default_sweep_output).pid.output_direct,
                            trigger_source=self.lockbox.asg.name,
                            duration=2./self.lockbox.asg.frequency,
                            ch1_active=True,
                            ch2_active=False,
                            average=True,
                            running_continuous=False,
                            rolling_mode=False)
                scope.save_state("autosweep")
            curve = scope.curve(ch=1,
                                timeout=2./self.lockbox.asg.frequency+0.1)
        return curve

    def get_stats_from_curve(self, curve):
        """
        gets the mean, min, max, rms value of curve (into the corresponding
        self's attributes).
        """
        self.mean = curve.mean()
        self.rms = curve.std()
        self.min = curve.min()
        self.max = curve.max()

    @property
    def expected_amplitude(self):
        return (self.max-self.min)/2.0

    @property
    def _sampler_time(self):
        try:
            return self.lockbox._sampler_time
        except:
            return 0.01

    def mean_rms(self):
        """
        returns a tuple containing the mean and rms value of the measured
        signal in volts.
        """
        if time() - self._lasttime >= self._sampler_time:
            self._lastmean, self._lastrms = self.pyrpl.rp.sampler.mean_stddev(self.signal(),
                                                                              t=self._sampler_time)
            self._lasttime = time()
        return self._lastmean, self._lastrms

    def relative_mean(self):
        """
        returns the ratio between the measured mean value and the expected one.
        """
        # get fresh data
        mean, rms = self.mean_rms()
        # compute relative quantity
        return mean/self.expected_amplitude

    def relative_rms(self):
        """
        returns the ratio between the measured rms value and the expected mean.
        """
        # get fresh data
        mean, rms = self.mean_rms()
        # compute relative quantity
        return rms/self.expected_amplitude

    def calibrate(self):
        """
        This function should be reimplemented to measure whatever property of
        the curve is needed by expected_signal.
        """
        curve = self.acquire()
        self.get_stats_from_curve(curve)
        # log calibration values
        self._logger.info("%s calibration successful - Min: %.3f  Max: %.3f  Mean: %.3f  Rms: %.3f",
                          self.name,
                          self.min, self.max, self.mean, self.rms)
        # update graph in lockbox
        self.lockbox._signal_launcher.input_calibrated.emit([self])

#    def update_graph(self):
#        if self._widget is not None:
#            y = self.expected_signal(self.plot_range)
#            self._widget.show_graph(self.plot_range, y)

    def expected_signal(self, variable):
        """
        Returns the value of the expected signal in V, depending on the
        variable value "variable".
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

    def inverse(self, func, y, x0, args=()):
        """
        Finds a solution x to the equation y = func(x) in the vicinity of x0.

        Parameters
        ----------
        func: function
            the function
        y: float or np.array(,dtype=float)
            the desired value of the function
        x0: float
            the starting point for the search
        args: tuple
            optional arguments to pass to func

        Returns
        -------
        x: float
            the solution. None if no inverse could be found.
        """
        try:
            inverse = [self._inverse(self.expected_signal, yy, x0, args=args) for yy in y]
            if len(inverse) == 1:
                return inverse[0]
            else:
                return inverse
        except TypeError:
            def myfunc(x, *args):
                return func(x, *args) - y
            solution, infodict, ier, mesg = scipy.optimize.fsolve(
                         myfunc,
                         x0,
                         args=args,
                         xtol=1e-6,
                         epsfcn=1e-8,
                         fprime=self.__getattribute__(func.__name__+'_slope'),
                         full_output=True)
            if ier == 1:  # means solution was found
                return solution[0]
            else:
                return None

    def clear(self):
        """
        Free all resources owned by this input
        """
        pass

    def variable(self):
        """
        Estimates the model variable from the current value of the input.
        """
        curve = self.acquire()
        act = curve.mean()
        set = self.lockbox.setpoint
        variable = self.inverse(act, set)
        if variable is not None:
            return variable
        else:
            logger.warning("%s could not be estimated. Run a calibration!",
                           self._variable)
            return None

    def create_widget(self):
        widget = super(InputSignal, self).create_widget()
        try:
            self.update_graph()
        except:
            pass
        return widget

    def clear(self):
        """ implements the freeing of all resources in child classes"""
        pass

class InputDirect(InputSignal):
    _section_name = 'direct_input'
    def signal(self):
        return self.input_channel


class InputFromOutput(InputDirect):
    _section_name = 'input_from_output'

    def expected_signal(self, x):
        return x

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
    _section_name = 'iq'
    _gui_attributes = InputSignal._gui_attributes + ['mod_freq',
                                                   'mod_amp',
                                                   'mod_phase',
                                                   'quadrature_factor',
                                                   'mod_output',
                                                   'bandwidth']

class InputIq(InputDirect):
    """ Base class for demodulated signals. A derived class must implement
    the method expected_signal (see InputPdh in fabryperot.py for example)"""
    _section_name = 'iq'
    _gui_attributes = InputSignal._gui_attributes + ['mod_freq',
                                                     'mod_amp',
                                                     'mod_phase',
                                                     'quadrature_factor',
                                                     'mod_output',
                                                     'bandwidth']

    _setup_attributes = _gui_attributes + ["min", "max", "mean", "rms"]
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

    def clear(self):
        super(InputIq, self).clear()
        self.pyrpl.iqs.free(self.iq)

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
                      input=self.input_channel,
                      gain=0,
                      bandwidth=self.bandwidth,
                      acbandwidth=self.mod_freq/100.0,
                      quadrature_factor=self.quadrature_factor,
                      output_signal='quadrature',
                      output_direct=self.mod_output)

class InputFromOutput(InputDirect):
    _section_name = 'input_from_output'

    def expected_signal(self, variable):
        return variable

