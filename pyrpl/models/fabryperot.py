import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *


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