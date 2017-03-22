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
    def setup_loop(self):
        self.scope = self.pyrpl.rp.scope
        self.scopes = self.pyrpl.scopes
        self.coarsemax = self.lockbox.__class__.coarse.max
        self.coarsemin = self.lockbox.__class__.coarse.min
        self.counter = 0
        self.tpos = []
        self.tneg = []
        self.lockbox.unlock()
        self.scope_setup()
        # switch coarse
        self.digital_coarse = not self.digital_coarse
        #self.switch_coarse()

    def scope_setup(self):
        self.scope.setup(duration=5e-4,
                         input1=self.lockbox.inputs.reflection.signal(),
                         input2="off",
                         trigger_source="ch1_positive_edge",
                         trigger_delay=0,
                         threshold_ch1=self.threshold,
                         rolling_mode=False,
                         running_state="running_single")
        #self.scope.curve_async()

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

    @property
    def digital_coarse(self):
        dmin = self.lockbox.coarse - self.coarsemin
        dmax = self.coarsemax - self.lockbox.coarse
        if dmin < dmax:
            return True
        return False

    @digital_coarse.setter
    def digital_coarse(self, value):
        if value:
            self.lockbox.coarse = self.coarsemin
        else:
            self.lockbox.coarse = self.coarsemax


    def loop(self):
        if self.scope._curve_acquiring():
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
                self.tpos.append(self.time)
            else:
                self.lockbox.coarse = self.coarsemin
                self.tneg.append(self.time)
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
                self.digital_coarse = not self.digital_coarse
                #self.switch_coarse()
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
        self.plot.append(red=self.lockbox.coarse,
                         green=self.trigger_time)


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
