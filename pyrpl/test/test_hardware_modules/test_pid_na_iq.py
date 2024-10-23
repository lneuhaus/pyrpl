import logging
logger = logging.getLogger(name=__name__)
from pyrpl.attributes import *
from pyrpl import CurveDB
from pyrpl.test.test_base import TestPyrpl
from pyrpl.async_utils import sleep


class TestPidNaIq(TestPyrpl):
    def setup(self):
        self.extradelay = 0.6 * 8e-9  # no idea where this comes from
            # shortcut
        self.pyrpl.na = self.pyrpl.networkanalyzer
        self.na = self.pyrpl.networkanalyzer
        # set na loglevel to DEBUG
        self.loglevel = self.na._logger.getEffectiveLevel()
        self.na._logger.setLevel(10)

    def teardown(self):
        self.na.stop()
        # set na loglevel to previous one
        self.na._logger.setLevel(self.loglevel)

    def test_na(self):
        error_threshold = 0.03  # (relative error, dominated by phase error)
        if self.r is None:
            return
        else:
            r = self.r
        extradelay = self.extradelay
        # shortcuts and na configuration
        na = self.pyrpl.na
        for iq in [r.iq0, r.iq1, r.iq2]:
            na._iq = iq
            na.setup(start_freq=3000,
                     stop_freq=10e6,
                     points=101,
                     # I reduced points from 1001 to 101, is it normal that
                     # it was taking ages ? -> no, should not take more than 1
                     # second with rbw=1000
                     rbw=1000,
                     avg_per_point=1,
                     trace_average=1,
                     amplitude=0.1, input=na.iq, output_direct='off',
                     acbandwidth=1000, logscale=True)
            data = na.single()
            f = na.data_x
            theory = np.array(f * 0 + 1.0,
                              dtype=complex)
            # obsolete since na data now comes autocorrected:
            # theory = na.transfer_function(f, extradelay=extradelay)
            relerror = np.abs((data - theory) / theory)
            maxerror = np.max(relerror)
            if maxerror > error_threshold:
                print(maxerror)
                c = CurveDB.create(f, data, name='test_na-failed-data')
                c.add_child(CurveDB.create(f, theory,
                                           name='test_na-failed-theory'))
                c.add_child(CurveDB.create(f, relerror,
                                           name='test_na-failed-relerror'))
                assert False, maxerror


    def test_inputfilter(self):
        """
        tests whether the modeled transfer function of pid module with
        any possible inputfilter (firstorder) corresponds to measured tf
        """
        error_threshold = 0.3 # 0.15 is ok for all but -3 MHz filter
        # testing one pid is enough
        pid = self.pyrpl.rp.pid0
        na = self.pyrpl.na
        na.setup(start_freq=10e3,
                 stop_freq=5e6,
                 # points 101->11, it was taking ages
                 points=11,
                 rbw=1000,
                 avg_per_point=1,
                 trace_average=1,
                 amplitude=0.1,
                 input=pid,
                 output_direct='off',
                 acbandwidth=0,
                 logscale=True,
                 paused=False,
                 differential_mode_enabled=False
                 )

        # setup pid: input is the network analyzer output.
        pid.input = na.iq
        pid.setpoint = 0

        # specify extradelay for theory. 3.6 cycles is empirical, but not
        # far from what expects for NA delay (2 cycles for output,
        # 2 for input)
        extradelay = self.extradelay

        # proportional gain of 1, no inputfilter
        pid.p = 1.0
        pid.i = 0
        pid.d = 0
        pid.ival = 0

        pid.inputfilter  # make sure this has been accessed before next step
        inputfilters = pid.inputfilter_options
        for bw in reversed(inputfilters):
            pid.inputfilter = [bw]
            data = na.single()
            f = na.data_x
            theory = pid.transfer_function(f, extradelay=extradelay)
            relerror = np.abs((data - theory) / theory)
            # get max error for values > -50 dB (otherwise its just NA noise)
            mask = np.asarray(np.abs(theory) > 3e-3, dtype=float)
            maxerror = np.max(relerror*mask)
            if maxerror > error_threshold:
                print(maxerror)
                c = CurveDB.create(f, data, name='test_inputfilter-failed-data')
                c.params["bandwidth"] = pid.inputfilter[0]
                c.save()
                c.add_child(CurveDB.create(f, theory,
                                           name='test_inputfilter-failed-theory'))
                c.add_child(CurveDB.create(f, relerror,
                                           name='test_inputfilter-failed-relerror'))
                assert False, (maxerror, bw)


    def test_pid_na1(self):
        # setup a pid module with a bunch of different settings and measure
        # its transfer function, and compare it to the model.

        error_threshold = 0.03  # (relative error)
        # Let's check the transfer function of the pid module with the
        # integrated NA
        if self.r is None:
            return
        else:
            r = self.r
        plotdata = []

        # shortcuts and na configuration
        na = self.pyrpl.na
        for pid in self.pyrpl.pids.all_modules:
            na.setup(start_freq=1000,
                     stop_freq=1000e3,
                     # points 101->11, it was taking ages
                     points=11,
                     rbw=100,
                     avg_per_point=1,
                     trace_average=1,
                     amplitude=0.1,
                     input=pid,
                     output_direct='off',
                     acbandwidth=0,
                     logscale=True)

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
            data= na.single()
            f = na.data_x
            plotdata.append((f, data, 'p=1'))
            theory = pid.transfer_function(f, extradelay=extradelay)
            relerror = np.abs((data - theory) / theory)
            maxerror = np.max(relerror)
            if maxerror > error_threshold:
                print(maxerror)
                c = CurveDB.create(f, data, name='test_na_pid-failed-data')
                c.add_child(CurveDB.create(f, theory,
                                           name='test_na_pid-failed-theory'))
                c.add_child(CurveDB.create(f, relerror,
                                           name='test_na_pid-failed-relerror'))
                assert False, maxerror

    def test_pid_na2(self):
        # setup a pid module with a bunch of different settings and measure
        # its transfer function, and compare it to the model.

        error_threshold = 0.04  # (relative error)
        # Let's check the transfer function of the pid module with the integrated NA
        plotdata = []

        # shortcuts and na configuration
        na = self.pyrpl.na
        for pid in self.pyrpl.pids.all_modules:
            na.setup(start_freq=1000,
                     stop_freq=1000e3,
                     # 101 points, 1 av->11 points, 7 av (taking ages)
                     points=11,
                     rbw=100,
                     avg_per_point=1,
                     trace_average=1,
                     amplitude=0.1, input=pid, output_direct='off',
                     acbandwidth=0, logscale=True)

            # setup pid: input is the network analyzer output.
            pid.input = na.iq
            pid.setpoint = 0

            # specify extradelay for theory. 3.6 cycles is empirical, but not
            # far from what one expects for NA delay (2 cycles for output,
            # 2 for input)
            extradelay = self.extradelay

            # proportional gain of 0.01, integral = 1 kHz
            pid.p = 0.025
            pid.i = 250
            pid.d = 0
            pid.ival = 0
            pid.inputfilter = 0
            data = na.single()
            f = na.data_x
            plotdata.append((f, data, 'p=%.1e, i=%.1e' % (pid.p, pid.i)))
            theory = pid.transfer_function(f, extradelay=extradelay)
            relerror = np.abs((data - theory) / theory)
            maxerror = np.max(relerror)
            if maxerror > error_threshold:
                print(maxerror)
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
            assert abs(pid.ival) <= 1.0, pid.ival

    def test_pid_na3(self):
        # setup a pid module with a bunch of different settings and measure
        # its transfer function, and compare it to the model.

        error_threshold = 0.1  # (relative error)
        # Let's check the transfer function of the pid module with the
        # integrated NA
        if self.r is None:
            return
        else:
            r = self.r
        plotdata = []

        # shortcuts and na configuration
        na = self.pyrpl.na
        for pid in self.pyrpl.pids.all_modules:
            na.setup(start_freq=1000,
                     stop_freq=1000e3,
                     points=11,
                     rbw=100,
                     avg_per_point=10,
                     trace_average=1,
                     amplitude=0.1, input=pid, output_direct='off',
                     acbandwidth=0, logscale=True)

            # setup pid: input is the network analyzer output.
            pid.input = na.iq
            pid.setpoint = 0

            # specify extradelay for theory. 3.6 cycles is empirical, but not
            # far from what one expects for NA delay (2 cycles for output,
            # 2 for input)
            extradelay = self.extradelay

            # proportional gain of 10, inputfilter: 2kHz high-pass, 10 kHz
            # Lowpass, 50kHz lowpass
            pid.p = 10
            pid.i = 0
            pid.d = 0
            pid.ival = 0
            pid.inputfilter = [-5e3, -10e3, 150e3, 300e3]
            print("Actual inputfilter after rounding: ", pid.inputfilter)
            data = na.single()
            f = na.data_x
            plotdata.append((f, data, 'p=10 + filter'))
            theory = pid.transfer_function(f, extradelay=extradelay)
            relerror = np.abs((data - theory) / theory)
            maxerror = np.max(relerror)
            if maxerror > error_threshold:
                print(maxerror)
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
        # Let's check the transfer function of the pid module with the
        # integrated NA
        if self.r is None:
            return
        else:
            r = self.r
        plotdata = []

        # shortcut for na and bpf (bandpass filter)
        na = self.pyrpl.networkanalyzer

        for bpf in [r.iq0, r.iq1]:
            plotdata = []
            # setup na for measurement
            na.setup(start_freq=300e3,
                     stop_freq=700e3,
                     points=51,
                     rbw=1000,
                     avg_per_point=3,
                     trace_average=1,
                     acbandwidth=0,
                     amplitude=0.2,
                     input=bpf,
                     output_direct='off',
                     logscale=False)
            # setup bandpass
            bpf.setup(frequency=500e3,  # center frequency
                      bandwidth=5000,  # Q=100.0,  # the filter quality factor # sorry, I am dropping this...
                      acbandwidth=500,  # ac filter to remove pot. input offsets
                      phase=0,  # nominal phase at center frequency (
                      # propagation phase lags not accounted for)
                      gain=1.0,  # peak gain = +0 dB
                      output_direct='off',
                      output_signal='output_direct',
                      input=na.iq)  # plug filter input to na output...

            for phase in [-45, 0, 45, 90]:
                bpf.phase = phase
                # take transfer function
                data = na.single()
                f = na.data_x
                theory = bpf.transfer_function(f, extradelay=extradelay)
                abserror = np.abs(data - theory)
                maxerror = np.max(abserror)
                # relerror = np.abs((data - theory) / theory)
                # maxerror = np.max(relerror)
                if maxerror > error_threshold:
                    print(maxerror)
                    c = CurveDB.create(f, data, name='test_iq_na-failed-data')
                    c.add_child(CurveDB.create(f, theory,
                                               name='test_iq_na-failed-theory'))
                    c.add_child(CurveDB.create(f, abserror,
                                               name='test_iq_na-failed-relerror'))
                    # c.add_child(CurveDB.create(f,relerror,name='test_iq_na-failed-abserror'))
                    assert False, (maxerror, phase, bpf.name)

    def test_diff_pid(self):
        """
        tests the differential pid feature of pid0 and pid1
        """
        rp = self.pyrpl.rp
        pid0, pid1, pid2 = rp.pid0, rp.pid1, rp.pid2
        for pid in [pid0, pid1, pid2]:
            # we start with all gains off and ival reset, so the output should be 0
            pid.setup(
                input='pid2',
                output_direct='off',
                setpoint=-0.25,
                p=0,
                i=0,
                inputfilter=0,
                max_voltage=1,
                min_voltage=-1,
                pause_gains='off',
                paused=False,
                differential_mode_enabled=False,
                )
            pid.ival = 0
            assert pid.current_output_signal == 0.0, pid.current_output_signal
        diff_module = dict(pid0=pid1, pid1=pid0)
        for pid in [pid0, pid1]:
            diffpid = diff_module[pid.name]
            # test normal working mode
            pid.p=30  # large p-gain should cause saturation
            assert pid.current_output_signal >= pid.max_voltage, (pid.current_output_signal, pid.max_voltage, pid.current_output_signal-pid.max_voltage)
            # enable differential mode, input to both pid0 and pid1 is the same, so output should be zero
            pid.differential_mode_enabled=True
            assert pid.current_output_signal == 0.0, pid.current_output_signal
            # this should not change even if input signal is changed
            pid2.ival = 1
            assert pid.current_output_signal == 0.0, pid.current_output_signal
            # this should not change even if input signal is changed
            pid2.ival = -0.1
            assert pid.current_output_signal == 0.0, pid.current_output_signal
            # but if the input to diffpid is disabled, we should recover normal pid
            pid.p = 3  # smaller p-gain to avoid saturation
            diffpid.input='off'
            assert abs(pid.current_output_signal-(-0.3))<1e-4, (pid.name, pid.current_output_signal)
            pid.differential_mode_enabled = False
            assert abs(pid.current_output_signal-(0.45))<5e-2, (pid.name, pid.current_output_signal)
            # reset initial values
            for apid in [pid0, pid1, pid2]:
                # we start with all gains off and ival reset, so the output should be 0
                apid.setup(
                    input='pid2',
                    output_direct='off',
                    setpoint=-0.25,
                    p=0,
                    i=0,
                    inputfilter=0,
                    max_voltage=1,
                    min_voltage=-1,
                    pause_gains='off',
                    paused=False,
                    differential_mode_enabled=False,
                )
                apid.ival = 0
            assert apid.current_output_signal == 0.0, apid.current_output_signal

    def test_pid_paused(self):
        """
        tests the sync feature of different pid modules
        """
        rp = self.pyrpl.rp
        pids = [rp.pid0, rp.pid1, rp.pid2]
        for pid in pids:
            # we start with all gains off and ival reset, so the output should be 0
            pid.setup(
                input='off',
                output_direct='off',
                setpoint=-1,
                p=0,
                i=0,
                inputfilter=0,
                max_voltage=1,
                min_voltage=-1,
                pause_gains='off'
                )
            pid.ival = 0
            assert pid.current_output_signal == 0.0, pid.current_output_signal
            # test p settings
            pid.p=10000000  # large p-gain should cause saturation
            # now pause the p-gain and assert that output is zero
            pid.pause_gains ='p'
            pid.paused = True
            assert pid.current_output_signal == 0.0, pid.current_output_signal
            # un-pause it and verify
            pid.paused = False
            assert pid.current_output_signal >= pid.max_voltage, (pid.current_output_signal, pid.max_voltage, pid.current_output_signal-pid.max_voltage)
            # test integrator part - first let integrator saturate
            pid.i = 10000000
            pid.p = 0
            assert pid.current_output_signal >= pid.max_voltage, pid.current_output_signal
            # now pause the i-gain and assert that output is unchanged
            pid.pause_gains = 'i'
            assert pid.current_output_signal >= pid.max_voltage, pid.current_output_signal
            # assert that ival can be set in presence of large gains
            pid.paused = True
            pid.ival = 0.1
            assert (pid.ival - pid.current_output_signal) <= 0.0001, (pid.current_output_signal, pid.ival)
            assert (pid.ival - 0.1) <= 0.0001, (pid.current_output_signal, pid.ival)
            pid.pause_gains = 'off'
            assert pid.current_output_signal >= pid.max_voltage, pid.current_output_signal
            # un-pause for later
            pid.paused = False

    def test_iq_sync(self):
        """
        tests the sync feature of different iq modules
        """
        rp = self.pyrpl.rp
        iqs = [rp.iq0, rp.iq1, rp.iq2]
        for iq in iqs:
            iq.setup(input='iq0',
                 frequency=47e6,
                 acbandwidth=1e5,
                 output_signal='output_direct',
                 gain=0,
                 amplitude=0.5,
                 phase=0,
                 output_direct='off')
            iq._na_averages=1e6
        # first measure in desync mode
        for iq in iqs:
            f = iq.frequency
            iq.frequency = 0 # this step is enough to de-sync iqs
            iq.frequency = f
        sleep(1e6/iq.frequency)
        angles = [np.angle(iq._nadata, deg=True) for iq in iqs]
        desyncdiff = (max(angles)-min(angles))
        assert desyncdiff > 0.01, "iq modules not desynchronized, desyncdiff = %f < 0.01! Angles: %s" % (desyncdiff, angles)
        # synchronize
        rp.iq0.synchronize_iqs()
        # now measure in synced mode
        for iq in iqs:
            iq.frequency = iq.frequency
        sleep(1e6/iq.frequency)
        angles = [np.angle(iq._nadata, deg=True) for iq in iqs]
        syncdiff = (max(angles)-min(angles))
        print(desyncdiff, syncdiff)
        assert syncdiff < 0.01, "synchronization of iq modules not working, syncdiff = %f > 0.01! Angles: %s"%(syncdiff, angles)
