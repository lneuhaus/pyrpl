import logging
logger = logging.getLogger(name=__name__)
import time
import copy
from qtpy import QtWidgets, QtCore
from .test_base import TestPyrpl
import numpy as np
from .. import global_config
from ..async_utils import sleep
from ..async_utils import wait
try:
    raise  # disables sound output during this test
    from pysine import sine
except:
    def sine(frequency, duration):
        print("Called sine(frequency=%f, duration=%f)" % (frequency, duration))


class TestNA(TestPyrpl):
    def setup(self):
        self.na = self.pyrpl.networkanalyzer
        # stop all other instruments since something seems to read from fpga all the time
        #self.pyrpl.hide_gui()
        self.r.scope.stop()
        self.pyrpl.spectrumanalyzer.stop()

    def test_first_na_stopped_at_startup(self):
        """
        This was so hard to detect, I am making a unit test
        """
        assert(self.na.running_state=='stopped')

    def teardown(self):
        self.na.stop()

    def test_na_running_states(self):
        # make sure scope rolling_mode and running states are correctly setup
        # when something is changed
        with self.pyrpl.networkanalyzer as self.na:
            def data_changing():
                data = copy.deepcopy(self.na.data_avg)
                sleep(self.communication_time * 10 + 0.01)
                return (data != self.na.data_avg).any()
            self.na.setup(start_freq=1000,
                          stop_freq=1e4,
                          rbw=1000,
                          points=10000,
                          trace_average=1)
            sleep(2.0*self.communication_time)
            self.na.continuous()
            sleep(self.communication_time * 5.0 + 0.1)
            assert data_changing()
            current_point = self.na.current_point
            self.na.rbw = 10000  # change some setup_attribute
            sleep(0.01)
            new_point = self.na.current_point
            assert new_point<current_point # make sure the
            #  run was
            #  restarted

            self.na.continuous()
            sleep(self.communication_time * 5.0)
            assert data_changing()
        self.na.stop()
        # do not let the na running or other tests might be
        # screwed-up !!!

    def test_benchmark_nogui(self):
        """
        test na speed without gui
        """
        # that's as good as we can do right now (1 read + 1 write per point + 0.9 error margin)
        with self.pyrpl.networkanalyzer as self.na:
            try:
                reads_per_na_cycle = global_config.test.reads_per_na_cycle
            except:
                reads_per_na_cycle = 3.1
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
            self.na.stop()
            tic = time.time()
            self.na.single()
            duration = (time.time() - tic)/self.na.points
            assert duration < maxduration, \
                "Na w/o gui should take at most %.1f ms per point, but actually " \
                "needs %.1f ms. This won't compromise functionality but it is " \
                "recommended that you establish a better ethernet connection " \
                "to your Red Pitaya module" % (maxduration*1000.0, duration*1000.0)

    def test_benchmark_gui(self):
        """
        test na speed with gui
        """
        with self.pyrpl.networkanalyzer as self.na:
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
                          points=points//2,
                          running_state='stopped',
                          average_per_point=1,
                          trace_average=1)
            tic = time.time()
            # debug read/write calls with audio output
            self.pyrpl.rp.client._sound_debug = False
            sine(1200, 0.5)
            result = self.na.single_async()
            sleep(0.1)
            # start counting points only after acquisition setup
            old_read = self.pyrpl.rp.client._read_counter
            old_write = self.pyrpl.rp.client._write_counter
            sine(1400, 0.5)
            wait(result, 10)
            sine(1500, 0.5)
            while self.na.running_state == 'running_single':
                sleep(0.1)
            sine(1600, 0.5)
            max_rw_points = self.na.points
            sleep(0.1)
            print("Reads: %d %d %d. " % (self.pyrpl.rp.client._read_counter, old_read, max_rw_points))
            assert self.pyrpl.rp.client._read_counter - old_read <= 2*max_rw_points,(self.pyrpl.rp.client._read_counter, old_read, max_rw_points)
            # twice because now we also read the# amplitude from the iq module
            print("Writes: %d %d %d. " % (self.pyrpl.rp.client._write_counter, old_write, max_rw_points))
            assert self.pyrpl.rp.client._write_counter - old_write <= max_rw_points, \
                (self.pyrpl.rp.client._write_counter, old_write, max_rw_points)
            sine(1700, 0.5)
            self.pyrpl.rp.client._sound_debug = False
            # check duration
            duration = (time.time() - tic)/self.na.points
            # Allow twice as long with gui
            maxduration *= 2
            assert duration < maxduration, \
                "Na gui should take at most %.1f ms per point, but actually " \
                "needs %.1f ms. This won't compromise functionality but it is " \
                "recommended that you establish a better ethernet connection" \
                "to your Red Pitaya module" % (maxduration*1000.0, duration*1000.0)
            # 2 s for 200 points with gui display
            # This is much slower in nosetests than in real life (I get <3 s).
            # Don't know why.
            sine(1600, 0.5)

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
        sleep(0.5)
        tic = time.time()
        self.total = 1000
        self.timer.start()
        while self.count < self.total:
            sleep(0.05)
        duration = time.time() - tic
        assert(duration < 3.0), duration

    def test_get_curve(self):
        with self.pyrpl.networkanalyzer as self.na:
            self.na.iq.output_signal = 'quadrature'
            self.na.setup(amplitude=1., start_freq=1e5, stop_freq=2e5, rbw=10000,
                          points=100, average_per_point=10, input=self.na.iq,
                          acbandwidth=0, trace_average=1)
            y = self.na.single()
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
                          running_state='stopped',
                          trace_average=1,
                          amplitude=0.01)
            self.na.continuous()
            sleep(0.05)
            self.na.pause()
            sleep(0.05)
            assert self.na.iq.amplitude==0
            self.na.continuous()
            sleep(0.05)
            assert self.na.iq.amplitude!=0
            self.na.stop()
            sleep(0.05)
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

            old = self.pyrpl.c._save_counter
            for i in range(10):
                sleep(0.01)
            new = self.pyrpl.c._save_counter
            self.na.stop()
            assert (old == new), (old, new)

    def test_save_curve(self):
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
            self.na.single()
            curve = self.na.save_curve()
            self.na.stop()
            assert len(curve.data[0]) == self.na.points
            assert len(curve.data[1]) == self.na.points
            self.curves.append(curve)  # curve will be deleted by teardownAll

    def test_iq_stopped_after_run(self):
        with self.pyrpl.networkanalyzer as self.na:
            self.na.setup(start_freq=1e5,
                          stop_freq=2e5,
                          rbw=100000,
                          points=100,
                          output_direct="out1",
                          input="out1",
                          running_state='stopped',
                          trace_average=1,
                          amplitude=0.01)
            self.na.single()
            assert self.na.iq.amplitude==0
