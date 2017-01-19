import logging
logger = logging.getLogger(name=__name__)
from .test_base import PyrplTestCase


class TestClass(PyrplTestCase):
    def test_spec_an(self):
        # at this point this test is still highly dubious (nothing is tested
        #  for, really)
        if self.pyrpl is None:
            return
        sa = self.pyrpl.spectrum_analyzer
        asg = self.pyrpl.rp.asg1
        asg.frequency = 1e6
        asg.amplitude = 0.1
        asg.waveform = 'cos'
        asg.trigger_source = 'immediately'
        sa.setup(center=1e6, span=1e3, input=asg)
        curve = sa.curve()
        # Assumes out1 is connected with adc1...
        assert(curve.argmax() == len(curve)/2), curve.argmax()
