import logging

import pytest

from .test_base import TestPyrpl

# passes on the simulated (_FAKE_) Red Pitaya too
pytestmark = pytest.mark.simulation

logger = logging.getLogger(name=__name__)


class TestExample(TestPyrpl):
    @pytest.fixture(autouse=True)
    def setup_asg(self):
        self.asg = self.pyrpl.rp.asg0

    # you are welcome to change the following silly tests to something useful
    def test_example(self):
        if 1 > 2:
            raise AssertionError()

    def test_example2(self):
        if self.asg.frequency < 0:
            raise AssertionError()

    def test_example3(self):
        if not self.asg.frequency >= 0:
            raise AssertionError()
