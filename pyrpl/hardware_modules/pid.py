"""
We have already seen some use of the pid module above. There are three
PID modules available: pid0 to pid2.

.. code:: python

    print(r.pid0.help())

Proportional and integral gain
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

    #make shortcut
    pid = r.pid0

    #turn off by setting gains to zero
    pid.p,pid.i = 0,0
    print("P/I gain when turned off:", pid.i,pid.p)

.. code:: python

    # small nonzero numbers set gain to minimum value - avoids rounding off to zero gain
    pid.p = 1e-100
    pid.i = 1e-100
    print("Minimum proportional gain: ", pid.p)
    print("Minimum integral unity-gain frequency [Hz]: ", pid.i)

.. code:: python

    # saturation at maximum values
    pid.p = 1e100
    pid.i = 1e100
    print("Maximum proportional gain: ", pid.p)
    print("Maximum integral unity-gain frequency [Hz]: ", pid.i)

Control with the integral value register
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

    import numpy as np
    #make shortcut
    pid = r.pid0

    # set input to asg1
    pid.input = "asg1"

    # set asg to constant 0.1 Volts
    r.asg1.setup(waveform="dc", offset = 0.1)

    # set scope ch1 to pid0
    r.scope.input1 = 'pid0'

    #turn off the gains for now
    pid.p,pid.i = 0, 0

    #set integral value to zero
    pid.ival = 0

    #prepare data recording
    from time import time
    times, ivals, outputs = [], [], []

    # turn on integrator to whatever negative gain
    pid.i = -10

    # set integral value above the maximum positive voltage
    pid.ival = 1.5

    #take 1000 points - jitter of the ethernet delay will add a noise here but we dont care
    for n in range(1000):
        times.append(time())
        ivals.append(pid.ival)
        outputs.append(r.scope.voltage_in1)

    #plot
    import matplotlib.pyplot as plt
    %matplotlib inline
    times = np.array(times)-min(times)
    plt.plot(times,ivals,times,outputs)
    plt.xlabel("Time [s]")
    plt.ylabel("Voltage")

Again, what do we see? We set up the pid module with a constant
(positive) input from the ASG. We then turned on the integrator (with
negative gain), which will inevitably lead to a slow drift of the output
towards negative voltages (blue trace). We had set the integral value
above the positive saturation voltage, such that it takes longer until
it reaches the negative saturation voltage. The output of the pid module
is bound to saturate at +- 1 Volts, which is clearly visible in the
green trace. The value of the integral is internally represented by a 32
bit number, so it can practically take arbitrarily large values compared
to the 14 bit output. You can set it within the range from +4 to -4V,
for example if you want to exloit the delay, or even if you want to
compensate it with proportional gain.

Input filters
^^^^^^^^^^^^^

The pid module has one more feature: A bank of 4 input filters in
series. These filters can be either off (bandwidth=0), lowpass
(bandwidth positive) or highpass (bandwidth negative). The way these
filters were implemented demands that the filter bandwidths can only
take values that scale as the powers of 2.

.. code:: python

    # off by default
    r.pid0.inputfilter

.. code:: python

    # minimum cutoff frequency is 1.1 Hz, maximum 3.1 MHz (for now)
    r.pid0.inputfilter = [1,1e10,-1,-1e10]
    print(r.pid0.inputfilter)

.. code:: python

    # not setting a coefficient turns that filter off
    r.pid0.inputfilter = [0,4,8]
    print(r.pid0.inputfilter)

.. code:: python

    # setting without list also works
    r.pid0.inputfilter = -2000
    print(r.pid0.inputfilter)

.. code:: python

    # turn off again
    r.pid0.inputfilter = []
    print(r.pid0.inputfilter)

You should now go back to the Scope and ASG example above and play
around with the setting of these filters to convince yourself that they
do what they are supposed to.
"""

from functools import lru_cache

import numpy as np
from qtpy import QtCore

from ..attributes import (
    BoolRegister,
    FloatProperty,
    FloatRegister,
    GainRegister,
    IntRegister,
    SelectRegister,
)
from ..modules import SignalLauncher
from ..pyrpl_utils import sorted_dict
from ..widgets.module_widgets import PidWidget
from .dsp import PauseRegister
from .filter import FilterModule


