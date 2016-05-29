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
            msg="Set REDPITAYA=localhost or the ip of your board to proceed!")

    def test_password(self):
        self.assertIsNotNone(
            self.password,
            msg="Set RP_PASSWORD=<your redpitaya password> to proceed!")
        
    def test_connect(self):
        if self.hostname != "localhost":
            r = RedPitaya(hostname=self.hostname, password=self.password)
            self.assertEqual(r.hk.led, 0)
    