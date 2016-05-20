from nose.tools import with_setup
from unittest import TestCase
import os
import numpy as np

from pyrpl import RedPitaya


class TestClass(object):
        
    @classmethod
    def setUpAll(self):
        hostname = os.environ.get('REDPITAYA')
        if hostname != 'unavailable':
            self.r = RedPitaya(hostname=hostname)
        else:
            self.r = None
    
	#you are invited to change the following two silly tests to something useful
    def test_example(self):
        if 1 > 2:
			assert False
			
    def test_example2(self):
        if self.r.asg1.frequency < 0:
			assert False
