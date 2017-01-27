from __future__ import division
from pyrpl.modules import SoftwareModule
from . import Signal
from pyrpl.attributes import SelectAttribute, SelectProperty, FloatProperty, FrequencyProperty, PhaseProperty
from pyrpl.widgets.module_widgets import LockboxInputWidget
from pyrpl.hardware_modules.dsp import DSP_INPUTS

import scipy
import numpy as np
import logging

logger = logging.getLogger(__name__)


class InputSignal(SoftwareModule):
    """
    An input signal allows to convert a measured voltage into the value of the
    model's physical variable in *unit*. The signal can be calibrated by
    taking a curve while scanning an output.
      - calibrate()
      -
    """
    section_name = 'input'  # name of the input
    gui_attributes = ["input_channel"]
    setup_attributes = gui_attributes + ["min", "max", "mean", "rms"]
    input_channel = SelectProperty(options=sorted(DSP_INPUTS.keys()))  # ['in1', 'in2']) # adc
    # Is it desirable to be allowed to select any internal signal?
    model_cls = None # Model class to which this input belongs.
    widget_class = LockboxInputWidget
    min = FloatProperty()
    max = FloatProperty()
    mean = FloatProperty()
    rms = FloatProperty(min=0, max=2)

    """
    def __init__(self, model):
        self.model = model
        super(InputSignal, self).__init__(model)
    """

    def init_module(self):
        """
        lockbox is the lockbox instance to which this input belongs.
        """
        self.lockbox = self.parent
        self.parameters = dict()
        self.plot_range = np.linspace(-5, 5, 200)

    @property
    def model(self):
        return self.parent.model

    def acquire(self):
        """
        returns an experimental curve in V obtained from a sweep of the lockbox.
        """
        self.lockbox.sweep()
        scope = self.pyrpl.scopes.pop(self.name)
        try:
            if not "sweep" in scope.states:
                scope.save_state("sweep")
            scope.load_state("sweep")
            scope.setup(input1=self.signal(), input2=self.lockbox.asg)
            curve = scope.curve(ch=1, timeout=0.1+2./self.lockbox.asg.frequency)
        finally:
            self.pyrpl.scopes.free(scope)
        return curve

    def get_stats_from_curve(self, curve):
        """
        gets the mean, min, max, rms value of curve (into the corresponding self's attributes)
        """
        self.mean = curve.mean()
        self.rms = curve.std()
        self.min = curve.min()
        self.max = curve.max()

    def calibrate(self):
        """
        This function should be reimplemented to measure whatever property of the curve is needed by expected_signal
        """
        curve = self.acquire()
        self.get_stats_from_curve(curve)
        if self.widget is not None:
            self.update_graph()

    def update_graph(self):
        if self.widget is not None:
            y = self.expected_signal(self.plot_range)
            self.widget.show_graph(self.plot_range, y)

    def expected_signal(self, variable):
        """
        Returns the value of the expected signal in V, depending on the variable value "variable". The parameters in
        self.parameters should have been calibrated beforehand.
        """
        raise NotImplementedError("Formula relating variable and parameters to output should be implemented in derived "
                                  "class")

    def expected_slope(self, variable):
        """
        Returns the slope of the expected signal wrt variable at a given value of the variable.
        """
        return scipy.misc.derivative(self.expected_signal,
                                     variable,
                                     dx=1e-9,
                                     n=1,  # first derivative
                                     order=3)

    def inverse(self, func, y, x0, args=()):
        """
        Finds a solution x to the equation y = func(x) in the
        vicinity of x0.

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


class InputDirect(InputSignal):
    section_name = 'direct_input'
    def signal(self):
        return self.input_channel


#class InputInternal(InputSignal): # Maybe the hierarchy should be the opposite...
#    section_name = 'internal_signal'
#    input_channel = SelectProperty(options=sorted(DSP_INPUTS.keys()))
#
#    def signal(self):
#        return self.input_channel


class PdhFrequencyProperty(FrequencyProperty):
    def set_value(self, instance, value):
        super(PdhFrequencyProperty, self).set_value(instance, value)
        instance.iq.frequency = value
        return value


class PdhAmplitudeProperty(FloatProperty):
    def set_value(self, instance, value):
        super(PdhAmplitudeProperty, self).set_value(instance, value)
        instance.iq.amplitude = value
        return value


class PdhPhaseProperty(PhaseProperty):
    def set_value(self, instance, value):
        super(PdhPhaseProperty, self).set_value(instance, value)
        instance.iq.phase = value
        return value


class PdhModOutputProperty(SelectProperty):
    def set_value(self, instance, value):
        super(PdhModOutputProperty, self).set_value(instance, value)
        instance.iq.output_direct = value
        return value


class PdhQuadratureFactorProperty(FloatProperty):
    def set_value(self, instance, value):
        super(PdhQuadratureFactorProperty, self).set_value(instance, value)
        instance.iq.quadrature_factor = value
        return value


class InputIQ(InputDirect):
    section_name = 'iq'
    gui_attributes = InputSignal.gui_attributes + ['mod_freq',
                                                   'mod_amp',
                                                   'mod_phase',
                                                   'quadrature_factor',
                                                   'mod_output']
    setup_attributes = gui_attributes + ["min", "max", "mean", "rms"]
    mod_freq = PdhFrequencyProperty()
    mod_amp = PdhAmplitudeProperty()
    mod_phase = PdhPhaseProperty()
    quadrature_factor = PdhQuadratureFactorProperty()
    mod_output = PdhModOutputProperty(['out1', 'out2'])

    def init_module(self):
        super(InputIQ, self).init_module()
        self._iq = None
        self.setup()

    def clear(self):
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
        print self.input_channel,"fffffffffffffffff"
        self.iq.setup(frequency=self.mod_freq,
                      amplitude=self.mod_amp,
                      phase=self.mod_phase,
                      input=self.input_channel,
                      gain=0,
                      bandwidth=[1e6, 1e6],
                      acbandwidth=1e6,
                      quadrature_factor=self.quadrature_factor,
                      output_signal='quadrature',
                      output_direct=self.mod_output)
