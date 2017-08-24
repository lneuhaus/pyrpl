# unitary test for the RedPitaya and Pyrpl modules and baseclass for all other
# tests
import logging
logger = logging.getLogger(name=__name__)
import os
from pyrpl import Pyrpl, RedPitaya, user_config_dir


class TestRedpitaya(object):
    @classmethod
    def setUpAll(cls):
        print("=======SETTING UP TestRedpitaya===========")
        cls.hostname = os.environ.get('REDPITAYA_HOSTNAME')
        cls.password = os.environ.get('REDPITAYA_PASSWORD')
        cls.r = RedPitaya()

    @classmethod
    def tearDownAll(cls):
        print("=======TEARING DOWN TestRedpitaya===========")
        cls.r.end_all()

    def test_redpitaya(self):
        assert (self.r is not None)

    def test_connect(self):
        assert self.r.hk.led == 0
