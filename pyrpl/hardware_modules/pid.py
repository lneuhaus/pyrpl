import numpy as np
from qtpy import QtCore
from ..attributes import FloatProperty, FloatRegister, GainRegister, BoolProperty
from ..modules import SignalLauncher
from . import FilterModule
from ..widgets.module_widgets import PidWidget


class IValAttribute(FloatProperty):
    """
    Attribute for integrator value
    """
    def __init__(self,
                 reset=False,
                 reset_value=1,
                 **kwargs):
        self.reset = reset
        self.reset_value = reset_value
        FloatProperty.__init__(self, **kwargs)
        
    def get_value(self, obj):
        red_value = float(obj._to_pyint(obj._read(0x100), bitlength=16)) / 2 ** 13
        reset_ival = self.reset.get_value(obj)
        reset_value = self.reset_value.get_value(obj)
        maxx = 1 - self.increment
        minn = -1
        if reset_ival==True and red_value>maxx:
            self.set_value(obj, -abs(reset_value))
        elif reset_ival==True and red_value<minn:
            self.set_value(obj, abs(reset_value))
        return red_value

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
        self.timer_ival.setInterval(1)  # in ms
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
    _widget_class = PidWidget
    _signal_launcher = SignalLauncherPid
    _setup_attributes = ["input",
                         "output_direct",
                         "setpoint",
                         "p",
                         "i",
                         "d",
                         "inputfilter",
                         "max_voltage",
                         "min_voltage"]
    _gui_attributes = _setup_attributes + ["ival", "reset_ival", "reset_value"]

    # the function is here so the metaclass generates a setup(**kwds) function
    def _setup(self):
        """
        sets up the pid (just setting the attributes is OK).
        """
        pass

    _delay = 4  # min delay in cycles from input to output_signal of the module
    # with integrator and derivative gain, delay is rather 4 cycles

    _PSR = 12  # Register(0x200)

    _ISR = 32  # Register(0x204)

    _DSR = 10  # Register(0x208)

    _GAINBITS = 24  # Register(0x20C)

    setpoint = FloatRegister(0x104, bits=14, norm= 2 **13,
                             doc="pid setpoint [volts]")

    min_voltage = FloatRegister(0x124, bits=14, norm= 2 **13,
                                doc="minimum output signal [volts]")
    max_voltage = FloatRegister(0x128, bits=14, norm= 2 **13,
                                doc="maximum output signal [volts]")

    p = GainRegister(0x108, bits=_GAINBITS, norm= 2 **_PSR,
                      doc="pid proportional gain [1]")
    i = GainRegister(0x10C, bits=_GAINBITS, norm= 2 **_ISR * 2.0 * np.pi * 8e-9,
                      doc="pid integral unity-gain frequency [Hz]")
    d = GainRegister(0x110, bits=_GAINBITS, norm= 2 ** _DSR /( 2.0 *np. pi * 8e-9),
                      invert=False,
                      doc="pid derivative 1/unity-gain frequency [1/Hz]. Off when 0.")
    
    reset_ival = BoolProperty(doc="set ival to -(+)reset_val if it reaches max(min)")
    
    reset_value = FloatProperty(min=0, max=4, increment= 8. / 2**16,
                             doc="reset i_val to this value (with right sign)")
    
    ival = IValAttribute(reset=reset_ival, reset_value=reset_value, min=-4, max=4, 
                         increment= 8. / 2**16,
        doc="current value of the integrator memory (i.e. pid output voltage offset)")


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
        tf: np.array(..., dtype=np.complex)
            The complex open loop transfer function of the module.
        """
        return Pid._transfer_function(frequencies,
                                      p=self.p,
                                      i=self.i,
                                      d=self.d,  # d is currently not available
                                      filter_values=self.inputfilter,
                                      extradelay_s=extradelay,
                                      module_delay_cycle=self._delay,
                                      frequency_correction=self._frequency_correction)

    @classmethod
    def _transfer_function(cls,
                           frequencies,
                           p,
                           i,
                           d,
                           filter_values=list(),
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
                               frequencies, p, i, d,
                               frequency_correction=1.):
        """
        returns the transfer function of a generic pid module
        delay is the module delay as found in pid._delay, p, i and d are the
        proportional, integral, and differential gains
        frequency_correction is the module frequency_corection as
        found in pid._frequency_corection
        """

        frequencies = np.array(frequencies, dtype=np.complex)
        # integrator with one cycle of extra delay
        tf = i / (frequencies * 1j) \
            * np.exp(-1j * 8e-9 * frequency_correction *
                  frequencies * 2 * np.pi)
        # proportional (delay in self._delay included)
        tf += p
        # derivative action with one cycle of extra delay
        if d != 0:
            tf += frequencies*1j/d \
                  * np.exp(-1j * 8e-9 * frequency_correction *
                           frequencies * 2 * np.pi)
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
        frequencies = np.array(frequencies, dtype=np.complex)
        tf = np.ones(len(frequencies), dtype=np.complex)
        tf *= np.exp(-1j * delay * frequencies * 2 * np.pi)
        return tf

    @classmethod
    def _filter_transfer_function(cls,
                                  frequencies, filter_values,
                                  frequency_correction=1.):
        """
        Transfer function of the inputfilter part of a pid module
        """
        frequencies = np.array(frequencies, dtype=np.complex)
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
