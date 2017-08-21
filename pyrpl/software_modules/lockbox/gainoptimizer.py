from qtpy import QtCore
from pyrpl.software_modules.lockbox import *
from pyrpl.async_utils import sleep


class GainOptimizerLoop(LockboxPlotLoop):
    amplitude = FloatProperty(default=0.1, doc='Amplitude of gain modulation for the estimation of the dependency '
                                               'of lock rms')

    unity_gain_frequency = FloatProperty(default = 0.01, doc="Unity gain frequency for the gain integrator.")

    current_gain_factor = FloatProperty(default=1.0, doc="Current gain factor of the gain correction mechanism.")

    measurement_time = FloatProperty(default=0.05, doc="Current gain factor of the gain correction mechanism.")


    #phase = PhaseProperty(default=0, doc="current phase of the gain modulation")
    @property
    def phase(self):
        return (self.n%2)*np.pi
    @phase.setter
    def phase(self, v):
        pass

    _phase_step = np.pi
    max_length = 10

    @property
    def rms(self):
        input = self.lockbox.inputs[self.lockbox.final_stage.input]
        input.stats(self.parent.measurement_time)
        return input.relative_rms

    @property
    def pdh(self):
        return self._lastrms[-1] * np.cos(self.phase-self._phase_step) + self.rms * np.cos(self.phase)

    def setup_loop(self):
        """ put your initialization routine here"""
        if not self.lockbox.is_locked_and_final(loglevel=0):
            self._clear()
        self._lastrms = [self.rms]
        self._lastpdh = [0]
        self._lasttime = [self.time]
        self.phase = 0
        self.current_gain_factor = self.lockbox.final_stage.gain_factor

    def loop(self, a):
        if not self.lockbox.is_locked_and_final(loglevel=0):
            setattr(self.parent, self.name, None)
            self._clear()
        # get the rms of the current error signal and store it
        rms, pdh, time = self.rms, self.pdh, self.time
        dt = time - self._lasttime[-1]
        self._lastrms.append(rms)
        self._lastpdh.append(pdh)
        self._lasttime.append(time)
        while len(self._lastrms) > self.max_length:
            self._lastrms.pop(0)
            self._lastpdh.pop(0)
            self._lasttime.pop(0)
        # compute integral
        self.current_gain_factor += pdh * self.parent.unity_gain_frequency * dt * 2.0 * np.pi
        self.phase = self.phase + self._phase_step
        self.lockbox.final_stage.gain_factor = self.current_gain_factor * (1.0 + self.parent.amplitude*np.cos(self.phase))
        self.plotappend(b=rms, g=pdh, r=self.current_gain_factor, y=self.lockbox.final_stage.gain_factor)

    def teardown_loop(self):
        """ put your destruction routine here"""
        self.lockbox.final_stage.gain_factor = self.current_gain_factor


class GainOptimizer(LockboxModule):
    """ a module that is used to optimize the lockbox gain by setting the gain_factor of the lockbox to the integral of
    an error signal derived from the slope of the error signal rms value vs gain_factor """
    _setup_attributes = ["interval", "amplitude", "unity_gain_frequency", "plot", "measurement_time"]
    _gui_attributes = _setup_attributes + ["start", "stop"]

    interval = FloatProperty(default=1.0, min=0)
    amplitude = FloatProperty(default=0.05, min=0)
    unity_gain_frequency = FloatProperty(default=0.1)
    plot = BoolProperty(default=True)
    measurement_time = FloatProperty(default=0.05, doc="Current gain factor of the gain correction mechanism.")

    def start(self):
        self.stop()
        if self.lockbox.is_locked_and_final(loglevel=0):
            self.loop = GainOptimizerLoop(parent=self,
                                          name="gainoptimizerloop",
                                          interval=self.interval,
                                          unity_gain_frequency=self.unity_gain_frequency,
                                          amplitude=self.amplitude,
                                          plot=self.plot
                                          )
        else:
            self._logger.error('The lockbox must be "locked" in order to start gain optimization.')

    def _start_when_locked(self):
        for i in range(100): # 100s timeout
            sleep(1.0)
            if self.lockbox.is_locked_and_final(loglevel=0):
                return self.start()

    def start_delayed(self):
        QtCore.QTimer.singleShot(100, self._start_when_locked)

    def stop(self):
        if hasattr(self, 'loop') and self.loop is not None:
            self.loop._clear()
            self.loop = None
