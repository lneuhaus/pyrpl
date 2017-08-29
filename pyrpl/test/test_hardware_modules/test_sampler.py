import logging
logger = logging.getLogger(name=__name__)
from pyrpl.test.test_base import TestPyrpl


class TestInput(TestPyrpl):
    def setup(self):
        self.p = self.pyrpl
        self.sampler = self.r.sampler

    def teardown(self):
        pass

    def test_sampler(self):
        with self.pyrpl.asgs.pop('test_sampler') as asg:
            asg.setup(amplitude=0.5,
                      offset = 0.1,
                      frequency=500e3,
                      waveform='sin',
                      output_direct='off',
                      trigger_source='immediately')
            # test sample function
            sample = getattr(self.sampler, asg.name)
            assert sample + 2.0**(-14) >= asg.offset - asg.amplitude, sample
            assert sample <= asg.offset + asg.amplitude, sample
            # test stats function
            mean, std, max, min = self.sampler.stats(asg.name, t=1.0)
            assert min <= mean, (mean, std, max, min)
            assert mean <= max, (mean, std, max, min)
            assert std <= (max-min)/2.0, (mean, std, max, min, (max-min)/2.0)
            assert max <= asg.offset + asg.amplitude, (mean, std, max, min, asg.offset + asg.amplitude)
            # needs a small margin to work properly because of rounding off towards negative values in asg
            assert min + 2.0**(-14) >= asg.offset - asg.amplitude, \
                (mean, std, max, min, min + 2.0**(-14), asg.offset - asg.amplitude)
