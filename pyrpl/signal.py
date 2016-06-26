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
        if self._acquiretime + self._config.timeout < time.time():
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
                              autosave=self._config.autosave
                              )

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


class RPSignal(Signal):
    # a signal that lives inside the RedPitaya
    def __init__(self, config, branch, redpitaya):
        self._rp = redpitaya
        super(RPSignal, self).__init__(config, branch)

    def _acquire(self):
        logger.debug("acquire() of signal %s was called! ", self._name)
        self._rp.scope.setup(duration=self._config.duration,
                             trigger_source='immediately',
                             average=self._config.average,
                             trigger_delay=0,
                             input1=self._config.redpitaya_input)
        self._lastvalues = \
                (self._rp.scope.curve(ch=1, timeout=self._config.duration*5)
                - self.offset) * self.unit_per_V
        self._acquiretime = time.time()

    @property
    def _times(self): return self._rp.scope.times

    @property
    def sample(self):
        self._rp.scope.input1 = self._config.redpitaya_input
        return (self._rp.scope.voltage1 - self.offset) * self.unit_per_V

    @property
    def nyquist_frequency(self): return 1.0 / self._rp.scope.sampling_time / 2

class RPOutputSignal(RPSignal):
    def __init__(self, config, branch, redpitaya):
        super(RPOutputSignal, self).__init__(config, branch, redpitaya)

        # each output gets its own pid
        if not hasattr(self, "pid"):
            self.pid = self._rp.pids.pop()

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

        # input off for now
        self.pid.input = "off"

        # configure inputfilter
        try:
            self.pid.inputfilter = self._config.inputfilter
        except KeyError:
            logger.debug("No inputfilter was defined for output %s. ",
                         self._name)
        # save the current inputfilter to the config file
        self._config["inputfilter"] = self.pid.inputfilter

        # configure iir if desired
        self._loadiir()

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


    def lock_off(self):
        self.pid.p = 0
        self.pid.i = 0
        self.pid.d = 0

    def lock_opt(self, slope=None, errorsignal=None, setpoint=None, factor=1.0):
        pass

