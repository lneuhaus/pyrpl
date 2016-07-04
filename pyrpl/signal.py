import time
import logging
import numpy as np
logger = logging.getLogger(__name__)

from .curvedb import CurveDB


class ExposedConfigParameter(object):
    def __init__(self, parameter):
        self._parameter = parameter

    def __get__(self, instance, owner):
        return instance._config.__getattribute__(self._parameter)

    def __set__(self, instance, value):
        instance._config.__setattr__(self._parameter, value)


class Signal(object):
    """" represention of a physial signal

    A predefined number of samples is aquired when any signal-related property
    is requested (except for sample which always gets a simultaneous datapoint.
    If several properties are requested simultaneously, all are derived from the
    same data trace. This is done by setting a timeout within
    which the signals can be requested, roughly corresponding to the required
    acquisition time. The recommended syntax for simultaneous acquisition is:

    mean, rms = signal.mean, signal.rms
    """
    def __init__(self, config, branch):
        # get the relevant config branch from config tree
        self._config = config._getbranch(branch, defaults=config.signal)
        # signal name = branch name
        self._name = self._config._branch
        self._acquiretime = 0
    unit = ExposedConfigParameter("unit")

    def __repr__(self):
        return str(self.__class__)+"("+self._name+")"

    @property
    def unit_per_V(self):
        return self._config[self.unit + "_per_V"]

    @unit_per_V.setter
    def unit_per_V(self, value):
        self._config[self.unit + "_per_V"] = value

    # placeholder for acquired data implementation, in default units (V)
    def _acquire(self):
        logger.debug("acquire() of signal %s was called! ", self._name)
        # get data
        self._lastvalues = np.random.normal(size=self._config.points)
        self._acquiretime = time.time()

    # placeholder for acquired timetrace implementation
    @property
    def _times(self):
        return np.linspace(0,
                           self._config.traceduration,
                           self._config.points,
                           endpoint=False)
    @property
    def nyquist_frequency(self):
        return self._config.points / self._config.traceduration / 2

    # placeholder for acquired data sample implementation (faster)
    @property
    def sample(self):
        return (np.random.normal() - self.offset) * self.unit_per_V

    # derived quantities from here on, no need to modify in derived class
    @property
    def _values(self):
        # has the timeout expired?
        if self._acquiretime + self._config.acquire_timeout < time.time():
            # take new data then
            self._acquire()
        # return scaled numbers (slower to do it here but nicer code)
        return (self._lastvalues - self.offset) * self.unit_per_V

    @property
    def mean(self): return self._values.mean()

    @property
    def rms(self):
        return np.sqrt(((self._values - self._values.mean())**2).mean())

    @property
    def max(self): return self._values.max()

    @property
    def min(self): return self._values.min()

    @property
    def curve(self):
        """ returns a curve with recent data and a lot of useful parameters"""
        # important: call _values first in order to get the _times
        # corresponding to the measurement setup of _values
        values = self._values
        times = self._times
        return CurveDB.create(times, values,
                              name=self._name,
                              mean=self.mean,
                              rms=self.rms,
                              max=self.max,
                              min=self.min,
                              average=self._config.average,
                              unit=self.unit,
                              unit_per_V=self.unit_per_V,
                              nyquist_frequency=self.nyquist_frequency,
                              acquiretime=self._acquiretime,
                              autosave=self._config.autosave)

    def get_offset(self):
        """ acquires and saves the offset of the signal """
        oldoffset = self.offset
        # make sure data are fresh
        self._acquire()
        self._config["offset"] = self._lastvalues.mean()
        newoffset = self.offset
        logger.debug("Offset for signal %s changed from %s to %s",
                     self._name, oldoffset, newoffset)
        return newoffset

    @property
    def offset(self):
        if self._config.offset_subtraction:
            return self._config.offset or 0
        else:
            return 0

    def get_peak(self):
        # make sure data are fresh
        self._acquire()
        self._config["peak"] = self.mean

        logger.debug("New peak value for signal %s is %s",
                     self._name, self._config.offset)

    @property
    def peak(self):
        """ peak signal value, as present when get_peak was last called"""
        return self._config.peak

    @property
    def redpitaya_input(self): return self._config.redpitaya_input

    @property
    def transfer_function(self):
        try:
            pk = self._config.transfer_function.open_loop
        except KeyError:
            logger.error("No transfer functions available for this output")
            return None
        return CurveDB.get(pk)


