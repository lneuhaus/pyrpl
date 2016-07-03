import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *
import threading


class FPM(FabryPerot):
    export_to_parent = FabryPerot.export_to_parent \
                       + ["relative_pdh_rms", "relative_reflection"]
    def setup(self):
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

    def sweep(self):
        duration = super(FPM, self).sweep()
        self._parent.rp.scope.setup(trigger_source='asg1',
                                    duration=duration)
        if "scopegui" in self._parent.c._dict:
            if self._parent.c.scopegui.auto_run_continuous:
               self._parent.rp.scope_widget.run_continuous()

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

    def relative_pdh_rms(self):
        rms = self.signals["pdh"].rms
        relrms = rms / self._config.peak_pdh
        self._pdh_rms_log.log(relrms)
        return relrms

    def lock(self,
             detuning=None,
             factor=None,
             firststage= None,
             laststage=None,
             thread=True):
        # firststage will allow timer-based recursive iteration over stages
        # i.e. calling lock(firststage = nexstage) from within this code
        stages = self._config.lock.stages._keys()
        if firststage:
            if not firststage in stages:
                self.logger.error("Firststage %s not found in stages: %s",
                                  firstage, stages)
            else:
                stages = stages[stages.index(firststage):]
        for stage in stages:
            self.logger.debug("Lock stage: %s", stage)
            parameters = dict(detuning=detuning, factor=factor)
            parameters.update((self._config.lock.stages[stage]))
            try:
                stime = parameters.pop("time")
            except KeyError:
                stime = 0
            if stage == laststage or stage == stages[-1]:
                if detuning:
                    parameters['detuning'] = detuning
                if factor:
                    parameters['factor'] = factor
                return self._lock(**parameters)
            else:
                if thread:
                    nextstage = stages[stages.index(stage)+1]
                    t = threading.Timer(stime,
                                    self.lock,
                                    kwargs = dict(
                                        detuning=detuning,
                                        factor=factor,
                                        firststage=nextstage,
                                        laststage=laststage,
                                        thread=thread))
                    return t.start()
                else:
                    self._lock(**parameters)
                    time.sleep(stime)

    def relative_reflection(self):
        return self.inputs["reflection"].mean / self.reflection(1000)

    def islocked(self):
        mean = self.inputs["reflection"].mean
        set = abs(self.state["set"][self._variable])
        return (mean <= self.reflection(set+1.0))
