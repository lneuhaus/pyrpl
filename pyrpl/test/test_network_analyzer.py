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



from pyrpl.network_analyzer import NetworkAnalyzer

class TestClass(object):
    @classmethod
    def setUpAll(self):
        # these tests wont succeed without the hardware
        if os.environ['REDPITAYA_HOSTNAME'] == 'unavailable':
            self.r = None
        else:
            self.r = RedPitaya()

    def test_na(self):
        if self.r is None:
            return
        na = NetworkAnalyzer(self.r)
        na.output_direct = "out1"
        na.input = "adc1"
        na.setup(start=1e6, stop=2e6, rbw=1e5)
        x, y, amp = na.curve()
        #Assumes out1 is connected with adc1...
        assert(max(abs(y) - 1)<0.2)

