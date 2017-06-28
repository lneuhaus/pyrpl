import logging
logger = logging.getLogger(name=__name__)
import numpy as np
from time import sleep
from PyQt4 import QtCore, QtGui
from .test_base import TestPyrpl

APP = QtGui.QApplication.instance()

class TestClass(TestPyrpl):

    def test_specan_stopped_at_startup(self):
        """
        This was so hard to detect, I am making a unit test
        """
        # this test is not efficient as nothing guarantees that it will be the first test that is executed
        assert(self.pyrpl.spectrumanalyzer.running_state=='stopped')

    def test_no_write_in_config(self):
        """
        Make sure the spec an isn't continuously writing to config file,
        even in running mode.
        :return:
        """
        self.pyrpl.spectrumanalyzer.setup_attributes = dict(span=1e5,
                                            input="out1",
                                            running_state='running_continuous')
        for i in range(25):
            sleep(0.01)
            APP.processEvents()
        old = self.pyrpl.c._save_counter
        for i in range(10):
            sleep(0.01)
            APP.processEvents()
        new = self.pyrpl.c._save_counter
        self.pyrpl.spectrumanalyzer.stop()
        assert (old == new), (old, new)

    def test_flatness_baseband(self):
        for span in [5e4, 1e5, 5e5, 1e6, 2e6]:
            print("Testing flatness for span %f..."%span)
            sa = self.pyrpl.spectrumanalyzer
            sa.setup(baseband=True,
                      center=0,
                      window='flattop',
                      span=span,
                      input1_baseband="asg0",
                      running_state='stopped')
            asg = self.pyrpl.rp.asg0
            asg.setup(frequency=1e5,
                      amplitude=1.0,
                      trigger_source='immediately',
                      offset=0,
                      waveform='sin')
            freqs = np.linspace(sa.rbw*3, sa.span/2-sa.rbw*3)
            points = []
            for freq in freqs:
                print("Testing flatness for span %f and frequency freq "
                      "%f..." % (span, freq))
                asg.frequency = freq
                curve = self.pyrpl.spectrumanalyzer.curve()[0]
                assert(abs(sa.frequencies[np.argmax(curve)] - freq) < sa.rbw), \
                    (sa.frequencies[np.argmax(curve)], freq, sa.rbw)
                points.append(max(curve))
                assert abs(max(curve) - asg.amplitude**2) < 0.01, max(curve)
                assert abs(max(sa.data_to_unit(curve,
                                               "Vrms^2/Hz",
                                                sa.rbw)*sa.rbw) -
                           (asg.amplitude**2)/2)<0.01, max(curve)

    def test_flatness_iqmode(self):
        return # to be tested in next release
        for span in [5e4, 1e5, 5e5, 1e6, 2e6]:
            self.pyrpl.spectrumanalyzer.setup(baseband=False,
                                              center=1e5,
                                              span=span,
                                              input="asg0",
                                              running_state='stopped')
            asg = self.pyrpl.rp.asg0
            asg.setup(frequency=1e5,
                      amplitude=1,
                      trigger_source='immediately',
                      offset=0,
                      waveform='sin')
            freqs = np.linspace(1e5, 9e5)
            points = []
            for freq in freqs:
                asg.frequency = freq
                curve = self.pyrpl.spectrumanalyzer.curve()
                points.append(max(curve))
                assert abs(max(curve) - 1) < 0.01, max(curve)