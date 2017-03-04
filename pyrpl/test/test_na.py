import logging
logger = logging.getLogger(name=__name__)
import time
import copy
from PyQt4 import QtGui, QtCore
from .test_base import TestPyrpl

from time import sleep

APP = QtGui.QApplication.instance()


class TestClass(TestPyrpl):
    def setup(self):
        self.na = self.pyrpl.na

    def test_na_stopped_at_startup(self):
        """
        This was so hard to detect, I am making a unit test
        """
        assert(self.na.running_state=='stopped')

    def test_na_running_states(self):
        # make sure scope rolling_mode and running states are correctly setup
        # when something is changed
        if self.r is None:
            return

        def data_changing():
            time.sleep(0.1)
            APP.processEvents()
            data = copy.deepcopy(self.na.y_averaged)
            time.sleep(.3)
            APP.processEvents()
            return (data != self.na.y_averaged).any()



        self.na.setup(start_freq=1000, stop_freq=1e4, rbw=1000, points=10000)
        for i in range(100):
            APP.processEvents()
        self.na.run_single()
        assert data_changing()

        self.na.rbw = 100  # change some setup_attribute
        assert self.na.running_state == "stopped"
        assert not data_changing()

        self.na.run_continuous()
        time.sleep(0.1)
        for i in range(100):
            APP.processEvents()


        assert data_changing()
        self.na.stop()  # do not let the na running or other tests might be
        # screwed-up !!!

    # maximum allowed duration to acquire one point without gui
    duration_per_point = 1.7e-3 # previously 5e-3
    # duration_per_point = 5e-3
    #@unittest.skip("testing skipping")
    def test_benchmark(self):
        """
        if self.r is None:
            return
        # test na speed without gui
        self.na.setup(start_freq=1e3,
                      stop_freq=1e4,
                      rbw=1e6,
                      points=10000,
                      avg=1)
        tic = time.time()
        self.na.curve()
        duration = (time.time() - tic)/self.na.points
        assert duration < self.duration_per_point, duration
        # that's as good as we can do right now (1 read + 1 write per point)

        """
        # test na speed with gui. Allow twice as long
        self.na.setup(start_freq=1e3,
                      stop_freq=1e4,
                      rbw=1e6,
                      points=1000,
                      avg=1)

        #for i in range(1000): # we should maybe put that in teardown(), setup(), or even pyrpl.__init__()
        #    APP.processEvents() # make sure no old events are going to screw up the timing test

        tic = time.time()
        self.na.run_single()
        APP.processEvents()
        print(self.na.running_state)
        while(self.na.running_state == 'running_single'):
            APP.processEvents()
        duration = (time.time() - tic)/self.na.points

        assert duration < 1.*self.duration_per_point, duration
        # 2 s for 200 points with gui display
        # This is much slower in nosetests than in real life (I get <3 s).
        # Don't know why.

    def coucou(self):
        self.count += 1
        if self.count < self.total:
            self.timer.start()

    def test_stupid_timer(self):
        self.timer = QtCore.QTimer()
        self.timer.setInterval(2)  # formerly 1 ms
        self.timer.setSingleShot(True)
        self.count = 0
        self.timer.timeout.connect(self.coucou)

        for i in range(1000):
            APP.processEvents()

        tic = time.time()
        self.total = 1000
        self.timer.start()
        while self.count < self.total:
            APP.processEvents()
        duration = time.time() - tic
        assert(duration < 2.5), duration

    def test_get_curve(self):
        if self.r is None:
            return
        self.na.iq.output_signal = 'quadrature'
        x, y, amp = self.na.curve(start_freq=1e5, stop_freq=2e5, rbw=10000,
                                  points=100, input=self.na.iq, acbandwidth=0)
        assert(all(abs(y-1)<0.1))  # If transfer function is taken into
        # account, that should be much closer to 1...
        # Also, there is this magic value of 0.988 instead of 1 ??!!!

    def test_iq_stopped_when_paused(self):
        if self.r is None:
            return
        self.na.setup(start_freq=1e5,
                      stop_freq=2e5,
                      rbw=100000,
                      points=100,
                      output_direct="out1",
                      input="out1",
                      amplitude=0.01)
        self.na.run_continuous()
        APP.processEvents()
        self.na.pause()
        APP.processEvents()
        assert self.na.iq.output_direct=='off'
        self.na.run_continuous()
        APP.processEvents()
        assert self.na.iq.output_direct=='out1'
        self.na.stop()
        APP.processEvents()
        assert self.na.iq.output_direct=='off'

    def test_iq_autosave_active(self):
        """
        At some point, iq._autosave_active was reinitialized by iq
        create_widget...
        """
        assert(self.na.iq._autosave_active==False)


    def test_no_write_in_config(self):
        """
        Make sure the na isn't continuously writing to config file,
        even in running mode.
        :return:
        """

        self.na.setup(start_freq=1e5,
                      stop_freq=2e5,
                      rbw=100000,
                      points=10,
                      output_direct="out1",
                      input="out1",
                      amplitude=0.01,
                      running_state="running_continuous")
        for i in range(10):
            sleep(0.01)
            APP.processEvents()
        old = self.pyrpl.c._save_counter
        for i in range(10):
            sleep(0.01)
            APP.processEvents()
        new = self.pyrpl.c._save_counter
        self.na.stop()
        assert (old == new), (old, new)