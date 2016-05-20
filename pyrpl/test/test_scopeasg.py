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
        assert self.r.scope.dac1==0
        self.r.asg1.output='out1'
        self.r.asg1.setup(amplitude=1.0,waveform='halframp',frequency=125e6/(2**14))
        self.r.scope.input1='dac1'
        self.r.scope.trigger_source = 'ch1_positive_edge'
        self.r.scope.threshold_ch1 = 0
        self.r.scope.hysteresis_ch1 = 1
        self.r.scope.trigger_delay = 8191
        self.r.scope.trigger_armed = True
        for i in range(100):
            if not self.r.scope.trigger_armed:
                break
        err = np.abs(self.r.scope.data_ch1[2**13])
        print "Error: ", err
        assert(err<0.01)
