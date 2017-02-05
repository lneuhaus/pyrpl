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
    source_config_file = "nosetests_source.yml"
    tmp_config_file = "nosetests_config.yml"

    @classmethod
    def erase_temp_file(self):
        tmp_conf = os.path.join(Pyrpl._user_config_dir,
                     self.tmp_config_file)
        if os.path.exists(tmp_conf):
            try:
                os.remove(tmp_conf)
            # sometimes, an earlier test delete file between exists and
            # remove calls, this gives a WindowsError
            except WindowsError:
                pass
        while os.path.exists(tmp_conf):
            pass  # make sure the file is really gone before proceeding further

    @classmethod
    def setUpAll(self):
        print("=======SETTING UP " + str(self.__class__) + " ===========")
        # these tests wont succeed without the hardware
        #if os.environ['REDPITAYA_HOSTNAME'] == 'unavailable':
        #    self.pyrpl = None
        #    self.r = None
        #else:
        self.erase_temp_file()  # also before (for instance in case of Ctrl-C)
        self.pyrpl = Pyrpl(config=self.tmp_config_file,
                           source=self.source_config_file)
        # self.pyrpl.create_widget() # create a second widget to be sure
        self.r = self.pyrpl.rp

    @classmethod
    def tearDownAll(self):
        print("=======TEARING DOWN " + str(self.__class__) + " ===========")
        # none of the below stuff works properly, all introduce more errors...
        # shut down the gui if applicable
        # -> this requires some other functions
        # at least stop all acquisitions
        #self.pyrpl.na.stop()
        #self.pyrpl.scope.stop()
        #self.pyrpl.specan.stop()
        #for pid in self.pyrpl.pids.all_modules:
        #    pid.widget.timer_ival.stop() # Already done in self.pyrpl.end()
        # for now a workaround: prevent reconnection after closing of
        # the connection
        #self.r.parameters['hostname'] = 'unavailable'
        # also kill the ssh such that no more fpga flashing can occur
        # does not work now
        #del self.r.ssh
        # properly close the connections
        self.pyrpl.end()  # rp.end()
        # delete the configfile
        self.erase_temp_file()


class TestMyPyrpl(TestPyrpl):
    """ example for a derived test class"""
    def test_pyrpl(self):
        assert (self.pyrpl is not None)
