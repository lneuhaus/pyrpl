from types import SimpleNamespace

import numpy as np
import pytest

from pyrpl.hardware_modules.pid import Pid
from pyrpl.software_modules.lockbox.output import OutputSignal


def _derivative_register_stub(frequency_correction=1.0, enabled=True):
    capabilities = {"pid_derivative"} if enabled else set()
    return SimpleNamespace(
        _frequency_correction=frequency_correction,
        _rp=SimpleNamespace(
            fpga_profile=SimpleNamespace(capabilities=capabilities),
        ),
    )


@pytest.mark.parametrize("frequency", [5e3, 100e3, -250e3])
def test_derivative_coefficient_sign_and_scaling(frequency):
    module = _derivative_register_stub(frequency_correction=1.0002)
    register = Pid.d

    encoded = register.from_python(module, frequency)
    decoded = register.to_python(module, encoded)

    assert np.sign(decoded) == np.sign(frequency)
    assert decoded == pytest.approx(frequency, rel=2e-4)


def test_derivative_is_disabled_outside_derivative_profile():
    module = _derivative_register_stub(enabled=False)

    assert Pid.d.validate_and_normalize(module, 0) == 0
    with pytest.raises(ValueError, match="pid_derivative"):
        Pid.d.validate_and_normalize(module, 100e3)


@pytest.mark.parametrize("ratio", [3.0, 5.0, 10.0])
def test_derivative_filter_factor_selects_nearest_fpga_cutoff(ratio):
    derivative_frequency = 100e3
    requested_cutoff = ratio * derivative_frequency
    shift = Pid._select_derivative_filter_shift(requested_cutoff)
    actual_cutoff = Pid._derivative_filter_cutoff(shift)
    available = np.asarray(
        [
            Pid._derivative_filter_cutoff(candidate)
            for candidate in range(1, Pid._DERIVATIVE_FILTER_MAX_SHIFT + 1)
        ]
    )

    assert Pid.derivative_filter_ratio.validate_and_normalize(None, ratio) == ratio
    assert abs(np.log(actual_cutoff / requested_cutoff)) == pytest.approx(
        np.min(np.abs(np.log(available / requested_cutoff)))
    )


def test_derivative_filter_factor_is_limited_to_three_and_ten():
    descriptor = Pid.derivative_filter_ratio

    assert descriptor.validate_and_normalize(None, 2.0) == 3.0
    assert descriptor.validate_and_normalize(None, 12.0) == 10.0


def test_exact_registered_derivative_transfer_function():
    frequencies = np.asarray([20e3, 100e3, 750e3])
    derivative_frequency = 80e3
    shift = 6
    correction = 1.0001
    sample_period = 8e-9 / correction
    zinv = np.exp(-1j * 2 * np.pi * frequencies * sample_period)
    alpha = 2.0**-shift
    registered_filter = alpha * zinv**2 / (1 - zinv + alpha * zinv**2)
    expected = (1 - zinv) / (2 * np.pi * sample_period * derivative_frequency) * registered_filter

    response = Pid._pid_transfer_function(
        frequencies,
        p=0,
        i=0,
        d=derivative_frequency,
        frequency_correction=correction,
        derivative_filter_shift=shift,
    )

    assert response == pytest.approx(expected)
    assert np.all(np.imag(response) > 0)
    assert Pid._pid_transfer_function(
        frequencies,
        p=0,
        i=0,
        d=-derivative_frequency,
        frequency_correction=correction,
        derivative_filter_shift=shift,
    ) == pytest.approx(-expected)


def test_combined_pid_response_is_sum_of_discrete_branches():
    frequencies = np.asarray([10e3, 100e3, 1e6])
    combined = Pid._pid_transfer_function(
        frequencies, p=0.4, i=2e3, d=150e3, derivative_filter_shift=5
    )
    separate = Pid._pid_transfer_function(
        frequencies, p=0.4, i=2e3, d=0
    ) + Pid._pid_transfer_function(frequencies, p=0, i=0, d=150e3, derivative_filter_shift=5)

    assert combined == pytest.approx(separate)


def test_default_profile_transfer_does_not_read_derivative_registers():
    class DefaultPidModel:
        p = 1.0
        i = 0.0
        inputfilter = 0
        _delay = 4
        _frequency_correction = 1.0
        _rp = SimpleNamespace(
            fpga_profile=SimpleNamespace(capabilities={"pid"}),
        )

        @property
        def d(self):
            raise AssertionError("default profile must not read d")

        @property
        def _derivative_filter_shift_register(self):
            raise AssertionError("default profile must not read derivative filter shift")

    response = Pid.transfer_function(DefaultPidModel(), np.asarray([100e3]))

    assert np.isfinite(response[0])


@pytest.mark.parametrize("external_gain, stage_gain", [(4.0, 2.0), (-2.0, 0.5)])
def test_lockbox_derivative_uses_inverse_gain_scaling(external_gain, stage_gain):
    p, i, d = OutputSignal._scaled_pid_gains(
        p=0.25,
        i=2e3,
        d=100e3,
        external_loop_gain=external_gain,
        gain_factor=stage_gain,
    )

    scale = stage_gain / external_gain
    assert p == pytest.approx(0.25 * scale)
    assert i == pytest.approx(2e3 * scale)
    assert d == pytest.approx(100e3 / scale)
    # Multiplication by the external gain reproduces the requested stage gain
    # for the derivative coefficient 1/d, just as for P and I.
    assert external_gain / d == pytest.approx(stage_gain / 100e3)


def test_lockbox_disabled_stage_disables_derivative():
    assert OutputSignal._scaled_pid_gains(1, 2, 3, 4, 0) == (0, 0, 0)


def test_lockbox_assisted_design_keeps_requested_derivative_crossover():
    requested_crossover = 100e3
    actuator_cutoff = 20e3
    derivative_frequency = 400e3
    ratio = 5.0
    p, i = OutputSignal._assisted_pi_gains(
        requested_crossover,
        actuator_cutoff,
        d=derivative_frequency,
        derivative_filter_ratio=ratio,
    )
    response = OutputSignal._design_pid_response(
        np.asarray([requested_crossover]),
        p=p,
        i=i,
        d=derivative_frequency,
        derivative_filter_ratio=ratio,
        analog_filter_cutoff=actuator_cutoff,
    )

    assert abs(response[0]) == pytest.approx(1.0, rel=1e-12)
    assert i / p == pytest.approx(actuator_cutoff)


def test_lockbox_manual_design_reports_derivative_crossover():
    p = 5.0
    i = 100e3
    d = 400e3
    ratio = 5.0
    actuator_cutoff = i / p
    crossover = OutputSignal._pid_unity_frequency(
        p,
        i,
        d,
        ratio,
        actuator_cutoff,
    )
    response = OutputSignal._design_pid_response(
        np.asarray([crossover]),
        p=p,
        i=i,
        d=d,
        derivative_filter_ratio=ratio,
        analog_filter_cutoff=actuator_cutoff,
    )

    assert abs(response[0]) == pytest.approx(1.0, rel=2e-4)
    assert crossover != pytest.approx(i)
