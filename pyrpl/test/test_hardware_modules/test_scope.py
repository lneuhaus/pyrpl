import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from time import sleep
from PyQt4 import QtCore, QtGui
from ..test_base import TestPyrpl
APP = QtGui.QApplication.instance()


class TestScope(TestPyrpl):
    """
    Be carreful to stop the scope at the end of each test!!!
    """
    # somehow the file seems to suffer from other nosetests, so pick an
    # individual name for this test:
    # tmp_config_file = "nosetests_config_scope.yml"

    def test_scope_stopped_at_startup(self):
        """
        This was so hard to detect, I am making a unit test
        """
        assert(self.r.scope.running_continuous==False)

    def data_changing(self):
        time.sleep(0.1)
        APP.processEvents()
        data = self.r.scope.last_datas[1]
        time.sleep(0.75)
        APP.processEvents()
        time.sleep(0.1)
        return ((data !=
                 self.r.scope.last_datas[1])[~np.isnan(data)]).any()


    def test_scope_rolling_mode_and_running_state_update(self):
        """ makes sure scope rolling_mode and running states are correctly
        setup when something is changed """


        self.r.asg1.frequency = 0
        self.r.scope.setup(duration=0.5, trigger_source='asg1',
                           trigger_delay=0., rolling_mode=True, input1='in1',
                           ch1_active=True, ch2_active=True)
        self.r.scope.run_continuous()
        assert self.data_changing()  # rolling mode should be active
        self.r.scope.save_state("running_roll")

        self.r.scope.duration = 0.001
        # rolling mode inactive for durations < 0.1 s
        assert not self.data_changing()

        sleep(0.5)
        self.r.scope.duration = 0.5
        assert self.data_changing()

        self.r.scope.rolling_mode = False
        self.r.scope.duration = 0.2
        self.r.scope.save_state("running_triggered")
        assert not self.data_changing()

        self.r.asg1.frequency = 1e5
        assert self.data_changing()

        self.r.scope.stop()
        self.r.scope.save_state("stop")
        assert not self.data_changing()

        self.r.scope.load_state("running_roll")
        assert self.data_changing()
        sleep(1)
        assert self.data_changing() # Make sure scope is not blocked after one buffer loop

        self.r.scope.stop()
        self.r.scope.load_state("running_triggered")
        assert self.data_changing()

        self.r.scope.load_state("stop")
        assert not self.data_changing()

        self.r.scope.stop()

    def test_save_curve(self):
        if self.r is None:
            return
        self.r.scope.setup(duration=0.01, trigger_source='immediately',
                           trigger_delay=0., rolling_mode=True, input1='in1',
                           ch1_active=True, ch2_active=True)
        self.r.scope.run_single()
        time.sleep(0.1)
        APP.processEvents()
        curve1, curve2 = self.r.scope.save_curve()
        attr = self.r.scope.get_setup_attributes()
        for curve in (curve1, curve2):
            intersect = set(curve.params.keys()) & set(attr)
            assert len(intersect) >= 5  # make sure some parameters are saved
            p1 = dict((k, curve.params[k]) for k in intersect)
            p2 = dict((k, attr[k]) for k in intersect)
            assert p1 == p2   # make sure those parameters are equal to the
            # setup_attributes of the scope

    def test_setup_rolling_mode(self):
        """calling setup with rolling mode should work"""
        self.r.scope.setup(duration=0.5,
                           trigger_delay=0., rolling_mode=True, input1='in1',
                           ch1_active=True, ch2_active=True,
                           running_continuous=True)
        assert self.data_changing()
        sleep(1)
        assert self.data_changing()  # Make sure scope is not blocked
                                     # after one buffer loop

        self.r.scope.stop()

    def test_scope_slave_free(self):
        """
        Make sure the scope returns to rolling mode after being freed
        :return:
        """
        self.pyrpl.rp.scope.setup(duration=0.5,
                  trigger_delay=0., rolling_mode=True, input1='in1',
                  ch1_active=True, ch2_active=True,
                  running_continuous=True)
        with self.pyrpl.scopes.pop("myapplication") as sco:
            sco.setup(duration=0.5,
                      trigger_delay=0., rolling_mode=False, input1='in1',
                      ch1_active=True, ch2_active=True,
                      running_continuous=False)
            assert not self.data_changing()
            curve = sco.curve()
        assert self.data_changing()
        sleep(1)
        assert self.data_changing()  # Make sure scope is not blocked
            # after one buffer loop
        self.pyrpl.rp.scope.stop()

    def test_no_write_in_config(self):
        """
        Make sure the scope isn't continuously writing to config file,
        even in running mode.
        :return:
        """

        for rolling_mode in (True, False):
            self.pyrpl.rp.scope.setup(duration=0.005,
                  trigger_delay=0., rolling_mode=rolling_mode, input1='in1',
                  ch1_active=True, ch2_active=True,
                  running_continuous=True)
            for i in range(10):
                sleep(0.01)
                APP.processEvents()
            old = self.pyrpl.c._save_counter
            for i in range(10):
                sleep(0.01)
                APP.processEvents()
            new = self.pyrpl.c._save_counter
            self.pyrpl.rp.scope.stop()
            assert(old==new), (old, new)