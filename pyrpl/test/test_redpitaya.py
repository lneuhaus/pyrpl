# unitary test for the RedPitaya and Pyrpl modules and baseclass for all other
# tests

import logging

import pytest

# passes on the simulated (_FAKE_) Red Pitaya too
pytestmark = pytest.mark.simulation

logger = logging.getLogger(name=__name__)


class TestRedpitaya:
    @pytest.fixture(autouse=True)
    def setup_rp(self, hardware_session):
        """
        Injects the RedPitaya instance from the session.
        Works regardless of whether a full Pyrpl app was created or just the driver.
        """
        self.r = hardware_session.rp

        # If you need config vars that are usually in RedPitaya class:
        self.read_time = hardware_session.read_time
        self.write_time = hardware_session.write_time

    def test_redpitaya(self):
        assert self.r is not None

    def test_connect(self):
        self.r.hk.led = 0
        assert self.r.hk.led == 0
