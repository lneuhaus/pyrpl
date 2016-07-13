import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *


class Filter(Model):
    """
    Model for a Fabry-Perot cavity in lorentzian approximation
    """

    # the internal variable for state specification
    _variable = 'x'

    export_to_parent = Model.export_to_parent + ['R0']


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

    def setup_pdh(self, **kwargs):
        return super(FabryPerot, self).setup_iq(input='pdh', **kwargs)

    def sweep(self):
        duration = super(FabryPerot, self).sweep()
        self._parent.rp.scope.setup(trigger_source='asg1',
                                    duration=duration)
        if "scopegui" in self._parent.c._dict:
            if self._parent.c.scopegui.auto_run_continuous:
                self._parent.rp.scope_widget.run_continuous()

    def relative_reflection(self):
        self.inputs["reflection"]._acquire()
        return self.inputs["reflection"].mean / self.reflection(1000)

    def relative_pdh_rms(self, avg=1):
        """ Returns the pdh rms normalized by the peak amplitude of pdh.
        With fpm cavity settings (typical), avg=50 yields values that
        scatter less than a percent. Best way to optimize a pdh lock. """
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

    def islocked(self):
        """ returns True if cavity is locked """
        input = None
        for i in self.inputs.keys():
            if i == "reflection" or i == "transmission":
                input = i
                break
        if input is None:
            raise KeyError("No transmission or reflection signal found.")
        self.inputs[input]._acquire()
        mean = self.inputs[input].mean
        set = abs(self.state["set"][self._variable])
        error_threshold = self._config.lock.error_threshold
        thresholdvalue = self.__getattribute__(input)(set + error_threshold)
        if input == "reflection":
            return (mean <= thresholdvalue)
        else:
            return (mean >= thresholdvalue)
