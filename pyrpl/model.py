import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)

from scipy.constants import c

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
        for output in self.outputs:
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

    #export_to_parent = super(FabryPerot).export_to_parent + ['R0']

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
        " transmission of the Fabry-Perot "
        return self._lorentz(x) * self._config.resonant_transmission

    def reflection(self, x):
        " reflection of the Fabry-Perot"
        offres = self._config.offresonant_reflection
        res = self._config.resonant_reflection
        return (res-offres) * self._lorentz(x) + offres

    @property
    def R0(self):
        " reflection coefficient on resonance "
        return self._config.resonant_reflection / \
               self._config.offresonant_reflection

    @property
    def T0(self):
        " transmission coefficient on resonance "
        return self._config.resonant_reflection / \
               self._config.offresonant_reflection

    @property
    def detuning_per_m(self):
        " detuning of +-1 corresponds to the half-maximum intracavity power "
        linewidth = self._config.wavelength / 2 / self._config.finesse
        return 1.0 / (linewidth / 2)

    @property
    def detuning(self):
        return self.variable

    # simplest possible lock algorithm
    def lock_reflection(self, detuning=1, factor=1.0):
        # self.unlock()
        self._lock(input=self.inputs["reflection"],
                   detuning=detuning,
                   factor=factor,
                   offset=1.0*np.sign(detuning))

    def lock_transmission(self, detuning=1, factor=1.0):
        self._lock(input=self.inputs["transmission"],
                   detuning=detuning,
                   factor=factor,
                   offset=1.0 * np.sign(detuning))

    lock = lock_reflection

    def calibrate(self):
        curves = super(FabryPerot, self).calibrate(
            scopeparams={'secondsignal': 'piezo'})
        duration = curves[0].params["duration"]

        # pick our favourite available signal
        for sig in self.inputs.values():
            # make a zoom calibration over roughly 10 linewidths
            duration *= (1.0 - sig._config.mean/sig._config.max) * 10
            curves = super(FabryPerot, self).calibrate(
                inputs=[sig],
                scopeparams={'secondsignal': 'piezo',
                             'trigger_source': 'ch1_positive_edge',
                             'threshold': (sig._config.max+sig._config.min)/2,
                             'duration': duration,
                             'timeout': 10*duration})
            if sig._name == 'reflection':
                self._config["offresonant_reflection"] = sig._config.max
                self._config["resonant_reflection"] = sig._config.min
            if sig._name == 'transmission':
                self._config["resonant_transmission"] = sig._config.max
        return curves

class FPM(FabryPerot):
    def setup(self):
        o = self.outputs["slow"]
        o.output_offset = o._config.lastoffset

    def sweep(self):
        duration = super(FPM, self).sweep()
        self._parent.   rp.scope.setup(trigger_source='asg1',
                                    duration=duration)

