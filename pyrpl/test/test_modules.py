from nose.tools import with_setup
from unittest import TestCase
import os
import numpy as np
import logging
logger = logging.getLogger(name=__name__)

from pyrpl import RedPitaya
from pyrpl.redpitaya_modules import *
from pyrpl.registers import *
from pyrpl.bijection import Bijection


class TestClass(object):
    
    @classmethod
    def setUpAll(self):
        # these tests wont succeed without the hardware
        if os.environ['REDPITAYA_HOSTNAME'] == 'unavailable':
            self.r = None
        else:
            self.r = RedPitaya()
    
    def test_asg(self):
        if self.r is None:
            return
        for asg in [self.r.asg1,self.r.asg2]:
            asg.setup(frequency=12345.)
            expect = 1./8191*np.round(8191.*np.cos( 
                                np.linspace(
                                    0, 
                                    2*np.pi, 
                                    asg.data_length, 
                                    endpoint=False)))
            if np.max(np.abs(expect-asg.data))>2**-12:
                assert False
   
    def test_asg_to_scope(self):
        if self.r is None:
            return
        for asg in [self.r.asg1, self.r.asg2]:
            self.r.scope.duration = 0.1
            
            
            asg.setup(waveform='ramp',
                      frequency=1./self.r.scope.duration,
                      trigger_source='immediately')
            
            expect = np.linspace(-1.0,3.0, asg.data_length, endpoint=False)
            expect[asg.data_length//2:] = -1*expect[:asg.data_length//2]
            expect*=-1
            self.r.scope.input1 = Bijection(self.r.scope._ch1._inputs).inverse[asg._dsp._number]
            self.r.scope.input2 = self.r.scope.input1
            #asg.trig()
            self.r.scope.setup(trigger_source=self.r.scope.input1) # the asg trigger
            
            measured = self.r.scope.curve(ch=1, timeout=4)
            if np.max(np.abs(measured-expect)) > 0.001:
                assert False            #    assert False
                
    def test_scope_trigger_immediately(self):
        if self.r is None:
            return
        self.r.scope.trigger_source = "immediately"
        self.r.scope.duration = 0.1
        self.r.scope.setup()
        self.r.scope.curve()
        