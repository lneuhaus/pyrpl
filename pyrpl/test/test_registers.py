from nose.tools import with_setup
from unittest import TestCase
import os
import numpy as np

from pyrpl import RedPitaya
from pyrpl.redpitaya_modules import *
from pyrpl.registers import *



class TestClass(object):
    
    @classmethod
    def setUpAll(self):
        hostname = os.environ.get('REDPITAYA')
        if hostname != 'unavailable':
            self.r = RedPitaya(hostname=hostname)
        else:
            self.r = None
    
    def test_generator(self):
        if self.r is None:
            assert False
        for modulekey, module in self.r.__dict__.items():
            if isinstance(module,BaseModule):
                print "Scanning module",modulekey,"..."
                for regkey,regclass in type(module).__dict__.items():
                    if isinstance(regclass,Register):
                        print "Scanning register",regkey,"..."
                        yield self.register_validation, module, modulekey, regclass, regkey
    

    def register_validation(self, module, modulekey, reg, regkey):
        print modulekey, regkey
        if type(reg)==Register:
            # try to read
            value = module.__getattribute__(regkey)
            if type(value) != int: #make sure Register represents an int
                assert False, 'wrong type: int != %s'%str(type(value))
        if type(reg)==LongRegister:
            # try to read
            value = module.__getattribute__(regkey)
            if type(value) != int and type(value) != long: 
                assert False, 'wrong type: int/long != %s'%str(type(value))#make sure Register represents an int
        if type(reg)==BoolRegister or type(reg)==IORegister:
            # try to read
            value = module.__getattribute__(regkey)
            if type(value) != bool: #make sure Register represents an int
                assert False
            #exclude read-only registers
            if regkey in ['reset_writestate_machine',
                          'trigger_armed']:
                return
            #write opposite value and confirm it has changed
            module.__setattr__(regkey, not value)
            if value == module.__getattribute__(regkey):
                assert False
            #write back original value and check for equality
            module.__setattr__(regkey, value)
            if value != module.__getattribute__(regkey):
                assert False
        if type(reg)==FloatRegister:
            # try to read
            value = module.__getattribute__(regkey)
            if type(value) != float: #make sure Register represents an int
                assert False
            #exclude read-only registers
            if regkey in ['pfd_integral',
                          'ch1_firstpoint',
                          'ch2_firstpoint',
                          'dac1',
                          'dac2',
                          'adc1',
                          'adc2']:
                return
            #write something different and confirm change
            if value == 0:
                write = 1e10
            else:
                write = 0
            module.__setattr__(regkey, write)
            if value == module.__getattribute__(regkey):
                assert False
            #write sth negative
            write = -1e10
            module.__setattr__(regkey, write)
            if module.__getattribute__(regkey)>=0:
                if reg.signed:
                    assert False
                else: #unsigned registers should use absolute value and 
                      #therefore not be zero when assigned large negative values
                    if module.__getattribute__(regkey) == 0:
                        assert False
            #set back original value
            module.__setattr__(regkey, value)
            if value != module.__getattribute__(regkey):
                assert False
        if type(reg)==PhaseRegister:
            # try to read
            value = module.__getattribute__(regkey)
            if type(value) != float: #make sure Register represents an int
                assert False
            #make sure any random phase has an error below 1e-6 degrees !
            if regkey not in ['scopetriggerphase']:
                for phase in np.linspace(-1234,5678,90):
                    module.__setattr__(regkey, phase)
                    if abs(module.__getattribute__(regkey)-(phase%360))>1e-6:
                        assert False
            #set back original value
            module.__setattr__(regkey, value)
            if value != module.__getattribute__(regkey):
                assert False
        if type(reg)==FrequencyRegister:
            # try to read
            value = module.__getattribute__(regkey)
            if type(value) != float: #make sure Register represents an int
                assert False
            #make sure any frequency has an error below 100 mHz!
            if regkey not in []:
                for freq in [0,1,10,1e2,1e3,1e4,1e5,1e6,1e7,1e8]:
                    module.__setattr__(regkey, freq)
                    if abs(module.__getattribute__(regkey)-freq)>0.1:
                        assert False
            #set back original value
            module.__setattr__(regkey, value)
            if value != module.__getattribute__(regkey):
                assert False
        if type(reg)==SelectRegister:
            # try to read
            value = module.__getattribute__(regkey)
            if type(value) != type(reg.options.keys()[0]): #make sure Register represents an int
                assert False
            #exclude read-only registers
            if regkey in []:
                return
            #try all options and confirm change that they are saved
            for option in reg.options.keys():
                module.__setattr__(regkey, option)
            if option != module.__getattribute__(regkey):
                assert False
            #set back original value
            module.__setattr__(regkey, value)
            if value != module.__getattribute__(regkey):
                assert False
        return
    
