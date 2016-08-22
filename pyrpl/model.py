import numpy as np
import scipy
import logging
import time
import threading

from .signal import *
from . import fitting
from . import pyrpl_utils

logger = logging.getLogger(name=__name__)

class Model(object):
    """ A generic model object that makes smart use of its inputs and outputs.
    This is the baseclass for all other models, such as interferometer,
    fabryperot and custom ones.

    Parameters
    ----------
    parent: Pyrpl
        The pyrpl object that instantiates this model. The model will
        retrieve many items from the pyrpl object, such as the redpitaya
        instance and various signals. It will also create new attributes in
        parent to provide the most important API functions that the model
        allows.
    """
    export_to_parent = ["sweep", "calibrate", "save_current_gain",
                        "unlock", "islocked", "lock", "help", "calib_lock",
                        "_lock", "get_offset"]

    # independent variable that specifies the state of the system
    _variable = 'x'

    def __init__(self, parent=None):
        self.logger = logging.getLogger(__name__)
        self.current_stage = 'UNLOCK'
        if parent is None:
            self._parent = self
        else:
            self._parent = parent
        self.inputs = self._parent.inputs
        self.outputs = self._parent.outputs
        self.signals = self._parent.signals
        self._config = self._parent.c.model
        self._make_helpers()
        self.state = {'actual': {self._variable: 0},
                      'set': {self._variable: 0}}

    def setup(self):
        """ sets up all signals """
        for signal in self.signals.values():
            try:
                params = signal._config.setup._dict
            except KeyError:
                params = dict()
            try:
                setupfn = self.__getattribute__("setup_"+signal._name)
            except AttributeError:
                self.logger.debug("No signal setup function setup_%s was "
                                  "found", signal._name)
                continue
            else:
                self.logger.debug("Calling setup_%s!", signal._name)
                try:
                    setupfn(**params)
                except TypeError:  # means the setup function doesnt take
                    # params
                    setupfn()

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
            inverse = [self._inverse(func, yy, x0, args=args) for yy in y]
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

    # helpers that create inverse and slope function of the model functions
    # corresponding to input signals
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
                # bug removed a la
                # http://stackoverflow.com/questions/3431676/creating-functions-in-a-loop
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
        input._acquire()  # make sure data is fresh
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

    def islocked(self):
        """ returns True if locked, else False """
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

    def unlock(self, ival=True):
        """ unlocks the system"""
        if hasattr(self, '_relocktimer'):  # stop relock timer if applicable
            self._relocktimer.stop()
        for o in self.outputs.values():
            o.unlock(ival=ival)
        self.current_stage = "UNLOCK"

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
        self.current_stage = "SWEEP"
        return 1.0 / frequency

    def _lock(self, input=None, factor=1.0, offset=None, outputs=None,
              _savegain=False, **kwargs):
        """
        Locks all outputs to input.

        Parameters
        ----------
        input: Signal
          the input signal that provides the error signal
        factor: float
            optional gain multiplier for debugging
        offset: float or None
            offset to start locking from. Not touched upon if None
        outputs: list or None
            if None, all outputs with lock configuration are enabled.
            if list of RPOutputSignal, only the specified outputs are touched.
        _savegain: bool
            option for automatic gain configuration, leave False
        kwargs must contain a pair _variable = setpoint, where _variable
        is the name of the variable of the model, as specified in the
        class attribute _variable.

        Returns
        -------
        None
        """

        if kwargs:
            self.state["set"].update(kwargs)
        self.state["set"]["factor"] = factor
        if input is None:
            input = self.inputs.values()[0]
        elif isinstance(input, str):
            input = self.inputs[input]
        inputname = input._name
        variable = kwargs.pop(self._variable)
        setpoint = self.__getattribute__(inputname)(variable)
        slope = self.__getattribute__(inputname+'_slope')(variable)
        # setpoint, slope come in 'units' of the input. Convert to V
        input_unit_per_V = input._config[input._config.unit+'_per_V']
        setpoint /= input_unit_per_V
        slope /= input_unit_per_V

        # trivial lock algorithm: just enable all gains
        if outputs is None:
            outputs = self.outputs.values()
        # unlock all unused outputs, but leave ival unaffected
        for o in [op for op in self.outputs.values() if op not in outputs]:
            o.unlock(ival=False)
        # engage lock on all desired outputs
        for o in outputs:
            if not isinstance(o, RPOutputSignal):
                o = self.outputs[o]
            # get unit of output calibration factor
            unit = o._config.calibrationunits.split("_per_V")[0]
            # get calibration factor
            variable_per_unit = self.__getattribute__(self._variable
                                                      + "_per_" + unit)
            if not _savegain:
                # enable lock of the output
                o.lock(slope=slope*variable_per_unit,
                       setpoint=setpoint,
                       input=input,
                       offset=offset,
                       factor=factor,
                       **kwargs)
            else:  # special option: instead of locking, write the gain
                o.save_current_gain(slope=slope*variable_per_unit)

    def save_current_gain(self, outputs=None):
        """ saves the current gain setting as default one (for all outputs
        unless a list of outputs is given, similar to _lock) """
        self._lock(outputs=outputs, _savegain=True)

    def stage_changed_hook(self, new_stage):
        """Overwrite or monkey patch this function for custom action upon
        new stage"""
        pass

    def lock(self,
             factor=None,
             firststage=None,
             laststage=None,
             thread=False,
             **kwargs):
        ### This function is almost a one-to-one duplicate of FabryPerot.lock (
        # except for the **kwargs that is read online). This is a major
        # source of bug !!!!

        # firststage will allow timer-based recursive iteration over stages
        # i.e. calling lock(firststage = nexstage) from within this code
        stages = self._config.lock.stages._keys()
        if firststage:
            if not firststage in stages:
                self.logger.error("Firststage %s not found in stages: %s",
                                  firstage, stages)
            else:
                stages = stages[stages.index(firststage):]
        for stage in stages:
            self.logger.debug("Lock stage: %s", stage)
            self.current_stage = stage
            self.stage_changed_hook(stage) # Some hook function
            if stage.startswith("call_"):
                try:
                    lockfn = self.__getattribute__(stage[len('call_'):])
                except AttributeError:
                    logger.error("Lock stage %s: model has no function %s.",
                                 stage, stage[len('call_'):])
                    raise
            else:
                # use _lock by default
                lockfn = self._lock
            parameters = dict(factor=factor)
            if self._variable in kwargs:
                parameters[self._variable] = kwargs[self._variable]
            parameters.update((self._config.lock.stages[stage]))
            try:
                stime = parameters.pop("time")
            except KeyError:
                stime = 0
            if stage == laststage or stage == stages[-1]:
                if self._variable in kwargs and kwargs[self._variable]:
                    parameters[self._variable] = kwargs[self._variable]
                if factor:
                    parameters['factor'] = factor
                try:
                    return lockfn(**parameters)
                except TypeError:  # function doesnt accept kwargs
                    raise
                    return lockfn()
            else:
                if thread:
                    # immediately execute current step (in another thread)
                    t0 = threading.Timer(0,
                                        lockfn,
                                        kwargs=parameters)
                    t0.start()  # bug here: lockfn must accept kwargs
                    # and launch timer for nextstage
                    nextstage = stages[stages.index(stage) + 1]
                    parameters = dict(factor=factor,
                                      firststage=nextstage,
                                      laststage=laststage,
                                      thread=thread)
                    if self._variable in kwargs and kwargs[self._variable]:
                        parameters[self._variable] = kwargs[self._variable]
                    t1 = threading.Timer(stime,
                                        self.lock,
                                        kwargs=parameters)
                    t1.start()
                    return None
                else:
                    try:
                        lockfn(**parameters)
                    except TypeError:  # function doesnt accept kwargs
                        lockfn()
                    pyrpl_utils.sleep(stime) ## Changed to pyrpl_utils.sleep,
                    #  which basically doesn't freeze the gui

    def relock(self, *args, **kwargs):
        """ executes 'lock' until 'islocked' returns true """
        while not self.islocked():
            self.lock(*args, **kwargs)

    def autorelock(self, timeout=1.0):
        """ sets up a timer that periodically calls relock() """
        if not hasattr(self, '_relocktimer'):
            from PyQt4.QtCore import QTimer
            self._relocktimer = QTimer()
        try:
            self._relocktimer.disconnect()
        except TypeError:
            pass
        self._relocktimer.timeout.connect(self.relock)
        self._relocktimer.setSingleShot(False)
        self._relocktimer.start(int(timeout*1000))

    def stop_autolock(self):
        self.timer.stop()

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
            if not isinstance(input, Signal):
                input = self.inputs[input]
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
                # add sweep phase at scope trigger to retrieve the scan
                # direction afterwards
                for o in self.outputs.values():
                    if 'sweep' in o._config._keys():
                        curve.params[o._name+'.sweep_triggerphase'] = \
                            o.sweep_triggerphase
                curve.save()
                try:
                    secondsignal = scopeparams["secondsignal"]
                    input2 = self.signals[secondsignal]
                    curve2 = input2.curve
                    curve.add_child(curve2)
                    self.logger.debug("Secondsignal %s successfully acquired.",
                                      secondsignal)
                except KeyError:
                    self.logger.debug("No secondsignal was specified for %s",
                                      input._name)
            finally:
                # make sure to reload config file here so that the modified
                # scope parameters are not written to config file
                self._parent.c._load()
            # save all parameters to config
            input._config["max"] = ma
            input._config["min"] = mi
            input._config["mean"] = mean
            input._config["rms"] = rms
            input._config["curve"] = curve.pk
        # turn off sweeps
        self.unlock()
        return curves

    def calib_lock(self):
        """ shortcut to call calibrate(), lock() and return islocked()"""
        self.calibrate()
        self.lock()
        return self.islocked()

    def setup_iq(self, inputsignal='iq', **kwargs):
        """
        Sets up an input signal derived from demodultaion of another input.
        The config file must contain an input signal named like the the
        parameter input with a section 'setup' whose entries are directly
        passed to redpitaya_modules.IQ.setup().

        Parameters
        ----------
        input: str
        kwargs: dict
            optionally override config files setup section by passing
            the arguments as kwargs here

        Returns
        -------
        None
        """
        if not isinstance(inputsignal, Signal):
            input = self.inputs[inputsignal]
        else:
            input = inputsignal
        if not kwargs:
            kwargs = input._config.setup._dict
        if 'iq' in kwargs:  # we can request a particular iq number if needed
            input.iq = self._parent.rp.__getattribute__(kwargs.pop('iq'))
        elif not hasattr(input , 'iq'):
            input.iq = self._parent.rp.iqs.pop()
        input.iq.setup(**kwargs)
        input._config['redpitaya_input'] = input.iq.name

    def help(self):
        """ provides some help to get started. """
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

    def fit(self, input, manualfit=True, **extra):
        """ attempts a fit of input's last calibration curve with the input's
        model"""
        if not isinstance(input, Signal):
            input = self.inputs[input]
        signalfn = self.__getattribute__(input._name)
        c = CurveDB.get(input._config.curve)
        data = c.data
        t = c.data.index.values
        def fitfn(variable_per_time, t0, offset, scale, **kwds):
            variables = (t-t0) * variable_per_time
            return np.array(offset + scale * signalfn(variables, **kwds),
                            dtype=np.double)
        # a very naive guess - should be refined with 'input_guess' function
        guess = {'variable_per_time': 10.0 / (t.max() - t.min()),
                 't0': 0,
                 'offset': 0,
                 'scale': 1.0}
        guess.update(extra)
        try:
            guessfn = self.__getattribute__(input._name + '_guess')
        except AttributeError:
            self.logger.warning("No function %s to guess fit "
                                "parameters is defined. Writing one will "
                                "improve fit performance. ",
                                input._name + '_guess')
        else:
            guess.update(guessfn())
        fitter = fitting.Fit(data, fitfn, manualguess_params=guess,
                            fixed_params={'offset': 0},
                            graphicalfit=manualfit, autofit=True)
        fitcurve = CurveDB.create(fitter.fitdata, name='fit_'+input._name)
        fitcurve.params.update(fitter.getparams())
        try:
            postfn = self.__getattribute__(input._name + '_postfit')
        except AttributeError:
            self.logger.warning("No function %s to use fit "
                                "parameters is defined. Writing one will "
                                "improve calibration results. ",
                                input._name + '_postfit')
        else:
            fitcurve.params.update(postfn())
        fitcurve.save()
        c.add_child(fitcurve)
        return fitcurve

    def get_offset(self):
        """ Execute this function to record the offsets for all input
        signals. If signal.offset_subtraction is true in the config file,
        the signal value 0 will from then on correspond to the measured
        offset. Before any locking configuration, this function should be
        executed in order to take the analog offsets of redpitaya inputs
        into account. """
        for input in self.inputs.values():
            input.get_offset()

