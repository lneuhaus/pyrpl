import unittest
import os

from pyrpl import RedPitaya
from pyrpl.redpitaya_modules import *
from pyrpl.registers import *

class RedPitayaTestCases(unittest.TestCase):
    def __init__(self, *args,**kwargs):
        self.setUp()
        super(RedPitayaTestCases,self).__init__(*args,**kwargs)
        
    def setUp(self):
        self.hostname = os.environ.get('REDPITAYA')
        self.r = RedPitaya(hostname=self.hostname)
        for key, module in self.r.__dict__.items():
            if isinstance(module,BaseModule):
                print "Scanning module",key,"..."
                for rkey,reg in type(module).__dict__.items():
                    if isinstance(reg,Register):
                        print "Scanning register",rkey,"..."
                        f = generatetest(module,reg,rkey)
                        self.__dict__["test_"+key+"_"+rkey] = f

    def tearDown(self):
        pass

    def test_modules(self):
        return
        """for regkey,reg in m.__dict__.items():
            if isinstance(m,Register):
                print "Testing register",regkey,"..."
                self.checkregister(m, reg, regkey)
                           
    def checkregister(self, module, reg, regkey):
        if isinstance(reg,BoolRegister):
            m[regkey]=True
            assertTrue(m[regkey])
            m[regkey]=Fqlse
            assertFalse(m[regkey])
            assertTrue(isinstance(reg,BoolRegister))
            
#        elif isinstance(reg,Register):
"""        
def generatetest(module,reg,rkey):
    def f():
        0/0
        print rkey
        return
    return f