class IValAttribute(FloatProperty):
    """
    Attribute for integrator value
    """

    def get_value(self, obj):
        return float(obj._to_pyint(obj._read(0x100), bitlength=16)) / 2**13
        # bitlength used to be 32 until 16/7/2016
        # still, FPGA has an asymmetric representation for reading and writing
        # from/to this register

    def set_value(self, obj, value):
        """set the value of the register holding the integrator's sum [volts]"""
        return obj._write(0x100, obj._from_pyint(int(round(value * 2**13)), bitlength=16))


class SignalLauncherPid(SignalLauncher):
    update_ival = QtCore.Signal()

    # the widget decides at the other hand if it has to be done or not
    # depending on the visibility
    def __init__(self, module):
        super().__init__(module)
        self.timer_ival = QtCore.QTimer()
        self.timer_ival.setInterval(1000)  # max. refresh rate: 1 Hz
        self.timer_ival.timeout.connect(self.update_ival)
        self.timer_ival.setSingleShot(False)
        self.timer_ival.start()

    def _clear(self):
        """
        kill all timers
        """
        self.timer_ival.stop()
        super()._clear()


class DerivativeGainRegister(GainRegister):
    """Derivative unity-gain frequency backed by an inverse gain register."""

    def _capability_available(self, obj):
        try:
            return "pid_derivative" in obj._rp.fpga_profile.capabilities
        except AttributeError:
            return False

    def _signed_register_value(self, value):
        value = int(value) & (2**self.bits - 1)
        if value >= 2 ** (self.bits - 1):
            value -= 2**self.bits
        return value

    def to_python(self, obj, value):
        value = self._signed_register_value(value)
        if value == 0:
            return 0.0
        return self.norm * obj._frequency_correction / value

    def get_value(self, obj):
        if not self._capability_available(obj):
            return 0.0
        return super().get_value(obj)

    def from_python(self, obj, value):
        if value == 0:
            return 0
        raw = int(round(self.norm * obj._frequency_correction / float(value)))
        raw = min(max(raw, -(2 ** (self.bits - 1))), 2 ** (self.bits - 1) - 1)
        if raw == 0:
            raw = 1 if value > 0 else -1
        return raw & (2**self.bits - 1)

    def validate_and_normalize(self, obj, value):
        value = float(value)
        if not np.isfinite(value):
            raise ValueError("PID derivative frequency must be finite")
        if value != 0 and not self._capability_available(obj):
            raise ValueError("PID derivative gain requires the 'pid_derivative' FPGA profile")
        return self.to_python(obj, self.from_python(obj, value))

    def set_value(self, obj, value):
        super().set_value(obj, value)
        obj._update_derivative_filter_shift()


class DerivativeFilterRatio(FloatProperty):
    """Ratio N between derivative roll-off and unity-gain frequencies."""

    def set_value(self, obj, value):
        super().set_value(obj, value)
        obj._update_derivative_filter_shift()


