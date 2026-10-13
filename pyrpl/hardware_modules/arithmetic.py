"""Two-input fixed-point arithmetic FPGA module."""

from collections import OrderedDict

import numpy as np

from ..attributes import FloatRegister, IntRegister, SelectRegister
from ..widgets.module_widgets import ArithmeticWidget
from .dsp import DspModule, InputSelectRegister, all_inputs


def arithmetic_result(
    operation,
    input_a,
    input_b,
    coefficient_a=1.0,
    coefficient_b=0.0,
    exponent_a=1,
    exponent_b=1,
    denominator_min=1 / 2**13,
):
    """Return the ideal normalized result of an arithmetic operation."""
    input_a = np.asarray(input_a)
    input_b = np.asarray(input_b)
    if operation == "polynomial":
        result = coefficient_a * input_a**exponent_a
        result += coefficient_b * input_b**exponent_b
    elif operation == "product":
        result = coefficient_a * input_a * input_b
    elif operation == "ratio":
        protected = np.abs(input_b) < denominator_min
        safe_denominator = np.where(protected, 1.0, input_b)
        result = coefficient_a * input_a / safe_denominator
        saturation_sign = np.where(
            np.signbit(coefficient_a) ^ np.signbit(input_a) ^ np.signbit(input_b),
            -1.0,
            1.0,
        )
        result = np.where(protected & (input_a != 0), saturation_sign, result)
        result = np.where(protected & (input_a == 0), 0.0, result)
    else:
        raise ValueError(f"Unknown arithmetic operation {operation!r}")
    return np.clip(result, -1.0, (2**13 - 1) / 2**13)


class Arithmetic(DspModule):
    """Combine two independently routed signals in real time.

    Signals use the normal PyRPL convention in which the signed 14-bit FPGA
    range represents approximately -1 to +1.  Polynomial exponents are
    intentionally limited to one and two so the implementation remains small
    and deterministic at 125 MHz.
    """

    _widget_class = ArithmeticWidget
    _setup_attributes = [
        "operation",
        "input",
        "input_b",
        "coefficient_a",
        "exponent_a",
        "coefficient_b",
        "exponent_b",
        "input_delay_a",
        "input_delay_b",
        "denominator_min",
        "output_direct",
    ]
    _gui_attributes = _setup_attributes

    # The polynomial and product datapaths contain input/power, coefficient,
    # and output-saturation registers. The ratio path uses an additional
    # thirteen-stage, one-result-per-clock divider.
    _delay = 5
    _ratio_delay = 17

    operation = SelectRegister(
        0x100,
        options=OrderedDict((("polynomial", 0), ("product", 1), ("ratio", 2))),
        default="polynomial",
        doc=(
            "polynomial: a*input^p + b*input_b^q; product: a*input*input_b; ratio: a*input/input_b"
        ),
    )
    coefficient_a = FloatRegister(
        0x104,
        bits=24,
        norm=2**16,
        default=1.0,
        doc="coefficient a",
    )
    coefficient_b = FloatRegister(
        0x108,
        bits=24,
        norm=2**16,
        default=0.0,
        doc="coefficient b (polynomial mode only)",
    )
    exponent_a = SelectRegister(
        0x10C,
        options=OrderedDict(((1, 0), (2, 1))),
        default=1,
        doc="exponent of the first polynomial input",
    )
    exponent_b = SelectRegister(
        0x110,
        options=OrderedDict(((1, 0), (2, 1))),
        default=1,
        doc="exponent of the second polynomial input",
    )
    input_delay_a = IntRegister(
        0x114,
        bits=3,
        min=0,
        max=7,
        default=0,
        doc="additional delay of the first input [FPGA cycles]",
    )
    input_delay_b = IntRegister(
        0x118,
        bits=3,
        min=0,
        max=7,
        default=0,
        doc="additional delay of the second input [FPGA cycles]",
    )
    denominator_min = FloatRegister(
        0x11C,
        bits=14,
        norm=2**13,
        signed=False,
        min=1 / 2**13,
        max=(2**14 - 1) / 2**13,
        default=1 / 2**13,
        doc="minimum absolute denominator used by ratio mode",
    )
    input_b = InputSelectRegister(
        0x14,
        options=all_inputs,
        default="in2",
        doc="selects the second arithmetic input",
    )
    abi_version = IntRegister(
        0x200,
        doc="Arithmetic hardware ABI signature ('ARI' followed by its revision)",
    )

    @property
    def input_a(self):
        """Alias for the ordinary DSP input."""
        return self.input

    @input_a.setter
    def input_a(self, value):
        self.input = value

    @property
    def denominator_too_small(self):
        """Whether the most recent ratio result used denominator protection."""
        return bool(self._read(0x120) & 1)

    @property
    def latency_cycles(self):
        """Datapath latency, excluding the configured per-input delays."""
        return self._ratio_delay if self.operation == "ratio" else self._delay

    def evaluate(self, input_a, input_b):
        """Evaluate the ideal normalized operation, including output clipping.

        This helper models the arithmetic expression and denominator policy;
        it deliberately does not model intermediate fixed-point rounding.
        """
        return arithmetic_result(
            self.operation,
            input_a,
            input_b,
            coefficient_a=self.coefficient_a,
            coefficient_b=self.coefficient_b,
            exponent_a=self.exponent_a,
            exponent_b=self.exponent_b,
            denominator_min=self.denominator_min,
        )
