import logging
logger = logging.getLogger(name=__name__)
import pyqtgraph as pg
import numpy as np
import time
from qtpy import QtCore
from .test_redpitaya import TestRedpitaya
from .. import APP
from ..async_utils import sleep


class TestPyqtgraph(TestRedpitaya):
    """ This test case creates a maximally simplistic scope gui
    that continuously plots the data of both scope channels,
    and checks the obtainable frame rate.
    Frame rates down to 20 Hz are accepted """
    N = 2 ** 14
    cycles = 50  # cycles to average frame rate over
    frequency = 10.0
    duration = 1.0
    dt = 0.01  # maximum frame rate is 100 Hz
    REDPITAYA = False  # REDPITAYA=True tests the speed with Red Pitaya Scope
    timeout = 10.0  # timeout if the gui never plots anything

    def setup(self):
        self.t0 = np.linspace(0, self.duration, self.N)
        self.plotWidget = pg.plot(title="Realtime plotting benchmark")
        self.cycle = 0
        self.starttime = time.time()  # not yet the actual starttime, but needed for timeout
        if self.REDPITAYA:
            self.r.scope.setup(trigger_source='immediately', duration=self.duration)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(1000*self.dt)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    def teardown(self):
        self.timer.stop()
        APP.processEvents()
        self.plotWidget.close()
        APP.processEvents()

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
            t = self.t0 + (time.time()-self.starttime)
            phi = 2.0*np.pi*self.frequency*t
            y1 = np.sin(phi)
            y2 = np.cos(phi)
        if self.cycle == 1:
            self.c1 = self.plotWidget.plot(t, y1, pen='g')
            self.c2 = self.plotWidget.plot(t, y2, pen='r')
        else:
            self.c1.setData(t, y1)
            self.c2.setData(t, y2)

    def test_speed(self):
        # for now, this test is a cause of hangup
        # return
        # wait for the gui to display all required curves
        while self.cycle < self.cycles or (time.time() > self.timeout + self.starttime):
            # this is needed such that the test GUI actually plots something
            sleep(0.01)
        if self.cycle < self.cycles:
            assert False, "Must complete %d cycles before testing for speed!"%self.cycles
        else:
            # time per frame
            dt = (self.endtime - self.starttime) / self.cycles
            print("Frame rate: %f Hz"%(1.0/dt))
            dt *= 1e3
            print("Update period: %f ms" %(dt))
            # require at least 20 fps
            assert (dt < 50.0), \
                "Frame update time of %f ms with%s redpitaya scope is above specification of 50 ms!" \
                % ('out' if self.REDPITAYA else '', dt)
