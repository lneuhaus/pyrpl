import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *


class LMSD(FabryPerot):
    """ LMSD only serves for error signal generation, not as a lockbox
    only functionality: iq demodulation, output the error signal to fpm,
    autotune the phase and frequency of lmsd
    """
    export_to_parent = ['unlock', 'sweep', 'islocked',
                        'save_current_gain', 'calibrate',
                        'lock']

    def setup_lmsd(self):
        self.setup_iq(input='lmsd')
        if 'lmsd_quadrature' not in self.inputs:
            self._config._root.inputs['lmsd_quadrature'] = {'redpitaya_input':
                                                         'iq2_2'}
            # execution of Pyrpl._makesignals is required here
            logger.error("LMSD Configuration was incomplete. Please restart "
                       "pyrpl now and the problem should disappear. ")
        self.unlock()
        self.outputs["piezo"].pid.input = self.inputs["lmsd"].redpitaya_input
        self.outputs["piezo"].pid.p = 1.0

    def lmsd(self, detuning, amplitude=20.0):
        """
        LMSD error signal

        Parameters
        ----------
        detuning: float
        amplitude: flaot. Drive amplitude in same units as detuning (i.e.
        cavity bandwidths).

        Returns
        -------
        float: error signal
        """
        #N = 101
        #dets = np.linspace(detuning-amplitude, detuning+amplitude, N,
        #                   endpoint=True)
        #lorentz = self.reflection(dets)
        #def _lmsd(x):
        #    return x
        #if detuning >= 1 or detuning <= -1:
        #    return 0
        #else:
        #    detuning *= np.pi / 2
        #    return np.sin(detuning)/np.cos(detuning)
        return detuning

    def lmsd_quadrature(self, detuning):
        return self.pdh(detuning, phase=np.pi/2)

    def calibrate(self, autoset=True):
        """ sweep is provided by other lockbox"""
        self.inputs['lmsd']._acquire(secondsignal='lmsd_quadrature')
        lmsd = self.inputs['lmsd'].curve
        lmsd_quadrature = self.inputs['lmsd_quadrature'].curve
        complex_lmsd = lmsd.data + 1j * lmsd_quadrature.data
        max = complex_lmsd.loc[complex_lmsd.abs().argmax()]
        phase = np.angle(max, deg=True)
        self.logger.info('Recommended phase correction for lmsd: %s degrees',
                         phase)
        qfactor = self.inputs['lmsd'].iq.quadrature_factor *0.8 / abs(max)
        self.logger.info('Recommended quadrature factor: %s',
                         qfactor)
        if autoset:
            self._config._root.inputs.lmsd.setup.phase -= phase
            self._config._root.inputs.lmsd.setup.quadrature_factor = qfactor
            self.setup_lmsd()
            self.logger.info('Autoset of iq parameters was executed.')
        return phase, qfactor

    @property
    def frequency(self):
        return self.inputs["lmsd"].iq.frequency

    @frequency.setter
    def frequency(self, v):
        self.inputs["lmsd"].iq.frequency = v
        self.inputs["lmsd"]._config.setup.frequency = v

