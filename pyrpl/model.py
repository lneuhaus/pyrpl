import numpy as np
import scipy
import logging
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
    export_to_parent = []

    state = {'actual': {},
             'set': {}}

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

    def setup(self):
        pass

    def search(self, *args, **kwargs):
        pass

    def lock(self, *args, **kwargs):
        pass

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

    def _make_helpers(self):
        # create any missing slope and inverse functions
        for inp in self.inputs:
            # test if the slope was defined in the model
            if not hasattr(self, inp._name+"_slope"):
                fn = self.__getattribute__(inp._name)
                def fn_slope(x, *args):
                    return self._derivative(fn, x, args=args)
                self.__setattr__(inp._name+"_slope", fn_slope)
            if not hasattr(self, inp._name + "_inverse"):
                fn = self.__getattribute__(inp._name)
                def fn_inverse(x, x0, *args):
                    return self._inverse(fn, x, x0, args=args)
                self.__setattr__(inp._name + "_inverse", fn_inverse)

    def set_optimal_gain(self):
        factor = self.state["set"]["factor"]
        for output in self.outputs:
            output.set_optimal_gain(factor)

    # unlock algorithm
    def unlock(self):
        for o in self.outputs:
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
        for o in self.outputs:
            frequency = o.sweep()
        return 1.0 / frequency


