"""
We have already seen some use of the pid module above. There are three
PID modules available: pid0 to pid2.

.. code:: python

    print r.pid0.help()

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

import numpy as np
from qtpy import QtCore
from ..attributes import FloatProperty, BoolRegister, FloatRegister, GainRegister, SelectRegister
from .dsp import PauseRegister
from ..modules import SignalLauncher
from . import FilterModule
from ..widgets.module_widgets import PidWidget
from ..pyrpl_utils import sorted_dict

class IValAttribute(FloatProperty):
    """
    Attribute for integrator value
    """
    def get_value(self, obj):
        return float(obj._to_pyint(obj._read(0x100), bitlength=16))\
               / 2 ** 13
        # bitlength used to be 32 until 16/7/2016
        # still, FPGA has an asymmetric representation for reading and writing
        # from/to this register

    def set_value(self, obj, value):
        """set the value of the register holding the integrator's sum [volts]"""
        return obj._write(0x100, obj._from_pyint(
            int(round(value * 2 ** 13)), bitlength=16))


class SignalLauncherPid(SignalLauncher):
    update_ival = QtCore.Signal()
    # the widget decides at the other hand if it has to be done or not
    # depending on the visibility
    def __init__(self, module):
        super(SignalLauncherPid, self).__init__(module)
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
        super(SignalLauncherPid, self)._clear()


class Pid(FilterModule):
    """
    A proportional/Integrator/Differential filter.

    The PID filter consists of a 4th order filter input stage, followed by a
    proportional and integral stage in parallel.

    .. warning:: at the moment, the differential stage of PIDs is disabled.

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
    _setup_attributes = ["input",
                         "output_direct",
                         "setpoint",
                         "p",
                         "i",
                         #"d",
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

    _delay = 3  # min delay in cycles from input to output_signal of the module
    # with integrator and derivative gain, delay is rather 4 cycles

    _PSR = 12  # Register(0x200)

    _ISR = 32  # Register(0x204)

    _DSR = 10  # Register(0x208)

    _GAINBITS = 24  # Register(0x20C)

    ival = IValAttribute(min=-4, max=4, increment= 8. / 2**16, doc="Current "
            "value of the integrator memory (i.e. pid output voltage offset)")

    setpoint = FloatRegister(0x104, bits=14, norm= 2 **13,
                             doc="pid setpoint [volts]")

    min_voltage = FloatRegister(0x124, bits=14, norm= 2 **13,
                                doc="minimum output signal [volts]")
    max_voltage = FloatRegister(0x128, bits=14, norm= 2 **13,
                                doc="maximum output signal [volts]")

    p = GainRegister(0x108, bits=_GAINBITS, norm= 2 **_PSR,
                      doc="pid proportional gain [1]")
    i = GainRegister(0x10C, bits=_GAINBITS, norm= 2 **_ISR * 2.0 * np.pi *
                                                  8e-9,
                      doc="pid integral unity-gain frequency [Hz]")
    #d = GainRegister(0x110, bits=_GAINBITS, norm= 2 ** _DSR /( 2.0 *np. pi *
    #                                                        8e-9),
    #                  invert=True,
    #                  doc="pid derivative unity-gain frequency [Hz]. Off
    # when 0.")

    pause_gains = SelectRegister(0x12C,
                                 options=sorted_dict(
                                       off=0,
                                       i=1,
                                       p=2,
                                       pi=3,
                                       d=4,
                                       id=5,
                                       pd=6,
                                       pid=7),
                                 bitmask=0b111,
                                 doc="Selects which gains are frozen during pausing/synchronization."
                                 )

    differential_mode_enabled = BoolRegister(0x12C,
                                             bit=3,
                                             doc="If True, the differential mode is enabled. "
                                                 "In this mode, the setpoint is given by the "
                                                 "input signal of another pid module. "
                                                 "Only pid0 and pid1 can be paired in "
                                                 "differential mode. "
                                             )

    paused = PauseRegister(0xC,
                           invert=True,
                           doc="While True, the gains selected with `pause` are "
                               "temporarily set to zero ")

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
        return Pid._transfer_function(frequencies,
                                      p=self.p,
                                      i=self.i,
                                      d=0,  # d is currently not available
                                      filter_values=self.inputfilter,
                                      extradelay_s=extradelay,
                                      module_delay_cycle=self._delay,
                                      frequency_correction=self._frequency_correction)

    @classmethod
    def _transfer_function(cls,
                           frequencies,
                           p,
                           i,
                           filter_values=list(),
                           d=0,
                           module_delay_cycle=_delay,
                           extradelay_s=0.0,
                           frequency_correction=1.0):
        return Pid._pid_transfer_function(frequencies,
                                 p=p,
                                 i=i,
                                 d=d,
                                 frequency_correction=frequency_correction)\
            * Pid._filter_transfer_function(frequencies,
                                 filter_values=filter_values,
                                 frequency_correction=frequency_correction)\
            * Pid._delay_transfer_function(frequencies,
                                 module_delay_cycle=module_delay_cycle,
                                 extradelay_s=extradelay_s,
                                 frequency_correction=frequency_correction)

    @classmethod
    def _pid_transfer_function(cls,
                               frequencies, p, i, d=0,
                               frequency_correction=1.):
        """
        returns the transfer function of a generic pid module
        delay is the module delay as found in pid._delay, p, i and d are the
        proportional, integral, and differential gains
        frequency_correction is the module frequency_correction as
        found in pid._frequency_correction
        """

        frequencies = np.array(frequencies, dtype=complex)
        # integrator with one cycle of extra delay
        tf = i / (frequencies * 1j) \
            * np.exp(-1j * 8e-9 * frequency_correction *
                  frequencies * 2 * np.pi)
        # proportional (delay in self._delay included)
        tf += p
        # derivative action with one cycle of extra delay
        # if self.d != 0:
        #    tf += frequencies*1j/self.d \
        #          * np.exp(-1j * 8e-9 * self._frequency_correction *
        #                   frequencies * 2 * np.pi)
        # add delay
        delay = 0 # module_delay * 8e-9 / self._frequency_correction
        tf *= np.exp(-1j * delay * frequencies * 2 * np.pi)
        return tf

    @classmethod
    def _delay_transfer_function(cls,
                                 frequencies,
                                 module_delay_cycle=_delay,
                                 extradelay_s=0,
                                 frequency_correction=1.0):
        """
        Transfer function of the eventual extradelay of a pid module
        """
        delay = module_delay_cycle * 8e-9 / frequency_correction + extradelay_s
        frequencies = np.array(frequencies, dtype=complex)
        tf = np.ones(len(frequencies), dtype=complex)
        tf *= np.exp(-1j * delay * frequencies * 2 * np.pi)
        return tf

    @classmethod
    def _filter_transfer_function(cls,
                                  frequencies, filter_values,
                                  frequency_correction=1.):
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
                tf /= (1.0 + 1j * frequencies / f)
                module_delay += 2  # two cycles extra delay per lowpass
            elif f < 0:  # highpass
                tf /= (1.0 + 1j * f / frequencies)
                # plus is correct here since f already has a minus sign
                module_delay += 1  # one cycle extra delay per highpass
        delay = module_delay * 8e-9 / frequency_correction
        tf *= np.exp(-1j * delay * frequencies * 2 * np.pi)
        return tf
