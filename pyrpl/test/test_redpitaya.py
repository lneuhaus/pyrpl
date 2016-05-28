# unitary test for the pyrpl module

import unittest
import os
import logging
logger = logging.getLogger(name=__name__)

from pyrpl import RedPitaya


class RedPitayaTestCases(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_hostname(self):
        self.assertIsTrue(
            "REDPITAYA_HOSTNAME" in os.environ,
            msg="Set REDPITAYA_HOSTNAME=unavailable or the ip of your board to proceed!")
        
    def test_connect(self):
        r = RedPitaya()
        self.assertEqual(r.hk.led, 0)
    