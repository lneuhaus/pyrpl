import logging

import pytest

from pyrpl.async_utils import sleep
from pyrpl.test.test_base import TestPyrpl
from pyrpl.widgets.startup_widget import HostnameSelectorWidget

# passes on the simulated (_FAKE_) Red Pitaya too
pytestmark = pytest.mark.simulation

logger = logging.getLogger(name=__name__)


class TestStartupWidgets(TestPyrpl):
    # somehow the file seems to suffer from other nosetests, so pick an
    # individual name for this test:
    # tmp_config_file = "nosetests_config_scope.yml"
    def teardown_method(self):
        pass

    def test_startup_widget(self):
        for hide_password in [True, False]:
            HostnameSelectorWidget._HIDE_PASSWORDS = hide_password
            self.widget = HostnameSelectorWidget()
        self.widget.show()
        self.widget.password = "dummy_password"

        self.widget.user = "dummy_user"
        self.widget.sshport = 12

        sleep(0.1)
        self.widget.item_double_clicked(self.widget.items[0], 0)  # Fake redpitaya

        self.widget.remove_device(self.widget.items[0])
        self.widget.countdown_start(2)
        sleep(3)
        self.widget.ok()
