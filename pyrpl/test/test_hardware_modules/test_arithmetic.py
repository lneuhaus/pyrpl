import time

import numpy as np
import pytest

from pyrpl.redpitaya_client import DummyClient


@pytest.mark.requires_fpga("arithmetic")
def test_arithmetic_dc_operations(hardware_session):
    """Check polynomial, product, ratio, and denominator protection."""
    rp = hardware_session.rp
    if isinstance(rp.client, DummyClient):
        pytest.skip("requires real FPGA signal processing")

    arithmetic = rp.arithmetic
    source_a = rp.asg0
    source_b = rp.asg1
    original_arithmetic = arithmetic.setup_attributes.copy()
    original_a = source_a.setup_attributes.copy()
    original_b = source_b.setup_attributes.copy()

    def measured_output():
        time.sleep(0.002)
        return rp.sampler.stats("arithmetic", t=0.002)[0]

    try:
        assert arithmetic.abi_version == 0x41524901
        source_a.setup(waveform="dc", amplitude=0, offset=0.25, output_direct="off")
        source_b.setup(waveform="dc", amplitude=0, offset=0.5, output_direct="off")

        arithmetic.setup(
            operation="polynomial",
            input="asg0",
            input_b="asg1",
            coefficient_a=1,
            exponent_a=1,
            coefficient_b=0.5,
            exponent_b=2,
            input_delay_a=0,
            input_delay_b=0,
            denominator_min=1 / 8192,
            output_direct="off",
        )
        assert measured_output() == pytest.approx(0.375, abs=2e-3)

        arithmetic.operation = "product"
        arithmetic.coefficient_a = 2
        assert measured_output() == pytest.approx(0.25, abs=2e-3)

        arithmetic.operation = "ratio"
        arithmetic.coefficient_a = 0.5
        assert measured_output() == pytest.approx(0.25, abs=2e-3)
        assert not arithmetic.denominator_too_small

        source_b.offset = 0
        assert measured_output() > 0.99
        assert arithmetic.denominator_too_small
    finally:
        arithmetic.setup_attributes = original_arithmetic
        source_a.setup_attributes = original_a
        source_b.setup_attributes = original_b


@pytest.mark.requires_fpga("arithmetic")
@pytest.mark.parametrize(
    "operation,coefficient,expected_delay", [("product", 2, 5), ("ratio", 0.5, 17)]
)
def test_arithmetic_dynamic_latency(hardware_session, operation, coefficient, expected_delay):
    """Measure both arithmetic pipelines against their common input trace.

    ASG0 supplies a square wave and ASG1 supplies +0.5. With a coefficient of
    two, product mode reproduces ASG0. With a coefficient of one half, ratio
    mode does the same. The two scope traces therefore have identical edges,
    separated only by the selected arithmetic pipeline latency.
    """
    rp = hardware_session.rp
    if isinstance(rp.client, DummyClient):
        pytest.skip("requires real FPGA signal processing")

    arithmetic = rp.arithmetic
    source_a = rp.asg0
    source_b = rp.asg1
    scope = rp.scope
    original_arithmetic = arithmetic.setup_attributes.copy()
    original_a = source_a.setup_attributes.copy()
    original_b = source_b.setup_attributes.copy()
    original_scope = scope.setup_attributes.copy()

    def rising_edges(values):
        threshold = 0.5 * sum(np.percentile(values, [10, 90]))
        return np.flatnonzero((values[:-1] < threshold) & (values[1:] >= threshold)) + 1

    try:
        source_a.setup(
            waveform="square",
            frequency=1e6,
            amplitude=0.1,
            offset=0,
            output_direct="off",
            trigger_source="immediately",
        )
        source_b.setup(waveform="dc", amplitude=0, offset=0.5, output_direct="off")
        arithmetic.setup(
            operation=operation,
            input="asg0",
            input_b="asg1",
            coefficient_a=coefficient,
            coefficient_b=0,
            exponent_a=1,
            exponent_b=1,
            input_delay_a=0,
            input_delay_b=0,
            denominator_min=1 / 8192,
            output_direct="off",
        )
        scope.setup(
            input1="asg0",
            input2="arithmetic",
            duration=scope.durations[0],
            trigger_source="immediately",
            trace_average=1,
            average=False,
        )
        input_trace, output_trace = scope.single(timeout=4)
        input_edges = rising_edges(input_trace)
        output_edges = rising_edges(output_trace)
        lags = []
        for input_edge in input_edges:
            candidates = output_edges[
                (output_edges >= input_edge + expected_delay - 2)
                & (output_edges <= input_edge + expected_delay + 2)
            ]
            if len(candidates):
                lags.append(int(candidates[0] - input_edge))

        assert len(lags) >= 10, f"Only {len(lags)} {operation} edges matched"
        assert np.median(lags) == pytest.approx(expected_delay, abs=1), lags
        assert np.max(np.abs(np.asarray(lags) - expected_delay)) <= 1, lags
    finally:
        scope.stop()
        scope.setup_attributes = original_scope
        arithmetic.setup_attributes = original_arithmetic
        source_a.setup_attributes = original_a
        source_b.setup_attributes = original_b
