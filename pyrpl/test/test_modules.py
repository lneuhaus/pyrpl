from nose.tools import with_setup
from unittest import TestCase
import os
import numpy as np
import logging
logger = logging.getLogger(name=__name__)

from pyrpl import RedPitaya
from pyrpl.redpitaya_modules import *
from pyrpl.registers import *
from pyrpl.bijection import Bijection

import time

from pyrpl import CurveDB


class TestClass(object):
    
    @classmethod
    def setUpAll(self):
        # these tests wont succeed without the hardware
        if os.environ['REDPITAYA_HOSTNAME'] == 'unavailable':
            self.r = None
        else:
            self.r = RedPitaya()
        self.extradelay = 0.6*8e-9 # no idea where this comes from

    def test_asg(self):
        if self.r is None:
            return
        for asg in [self.r.asg1,self.r.asg2]:
            asg.setup(frequency=12345.)
            expect = 1./8191*np.round(8191.*np.sin(
                                np.linspace(
                                    0, 
                                    2*np.pi, 
                                    asg.data_length, 
                                    endpoint=False)))
            diff = np.max(np.abs(expect-asg.data))
            if diff > 2**-12:
                assert False, 'diff = '+str(diff)

    def test_asg_to_scope(self):
        if self.r is None:
            return
        for asg in [self.r.asg1, self.r.asg2]:
            self.r.scope.duration = 0.1
            asg.setup(waveform='ramp',
                      frequency=1./self.r.scope.duration,
                      trigger_source='immediately',
                      amplitude=1,
                      offset=0)
            
            expect = np.linspace(-1.0,3.0, asg.data_length, endpoint=False)
            expect[asg.data_length//2:] = -1*expect[:asg.data_length//2]
            expect*=-1
            self.r.scope.input1 = Bijection(self.r.scope._ch1._inputs).inverse[asg._dsp._number]
            self.r.scope.input2 = self.r.scope.input1
            #asg.trig()
            self.r.scope.setup(trigger_source=self.r.scope.input1) # the asg trigger
            measured = self.r.scope.curve(ch=1, timeout=4)
            diff = np.max(np.abs(measured-expect))
            if diff > 0.001:
                c = CurveDB.create(expect, measured,
                                name='failed test asg_to_scope: '
                                     'measured trace vs expected one')
                assert False, 'diff = '+str(diff)

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
        # next line should wor for any value > duration/2
        self.r.scope.trigger_delay = self.r.scope.duration  # /2
        self.r.scope.setup()
        time.sleep(0.01) # increased from 0.01 because of
        # systematic failure on remote server
        assert(self.r.scope.pretrig_ok)
        
    def test_amspwm(self):
        threshold = 0.0005
        if self.r is None:
            return
        asg = self.r.asg1
        asg.setup(amplitude=0, offset=0)
        for pwm in [self.r.pwm0, self.r.pwm1]:
            pwm.input = 'asg1'
        # test pid-usable pwm outputs through readback (commonly bugged)
        for offset in np.linspace(-1.5, 1.5, 20):
            asg.offset = offset
            if offset > 1.0:
                offset = 1.0
            elif offset < -1.0:
                offset = -1.0
            assert abs(self.r.ams.dac0-offset) > threshold, \
                str(self.r.ams.dac0) + " vs " + str(offset)
            assert abs(self.r.ams.dac1 - offset) > threshold, \
                str(self.r.ams.dac1) + " vs " + str(offset)
        # test direct write access
        for offset in np.linspace(0, 1.8):
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
        assert(time.time() - tic<0.1)

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
        assert(self.r.scope.times[self.r.scope.data_length//2]==0.01)

        self.r.scope.trigger_source = "immediately"
        self.r.scope.duration = 0.001
        self.r.scope.trigger_delay = 0.01
        assert (self.r.scope.times[0] == 0)

        self.r.scope.trigger_source = "asg1"
        self.r.scope.duration = 0.001
        self.r.scope.trigger_delay = 0.01
        assert (self.r.scope.times[self.r.scope.data_length//2]==0.01)

    def test_scope_duration_autosetting(self):
        # tests if trigger delay doesnt change when duration is altered
        if self.r is None:
            return
        self.r.scope.setup(duration=0.001, trigger_source='asg1',
                           trigger_delay= 0.1)
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
        assert abs(centertime-0.1)<1e-5, centertime

    def test_na(self):
        error_threshold = 0.02  # (relative error, dominated by phase error)
        if self.r is None:
            return
        else:
            r = self.r
        extradelay = self.extradelay
        # shortcuts and na configuration
        na = r.na
        for iq in [r.iq0, r.iq1, r.iq2]:
            na._iq = iq
            na.setup(start=3000, stop=10e6, points=1001, rbw=1000, avg=1,
                     amplitude=0.1, input=na.iq, output_direct='off',
                     acbandwidth=1000, logscale=True)
            f, data, a = na.curve()
            theory = np.array(f*0+1.0,
                              dtype=np.complex)
            # obsolete since na data now comes autocorrected
            # theory = na.transfer_function(f, extradelay=extradelay)
            relerror = np.abs((data - theory)/theory)
            maxerror = np.max(relerror)
            if maxerror > error_threshold:
                c = CurveDB.create(f, data, name='test_na-failed-data')
                c.add_child(CurveDB.create(f, theory,
                                           name='test_na-failed-theory'))
                c.add_child(CurveDB.create(f, relerror,
                                           name='test_na-failed-relerror'))
                assert False, maxerror

    def test_pid_na1(self):
        # setup a pid module with a bunch of different settings and measure
        # its transfer function, and compare it to the model.

        error_threshold = 0.02  # (relative error)
        # Let's check the transfer function of the pid module with the integrated NA
        if self.r is None:
            return
        else:
            r = self.r
        plotdata = []

        # shortcuts and na configuration
        na = r.na
        for pid in r.pids:
            na.setup(start=1000, stop=1000e3, points=101, rbw=100, avg=1,
                     amplitude=0.1, input=pid, output_direct='off',
                     acbandwidth=0, logscale=True)

            # setup pid: input is the network analyzer output.
            pid.input = na.iq
            pid.setpoint = 0

            # specify extradelay for theory. 3.6 cycles is empirical, but not
            # far from what expects for NA delay (2 cycles for output, 2 for input)
            extradelay = self.extradelay

            # proportional gain of 1, no inputfilter
            pid.p = 1.0
            pid.i = 0
            pid.d = 0
            pid.ival = 0
            pid.inputfilter = 0
            f, data, amplitudes = na.curve()
            plotdata.append((f, data, 'p=1'))
            theory = pid.transfer_function(f, extradelay=extradelay)
            relerror = np.abs((data - theory) / theory)
            maxerror = np.max(relerror)
            if maxerror > error_threshold:
                c = CurveDB.create(f, data, name='test_na_pid-failed-data')
                c.add_child(CurveDB.create(f, theory,
                                           name='test_na_pid-failed-theory'))
                c.add_child(CurveDB.create(f, relerror,
                                           name='test_na_pid-failed-relerror'))
                assert False, maxerror

    def test_pid_na2(self):
        # setup a pid module with a bunch of different settings and measure
        # its transfer function, and compare it to the model.

        error_threshold = 0.02  # (relative error)
        # Let's check the transfer function of the pid module with the integrated NA
        if self.r is None:
            return
        else:
            r = self.r
        plotdata = []

        # shortcuts and na configuration
        na = r.na
        for pid in r.pids:
            na.setup(start=1000, stop=1000e3, points=101, rbw=100,
                     avg=1,
                     amplitude=0.1, input=pid, output_direct='off',
                     acbandwidth=0, logscale=True)

            # setup pid: input is the network analyzer output.
            pid.input = na.iq
            pid.setpoint = 0

            # specify extradelay for theory. 3.6 cycles is empirical, but not
            # far from what expects for NA delay (2 cycles for output, 2 for input)
            extradelay = self.extradelay

            # proportional gain of 0.01, integral = 1 kHz
            pid.p = 0.05
            pid.i = 500
            pid.d = 0
            pid.ival = 0
            pid.inputfilter = 0
            f, data, amplitudes = na.curve()
            plotdata.append((f, data, 'p=1e-1, i=1e3'))
            theory = pid.transfer_function(f, extradelay=extradelay)
            relerror = np.abs((data - theory) / theory)
            maxerror = np.max(relerror)
            if maxerror > error_threshold:
                c = CurveDB.create(f, data, name='test_na_pid-failed-data')
                c.add_child(CurveDB.create(f, theory,
                                           name='test_na_pid-failed-theory'))
                c.add_child(CurveDB.create(f, relerror,
                                           name='test_na_pid-failed-relerror'))
                assert False, maxerror
            # check that no saturation has occured
            print ("Integral value after measurement: ", pid.ival)
            if abs(pid.ival) >= 1.0:
                print("Saturation has occured. Data not reliable.")
            assert abs(pid.ival)<=1.0, pid.ival

    def test_pid_na3(self):
        # setup a pid module with a bunch of different settings and measure
        # its transfer function, and compare it to the model.

        error_threshold = 0.1  # (relative error)
        # Let's check the transfer function of the pid module with the integrated NA
        if self.r is None:
            return
        else:
            r = self.r
        plotdata = []

        # shortcuts and na configuration
        na = r.na
        for pid in r.pids:
            na.setup(start=1000, stop=1000e3, points=101, rbw=100,
                     avg=1,
                     amplitude=0.1, input=pid, output_direct='off',
                     acbandwidth=0, logscale=True)

            # setup pid: input is the network analyzer output.
            pid.input = na.iq
            pid.setpoint = 0

            # specify extradelay for theory. 3.6 cycles is empirical, but not
            # far from what expects for NA delay (2 cycles for output, 2 for input)
            extradelay = self.extradelay

            # proportional gain of 10, inputfilter: 2kHz high-pass, 10 kHz
            # Lowpass, 50kHz lowpass
            pid.p = 10
            pid.i = 0
            pid.d = 0
            pid.ival = 0
            pid.inputfilter = [-5e3, -10e3, 150e3, 300e3]
            print("Actual inputfilter after rounding: ", pid.inputfilter)
            f, data, amplitudes = na.curve()
            plotdata.append((f, data, 'p=10 + filter'))
            theory = pid.transfer_function(f, extradelay=extradelay)
            relerror = np.abs((data - theory) / theory)
            maxerror = np.max(relerror)
            if maxerror > error_threshold:
                c = CurveDB.create(f, data, name='test_na_pid-failed-data')
                c.add_child(CurveDB.create(f, theory,
                                           name='test_na_pid-failed-theory'))
                c.add_child(CurveDB.create(f, relerror,
                                           name='test_na_pid-failed-relerror'))
                assert False, maxerror
            # reset
            pid.setpoint = 0
            pid.p = 0
            pid.i = 0
            pid.d = 0
            pid.ival = 0
            pid.inputfilter = 0

    def test_iq_na(self):
        # sets up a bandpass filter with iq modules and tests its transfer
        # function w.r.t. to the predicted one
        extradelay = 0
        error_threshold = 0.07
        # Let's check the transfer function of the pid module with the integrated NA
        if self.r is None:
            return
        else:
            r = self.r
        plotdata = []

        # shortcut for na and bpf (bandpass filter)
        na = r.na

        for bpf in [r.iq0, r.iq2]:
            plotdata = []
            # setup na for measurement
            na.setup(start=300e3, stop=700e3, points=201, rbw=1000, avg=3,
                     acbandwidth=0, amplitude=0.2, input=bpf,
                     output_direct='off', logscale=False)
            # setup bandpass
            bpf.setup(frequency=500e3, #center frequency
                      Q=100.0,  # the filter quality factor
                      acbandwidth=500, # ac filter to remove pot. input offsets
                      phase=0,  # nominal phase at center frequency (
                      # propagation phase lags not accounted for)
                      gain=1.0,  # peak gain = +0 dB
                      output_direct='off',
                      output_signal='output_direct',
                      input='iq1')

            for phase in [-45, 0, 45, 90]:
                bpf.phase = phase
                # take transfer function
                f, data, ampl = na.curve()
                theory = bpf.transfer_function(f, extradelay=extradelay)
                abserror = np.abs(data - theory)
                maxerror = np.max(abserror)
                #relerror = np.abs((data - theory) / theory)
                #maxerror = np.max(relerror)
                if maxerror > error_threshold:
                    c = CurveDB.create(f, data, name='test_iq_na-failed-data')
                    c.add_child(CurveDB.create(f, theory,
                                               name='test_iq_na-failed-theory'))
                    c.add_child(CurveDB.create(f, abserror,
                                               name='test_iq_na-failed-relerror'))
                    #c.add_child(CurveDB.create(f,relerror,name='test_iq_na-failed-abserror'))
                    assert False, (maxerror, phase)
