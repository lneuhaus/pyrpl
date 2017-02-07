# unitary test for the RedPitaya and Pyrpl modules and baseclass for all other
# tests
import logging
logger = logging.getLogger(name=__name__)
import os
from .. import Pyrpl, user_config_dir


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
        print("=======SETTING UP TestPyrpl===========")
        # these tests will not succeed without the hardware
        cls.erase_temp_file()  # also before (for instance in case of Ctrl-C)
        cls.pyrpl = Pyrpl(config=cls.tmp_config_file,
                          source=cls.source_config_file)
        # self.pyrpl.create_widget() # create a second widget to be sure
        cls.r = cls.pyrpl.rp

    @classmethod
    def tearDownAll(cls):
        print("=======TEARING DOWN TestPyrpl===========")
        # shut down Pyrpl
        cls.pyrpl.end()
        # delete the configfile
        cls.erase_temp_file()


# only one test class per file is allowed due to conflicts
#
#class TestMyPyrpl(TestPyrpl):
#    """ example for a derived test class"""
#    def test_pyrpl(self):
#        assert (self.pyrpl is not None)
