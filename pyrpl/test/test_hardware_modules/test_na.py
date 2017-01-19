import logging
import os

logger = logging.getLogger(name=__name__)

from pyrpl import RedPitaya, Pyrpl
from pyrpl.attributes import *

import time
import copy
from PyQt4 import QtCore, QtGui

APP = QtGui.QApplication.instance()

class TestClass(object):
    @classmethod
    def setUpAll(self):
        # these tests wont succeed without the hardware
        if os.environ['REDPITAYA_HOSTNAME'] == 'unavailable':
            self.r = None
        else:
            # Delete
            filename = os.path.join(os.path.split(os.path.dirname(__file__))[0], 'config', 'user_config',
                                    'tests_temp.yml')
            if os.path.exists(filename):
                os.remove(filename)
            self.pyrpl = Pyrpl(config="tests_temp", source="tests_source")
            self.r = self.pyrpl.rp
            self.na = self.pyrpl.na
        self.extradelay = 0.6 * 8e-9  # no idea where this comes from

    def test_na_running_states(self):
        # make sure scope rolling_mode and running states are correctly setup when something is changed
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
        self.na.run_single()
        assert data_changing()

        self.na.rbw=100 # change some setup_attribute
        assert self.na.running_state=="stopped"
        assert not data_changing()

        self.na.run_continuous()
        assert data_changing()


    def test_benchmark(self):
        if self.r is None:
            return
        self.na.setup(start_freq=1000, stop_freq=1e4, rbw=1000000, points=200, avg=1)
        tic = time.time()
        self.na.run_single()
        APP.processEvents()
        print(self.na.running_state)
        while(self.na.running_state=='running_single'):
            APP.processEvents()
        duration = time.time() - tic
        assert duration<2 # 2 s for 200 points with gui display
        # This is much slower in nosetests than in real life (I get <3 s). Don't know why

        self.na.setup(start_freq=1000, stop_freq=1e4, rbw=1000000, points=1000, avg=1)
        tic = time.time()
        self.na.curve()
        duration = time.time() - tic
        assert duration < 2 # that's as good as we can do right now (1 read + 1 write per point)

    def test_get_curve(self):
        if self.r is None:
            return
        self.na.iq.output_signal = 'quadrature'
        x, y, amp = self.na.curve(start_freq=1e5, stop_freq=2e5, rbw=10000, points=100,
                                  input=self.na.iq, acbandwidth=0)
        assert(all(abs(y-1)<0.1)) # If transfer function is taken into account, that should be much closer to 1...
        # Also, there is this magic value of 0.988 instead of 1 ??!!!

    def test_iq_stoped_when_paused(self):
        if self.r is None:
            return
        self.na.setup(start_freq=1e5, stop_freq=2e5, rbw=100000, points=100, output_direct="out1", input="out1", amplitude=0.01)
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