class Interferometer(Model):
    """ simplest type of optical interferometer with one photodiode """

    # declare here the public functions that are exported to the Pyrpl class
    export_to_parent = ['lock', 'unlock', 'islocked', 'calibrate', 'sweep',
                        'help', 'set_optimal_gain', 'phase']

    # the internal state memory
    state = {'set': {'phase': 0},
             'actual': {'phase': 0}}

    # theoretical model for input signal 'port1'
    def port1(self, phase):
        """ photocurrent at port1 of an ideal interferometer vs phase (rad)"""
        amplitude = (self._parent.port1._config.max
                     - self._parent.port1._config.min) / 2
        return np.sin(phase) * amplitude

    @property
    def phase_per_m(self):
        return 2*np.pi/self._config.wavelength

    @property
    def phase(self):
        act = self._parent.port1.mean
        set = self.state["set"]["phase"]
        phase = self.port1_inverse(act, set)
        if phase is not None:
            return phase%(2*np.pi)
        else:
            logger.warning("Phase could not be estimated. Run a calibration!")
            return None

    # lock algorithm
    def lock(self, phase=0, factor=1.0):
        """
        Locks the interferometer
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
        self.state["set"]["phase"] = phase
        self.state["set"]["factor"] = factor
        input = self._parent.port1
        for o in self.outputs:
            # trivial to lock: just enable all gains
            unit = o._config.calibrationunits.split("_per_V")[0]
            phase_per_unit = self.__getattribute__("phase_per_"+unit)
            o.lock(slope=self.port1_slope(phase)*phase_per_unit,
                   setpoint=self.port1(phase),
                   input=input._config.redpitaya_input,
                   offset=0,
                   factor=factor)

    def islocked(self):
        """ returns True if interferometer is locked, else False"""
        # check phase error
        dphase = abs(self.phase - self.state["set"]["phase"])
        if dphase > self._config.maxerror:
            return False
        else:
            # test for output saturation
            for o in self.outputs:
                if o.issaturated:
                    return False
        # lock seems ok (but not a failsafe criterion without additional info)
        return True

    def calibrate(self):
        self.unlock()
        duration = self.sweep()
        curves = []
        for inp in self.inputs:
            try:
                inp._config._data["trigger_source"] = "asg1"
                inp._config._data["duration"] = duration
                inp._acquire()
                # when signal: autosave is enabled, each calibration will
                # automatically save a curve
                if inp._config.autosave:
                    curve, ma, mi = inp.curve, inp.max, inp.min
                    curves.append(curve)
                else:
                    ma, mi = inp.max, inp.min
            finally:
                # make sure to reload config file here so that the modified
                # scope parameters are not written to config file
                self._parent.c._load()
            inp._config["max"] = ma
            inp._config["min"] = mi
        # turn off sweeps
        self.unlock()
        #self._parent._setupscope()
        return curves

    def help(self):
        self.logger.info("Interferometer\n-------------------\n"
                         +"Usage: \n"
                         +"Create Pyrpl object: p = Pyrpl('myconfigfile')"
                         +"Turn off the laser and execute: \n"
                         +"p.get_offset()\n"
                         +"Turn the laser back on and execute:\n"
                         +"p.calibrate()\n"
                         +"(everytime power or alignment has changed). Then: "
                         +"p.lock(factor=1.0)\n"
                         +"The interferometer should be locked now. Play \n"
                         +"with the value of factor until you find a \n"
                         +"reasonable lock performance and save this as \n"
                         +"the new default with p.set_optimal_gain(). \n"
                         +"Now simply call p.lock(phase=myphase) to lock \n"
                         +"at arbitrary phase 'myphase' (rad). "
                         +"Assert if locked with p.islocked() and unlock \n"
                         +"with p.unlock(). ")


class FabryPerot(Model):
    # the internal state memory
    state = {'set': {'detuning': 0},
             'actual': {'detuning': 0}}

    def _lorentz(self, x):
        return 1.0 / (1.0 + x ** 2)

    # def transmission(self, x):
    #    " relative transmission. Max transmission will be calibrated as peak"
    #    return self._lorentz(x/self.bandwidth)

    def FWHM(self):
        return self._config.linewidth / 2

    def reflection(self, x):
        " relative reflection"
        return 1.0 - (1.0 - self._config.R0) * self._lorentz(x / self.FWHM)



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
        self.state["set"]["phase"] = phase
        self.state["set"]["factor"] = factor
        input = self._parent.port1
        for o in self.outputs:
            # trivial to lock: just enable all gains
            unit = o._config.calibrationunits.split("_per_V")[0]
            phase_per_unit = self.__getattribute__("phase_per_"+unit)
            o.lock(slope=self.port1_slope(phase)*phase_per_unit,
                   setpoint=self.port1(phase),
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
            for o in self.outputs:
                if o.issaturated:
                    return False
        # lock seems ok (but not a failsafe criterion without additional info)
        return True

    def calibrate(self):
        self.unlock()
        duration = self.sweep()
        curves = []
        for inp in self.inputs:
            try:
                inp._config._data["trigger_source"] = "asg1"
                inp._config._data["duration"] = duration
                inp._acquire()
                # when signal: autosave is enabled, each calibration will
                # automatically save a curve
                if inp._config.autosave:
                    curve, ma, mi = inp.curve, inp.max, inp.min
                    curves.append(curve)
                else:
                    ma, mi = inp.max, inp.min
            finally:
                # make sure to reload config file here so that the modified
                # scope parameters are not written to config file
                self._parent.c._load()
            inp._config["max"] = ma
            inp._config["min"] = mi
        # turn off sweeps
        self.unlock()
        return curves

    def help(self):
        self.logger.info("Fabry-Perot\n-------------------\n"
                         +"Usage: \n"
                         +"Create Pyrpl object: p = Pyrpl('myconfigfile')"
                         +"Turn off the laser and execute: \n"
                         +"p.get_offset()\n"
                         +"Turn the laser back on and execute:\n"
                         +"p.calibrate()\n"
                         +"(everytime power or alignment has changed). Then: "
                         +"p.lock(factor=1.0)\n"
                         +"The interferometer should be locked now. Play \n"
                         +"with the value of factor until you find a \n"
                         +"reasonable lock performance and save this as \n"
                         +"the new default with p.set_optimal_gain(). \n"
                         +"Now simply call p.lock(phase=myphase) to lock \n"
                         +"at arbitrary phase 'myphase' (rad). "
                         +"Assert if locked with p.islocked() and unlock \n"
                         +"with p.unlock(). ")

