import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from time import sleep
from PyQt4 import QtCore, QtGui
from ..test_base import TestPyrpl
APP = QtGui.QApplication.instance()


class TestScope(TestPyrpl):
    def setup(self):
        self.asg = self.pyrpl.asgs.pop("trigtest")
        self.t = self.pyrpl.rp.trig

    def teardown(self):
        self.pyrpl.asgs.free(self.asg)

    def test_trigger(self):
        self.asg = self.pyrpl.rp.asg0
        self.asg.setup(amplitude=0,
                       offset=0.5,
                       waveform='sin',
                       output_direct='off')
        self.t.setup(input=self.asg,
                     output_direct='off',
                     threshold=self.asg.offset,
                     hysteresis=1e-3,
                     armed=True,
                     auto_rearm=False,
                     trigger_source='pos_edge',
                     output_signal='asg0_phase')
        assert self.t.armed == True
        self.asg.setup(frequency=10000.0,
                       amplitude=0.4,
                       offset=0.5,
                       waveform='sin',
                       output_direct='off')
        assert self.t.armed == False
        asg0phase = self.t.output_signal_to_phase(self.pyrpl.rp.sampler.trig)
        assert abs(asg0phase)<=1.0, asg0phase
        self.t.trigger_source='neg_edge'
        self.t.armed=True
        asg0phase = self.t.output_signal_to_phase(self.pyrpl.rp.sampler.trig)
        assert abs(asg0phase-180.0)<=1.0, asg0phase
