from nose.tools import with_setup
from unittest import TestCase
import os
import numpy as np

from pyrpl import RedPitaya
from pyrpl.redpitaya_modules import *
from pyrpl.registers import *
from pyrpl.bijection import Bijection


class TestClass(object):
    
    @classmethod
    def setUpAll(self):
        hostname = os.environ.get('REDPITAYA')
        if hostname != 'unavailable':
            self.r = RedPitaya(hostname=hostname)
        else:
            self.r = None
    
    
    def test_asg(self):
        if self.r is None:
            return
        for asg in [self.r.asg1,self.r.asg2]:
            asg.setup(frequency=12345.)
            expect = np.cos( np.linspace(
                                        0, 
                                        2*np.pi, 
                                        asg.data_length, 
                                        endpoint=False))
            
            if np.max(np.abs(expect-asg.data))>2**-12:
                assert False
   
   
    def test_asg_to_scope(self):
        if self.r is None:
            return
        for asg in [self.r.asg1,self.r.asg2]:
            asg.setup(waveform='ramp',
                      frequency=987654.,
                      trigger_source=None)
            expect = np.linspace(-1.0,3.0, asg.data_length, endpoint=False)
            expect[asg.data_length//2:] = -1*expect[:asg.data_length//2]
            self.r.scope.input1 = Bijection(self.r.scope._ch1._inputs).inverse[asg._dsp.number]
            self.r.scope.input2 = self.r.scope.input1
            self.r.scope.setup(duration = 5e-5,
                        trigger_source = 'asg_positive_edge')
            asg.trig()
            from time import sleep
            sleep(0.001)
            measured = self.r.scope.data_ch1
            #import matplotlib.pyplot as plt
            #plt.plot(self.r.scope.times,self.r.scope.data_ch1,self.r.scope.times,expect)
            #assert False
            
            #trigger should catch on asg output
            
            if self.r.scope.trigger_source == 'asg_positive_edge':
                pass
                #assert False
            
            