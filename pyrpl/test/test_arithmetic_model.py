import json
from pathlib import Path

import numpy as np
import pytest

from pyrpl.fpga_profiles import FpgaProfile
from pyrpl.hardware_modules.arithmetic import Arithmetic, arithmetic_result
from pyrpl.hardware_modules.dsp import dsp_addr_base
from pyrpl.redpitaya_client import DummyClient


def test_arithmetic_polynomial_and_product_model():
    polynomial = arithmetic_result(
        "polynomial",
        np.array([-0.5, 0.25]),
        np.array([0.25, 0.5]),
        coefficient_a=0.5,
        coefficient_b=2.0,
        exponent_a=1,
        exponent_b=2,
    )
    np.testing.assert_allclose(polynomial, [-0.125, 0.625])

    product = arithmetic_result("product", np.array([-0.5, 0.25]), 0.5, coefficient_a=2.0)
    np.testing.assert_allclose(product, [-0.5, 0.25])


def test_arithmetic_ratio_model_and_protection():
    ratio = arithmetic_result(
        "ratio",
        np.array([0.25, -0.25, 0.0, 0.25]),
        np.array([0.5, -0.5, 0.0, 0.0]),
        coefficient_a=-0.5,
        denominator_min=1 / 8192,
    )
    np.testing.assert_allclose(ratio[:3], [-0.25, -0.25, 0.0])
    assert ratio[3] == pytest.approx(-1.0)


def test_arithmetic_model_rejects_unknown_operation():
    with pytest.raises(ValueError, match="Unknown arithmetic operation"):
        arithmetic_result("power", 0.1, 0.2)


def test_arithmetic_profile_contract_and_register_map():
    manifest_path = (
        Path(__file__).parents[1] / "fpga" / "profiles" / "arithmetic" / "manifest.template.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert {"arithmetic", "pid_derivative"} <= set(manifest["capabilities"])
    assert "pid_input_filters" not in manifest["capabilities"]
    assert manifest["hardware"]["pid_input_filter_stages"] == 0
    assert manifest["hardware"]["arithmetic_abi"] == 0x41524901
    assert manifest["timing"]["arithmetic"] == {"_delay": 5, "_ratio_delay": 17}
    assert Arithmetic.input_b.address == 0x14
    assert Arithmetic.operation.address == 0x100
    assert Arithmetic.abi_version.address == 0x200

    profile = FpgaProfile(
        id=manifest["id"],
        description=manifest["description"],
        abi_version=manifest["abi_version"],
        capabilities=frozenset(manifest["capabilities"]),
        hardware_modules=tuple(manifest["hardware_modules"]),
        software_managers=tuple(manifest["software_managers"]),
        timing=manifest["timing"],
        hardware=manifest["hardware"],
        bitstream=Path(),
        dtbo=Path(),
    )
    dummy = DummyClient(profile)
    assert dummy.read_fpgamemory(dsp_addr_base("arithmetic") + 0x200) == 0x41524901
