# unitary test for the RedPitaya and Pyrpl modules and baseclass for all other
# tests
import unittest
import os
import logging

from .. import Pyrpl, RedPitaya
logger = logging.getLogger(name=__name__)

class TestRedpitaya(unittest.TestCase):
    @classmethod
    def setUpAll(self):
        self.hostname = os.environ.get('REDPITAYA_HOSTNAME')
        self.password = os.environ.get('REDPITAYA_PASSWORD')
        # these tests wont succeed without the hardware
        if os.environ['REDPITAYA_HOSTNAME'] == 'unavailable':
            self.r = None
        else:
            self.r = RedPitaya()
        #self.mysetup()

    def mysetup(self):
        # derived class custom setup
        pass

    @classmethod
    def tearDownAll(self):
        pass


class TestMyRedpitaya(TestRedpitaya):
    """ example for a derived test class"""

    def test_import(self):
        assert (self.r is not None)

    def test_hostname(self):
        self.assertIsNotNone(
            self.hostname,
            msg="Set REDPITAYA_HOSTNAME=unavailable or the ip of your board to proceed!")

    def test_connect(self):
        r = RedPitaya(hostname=self.hostname)
        self.assertEqual(r.hk.led, 0)


class TestPyrpl(unittest.TestCase):
    @classmethod
    def setUpAll(self):
        # these tests wont succeed without the hardware
        if os.environ['REDPITAYA_HOSTNAME'] == 'unavailable':
            self.pyrpl = None
            self.r = None
        else:
            self.pyrpl = Pyrpl(config="tests_temp", source="tests_source")
            self.r = self.pyrpl.rp

    @classmethod
    def tearDownAll(self):
        # shut down the gui if applicable
        pass
        # properly close the connections
        self.pyrpl.rp.end()
        # delete the configfile
        os.remove(self.pyrpl.c._filename)


class TestMyPyrpl(TestPyrpl):
    """ example for a derived test class"""
    def test_import(self):
        assert (self.pyrpl is not None)
