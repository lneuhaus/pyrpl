import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from PyQt4 import QtCore, QtGui
from ..test_base import TestPyrpl
APP = QtGui.QApplication.instance()


class TestScopeClass(TestPyrpl):
    # somehow the file seems to suffer from other nosetests, so pick an
    # individual name for this test:
    # tmp_config_file = "nosetests_config_scope.yml"

    def test_scope_stopped_at_startup(self):
        """
        This was so hard to detect, I am making a unit test
        """
        assert(self.r.scope.running_continuous==False)

    def test_scope_rolling_mode_and_running_state_update(self):
        """ makes sure scope rolling_mode and running states are correctly
        setup when something is changed """
        def data_changing():
            time.sleep(0.1)
            APP.processEvents()
            data = self.r.scope.last_datas[1]
            time.sleep(0.75)
            APP.processEvents()
            time.sleep(0.1)
            return ((data !=
                     self.r.scope.last_datas[1])[~np.isnan(data)]).any()

        self.r.asg1.frequency = 0
        self.r.scope.setup(duration=0.5, trigger_source='asg1',
                           trigger_delay=0., rolling_mode=True, input1='in1',
                           ch1_active=True, ch2_active=True)
        self.r.scope.run_continuous()
        assert data_changing()  # rolling mode should be active
        self.r.scope.save_state("running_roll")

        self.r.scope.duration = 0.001
        # rolling mode inactive for durations < 0.1 s
        assert not data_changing()

        from time import sleep
        sleep(0.5)
        self.r.scope.duration = 0.5
        assert data_changing()

        self.r.scope.rolling_mode = False
        self.r.scope.duration = 0.2
        self.r.scope.save_state("running_triggered")
        assert not data_changing()

        self.r.asg1.frequency = 1e5
        assert data_changing()

        self.r.scope.stop()
        self.r.scope.save_state("stop")
        assert not data_changing()

        self.r.scope.load_state("running_roll")
        assert data_changing()

        self.r.scope.stop()
        self.r.scope.load_state("running_triggered")
        assert data_changing()

        self.r.scope.load_state("stop")
        assert not data_changing()

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