class RPSignal(Signal):
    # a signal that lives inside the RedPitaya
    def __init__(self, config, branch, parent, restartscope=lambda: None):
        self._parent = parent
        self._rp = parent.rp
        self._restartscope = restartscope
        super(RPSignal, self).__init__(config, branch)

    @property
    def _redpitaya_input(self):
        return self._config.redpitaya_input

    def _saverawdata(self, data, times):
        self._lastvalues = data
        self._lasttimes = times
        self._acquiretime = time.time()

    def _acquire(self, secondsignal=None):
        logger.debug("acquire() of signal %s was called! ", self._name)
        if secondsignal is None:
            try:
                secondsignal = self._config.secondsignal
            except KeyError:
                pass
        if isinstance(secondsignal, str):
            secondsignal = self._parent.signals[secondsignal]
        if secondsignal is not None:
            input2 = secondsignal._redpitaya_input
            logger.debug("Second signal '%s' for acquisition set up.",
                         secondsignal)
        else:
            input2 = None
        self._rp.scope.setup(duration=self._config.duration,
                             trigger_source=self._config.trigger_source,
                             average=self._config.average,
                             threshold=self._config.threshold,
                             hysteresis=self._config.hysteresis,
                             trigger_delay=self._config.trigger_delay,
                             input1=self._redpitaya_input,
                             input2=input2)
        try:
            timeout = self._config.timeout
        except KeyError:
            timeout = self._rp.scope.duration*5
        self._saverawdata(self._rp.scope.curve(ch=1, timeout=timeout), self._rp.scope.times)
        if secondsignal is not None:
            secondsignal._saverawdata(self._rp.scope.curve(ch=2, timeout=-1), self._rp.scope.times)
        self._restartscope()

    @property
    def _times(self): return self._lasttimes#self._rp.scope.times

    @property
    def sample(self):
        self._rp.scope.input1 = self.redpitaya_input
        return (self._rp.scope.voltage1 - self.offset) * self.unit_per_V

    @property
    def nyquist_frequency(self): return 1.0 / self._rp.scope.sampling_time / 2

    @property
    def curve(self):
        curve = super(RPSignal, self).curve
        extraparams = dict(
            trigger_timestamp = self._rp.scope.trigger_timestamp,
            duration = self._rp.scope.duration)
        curve.params.update(extraparams)
        curve.save()
        return curve


