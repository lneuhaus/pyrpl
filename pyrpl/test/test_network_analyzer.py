import logging
import os

logger = logging.getLogger(name=__name__)

from pyrpl import RedPitaya

from pyrpl.software_modules.network_analyzer import NetworkAnalyzer

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

