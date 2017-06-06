from .loop import PlotLoop
from ..attributes import *
from ..modules import Module
import numpy as np

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
        if self.parent.reset_ival_on_restart:
            self.parent._ival = 0
        self.lasttime = self.time
        self.lasterror = 0

    def loop(self):
        input = self.input
        if input is None or np.isnan(input):
            self._logger.error("Could not retrieve the input signal for %s.%s.", self.parent, self.name)
            return
        error = input - self.parent.setpoint
        dt, self.lasttime = self.time - self.lasttime, self.time
        self.parent._ival += self.parent.i * dt * 2.0 * np.pi * error
        self.parent._ival = self.saturate_output(self.parent._ival)
        out = self.parent._ival + self.parent.p * error + self.parent.d * 2.0 * np.pi / dt * (error-self.lasterror)
        out = self.saturate_output(out)
        self.output = out
        if self.parent.plot:
            self.plotappend(r=error, g=self.output)
        self.lasterror = error
        self.interval = self.parent.interval
        self.parent._loop_hook()

    def saturate_output(self, v):
        if v > self.parent.output_max:
            v = self.parent.output_max
        elif v < self.parent.output_min:
            v = self.parent.output_min
        return v

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
                                   plot=True, #obj.plot, # obj.plot is handled in loop() above
                                   plotter="plotter")

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
    _ival = FloatProperty(default=0)
    reset_ival_on_restart = BoolProperty(default=True)
    setpoint = FloatProperty(default=0)
    input = StringProperty(default='pyrpl.rp.sampler.in1')
    output = StringProperty(default='pyrpl.rp.asg0.offset')
    output_max = FloatProperty(default=np.inf)
    output_min = FloatProperty(default=-np.inf)

    interval = FloatProperty(default=1.0, min=0)
    plot = BoolProperty(default=True)
    plotter = Plotter(legend='error (red, V) and output (green, V)')  # plotting window
    running = RunningProperty(default=False)
    _setup_attributes = ['input', 'output', 'p', 'i', 'd', 'setpoint', 'reset_ival_on_restart',
                         'interval', 'plot', 'running']
    _gui_attributes = _setup_attributes + ["plotter"]

    def start(self):
        if not self.running:
            self.running = True

    def stop(self):
        self.running = False

    def _loop_hook(self):
        """
        this function is called at the end of each loop.

        May be used for additional plotting, for example
        """
        pass
