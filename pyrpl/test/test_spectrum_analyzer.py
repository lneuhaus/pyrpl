import logging
logger = logging.getLogger(name=__name__)
from .test_base import TestPyrpl

from time import sleep
from PyQt4 import QtCore, QtGui

APP = QtGui.QApplication.instance()

class TestClass(TestPyrpl):

    def test_specan_stopped_at_startup(self):
        """
        This was so hard to detect, I am making a unit test
        """
        assert(self.pyrpl.spectrum_analyzer.running_continuous==False)

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

    def test_no_write_in_config(self):
        """
        Make sure the spec an isn't continuously writing to config file,
        even in running mode.
        :return:
        """

        self.pyrpl.spectrum_analyzer.setup(center=2e5,
                      span=1e5,
                      rbw=100000,
                      input="out1",
                      running_continuous=True)
        for i in range(15):
            sleep(0.01)
            APP.processEvents()
        old = self.pyrpl.c._save_counter
        for i in range(10):
            sleep(0.01)
            APP.processEvents()
        new = self.pyrpl.c._save_counter
        self.pyrpl.spectrum_analyzer.stop()
        assert (old == new), (old, new)
