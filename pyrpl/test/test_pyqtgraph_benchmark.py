import logging
import time

import numpy as np
import pyqtgraph as pg
import pytest
from qtpy import QtCore

from .. import APP
from ..async_utils import sleep
from .test_redpitaya import TestRedpitaya

# passes on the simulated (_FAKE_) Red Pitaya too
pytestmark = pytest.mark.simulation

logger = logging.getLogger(name=__name__)


class TestPyqtgraph(TestRedpitaya):
    """This test case creates a maximally simplistic scope gui
    that continuously plots the data of both scope channels,
    and checks the obtainable frame rate.
    Frame rates down to 20 Hz are accepted"""

    N = 2**14
    cycles = 50  # cycles to average frame rate over
    frequency = 10.0
    duration = 1.0
    dt = 0.01  # maximum frame rate is 100 Hz
    REDPITAYA = False  # REDPITAYA=True tests the speed with Red Pitaya Scope
    timeout = 10.0  # timeout if the gui never plots anything

    @pytest.fixture(autouse=True)
    def setup_timer(self):
        self.t0 = np.linspace(0, self.duration, self.N)
        self.plotWidget = pg.plot(title="Realtime plotting benchmark")
        self.cycle = 0
        self.starttime = time.time()  # not yet the actual starttime, but needed for timeout
        if self.REDPITAYA:
            self.r.scope.setup(trigger_source="immediately", duration=self.duration)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(int(1000 * self.dt))
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

        yield  # Test runs here

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
            # y1 = self.r.scope.curve(ch=1, timeout=0)
            # y2 = self.r.scope.curve(ch=2, timeout=0)
            # self.r.scope.setup()
            y1 = self.r.scope._data_ch1_current
            y2 = self.r.scope._data_ch2_current
        else:
            t = self.t0 + (time.time() - self.starttime)
            phi = 2.0 * np.pi * self.frequency * t
            y1 = np.sin(phi)
            y2 = np.cos(phi)
        if self.cycle == 1:
            self.c1 = self.plotWidget.plot(t, y1, pen="g")
            self.c2 = self.plotWidget.plot(t, y2, pen="r")
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
            raise AssertionError(f"Must complete {self.cycles:d} cycles before testing for speed!")
        else:
            # time per frame
            dt = (self.endtime - self.starttime) / self.cycles
            print(f"Frame rate: {1.0 / dt:f} Hz")
            dt *= 1e3
            print(f"Update period: {dt:f} ms")
            # require at least 20 fps
            assert dt < 50.0, (
                f"Frame update time of {dt:f} ms with "
                f"{'out' if self.REDPITAYA else ''} redpitaya scope is above "
                "specification of 50 ms!"
            )
