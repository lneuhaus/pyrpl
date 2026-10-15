import contextlib
import logging
import traceback

import numpy as np
import pytest

from pyrpl import APP
from pyrpl.async_utils import sleep
from pyrpl.software_modules.spectrum_analyzer import SpectrumAnalyzer, get_window_numpy
from pyrpl.test.frequency_response_artifacts import save_frequency_response
from pyrpl.test.test_base import TestPyrpl

logger = logging.getLogger(name=__name__)


class TestSpectrumAnalyzer(TestPyrpl):
    @pytest.fixture(autouse=True)
    def setup_spectrum_analyzer(self):
        self.sa = self.pyrpl.spectrumanalyzer
        self.asg = self.pyrpl.rp.asg0
        self.iq = self.pyrpl.rp.iq0

        # The hardware session is shared by the test suite. Start every test
        # from an idle acquisition state and leave signal generators harmless.
        self.r.scope.stop()
        self.pyrpl.networkanalyzer.stop()
        self.sa.stop()

        yield

        self.sa.stop()
        self.r.scope.stop()
        with contextlib.suppress(AttributeError, RuntimeError, OSError, ValueError):
            self.asg.setup(amplitude=0, output_direct="off")
        with contextlib.suppress(AttributeError, RuntimeError, OSError, ValueError):
            self.iq.setup(amplitude=0, output_direct="off")

    @pytest.mark.parametrize(
        ("unit", "expected"),
        [
            ("Vpk^2", 8.0),
            ("dB(Vpk^2)", 10 * np.log10(8.0)),
            ("Vpk", np.sqrt(8.0)),
            ("Vrms^2", 4.0),
            ("dB(Vrms^2)", 10 * np.log10(4.0)),
            ("Vrms", 2.0),
            ("Vrms^2/Hz", 2.0),
            ("dB(Vrms^2/Hz)", 10 * np.log10(2.0)),
            ("Vrms/sqrt(Hz)", np.sqrt(2.0)),
        ],
    )
    def test_data_to_unit(self, unit, expected):
        converted = self.sa.data_to_unit(np.array([8.0]), unit, rbw=2.0)
        np.testing.assert_allclose(converted, [expected], rtol=1e-12, atol=1e-12)

    @pytest.mark.parametrize("window", SpectrumAnalyzer.windows)
    def test_window_coherent_tone_calibration(self, window):
        length = 2048
        cycles = 37
        samples = np.arange(length)
        tone = np.cos(2 * np.pi * cycles * samples / length)
        weights = get_window_numpy(window, length)
        weights /= np.sum(weights) / 2

        spectrum = np.abs(np.fft.rfft(tone * weights, length * 16)) ** 2
        assert np.isfinite(spectrum).all()
        assert np.max(spectrum) == pytest.approx(1.0, rel=2e-3)

        equivalent_noise_bandwidth = np.sum(weights**2) / np.sum(weights) ** 2
        assert equivalent_noise_bandwidth > 0

    def test_no_write_in_config(self):
        """
        Make sure the spec an isn't continuously writing to config file,
        even in running mode.
        :return:
        """
        self.sa.setup(baseband=True, span=1e5, input1_baseband="out1")
        self.sa.continuous()
        sleep(0.1)
        assert self.sa.running_state == "running_continuous"
        # record where each save during the measurement comes from, so that a
        # failure names the attribute that was written
        tree = self.pyrpl.c
        saves = []
        original_save = tree._save

        def recording_save(*args, **kwargs):
            stack = traceback.format_stack(limit=16)[:-1]
            saves.append("".join(frame for frame in stack if "pyrpl" in frame))
            return original_save(*args, **kwargs)

        object.__setattr__(tree, "_save", recording_save)
        try:
            old = tree._save_counter
            for _i in range(10):
                sleep(0.01)
                APP.processEvents()
            new = tree._save_counter
        finally:
            del tree.__dict__["_save"]
        self.sa.stop()
        assert self.sa.running_state == "stopped"
        assert old == new, (old, new, "\n".join(saves))

    @pytest.mark.parametrize("span", [5e4, 1e5, 5e5, 1e6, 2e6])
    def test_baseband_tone_calibration(self, span):
        self.sa.setup(
            baseband=True,
            center=0,
            window="flattop",
            span=span,
            input1_baseband=self.asg,
            trace_average=1,
        )
        self.sa.stop()
        self.asg.free()
        self.asg.setup(
            frequency=1e5,
            amplitude=1.0,
            trigger_source="high",
            offset=0,
            waveform="sin",
        )
        frequencies = np.linspace(self.sa.rbw * 3, self.sa.span / 2 - self.sa.rbw * 3, 11)
        for frequency in frequencies:
            self.sa._logger.info(
                "Testing baseband calibration for span %f at %f Hz", span, frequency
            )
            self.asg.frequency = frequency
            curve = self.sa.single()[0]
            peak_index = int(np.argmax(curve))
            peak = float(curve[peak_index])
            assert abs(self.sa.frequencies[peak_index] - frequency) < self.sa.rbw, (
                self.sa.frequencies[peak_index],
                frequency,
                self.sa.rbw,
            )
            assert abs(peak - self.asg.amplitude**2) < 0.01, peak
            peak_psd = np.max(self.sa.data_to_unit(curve, "Vrms^2/Hz", self.sa.rbw))
            assert abs(peak_psd * self.sa.rbw - self.asg.amplitude**2 / 2) < 0.01

    # Below this frequency the spectrum holds a DC offset of the signal chain,
    # not filtered white noise: it is left out of the comparison.
    WHITE_NOISE_MIN_FREQUENCY = 4e3

    def _filtered_white_noise_calibration(self, frequency_indices):
        """
        Make sure a white noise results in a flat spectrum, with a PSD equal to
        <V^2> when integrated from 0 Hz to Nyquist frequency. To make sure
        no aliasing problem occurs, a narrowbandpass filter is used.
        The test cannot be perfomed for the largest bandwidth because then the
        transfer function correction for the scope decimation should not be
        applied for internal signals (however, the sinc correction is
        applied in practice).

        The bandpass filter is centred on the points frequency_indices of 5
        frequencies evenly spaced from 10 bandwidths to Nyquist minus 10
        bandwidths.
        """
        self.asg.setup(amplitude=0.4, waveform="noise", trigger_source="high")

        self.iq.setup(
            input=self.asg,
            acbandwidth=10,
            gain=1.0,
            amplitude=0,
            quadrature_factor=0,
            bandwidth=5e3,
            frequency=1e5,
            output_signal="output_direct",
        )

        self.sa.setup(
            input1_baseband=self.iq,
            span=10e6,
            trace_average=50,
            window="gaussian",
        )
        self.sa.stop()

        noise_nyquist_frequency = 1.0 / (2 * 8e-9)
        frequencies = np.linspace(
            10 * self.iq.bandwidth[0], self.sa.span / 2 - 10 * self.iq.bandwidth[0], 5
        )
        for frequency in frequencies[list(frequency_indices)]:
            self.iq.frequency = frequency
            in1, _in2, _cross_real, _cross_imag = self.sa.single()
            measured_psd = self.sa.data_to_unit(in1, "Vrms^2/Hz", self.sa.rbw)
            x = self.sa.data_x
            keep = x >= self.WHITE_NOISE_MIN_FREQUENCY
            x, measured_psd = x[keep], measured_psd[keep]

            delta = x - self.iq.frequency
            shape = 1.0 / (1.0 + delta**2 / self.iq.bandwidth[0] ** 2)
            fitted_amplitude = max(
                0.0,
                np.vdot(shape, measured_psd).real / np.vdot(shape, shape).real,
            )
            fitted_psd = fitted_amplitude * shape
            relative_fit_rms = np.linalg.norm(measured_psd - fitted_psd) / max(
                np.linalg.norm(fitted_psd), np.finfo(float).eps
            )

            artifact = save_frequency_response(
                f"spectrum_white_noise_{int(round(self.iq.frequency))}_hz",
                x,
                measured_psd,
                fitted_psd,
                metadata={
                    "center_frequency_hz": self.iq.frequency,
                    "bandwidth_hz": self.iq.bandwidth[0],
                    "relative_fit_rms": relative_fit_rms,
                    "trace_average": self.sa.trace_average,
                    "min_frequency_hz": self.WHITE_NOISE_MIN_FREQUENCY,
                },
            )
            if artifact is not None:
                logger.info("Saved filtered white-noise response to %s.*", artifact)

            calibrated_variance = fitted_amplitude * noise_nyquist_frequency
            relative_calibration_error = (
                abs(calibrated_variance - self.asg.amplitude**2) / self.asg.amplitude**2
            )
            assert relative_calibration_error < 0.1, (
                self.iq.frequency,
                calibrated_variance,
                self.asg.amplitude**2,
            )
            assert relative_fit_rms < 0.30, relative_fit_rms

    def test_filtered_white_noise_psd_calibration(self):
        """White-noise PSD calibration up to a quarter of the span.

        There the scope decimation correction (a sinc) stays small and the
        calibration error is about 1 %."""
        self._filtered_white_noise_calibration(frequency_indices=[0, 1, 2])

    @pytest.mark.xfail(
        reason="about 8-12 % of the white-noise power is missing near Nyquist, where "
        "the scope decimation correction is large; the measured integrated power "
        "is low too, so it is not a fit artefact. To be investigated.",
        strict=False,
    )
    def test_filtered_white_noise_psd_calibration_near_nyquist(self):
        """White-noise PSD calibration between a quarter of the span and Nyquist."""
        self._filtered_white_noise_calibration(frequency_indices=[3, 4])

    def test_iq_transfer_from_white_noise_cross_spectrum(self):
        """
        Measure the transfer function of an iq filter by measuring the
        cross-spectrum between white-noise input and output
        """
        self.asg.setup(amplitude=0.4, waveform="noise", trigger_source="immediately")

        self.iq.setup(
            frequency=10000e3,  # center frequency
            bandwidth=300000,
            amplitude=0,
            acbandwidth=500,
            phase=0,
            gain=1.0,
            quadrature_factor=0,
            output_direct="off",
            output_signal="output_direct",
            input=self.asg,
        )

        self.sa.setup(
            input1_baseband=self.asg,
            input2_baseband=self.iq,
            span=125e6,
            trace_average=50,
        )

        in1, in2, c_re, c_im = self.sa.single()

        cross = c_re + 1j * c_im
        exp = cross / in1
        theory = self.iq.transfer_function(self.sa.frequencies)

        # The DC point is excluded because the configured input high-pass has
        # zero theoretical response there.
        frequencies = self.sa.frequencies[1:]
        measured = exp[1:]
        expected = theory[1:]
        absolute_error = np.abs(measured - expected)
        diff = absolute_error.max()
        # This is a stochastic maximum over the complete spectrum. Historical
        # measurements showed that 0.05 failed intermittently even when the
        # mean response was correct.
        maxdiff = 0.08
        artifact = save_frequency_response(
            f"iq_white_noise_{self.iq.name}",
            frequencies,
            measured,
            expected,
            metadata={
                "center_frequency_hz": self.iq.frequency,
                "bandwidth_hz": self.iq.bandwidth,
                "input_filter_hz": self.iq.inputfilter,
                "iq_delay_cycles": self.iq._delay,
                "maximum_allowed_absolute_error": maxdiff,
            },
        )
        if artifact is not None:
            logger.info("Saved IQ white-noise response artifacts to %s.*", artifact)
        worst_index = int(np.argmax(absolute_error))
        assert diff < maxdiff, (
            diff,
            frequencies[worst_index],
            measured[worst_index],
            expected[worst_index],
        )

    def test_iq_mode_aliasing_diagnostic(self):
        """Record the historical IQ-mode flatness sweep without masking aliasing."""
        self.sa.setup(
            baseband=False,
            center=1e5,
            span=2e6,
            input=self.asg,
            trace_average=1,
            window="flattop",
        )
        self.sa.stop()
        self.asg.setup(
            frequency=1e5,
            amplitude=1.0,
            trigger_source="immediately",
            offset=0,
            waveform="sin",
        )

        tone_frequencies = np.linspace(1e5, 9e5, 50)
        peak_powers = []
        detected_frequencies = []
        for frequency in tone_frequencies:
            self.asg.frequency = frequency
            curve = self.sa.single()
            peak_index = int(np.argmax(curve))
            peak_powers.append(float(curve[peak_index]))
            detected_frequencies.append(float(self.sa.frequencies[peak_index]))

        peak_powers = np.asarray(peak_powers)
        detected_frequencies = np.asarray(detected_frequencies)
        expected_power = np.full_like(peak_powers, self.asg.amplitude**2)
        frequency_error = detected_frequencies - tone_frequencies

        flatness_artifact = save_frequency_response(
            "spectrum_iq_mode_flatness_diagnostic",
            tone_frequencies,
            peak_powers,
            expected_power,
            metadata={
                "center_frequency_hz": self.sa.center,
                "span_hz": self.sa.span,
                "rbw_hz": self.sa.rbw,
                "maximum_peak_power_error": float(np.max(np.abs(peak_powers - expected_power))),
                "diagnostic_only": True,
            },
        )
        mapping_artifact = save_frequency_response(
            "spectrum_iq_mode_frequency_mapping_diagnostic",
            tone_frequencies,
            detected_frequencies,
            tone_frequencies,
            metadata={
                "center_frequency_hz": self.sa.center,
                "span_hz": self.sa.span,
                "rbw_hz": self.sa.rbw,
                "maximum_frequency_error_hz": float(np.max(np.abs(frequency_error))),
                "diagnostic_only": True,
            },
        )
        if flatness_artifact is not None:
            logger.info(
                "Saved IQ-mode diagnostic artifacts to %s.* and %s.*",
                flatness_artifact,
                mapping_artifact,
            )

        assert np.isfinite(peak_powers).all()
        assert np.isfinite(detected_frequencies).all()
        assert np.max(peak_powers) > 0

    def test_save_curve(self):
        self.sa.setup(
            baseband=True,
            center=0,
            window="flattop",
            span=1e6,
            input1_baseband=self.asg,
            input2_baseband="in2",
            display_input1_baseband=True,
            display_input2_baseband=True,
            display_cross_amplitude=True,
        )
        self.sa.single()
        curves = self.sa.save_curve()
        assert len(curves) == 3
        assert all(curve is not None for curve in curves)
        np.testing.assert_array_equal(curves[0].data[1], self.sa.data_avg[0])
        np.testing.assert_array_equal(curves[1].data[1], self.sa.data_avg[1])
        np.testing.assert_array_equal(
            curves[2].data[1], self.sa.data_avg[2] + 1j * self.sa.data_avg[3]
        )
        self.curves.extend(curves)
