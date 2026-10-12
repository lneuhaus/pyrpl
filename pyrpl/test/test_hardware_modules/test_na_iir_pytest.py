import logging
import os

import numpy as np
import pytest

from pyrpl import CurveDB
from pyrpl.test.frequency_response_artifacts import save_frequency_response
from pyrpl.test.test_base import TestPyrpl

logger = logging.getLogger(name=__name__)

pytestmark = pytest.mark.requires_fpga("iir")


@pytest.fixture(autouse=True, scope="class")
def setup_iir(hardware_session):
    # shortcuts
    pyrpl = hardware_session.pyrpl
    na = pyrpl.networkanalyzer
    iir = pyrpl.rp.iir
    original_delay = iir._delay
    original_minloops = iir._minloops
    if "PYRPL_TEST_IIR_DELAY_CYCLES" in os.environ:
        iir._delay = float(os.environ["PYRPL_TEST_IIR_DELAY_CYCLES"])
    if "PYRPL_TEST_IIR_MIN_LOOPS" in os.environ:
        iir._minloops = int(os.environ["PYRPL_TEST_IIR_MIN_LOOPS"])
    # set na loglevel to DEBUG
    loglevel = na._logger.getEffectiveLevel()
    na._logger.setLevel(10)
    na.auto_bandwidth = False
    na.auto_amplitude = False
    yield

    # Teardown
    na.stop()
    iir._delay = original_delay
    iir._minloops = original_minloops
    # set na loglevel to previous one
    na._logger.setLevel(loglevel)


