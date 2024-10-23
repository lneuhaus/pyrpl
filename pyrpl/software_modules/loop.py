"""
Defines a number of Loop modules to be used to perform periodically a task
"""
import numpy as np
import pyqtgraph as pg
from ..modules import Module
from ..async_utils import sleep_async, wait, ensure_future #MainThreadTimer
from ..pyrpl_utils import time
from qtpy import QtCore


class Loop(Module):
    timer = QtCore.QTimer()
    def __init__(self, parent, name='loop', interval=1.0,
                 autostart=True,
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
        #self.timer = MainThreadTimer(interval=0)
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
        try:
            try:
                self.loop()
            except TypeError:
                # allows to pass instance functions of the parent module as arguments as well
                try:
                    self.loop(self.parent, self)
                except TypeError:
                    self.loop(self.parent)
        except BaseException as e:
            # we do not want the loop to stop launching the next cycle (code
            # below this) if there is an exception raised by the loop function)
            self._logger.error("Error in main_loop of %s: %s", self.name, e)
        # increment counter
        self.n += 1
        if not self._ended:
            self.timer.start()

    def setup_loop(self):
        """ put your initialization routine here"""
        pass

    def pause_loop(self):
        self._ended = True

    def start_loop(self):
        self._ended = False
        self.main_loop()

    def loop(self):
        # insert your loop function here
        pass

    def teardown_loop(self):
        """ put your destruction routine here"""
        pass

    # useful helpers for precise timing, e.g. of the trigger module
    @property
    def fpga_time(self):
        """ current FPGA time in s since startup """
        return 8e-9 * self.pyrpl.rp.trig.current_timestamp / \
               self.pyrpl.rp.frequency_correction \
               - self.loop_start_time

    @property
    def trigger_time(self):
        """ FPGA time in s when trigger even occured (same frame of reference
        as self.time())"""
        return 8e-9 * self.pyrpl.rp.trig.trigger_timestamp / \
               self.pyrpl.rp.frequency_correction \
               - self.loop_start_time


class PlotWindow(object):
    """ makes a plot window where the x-axis is time since startup.

    append(color=value) adds new data to the plot for
    color in (red, green).

    close() closes the plot"""
    def __init__(self, title="plotwindow"):
        self.win = pg.GraphicsLayoutWidget(title=title)
        self.pw = self.win.addPlot()
        self.curves = {}
        self.win.show()
        self.plot_start_time = time()

    _defaultcolors = ['g', 'r', 'b', 'y', 'c', 'm', 'o', 'w']

    def append(self, *args, **kwargs):
        """
        usage:
            append(green=0.1, red=0.5, blue=0.21)
        # former, now almost deprecated version:
            append(0.5, 0.6)
        """
        for k in kwargs.keys():
            v = kwargs.pop(k)
            kwargs[k[0]] = v
        i=0
        for value in args:
            while self._defaultcolors[i] in kwargs:
                i += 1
            kwargs[self._defaultcolors[i]] = value
        t = time()-self.plot_start_time
        for color, value in kwargs.items():
            if value is not None:
                if not color in self.curves:
                    self.curves[color] = self.pw.plot(pen=color)
                curve = self.curves[color]
                x, y = curve.getData()
                if x is None or y is None:
                    x, y = np.array([t]), np.array([value])
                else:
                    x, y = np.append(x, t), np.append(y, value)
                curve.setData(x, y)

    def close(self):
        self.win.close()


class PlotLoop(Loop):
    def __init__(self, *args, **kwargs):
        try:
            self.plot = kwargs.pop("plot")
        except KeyError:
            self.plot = True
        try:
            self.plotter = kwargs.pop("plotter")
        except KeyError:
            self.plotter = None
        if self.plot and self.plotter is None:
            self.plot = PlotWindow(title=self.name)
        super(PlotLoop, self).__init__(*args, **kwargs)

    def plotappend(self, *args, **kwargs):
        if self.plot:
            if self.plotter is not None:
                setattr(self.parent, self.plotter, (args, kwargs))
            else:
                try:
                    self.plot.append(**kwargs)
                except BaseException as e:
                    self._logger.error("Error occured during plotting in Loop %s: %s",
                                       self.name, e)

    def _clear(self):
        super(PlotLoop, self)._clear()
        if hasattr(self, 'plot') and hasattr(self.plot, 'close'):
            self.plot.close()