class RPOutputSignal(RPSignal):
    def __init__(self, config, branch, parent, restartscope):
        super(RPOutputSignal, self).__init__(config,
                                             branch,
                                             parent,
                                             restartscope)
        self.setup()

    def setup(self, **kwargs):
        # each output gets its own pid
        if not hasattr(self, "pid"):
            self.pid = self._rp.pids.pop()

        # set voltage limits
        try:
            self.pid.max_voltage = self._config.max_voltage
        except KeyError:
            self._config["max_voltage"] = self.pid.max_voltage
        try:
            self.pid.min_voltage = self._config.min_voltage
        except KeyError:
            self._config["min_voltage"] = self.pid.min_voltage

        # routing of output
        try:
            out = self._config.redpitaya_output
        except KeyError:
            logger.error("Output port for signal signal %s could not be "
                         + "identified.", self._name)
            raise
        if out.startswith("pwm"):
            out = self._rp.__getattribute__(out)
            out.input = self.pid.name
            self.pid.output_direct = "off"
        else:
            self.pid.output_direct = out

        # set input if specified
        try:
            self.pid.input = self._config.redpitaya_input
        except KeyError:
            self.pid.input = "off"

        # configure inputfilter
        try:
            self.pid.inputfilter = self._config.lock.inputfilter
        except (KeyError, AttributeError):
            logger.debug("No inputfilter was defined for output %s. ",
                         self._name)
        # save the current inputfilter to the config file
        try:
            self._config["lock"]["inputfilter"] = self.pid.inputfilter
        except KeyError:
            self._config["lock"] = {"inputfilter": self.pid.inputfilter}

        # configure iir if desired
        self._loadiir()

        # make sure the units of calibration make sense
        if not 'calibrationunits' in self._config._keys():
            calibrations = [k for k in self._config._keys() if k.endswith("_per_V")]
            if not calibrations or len(calibrations) > 1:
                raise ValueError("Too few / too many calibrations for output "
                                 +self._name+" are specified in config file: "
                                 +str(calibrations)
                                 +". Remove all but one to continue.")
            else:
                self._config['calibrationunits'] = calibrations[0]

    def _loadiir(self):
        try:
            # workaround for complex numbers from yaml
            iirzeros = [complex(n) for n in self._config.iir.zeros]
            iirpoles = [complex(n) for n in self._config.iir.poles]
            iirgain = self._config.iir.gain
        except KeyError:
            logger.debug("No iir filter was defined for output %s. ",
                         self._name)
            return
        if not hasattr(self, "iir"):
            self.iir = self._rp.iirs.pop()
        logger.error("IIR setup not implemented at the time being.")

    @property
    def _redpitaya_input(self):
        return self.pid.name

    @property
    def issaturated(self):
        # tells us if the output has saturated
        ival, max, min = self.pid.ival, self.pid.max_voltage, \
                         self.pid.min_voltage
        if ival > max or ival < min:
            return True
        else:
            return False

    def off(self):
        """ Turns off all feedback or sweep """
        self.pid.p = 0
        self.pid.i = 0
        self.pid.d = 0
        self.pid.ival = 0

    def unlock(self):
        if 'lock' in self._config._data and not self._config.lock:
            return
        else:
            self.off()

    def lock(self,
             slope,
             setpoint,
             input=None,
             factor=1.0,
             offset=None):
        """
        Enables feedback with this output. The realized transfer function of
        the pid plus specified external analog filters is a pure integrator,
        to within the limits imposed by the knowledge of the external filters.
        The desired unity gain frequency is stored in the config file.

        Parameters
        ----------
        slope: float
            The slope of the input error signal. If the output is specified in
            units of m_per_V, the slope must come in units of V_per_m.
        setpoint: float
            The lock setpoint in V.
        input: RPSignal or str
            The input signal of the pid. None leaves the currend pid input.
        factor: float
            An extra factor to multiply the gain with for debugging purposes.
        offset:
            The output offset (V) when the lock is enabled.

        Returns
        -------
        None
        """

        # if output is disabled for locking, skip the rest
        if ('lock' not in self._config._keys()) or \
                ("skip" in self._config.lock._keys() and
                 self._config.lock.skip):
            return

        # compute integrator unity gain frequency
        if slope == 0:
            raise ValueError("Cannot lock on a zero slope!")
        integrator_ugf = self._config.lock.unity_gain_frequency * factor * -1
        integrator_ugf /= (self._config[self._config.calibrationunits] * slope)

        # if gain is disabled somewhere, return
        if integrator_ugf == 0:
            self.off()
            logger.warning("Lock called with zero gain! ")
            return

        # if analog lowpass filters are present, also use proportional
        # (first-order lowpass) and derivative (for second-order lowpass) gain
        try:
            lowpass = sorted(self._config.analogfilter.lowpass)
        except KeyError:
            self._config['analogfilter']= {'lowpass': []}
            lowpass = sorted(self._config.analogfilter.lowpass)

        if len(lowpass) >= 0:
            # no analog lowpass -> pure integrator lock
            proportional = 0
            differentiator_ugf = 0
        if len(lowpass) >= 1:
            # set PI corner at first lowpass cutoff
            proportional = integrator_ugf / lowpass[0]
        if len(lowpass) >= 2:
            # set PD corner at second lowpass cutoff if present
            differentiator_ugf = lowpass[1] / proportional
        if len(lowpass) >= 3:
            logger.warning("Output %s: Don't know how to handle >= 3rd order "
                           +"analog filter. Consider IIR design. ")

        if input:
            if isinstance(input, RPSignal):
                self.pid.input = input._config.redpitaya_input
                # correct setpoint for input offset
                setpoint += input.offset
            else:  # probably a string
                self.pid.input = input

        if offset:
            # must turn off gains before setting the offset
            self.off()
            # offset is internal integral value
            self.pid.ival = offset
            # sleep for the lowest analog lowpass damping time to let the
            # offset settle analogically
            if lowpass:
                time.sleep(1.0/lowpass[0])

        # reset inputfilter - allows configuration from configfile in
        # near real time
        self.pid.inputfilter = self._config.lock.inputfilter

        # rapidly turn on all gains
        self.pid.setpoint = setpoint
        self.pid.i = integrator_ugf
        self.pid.p = proportional
        self.pid.d = differentiator_ugf

        # set the offset once more in case the lack of synchronous gain enabling
        # messed up the offset
        if offset:
            self.pid.ival = offset

        # issue a warning if some gain could not be implemented
        for act, set, name in [(self.pid.i, integrator_ugf, "integrator"),
                           (self.pid.p, proportional, "proportional"),
                           (self.pid.d, differentiator_ugf, "differentiator"),
                           (self.pid.setpoint, setpoint, "setpoint")]:
            if set != 0 and (act / set < 0.9 or act / set > 1.1):
                # the next condition is to avoid diverging quotients setpoints
                # near zero
                if not (name == 'setpoint' and abs(act-set) < 1e-3):
                    logger.warning("Implemented value for %s of output %s has "
                            + "saturated more than 10%% away from desired "
                            + "value. Try to modify analog gains.",
                            name, self._name)

    def sweep(self, frequency=None, amplitude=None, waveform=None):
        try:
            kwargs = self._config.sweep._dict
        except KeyError:
            logger.debug("Sweep for output '%s' is disabled.", self._name)
            return None
        if frequency:
            kwargs["frequency"] = frequency
        if waveform:
            kwargs["waveform"] = waveform
        if amplitude:
            kwargs["amplitude"] = amplitude

        # set asg amplitude always to 1.0 and feed sweep through pid instead
        amplitude = kwargs["amplitude"]
        kwargs["amplitude"] = 1.0
        kwargs["output_direct"] = "off"
        if 'asg' in kwargs:
            asgname = kwargs.pop("asg")
        else:
            asgname = 'asg1'
        asg = self._rp.__getattribute__(asgname)
        asg.setup(**kwargs)
        self.pid.input = asgname
        self.pid.p = amplitude
        return asg.frequency

    def save_current_gain(self, factor):
        try:
            ugf = self._config.unity_gain_frequency
        except KeyError:
            pass
        else:
            self._config.lock.unity_gain_frequency = ugf * factor
        self._config.lock.inputfilter = self.pid.inputfilter

    @property
    def output_offset(self):
        return self.pid.ival

    @output_offset.setter
    def output_offset(self, value):
        self.pid.ival = value
        offset = self.pid.ival
        if offset > self._config.max_voltage:
            offset = self._config.max_voltage
        elif offset < self._config.min_voltage:
            offset = self._config.min_voltage
        self._config['lastoffset'] = offset
