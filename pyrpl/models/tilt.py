import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *
from pyinstruments import CurveDB


class TEM02FabryPerot(FabryPerot):
    export_to_parent = ['unlock', 'sweep', 'islocked',
                        'save_current_gain', 'calibrate',
                        'lock_tilt', 'lock_transmission', 'lock', 'get_tilt_offset']

    #def tilt(self, detuning):
    #    return self._lorentz_slope_normalized(detuning)*self._parent.tilt._config.slope_sign \
    #           * 0.5 * (self._parent.tilt._config.max-self._parent.tilt._config.min)


    def _tilt(self, detuning, scale=1.0, y0=0, phase=0, eta=1):
        #detuning = (self.x()-x0)*detuning_per_time
        #    return self._lorentz_slope_normalized(detuning)*scale+y0
        #eta = 1.0
        phase*=np.pi/180.0
        def a_ref(x):
            return 1 - eta / (1 + 1j * x)
        x = detuning
        return scale*np.real(a_ref(x) * np.exp(1j * phase)) - np.real(a_ref(100000) * np.exp(1j * phase))/eta+y0

    def tilt(self, detuning):
        id = self._config.tilt_fit
        cp = CurveDB.get(id).params
        params = dict()
        for param in ['scale', 'y0', 'phase', 'eta']:
            params[param] = cp[param]
        return self._tilt(detuning, **params)

    def transmission(self, detuning):
        return self._lorentz(detuning)*self._parent.transmission._config.max \
               + self._parent.transmission._config.min

    def _tilt_normalized(self, x, phase=0):
        def a_ref(x):
            return 1 - eta / (1 + 1j * x)
        return np.real(a_ref(x) * np.exp(1j * phase))

    #def calibrate(self):
    #    self.unlock()
    #    duration = self.sweep()
    #    # input signal calibration
    #    for input in self.inputs.values():
    #        try:
    #            input._config._data["trigger_source"] = "asg1"
    #            input._config._data["duration"] = duration
    #            input._acquire()
    #            curve, ma, mi = input.curve, input.max, input.min
    #            input._config._data["trigger_source"] = "ch1_positive_edge"
    #            input._config._data["threshold"] = ma*self._config.calibration_threshold
    #            input._config._data["trigger_delay"] = 0
    #            # input._config._data["hysteresis_ch1"] = ma / 20
    #            input._config._data["duration"] = duration/self._config.calibration_zoom
    #            input._config._data["timeout"] = duration*5
    #            input._acquire()
    #            curve, ma, mi = input.curve, input.max, input.min
    #        finally:
    #            # make sure to reload config file here so that the modified
    #            # scope parameters are not written to config file
    #            self._parent.c._load()
    #        input._config["max"] = ma
    #        input._config["min"] = mi
    #
    #    # turn off sweeps
    #    self.unlock()

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

    #def lock(self, detuning=0, factor=1.0, stop=False):
    #    while not self.islocked():
    #        self._parent.piezo.pid.ival = self._config.lock.drift_offset
    #        self.lock_transmission(factor=factor, detuning=self._config.lock.drift_detuning)
    #        time.sleep(self._config.lock.drift_timeout)
    #    if stop:
    #        return
    #    self.lock_transmission(detuning = self._config.lock.drift_detuning*0.66)
    #    time.sleep(0.01)
    #    return self.lock_tilt(detuning=detuning, factor=factor)

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

    def get_tilt_offset(self):
        self.inputs["tilt"].get_offset()
