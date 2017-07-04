import logging
logger = logging.getLogger(name=__name__)
import time
import copy
from qtpy import QtWidgets, QtCore
from .test_base import TestPyrpl
import numpy as np
from .. import global_config
from ..async_utils import sleep as async_sleep


class TestNA(TestPyrpl):
    def setup(self):
        self.na = self.pyrpl.networkanalyzer

    def test_na_stopped_at_startup(self):
        """
        This was so hard to detect, I am making a unit test
        """
        assert(self.na.running_state=='stopped')

    def test_na_running_states(self):
        # make sure scope rolling_mode and running states are correctly setup
        # when something is changed
        with self.pyrpl.networkanalyzer as self.na:
            def data_changing():
                data = copy.deepcopy(self.na.data_avg)
                async_sleep(self.communication_time * 10)
                return (data != self.na.data_avg).any()

            self.na.setup(start_freq=1000,
                          stop_freq=1e4,
                          rbw=1000,
                          points=10000,
                          trace_average=1)
            async_sleep(2.0*self.communication_time)
            self.na.single_async()
            async_sleep(self.communication_time * 5.0)
            assert data_changing()

            current_point = self.na.current_point
            self.na.rbw = 10000  # change some setup_attribute
            assert self.na.current_point < current_point # make sure the run was
            #  restarted

            self.na.continuous()
            async_sleep(self.communication_time * 5.0)
            assert data_changing()
            self.na.stop()  # do not let the na running or other tests might be
            # screwed-up !!!

    #@unittest.skip("testing skipping")
    def test_benchmark(self):
        with self.pyrpl.networkanalyzer as self.na:
            # test na speed without gui -
            # that's as good as we can do right now (1 read + 1 write per point
            # + 0.9 error margin)
            try:
                reads_per_na_cycle = global_config.test.reads_per_na_cycle
            except:
                reads_per_na_cycle = 2.9
                logger.info("Could not find global config file entry "
                            "'test.reads_per_na_cycle. Assuming default value "
                            "%.1f.", reads_per_na_cycle)
            maxduration = self.communication_time * reads_per_na_cycle
            # maxduration factor used to be 2.9, but travis needs more time
            points = int(round(10.0 / maxduration))
            self.na.setup(start_freq=1e3,
                          stop_freq=1e4,
                          rbw=1e6,
                          points=points,
                          average_per_point=1,
                          trace_average=1)
            tic = time.time()
            self.na.curve()
            duration = (time.time() - tic)/self.na.points
            assert duration < maxduration, \
                "Na w/o gui should take at most %.1f ms per point, but actually " \
                "needs %.1f ms. This won't compromise functionality but it is " \
                "recommended that establish a more direct ethernet connection" \
                "to you Red Pitaya module" % (maxduration*1000.0, duration*1000.0)
            # test na speed with gui.
            self.na.setup(start_freq=1e3,
                          stop_freq=1e4,
                          rbw=1e6,
                          points=points//2,
                          average_per_point=1,
                          trace_average=1)
            tic = time.time()
            self.na.single()
            async_sleep(0.05)
            print(self.na.running_state)
            while(self.na.running_state == 'running_single'):
                async_sleep(0.05)
            duration = (time.time() - tic)/self.na.points
            #Allow twice as long with gui
            maxduration *= 2
            assert duration < maxduration, \
                "Na gui should take at most %.1f ms per point, but actually " \
                "needs %.1f ms. This won't compromise functionality but it is " \
                "recommended that establish a more direct ethernet connection" \
                "to you Red Pitaya module" % (maxduration*1000.0, duration*1000.0)
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
        async_sleep(0.5)
        tic = time.time()
        self.total = 1000
        self.timer.start()
        while self.count < self.total:
            async_sleep(0.05)
        duration = time.time() - tic
        assert(duration < 3.0), duration

    def test_get_curve(self):
        with self.pyrpl.networkanalyzer as self.na:
            self.na.iq.output_signal = 'quadrature'
            self.na.setup(amplitude=1., start_freq=1e5, stop_freq=2e5, rbw=10000,
                          points=100, avg_per_point=10, input=self.na.iq,
                          acbandwidth=0)
            y = self.na.curve()
            assert(all(abs(y-1)<0.1))  # If transfer function is taken into
            # account, that should be much closer to 1...
            # Also, there is this magic value of 0.988 instead of 1 ??!!!

    def test_iq_stopped_when_paused(self):
        with self.pyrpl.networkanalyzer as self.na:
            self.na.setup(start_freq=1e5,
                          stop_freq=2e5,
                          rbw=100000,
                          points=100,
                          output_direct="out1",
                          input="out1",
                          trace_average=1,
                          amplitude=0.01)
            self.na.continuous()
            async_sleep(0.05)
            self.na.pause()
            async_sleep(0.05)
            assert self.na.iq.amplitude==0
            self.na.continuous()
            async_sleep(0.05)
            assert self.na.iq.amplitude!=0
            self.na.stop()
            async_sleep(0.05)
            assert self.na.iq.amplitude==0

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
        with self.pyrpl.networkanalyzer as self.na:
            self.na.setup(start_freq=1e5,
                          stop_freq=2e5,
                          rbw=100000,
                          points=10,
                          output_direct="out1",
                          input="out1",
                          amplitude=0.01,
                          trace_average=1,
                          running_state="running_continuous")
            for i in range(20):
                async_sleep(0.01)
            old = self.pyrpl.c._save_counter
            for i in range(10):
                async_sleep(0.01)
            new = self.pyrpl.c._save_counter
            self.na.stop()
            assert (old == new), (old, new)
