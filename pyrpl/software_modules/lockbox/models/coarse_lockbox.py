from pyhardware import instrument

from pyrpl.software_modules.lockbox import *
from pyrpl.software_modules.lockbox.signals import *
from pyrpl.software_modules.lockbox.loop import *


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
        self.coarsemax = self.lockbox.__class__.coarse.max
        self.coarsemin = self.lockbox.__class__.coarse.min

    def loop(self):
        # attention: self.time() is FPGA time, time() is plot-relevant time
        self.c.n += 1

        if self.c.n % 20. == 0:
            if self.lockbox.coarse < 0.1:
                self.lockbox.coarse = self.coarsemax
            else:
                self.lockbox.coarse = self.coarsemin
        tact = time() - self.plot.plot_start_time

        self.plot.append(green=self.trigger_time(),
                         red=self.lockbox.coarse)


class CoarseSearchStepLockbox(Lockbox):
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
    _gui_attributes = ["start", "stop", "interval"]

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
