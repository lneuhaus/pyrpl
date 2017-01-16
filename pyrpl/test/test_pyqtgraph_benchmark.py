import pyqtgraph as pg
import numpy as np
import unittest
import time
from PyQt4 import QtCore
from PyQt4 import QtGui
import logging
from pyrpl import RedPitaya
logger = logging.getLogger(name=__name__)

APP = QtGui.QApplication.instance()


class PyqtgraphTestCases(unittest.TestCase):
    N = 2 ** 14
    cycles = 100
    frequency = 10
    duration = 1.0
    dt = 0.01
    REDPITAYA = True

    def setUp(self):
        self.t0 = np.linspace(0, self.duration, self.N)
        self.plotWidget = pg.plot(title="Realtime plotting benchmark")
        self.cycle = 0

        if self.REDPITAYA:
            self.r = RedPitaya()
            self.r.scope.setup(trigger_source='immediately', duration=self.duration)

        self.timer = QtCore.QTimer()
        self.timer.setInterval(1000*self.dt)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    def update_plot(self):
        self.cycle += 1
        if self.cycle == 1:
            self.starttime = time.time()
        if self.cycle == self.cycles:
            self.endtime = time.time()
        if self.REDPITAYA:
            t = self.r.scope.times
            #y1 = self.r.scope.curve(ch=1, timeout=0)
            #y2 = self.r.scope.curve(ch=2, timeout=0)
            #self.r.scope.setup()
            y1 = self.r.scope._data_ch1_current
            y2 = self.r.scope._data_ch2_current
        else:
            t = self.t0 - self.starttime + time.time()
            phi = 2.0*np.pi*self.frequency*t
            y1 = np.sin(phi)
            y2 = np.cos(phi)
        if self.cycle == 1:
            self.c1 = self.plotWidget.plot(t, y1, pen='g')
            self.c2 = self.plotWidget.plot(t, y2, pen='r')
        else:
            self.c1.setData(t, y1)
            self.c2.setData(t, y2)

    def tearDown(self):
        self.timer.stop()

    def test_speed(self):
        while self.cycle < self.cycles:
            time.sleep(0.001)
            APP.processEvents()
        if self.cycle < self.cycles:
            print("Must complete %d cycles before testing for speed!"%self.cycles)
            assert False
        else:
            dt = (self.endtime - self.starttime) / self.cycles
            print("Frame rate: %f Hz"%(1.0/dt))
            print("Update period: %f ms" %(dt))
            assert (dt < 1e-3)
