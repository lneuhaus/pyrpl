# unitary test for the pyrpl module

import unittest
import os

from pyrpl import RedPitaya


class RedPitayaTestCases(unittest.TestCase):

    def setUp(self):
        self.hostname = os.environ.get('REDPITAYA')

    def tearDown(self):
        pass

    def test_hostname(self):
        self.assertIsNotNone(
            self.hostname,
            msg="Set REDPITAYA=localhost or the ip of your board to proceed!")
        
    def test_connect(self):
        if self.hostname != "localhost":
            r = RedPitaya(hostname=self.hostname)
            self.assertEqual(r.hk.led, 0)
    