import unittest
import os

from pyrpl import RedPitaya
from pyrpl.redpitaya_modules import *
from pyrpl.registers import *

class RedPitayaTestCases(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.hostname = os.environ.get('REDPITAYA')
        if self.hostname != 'localhost':
            self.r = RedPitaya(hostname=self.hostname)
        else:
            return
        for modulekey, module in self.r.__dict__.items():
                if isinstance(module,BaseModule):
                    print "Scanning module",modulekey,"..."
                    for regkey,reg in type(module).__dict__.items():
                        if isinstance(reg,Register):
                            print "Scanning register",regkey,"..."
                            f = self.generatetest(module,modulekey,reg,regkey)

    def generatetest(self, module, modulekey, reg, regkey):
        def test_function():
            0/0
            print regkey
            return
        self.__dict__["test_"+module+"_"+register+"_"+rkey] = f
        return f

    def test_alibi(self):
        return

