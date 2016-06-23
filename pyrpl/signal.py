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

    @property
    def unit_per_V(self):
        return self._config[self.unit+"_per_V"]

    @unit_per_V.setter
    def unit_per_V(self, value):
        self._config[self.unit+"_per_V"] = value

    # placeholder for acquired data implementation
    def _acquire(self):
        logger.debug("acquire() of signal %s was called! ", self._name)
        self._lastvalues = (np.random.normal(size=self._config.points) \
                           -self._offset) * self.unit_per_V
        self._acquiretime = time.time()

    # placeholder for acquired timetrace implementation
    @property
    def _times(self):
        return np.linspace(0,
                           self._config.traceduration,
                           self._config.points,
                           endpoint=False)

    # placeholder for acquired data sample implementation (faster)
    @property
    def sample(self):
        return np.random.normal() * self.unit_per_V

    # derived quantities from here on, no need to modify in derived class
    @property
    def _values(self):
        # has the timeout expired?
        if self._acquiretime + self._config.timeout < time.time():
            # take new data then
            self._acquire()
        return self._lastvalues

    @property
    def mean(self):
        return self._values.mean() # already scaled in _values

    @property
    def rms(self):
        return np.sqrt(((self._values - self._values.mean())**2).mean())

    @property
    def max(self):
        return self._values.max()

    @property
    def min(self):
        return self._values.min()

    def get_offset(self):
        oldoffset = self._offset
        # make sure data are fresh
        self._acquire()
        newoffset = self.mean + oldoffset
        self._config["offset"] = newoffset
        logger.debug("New offset for signal %s is %s",
                     self._name, newoffset)
        return newoffset

    @property
    def _offset(self):
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
                              acquiretime=self._acquiretime,
                              autosave=self._config.autosave
                              )


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
            self._rp.scope.curve(ch=1, timeout=self._config.duration*5) \
            * self.unit_per_V
        self._acquiretime = time.time()

    @property
    def _times(self):
        return self._rp.scope.times

    @property
    def sample(self):
        self._rp.scope.input1 = self._config.redpitaya_input
        return self._rp.scope.voltage1 * self.unit_per_V
