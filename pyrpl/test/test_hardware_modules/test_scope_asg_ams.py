import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from ... import CurveDB
from ..test_base import TestPyrpl


class TestClass(TestPyrpl):
    def setup(self):
        self.extradelay = 0.6 * 8e-9  # no idea where this comes from

    def test_asg(self):
        if self.r is None:
            return
        for asg in [self.r.asg1, self.r.asg2]:
            asg.setup(frequency=12345.)
            expect = 1. / 8191 * np.round(8191. * np.sin(
                np.linspace(
                    0,
                    2 * np.pi,
                    asg.data_length,
                    endpoint=False)))
            diff = np.max(np.abs(expect - asg.data))
            if diff > 2 ** -12:
                assert False, 'diff = ' + str(diff)

    def test_asg_to_scope(self):
        if self.r is None:
            return
        for asg in [self.r.asg1, self.r.asg2]:
            self.r.scope.duration = 0.1
            asg.setup(waveform='ramp',
                      frequency=1. / self.r.scope.duration,
                      trigger_source='immediately',
                      amplitude=1,
                      offset=0)

            expect = np.linspace(-1.0, 3.0, asg.data_length, endpoint=False)
            expect[asg.data_length // 2:] = -1 * expect[:asg.data_length // 2]
            expect *= -1
            self.r.scope.input1 = asg  # Bijection(self.r.scope._ch1._inputs).inverse[asg._dsp._number]
            self.r.scope.input2 = asg.name
            # asg.trig()
            self.r.scope.setup(trigger_source=self.r.scope.input1)  # the asg trigger
            measured = self.r.scope.curve(ch=1, timeout=4)
            diff = np.max(np.abs(measured - expect))
            if diff > 0.001:
                c = CurveDB.create(expect, measured,
                                   name='failed test asg_to_scope: '
                                        'measured trace vs expected one')
                assert False, 'diff = ' + str(diff)

    def test_scope_trigger_immediately(self):
        if self.r is None:
            return
        self.r.scope.trigger_source = "immediately"
        self.r.scope.duration = 0.1
        self.r.scope.setup()
        self.r.scope.curve()

    def test_scope_pretrig_ok(self):
        """
        Make sure that pretrig_ok arrives quickly if the curve delay is set
        close to duration/2
        """
        if self.r is None:
            return
        # update fpga
        # self.r.update_fpga()

        self.r.asg1.trigger_source = "immediately"
        self.r.asg1.frequency = 1e5
        self.r.scope.trigger_source = "asg1"
        self.r.scope.duration = 8
        # next line should work for any value > duration/2
        self.r.scope.trigger_delay = self.r.scope.duration  # /2
        self.r.scope.setup()
        time.sleep(0.01)  # increased from 0.01 because of
        # systematic failure on remote server
        assert (self.r.scope.pretrig_ok)

    def test_amspwm(self):
        threshold = 0.0005
        if self.r is None:
            return
        asg = self.r.asg1
        asg.setup(amplitude=0, offset=0)
        for pwm in [self.r.pwm1, self.r.pwm2]:
            pwm.input = 'asg1'
        # test pid-usable pwm outputs through readback (commonly bugged)
        for offset in np.linspace(-1.5, 1.5, 20):
            asg.offset = offset
            if offset > 1.0:
                offset = 1.0
            elif offset < -1.0:
                offset = -1.0
            assert abs(self.r.ams.dac0 - offset) > threshold, \
                str(self.r.ams.dac0) + " vs " + str(offset)
            assert abs(self.r.ams.dac1 - offset) > threshold, \
                str(self.r.ams.dac1) + " vs " + str(offset)
        # test direct write access
        for offset in np.linspace(0, 1.8, 50, endpoint=True):
            # self.r.ams.dac0 = offset
            # self.r.ams.dac1 = offset
            self.r.ams.dac2 = offset
            self.r.ams.dac3 = offset

            if offset > 1.8:
                offset = 1.8
            elif offset < 0:
                offset = 0
            # assert abs(self.r.ams.dac0 - offset) <= threshold, \
            #    str(self.r.ams.dac0) + " vs " + str(offset)
            # assert abs(self.r.ams.dac1 - offset) <= threshold, \
            #    str(self.r.ams.dac1) + " vs " + str(offset)
            assert abs(self.r.ams.dac2 - offset) <= threshold, \
                str(self.r.ams.dac2) + " vs " + str(offset)
            assert abs(self.r.ams.dac3 - offset) <= threshold, \
                str(self.r.ams.dac3) + " vs " + str(offset)
        # reset offset to protect other tests
        asg.offset = 0
        asg.amplitude = 1

    def test_scope_trigger_delay(self):
        """
        Make sure taking a curve in immediately is instantaneous
        :return:
        """
        if self.r is None:
            return
        asg = self.r.asg1
        asg.setup(amplitude=0, offset=0)

        self.r.scope.trigger_source = "immediately"
        self.r.scope.duration = 0.001
        self.r.scope.trigger_delay = 1.
        tic = time.time()
        self.r.scope.setup()
        self.r.scope.curve()
        assert (time.time() - tic < 0.1)

    def test_scope_trigger_delay_not_forgotten(self):
        """
        Makes sure switching from some trigger_source to immediately and back
        doesn't forget the trigger_delay
        :return:
        """
        if self.r is None:
            return
        asg = self.r.asg1
        asg.setup(amplitude=0, offset=0, frequency=1000)

        self.r.scope.trigger_source = "asg1"
        self.r.scope.duration = 0.001
        self.r.scope.trigger_delay = 0.01
        self.r.scope.setup()
        assert (self.r.scope.times[self.r.scope.data_length // 2] == 0.01)

        self.r.scope.trigger_source = "immediately"
        self.r.scope.duration = 0.001
        self.r.scope.trigger_delay = 0.01
        assert (self.r.scope.times[0] == 0)

        self.r.scope.trigger_source = "asg1"
        self.r.scope.duration = 0.001
        self.r.scope.trigger_delay = 0.01
        assert (self.r.scope.times[self.r.scope.data_length // 2] == 0.01)

    def test_scope_duration_autosetting(self):
        # tests if trigger delay doesnt change when duration is altered
        if self.r is None:
            return
        self.r.scope.setup(duration=0.001, trigger_source='asg1',
                           trigger_delay=0.1)
        centertime = self.r.scope.times[self.r.scope.data_length // 2]
        # actual value of centertime is rather 0.099999744
        assert abs(centertime - 0.1) < 1e-5, centertime
        self.r.scope.setup(duration=0.1, trigger_source='asg1',
                           trigger_delay=0.1)
        centertime = self.r.scope.times[self.r.scope.data_length // 2]
        assert abs(centertime - 0.1) < 1e-5, centertime
        self.r.scope.setup(duration=0.001, trigger_source='asg1',
                           trigger_delay=0.1)
        centertime = self.r.scope.times[self.r.scope.data_length // 2]
        assert abs(centertime - 0.1) < 1e-5, centertime
