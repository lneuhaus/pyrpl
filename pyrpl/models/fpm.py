import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *

class FPM(FabryPerot):
    def setup(self):
        o = self.outputs["slow"]
        o.output_offset = o._config.lastoffset

        # instantiate the function generator for pdh - may take a few tries..
        from pyinstruments.pyhardwaredb import instrument
        from visa import VisaIOError
        pdh_instrument = self._config._root.general.pdh_generator
        for i in range(5):
            try:
                self._generator = instrument(pdh_instrument)
            except VisaIOError:
                self.logger.warning("VI_ERROR_IO occured with " \
                      + pdh_instrument + \
                      " again in attempt %d. Trying again...", i)
            else:
                break
        from pyinstruments.datalogger.models import SensingDevice
        self._coarse_voltage_log = SensingDevice(
            name="fpm_2p_coarse[V]")  # logbook for coarse voltage to estimate drift rates for example
        self._pdh_rms_log = SensingDevice(
            name="pdh_rms_rel")  # logbook for pdh rms



    def sweep(self):
        duration = super(FPM, self).sweep()
        self._parent.   rp.scope.setup(trigger_source='asg1',
                                    duration=duration)


    @property
    def pdhon(self):
        self._pdh.channel_idx = 1
        return self._pdh.output_enabled

    def _setup_pdh(self, phase=None, frequency=None):
        if not self.pdhon:
            if frequency is None:
                frequency = self.constants["pdh_frequency"]
            if phase is None:
                phase = self.constants["pdh_phase"]
            phase = phase % 360.0
            # self.constants = { "pdh_phase": phase,
            #                   "pdh_frequency": frequency}
            # set fgen clock to external
            self._pdh.recall(1)
            self._pdh.phaseinit()  # realign the phase of the two generators just in case (once problems were observed after a few weeks)
            for i in range(2):
                self._pdh.channel_idx = i + 1
                self._pdh.output_enabled = False
                self._pdh.waveform = "SIN"
                self._pdh.impedance = 50
                self._pdh.offset = 0
                self._pdh.frequency = frequency
                if i == 0:  # modulator output to EOM
                    self._pdh.phase = 0
                    self._pdh.amplitude = 4.0
                else:  # demodulator output
                    self._pdh.phase = phase
                    self._pdh.amplitude = 1.4
                self._pdh.output_enabled = True
                self._pdh.phaseinit()
        #return super(RPLockbox_FPM, self)._setup_pdh()


    def _disable_pdh(self, sbfreq=None):
        for i in range(2):
            self._pdh.channel_idx = i + 1
            self._pdh.output_enabled = False
        if not sbfreq is None:
            self._pdh.channel_idx = 1
            self._pdh.waveform = "SIN"
            self._pdh.impedance = 50
            self._pdh.offset = 0
            self._pdh.frequency = sbfreq
            self._pdh.phase = 0
            self._pdh.amplitude = 3.5
            self._pdh.output_enabled = True
        #return super(RPLockbox_FPM, self)._disable_pdh()
