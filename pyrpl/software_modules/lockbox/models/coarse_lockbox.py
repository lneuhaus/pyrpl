from pyhardware import instrument

from pyrpl.software_modules.lockbox import *
from pyrpl.software_modules.lockbox.signals import *
from pyrpl.software_modules.lockbox.loop import *
from pyrpl.software_modules.lockbox.models.fabryperot import *



class CoarseProperty(FloatAttribute):
    def __init__(self, **kwds):
        self._initialized = False
        super(CoarseProperty, self).__init__(**kwds)

    def get_value(self, obj, obj_type):
        if obj is None:
            return self
        return obj.fgen.offset

    def set_value(self, obj, val):
        if val > self.max:
            obj._logger.warning("Coarse cannot go above max. value of %s!",
                                self.max)
        if val < self.min:
            obj._logger.warning("Coarse cannot go above min. value of %s!",
                                self.min)
        if obj.fgen.waveform != "DC":
            obj.fgen.waveform = "DC"
        if self._initialized:
            obj.fgen.offset = val
        else:
            obj.fgen.set = val
            self._initialized = True


class CoarseSearchStep(LockboxPlotLoop): # or inherit from
    def _init_module(self):
        self.c.n = 0
        self.scope = self.pyrpl.rp.scope
        self.scopes = self.pyrpl.scopes
        self.coarsemax = self.lockbox.__class__.coarse.max
        self.coarsemin = self.lockbox.__class__.coarse.min
        self.scope_setup()
        self.counter = 0
        self.pwm0 = []
        self.pwm1 = []
        self.tpos = []
        self.tneg = []

    def scope_setup(self):
        self.scope.setup(duration=5e-4,
                         input1=self.lockbox.inputs.reflection.signal(),
                         input2="off",
                         trigger_source="ch1_positive_edge",
                         trigger_delay=0,
                         threshold_ch1=self.threshold,
                         rolling_mode=False,
                         running_state="running_single")

    @property
    def threshold(self):
        with self.scopes.pop('test') as s:
            s.setup(duration=5e-4,
                         trigger_source="immediately",
                         input1=self.lockbox.inputs.reflection.signal())
            data, _ = s.curve()
            s.free()

        val = data.mean()*0.5
        return val

    @property
    def coarse_close_to_min(self):
        dmin = self.lockbox.coarse - self.coarsemin
        dmax = self.coarsemax - self.lockbox.coarse
        if dmin < dmax:
            return True
        return False

    def switch_coarse(self):
        if self.coarse_close_to_min:
            self.lockbox.coarse = self.coarsemax
        else:
            self.lockbox.coarse = self.coarsemin

    def loop(self):
        self.c.n += 1
        if self.c.n == 1:
            #First iteration
            #Setup everything
            self._init_module()
            self.lockbox.unlock()
            self.scope_setup()
            #Choose starting point
            self.switch_coarse()
            self.c.n += 1
        elif self.scope._curve_acquiring():
            #No trigger
            pass
        elif self.counter < 7:
            #Triggered, pass the resonance
            self.counter += 1
        elif max(len(self.tpos), len(self.tneg)) < 2:
            #Trigger passed, changing coarse values
            self.scope_setup()
            self.counter = 0
            if self.coarse_close_to_min:
                self.lockbox.coarse = self.coarsemax
                self.tpos.append(time())
            else:
                self.lockbox.coarse = self.coarsemin
                self.tneg.append(time())
        else:
            #Time to evaluate coarse and update coarse min max
            self.scope_setup()
            self.counter = 0
            tpos = np.array(self.tpos)
            tneg = np.array(self.tneg)
            self.tpos = []
            self.tneg = []
            if len(tpos) < len(tneg):
                pwm_period = (tneg[1:]-tneg[:-1]).mean()
                pwm_value = (tneg[1:]-tpos).mean()/pwm_period
            else:
                pwm_period = (tpos[1:]-tpos[:-1]).mean()
                pwm_value = (tneg-tpos[:-1]).mean()/pwm_period
            val = pwm_value*self.coarsemax+(1-pwm_value)*self.coarsemin
            print val
            old_amp = (self.coarsemax - self.coarsemin) / 2.
            amplitude = min(self.coarsemax - val, val - self.coarsemin)
            if amplitude / old_amp > 0.6:
                amplitude *= 0.6
            if amplitude > 0.01:
                #Continue search with decreased amplitude
                self.coarsemin = val - amplitude
                self.coarsemax = val + amplitude
                self.switch_coarse()
            else:
                #Stop search and go to more realistic value of coarse
                self._init_module()
                self.lockbox.coarse = val
                self.lockbox.sweep()
                self.scope.setup(duration=0.2,
                                 input1=self.lockbox.inputs.reflection.signal(),
                                 input2="out2",
                                 trigger_source="asg1",
                                 trigger_delay=0,
                                 threshold_ch1=self.threshold,
                                 rolling_mode=False,
                                 running_state="running_continuous")
                self._clear()
                return

        self.plot.append(green=self.trigger_time(),
                         red=self.lockbox.coarse)


    def oldloop(self):
        # attention: self.time() is FPGA time, time() is plot-relevant time
        self.c.n += 1
        if self.c.n == 0:
            if self.scope._curve_acquiring():
                self.c.n = -1
            else:
                self.counter = 0
        elif self.c.n == 1:
            self.scope_setup()
            self.lockbox.coarse = self.coarsemax
        elif self.scope._curve_acquiring() and self.counter==0:
            pass
        elif self.counter < 5:
            self.counter += 1
        else:
            self.counter = 0
            self.scope_setup()
            if len(self.pwm0)==len(self.pwm1) and len(self.pwm0) > 1:
                self.pwm1[-1] -= time()
                self.pwm0 = np.array(self.pwm0)
                self.pwm1 = np.array(self.pwm1)
                val = (
                (self.pwm0 * self.coarsemin + self.pwm1 * self.coarsemax) /
                (self.pwm0 + self.pwm1)).mean()
                old_amp = (self.coarsemax-self.coarsemin)/2.
                amplitude = min(self.coarsemax-val, val-self.coarsemin)
                if amplitude > 0.1:
                    if amplitude / old_amp > 0.9:
                        amplitude *= 0.9
                    self.coarsemin = val - amplitude
                    self.coarsemax = val + amplitude
                    self.pwm0, self.pwm1 = [], []
                    self.lockbox.coarse = self.coarsemin
                    self.c.n =-1
                else:
                    self._clear()
                    self.lockbox.coarse = val
                    self.lockbox.sweep()
                    self.scope.setup(duration=0.1,
                                     input1=self.lockbox.inputs.reflection.signal(),
                                     input2="out2",
                                     trigger_source="asg1",
                                     trigger_delay=0,
                                     threshold_ch1=self.threshold,
                                     rolling_mode=False,
                                     running_state="running_continuous")
                    self._init_module()
            else:
                if self.lockbox.coarse < self.coarsemin + 1e-6:
                    self.lockbox.coarse = self.coarsemax
                    self.pwm1.append(time())
                    if len(self.pwm0) > 0:
                        self.pwm0[-1] -= time()
                else:
                    if len(self.pwm1) > 0:
                        self.pwm1[-1] -= time()
                    self.lockbox.coarse = self.coarsemin
                    self.pwm0.append(time())

        tact = time() - self.plot.plot_start_time

        self.plot.append(green=self.trigger_time(),
                         red=self.lockbox.coarse)


class CoarseSearchStepLockbox(FabryPerot):
    coarse = CoarseProperty(default=0,
                            # max voltage at piezo: 100 V
                            # max voltage before divider:
                            # 100V / (120 kOhm / 200 kOhm)
                            # max voltage at tegam input:
                            # 100V / (120 kOhm / 200 kOhm) / 50.0
                            max=100.0 / (120e3 / 200e3) / 50.0,
                            min=-0.0 / (120e3 / 200e3) / 50.0,
                            # max=120.0/(120e3/200e3)/50.0,
                            # min=-20.0 / (120e3 / 200e3) / 50.0,
                            increment=0.001)

    def _init_module(self):
        self.fgen = instrument('FgenCoarse')

    loop = None
    _gui_attributes = ["start", "stop", "interval", "coarse"]

    interval = FloatProperty(default=0.01, min=0)

    def start(self):
        self.stop()
        self.loop = CoarseSearchStep(parent=self,
                                     name="example_loop",
                                     interval=self.interval)

    def stop(self):
        if self.loop is not None:
            self.loop._clear()
            self.loop = None
