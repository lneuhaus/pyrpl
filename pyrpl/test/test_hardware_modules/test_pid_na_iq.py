import logging
import os

import numpy as np
import pytest

from pyrpl import CurveDB
from pyrpl.async_utils import sleep, wait
from pyrpl.test.frequency_response_artifacts import fit_residual_delay, save_frequency_response
from pyrpl.test.test_base import TestPyrpl

logger = logging.getLogger(name=__name__)


@pytest.fixture(autouse=True, scope="class")
def setup_na(hardware_session):
    pyrpl = hardware_session.pyrpl

    # shortcuts
    na = pyrpl.networkanalyzer
    iqs = [pyrpl.rp.iq0, pyrpl.rp.iq1, pyrpl.rp.iq2]
    pids = pyrpl.pids.all_modules
    original_na_delay = na._delay
    original_iq_delays = [iq._delay for iq in iqs]
    if "PYRPL_TEST_NA_DELAY_CYCLES" in os.environ:
        na._delay = float(os.environ["PYRPL_TEST_NA_DELAY_CYCLES"])
    if "PYRPL_TEST_IQ_DELAY_CYCLES" in os.environ:
        iq_delay = float(os.environ["PYRPL_TEST_IQ_DELAY_CYCLES"])
        for iq in iqs:
            iq._delay = iq_delay
    na.auto_bandwidth = False
    na.auto_amplitude = False
    # Hardware tests must not inherit an externally armed IQ oscillator from
    # a saved GUI configuration.
    for iq in iqs:
        iq.trigger_source = "immediately"
        if "iq_vco" in pyrpl.rp.fpga_profile.capabilities:
            iq.vco_on = False
            iq.vco_input = "off"
            iq.vco_range = 0
    if "pid_external_pause" in pyrpl.rp.fpga_profile.capabilities:
        for pid in pids:
            pid.pause_source = "off"
    # set na loglevel to DEBUG
    loglevel = na._logger.getEffectiveLevel()
    na._logger.setLevel(10)

    yield  # Test runs here

    na.stop()
    na._delay = original_na_delay
    for iq, delay in zip(iqs, original_iq_delays):
        iq._delay = delay
        iq.trigger_source = "immediately"
        if "iq_vco" in pyrpl.rp.fpga_profile.capabilities:
            iq.vco_on = False
            iq.vco_input = "off"
            iq.vco_range = 0
    # set na loglevel to previous one
    na._logger.setLevel(loglevel)
    for pid in pids:
        pid.input = "off"
        pid.p = 0
        pid.i = 0
        pid.d = 0
        pid.ival = 0
        pid.output_direct = "off"
        pid.setpoint = 0
        pid.inputfilter = 0
        pid.pause_gains = "off"
        pid.paused = False
        if "pid_external_pause" in pyrpl.rp.fpga_profile.capabilities:
            pid.pause_source = "off"
            pid.pause_pin = "P0"
        pid.differential_mode_enabled = False


