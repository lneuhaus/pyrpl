# unitary test for the RedPitaya and Pyrpl modules and baseclass for all other
# tests
import logging
logger = logging.getLogger(name=__name__)
import os
from .. import Pyrpl, user_config_dir
from ..pyrpl_utils import time

class TestPyrpl(object):
    """ base class for all pyrpl tests """
    # names of the configfiles to use
    source_config_file = "nosetests_source.yml"
    tmp_config_file = "nosetests_config.yml"

    @classmethod
    def erase_temp_file(self):
        tmp_conf = os.path.join(user_config_dir,
                     self.tmp_config_file)
        if os.path.isfile(tmp_conf):
            try:
                os.remove(tmp_conf)
            # sometimes, an earlier test delete file between exists and
            # remove calls, this gives a WindowsError
            except WindowsError:
                pass
        while os.path.exists(tmp_conf):
            pass  # make sure the file is really gone before proceeding further

    @classmethod
    def setUpAll(cls):
        print("=======SETTING UP %s===========" % cls.__name__)
        # these tests will not succeed without the hardware
        cls.erase_temp_file()  # also before (for instance in case of Ctrl-C)
        cls.pyrpl = Pyrpl(config=cls.tmp_config_file,
                          source=cls.source_config_file)
        # self.pyrpl.create_widget() # create a second widget to be sure
        cls.r = cls.pyrpl.rp
        # get an estimate of the read/write time
        N=10
        t0 = time()
        for i in range(N):
            cls.r.hk.led
        cls.read_time = (time()-t0)/float(N)
        t0 = time()
        for i in range(N):
            cls.r.hk.led = 0
        cls.write_time = (time()-t0)/float(N)
        cls.communication_time = (cls.read_time + cls.write_time)/2.0

    def test_read_write_time(self):
        maxtime = 3e-3 # maximum time per read/write in seconds
        assert self.read_time < maxtime, \
            "read operation is very slow: %e s" % self.read_time
        assert self.write_time < maxtime, \
            "write operation is very slow: %e s" % self.write_time

    @classmethod
    def tearDownAll(cls):
        print("=======TEARING DOWN %s===========" % cls.__name__)
        # shut down Pyrpl
        cls.pyrpl.end()
        # delete the configfile
        cls.erase_temp_file()

    def test_pyrpl(self):
        assert (self.pyrpl is not None)

# only one test class per file is allowed due to conflicts
