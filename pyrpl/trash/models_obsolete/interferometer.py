import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *


class Interferometer(Model):
    """ simplest type of optical interferometer with one photodiode """

    # the variable which we would like to control
    _variable = "phase"

    # theoretical model for input signal 'transmission'
    def transmission(self, phase):
        phase = phase * np.pi / 180.0
        """ photocurrent of an ideal interferometer vs phase (rad)"""
        amplitude = (self.inputs['transmission']._config.max
                     - self.inputs['transmission']._config.min) / 2
        mean = (self.inputs['transmission']._config.max
                     + self.inputs['transmission']._config.min) / 2
        return np.sin(phase) * amplitude + mean

    def iq(self, phase):
        phase = phase * np.pi / 180.0
        amplitude = (self.inputs['iq']._config.max
                     - self.inputs['iq']._config.min) / 2
        mean = (self.inputs['iq']._config.max
            + self.inputs['iq']._config.min) / 2
        return np.cos(phase) * amplitude + mean

    # how phase converts to other units that are used in the configfile
    @property
    def phase_per_m(self):
        return 360.0 / self._config.wavelength

    # how to estimate the actual phase
    @property
    def phase(self):
        return self.variable % (360.0)

    #def lock(self, phase=0, factor=1):
    #    return self._lock(phase=phase,
    #                      input='transmission',
    #                      offset=0,
    #                      factor=factor)

    def calibrate(self):
        return super(Interferometer, self).calibrate(
            scopeparams={'secondsignal': 'piezo'})

    def sweep(self):
        duration = super(Interferometer, self).sweep()
        self._parent.rp.scope.setup(trigger_source='asg1',
                                    duration=duration)
        if "scopegui" in self._parent.c._dict:
            if self._parent.c.scopegui.auto_run_continuous:
                self._parent.rp.scope_widget.run_continuous()

    def islocked(self):
        """ returns True if locked, else False """
        # copy paste of model.islocked except for the modulo operation
        if hasattr(self, self._variable):
            variable = self.__getattribute__(self._variable)
        else:
            variable = self.variable
        diff = ((variable - self.state["set"][self._variable]+90.0) %
                180.0)-90.0
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
