"""Select options given as strings, as the GUI combo boxes and text configuration
files provide them."""

import pytest

from pyrpl.redpitaya import RedPitaya


@pytest.fixture
def fake_arithmetic_redpitaya():
    rp = RedPitaya(config=None, hostname="_FAKE_", fpga_profile="arithmetic", gui=False)
    yield rp
    rp.end_all()


def test_integer_select_option_accepts_its_string(fake_arithmetic_redpitaya):
    arithmetic = fake_arithmetic_redpitaya.arithmetic
    # the options of the exponents are the integers 1 and 2
    arithmetic.exponent_a = "2"
    assert arithmetic.exponent_a == 2
    arithmetic.exponent_a = 1
    assert arithmetic.exponent_a == 1
    with pytest.raises(ValueError):
        arithmetic.exponent_a = "3"
