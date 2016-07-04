import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *

class FPMembranes(FabryPerot):
    def pdh(self, detuning):
        offset = self._config.offset_pdh
        phi = self._config.phase_pdh
        ampl = self._config.ampl_pdh
        width = c/(4*self._config.cavity_length*self._config.finesse)
        mod = self._config.mod_pdh

        detuning = detuning*width

        f1 = 2 * ampl * detuning * width * (mod ** 2)
        numer = ((detuning ** 2 + width ** 2 - mod ** 2) * np.cos(phi) - 2 * width * mod * np.sin(phi))
        denom = ((detuning ** 2 + width ** 2) * (width ** 2 + (detuning - mod) ** 2) * (width ** 2 + (detuning + mod) ** 2))
        ret = offset + f1 * numer / denom

        return ret

    def lock_pdh(self, factor=1.):
        """
        initial_detuning = 0.2
        for index, output in enumerate(self.outputs.values()):
            if index==0:
                offset = 1
            else:
                offset = None
            output.lock(self.pdh_slope(initial_detuning)*self.detuning_per_m, initial_detuning, self.inputs['pdh'], factor=1, offset=offset)
        """
        self._lock(input=self.inputs["pdh"],
                   factor=factor,
                   detuning=-0.2,
                   offset=1.)

    lock = lock_pdh

    def change_detuning(self, detuning):
        """
        Dirty and temporary: need to check with Leo how we should proceed
        :return:
        """

        for index, output in enumerate(self.outputs.values()):
            output.lock(self.pdh_slope(detuning) * self.detuning_per_m, detuning, self.inputs['pdh'])


    def pdh_score(self, data):
        """
        This score should be maximised to improve the phase of the demodulation
        :return:
        """

        return (data.max() - data.min()) / (data.argmin() - data.argmax())

    @property
    def duration_zoom(self):
        if hasattr(self._config, 'duration_zoom'):
            return self._config.duration_zoom
        else:
            self._config["duration_zoom"] = 5*self.duration_sweep/self._config.finesse
            return self._config.duration_zoom

    @property
    def duration_ramp(self):
        return self._config.duration_ramp

    def acquire_pdh_phase(self, phi, parent=None):
        """
        Acquires one pdh phase
        :param phi: pdh phase to acquire.
        parent: parent curve to store calibration curve.
        :return: score, phase
        score: the pdh_score to maximize
        curve: the calibration curve
        """

        sig = self.inputs["pdh"]
        self.inputs["pdh"]._config.phase = phi
        self.setup()
        self.sweep() # it would be cleaner to have a periodic=False in asg to make
        # sure curve is only acquired when ramp is rising
        curve = Model.calibrate(self,
                                inputs=[sig],
                                scopeparams=dict(secondsignal='piezo',
                                                 duration=self.duration_zoom,
                                                 trigger_delay=self._config["trigger_delay_zoom"],
                                                 threshold=0.1,
                                                 average=True,
                                                 timeout=self.duration_ramp*4))[0]
        score = self.pdh_score(curve.data)
        curve.params["phi_pdh"] = phi
        curve.params["score"] = score
        if sig._config.autosave and parent is not None:
            curve.move(parent)
        return score, curve

    def search_pdh_phase(self, phi, val, phi_step, phi_accuracy, parent=None):
        """
        Looks for best score by n dichotomy steps between phi1 and phi2
        :param phi1:
        :param phi2:
        :param n:
        :return:
        """
        if phi_step<phi_accuracy:
            return phi
        for new_phi in (phi + phi_step, phi - phi_step):
            new_val, curve = self.acquire_pdh_phase(new_phi, parent)
            self.logger.info("phi_pdh: %i -> %i", new_phi, new_val)
            if new_val>val:
                return self.search_pdh_phase(new_phi, new_val, phi_step/2, phi_accuracy, parent)
        # best result was for phi
        return self.search_pdh_phase(phi, val, phi_step/2, phi_accuracy, parent)

    def calibrate(self):
        self._config["duration_ramp"] = self.sweep()/2
        curves = Model.calibrate(self,
                               inputs=[self.inputs['reflection']],
                               scopeparams=dict(duration=self.duration_ramp*2,
                                                trigger_delay=self.duration_ramp/2.))
        last_duration = curves[0].params["duration"]
        self.sweep()
        self._config["trigger_delay_zoom"] = curves[0].data[0:self.duration_ramp].argmin()

        timeout = last_duration * 6
        for sig in self.inputs.values():
            curves += Model.calibrate(self,
                            inputs=[sig],
                            scopeparams=dict(secondsignal='piezo',
                                             duration=self.duration_zoom,
                                             trigger_delay=self._config["trigger_delay_zoom"],
                                             timeout=timeout))
            if sig._name == 'pdh':
                parent = curves[-1]
                scores = []
                phis = (0., 120., 240.)
                for phi in phis:
                    score, curve = self.acquire_pdh_phase(phi, parent)
                    scores.append(score)
                    #look for optimal phase between phi_guess +- 45 deg
                tab = [(val, phi) for (val, phi) in zip(scores, phis)]
                (val, phi) = sorted(tab)[-1]
                #delta_phi = phi2 - phi1
                #delta_phi = (delta_phi + 180.) % (360.) - 180.
                #phi2 = phi1 + delta_phi
                sig._config.phase = self.search_pdh_phase(phi, val, phi_step=60., phi_accuracy=1., parent=parent)
                self._config.offset_pdh = sig._config.mean
                self._config.ampl_pdh = (sig._config.max - sig._config.min)/2
        return curves

    def setup(self):
        self._parent.rp.iq0.setup(frequency=self._config.mod_pdh,
                                  bandwidth=[self.inputs['pdh']._config.bandwidth, self.inputs['pdh']._config.bandwidth],
                                  gain=0,
                                  phase=self.inputs["pdh"]._config.phase,
                                  acbandwidth=500000,
                                  amplitude=self.inputs['pdh']._config.mod_amplitude_v,
                                  input=self.inputs['pdh']._config.redpitaya_mod_input,
                                  output_direct=self.inputs['pdh']._config.redpitaya_mod_output,
                                  output_signal='quadrature',
                                  quadrature_factor=self.inputs['pdh']._config.redpitaya_quadrature_factor)
        #o = self.outputs["slow"]
        #o.output_offset = o._config.lastoffset

    def sweep(self):
        duration = super(FPMembranes, self).sweep()
        self._parent.rp.scope.setup(trigger_source='asg1',
                                    duration=duration)
        return duration
