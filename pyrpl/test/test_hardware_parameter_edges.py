from types import SimpleNamespace

import numpy as np
import pytest

from pyrpl.attributes import FilterRegister
from pyrpl.hardware_modules.iir.iir import IIR
from pyrpl.hardware_modules.iq import Iq


class RegisterReadStub:
    def __init__(self, values):
        self.values = values

    def _read(self, address):
        return self.values[address]


def test_filter_register_without_hardware_stages_only_accepts_bypass():
    register = FilterRegister(
        0x120,
        filterstages=0x220,
        shiftbits=0x224,
        minbw=0x228,
    )
    register.name = "inputfilter"
    module = RegisterReadStub({0x220: 0, 0x224: 5, 0x228: 10})

    assert register.valid_frequencies(module) == [0]
    assert register.validate_and_normalize(module, 0) == 0
    assert register.validate_and_normalize(module, 1e6) == 0


@pytest.mark.parametrize("value", [-3.999, -1.25, -(2**-21), 0, 2**-21, 1.25, 3.999])
def test_iir_fixed_point_roundtrip_below_32_bits(value):
    iir = object.__new__(IIR)
    high, low = iir._from_double(value, bitlength=24, shift=21)
    decoded = iir._to_double(high, low, bitlength=24, shift=21)

    assert decoded == pytest.approx(value, abs=2**-22)


def test_iir_fixed_point_rejects_unsupported_bitlength():
    iir = object.__new__(IIR)

    with pytest.raises(ValueError, match="between 1 and 64"):
        iir._to_double(0, 0, bitlength=0)


def _iq_model(**overrides):
    values = {
        "gain": 1.0,
        "bandwidth": [300e3],
        "frequency": 10e6,
        "inputfilter": 0,
        # the module's pipeline delays (cycles), kept in sync with Iq
        "_delay": Iq._delay,
        "_quadrature_delay": Iq._quadrature_delay,
        "_frequency_correction": 1.0,
        "phase": 0.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_iq_pipeline_delay_at_center_is_quadrature_delay():
    iq = _iq_model()

    response = Iq.transfer_function(iq, np.array([iq.frequency]))[0]
    three_cycle_carrier_delay = np.exp(-1j * 3 * 8e-9 * iq.frequency * 2 * np.pi)

    assert response == pytest.approx(three_cycle_carrier_delay)


def test_iq_input_highpass_is_finite_and_zero_at_dc():
    iq = _iq_model(inputfilter=-500.0)

    response = Iq.transfer_function(iq, np.array([0.0]))[0]

    assert np.isfinite(response)
    assert response == 0