class TestIir(TestPyrpl):
    @property
    def iir(self):
        return self.pyrpl.rp.iir

    @property
    def na(self):
        return self.pyrpl.networkanalyzer

    def test_pz_interface(self):
        """tests that poles and real/comples_poles remain sync'ed"""
        iir = self.iir
        # This test only checks the synchronization of the pole/zero list
        # attributes. Some intermediate states (in particular zeros without
        # poles) are not implementable filters, so do not program the FPGA
        # after each individual list mutation.
        with iir.do_setup:
            iir.poles = [-1000j - 2032, -34343j - 3424, -1221, -43254.4]
            assert iir.real_poles == [-1221, -43254.4], iir.real_poles
            assert iir.complex_poles == [1000j - 2032, 34343j - 3424], (
                iir.complex_poles
            )  # attention: imaginary part is positivized
            iir.real_poles = []
            assert iir.complex_poles == [1000j - 2032, 34343j - 3424], (
                iir.complex_poles
            )  # attention: imaginary part is positivized
            assert iir.poles == iir.complex_poles, iir.poles
            iir.complex_poles = []
            assert iir.poles == []
            assert iir.real_poles == []
            assert iir.complex_poles == []

            iir.zeros = [-1000j - 2032, -34343j - 3424, -1221, -43254.4]
            assert iir.real_zeros == [-1221, -43254.4], iir.real_zeros
            assert iir.complex_zeros == [1000j - 2032, 34343j - 3424], (
                iir.complex_zeros
            )  # attention: imaginary part is positivized
            iir.real_zeros = []
            assert iir.complex_zeros == [1000j - 2032, 34343j - 3424], (
                iir.complex_zeros
            )  # attention: imaginary part is positivized
            assert iir.zeros == iir.complex_zeros, iir.zeros
            iir.complex_zeros = []
            assert iir.zeros == []
            assert iir.real_zeros == []
            assert iir.complex_zeros == []

    @pytest.mark.parametrize("setting", range(14))  # iir._IIRSTAGES = 14
    def test_iirsimple_na_generator(self, setting):
        # this test defines a simple transfer function that occupies 2
        # biquads in the iir filter. It then shifts the coefficients through
        # all available biquad spots and verifies that the transfer
        # function, as obtained from a na measurement, is in agreement with
        # the expected one. If something fails, the curves are saved to
        # CurveDB.
        extradelay = 0
        mean_relative_error_threshold = 0.10
        normalized_absolute_error_threshold = 0.05
        # A maximum relative-error check is ill-conditioned around the deep
        # notch of this filter: a small coefficient-rounding shift makes the
        # relative error arbitrarily large as the theoretical response tends
        # to zero. The mean relative error checks the whole response, while
        # the peak-normalized absolute error still catches a broken biquad.
        # setup na
        na = self.na
        iir = self.iir
        if setting >= iir._IIRSTAGES:
            pytest.skip(f"Bitstream provides only {iir._IIRSTAGES} IIR stages")
        na.setup(
            start_freq=3e3,
            stop_freq=1e6,
            points=301,
            rbw=500,
            average_per_point=1,
            trace_average=1,
            amplitude=0.005,
            input=iir,
            output_direct="off",
            logscale=True,
        )

        # setup a simple iir transfer function
        zeros = [1e5j - 3e3]
        poles = [5e4j - 3e3]
        gain = 1.0
        iir.setup(
            zeros=zeros,
            poles=poles,
            gain=gain,
            loops=35,
            input=na.iq,
            output_direct="off",
        )

        iir.on = False
        # shift coefficients into the biquad specified by 'setting'
        iir.coefficients = np.roll(iir.coefficients, 6 * setting)
        iir.iirfilter._fcoefficients = iir.coefficients
        iir.on = True

        self.na_assertion(
            setting,
            iir,
            mean_relative_error_threshold,
            extradelay=extradelay,
            relative=True,
            mean=True,
            normalized_absolute_threshold=normalized_absolute_error_threshold,
        )

    params = []
    # setting 0
    z, p, g, loops = (
        np.array(
            [
                -1510.0000001 + 10101.36145285j,
                -2100.0000001 + 21828.90817759j,
                -1000.0000001 + 30156.73583005j,
                -1000.0000001 + 32063.2533145j,
                -6100.0000001 + 44654.63524562j,
            ]
        ),
        np.array(
            [
                -151.00000010 + 16271.51686739j,
                -51.00000010 + 22342.54324816j,
                -10.00000010 + 30884.30406145j,
                -41.00000010 + 32732.52445066j,
                -51.00000010 + 46953.00496993j,
            ]
        ),
        0.03,
        400,
    )
    naset = dict(
        start_freq=3e3,
        stop_freq=50e3,
        points=501,
        rbw=500,
        average_per_point=10,
        trace_average=1,
        amplitude=0.05,
        output_direct="off",
        logscale=True,
    )
    error_threshold = [0.05, 0.1]
    params.append(
        (
            z,
            p,
            g,
            loops,
            naset,
            "0 - low_sampling",
            error_threshold,
            ["final", "continuous"],
        )
    )

    # setting 1 - minimum number of loops
    z = [1e5j - 3e3]
    p = [5e4j - 3e3]
    g = 0.5
    loops = None
    naset = dict(
        start_freq=3e3,
        stop_freq=10e6,
        points=301,
        rbw=500,
        average_per_point=1,
        trace_average=1,
        amplitude=0.05,
        output_direct="off",
        logscale=True,
    )
    # The final model includes the progressive FPGA biquad latency and is the
    # strict implementation check. The ideal continuous model intentionally
    # omits that section-dependent delay, which becomes visible near 10 MHz.
    error_threshold = [0.05, 0.10]
    params.append(
        (
            z,
            p,
            g,
            loops,
            naset,
            "1 - loops_None",
            error_threshold,
            ["final", "continuous"],
        )
    )

    # setting 2 - complicated with well-defined loops (similar to 1)
    z, p, g = (
        np.array(
            [
                -151.0000001 + 10101.36145285j,
                -210.0000001 + 21828.90817759j,
                -100.0000001 + 30156.73583005j,
                -100.0000001 + 32063.2533145j,
                -610.0000001 + 44654.63524562j,
            ]
        ),
        np.array(
            [
                -151.00000010 + 16271.51686739j,
                -51.00000010 + 22342.54324816j,
                -50.00000010 + 30884.30406145j,
                -41.00000010 + 32732.52445066j,
                -51.00000010 + 46953.00496993j,
            ]
        ),
        0.5,
    )
    loops = 80
    naset = dict(
        start_freq=3e3,
        stop_freq=50e3,
        points=1000,  # 2501
        rbw=300,  # 1000,1000
        average_per_point=3,  # 5
        trace_average=1,
        amplitude=0.02,
        output_direct="off",
        logscale=True,
    )
    error_threshold = 0.03
    params.append(
        (
            z,
            p,
            g,
            loops,
            naset,
            "2 - loops=80",
            error_threshold,
            ["final", "continuous"],
        )
    )

    # setting 3, medium complex transfer function
    z = [+4e4j - 300, +2e5j - 3000]
    p = [+5e4j - 300, +1e5j - 3000, +1e6j - 30000, -5e5]
    g = 1.0
    loops = None
    naset = dict(
        start_freq=1e4,
        stop_freq=500e3,
        points=301,
        rbw=1000,
        average_per_point=1,
        trace_average=1,
        amplitude=0.01,
        output_direct="off",
        logscale=True,
    )
    # The final model is the strict FPGA implementation check. The continuous
    # model omits discretization, coefficient rounding, and progressive stage
    # delays, so allow it slightly more margin.
    error_threshold = [0.04, 0.05]
    params.append((z, p, g, loops, naset, "3 - medium", error_threshold, ["final", "continuous"]))

    @pytest.mark.parametrize(
        "param_set", params, ids=lambda p: p[5]
    )  # Use the name field as test ID
    def test_iircomplicated_na(self, param_set):
        """
        This test defines a number of complicated IIR transfer functions
        and tests whether the NA response of the filter corresponds to what's
        expected.

        sorry for the ugly code - the test works though
        if there is a problem, no need to try to understand what the code
        does at first (rather read the iir module code):
        Just check the latest new CurveDB curves and for each failed test
        you should find a set of curves whose names indicate the failed
        test, whose parameters show the error between measurement and
        theory, and by comparing the measurement and theory curve you
        should be able to figure out what went wrong in the iir filter...
        """
        if self.r is None:
            pytest.skip("No Red Pitaya connection")

        z, p, g, loops, naset, name, error_threshold, kinds = param_set

        na = self.pyrpl.networkanalyzer
        iir = self.pyrpl.rp.iir

        # Set input in naset
        naset["input"] = iir

        na.setup(**naset)
        iir.setup(zeros=z, poles=p, gain=g, loops=loops, input=na.iq, output_direct="off")

        self.na_assertion(name, iir, error_threshold, 0, True, True, kinds)

    def na_assertion(
        self,
        setting,
        module,
        error_threshold=0.1,
        extradelay=0,
        relative=False,
        mean=False,
        kinds=None,
        normalized_absolute_threshold=None,
    ):
        """
        helper function: tests if module.transfer_function is within
        error_threshold of the measured transfer function of the module
        """
        na = self.na
        na.input = module
        na._logger.info("Starting NA acquisition...")
        data = na.single()
        na._logger.info("NA acquisition finished...")
        f = na.data_x
        extrastring = str(setting)
        if not kinds:
            kinds = [None]
        for kind in kinds:
            if kind is None:
                theory = module.transfer_function(f, extradelay=extradelay)
                eth = error_threshold
            else:
                extrastring += "_" + kind + "_"
                theory = module.transfer_function_by_kind(f, kind=kind)
                try:
                    eth = error_threshold[kinds.index(kind)]
                except (IndexError, TypeError, ValueError):
                    eth = error_threshold
            error = np.abs((data - theory) / theory) if relative else np.abs(data - theory)
            maxerror = np.mean(error) if mean else np.max(error)
            absolute_error = np.abs(data - theory)
            response_scale = max(np.max(np.abs(theory)), np.finfo(float).eps)
            normalized_absolute_error = np.max(absolute_error) / response_scale
            artifact_name = f"iir_{module.name}_{setting}_{kind or 'default'}"
            artifact = save_frequency_response(
                artifact_name,
                f,
                data,
                theory,
                metadata={
                    "setting": setting,
                    "kind": kind,
                    "error_threshold": eth,
                    "error_is_relative": relative,
                    "error_uses_mean": mean,
                    "normalized_absolute_error": normalized_absolute_error,
                    "normalized_absolute_error_threshold": normalized_absolute_threshold,
                    "iir_bits": module._IIRBITS,
                    "iir_stages": module._IIRSTAGES,
                    "loops": module.loops,
                    "module_delay_cycles": module._delay,
                },
            )
            logger.info("Saved IIR response artifacts to %s.*", artifact)
            relative_error_failed = maxerror > eth
            normalized_absolute_error_failed = (
                normalized_absolute_threshold is not None
                and normalized_absolute_error > normalized_absolute_threshold
            )
            if relative_error_failed or normalized_absolute_error_failed:
                c = CurveDB.create(
                    f,
                    data,
                    name="test_" + module.name + "_" + extrastring + "_na-failed-data",
                )
                c.params["unittest_relative"] = relative
                c.params["unittest_maxerror"] = maxerror
                c.params["unittest_error_threshold"] = eth
                c.params["unittest_normalized_absolute_error"] = normalized_absolute_error
                c.params["unittest_normalized_absolute_error_threshold"] = (
                    normalized_absolute_threshold
                )
                c.params["unittest_setting"] = setting
                c.save()
                c.add_child(
                    CurveDB.create(f, theory, name="test_" + module.name + "_na-failed-theory")
                )
                c.add_child(
                    CurveDB.create(f, error, name="test_" + module.name + "_na-failed-error")
                )
                raise AssertionError(
                    {
                        "error": maxerror,
                        "error_threshold": eth,
                        "normalized_absolute_error": normalized_absolute_error,
                        "normalized_absolute_error_threshold": normalized_absolute_threshold,
                        "setting": setting,
                    }
                )
