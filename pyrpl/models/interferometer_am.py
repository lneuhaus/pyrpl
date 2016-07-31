import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *

class Interferometer_Am(Interferometer):
    """ simplest type of optical interferometer with one photodiode """

    # the variable which we would like to control
    _variable = "transmission"

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
