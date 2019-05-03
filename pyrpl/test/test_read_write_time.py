import os
import logging
logger = logging.getLogger(name=__name__)

from .test_base import TestPyrpl
from ..errors import UnexpectedPyrplError, ExpectedPyrplError


class TestReadWriteTime(TestPyrpl):
    def test_pyrpl(self):
        assert (self.pyrpl is not None)

    def test_read_write_time(self):
        # maximum time per read/write in seconds
        try:
            maxtime = global_config.test.max_communication_time
        except:
            raise ExpectedPyrplError("Error with global config file. "
                                       "Please delete the file %s and retry!"
                                       % os.path.join(user_config_dir,
                                                      'global_config.yml'))
        assert self.read_time < maxtime, \
            "Read operation is very slow: %e s (expected < %e s). It is " \
            "highly recommended that you improve the network connection to " \
            "your Red Pitaya device. " % (self.read_time, maxtime)
        assert self.write_time < maxtime, \
            "Write operation is very slow: %e s (expected < %e s). It is " \
            "highly recommended that you improve the network connection to " \
            "your Red Pitaya device. " % (self.write_time, maxtime)
