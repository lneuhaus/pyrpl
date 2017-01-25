# unitary test for the RedPitaya and Pyrpl modules and baseclass for all other
# tests
import logging
logger = logging.getLogger(name=__name__)
import os
from .. import Pyrpl, RedPitaya

class TestRedpitaya(object):
    @classmethod
    def setUpAll(self):
        self.hostname = os.environ.get('REDPITAYA_HOSTNAME')
        self.password = os.environ.get('REDPITAYA_PASSWORD')
        # these tests wont succeed without the hardware
        #if os.environ['REDPITAYA_HOSTNAME'] == 'unavailable':
        #    self.r = None
        #else:
        self.r = RedPitaya()

    @classmethod
    def tearDownAll(self):
        pass


class TestMyRedpitaya(TestRedpitaya):
    """ example for a derived test class"""

    def test_redpitaya(self):
        assert (self.r is not None)

    def test_connect(self):
        assert self.r.hk.led == 0


class TestPyrpl(TestRedpitaya):
    """ base class for all pyrpl tests """
    # name of the configfile to use
    source_config_file = "tests_source"

    @classmethod
    def setUpAll(self):
        # these tests wont succeed without the hardware
        #if os.environ['REDPITAYA_HOSTNAME'] == 'unavailable':
        #    self.pyrpl = None
        #    self.r = None
        #else:
        self.pyrpl = Pyrpl(config="tests_temp",
                           source=self.source_config_file)
        self.r = self.pyrpl.rp

    @classmethod
    def tearDownAll(self):
        # none of the below stuff works properly, all introduce more errors...
        # shut down the gui if applicable
        # -> this requires some other functions
        # at least stop all acquisitions
        #self.pyrpl.na.stop()
        #self.pyrpl.scope.stop()
        # self.pyrpl.specan.stop()
        # for now a workaround: prevent reconnection after closing of
        # the connection
        #self.r.parameters['hostname'] = 'unavailable'
        # also kill the ssh such that no more fpga flashing can occur
        # does not work now
        #del self.r.ssh
        # properly close the connections
        self.pyrpl.rp.end()
        # delete the configfile
        os.remove(self.pyrpl.c._filename)


class TestMyPyrpl(TestPyrpl):
    """ example for a derived test class"""
    def test_pyrpl(self):
        assert (self.pyrpl is not None)
