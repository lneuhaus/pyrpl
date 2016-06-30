import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)


def getmodel(modeltype):
    try:
        return globals()[modeltype]
    except KeyError:
        # try to find a similar model with lowercase spelling
        for k in globals():
            if k.lower() == modeltype.lower():
                return globals()[k]
        logger.error("Model %s not found in model definition file %s",
                     modeltype, __file__)


class Model(object):
    " generic model object that will make smart use of its inputs and outputs"
    export_to_parent = ["sweep", "calibrate", "set_optimal_gain",
                        "unlock", "islocked", "lock", "help"]

    # independent variable that specifies the state of the system
    _variable = 'x'

    def __init__(self, parent=None):
        self.logger = logging.getLogger(__name__)
        if parent is None:
            self._parent = self
        else:
            self._parent = parent
        self.inputs = self._parent.inputs
        self.outputs = self._parent.outputs
        self._config = self._parent.c.model
        self._make_helpers()
        self.state = {'actual': {self._variable: 0},
                      'set': {self._variable: 0}}

    def _derivative(self, func, x, n=1, args=()):
        return scipy.misc.derivative(func,
                                     x,
                                     dx=1e-9,
                                     n=n,
                                     args=args,
                                     order=3)

    def _inverse(self, func, y, x0, args=()):
        """
        Finds a solution x to the equation y = func(x) in the
        vicinity of x0.

        Parameters
        ----------
        func: function
            the function
        y: float
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
        def myfunc(x, *args):
            return func(x, *args) - y
        solution, infodict, ier, mesg = scipy.optimize.fsolve(
                                     myfunc,
                                     x0,
                                     args=args,
                                     xtol=1e-9,
                                     full_output=True)
        if ier == 1:  # means solution was found
            return solution
        else:
            return None

    def _make_slope(self, fn):
        def fn_slope(x, *args):
            return self._derivative(fn, x, args=args)
        return fn_slope

    def _make_inverse(self, fn):
        def fn_inverse(y, x0, *args):
            return self._inverse(fn, y, x0, args=args)
        return fn_inverse

    def _make_helpers(self):
        # create any missing slope and inverse functions
        for input in self.inputs.values():
            # test if the slope was defined in the model
            if not hasattr(self, input._name+"_slope"):
                self.logger.debug("Making slope function for input %s",
                                  input._name)
                fn = self.__getattribute__(input._name)
                # bug removed a la http://stackoverflow.com/questions/3431676/creating-functions-in-a-loop
                self.__setattr__(input._name+"_slope",
                                 self._make_slope(fn))
            if not hasattr(self, input._name + "_inverse"):
                self.logger.debug("Making inverse function for input %s",
                                  input._name)
                fn = self.__getattribute__(input._name)
                self.__setattr__(input._name + "_inverse",
                                 self._make_inverse(fn))

    @property
    def variable(self):
        """ returns an estimate of the variable defined in _variable """
        inputname, input = self.inputs.items()[0]
        act = input.mean
        set = self.state["set"][self._variable]
        variable = self.__getattribute__(inputname+'_inverse')(act, set)
        # save in state buffer
        self.state["actual"][self._variable] = variable
        if variable is not None:
            return variable
        else:
            logger.warning("%s could not be estimated. Run a calibration!",
                           self._variable)
            return None

    def set_optimal_gain(self):
        factor = self.state["set"]["factor"]
        for output in self.outputs:
            output.set_optimal_gain(factor)

    def islocked(self):
        """ returns True if locked, else False"""
        if hasattr(self, self._variable):
            variable = self.__getattribute__(self._variable)
        else:
            variable = self.variable
        diff = variable - self.state["set"][self._variable]
        # first check if parameter error exceeds threshold
        if abs(diff) > self._config.lock.error_threshold:
            return False
        else:
            # test for output saturation
            for o in self.outputs.values():
                if o.issaturated:
                    return False
        # lock seems ok
        return True

    # unlock algorithm
    def unlock(self):
        for o in self.outputs.values():
            o.off()

    def sweep(self):
        """
        Enables the pre-configured sweep on all outputs.

        Returns
        -------
        duration: float
            The duration of one sweep period, as it is useful to setup the
            scope.
        """
        frequency = None
        for o in self.outputs.values():
            frequency = o.sweep()
        return 1.0 / frequency


    def _lock(self, input=None, factor=1.0, offset=None, **kwargs):
        """
        Locks all outputs to input.
        Parameters
        ----------
        input: Signal
          the input signal that provides the error signal
        factor: float
            optional gain multiplier for debugging
        offset:
            offset to start locking from. Not touched upon if None
        kwargs must contain a pair _variable = setpoint, where _variable
        is the name of the variable of the model, as specified in the
        class attribute _variable.

        Returns
        -------
        None
        """
        self.state["set"].update(kwargs)
        self.state["set"]["factor"] = factor
        if input is None:
            input = self.inputs.values()[0]
        elif isinstance(input, str):
            input = self.inputs[input]
        inputname = input._name
        variable = kwargs[self._variable]
        setpoint = self.__getattribute__(inputname)(variable)
        slope = self.__getattribute__(inputname+'_slope')(variable)

        # trivial to lock: just enable all gains
        for o in self.outputs.values():
            # get unit of output calibration factor
            unit = o._config.calibrationunits.split("_per_V")[0]
            #get calibration factor
            variable_per_unit = self.__getattribute__(self._variable
                                                      + "_per_" + unit)
            # enable lock of the output
            o.lock(slope=slope*variable_per_unit,
                   setpoint=setpoint,
                   input=input,
                   offset=offset,
                   factor=factor)

    def lock(self, variable):
        self._lock(x=variable)

    def calibrate(self, inputs=None, scopeparams={}):
        """
        Calibrates by performing a sweep as defined for the outputs and
        recording and saving min and max of each input.

        Parameters
        -------
        inputs: list
            list of input signals to calibrate. All inputs are used if None.
        scopeparams: dict
            optional parameters for signal acquisition during calibration
            that are temporarily written to _config

        Returns
        -------
        curves: list
            list of all acquired curves
        """
        self.unlock()
        duration = self.sweep()
        curves = []
        if not inputs:
            inputs = self.inputs.values()
        for input in inputs:
            try:
                input._config._data["trigger_source"] = "asg1"
                input._config._data["duration"] = duration
                input._config._data.update(scopeparams)
                input._acquire()
                # when signal: autosave is enabled, each calibration will
                # automatically save a curve
                curve, ma, mi, mean, rms = input.curve, input.max, input.min, \
                                           input.mean, input.rms
                curves.append(curve)
                try:
                    secondsignal = scopeparams["secondsignal"]
                    input2 = self.inputs[secondsignal]
                    curve2 = input2.curve
                    curve.add_child(curve2)
                except KeyError:
                    # no secondsignal was specified
                    pass
            finally:
                # make sure to reload config file here so that the modified
                # scope parameters are not written to config file
                self._parent.c._load()
            # save all parameters to config
            input._config["max"] = ma
            input._config["min"] = mi
            input._config["mean"] = mean
            input._config["rms"] = rms
        # turn off sweeps
        self.unlock()
        return curves

    def help(self):
        self.logger.info("Interferometer\n-------------------\n"
                         + "Usage: \n"
                         + "Create Pyrpl object: p = Pyrpl('myconfigfile')\n"
                         + "Turn off the laser and execute: \n"
                         + "p.get_offset()\n"
                         + "Turn the laser back on and execute:\n"
                         + "p.calibrate()\n"
                         + "(everytime power or alignment has changed). Then: "
                         + "p.lock(factor=1.0)\n"
                         + "The device should be locked now. Play \n"
                         + "with the value of factor until you find a \n"
                         + "reasonable lock performance and save this as \n"
                         + "the new default with p.set_optimal_gain(). \n"
                         + "Now simply call p.lock() to lock.  \n"
                         + "Assert if locked with p.islocked() and unlock \n"
                         + "with p.unlock(). ")


class Interferometer(Model):
    """ simplest type of optical interferometer with one photodiode """

    # the variable which we would like to control
    _variable = "phase"

    # theoretical model for input signal 'transmission'
    def transmission(self, phase):
        """ photocurrent of an ideal interferometer vs phase (rad)"""
        amplitude = (self.inputs['transmission']._config.max
                     - self.inputs['transmission']._config.min) / 2
        mean = (self.inputs['transmission']._config.max
                     + self.inputs['transmission']._config.min) / 2
        return np.sin(phase) * amplitude + mean

    # how phase converts to other units that are used in the configfile
    @property
    def phase_per_m(self):
        return 2*np.pi/self._config.wavelength

    # how to estimate the actual phase
    @property
    def phase(self):
        return self.variable % (2*np.pi)

    def lock(self, phase=0, factor=1):
        return self._lock(phase=phase,
                          input='transmission',
                          offset=0,
                          factor=factor)

    def calibrate(self):
        return  super(Interferometer, self).calibrate(
            scopeparams={'secondsignal': 'piezo'})


class FabryPerot(Model):
    # the internal variable for state specification
    _variable = 'detuning'

    # lorentzian functions
    def _lorentz(self, x):
        return 1.0 / (1.0 + x ** 2)

    def _lorentz_slope(self, x):
        return -2.0*x / (1.0 + x ** 2)**2

    def _lorentz_slope_normalized(self, x):
        # max slope occurs at x +- sqrt(3)
        return  self._lorentz_slope(x) / abs(self._lorentz_slope(np.sqrt(3)))

    def _lorentz_slope_slope(self, x):
        return (-2.0+6.0*x**2) / (1.0 + x ** 2)**3

    def _lorentz_slope_normalized_slope(self, x):
        """ slope of normalized slope (!= normalized slope of slope) """
        return (-2.0+6.0*x**2) / (1.0 + x ** 2)**3  \
               / abs(self._lorentz_slope(np.sqrt(3)))

    def transmission(self, x):
        " relative transmission. Max transmission will be calibrated as peak"
        return self._lorentz(x) * self._config.resonant_transmission

    def reflection(self, x):
        " relative transmission. Max transmission will be calibrated as peak"
        return self._config.offresonant_reflection * self._lorentz(x) * self._config.resonant_transmission

    def FWHM(self):
        return self._config.linewidth / 2

    def reflection(self, x):
        " relative reflection"
        return 1.0 - (1.0 - self._config.R0) * self._lorentz(x / self.FWHM)
    #   return 1.0 - self._lorentz(x)

    def transmission(self, x):
        return self._lorentz(x)*self.signals.transmission

    def islocked(self):
        if self.inputs.reflection.mean:
            return False

class FabryPerot_Reflection(FabryPerot):
    # declare here the public functions that are exported to the Pyrpl class
    export_to_parent = ['lock', 'unlock', 'islocked', 'calibrate', 'sweep',
                        'help', 'set_optimal_gain']

    # theoretical model for input signal 'port1'
    def reflection(self, detuning):
        """ photocurrent at port1 of an ideal interferometer vs phase (rad)"""
        return self._parent.reflection.peak * self._lorentz(detuning)

    def pdh(self, detuning):
        return self.reflection_slope(detuning)

    @property
    def detuning_per_m(self):
        return self._config.finesse / self._config.wavelength / 2

    @property
    def detuning(self):
        act = self._parent.reflection.mean
        set = self.state["set"]["detuning"]
        detuning = self.reflection_inverse(act, set)
        if detuning is not None:
            return detuning
        else:
            logger.warning("Detuning could not be estimated. "
                            +"Re-run a calibration!")
            return None

    # lock algorithm
    def lock(self, detuning=1, factor=1.0):
        """
        Locks the cavity
        Parameters
        ----------
        phase: float
            phase (rad) of the quadrature to be locked at
        factor: float
            optional gain multiplier for debugging

        Returns
        -------
        True if locked successfully, else false

        """

        self.state["set"]["detuning"] = detuning
        self.state["set"]["factor"] = factor
        input = self._parent.port1
        for o in self.outputs.values():
            # trivial to lock: just enable all gains
            unit = o._config.calibrationunits.split("_per_V")[0]
            detuning_per_unit = self.__getattribute__("detuning_per_" + unit)
            o.lock(slope=self.port1_slope(detuning) * detuning_per_unit,
                   setpoint=self.port1(detuning),
                   input=input._config.redpitaya_input,
                   offset=0,
                   factor=factor)


    def islocked(self):
        """ returns True if interferometer is locked, else False"""
        # check phase error
        dphase = abs(self.detuning - self.state["set"]["detuning"])
        if dphase > self._config.maxerror:
            return False
        else:
            # test for output saturation
            for o in self.outputs.values():
                if o.issaturated:
                    return False
        # lock seems ok (but not a failsafe criterion without additional info)
        return True


    def calibrate(self):
        self.unlock()
        duration = self.sweep()
        curves = []
        for input in self.inputs.values():
            try:
                input._config._data["trigger_source"] = "asg1"
                input._config._data["duration"] = duration
                input._acquire()
                # when signal: autosave is enabled, each calibration will
                # automatically save a curve
                if input._config.autosave:
                    curve, ma, mi = input.curve, input.max, input.min
                    curves.append(curve)
                else:
                    ma, mi = input.max, input.min
            finally:
                # make sure to reload config file here so that the modified
                # scope parameters are not written to config file
                self._parent.c._load()
            input._config["max"] = ma
            input._config["min"] = mi
        # turn off sweeps
        self.unlock()
        return curves


    def help(self):
        self.logger.info("Fabry-Perot\n-------------------\n"
                         + "Usage: \n"
                         + "Create Pyrpl object: p = Pyrpl('myconfigfile')"
                         + "Turn off the laser and execute: \n"
                         + "p.get_offset()\n"
                         + "Turn the laser back on and execute:\n"
                         + "p.calibrate()\n"
                         + "(everytime power or alignment has changed). Then: "
                         + "p.lock(factor=1.0)\n"
                         + "The interferometer should be locked now. Play \n"
                         + "with the value of factor until you find a \n"
                         + "reasonable lock performance and save this as \n"
                         + "the new default with p.set_optimal_gain(). \n"
                         + "Now simply call p.lock(phase=myphase) to lock \n"
                         + "at arbitrary phase 'myphase' (rad). "
                         + "Assert if locked with p.islocked() and unlock \n"
                         + "with p.unlock(). ")


class TEM02FabryPerot(FabryPerot):
    export_to_parent = ['unlock', 'sweep', 'islocked',
                        'set_optimal_gain', 'calibrate',
                        'lock_tilt', 'lock_transmission', 'lock']

    def tilt(self, detuning):
        return self._lorentz_slope(detuning)/0.6495 *self._parent.tilt._config.slope_sign \
               * 0.5 * (self._parent.tilt._config.max-self._parent.tilt._config.min)

    def transmission(self, detuning):
        return self._lorentz(detuning)*self._parent.transmission._config.max \
               + self._parent.transmission._config.min

    def calibrate(self):
        self.unlock()
        duration = self.sweep()
        # input signal calibration
        for input in self.inputs.values():
            try:
                input._config._data["trigger_source"] = "asg1"
                input._config._data["duration"] = duration
                input._acquire()
                curve, ma, mi = input.curve, input.max, input.min
                input._config._data["trigger_source"] = "ch1_positive_edge"
                input._config._data["threshold"] = ma*self._config.calibration_threshold
                input._config._data["trigger_delay"] = 0
                # input._config._data["hysteresis_ch1"] = ma / 20
                input._config._data["duration"] = duration/self._config.calibration_zoom
                input._config._data["timeout"] = duration*5
                input._acquire()
                curve, ma, mi = input.curve, input.max, input.min
            finally:
                # make sure to reload config file here so that the modified
                # scope parameters are not written to config file
                self._parent.c._load()
            input._config["max"] = ma
            input._config["min"] = mi

        # turn off sweeps
        self.unlock()

    @property
    def detuning_per_m(self):
        return 1./(self._config.wavelength/2/self._config.finesse/2)

    def lock_transmission(self, detuning=1, factor=1.0):
        """
        Locks on transmission
        Parameters
        ----------
        detuning: float
            detuning (HWHM) to be locked at
        factor: float
            optional gain multiplier for debugging

        Returns
        -------
        True if locked successfully, else false
        """
        self.state["set"]["detuning"] = detuning
        self.state["set"]["factor"] = factor
        input = self._parent.transmission
        for o in self.outputs.values():
            # trivial to lock: just enable all gains
            unit = o._config.calibrationunits.split("_per_V")[0]
            detuning_per_unit = self.__getattribute__("detuning_per_" + unit)
            o.lock(slope=self.transmission_slope(detuning) * detuning_per_unit,
                   setpoint=self.transmission(detuning),
                   input=input._config.redpitaya_input,
                   offset=None,
                   factor=factor)
        return self.islocked()

    def lock_tilt(self, detuning=1, factor=1.0):
        """
        Locks on transmission
        Parameters
        ----------
        detuning: float
            detuning (HWHM) to be locked at
        factor: float
            optional gain multiplier for debugging

        Returns
        -------
        True if locked successfully, else false
        """
        self.state["set"]["detuning"] = detuning
        self.state["set"]["factor"] = factor
        input = self._parent.tilt
        for o in self.outputs.values():
            # trivial to lock: just enable all gains
            unit = o._config.calibrationunits.split("_per_V")[0]
            detuning_per_unit = self.__getattribute__("detuning_per_" + unit)
            o.lock(slope=self.tilt_slope(detuning) * detuning_per_unit,
                   setpoint=self.tilt(detuning),
                   input=input._config.redpitaya_input,
                   offset=None,
                   factor=factor)

    def lock(self, detuning=0, factor=1.0, stop=False):
        while not self.islocked():
            self._parent.piezo.pid.ival = self._config.lock.drift_offset
            self.lock_transmission(factor=factor, detuning=self._config.lock.drift_detuning)
            time.sleep(self._config.lock.drift_timeout)
        if stop: return
        return self.lock_tilt(detuning=detuning, factor=factor)

    @property
    def relative_transmission(self):
        return (self._parent.transmission.mean - self._parent.transmission._config.min)\
               / (self._parent.transmission._config.max-self._parent.transmission._config.min)

    def islocked(self):
        """ returns True if interferometer is locked, else False"""
        # check phase error
        rel_t = self.relative_transmission
        self.logger.debug("Relative transmission: %s", rel_t)
        if rel_t < self._config.lock.relative_transmission_threshold:
            # lock seems ok (but not a failsafe criterion without additional info)
            return False
        else:
            # test for output saturation
            for o in self.outputs.values():
                if o.issaturated:
                    self.logger.debug("Output %s is saturated!", o._name)
                    return False
        return True
