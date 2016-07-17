import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *


class LMSD(FabryPerot):
    export_to_parent = ['unlock', 'sweep', 'islocked',
                        'save_current_gain', 'calibrate',
                        'lock']

    def setup_lmsd(self):
        curves = self.setup_iq(input='lmsd')
        if 'lmsd_quadrature' in self.inputs:
            return curves
        else:
            self._config._root.inputs['lmsd_quadrature'] = {'redpitaya_input':
                                                         'iq2_2'}
            # execution of Pyrpl._makesignals is required here
            logger.error("LMSD Configuration was incomplete. Please restart "
                       "pyrpl now and the problem should disappear. ")
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

    def calibrate(self):
        curves = super(FabryPerot, self).calibrate(inputs=['reflection'],
                                                   scopeparams={
                                                       'secondsignal':
                                                           'piezo'})
        curves += super(FabryPerot, self).calibrate(inputs=['lmsd'],
                                scopeparams={'secondsignal':'lmsd_quadrature'})
        return curves
        #lmsd = curves[-1]
        #lmsd_quadrature = list(lmsd.childs)[0]
        #complex = lmsd

