from .loop import PlotLoop
from ..attributes import *
from ..modules import Module
from numpy import isnan

class SoftwarePidLoop(PlotLoop):
    @property
    def input(self):
        return recursive_getattr(self.parent, self.parent.input)

    @property
    def output(self):
        return recursive_getattr(self.parent, self.parent.output)

    @output.setter
    def output(self, value):
        return recursive_setattr(self.parent, self.parent.output, value)

    def setup_loop(self):
        """ put your initialization routine here"""
        self.ival = 0
        self.lasttime = self.time
        self.lasterror = 0

    def loop(self):
        input = self.input
        if input is None or isnan(input):
            self._logger.error("Could not retrieve the input signal for %s.%s.", self.parent, self.name)
            return
        error = input - self.parent.setpoint
        dt, self.lasttime = self.time - self.lasttime, self.time
        self.ival += self.parent.i * dt * 2.0 * np.pi * error
        out = self.ival + self.parent.p * error + self.parent.d * 2.0 * np.pi / dt * (error-self.lasterror)
        self.output = out
        self.plotappend(b=error, r=self.output)
        self.lasterror = error

    def teardown_loop(self):
        """ put your destruction routine here"""
        self.parent.__class__.running.value_updated(self.parent, False)


class RunningProperty(LedProperty):
    def get_value(self, obj):
        val = hasattr(obj, 'loop') and obj.loop is not None
        if val != super(RunningProperty, self).get_value(obj):
            setattr(obj, self.name, val)
        return val

    def start(self, obj):
        """
        starts a new loop
        """
        self.stop(obj)
        obj.loop = SoftwarePidLoop(parent=obj,
                                   name="loop",
                                   interval=obj.interval,
                                   plot=obj.plot)

    def stop(self, obj):
        """
        stops the running loop
        """
        if hasattr(obj, 'loop') and obj.loop is not None:
            obj.loop._clear()
            obj.loop = None

    true_function = start
    false_function = stop


class SoftwarePidController(Module):
    p = FloatProperty(default=-1.0)
    i = FloatProperty(default=0)
    d = FloatProperty(default=0)
    setpoint = FloatProperty(default=0)
    input = StringProperty(default='pyrpl.rp.sampler.in1')
    output = StringProperty(default='pyrpl.rp.asg0.offset')
    interval = FloatProperty(default=1.0, min=0)
    plot = BoolProperty(default=True)
    running = RunningProperty(default=False)
    _setup_attributes = ['p', 'i', 'd', 'setpoint', 'interval', "plot", "running"]
    _gui_attributes = _setup_attributes

    def start(self):
        if not self.running:
            self.running = True

    def stop(self):
        self.running = False
