import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *


class FabryPerot(Model):
    """
    Model for a Fabry-Perot cavity in lorentzian approximation
    """

    # the internal variable for state specification
    _variable = 'detuning'

    export_to_parent = Model.export_to_parent + ['R0']

    # lorentzian functions
    def _lorentz(self, x):
        return 1.0 / (1.0 + x ** 2)

    def _lorentz_slope(self, x):
        return -2.0*x / (1.0 + x ** 2)**2

    def _lorentz_slope_normalized(self, x):
        # max slope occurs at x +- 1/sqrt(3)
        return self._lorentz_slope(x) / abs(self._lorentz_slope(1/np.sqrt(3)))

    def _lorentz_slope_slope(self, x):
        return (-2.0+6.0*x**2) / (1.0 + x ** 2)**3

    def _lorentz_slope_normalized_slope(self, x):
        """ slope of normalized slope (!= normalized slope of slope) """
        return (-2.0+6.0*x**2) / (1.0 + x ** 2)**3  \
               / abs(self._lorentz_slope(np.sqrt(3)))

    def _pdh_normalized(self, x, sbfreq=10.0, phase=0, eta=1):
        # pdh only has appreciable slope for detunings between -0.5 and 0.5
        # unless you are using it for very exotic purposes..
        # incident beam: laser field
        # a at x,
        # 1j*a*rel at x+sbfreq
        # 1j*a*rel at x-sbfreq
        # in the end we will only consider cross-terms so the parameter rel will be normalized out
        # all three fields incident on cavity
        # eta is ratio between input mirror transmission and total loss (including this transmission),
        # i.e. between 0 and 1. While there is a residual dependence on eta, it is very weak and
        # can be neglected for all practical purposes.
        # intracavity field a_cav, incident field a_in, reflected field a_ref    #
        # a_cav(x) = a_in(x)*sqrt(eta)/(1+1j*x)
        # a_ref(x) = -1 + eta/(1+1j*x)
        def a_ref(x):
            return 1 - eta / (1 + 1j * x)

        # reflected intensity = abs(sum_of_reflected_fields)**2
        # components oscillating at sbfreq: cross-terms of central lorentz with either sideband
        i_ref = np.conjugate(a_ref(x)) * 1j * a_ref(x + sbfreq) \
                + a_ref(x) * np.conjugate(1j * a_ref(x - sbfreq))
        # we demodulate with phase phi, i.e. multiply i_ref by e**(1j*phase), and take the real part
        # normalization constant is very close to 1/eta
        return np.real(i_ref * np.exp(1j * phase)) / eta

    def transmission(self, x):
        " transmission of the Fabry-Perot "
        return self._lorentz(x) * self._config.resonant_transmission

    def reflection(self, x):
        " reflection of the Fabry-Perot"
        offres = self._config.offresonant_reflection
        res = self._config.resonant_reflection
        return (res-offres) * self._lorentz(x) + offres

    def pdh(self, x):
        sbfreq = self.signals["pdh"]._config.setup.frequency \
                 * self.detuning_per_Hz
        return self._pdh_normalized(x, sbfreq=sbfreq) \
               * self._config.peak_pdh

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
    def detuning_per_Hz(self):
        " detuning of +-1 corresponds to the half-maximum intracavity power "
        fsr = 2.99792458e8 / 2 / self._config.length
        linewidth = fsr / self._config.finesse
        return 1.0 / (linewidth / 2)

    @property
    def detuning(self):
        detuning = self.variable
        # force the sign of detuning to be the right one,
        # because reflection and transmission are even functions
        if self.state['set']['detuning'] * detuning < 0:
            self.logger.debug("Detuning estimation converged to wrong sign. "
                              "Sign was corrected. ")
            return detuning * -1
        else:
            return detuning

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

    def calibrate(self):
        curves = super(FabryPerot, self).calibrate(
            scopeparams={'secondsignal': 'piezo'})
        duration = curves[0].params["duration"]

        # pick our favourite available signal
        for sig in self.inputs.values():
            # make a zoom calibration over roughly 10 linewidths
            curves = super(FabryPerot, self).calibrate(
                inputs=[sig],
                scopeparams={'secondsignal': 'piezo',
                             'trigger_source': 'ch1_positive_edge',
                             'threshold': sig._config.max *
                                  self._config.calibration.relative_threshold,
                             'duration': duration
                                         * self._config.calibration.zoomfactor,
                             'timeout': duration*10})
            if sig._name == 'reflection':
                self._config["offresonant_reflection"] = sig._config.max
                self._config["resonant_reflection"] = sig._config.min
            if sig._name == 'transmission':
                self._config["resonant_transmission"] = sig._config.max
            if sig._name == 'pdh':
                self._config["peak_pdh"] = (sig._config.max - sig._config.min)/2
        return curves

    def relative_reflection(self):
        self.inputs["reflection"]._acquire()
        return self.inputs["reflection"].mean / self.reflection(1000)

    def relative_pdh_rms(self, avg = 1):
        if avg > 1:
            sum = 0
            for i in range(avg):
                sum += self.relative_pdh_rms()**2
            return np.sqrt(sum/avg)
        else:
            self.signals["pdh"]._acquire()
            rms = self.signals["pdh"].rms
            relrms = rms / self._config.peak_pdh
            self._pdh_rms_log.log(relrms)
            return relrms

