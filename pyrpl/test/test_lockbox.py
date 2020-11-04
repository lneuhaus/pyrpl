import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from ..async_utils import sleep, sleep_async, ensure_future
from .test_base import TestPyrpl


class TestLockbox(TestPyrpl):
    source_config_file = "nosetests_source_lockbox.yml"

    #def setup(self):
    #    self.lockbox = self.pyrpl.lockbox

    @property
    def lockbox(self):
        return self.pyrpl.lockbox

    def test_create_stage(self):
        old_len = len(self.lockbox.sequence)
        widget = self.lockbox._create_widget()
        self.lockbox.sequence.append({'gain_factor': 2.0})
        assert len(self.lockbox.sequence) == old_len + 1

        # wait for stage creation signal to impact the GUI (async sleep to
        # let the EventLoop handle the notifiction from sequence...)
        sleep(0.1)
        assert len(widget.sequence_widget.stage_widgets) == old_len + 1
        self.lockbox.sequence.append({'gain_factor':3.0})

        assert self.lockbox.sequence[-1].gain_factor == 3.0
        assert self.lockbox.sequence[-2].name == old_len

        assert self.lockbox.sequence[old_len].gain_factor == 2.0
        self.lockbox.sequence.pop()

        assert len(self.lockbox.sequence) == old_len + 1
        assert self.lockbox.sequence.pop()['gain_factor']==2.0

    def test_change_classname(self):
        for classname in ["Linear", "FabryPerot", "Interferometer"]:
            self.pyrpl.lockbox.classname = classname
            assert(self.pyrpl.lockbox.classname == classname)

    def test_real_lock(self):
        self.setup_fake_system()

        self.lockbox.lock()
        assert self.lockbox.is_locked()

    def setup_fake_system(self):
        """
        When frequency modulation will be available on the IQ modules, we could
        simulate a Non-linear system such as a Fabry Perot cavity,
        which ould be really cool... At the moment, we only simulate a linear
        system with a pid.
        :return:
        """
        pid = self.pyrpl.rp.pid1
        self.pyrpl.lockbox.classname = 'Interferometer'
        lockbox = self.pyrpl.lockbox
        pid.i = -1
        pid.p = -1
        pid.input = lockbox.outputs.piezo
        lockbox.inputs.port1.input_signal = pid
        output = lockbox.outputs.values()[0]
        print(output.name)
        output.sweep_frequency = 50
        output.sweep_amplitude = 0.3
        output.sweep_offset = 0.1
        output.sweep_waveform = 'sin'

        lockbox.calibrate_all()

        lockbox.sequence.append({'gain_factor':1.0e6})
        lockbox.sequence[-1].input = 'port1'
        output.desired_unity_gain_frequency = 1e7
        lockbox.sequence[-1].outputs.piezo.lock_on = True
        lockbox.sequence[-1].outputs.piezo.reset_offset = True
        lockbox.sequence[-1].duration = 1 # It takes 1 s to acquire lock

    def test_calibrate(self):
        self.setup_fake_system()
        lockbox = self.pyrpl.lockbox
        self.pyrpl.rp.pid1.i = 0
        self.pyrpl.rp.pid1.p = 1
        self.pyrpl.rp.pid1.ival = 0
        lockbox.calibrate_all()
        cal = lockbox.inputs.port1.calibration_data
        assert abs(cal.mean - 0.1) < 0.01, cal.mean
        assert abs(cal.max - 0.4) < 0.01, cal.max
        assert abs(cal.min - (-0.2)) < 0.01, cal.min
        assert abs(cal.amplitude - (0.3)) < 0.01, cal.amplitude

    def test_sleep_while_locked(self):
        self.setup_fake_system()
        self.lockbox.lock()
        pid = self.pyrpl.rp.pid1
        async def unlock_later(time_s):
            await sleep_async(time_s)
            pid.ival = 1
            pid.p = 0
            pid.i = 0
        res = self.lockbox.sleep_while_locked(1)
        assert res
        ensure_future(unlock_later(0.5))
        res = self.lockbox.sleep_while_locked(10)
        assert not res

    def test_auto_relock(self):
        self.setup_fake_system()
        self.lockbox.auto_lock = True

        # monkey patch a function to make sure lockbox went to first stage
        # again
        def increment(obj):
            obj.first_stage_counter+=1

        self.lockbox.__class__.increment = increment
        self.lockbox.first_stage_counter = 0

        self.lockbox.lock_async()
        assert self.lockbox.classname == 'Interferometer'

        self.lockbox.sequence[0].function_call = "increment"
        pid = self.pyrpl.rp.pid1

        async def unlock_later(time_s):
            await sleep_async(time_s)
            pid.ival = 1
            pid.p = 0
            pid.i = 0
            await sleep_async(time_s)
            pid.p = -1
            pid.i = -1
        sleep(0.5)
        assert self.lockbox.is_locked()
        ensure_future(unlock_later(1))
        sleep(5)
        assert self.lockbox.is_locked()
        assert self.lockbox.first_stage_counter == 2

        # make a config file for a lock including iir that locks onto itself
        # then load another state and lock a pid with existing integrator
        # test lock with islocked, test autorelock, test unit issues,
        # test change of lockbox with incompatible settings, test saving of
        # relevant lock parameters.
