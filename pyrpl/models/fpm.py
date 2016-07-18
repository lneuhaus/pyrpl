import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *

class FPM(FabryPerot):
    """ custom class for the measurement fabry perot of the ZPM experiment """

    export_to_parent = FabryPerot.export_to_parent \
                       + ["relative_pdh_rms", "relative_reflection",
                          "setup_ringdown", "teardown_ringdown", "lock_lmsd",
                          "setup_lmsd"]

    def setup(self):
        super(FPM, self).setup()
        # compatibility with other code
        self._parent.constants = self._parent.c.constants

    def setup_pdh(self, **kwargs):
        o = self.outputs["slow"]
        o.output_offset = o._config.lastoffset

        # instantiate the function generator for pdh - may take a few tries..
        from pyinstruments.pyhardwaredb import instrument
        from visa import VisaIOError
        signal = self.inputs["pdh"]
        pdh_instrument = signal._config.setup.generator
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
        self._enable_pdh()

    @property
    def pdh_enabled(self):
        self._generator.channel_idx = 1
        return self._generator.output_enabled

    def _enable_pdh(self, phase=None, frequency=None):
        signal = self.inputs["pdh"]
        if phase is None:
            phase = signal._config.setup.phase
        phase = phase % 360.0
        if frequency is None:
            frequency = signal._config.setup.frequency
        if not self.pdh_enabled or phase != self._generator.phase\
                or frequency != self._generator.frequency:
            self._generator.recall(1)
            self._generator.phaseinit()
            # realign the phase of the two generators just in case
            # (once problems were observed after a few weeks)
            for i in range(2):
                self._generator.channel_idx = i + 1
                self._generator.output_enabled = False
                self._generator.waveform = "SIN"
                self._generator.impedance = 50
                self._generator.offset = 0
                self._generator.frequency = frequency
                if i == 0:  # modulator output to EOM
                    self._generator.phase = 0
                    self._generator.amplitude = \
                        signal._config.setup.amplitude
                else:  # demodulator output
                    self._generator.phase = phase
                    self._generator.amplitude = 1.4
                self._generator.output_enabled = True
                self._generator.phaseinit()
        #return super(RPLockbox_FPM, self)._setup_pdh()

    def _disable_pdh(self, sbfreq=None):
        signal = self.inputs["pdh"]
        for i in range(2):
            self._generator.channel_idx = i + 1
            self._generator.output_enabled = False
        if not sbfreq is None:
            self._generator.channel_idx = 1
            self._generator.waveform = "SIN"
            self._generator.impedance = 50
            self._generator.offset = 0
            self._generator.frequency = sbfreq
            self._generator.phase = 0
            self._generator.amplitude = \
                signal._config.setup.amplitude_for_finesse
            self._generator.output_enabled = True
        #return super(RPLockbox_FPM, self)._disable_pdh()

    @property
    def coarse(self):
        return self._parent.slow.output_offset

    @coarse.setter
    def coarse(self, v):
        self._parent.slow.output_offset = v

    def setup_ringdown(self,
                       frequency=3.578312e6,
                       amplitude=0.1,
                       duration=1.0):
        output = self._config._root.outputs.fastpiezo.redpitaya_output
        self._parent.rp.asg1.setup(
            frequency=frequency,
            amplitude=amplitude,
            cycles_per_burst=int(np.round(frequency*duration)),
            output_direct=output,
            trigger_source="ext_positive_edge")

    def teardown_ringdown(self):
        self._parent.rp.asg1.disable_advanced_trigger()

    def center_on_resonance(self, start=-1, coarse='slow'):
        self.unlock()
        self.sweep()
        coarsepid = self.outputs[coarse].pid
        coarse.ival = -1
        coarsebw = sorted(self.outputs[
                               coarse]._config.analogfilter.lowpass)

    def setup_lmsd(self):
        self._disable_pdh()
        if not hasattr(self, 'l'):
            from pyrpl import Pyrpl
            self.l = Pyrpl('lmsd')
        self.unlock()

    @property
    def lmsd_frequency(self):
        return self.l.lmsd.iq.frequency

    @lmsd_frequency.setter
    def lmsd_frequency(self, v):
        self.l.lmsd.iq.frequency = v
        self.l.lmsd._config.setup.frequency = v

    def lock_lmsd(self, gain=0.01, sleeptime=1.0):
        from time import sleep
        self.unlock()
        self.l.unlock()
        self.l.piezo.pid.input="iq2"
        self.l.piezo.pid.setpoint = 0
        self.l.piezo.pid.i = 0
        self.l.piezo.pid.ival = 0
        self.l.piezo.pid.p = 1.0
        self.piezo = self.outputs["piezo"]
        self.piezo.pid.input = 'adc1'
        self.piezo.pid.setpoint = 0.6
        self.piezo.pid.ival = 3.0
        sleep(0.03)
        self.piezo.pid.i = gain
        sleep(sleeptime)
        self.piezo.pid.setpoint = 0.42

    def _lmsd(detuning, phi=0, xmax=10):
        """ lmsd error signal"""
        N = 300
        t = np.linspace(0, 2*np.pi, N, endpoint=False)
        x = np.sin(t)*xmax
        R = self._lorentz(x-detuning)
        prod = R*np.sin(t+phi/180.0*np.pi)
        errsig = np.mean(prod)
        return errsig

    def _lmsd_normalized(detuning, phi=0, xmax=10):
        if xmax>1.5:
            return _lmsd(detuning, phi=phi, xmax=xmax) / _lmsd(xmax-0.5, phi=0, xmax=xmax)
        elif xmax>0.5:
            return _lmsd(detuning, phi=phi, xmax=xmax) / _lmsd(xmax, phi=0, xmax=xmax)
        else:
            return _lmsd(detuning, phi=phi, xmax=xmax) / _lmsd(0.5, phi=0, xmax=xmax)

    def lmsd(self, detuning):
        return self._lmsd_normalized(detuning,
                                     phi=self._config.lmsd.phi,
                                     xmax=self._config.lmsd.xmax) \
               * self._config.lmsd.peak