class TestPidNaIq(TestPyrpl):
    @property
    def na(self):
        return self.pyrpl.networkanalyzer

    def test_na(self):
        error_threshold = 0.03  # (relative error, dominated by phase error)
        if self.r is None:
            return
        else:
            r = self.r
        # shortcuts and na configuration
        na = self.na
        original_iq = na.iq
        try:
            for iq in [r.iq0, r.iq1, r.iq2]:
                na._iq = iq
                na.setup(
                    start_freq=3000,
                    stop_freq=10e6,
                    points=101,
                    # I reduced points from 1001 to 101, is it normal that
                    # it was taking ages ? -> no, should not take more than 1
                    # second with rbw=1000
                    rbw=1000,
                    average_per_point=1,
                    trace_average=1,
                    amplitude=0.1,
                    input=na.iq,
                    output_direct="off",
                    acbandwidth=1000,
                    logscale=True,
                )
                data = na.single()
                f = na.data_x
                theory = np.array(f * 0 + 1.0, dtype=complex)
                # obsolete since na data now comes autocorrected:
                # theory = na.transfer_function(f, extradelay=extradelay)
                delay_fit = fit_residual_delay(f, data, theory)
                clock_period = 8e-9 / iq._frequency_correction
                delay_fit["delay_cycles"] = delay_fit["delay_seconds"] / clock_period
                delay_fit["delay_standard_error_cycles"] = (
                    delay_fit["delay_standard_error_seconds"] / clock_period
                )
                delay_fit["modeled_network_analyzer_delay_cycles"] = na._delay
                delay_fit["inferred_network_analyzer_delay_cycles"] = (
                    na._delay + delay_fit["delay_cycles"]
                )
                delay_fit["inferred_network_analyzer_delay_nanoseconds"] = (
                    delay_fit["inferred_network_analyzer_delay_cycles"]
                    * clock_period
                    * 1e9
                )
                relerror = np.abs((data - theory) / theory)
                maxerror = np.max(relerror)
                artifact = save_frequency_response(
                    f"network_analyzer_{iq.name}",
                    f,
                    data,
                    theory,
                    metadata={
                        "error_threshold": error_threshold,
                        "fpga_profile": self.pyrpl.rp.fpga_profile.id,
                        "network_analyzer_delay_cycles": na._delay,
                        "iq_delay_cycles": iq._delay,
                        "delay_fit": delay_fit,
                    },
                )
                logger.info(
                    "%s corrected NA residual delay: %.3f +/- %.3f ns "
                    "(%.4f cycles); inferred total NA delay: %.4f cycles; "
                    "fit R^2: %.5f; artifact: %s",
                    iq.name,
                    delay_fit["delay_nanoseconds"],
                    delay_fit["delay_standard_error_nanoseconds"],
                    delay_fit["delay_cycles"],
                    delay_fit["inferred_network_analyzer_delay_cycles"],
                    delay_fit["r_squared"],
                    artifact,
                )
                if maxerror > error_threshold:
                    print(maxerror)
                    c = CurveDB.create(f, data, name="test_na-failed-data")
                    c.add_child(CurveDB.create(f, theory, name="test_na-failed-theory"))
                    c.add_child(CurveDB.create(f, relerror, name="test_na-failed-relerror"))
                    raise AssertionError(maxerror)
        finally:
            na._iq = original_iq

    @pytest.mark.requires_fpga("pid_input_filters")
    def test_inputfilter(self):
        """
        tests whether the modeled transfer function of pid module with
        any possible inputfilter (firstorder) corresponds to measured tf
        """
        error_threshold = 0.3  # 0.15 is ok for all but -3 MHz filter
        # testing one pid is enough
        pid = self.pyrpl.rp.pid0
        na = self.na
        na.setup(
            start_freq=10e3,
            stop_freq=5e6,
            # points 101->11, it was taking ages
            points=11,
            rbw=1000,
            average_per_point=1,
            trace_average=1,
            amplitude=0.1,
            input=pid,
            output_direct="off",
            acbandwidth=0,
            logscale=True,
        )

        # setup pid: input is the network analyzer output.
        pid.input = na.iq
        pid.setpoint = 0

        # proportional gain of 1, no inputfilter
        pid.p = 1.0
        pid.i = 0
        pid.d = 0
        pid.ival = 0

        _ = pid.inputfilter  # make sure this has been accessed before next step
        inputfilters = pid.inputfilter_options
        for bw in reversed(inputfilters):
            pid.inputfilter = [bw]
            data = na.single()
            f = na.data_x
            theory = pid.transfer_function(f)
            relerror = np.abs((data - theory) / theory)
            # get max error for values > -50 dB (otherwise its just NA noise)
            mask = np.asarray(np.abs(theory) > 3e-3, dtype=float)
            maxerror = np.max(relerror * mask)
            if maxerror > error_threshold:
                print(maxerror)
                c = CurveDB.create(f, data, name="test_inputfilter-failed-data")
                c.params["bandwidth"] = pid.inputfilter[0]
                c.save()
                c.add_child(CurveDB.create(f, theory, name="test_inputfilter-failed-theory"))
                c.add_child(CurveDB.create(f, relerror, name="test_inputfilter-failed-relerror"))
                raise AssertionError((maxerror, bw))

    def test_pid_na1(self):
        # setup a pid module with a bunch of different settings and measure
        # its transfer function, and compare it to the model.

        error_threshold = 0.03  # (relative error)
        # Let's check the transfer function of the pid module with the
        # integrated NA
        if self.r is None:
            return
        else:
            pass
        plotdata = []

        # shortcuts and na configuration
        na = self.na
        for pid in self.pyrpl.pids.all_modules:
            na.setup(
                start_freq=1000,
                stop_freq=10e6,
                # points 101->11, it was taking ages
                points=101,
                rbw=100,
                average_per_point=1,
                trace_average=1,
                amplitude=0.1,
                input=pid,
                output_direct="off",
                acbandwidth=0,
                logscale=True,
            )

            # setup pid: input is the network analyzer output.
            pid.input = na.iq
            pid.setpoint = 0

            # proportional gain of 1, no inputfilter
            pid.p = 1.0
            pid.i = 0
            pid.d = 0
            pid.ival = 0
            pid.inputfilter = 0
            data = na.single()
            f = na.data_x
            plotdata.append((f, data, "p=1"))
            theory = pid.transfer_function(f)
            delay_fit = fit_residual_delay(f, data, theory)
            delay_fit["delay_cycles_125mhz"] = delay_fit["delay_seconds"] / 8e-9
            delay_fit["delay_standard_error_cycles_125mhz"] = (
                delay_fit["delay_standard_error_seconds"] / 8e-9
            )
            delay_fit["modeled_pid_delay_cycles"] = pid._delay
            delay_fit["total_delay_cycles_125mhz"] = (
                pid._delay + delay_fit["delay_cycles_125mhz"]
            )
            delay_fit["total_delay_seconds"] = (
                pid._delay * 8e-9 + delay_fit["delay_seconds"]
            )
            delay_fit["total_delay_nanoseconds"] = delay_fit["total_delay_seconds"] * 1e9
            artifact = save_frequency_response(
                f"pid_delay_fit_{pid.name}",
                f,
                data,
                theory,
                metadata={
                    "fpga_profile": self.pyrpl.rp.fpga_profile.id,
                    "pid_delay_cycles": pid._delay,
                    "delay_fit": delay_fit,
                },
            )
            logger.info(
                "%s residual delay: %.3f +/- %.3f ns (%.3f cycles at 125 MHz); "
                "total path: %.3f ns (%.3f cycles); fit R^2: %.5f; artifact: %s",
                pid.name,
                delay_fit["delay_nanoseconds"],
                delay_fit["delay_standard_error_nanoseconds"],
                delay_fit["delay_cycles_125mhz"],
                delay_fit["total_delay_nanoseconds"],
                delay_fit["total_delay_cycles_125mhz"],
                delay_fit["r_squared"],
                artifact,
            )
            relerror = np.abs((data - theory) / theory)
            maxerror = np.max(relerror)
            if maxerror > error_threshold:
                print(maxerror)
                c = CurveDB.create(f, data, name="test_na_pid-failed-data")
                c.add_child(CurveDB.create(f, theory, name="test_na_pid-failed-theory"))
                c.add_child(CurveDB.create(f, relerror, name="test_na_pid-failed-relerror"))
                raise AssertionError(maxerror)

    def test_pid_na2(self):
        # setup a pid module with a bunch of different settings and measure
        # its transfer function, and compare it to the model.

        error_threshold = 0.05  # (relative error) used to be 0.04
        # Let's check the transfer function of the pid module with the integrated NA
        plotdata = []

        # shortcuts and na configuration
        na = self.na
        for pid in self.pyrpl.pids.all_modules:
            na.setup(
                start_freq=1000,
                stop_freq=10e6,
                # 101 points, 1 av->11 points, 7 av (taking ages)
                points=101,
                rbw=100,
                average_per_point=1,
                trace_average=1,
                amplitude=0.1,
                input=pid,
                output_direct="off",
                acbandwidth=0,
                logscale=True,
            )

            # setup pid: input is the network analyzer output.
            pid.input = na.iq
            pid.setpoint = 0

            # proportional gain of 0.01, integral = 1 kHz
            pid.p = 0.025
            pid.i = 250
            pid.d = 0
            pid.ival = 0
            pid.inputfilter = 0
            data = na.single()
            f = na.data_x
            plotdata.append((f, data, f"p={pid.p:.1e}, i={pid.i:.1e}"))
            theory = pid.transfer_function(f)
            relerror = np.abs((data - theory) / theory)
            maxerror = np.max(relerror)
            if maxerror > error_threshold:
                print(maxerror)
                c = CurveDB.create(f, data, name="test_na_pid-failed-data")
                c.add_child(CurveDB.create(f, theory, name="test_na_pid-failed-theory"))
                c.add_child(CurveDB.create(f, relerror, name="test_na_pid-failed-relerror"))
                raise AssertionError(maxerror)
            # check that no saturation has occured
            print("Integral value after measurement: ", pid.ival)
            if abs(pid.ival) >= 1.0:
                print("Saturation has occured. Data not reliable.")
            assert abs(pid.ival) <= 1.0, pid.ival

    @pytest.mark.requires_fpga("pid_input_filters")
    def test_pid_na3(self):
        # setup a pid module with a bunch of different settings and measure
        # its transfer function, and compare it to the model.

        error_threshold = 0.1  # (relative error)
        # Let's check the transfer function of the pid module with the
        # integrated NA
        if self.r is None:
            return
        else:
            pass
        plotdata = []

        # shortcuts and na configuration
        na = self.na
        for pid in self.pyrpl.pids.all_modules:
            na.setup(
                start_freq=1000,
                stop_freq=1000e3,
                points=101,
                rbw=100,
                average_per_point=10,
                trace_average=1,
                amplitude=0.1,
                input=pid,
                output_direct="off",
                acbandwidth=0,
                logscale=True,
            )

            # setup pid: input is the network analyzer output.
            pid.input = na.iq
            pid.setpoint = 0

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
            plotdata.append((f, data, "p=10 + filter"))
            theory = pid.transfer_function(f)
            relerror = np.abs((data - theory) / theory)
            maxerror = np.max(relerror)
            if maxerror > error_threshold:
                print(maxerror)
                c = CurveDB.create(f, data, name="test_na_pid-failed-data")
                c.add_child(CurveDB.create(f, theory, name="test_na_pid-failed-theory"))
                c.add_child(CurveDB.create(f, relerror, name="test_na_pid-failed-relerror"))
                raise AssertionError(maxerror)
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

        # shortcut for na and bpf (bandpass filter)
        na = self.pyrpl.networkanalyzer

        for bpf in [r.iq0, r.iq1]:
            # setup na for measurement
            na.setup(
                start_freq=300e3,
                stop_freq=700e3,
                points=51,
                rbw=1000,
                average_per_point=3,
                trace_average=1,
                acbandwidth=0,
                amplitude=0.2,
                input=bpf,
                output_direct="off",
                logscale=False,
            )
            # setup bandpass
            bpf.setup(
                frequency=500e3,  # center frequency
                bandwidth=5000,  # Q=100.0,  # the filter quality factor # sorry, I am dropping this
                acbandwidth=500,  # ac filter to remove pot. input offsets
                phase=0,  # nominal phase at center frequency (
                # propagation phase lags not accounted for)
                gain=1.0,  # peak gain = +0 dB
                output_direct="off",
                output_signal="output_direct",
                input=na.iq,
            )  # plug filter input to na output...

            for phase in [-45, 0, 45, 90]:
                bpf.phase = phase
                # take transfer function
                data = na.single()
                f = na.data_x
                theory = bpf.transfer_function(f, extradelay=extradelay)
                abserror = np.abs(data - theory)
                maxerror = np.max(abserror)
                artifact = save_frequency_response(
                    f"iq_{bpf.name}_phase_{phase:+g}",
                    f,
                    data,
                    theory,
                    metadata={
                        "phase_degrees": phase,
                        "error_threshold": error_threshold,
                        "iq_delay_cycles": bpf._delay,
                        "network_analyzer_delay_cycles": na._delay,
                        "frequency_hz": bpf.frequency,
                        "bandwidth_hz": bpf.bandwidth,
                        "acbandwidth_hz": bpf.acbandwidth,
                        "gain": bpf.gain,
                    },
                )
                logger.info("Saved IQ response artifacts to %s.*", artifact)
                # relerror = np.abs((data - theory) / theory)
                # maxerror = np.max(relerror)
                if maxerror > error_threshold:
                    print(maxerror)
                    c = CurveDB.create(f, data, name="test_iq_na-failed-data")
                    c.add_child(CurveDB.create(f, theory, name="test_iq_na-failed-theory"))
                    c.add_child(CurveDB.create(f, abserror, name="test_iq_na-failed-relerror"))
                    # c.add_child(CurveDB.create(f,relerror,name='test_iq_na-failed-abserror'))
                    raise AssertionError((maxerror, phase, bpf.name))

    @pytest.mark.requires_fpga("three_pids")
    def test_diff_pid(self):
        """
        tests the differential pid feature of pid0 and pid1
        """
        rp = self.pyrpl.rp
        pid0, pid1, pid2 = rp.pid0, rp.pid1, rp.pid2
        for pid in [pid0, pid1, pid2]:
            # we start with all gains off and ival reset, so the output should be 0
            pid.setup(
                input="pid2",
                output_direct="off",
                setpoint=-0.25,
                p=0,
                i=0,
                inputfilter=0,
                max_voltage=1,
                min_voltage=-1,
                pause_gains="off",
                paused=False,
                differential_mode_enabled=False,
            )
            pid.ival = 0
            assert pid.current_output_signal == 0.0, pid.current_output_signal
        diff_module = dict(pid0=pid1, pid1=pid0)
        for pid in [pid0, pid1]:
            diffpid = diff_module[pid.name]
            # test normal working mode
            pid.p = 30  # large p-gain should cause saturation
            assert pid.current_output_signal >= pid.max_voltage, (
                pid.current_output_signal,
                pid.max_voltage,
                pid.current_output_signal - pid.max_voltage,
            )
            # enable differential mode, input to both pid0 and pid1 is the same,
            # so output should be zero
            pid.differential_mode_enabled = True
            assert pid.current_output_signal == 0.0, pid.current_output_signal
            # this should not change even if input signal is changed
            pid2.ival = 1
            assert pid.current_output_signal == 0.0, pid.current_output_signal
            # this should not change even if input signal is changed
            pid2.ival = -0.1
            assert pid.current_output_signal == 0.0, pid.current_output_signal
            # but if the input to diffpid is disabled, we should recover normal pid
            pid.p = 3  # smaller p-gain to avoid saturation
            diffpid.input = "off"
            assert abs(pid.current_output_signal - (-0.3)) < 1e-4, (
                pid.name,
                pid.current_output_signal,
            )
            pid.differential_mode_enabled = False
            assert abs(pid.current_output_signal - (0.45)) < 5e-2, (
                pid.name,
                pid.current_output_signal,
            )
            # reset initial values
            for apid in [pid0, pid1, pid2]:
                # we start with all gains off and ival reset, so the output should be 0
                apid.setup(
                    input="pid2",
                    output_direct="off",
                    setpoint=-0.25,
                    p=0,
                    i=0,
                    inputfilter=0,
                    max_voltage=1,
                    min_voltage=-1,
                    pause_gains="off",
                    paused=False,
                    differential_mode_enabled=False,
                )
                apid.ival = 0
            assert apid.current_output_signal == 0.0, apid.current_output_signal

    def test_pid_paused(self):
        """
        tests the sync feature of different pid modules
        """
        pids = self.pyrpl.pids.all_modules
        for pid in pids:
            # we start with all gains off and ival reset, so the output should be 0
            pid.setup(
                input="off",
                output_direct="off",
                setpoint=-1,
                p=0,
                i=0,
                inputfilter=0,
                max_voltage=1,
                min_voltage=-1,
                pause_gains="off",
            )
            pid.ival = 0
            assert pid.current_output_signal == 0.0, pid.current_output_signal
            # test p settings
            pid.p = 10000000  # large p-gain should cause saturation
            # now pause the p-gain and assert that output is zero
            pid.pause_gains = "p"
            pid.paused = True
            assert pid.current_output_signal == 0.0, pid.current_output_signal
            # un-pause it and verify
            pid.paused = False
            assert pid.current_output_signal >= pid.max_voltage, (
                pid.current_output_signal,
                pid.max_voltage,
                pid.current_output_signal - pid.max_voltage,
            )
            # test integrator part - first let integrator saturate
            pid.i = 10000000
            pid.p = 0
            assert pid.current_output_signal >= pid.max_voltage, pid.current_output_signal
            # now pause the i-gain and assert that output is unchanged
            pid.pause_gains = "i"
            assert pid.current_output_signal >= pid.max_voltage, pid.current_output_signal
            # assert that ival can be set in presence of large gains
            pid.paused = True
            pid.ival = 0.1
            assert (pid.ival - pid.current_output_signal) <= 0.0001, (
                pid.current_output_signal,
                pid.ival,
            )
            assert (pid.ival - 0.1) <= 0.0001, (pid.current_output_signal, pid.ival)
            pid.pause_gains = "off"
            assert pid.current_output_signal >= pid.max_voltage, pid.current_output_signal
            # un-pause for later
            pid.paused = False

    @pytest.mark.requires_fpga("pid_external_pause")
    def test_pid_external_pause(self):
        """Hold the complete PID output low on P0 and resume it high."""
        rp = self.pyrpl.rp
        pid = rp.pid0
        asg = rp.asg0
        scope = rp.scope
        hk = rp.hk
        original_pin_direction = hk.expansion_P0_output
        original_pin_output = bool(hk._read(0x18) & 1)

        frequency = 1e6
        amplitude = 0.4
        duration = scope.data_length / 125e6

        try:
            # Start enabled with a nonzero DC output, then pause and replace
            # the input with a sine. The held output must remain at the old
            # DC value until the same P0 edge triggers the scope and PID.
            hk.expansion_P0_output = True
            hk.expansion_P0 = True
            asg.setup(
                waveform="dc",
                amplitude=0,
                offset=0.25,
                trigger_source="immediately",
                output_direct="off",
            )
            pid.setup(
                input="asg0",
                output_direct="off",
                setpoint=0,
                p=1,
                i=0,
                inputfilter=0,
                min_voltage=-1,
                max_voltage=1,
                pause_gains="off",
                paused=False,
                pause_source="external",
                pause_pin="P0",
                differential_mode_enabled=False,
            )
            pid.ival = 0
            sleep(0.01)

            hk.expansion_P0 = False
            sleep(0.001)
            held_output = rp.sampler.pid0
            assert abs(held_output) > 0.1

            asg.setup(
                waveform="sin",
                frequency=frequency,
                amplitude=amplitude,
                offset=0,
                trigger_source="immediately",
                output_direct="off",
            )
            sleep(0.001)
            held_mean, held_std, _, _ = rp.sampler.stats("pid0", t=0.005)
            assert held_mean == pytest.approx(held_output, abs=0.002)
            assert held_std < 0.002

            scope.setup(
                input1="pid0",
                input2="off",
                duration=duration,
                trigger_source="ext_positive_edge",
                trigger_delay=0,
                trace_average=1,
                ch1_active=True,
                ch2_active=False,
                rolling_mode=False,
            )
            acquisition = scope.single_async()
            scope.wait_for_pretrigger()
            hk.expansion_P0 = True
            trace = wait(acquisition, timeout=5)[0]
            times = scope.times

            pretrigger = trace[
                (times > times[0] + 1e-6) & (times < -1e-6)
            ]
            assert pretrigger.size > 0
            assert np.mean(pretrigger) == pytest.approx(held_output, abs=0.01)
            assert np.ptp(pretrigger) < 0.01

            active = times > 2e-6
            omega_t = 2 * np.pi * asg.frequency * times[active]
            basis = np.column_stack(
                (np.sin(omega_t), np.cos(omega_t), np.ones(np.count_nonzero(active)))
            )
            coefficients, *_ = np.linalg.lstsq(basis, trace[active], rcond=None)
            fitted = basis @ coefficients
            measured_amplitude = np.hypot(coefficients[0], coefficients[1])
            residual_rms = np.sqrt(np.mean((trace[active] - fitted) ** 2))
            assert measured_amplitude == pytest.approx(asg.amplitude, rel=0.05, abs=0.01)
            assert residual_rms < 0.02
        finally:
            scope.stop()
            scope.trigger_source = "immediately"
            pid.pause_source = "off"
            pid.pause_pin = "P0"
            pid.p = 0
            pid.i = 0
            pid.d = 0
            pid.ival = 0
            asg.amplitude = 0
            asg.offset = 0
            hk.expansion_P0 = original_pin_output
            hk.expansion_P0_output = original_pin_direction

    @pytest.mark.requires_fpga("pid_derivative")
    def test_pid_derivative_frequency_response(self):
        """Check derivative sign, coefficient, latency and combined PID response."""
        na = self.na
        error_threshold = 0.05  # relative complex error, including phase/latency
        for pid in self.pyrpl.pids.all_modules:
            na.setup(
                start_freq=10e3,
                stop_freq=2e6,
                points=31,
                rbw=1e3,
                average_per_point=3,
                trace_average=1,
                amplitude=0.02,
                input=pid,
                output_direct="off",
                acbandwidth=0,
                logscale=True,
            )
            pid.setup(
                input=na.iq,
                setpoint=0,
                p=0.2,
                i=2e3,
                d=100e3,
                derivative_filter_ratio=5,
                inputfilter=0,
                min_voltage=-1,
                max_voltage=1,
                pause_gains="off",
                paused=False,
            )
            # test_pid_paused deliberately leaves the integrator saturated.
            # The derivative response must not depend on that earlier test's
            # hardware state, especially since changing i does not clear ival.
            pid.ival = 0
            assert pid.d == pytest.approx(100e3, rel=2e-4)
            assert np.sign(pid.d) == 1
            requested_cutoff = pid.derivative_filter_ratio * abs(pid.d)
            assert pid.derivative_filter_bandwidth == pytest.approx(
                pid._derivative_filter_cutoff(
                    pid._derivative_filter_shift_register,
                    pid._frequency_correction,
                )
            )
            assert pid._derivative_filter_shift_register == pid._select_derivative_filter_shift(
                requested_cutoff, pid._frequency_correction
            )

            data = na.single()
            frequencies = na.data_x
            theory = pid.transfer_function(frequencies)
            relative_error = np.abs((data - theory) / theory)
            artifact = save_frequency_response(
                f"pid_derivative_{pid.name}",
                frequencies,
                data,
                theory,
                metadata={
                    "d_hz": pid.d,
                    "filter_ratio": pid.derivative_filter_ratio,
                    "filter_bandwidth_hz": pid.derivative_filter_bandwidth,
                    "filter_shift": pid._derivative_filter_shift_register,
                    "error_threshold": error_threshold,
                    "error_kind": "relative_complex",
                },
            )
            logger.info("Saved derivative response artifacts to %s.*", artifact)
            assert np.max(relative_error) < error_threshold

            pid.p = 0
            pid.i = 0
            pid.ival = 0
            positive = na.single()
            pid.d = -100e3
            negative = na.single()
            active = np.abs(positive) > 0.02
            assert np.max(np.abs(positive[active] + negative[active])) < 0.08

    @pytest.mark.requires_fpga("pid_derivative")
    def test_pid_derivative_saturation_and_pause(self):
        """Exercise derivative limiting and ensure pause clears its state."""
        rp = self.pyrpl.rp
        for pid in self.pyrpl.pids.all_modules:
            rp.asg0.setup(
                waveform="square",
                frequency=100e3,
                amplitude=0.5,
                offset=0,
                output_direct="off",
                trigger_source="immediately",
            )
            pid.setup(
                input="asg0",
                setpoint=0,
                p=0,
                i=0,
                d=20e3,
                derivative_filter_ratio=10,
                inputfilter=0,
                min_voltage=-0.25,
                max_voltage=0.25,
                pause_gains="d",
                paused=False,
            )
            # Keep this test independent of the preceding response test and
            # of any PID state that was already present on the board.
            pid.ival = 0
            rp.scope.setup(
                input1=pid.name,
                input2="asg0",
                duration=100e-6,
                trigger_source="immediately",
            )
            derivative, _ = rp.scope.single(timeout=4)
            tolerance = 2.0 / 2**13
            assert np.max(derivative) <= pid.max_voltage + tolerance
            assert np.min(derivative) >= pid.min_voltage - tolerance
            assert np.max(derivative) > 0.95 * pid.max_voltage
            assert np.min(derivative) < 0.95 * pid.min_voltage

            pid.paused = True
            paused, _ = rp.scope.single(timeout=4)
            assert np.max(np.abs(paused)) < 5 * tolerance
            pid.paused = False

    @pytest.mark.requires_fpga("iq_vco")
    def test_iq_vco_frequency_sign_and_scaling(self):
        """Check that positive and negative controls tune the IQ carrier."""
        rp = self.pyrpl.rp
        iq = rp.iq0
        asg = rp.asg0
        base_frequency = 1e6
        vco_range = 400e3
        controls = (-0.5, 0.0, 0.5)

        def measured_frequency():
            trace = rp.scope.single(timeout=4)[0]
            times = rp.scope.times
            # Average over all positive-going zero crossings. This is less
            # sensitive to scope sample quantization than one measured period.
            edges = np.flatnonzero((trace[:-1] <= 0) & (trace[1:] > 0))
            assert len(edges) >= 20
            return (len(edges) - 1) / (times[edges[-1]] - times[edges[0]])

        try:
            asg.setup(
                waveform="dc",
                amplitude=0,
                offset=0,
                frequency=1e3,
                trigger_source="immediately",
                output_direct="off",
            )
            iq.setup(
                input="off",
                frequency=base_frequency,
                bandwidth=0,
                gain=0,
                amplitude=0.5,
                phase=0,
                output_direct="off",
                output_signal="output_direct",
                trigger_source="immediately",
                vco_input="asg0",
                vco_range=vco_range,
                vco_on=True,
            )
            rp.scope.setup(
                input1="iq0",
                input2="off",
                duration=100e-6,
                trigger_source="immediately",
                trace_average=1,
                ch1_active=True,
                ch2_active=False,
                rolling_mode=False,
            )

            measured = []
            for control in controls:
                asg.offset = control
                sleep(0.02)
                measured.append(measured_frequency())

            expected = [base_frequency + control * vco_range for control in controls]
            assert measured == pytest.approx(expected, rel=0.01)
            assert measured[0] < measured[1] < measured[2]
        finally:
            iq.vco_on = False
            iq.vco_input = "off"
            iq.vco_range = 0
            asg.offset = 0

    def test_iq_sync(self):
        """
        tests the sync feature of different iq modules
        """
        rp = self.pyrpl.rp
        iqs = [rp.iq0, rp.iq1, rp.iq2]
        for iq in iqs:
            iq.setup(
                input="iq0",
                frequency=47e6,
                acbandwidth=1e5,
                bandwidth=0,
                output_signal="output_direct",
                gain=0,
                amplitude=0.5,
                quadrature_factor=0,
                phase=0,
                output_direct="off",
            )
            iq._na_averages = 1e6
        # first measure in desync mode
        for iq in iqs:
            f = iq.frequency
            iq.frequency = 0  # this step is enough to de-sync iqs
            iq.frequency = f
        sleep(1e6 / iq.frequency)
        angles = np.array([np.angle(iq._nadata, deg=True) for iq in iqs])

        def circular_spread_degrees(phases):
            """Return phase spread without a false jump at -180/180 degrees."""
            relative = np.angle(
                np.exp(1j * np.deg2rad(phases - phases[0])),
                deg=True,
            )
            return np.ptp(relative)

        desyncdiff = circular_spread_degrees(angles)
        assert desyncdiff > 0.01, (
            f"iq modules not desynchronized, desyncdiff = {desyncdiff:f} < 0.01! Angles: {angles}"
        )
        # synchronize
        rp.iq0.synchronize_iqs()
        # now measure in synced mode
        for iq in iqs:
            iq.frequency = iq.frequency
        sleep(1e6 / iq.frequency)
        angles = np.array([np.angle(iq._nadata, deg=True) for iq in iqs])
        syncdiff = circular_spread_degrees(angles)
        print(desyncdiff, syncdiff)
        # The IQ oscillator uses an 11-bit lookup-table address, corresponding
        # to 360 / 2048 = 0.176 degrees per phase step.  A 0.01-degree hardware
        # assertion is therefore unnecessarily tighter than its resolution.
        sync_tolerance_degrees = 0.2
        assert syncdiff < sync_tolerance_degrees, (
            "synchronization of iq modules not working, "
            f"syncdiff = {syncdiff:f} > {sync_tolerance_degrees:f}! "
            f"Angles: {angles}"
        )

    def test_iq_external_trigger(self):
        """Start an IQ and the scope from the same P0 expansion-pin edge."""
        rp = self.pyrpl.rp
        iq = rp.iq0
        scope = rp.scope
        hk = rp.hk
        original_pin_direction = hk.expansion_P0_output
        original_pin_output = bool(hk._read(0x18) & 1)

        frequency = 1e6
        amplitude = 0.5
        duration = scope.data_length / 125e6

        try:
            # Drive the expansion pin low before arming. The IOBUF input path
            # reads back the level driven on P0, providing an automatic test
            # without an external pulse generator or a physical jumper.
            hk.expansion_P0_output = True
            hk.expansion_P0 = False

            iq.setup(
                input="off",
                frequency=frequency,
                trigger_source="external",
                trigger_pin="P0",
                bandwidth=0,
                gain=0,
                amplitude=amplitude,
                phase=0,
                output_direct="off",
                output_signal="output_direct",
            )
            scope.setup(
                input1="iq0",
                input2="off",
                duration=duration,
                trigger_source="ext_positive_edge",
                trigger_delay=0,
                trace_average=1,
                ch1_active=True,
                ch2_active=False,
                rolling_mode=False,
            )

            acquisition = scope.single_async()
            scope.wait_for_pretrigger()

            hk.expansion_P0 = True
            trace = wait(acquisition, timeout=5)[0]
            times = scope.times

            # Well before the shared trigger, the externally armed IQ must be
            # held at zero. Ignore a short interval at the oldest edge of the
            # circular scope buffer, where a few samples from acquisition
            # startup can remain, as well as the different trigger/datapath
            # latencies around t=0.
            pretrigger = trace[(times > times[0] + 1e-6) & (times < -1e-6)]
            assert pretrigger.size > 0
            assert np.max(np.abs(pretrigger)) < 0.01

            active_indices = np.flatnonzero(np.abs(trace) > 0.05)
            assert active_indices.size > 0
            first_active_time = times[active_indices[0]]
            assert abs(first_active_time) < 0.5e-6

            # After startup, fit an arbitrary-phase sinusoid at the requested
            # IQ frequency. This checks waveform, frequency and amplitude
            # without depending on the exact trigger-to-modulator latency.
            active = times > 2e-6
            omega_t = 2 * np.pi * iq.frequency * times[active]
            basis = np.column_stack(
                (np.sin(omega_t), np.cos(omega_t), np.ones(np.count_nonzero(active)))
            )
            coefficients, *_ = np.linalg.lstsq(basis, trace[active], rcond=None)
            fitted = basis @ coefficients
            measured_amplitude = np.hypot(coefficients[0], coefficients[1])
            residual_rms = np.sqrt(np.mean((trace[active] - fitted) ** 2))
            assert measured_amplitude == pytest.approx(iq.amplitude, rel=0.05, abs=0.01)
            assert residual_rms < 0.02
        finally:
            scope.stop()
            scope.trigger_source = "immediately"
            iq.amplitude = 0
            iq.trigger_source = "immediately"
            iq.trigger_pin = "P0"
            hk.expansion_P0 = original_pin_output
            hk.expansion_P0_output = original_pin_direction
