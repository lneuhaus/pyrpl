# unitary test for the pyrpl module

import unittest
import os
import logging
logger = logging.getLogger(name=__name__)

from pyrpl import RedPitaya


class RedPitayaTestCases(unittest.TestCase):

    def setUp(self):
        self.hostname = os.environ.get('REDPITAYA_HOSTNAME')
        self.password = os.environ.get('REDPITAYA_PASSWORD')

    def tearDown(self):
        pass

    def test_hostname(self):
        self.assertIsNotNone(
            self.hostname,
            msg="Set REDPITAYA_HOSTNAME=unavailable or the ip of your board to proceed!")

    def test_password(self):
        if self.hostname == "unavailable":
            return
        self.assertIsNotNone(
            self.password,
            msg="Set REDPITAYA_PASSWORD=<your redpitaya password> to proceed!")
        
    def test_connect(self):
        r = RedPitaya(hostname=self.hostname, password=self.password)
        self.assertEqual(r.hk.led, 0)