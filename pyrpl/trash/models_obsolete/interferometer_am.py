import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *

class Interferometer_Am(Interferometer):
    """ simplest type of optical interferometer with one photodiode """

    # the variable which we would like to control
    # we choose phase here and do everything concerning power around this
    # advantage is that phase is a reasonable variable which will always
    # lead to a lock
    _variable = "phase"

    export_to_parent = Interferometer.export_to_parent + \
                       ['calibrate_power', 'get_power', 'set_power',
                        'minimum_transmission', 'gains_off']

    # theoretical model for input signal 'transmission'
    def transmission(self, phase):
        """ photocurrent of an ideal interferometer vs phase (rad)"""
        amplitude = (self.inputs['transmission']._config.max
                     - self.inputs['transmission']._config.min) / 2
        mean = (self.inputs['transmission']._config.max
                     + self.inputs['transmission']._config.min) / 2
        return np.sin(phase) * amplitude + mean

    def setup_transmission(self):
        """ turn on the shutter by default """
        self.shutter = True

    # how phase converts to other units that are used in the configfile
    #@property
    #def phase_per_V(self):
    #    return np.pi/self._config.V_pi

    @property
    def phase_per_phase(self):
        return 1.0

    def lock(self, phase=0, factor=1):
        return self._lock(phase=phase,
                          input='transmission',
                          offset=0,
                          factor=factor)

    def calibrate(self):
        return super(Interferometer, self).calibrate(
            scopeparams={'secondsignal': 'eom'})

    @property
    def shutter(self):
        """True if shutter cuts the beam"""
        return not self._parent.rp.hk.expansion_P6

    @shutter.setter
    def shutter(self, v):
        """True if shutter cuts the beam"""
        self._parent.rp.hk.expansion_P6 = not v

    def get_offset(self):
        shutterstate = self.shutter
        self.shutter = True
        time.sleep(self._config.shutter.settle_time)
        v = super(Interferometer_Am, self).get_offset()
        self.shutter = shutterstate
        time.sleep(self._config.shutter.settle_time)
        return v

    def sweep(self):
        self.shutter = False
        return super(Interferometer_Am, self).sweep()

    def teardown_iq(self):
        self.inputs['iq'].iq.amplitude = 0

    @property
    def pinjected(self):
        return self.inputs['transmission'].mean

    @pinjected.setter
    def pinjected(self, p):
        # get the phase corresponding to p
        if p < 0:
            self.shutter = True
            self.unlock()
        elif p == 0:
            return self.minimum_transmission()
        else:
            if not self.islocked() or self.shutter:  # take care of the offset
                self.unlock(ival=True)
                time.sleep(self._config.unlock.time)
                self.minimum_transmission()
            self.unlock(ival=False)
            self.teardown_iq()
            phase = self.transmission_inverse(p, 0)
            if phase is None:
                c = self.inputs['transmission']._config
                if p > c.max:
                    self.logger.warning('Requested power %s exceeds maximum '
                                        'power %s. Setting power to '
                                        'available maximum. ', p, c.max)
                    self.maximum_transmission()
                elif p < c.min:
                    self.logger.warning('Requested power %s below minimum '
                                        'power %s. Setting power to '
                                        'available minimum. ', p, c.min)
                    self.minimum_transmission()
                else:
                    self.logger.error('Some error occured during setting the '
                                      'requested power %s. Turned off the '
                                      'power to prevent further errors.', p)
            else:
                # manually take care of the offset
                self.lock(phase=phase)
            # sleep a short while for lock to settle
            #time.sleep(self._config.minimum_transmission.time)

    def calibrate(self):
        """ nothing new here. Yet.. """
        res = super(Interferometer_Am, self).calibrate()
        c = self.inputs['transmission']._config
        return res

    def set_power(self, v=None):
        if v is not None:
            self.pinjected = v
            p = self.pinjected
            for i in range(3):
                if (v > 0.01 and abs(p - v) > 0.01) or \
                        (v <= 0.01 and abs(p-v) > 0.001) :
                    self.pinjected = v
                    p = self.pinjected
                else:
                    break
        return p

    def get_power(self):
        return self.pinjected

    def calibrate_power(self, mW):
        act = self.inputs['transmission'].mean
        correction = mW/act
        self.inputs['transmission']._config.mW_per_V *= correction
        return self.pinjected

    def minimum_transmission(self):
        self.setup_iq()
        self.shutter = False
        params = self._config.minimum_transmission._dict
        params['input'] = 'iq'
        try:
            t = params.pop('time')
        except KeyError:
            t = 0
        self.unlock()
        self._lock(**params)
        time.sleep(t)

    def gains_off(self):
        return super(Interferometer_Am, self).unlock(ival=False)
