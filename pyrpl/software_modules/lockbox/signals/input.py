from pyrpl.modules import SoftwareModule
from . import Signal
from pyrpl.attributes import SelectAttribute, SelectProperty, FloatProperty, FrequencyProperty, PhaseProperty

import scipy
import logging

logger = logging.getLogger(__name__)

class InputSignal(SoftwareModule):
    """
    An input signal allows to convert a measured voltage into the value of the model's physical variable in *unit*.
    The signal can be calibrated by taking a curve while scanning an output.
      - calibrate()
      -
    """
    section_name = 'input'  # name of the input
    gui_attributes = ["adc"]
    setup_attributes = gui_attributes
    adc = SelectProperty(options=['adc1', 'adc2']) # adc
    model_cls = None # Model class to which this input belongs.

    def init_module(self):
        """
        lockbox is the lockbox instance to which this input belongs.
        """
        self.lockbox = self.parent
        self.parameters = dict()

    def acquire(self):
        """
        returns an experimental curve in V obtained from a sweep of the lockbox.
        """
        self.lockbox.sweep()

    def calibrate(self):
        """
        This function should be reimplemented to measure whatever property of the curve is needed by expected_signal
        """
        curve = self.acquire()
        self.parameters = dict(mean=curve.mean(), rms=curve.rms())

    def expected_signal(self, variable):
        """
        Returns the value of the expected signal in V, depending on the variable value "variable". The parameters in
        self.parameters should have been calibrated beforehand.
        """
        raise NotImplementedError("Formula relating variable and parameters to output should be implemented in derived "
                                  "class")

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


class InputDirect(InputSignal):
    section_name = 'direct_input'


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


class InputPdh(InputSignal):
    section_name = 'pdh'
    mod_freq   = PdhFrequencyProperty()
    mod_amp    = PdhAmplitudeProperty()
    mod_phase  = PdhPhaseProperty()
    mod_output = PdhModOutputProperty(['dac1', 'dac2'])

    def init_module(self):
        self._iq = None

    @property
    def iq(self):
        if self._iq is None:
            self._iq = self.pyrpl.pop(self.name)
        return self.iq

    def _setup(self):
        """
        setup a PDH error signal using the attribute values
        """
        self.iq.setup(frequency=self.frequency,
                      amplitude=self.amplitude,
                      phase=self.phase,
                      input=self.adc,
                      gain=0,
                      quadrature_factor=0.01,
                      output='quadrature',
                      output_direct=self.mod_output)