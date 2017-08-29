import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from time import sleep
from qtpy import QtCore, QtWidgets
from pyrpl.test.test_base import TestPyrpl


class TestScope(TestPyrpl):
    def setup(self):
        self.asg = self.pyrpl.asgs.pop("trigtest")
        self.t = self.pyrpl.rp.trig

    def teardown(self):
        self.pyrpl.asgs.free(self.asg)

    def test_trigger(self):
        self.asg = self.pyrpl.rp.asg0
        # asg off, confirm trigger remains armed
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
        # asg on, confirm trigger works
        self.asg.setup(frequency=10000.0,
                       amplitude=0.4,
                       offset=0.5,
                       waveform='sin',
                       output_direct='off',
                       trigger_source='immediately')
        assert self.t.armed == False
        # confirm that trigger outputs the right phase
        asg0phase = self.t.output_signal_to_phase(self.pyrpl.rp.sampler.trig)
        assert abs(asg0phase)<=1.0, asg0phase
        # confirm that trigger outputs right phase for neg edge as well
        self.t.trigger_source='neg_edge'
        self.t.armed=True
        asg0phase = self.t.output_signal_to_phase(self.pyrpl.rp.sampler.trig)
        assert abs(asg0phase-180.0)<=1.0, asg0phase
        # test auto_rearm
        self.asg.frequency = 10e6 # do this at high frequency
        self.t.auto_rearm = True
        #assert self.t.armed == False  # even auto_rearm must be switched on
        self.t.armed = True
        # trigger should be armed most of the time (except for the cycle
        # after triggering)
        armed = 0
        for i in range(100):
            if self.t.armed:
                armed += 1
        assert armed >= 99, armed
        # trigger should stay low when autorearm is off
        self.t.auto_rearm = False
        assert self.t.armed == False