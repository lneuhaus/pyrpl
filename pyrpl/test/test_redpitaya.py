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

    # This test is not strictly required as the password may be unchanged 'root'
    #def test_password(self):
    #    self.assertIsNotNone(
    #        self.password,
    #        msg="Set REDPITAYA_PASSWORD=<your redpitaya password> to proceed!")
        
    def test_connect(self):
        r = RedPitaya(hostname=self.hostname)
        self.assertEqual(r.hk.led, 0)
    