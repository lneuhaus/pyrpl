import numpy as np
import pyqtgraph as pg
from ...modules import Module
from . import LockboxModule
from ...async_utils import sleep, PyrplFuture, MainThreadTimer
from ...pyrpl_utils import time

class Loop(Module):
    def __init__(self, parent, name='loop', interval=0.01,
                 loop_function=None, init_function=None, clear_function=None):
        # parent is parent pyrpl module
        # name is important for the right config file section name
        # optionally, init_function, loop_function, and clear_function can be passed
        # as arguments
        if init_function is not None:
            self._init_module = init_function
        if loop_function is not None:
            self.loop = loop_function
        if clear_function is not None:
            self._clear_module = clear_function
        super(Loop, self).__init__(parent, name=name)
        self._ended = False  # becomes True when loop is ended
        self.timer = MainThreadTimer(interval=0)
        # interval in seconds
        self.interval = interval
        self.timer.timeout.connect(self.main_loop)
        self.timer.start()
        self.loop_start_time = time()

    @property
    def interval(self):
        return float(self.timer.interval())/1000.0

    @interval.setter
    def interval(self, val):
        self.timer.setInterval(val*1000.0)

    def _clear(self):
        self._signal_launcher.clear()
        self._ended = True
        self.timer.stop()
        self._clear_module()
        super(Loop, self)._clear()

    def main_loop(self):
        # this function is called by
        self.loop()
        if not self._ended:
            self.timer.start()

    def _init_module(self):
        """ put your initialization routine here"""
        pass

    def _clear_module(self):
        """ put your destruction routine here"""
        pass

    def loop(self):
        # insert your loop function here
        pass


class LockboxLoop(Loop, LockboxModule):
    # inheriting from LockboxModule essentially creates a lockbox property
    # that refers to the lockbox
    def fpga_time(self):
        """ current FPGA time in s """
        return float(self.pyrpl.rp.scope.current_timestamp) * 8e-9 / self.pyrpl.rp.frequency_correction

    def trigger_time(self):
        """ FPGA time in s when trigger even occured """
        return 8e-9 * float(self.pyrpl.rp.scope.trigger_timestamp) * 8e-9 / self.pyrpl.rp.frequency_correction


class PlotWindow(object):
    """ makes a plot window where the x-axis is time since startup.

    append(color=value) adds new data to the plot for
    color in (red, green).

    close() closes the plot"""
    def __init__(self, title="plotwindow"):
        self.win = pg.GraphicsWindow(title=title)
        #self.win.setWindowTitle(title)
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


class LockboxPlotLoop(LockboxLoop):
    def __init__(self, *args, **kwargs):
        self.plot = PlotWindow()
        super(LockboxPlotLoop, self).__init__(*args, **kwargs)

    def append(self, red=None, green=None):
        self.plot.append(red=red, green=green)

    def _clear(self):
        self.plot.close()
        super(LockboxPlotLoop, self)._clear()
