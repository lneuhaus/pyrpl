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

    Parameters
    ----------
    config: MemoryBranch
        Any memorybranch of the MemoryTree object corresponding to the
        config file that defines this signal.
    branch: str
        The branch name that defines the signal.
        Example: "mysignals.myinputs.myinput"
    """
    def __init__(self, config, branch):
        # get the relevant config branch from config tree
        self._config = config._getbranch(branch, defaults=config.signal)
        # signal name = branch name
        self._name = self._config._branch
        self._acquiretime = 0

    # The units in which the signal will be calibrated
    unit = ExposedConfigParameter("unit")

    def __repr__(self):
        return str(self.__class__)+"("+self._name+")"

    @property
    def unit_per_V(self):
        """ The factor to convert this signal from Volts to the units as
        specified in the config file. Setting this property will affect the
        config file. """
        return self._config[self.unit + "_per_V"]

    @unit_per_V.setter
    def unit_per_V(self, value):
        self._config[self.unit + "_per_V"] = value

    # placeholder for acquired data implementation, in default units (V)
    def _acquire(self):
        """
        Acquires new data for the signal. Automatically called
        once the buffered data are older than the timeout specified in the
        signal configuration, but it can often be useful to manually enforce
        a new acquisition through this function.

        Returns
        -------
        None
        """
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
        """ Returns the nyquist frequency of the predefined measurements
        such as mean, rms, curve, min, max """
        return self._config.points / self._config.traceduration / 2

    # placeholder for acquired data sample implementation (faster)
    @property
    def sample(self):
        """ Returns one most recent sample of the signal. Does not rely on
        self._acquire. """
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
    def mean(self):
        """ Returns the mean of the last signal acquisition """
        return self._values.mean()

    @property
    def rms(self):
        """ Returns the rms of the last signal acquisition """
        return np.sqrt(((self._values - self._values.mean())**2).mean())

    @property
    def max(self):
        """ Returns the maximum of the last signal acquisition """
        return self._values.max()

    @property
    def min(self):
        """ Returns the minimum of the last signal acquisition """
        return self._values.min()

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
    def transfer_function(self):
        try:
            pk = self._config.transfer_function.open_loop
        except KeyError:
            logger.error("No transfer functions available for this output")
            return None
        return CurveDB.get(pk)


class RPSignal(Signal):
    """
    A Signal that corresponds to an inputsignal of the DSPModule inside
    the RedPitaya

    Parameters
    ----------
    config: MemoryBranch
        Any memorybranch of the MemoryTree object corresponding to the
        config file that defines this signal.
    branch: str
        The branch name that defines the signal.
        Example: "mysignals.myinputs.myinput"
    parent: Pyrpl
        The Pyrpl object hosting this signal. In principle, any object
        containing an attribute 'rp' referring to a RedPitaya object can be
        parent.
    restartscope: function
        The function that the signal calls after acquisition to reset the
        scope to its orignal state.
    """
    def __init__(self, config, branch, parent, restartscope=lambda: None):
        self._parent = parent
        self._rp = parent.rp
        self._restartscope = restartscope
        super(RPSignal, self).__init__(config, branch)

    @property
    def redpitaya_input(self):
        """
        Returns
        -------
        input: str
            The DSPModule name of the input signal corresponding to this
            signal in the redpitaya """
        return self._config.redpitaya_input

    def _saverawdata(self, data, times):
        self._lastvalues = data
        self._lasttimes = times
        self._acquiretime = time.time()

    def _acquire(self, secondsignal=None):
        """
        Acquires new data for the signal. Automatically called
        once the buffered data are older than the timeout specified in the
        signal configuration, but it can often be useful to manually enforce
        a new acquisition through this function.

        Parameters
        ----------
        secondsignal: Signal or str
            Signal or name of signal that should be recorded simultaneously
            with this signal. The result will be directly stored in the second
            signal and can be retrieved through properties like curve or
            mean of the second signal.

        Returns
        -------
        None
        """
        logger.debug("acquire() of signal %s was called! ", self._name)
        if secondsignal is None:
            try:
                secondsignal = self._config.secondsignal
            except KeyError:
                pass
        if isinstance(secondsignal, str):
            secondsignal = self._parent.signals[secondsignal]
        if secondsignal is not None:
            input2 = secondsignal.redpitaya_input
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
                             input1=self.redpitaya_input,
                             input2=input2)
        try:
            timeout = self._config.timeout
        except KeyError:
            timeout = self._rp.scope.duration*5
        self._saverawdata(self._rp.scope.curve(ch=1, timeout=timeout),
                          self._rp.scope.times)
        if secondsignal is not None:
            secondsignal._saverawdata(self._rp.scope.curve(ch=2, timeout=-1),
                                      self._rp.scope.times)
        self._restartscope()

    @property
    def _times(self):
        return self._lasttimes#self._rp.scope.times

    @property
    def sample(self):
        """ Returns a single sample of the signal"""
        self._rp.scope.input1 = self.redpitaya_input
        return (self._rp.scope.voltage1 - self.offset) * self.unit_per_V

    @property
    def nyquist_frequency(self):
        """ Returns the nyquist frequency of the predefined measurements
        such as mean, rms, curve, min, max """
        return 1.0 / self._rp.scope.sampling_time / 2

    @property
    def curve(self):
        """ Returns a CurveDB object with the last result of _acquitision """
        curve = super(RPSignal, self).curve
        extraparams = dict(
            trigger_timestamp=self._rp.scope.trigger_timestamp,
            duration=self._rp.scope.duration)
        curve.params.update(extraparams)
        curve.save()
        return curve

    def fit(self, *args, **kwargs):
        """ shortcut to the function fit of the underlying model """
        self._parent.fit(input=self, *args, **kwargs)


class RPOutputSignal(RPSignal):
    """
    A Signal that drives an output of the RedPitaya. It shares all
    properties of RPSignal (an input signal), but furthermore reserves a PID
    module to forward its input to an output of the redpitaya. Proper
    configuration in the config file leads to almost automatic locking
    behaviour: If the output signal knows its transfer function, it can
    adjust the PID parameters to provide an ideal proportional or integral
    transfer function.

    Parameters
    ----------
    config: MemoryBranch
        Any memorybranch of the MemoryTree object corresponding to the
        config file that defines this signal.
    branch: str
        The branch name that defines the signal.
        Example: "mysignals.myinputs.myinput"
    parent: Pyrpl
        The Pyrpl object hosting this signal. In principle, any object
        containing an attribute 'rp' referring to a RedPitaya object can be
        parent.
    restartscope: function
        The function that the signal calls after acquisition to reset the
        scope to its orignal state.
    """
    def __init__(self, config, branch, parent, restartscope):
        super(RPOutputSignal, self).__init__(config,
                                             branch,
                                             parent,
                                             restartscope)
        self.setup()

    def setup(self, **kwargs):
        """
        Sets up the output according to the config file specifications.

        Parameters
        ----------
        kwargs: dict
            Not used here, but present to ease overwriting in derived signal
            classes since the API typically passes all setup parameters of the
            signal here.

        Returns
        -------
        None
        """
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

        # is a second pid needed?
        if self._pid2_filter or self._second_integrator_crossover > 0:
            # if we already have a pid2, let's return it to the stack first
            if hasattr(self, 'pid2'):
                self.pid2.p = 0
                self.pid2.i = 0
                self.pid2.d = 0
                self.pid2.ival = 0
                self._rp.pids.append(self.pid2)
            # self.pid has been configured on the output side. Therfore we
            # rename it to pid2 and create a new self.pid for the intput
            # configuration to be compatible with the single-pid code.
            self.pid2 = self.pid
            self.pid = self._rp.pids.pop()
            logger.debug("Second PID %s acquired for output %s.",
                         self.pid.name, self._name)
            self.pid2.inputfilter = self._pid2_filter
            self.pid2.input = self.pid.name
            self.pid.max_voltage = 1
            self.pid.min_voltage = -1
            self.pid.p = 1.0

        # configure inputfilter
        try:
            self.pid.inputfilter = self._config.lock.inputfilter
        except (KeyError, AttributeError):
            logger.debug("No inputfilter was defined for output %s. ",
                         self._name)

        # save the current inputfilter to the config file
        try:
            self._config["lock"]["inputfilter"] = self._inputfilter
        except KeyError:
            self._config["lock"] = {"inputfilter": self._inputfilter}

        # set input to off
        self.pid.input = "off"

        # configure iir if desired
        self.setup_iir()

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

    @property
    def issaturated(self):
        """
        Returns
        -------

        True: if the output has saturated
        False: otherwise
        """
        ival, max, min = self.pid.ival, self.pid.max_voltage, \
                         self.pid.min_voltage
        if ival > max or ival < min:
            return True
        else:
            return False

    def off(self):
        """ Turns off all feedback gains, sweeps and sets the offset to
        zero. """
        self.pid.p = 0
        self.pid.i = 0
        self.pid.d = 0
        self.pid.ival = 0
        if hasattr(self, 'pid2'):
            self.pid2.i = 0
            self.pid2.p = 1
            self.pid2.d = 0
            self.pid2.ival = 0

    def unlock(self):
        """ Turns the signal lock off if the signal is used for locking """
        if self._skiplock:
            return
        else:
            self.off()

    def lock(self,
             slope,
             setpoint=None,
             input=None,
             factor=1.0,
             offset=None,
             second_integrator=0,
             setup_iir=False):
        """
        Enables feedback with this output. The realized transfer function of
        the pid plus specified external analog filters is a pure integrator if
        the config file defines unity_gain_frequency for the output, or a pure
        proportional gain if the config file defines proportional_gain for the
        output. This transfer function can be further refined by
        setting the fields 'inputfilter' and 'iir' for the output in the config
        file. An incorrect specification of the external analog filter will
        result in an imperfect transfer function.

        Parameters
        ----------
        slope: float or None
            The slope of the input error signal. If the output is specified in
            units of m_per_V, the slope must come in units of V_per_m. None
            leaves the current slope unchanged (also ignores factor).
        setpoint: float or None
            The lock setpoint in V. None leaves the setpoint unchanged
        input: RPSignal oror None
            The input signal of the pid, either as RPSignal object.  None
            leaves the currend pid input.
        factor: float
            An extra factor to multiply the gain with for debugging purposes.
        offset: float or None
            The output offset (V) when the lock is enabled.
        second_integrator: float
            Factor to multiply a predefined second integrator gain with. Useful
            for ramping up the second integrator in a smooth fashion.
        setup_iir: bool
            If True, no iir filter is set up. Usually, it is enough to
            switch on the iir filter only in the final step. This results in a
            gain in speed and avoids saturation of internal degrees of
            freedom of the IIR.

        Returns
        -------
        None
        """

        # if output is disabled for locking, skip the rest
        if self._skiplock:
            return

        # normalize slope to our units
        slope *= self._config[self._config.calibrationunits]

        # design the loop shape
        loopshape = self._config.lock._dict  # maybe rename the branch to loopshape
        if ("unity_gain_frequency" in loopshape
                                and "proportional_gain" in loopshape):
            raise ValueError("Output " + self._name + " loopshape is "
                    "overdefined. Defines either unity_gain_frequency or "
                    "proportional_gain, but not both!")
        if slope is None:
            if "unity_gain_frequency" in loopshape:
                integrator_on = True
                gain = self.pid.i
            else:  # "proportional" in loopshape:
                integrator_on = False
                gain = self.pid.p
        elif slope == 0:
            raise ValueError("Cannot lock on a zero slope!")
        else:
            if "unity_gain_frequency" in loopshape:
                integrator_on = True
                gain = self._config.lock.unity_gain_frequency
            else:  # "proportional" in loopshape:
                integrator_on = False
                gain = self._config.lock.proportional_gain
            gain *= factor * -1 / slope

        # if gain is disabled somewhere, return
        if gain == 0:
            self.off()
            logger.warning("Lock called with zero gain! ")
            return

        # if analog lowpass filters are present, try to adjust transfer
        # function in order to compensate for it with PID
        try:
            lowpass = sorted(self._config.analogfilter.lowpass)
        except KeyError:
            self._config['analogfilter']= {'lowpass': []}
            lowpass = sorted(self._config.analogfilter.lowpass)
        if integrator_on:
            integrator_ugf = gain
        else:
            integrator_ugf = 0
            # pretending there was a 1Hz analog filter will get us the right
            # proportional gain with or without integrator in the next block
            lowpass = [1.0] + lowpass

        if len(lowpass) >= 0:  # i.e. always
            # no analog lowpass -> pure integrator lock
            proportional = 0
            differentiator_ugf = 0
        if len(lowpass) >= 1:
            # set PI corner at first lowpass cutoff
            proportional = gain / lowpass[0]
        if len(lowpass) >= 2:
            # set PD corner at second lowpass cutoff if present
            differentiator_ugf = lowpass[1] / proportional
        if len(lowpass) >= 3:
            logger.warning("Output %s: Don't know how to handle >= 3rd order "
                           +"analog filter. Consider IIR design. ")

        if input is not None:
            if not isinstance(input, RPSignal):
                logger.error("Input %s must be a RPSignal instance.", input)
            self.pid.input = input.redpitaya_input
        # if iir was used, input may be on the iir at the moment
        elif (self.pid.input == 'iir') and hasattr(self, "iir"):
            self.pid.input = self.iir.input

        # get inputoffset
        if input is None:
            inputbranch = self._config._root.inputs["self.pid.input"]
            if inputbranch.offset_subtraction:
                inputoffset = inputbranch.offset
            else:
                inputoffset = 0
        else:
            inputoffset = input.offset

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
        if hasattr(self, 'pid2'):
            self.pid2.inputfilter = self._pid2_filter

        # setup iir filter if it is configured - this takes care of input
        # signal routing. To be executed, set 'setup_iir: true' in the
        # appropriate lock stage in the config file
        if setup_iir:
            self.setup_iir()

        # rapidly turn on all gains
        if setpoint is None:
            setpoint = self.pid.setpoint
        else:
            self.pid.setpoint = setpoint + inputoffset
        self.pid.i = integrator_ugf
        self.pid.p = proportional
        self.pid.d = differentiator_ugf
        if second_integrator != 0:
            if hasattr(self, 'pid2'):
                self.pid2.i = self._second_integrator_crossover\
                              * second_integrator
                self.pid2.p = 1.0

        # set the offset once more in case the lack of synchronous gain enabling
        # messed up the offset
        if offset:
            self.pid.ival = offset
            if hasattr(self, 'pid2'):
                self.pid2.ival = 0

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

    def save_current_gain(self, slope=1.0):
        """ converts the current transfer function of the output into its
        default transfer function by updating relevant settings in the
        config file.

        Parameters
        ----------
        slope: float
            the slope that lock would receive at the current setpoint.

        Returns
        -------
        None
        """
        # normalize slope to our units
        slope *= self._config[self._config.calibrationunits]
        # save inputfilters
        self._config.lock.inputfilter = self._inputfilter
        # save new pid gains
        newgains = {"p": self.pid.p,
                    "i": self.pid.i,
                    "d": self.pid.d}
        # first take care of pid2 if it exists
        if hasattr(self, "pid2"):
            newgains['p'] *= self.pid2.p
            if self.pid2.d != 0:
                if newgains["d"] == 0:
                    newgains["d"] = self.pid2.d
                else:
                    logger.error('Nonzero differential gain in pid2 '
                                 'of output %s detected. No method '
                                 'implemented to record this gain in the '
                                 'config file. Please modify '
                                 'RPOutputsignal.save_current_gain '
                                 'accordingly! ')
            if self.pid2.i != 0:
                self._config.lock['second_integrator_crossover'] = \
                    self.pid2.i / self.pid2.p
        # now we only need to transcribe newgains into the config file
        lowpass = []
        if newgains['i'] == 0:  # means config file cannot have
            # unity_gain_frequency entry
            if "unity_gain_frequency" in self._config.lock._keys():
                self._config.lock._data.pop("unity_gain_frequency")
            self._config.lock.proportional_gain = newgains["p"] * -1 * slope
        else:
            # remove possible occurrence of proportional_gain
            if "proportional_gain" in self._config.lock._keys():
                self._config.lock._data.pop("proportional_gain")
            self._config.lock.unity_gain_frequency = newgains["i"] * -1 * slope
            if newgains['p'] != 0:
                lowpass.append(newgains['i']/newgains['p'])
            elif newgains['d'] != 0:  # strange case where d != 0 and p ==0
                lowpass.append(1e20)
        if newgains['d'] != 0:
            lowpass.append(newgains['d'] * newgains['p'])
        # save lowpass setting
        self._config['analogfilter']['lowpass'] = lowpass


    def sweep(self, frequency=None, amplitude=None, waveform=None):
        """ If the signal configuration contains a sweep section, this one
        is executed here to provide the predefined sweep at the output. """
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
        self._asg = asg  # for future reference
        asg.setup(**kwargs)
        self.pid.input = asgname
        self.pid.p = amplitude
        return asg.frequency

    @property
    def _sweep_triggerphase(self):
        """ returns the last scopetriggerphase for the sweeping asg """
        return self._asg.scopetriggerphase

    def _analogfilter(self, frequencies):
        tf = np.array(frequencies, dtype=np.complex)*0.0 + 1.0
        try:
            lp = self._config.analogfilter.lowpass
        except KeyError:
            return tf
        else:
            for p in lp:
                tf /= (1.0 + 1j * frequencies / p)
            return tf

    @property
    def sweep_triggerphase(self):
        """ returns the last scopetriggerphase for the sweeping asg,
        corrected for phase delay due to analog output filters of the output"""
        if hasattr(self, '_asg') and self._asg.amplitude != 0:
            f = self._asg.frequency
            analogdelay = np.angle(self._analogfilter(f), deg=True)
            return (self._sweep_triggerphase + analogdelay) % 360
        else:
            return 0

    @property
    def output_offset(self):
        """ The output offset of the output signal. At the moment simply a
        pointer to self.pid.ival """
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

    @property
    def _skiplock(self):
        if 'lock' not in self._config._keys():
            return True
        if 'skip' in self._config.lock._keys():
            if self._config.lock.skip:
                return True
        return False

    @property
    def _pid2_filter(self):
        # this is a method to get the pid2 filter coefficients
        # future implementation might change where this value is stored
        try:
            return self._config.lock.inputfilter[len(self.pid.inputfilter):]
        except KeyError:
            return []

    @property
    def _inputfilter(self):
        if hasattr(self, 'pid2'):
            return self.pid.inputfilter + self.pid2.inputfilter
        else:
            return self.pid.inputfilter

    @property
    def _second_integrator_crossover(self):
        try:
            sic = self._config.lock.second_integrator_crossover
        except KeyError:
            sic = 0
        return sic


    @property
    def redpitaya_input(self):
        """
        Returns
        -------
        input: str
            The DSPModule name of the input signal corresponding to this
            signal in the redpitaya """
        return self.pid.name

    def setup_iir(self, **kwargs):
        """
        Inserts an iir filter before the output pid. For correct routing,
        the pid input must be set correctly, as the iir filter will reuse
        the pid input setting as its own input and send its output through
        the pid.

        Parameters
        ----------
        kwargs: dict
            Any kwargs that are accepted by IIR.setup(). By default,
            the output's iir section in the config file is used for these
            parameters.

        Returns
        -------
        None
        """
        # load data from config file
        try:
            iirconfig = self._config.iir._dict
        except KeyError:
            logger.debug("No iir filter was defined for output %s. ",
                         self._name)
            return
        else:
            logger.debug("Setting up IIR filter for output %s. ", self._name)
        # overwrite defaults with kwargs
        iirconfig.update(kwargs)
        # workaround for complex numbers from yaml
        iirconfig["zeros"] = [complex(n) for n in iirconfig.pop("zeros")]
        iirconfig["poles"]= [complex(n) for n in iirconfig.pop("poles")]
        # get module
        if not hasattr(self, "iir"):
            self.iir = self._rp.iirs.pop()
            logger.debug("IIR filter retrieved for output %s. ", self._name)
        # output_direct off, since iir goes through pid
        iirconfig["output_direct"] = "off"
        # input setting -> copy the pid input if it is not erroneously on iir
        pidinput = self.pid.input
        if pidinput != 'iir':
            iirconfig["input"] = pidinput
        # setup
        self.iir.setup(**iirconfig)
        # route iir output through pid
        self.pid.input = self.iir.name
