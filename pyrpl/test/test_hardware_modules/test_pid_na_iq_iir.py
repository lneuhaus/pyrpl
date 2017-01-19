import logging
logger = logging.getLogger(name=__name__)
from ...attributes import *
from ... import CurveDB
from ..test_base import TestPyrpl


class TestClass(TestPyrpl):
    def setup(self):
        self.extradelay = 0.6 * 8e-9  # no idea where this comes from

    def test_na(self):
        error_threshold = 0.03  # (relative error, dominated by phase error)
        if self.r is None:
            return
        else:
            r = self.r
        extradelay = self.extradelay
        # shortcuts and na configuration
        na = self.pyrpl.na
        for iq in [r.iq1, r.iq2, r.iq3]:
            na._iq = iq
            na.setup(start_freq=3000, stop_freq=10e6, points=101, rbw=1000, avg=1,
                     # I reduced from 1001 to 101, is it normal that
                     # it was taking ages ? -> no, should not take more than 1 second with rbw=1000
                     amplitude=0.1, input=na.iq, output_direct='off',
                     acbandwidth=1000, logscale=True)
            f, data, a = na.curve()
            theory = np.array(f * 0 + 1.0,
                              dtype=np.complex)
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

    def test_pid_na1(self):
        # setup a pid module with a bunch of different settings and measure
        # its transfer function, and compare it to the model.

        error_threshold = 0.03  # (relative error)
        # Let's check the transfer function of the pid module with the integrated NA
        if self.r is None:
            return
        else:
            r = self.r
        plotdata = []

        # shortcuts and na configuration
        na = self.pyrpl.na
        for pid in self.pyrpl.pids.all_modules:
            na.setup(start_freq=1000, stop_freq=1000e3, points=11, rbw=100, avg=1,  # points 101->11, it was taking ages
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

        error_threshold = 0.03  # (relative error)
        # Let's check the transfer function of the pid module with the integrated NA
        if self.r is None:
            return
        else:
            r = self.r
        plotdata = []

        # shortcuts and na configuration
        na = self.pyrpl.na
        for pid in self.pyrpl.pids.all_modules:
            na.setup(start_freq=1000, stop_freq=1000e3, points=11, rbw=100,  # 101 points, 1 av->11 points, 7 av (taking ages)
                     avg=7,
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
        # Let's check the transfer function of the pid module with the integrated NA
        if self.r is None:
            return
        else:
            r = self.r
        plotdata = []

        # shortcuts and na configuration
        na = self.pyrpl.na
        for pid in self.pyrpl.pids.all_modules:
            na.setup(start_freq=1000, stop_freq=1000e3, points=11, rbw=100,
                     avg=10,
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
        # Let's check the transfer function of the pid module with the integrated NA
        if self.r is None:
            return
        else:
            r = self.r
        plotdata = []

        # shortcut for na and bpf (bandpass filter)
        na = self.pyrpl.na

        for bpf in [r.iq1, r.iq2]:
            plotdata = []
            # setup na for measurement
            na.setup(start_freq=300e3, stop_freq=700e3, points=51, rbw=1000, avg=3,
                     acbandwidth=0, amplitude=0.2, input=bpf,
                     output_direct='off', logscale=False)
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
                f, data, ampl = na.curve()
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
                    assert False, (maxerror, phase)

    def test_iirsimple_na_generator(self):
        # this test defines a simple transfer function that occupies 2
        # biquads in the iir filter. It then shifts the coefficients through
        # all available biquad spots and verifies that the transfer
        # function, as obtained from a na measurement, is in agreement with
        # the expected one. If something fails, the curves are saved to
        # CurveDB.
        extradelay = 0
        error_threshold = 0.25  # this value is mainly so high because of
        # ringing effects since we sweep over a resonance of the IIR filter
        # over a timescale comparable to its bandwidth. We should implement
        # another filter with very slow scan to test for model accuracy.
        # This test is only to confirm that all of the biquads are working.
        if self.r is None:
            return
        else:
            r = self.r
        # setup na
        na = self.pyrpl.na
        iir = self.pyrpl.rp.iir
        self.pyrpl.na.setup(start_freq=3e3,
                            stop_freq=1e6,
                            points=301,
                            rbw=[500, 500],
                            avg=1,
                            amplitude=0.005,
                            input=iir,
                            output_direct='off',
                            logscale=True)

        # setup a simple iir transfer function
        zeros = [1e5j - 3e3]
        poles = [5e4j - 3e3]
        gain = 1.0
        iir.setup(zeros=zeros, poles=poles, gain=gain,
                  loops=35,
                  input=na.iq,
                  output_direct='off')

        for setting in range(iir._IIRSTAGES):
            iir.on = False
            # shift coefficients into next pair of biquads (each biquad has
            # 6 coefficients)
            iir.coefficients = np.roll(iir.coefficients, 6)
            iir.iirfilter._fcoefficients = iir.coefficients
            iir.on = True
            # self.na_assertion(setting=setting,
            #                  module=iir,
            #                  error_threshold=error_threshold,
            #                  extradelay=extradelay,
            #                  relative=True)
            yield self.na_assertion, \
                  setting, iir, error_threshold, extradelay, True

    def test_iircomplicated_na_generator(self):
        # this test defines a number of complicated IIR transfer functions
        # and tests whether the NA response of the filter corresponds to what's
        # expected.
        #
        # sorry for the ugly code - the test works though
        # if there is a problem, no need to try to understand what the code
        # does at first (rather read the iir module code):
        # Just check the latest new CurveDB curves and for each failed test
        # you should find a set of curves whose names indicate the failed
        # test, whose parameters show the error between measurement and
        # theory, and by comparing the measurement and theory curve you
        # should be able to figure out what went wrong in the iir filter...

        extradelay = 0
        error_threshold = 0.005  # mean relative error over the whole curve,
        # values will be redifined individually
        if self.r is None:
            return
        else:
            pyrpl = self.pyrpl
        # setup na
        na = pyrpl.na
        iir = pyrpl.rp.iir

        params = []
        # setting 1
        z, p, g, loops = (np.array([-1510.0000001 - 10101.36145285j, -1510.0000001 +
                                    10101.36145285j,
                                    -2100.0000001 - 21828.90817759j, -2100.0000001 + 21828.90817759j,
                                    -1000.0000001 - 30156.73583005j, -1000.0000001 + 30156.73583005j,
                                    -1000.0000001 - 32063.2533145j, -1000.0000001 + 32063.2533145j,
                                    -6100.0000001 - 44654.63524562j, -6100.0000001 + 44654.63524562j]),
                          np.array([-151.00000010 - 16271.51686739j,
                                    -151.00000010 + 16271.51686739j, -51.00000010 - 22342.54324816j,
                                    -51.00000010 + 22342.54324816j, -10.00000010 - 30884.30406145j,
                                    -10.00000010 + 30884.30406145j, -41.00000010 - 32732.52445066j,
                                    -41.00000010 + 32732.52445066j, -51.00000010 - 46953.00496993j,
                                    -51.00000010 + 46953.00496993j]),
                          0.03,
                          400)
        naset = dict(start_freq=3e3,
                     stop_freq=50e3,
                     points=2001,
                     rbw=[500, 500],
                     avg=1,
                     amplitude=0.05,
                     input=iir,
                     output_direct='off',
                     logscale=True)
        error_threshold = 0.05  # [0.01, 0.03] works if avg=10 in naset
        params.append((z, p, g, loops, naset, "low_sampling", error_threshold,
                       ['final', 'continuous']))

        # setting 2 - minimum number of loops
        z = [1e5j - 3e3]
        p = [5e4j - 3e3]
        g = 0.5
        loops = None
        naset = dict(start_freq=3e3,
                     stop_freq=10e6,
                     points=1001,
                     rbw=[500, 500],
                     avg=1,
                     amplitude=0.05,
                     input=iir,
                     output_direct='off',
                     logscale=True)
        error_threshold = 0.05  # large because of phase error at high freq
        params.append((z, p, g, loops, naset, "loops_None", error_threshold,
                       ['final', 'continuous']))

        # setting 3 - complicated with well-defined loops (similar to 1)
        z, p, g = (
            np.array([-151.0000001 - 10101.36145285j, -151.0000001 +
                      10101.36145285j,
                      -210.0000001 - 21828.90817759j, -210.0000001 + 21828.90817759j,
                      -100.0000001 - 30156.73583005j, -100.0000001 + 30156.73583005j,
                      -100.0000001 - 32063.2533145j, -100.0000001 + 32063.2533145j,
                      -610.0000001 - 44654.63524562j, -610.0000001 + 44654.63524562j]),
            np.array([-151.00000010 - 16271.51686739j,
                      -151.00000010 + 16271.51686739j, -51.00000010 - 22342.54324816j,
                      -51.00000010 + 22342.54324816j, -50.00000010 - 30884.30406145j,
                      -50.00000010 + 30884.30406145j, -41.00000010 - 32732.52445066j,
                      -41.00000010 + 32732.52445066j, -51.00000010 - 46953.00496993j,
                      -51.00000010 + 46953.00496993j]),
            0.5)
        loops = 80
        naset = dict(start_freq=3e3,
                     stop_freq=50e3,
                     points=2501,
                     rbw=[1000, 1000],
                     avg=5,
                     amplitude=0.02,
                     input=iir,
                     output_direct='off',
                     logscale=True)
        error_threshold = 0.025
        params.append((z, p, g, loops, naset, "loops=80", error_threshold,
                       ['final', 'continuous']))

        # setting 4, medium complex transfer function
        z = [-4e4j - 300, +4e4j - 300, -2e5j - 3000, +2e5j - 3000]
        p = [-5e4j - 300, +5e4j - 300, -1e5j - 3000, +1e5j - 3000, -1e6j - 30000,
             +1e6j - 30000, -5e5]
        g = 1.0
        loops = None
        naset = dict(start_freq=1e4,
                     stop_freq=500e3,
                     points=301,
                     rbw=1000,
                     avg=1,
                     amplitude=0.01,
                     input='iir',
                     output_direct='off',
                     logscale=True)
        error_threshold = [0.03, 0.04]
        params.append((z, p, g, loops, naset, "4 - medium", error_threshold,
                       ['final', 'continuous']))

        # config na and iir and launch the na assertions
        for param in params[2:3]:
            z, p, g, loops, naset, name, maxerror, kinds = param
            self.pyrpl.na.setup(**naset)
            iir.setup(zeros=z, poles=p, gain=g, loops=loops, input=na.iq, output_direct='off')
            yield self.na_assertion, name, iir, maxerror, 0, True, True, kinds
            # default arguments of na_assertion:
            # setting, module, error_threshold=0.1,
            # extradelay=0, relative=False, mean=False, kinds=[]

    def na_assertion(self, setting, module, error_threshold=0.1,
                     extradelay=0, relative=False, mean=False, kinds=None):
        """ helper function: tests if module.transfer_function is within
        error_threshold of the measured transfer function of the module"""
        self.pyrpl.na.input = module
        f, data, ampl = self.pyrpl.na.curve()
        extrastring = str(setting)
        if not kinds:
            kinds = [None]
        for kind in kinds:
            if kind is None:
                theory = module.transfer_function(f, extradelay=extradelay)
                eth = error_threshold
            else:
                extrastring += '_' + kind + '_'
                theory = module.transfer_function(f, extradelay=extradelay,
                                                  kind=kind)
                try:
                    eth = error_threshold[kinds.index(kind)]
                except:
                    eth = error_threshold
            if relative:
                error = np.abs((data - theory) / theory)
            else:
                error = np.abs(data - theory)
            if mean:
                maxerror = np.mean(error)
            else:
                maxerror = np.max(error)
            if maxerror > eth:
                c = CurveDB.create(f, data, name='test_' + module.name
                                                 + '_' + extrastring + '_na-failed-data')
                c.params["unittest_relative"] = relative
                c.params["unittest_maxerror"] = maxerror
                c.params["unittest_error_threshold"] = eth
                c.params["unittest_setting"] = setting
                c.save()
                c.add_child(CurveDB.create(f, theory,
                                           name='test_' + module.name + '_na-failed-theory'))
                c.add_child(CurveDB.create(f, error,
                                           name='test_' + module.name + '_na-failed-error'))
                assert False, (maxerror, setting)
