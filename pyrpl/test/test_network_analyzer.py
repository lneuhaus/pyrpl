import logging
import os

logger = logging.getLogger(name=__name__)

from pyrpl import Pyrpl

from pyrpl.software_modules.network_analyzer import NetworkAnalyzer

class TestClass(object):
    @classmethod
    def setUpAll(self):
        # these tests wont succeed without the hardware
        if os.environ['REDPITAYA_HOSTNAME'] == 'unavailable':
            self.pyrpl = None
        else:
            filename = os.path.join(os.path.split(os.path.dirname(__file__))[0], 'config', 'tests_temp.yml')
            if os.path.exists(filename):
                os.remove(filename)
            self.pyrpl = Pyrpl(config="tests_temp", source="tests_source")
            self.r = self.pyrpl.rp

    def test_na(self):
        if self.pyrpl is None:
            return
        na = self.pyrpl.na
        na.output_direct = "out1"
        na.input = "adc1"
        na.setup(start=1e6, stop=2e6, rbw=1e5)
        x, y, amp = na.curve()
        #Assumes out1 is connected with adc1...
        assert(max(abs(y) - 1)<0.2)