class FPMembranes(FabryPerot):
    def pdh(self, detuning):
        offset = self._config.offset_pdh
        phi = self._config.phase_pdh
        ampl = self._config.ampl_pdh
        width = c/(4*self._config.cavity_length*self._config.finesse)
        mod = self._config.mod_pdh

        detuning = detuning*width

        f1 = 2 * ampl * detuning * width * (mod ** 2)
        numer = ((detuning ** 2 + width ** 2 - mod ** 2) * np.cos(phi) - 2 * width * mod * np.sin(phi))
        denom = ((detuning ** 2 + width ** 2) * (width ** 2 + (detuning - mod) ** 2) * (width ** 2 + (detuning + mod) ** 2))
        ret = offset + f1 * numer / denom

        return ret

    def lock_pdh(self, detuning=1., factor=1.):
        self._lock(input=self.inputs["pdh"],
                   factor=factor,
                   detuning=detuning,
                   offset=1.)

    lock = lock_pdh

    def pdh_score(self, data):
        """
        This score should be maximised to improve the phase of the demodulation
        :return:
        """
        return (data.max() - data.min()) / (data.argmax() - data.argmin())

    @property
    def duration_zoom(self):
        if hasattr(self._config, 'duration_zoom'):
            return self._config.duration_zoom
        else:
            self._config["duration_zoom"] = 5*self.duration_sweep/self._config.finesse
            return self._config.duration_zoom


    @property
    def duration_sweep(self):
        return self._parent.c.scope.duration

    def acquire_pdh_phase(self, phi, parent=None):
        """
        Acquires one pdh phase
        :param phi: pdh phase to acquire.
        parent: parent curve to store calibration curve.
        :return: score, phase
        score: the pdh_score to maximize
        curve: the calibration curve
        """

        sig = self.inputs["pdh"]
        self.inputs["pdh"]._config.phase = phi
        self.setup()
        self.sweep() # it would be cleaner to have a periodic=False in asg to make
        # sure curve is only acquired when ramp is rising
        curve = Model.calibrate(self,
                                inputs=[sig],
                                scopeparams=dict(secondsignal='transmission',
                                                 duration=self.duration_zoom,
                                                 trigger_delay=self._config["trigger_delay_zoom"],
                                                 threshold=0.1,
                                                 average=True,
                                                 timeout=self.duration_sweep*2))[0]
        score = self.pdh_score(curve.data)
        curve.params["phi_pdh"] = phi
        curve.params["score"] = score
        if sig._config.autosave and parent is not None:
            curve.move(parent)
        return score, curve

    def search_pdh_phase(self, phi, val, phi_step, phi_accuracy, parent=None):
        """
        Looks for best score by n dichotomy steps between phi1 and phi2
        :param phi1:
        :param phi2:
        :param n:
        :return:
        """
        if phi_step<phi_accuracy:
            return phi
        for new_phi in (phi + phi_step, phi - phi_step):
            new_val, curve = self.acquire_pdh_phase(new_phi, parent)
            self.logger.info("phi_pdh: %i -> %i", new_phi, new_val)
            if new_val>val:
                return self.search_pdh_phase(new_phi, new_val, phi_step/2, phi_accuracy, parent)
        # best result was for phi
        return self.search_pdh_phase(phi, val, phi_step/2, phi_accuracy, parent)

    def calibrate(self):
        duration = self.sweep()
        curves = Model.calibrate(self,
                               inputs=[self.inputs['reflection']],
                               scopeparams=dict(duration=duration,
                                                trigger_delay=duration/2.))
        last_duration = curves[0].params["duration"]
        self.sweep()
        self._config["trigger_delay_zoom"] = curves[0].data.argmin()

        timeout = last_duration * 3
        for sig in self.inputs.values():
            curves += Model.calibrate(self,
                            inputs=[sig],
                            scopeparams=dict(secondsignal='piezo',
                                             duration=self.duration_zoom,
                                             trigger_delay=self._config["trigger_delay_zoom"],
                                             timeout=timeout))
            if sig._name == 'pdh':
                parent = curves[-1]
                scores = []
                phis = (0., 120., 240.)
                for phi in phis:
                    score, curve = self.acquire_pdh_phase(phi, parent)
                    scores.append(score)
                    #look for optimal phase between phi_guess +- 45 deg
                tab = [(val, phi) for (val, phi) in zip(scores, phis)]
                (val, phi) = sorted(tab)[-1]
                #delta_phi = phi2 - phi1
                #delta_phi = (delta_phi + 180.) % (360.) - 180.
                #phi2 = phi1 + delta_phi
                sig._config.phase = self.search_pdh_phase(phi, val, phi_step=60., phi_accuracy=1., parent=parent)
                self._config.offset_pdh = sig._config.mean
                self._config.ampl_pdh = (sig._config.max - sig._config.min)/2
        return curves

    def setup(self):
        self._parent.rp.iq0.setup(frequency=self._config.mod_pdh,
                                  bandwidth=[self.inputs['pdh']._config.bandwidth, self.inputs['pdh']._config.bandwidth],
                                  gain=0,
                                  phase=self.inputs["pdh"]._config.phase,
                                  acbandwidth=500000,
                                  amplitude=self.inputs['pdh']._config.mod_amplitude_v,
                                  input=self.inputs['pdh']._config.redpitaya_mod_input,
                                  output_direct=self.inputs['pdh']._config.redpitaya_mod_output,
                                  output_signal='quadrature',
                                  quadrature_factor=self.inputs['pdh']._config.redpitaya_quadrature_factor)
        #o = self.outputs["slow"]
        #o.output_offset = o._config.lastoffset

    def sweep(self):
        duration = super(FPMembranes, self).sweep()
        self._parent.rp.scope.setup(trigger_source='asg1',
                                    duration=duration)
        return duration



class TEM02FabryPerot(FabryPerot):
    export_to_parent = ['unlock', 'sweep', 'islocked',
                        'save_current_gain', 'calibrate',
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
