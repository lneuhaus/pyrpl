import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from ..async_utils import sleep as async_sleep
from .test_base import TestPyrpl


class TestLockbox(TestPyrpl):
    source_config_file = "nosetests_source_lockbox.yml"

    def setup(self):
        self.lockbox = self.pyrpl.lockbox

    def test_create_stage(self):
        old_len = len(self.lockbox.sequence)
        widget = self.lockbox._create_widget()
        self.lockbox.sequence.append({'gain_factor': 2.0})
        assert len(self.lockbox.sequence) == old_len + 1

        # wait for stage creation signal to impact the GUI (async sleep to
        # let the EventLoop handle the notifiction from sequence...)
        async_sleep(0.1)
        assert len(widget.sequence_widget.stage_widgets) == old_len + 1
        self.lockbox.sequence.append({'gain_factor':3.0})

        assert self.lockbox.sequence[-1].gain_factor == 3.0
        assert self.lockbox.sequence[-2].name == old_len

        assert self.lockbox.sequence[old_len].gain_factor == 2.0
        self.lockbox.sequence.pop()

        assert len(self.lockbox.sequence) == old_len + 1
        assert self.lockbox.sequence.pop()['gain_factor']==2.0

    def test_real_lock(self):
        delay = 0.01
        pid = self.pyrpl.rp.pid1
        pid.i = 0.1
        pid.p = 0.1
        self.lockbox.classname = 'Linear'
        self.lockbox.sequence = []
        self.lockbox.sequence.append({})
        self.lockbox.outputs.output1.p = 0
        self.lockbox.outputs.output1.i = -10.

    def test_lock(self):
        pass
        # make a config file for a lock including iir that locks onto itself
        # then load another state and lock a pid with existing integrator
        # test lock with islocked, test autorelock, test unit issues,
        # test change of lockbox with incompatible settings, test saving of
        # relevant lock parameters.
