import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from qtpy import QtCore, QtWidgets
from pyrpl.test.test_base import TestPyrpl
from pyrpl import APP
from pyrpl.curvedb import CurveDB
from pyrpl.widgets.startup_widget import HostnameSelectorWidget
from pyrpl.async_utils import sleep

class TestStartupWidgets(TestPyrpl):
    # somehow the file seems to suffer from other nosetests, so pick an
    # individual name for this test:
    # tmp_config_file = "nosetests_config_scope.yml"
    def teardown(self):
        pass

    def test_startup_widget(self):
        for hide_password in [True, False]:
            HostnameSelectorWidget._HIDE_PASSWORDS = hide_password
            self.widget = HostnameSelectorWidget()
        self.widget.show()
        self.widget.password = "dummy_password"

        self.widget.user = 'dummy_user'
        self.widget.sshport = 12

        sleep(0.1)
        self.widget.item_double_clicked(self.widget.items[0], 0) # Fake redpitaya

        self.widget.remove_device(self.widget.items[0])
        self.widget.countdown_start(2)
        sleep(3)
        self.widget.ok()
