import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)

class Model(object):
    """ generic model object that makes smart use of its inputs and outputs
    baseclass for all other models """

    export_to_parent = ["sweep", "calibrate", "save_current_gain",
                        "unlock", "islocked", "lock", "help", "calib_lock"]


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

    def setup(self):
        """ Custom setup function """
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

    def save_current_gain(self):
        factor = self.state["set"]["factor"]
        for output in self.outputs.values():
            output.save_current_gain(factor)

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
            o.unlock()

    def sweep(self):
        """
        Enables the pre-configured sweep on all outputs.

        Returns
        -------
        duration: float
            The duration of one sweep period, as it is useful to setup the
            scope.
        """
        self.unlock()
        frequency = None
        for o in self.outputs.values():
            frequency = o.sweep() or frequency
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

    def lock(self, variable, factor=1.0):
        self._lock(x=variable, factor=factor)

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

    def calib_lock(self):
        self.calibrate()
        self.lock()
        return self.islocked()

    def help(self):
        self.logger.info("PyRP Lockbox\n-------------------\n"
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
                         + "the new default with p.save_current_gain(). \n"
                         + "Now simply call p.lock() to lock.  \n"
                         + "Assert if locked with p.islocked() and unlock \n"
                         + "with p.unlock(). ")
