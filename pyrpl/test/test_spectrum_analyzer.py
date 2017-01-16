import logging
import os

logger = logging.getLogger(name=__name__)

from pyrpl import RedPitaya, Pyrpl

from pyrpl.software_modules.spectrum_analyzer import SpectrumAnalyzer

class TestClass(object):
    @classmethod
    def setUpAll(self):
        # these tests wont succeed without the hardware
        if os.environ['REDPITAYA_HOSTNAME'] == 'unavailable':
            self.pyrpl = None
        else:
            self.pyrpl = Pyrpl(config="tests_temp", source="tests_source")


    def test_spec_an(self):
        if self.pyrpl is None:
            return
        sa = self.pyrpl.spectrum_analyzer
        sa.input = "asg1"
        self.pyrpl.rp.asg1.frequency = 1e6
        self.pyrpl.rp.asg1.trigger_source = 'immediately'

        sa.setup(center=1e6, span=1e5)
        curve = sa.curve()
        #Assumes out1 is connected with adc1...
        assert(curve.argmax()==len(curve)/2), curve.argmax()