class Pid(FilterModule):
    """
    A proportional/Integrator/Differential filter.

    The PID filter consists of a 4th order filter input stage, followed by a
    proportional and integral stage in parallel.

    The derivative stage is available only with the experimental
    ``pid_derivative`` FPGA profile. Its noise-limiting roll-off can be set
    between ``3 / tau_d`` and ``10 / tau_d``.

    Example:

    .. code-block :: python

        from pyrpl import Pyrpl
        pid = Pyrpl().rp.pid0

        # set a second order low-pass filter with 100 Hz cutoff frequency
        pid.inputfilter = [100, 100]
        # set asg0 as input
        pid.input = 'asg0'
        # setpoint at -0.1
        pid.setpoint = -0.1
        # integral gain at 0.1
        pid.i = 0.1
        # proportional gain at 0.1
        pid.p = 0.1

    .. code-block :: python

        >>> print(pid.ival)
        0.43545

    .. code-block :: python

        >>> print(pid.ival)
        0.763324
    """

    _widget_class = PidWidget
    _signal_launcher = SignalLauncherPid
    _setup_attributes = [
        "input",
        "output_direct",
        "setpoint",
        "p",
        "i",
        # "d",
        "inputfilter",
        "max_voltage",
        "min_voltage",
        "pause_gains",
        "paused",
        "differential_mode_enabled",
    ]
    _gui_attributes = _setup_attributes + ["ival"]

    # the function is here so the metaclass generates a setup(**kwds) function
    def _setup(self):
        """
        sets up the pid (just setting the attributes is OK).
        """
        pass

    # Effective latency from the selected DSP input to output_signal. Hardware
    # NA measurements over 10 MHz resolve this as four complete sample cycles.
    _delay = 4
    # Profiles that enable the dedicated PID input register override this to 5.

    _PSR = 12  # Register(0x200)

    _ISR = 32  # Register(0x204)

    _DSR = 10  # Register(0x208)

    _GAINBITS = 24  # Register(0x20C)
    _DERIVATIVE_FILTER_MAX_SHIFT = 24
    _DERIVATIVE_NORM = 2**_DSR / (2.0 * np.pi * 8e-9)

    ival = IValAttribute(
        min=-4,
        max=4,
        increment=8.0 / 2**16,
        doc="Current value of the integrator memory (i.e. pid output voltage offset)",
    )

    setpoint = FloatRegister(0x104, bits=14, norm=2**13, doc="pid setpoint [volts]")

    min_voltage = FloatRegister(0x124, bits=14, norm=2**13, doc="minimum output signal [volts]")
    max_voltage = FloatRegister(0x128, bits=14, norm=2**13, doc="maximum output signal [volts]")

    p = GainRegister(0x108, bits=_GAINBITS, norm=2**_PSR, doc="pid proportional gain [1]")
    i = GainRegister(
        0x10C,
        bits=_GAINBITS,
        norm=2**_ISR * 2.0 * np.pi * 8e-9,
        doc="pid integral unity-gain frequency [Hz]",
    )
    d = DerivativeGainRegister(
        0x110,
        bits=_GAINBITS,
        norm=_DERIVATIVE_NORM,
        invert=True,
        min=-_DERIVATIVE_NORM,
        max=_DERIVATIVE_NORM,
        increment=_DERIVATIVE_NORM / (2 ** (_GAINBITS - 1) - 1),
        log_increment=True,
        doc="Derivative unity-gain frequency [Hz]. Zero disables it.",
    )
    derivative_filter_ratio = DerivativeFilterRatio(
        default=5.0,
        min=3.0,
        max=10.0,
        increment=0.1,
        doc="Derivative roll-off frequency as a multiple of 1 / tau_d.",
    )
    _derivative_filter_shift_register = IntRegister(
        0x114,
        bits=6,
        min=1,
        max=_DERIVATIVE_FILTER_MAX_SHIFT,
        doc="Internal quantized derivative-filter shift.",
    )

    @classmethod
    @lru_cache(maxsize=None)  # caches the result of the cutoff calculation.
    def _derivative_filter_normalized_cutoff(cls, shift):
        """Return the exact -3 dB angular cutoff in radians/sample."""
        alpha = 2.0 ** (-int(shift))

        def magnitude_squared(omega):
            zinv = np.exp(-1j * omega)
            response = alpha * zinv**2 / (1.0 - zinv + alpha * zinv**2)
            return abs(response) ** 2

        grid = np.concatenate(([0.0], np.geomspace(1e-12, np.pi, 2048)))
        values = np.asarray([magnitude_squared(value) for value in grid])
        crossings = np.flatnonzero(values <= 0.5)
        if len(crossings) == 0:
            return np.pi
        upper_index = max(int(crossings[0]), 1)
        lower, upper = grid[upper_index - 1], grid[upper_index]
        for _ in range(60):
            middle = (lower + upper) / 2.0
            if magnitude_squared(middle) > 0.5:
                lower = middle
            else:
                upper = middle
        return (lower + upper) / 2.0

    @classmethod
    def _derivative_filter_cutoff(cls, shift, frequency_correction=1.0):
        sample_rate = 125e6 * frequency_correction
        return cls._derivative_filter_normalized_cutoff(shift) * sample_rate / (2 * np.pi)

    @classmethod
    def _select_derivative_filter_shift(cls, cutoff, frequency_correction=1.0):
        if cutoff <= 0:
            return 4
        shifts = np.arange(1, cls._DERIVATIVE_FILTER_MAX_SHIFT + 1)
        cutoffs = np.asarray(
            [cls._derivative_filter_cutoff(shift, frequency_correction) for shift in shifts]
        )
        return int(shifts[np.argmin(np.abs(np.log(cutoffs / cutoff)))])

    def _update_derivative_filter_shift(self):
        try:
            derivative_available = "pid_derivative" in self._rp.fpga_profile.capabilities
        except AttributeError:
            derivative_available = False
        if not derivative_available:
            return
        derivative_frequency = abs(self.d)
        if derivative_frequency == 0:
            return
        cutoff = derivative_frequency * self.derivative_filter_ratio
        self._derivative_filter_shift_register = self._select_derivative_filter_shift(
            cutoff, self._frequency_correction
        )

    @property
    def derivative_filter_bandwidth(self):
        """Actual quantized -3 dB roll-off frequency in Hz."""
        if "pid_derivative" not in self._rp.fpga_profile.capabilities:
            raise RuntimeError(
                "Derivative filter bandwidth requires the 'pid_derivative' FPGA profile"
            )
        return self._derivative_filter_cutoff(
            self._derivative_filter_shift_register, self._frequency_correction
        )

    pause_gains = SelectRegister(
        0x12C,
        options=sorted_dict(off=0, i=1, p=2, pi=3, d=4, id=5, pd=6, pid=7),
        bitmask=0b111,
        doc="Selects which gains are frozen during pausing/synchronization.",
    )

    differential_mode_enabled = BoolRegister(
        0x12C,
        bit=3,
        doc="If True, the differential mode is enabled. "
        "In this mode, the setpoint is given by the "
        "input signal of another pid module. "
        "Only pid0 and pid1 can be paired in "
        "differential mode. ",
    )

    paused = PauseRegister(
        0xC,
        invert=True,
        doc="While True, the gains selected with `pause` are temporarily set to zero ",
    )

    _pause_sources = sorted_dict(off=0, external=1)
    pause_sources = _pause_sources.keys()
    pause_source = SelectRegister(
        0x130,
        options=_pause_sources,
        default="off",
        doc=(
            "External sample-and-hold control. When external is selected, "
            "the PID runs while pause_pin is high and holds its complete "
            "state and output while the pin is low."
        ),
    )

    _pause_pins = sorted_dict(
        **{
            **{f"P{index}": index for index in range(8)},
            **{f"N{index}": index + 8 for index in range(8)},
        }
    )
    pause_pins = _pause_pins.keys()
    pause_pin = SelectRegister(
        0x134,
        options=_pause_pins,
        default="P0",
        doc="Expansion connector input used for external PID sample-and-hold.",
    )

    @property
    def proportional(self):
        return self.p

    @property
    def integral(self):
        return self.i

    @property
    def derivative(self):
        return self.d

    @property
    def reg_integral(self):
        return self.ival

    @proportional.setter
    def proportional(self, v):
        self.p = v

    @integral.setter
    def integral(self, v):
        self.i = v

    @derivative.setter
    def derivative(self, v):
        self.d = v

    @reg_integral.setter
    def reg_integral(self, v):
        self.ival = v

    # deactivated for performance reasons
    # normalization_on = BoolRegister(0x130, 0,
    #                                 doc="if True the PID is used "
    #                                     "as a normalizer")
    #
    # # current normalization gain is p-register
    # normalization_i = FloatRegister(0x10C, bits=_GAINBITS,
    #                                 norm=2 ** (_ISR) * 2.0 * np.pi *
    #                                      8e-9 / 2 ** 13 / 1.5625,
    #                                 # 1.5625 is empirical value,
    #                                 # no time/idea to do the maths
    #                                 doc="stablization crossover frequency [Hz]")
    #
    # @property
    # def normalization_gain(self):
    #     """ current gain in the normalization """
    #     return self.p / 2.0
    #
    # normalization_inputoffset = FloatRegister(0x110, bits=(14 + _DSR),
    #                                           norm=2 ** (13 + _DSR),
    #                                           doc="normalization inputoffset [volts]")

    def transfer_function(self, frequencies, extradelay=0):
        """
        Returns a complex np.array containing the transfer function of the
        current PID module setting for the given frequency array. The
        settings for p, i, d and inputfilter, as well as delay are aken into
        account for the modelisation. There is a slight dependency of delay
        on the setting of inputfilter, i.e. about 2 extracycles per filter
        that is not set to 0, which is however taken into account.

        Parameters
        ----------
        frequencies: np.array or float
            Frequencies to compute the transfer function for
        extradelay: float
            External delay to add to the transfer function (in s). If zero,
            only the delay for internal propagation from input to
            output_signal is used. If the module is fed to analog inputs and
            outputs, an extra delay of the order of 200 ns must be passed as
            an argument for the correct delay modelisation.

        Returns
        -------
        tf: np.array(..., dtype=complex)
            The complex open loop transfer function of the module.
        """
        derivative_available = "pid_derivative" in self._rp.fpga_profile.capabilities
        return Pid._transfer_function(
            frequencies,
            p=self.p,
            i=self.i,
            d=self.d if derivative_available else 0,
            derivative_filter_shift=(
                self._derivative_filter_shift_register if derivative_available else 4
            ),
            filter_values=self.inputfilter,
            extradelay_s=extradelay,
            module_delay_cycle=self._delay,
            frequency_correction=self._frequency_correction,
        )

    @classmethod
    def _transfer_function(
        cls,
        frequencies,
        p,
        i,
        filter_values=None,
        d=0,
        module_delay_cycle=_delay,
        extradelay_s=0.0,
        frequency_correction=1.0,
        derivative_filter_shift=4,
    ):
        if filter_values is None:
            filter_values = list()
        return (
            Pid._pid_transfer_function(
                frequencies,
                p=p,
                i=i,
                d=d,
                frequency_correction=frequency_correction,
                derivative_filter_shift=derivative_filter_shift,
            )
            * Pid._filter_transfer_function(
                frequencies,
                filter_values=filter_values,
                frequency_correction=frequency_correction,
            )
            * Pid._delay_transfer_function(
                frequencies,
                module_delay_cycle=module_delay_cycle,
                extradelay_s=extradelay_s,
                frequency_correction=frequency_correction,
            )
        )

    @classmethod
    def _pid_transfer_function(
        cls,
        frequencies,
        p,
        i,
        d=0,
        frequency_correction=1.0,
        derivative_filter_shift=4,
    ):
        """
        returns the transfer function of a generic pid module
        delay is the module delay as found in pid._delay, p, i and d are the
        proportional, integral, and differential gains
        frequency_correction is the module frequency_correction as
        found in pid._frequency_correction
        """

        frequencies = np.array(frequencies, dtype=complex)
        sample_period = 8e-9 / frequency_correction
        zinv = np.exp(-1j * sample_period * frequencies * 2 * np.pi)
        # integrator with one cycle of extra delay
        tf = i / (frequencies * 1j) * zinv
        # proportional (delay in self._delay included)
        tf += p
        if d != 0:
            alpha = 2.0 ** (-int(derivative_filter_shift))
            # The registered filter correction produces the exact transfer
            # alpha*z^-2 / (1 - z^-1 + alpha*z^-2).
            derivative_filter = alpha * zinv**2 / (1.0 - zinv + alpha * zinv**2)
            tf += (1.0 - zinv) / (2.0 * np.pi * sample_period * d) * derivative_filter
        # add delay
        delay = 0  # module_delay * 8e-9 / self._frequency_correction
        tf *= np.exp(-1j * delay * frequencies * 2 * np.pi)
        return tf

    @classmethod
    def _delay_transfer_function(
        cls,
        frequencies,
        module_delay_cycle=_delay,
        extradelay_s=0,
        frequency_correction=1.0,
    ):
        """
        Transfer function of the eventual extradelay of a pid module
        """
        delay = module_delay_cycle * 8e-9 / frequency_correction + extradelay_s
        frequencies = np.array(frequencies, dtype=complex)
        tf = np.ones(len(frequencies), dtype=complex)
        tf *= np.exp(-1j * delay * frequencies * 2 * np.pi)
        return tf

    @classmethod
    def _filter_transfer_function(cls, frequencies, filter_values, frequency_correction=1.0):
        """
        Transfer function of the inputfilter part of a pid module
        """
        frequencies = np.array(frequencies, dtype=complex)
        module_delay = 0
        tf = np.ones(len(frequencies), dtype=complex)
        # input filter modelisation
        if not isinstance(filter_values, list):
            filter_values = list([filter_values])
        for f in filter_values:
            if f == 0:
                continue
            elif f > 0:  # lowpass
                tf /= 1.0 + 1j * frequencies / f
                module_delay += 2  # two cycles extra delay per lowpass
            elif f < 0:  # highpass
                tf /= 1.0 + 1j * f / frequencies
                # plus is correct here since f already has a minus sign
                module_delay += 1  # one cycle extra delay per highpass
        delay = module_delay * 8e-9 / frequency_correction
        tf *= np.exp(-1j * delay * frequencies * 2 * np.pi)
        return tf
