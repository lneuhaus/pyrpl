"""
Defines a number of Loop modules to be used to perform periodically a task
"""

import numpy as np
import pyqtgraph as pg
from ..modules import Module
from .lockbox import LockboxModule
from ..async_utils import sleep, PyrplFuture, MainThreadTimer
from ..pyrpl_utils import time


class Loop(Module):
    def __init__(self, parent, name='loop', interval=0.01, autostart=True,
                 loop_function=None, setup_function=None,
                 teardown_function=None, **kwargs):
        # parent is parent pyrpl module
        # name is important for the right config file section name
        # optionally, init_function, loop_function, and clear_function can be passed
        # as arguments
        super(Loop, self).__init__(parent, name=name)
        self.kwargs = kwargs  # allows using kwargs in setup_loop
        if setup_function is not None:
            self.setup_loop = setup_function
        if loop_function is not None:
            self.loop = loop_function
        if teardown_function is not None:
            self.teardown_loop = teardown_function
        self._ended = False  # becomes True when loop is ended
        self.timer = MainThreadTimer(interval=0)
        # interval in seconds
        self.interval = interval
        self.timer.timeout.connect(self.main_loop)
        self.n = 0  # counter for the number of loops
        self.time  # initialize start time in internal time format
        # call custom initialization (excluded above)
        try:
            self.setup_loop()
        except TypeError:
            # allows to pass instance functions of the parent module as arguments as well
            self.setup_loop(self.parent, self)
        if autostart:
            self.main_loop()

    @property
    def time(self):
        """ time since start of the loop """
        try:
            return time() - self.loop_start_time
        except AttributeError:
            self.loop_start_time = time()
            return 0

    @property
    def interval(self):
        return float(self.timer.interval())/1000.0

    @interval.setter
    def interval(self, val):
        self.timer.setInterval(val*1000.0)

    def _clear(self):
        self._ended = True
        self.timer.stop()
        try:
            self.teardown_loop()
        except TypeError:
            # allows to pass instance functions of the parent module as arguments as well
            self.teardown_loop(self.parent, self)
        super(Loop, self)._clear()

    def main_loop(self):
        self.n += 1
        try:
            self.loop()
        except TypeError:
            # allows to pass instance functions of the parent module as arguments as well
            self.loop(self.parent, self)
        if not self._ended:
            self.timer.start()

    def setup_loop(self):
        """ put your initialization routine here"""
        pass

    def loop(self):
        # insert your loop function here
        pass

    def teardown_loop(self):
        """ put your destruction routine here"""
        pass


class LockboxLoop(Loop, LockboxModule):
    # inheriting from LockboxModule essentially creates a lockbox property
    # that refers to the lockbox
    @property
    def fpga_time(self):
        """ current FPGA time in s since startup """
        return 8e-9 * self.pyrpl.rp.scope.current_timestamp / \
                       self.pyrpl.rp.frequency_correction \
                       - self.loop_start_time

    @property
    def trigger_time(self):
        """ FPGA time in s when trigger even occured (same frame of reference as self.time())"""
        return 8e-9 * self.pyrpl.rp.scope.trigger_timestamp / self.pyrpl.rp.frequency_correction \
               - self.loop_start_time


class PlotWindow(object):
    """ makes a plot window where the x-axis is time since startup.

    append(color=value) adds new data to the plot for
    color in (red, green).

    close() closes the plot"""
    def __init__(self, title="plotwindow"):
        self.win = pg.GraphicsWindow(title=title)
        self.pw = self.win.addPlot()
        self.curve_green = self.pw.plot(pen="g")
        self.curve_red = self.pw.plot(pen="r")
        self.win.show()
        self.plot_start_time = time()

    def append(self, green=None, red=None):
        t = time()-self.plot_start_time
        for curve, value in [(self.curve_green, green),
                             (self.curve_red, red)]:
            if value is not None:
                x, y = curve.getData()
                if x is None or y is None:
                    x, y = np.array([t]), np.array([value])
                else:
                    x, y = np.append(x, t), np.append(y, value)
                curve.setData(x, y)

    def close(self):
        self.win.close()


class PlotLoop(LockboxLoop):
    def __init__(self, *args, **kwargs):
        try:
            plot = kwargs.pop("plot")
        except KeyError:
            plot = True
        if plot:
            self.plot = PlotWindow()
            #self.win.setWindowTitle(self.name)
        super(PlotLoop, self).__init__(*args, **kwargs)


    def plotappend(self, red=None, green=None):
        self.plot.append(red=red, green=green)

    def _clear(self):
        self.plot.close()
        super(PlotLoop, self)._clear()


class LockboxPlotLoop(PlotLoop, LockboxLoop):
    pass
