"""
Demodulation of a signal means convolving it with a sine and cosine at
the 'carrier frequency'. The two resulting signals are usually low-pass
filtered and called 'quadrature I' and 'quadrature Q'. Based on this
simple idea, the IQ module of pyrpl can implement several
functionalities, depending on the particular setting of the various
registers. In most cases, the configuration can be completely carried
out through the setup function of the module.



Lock-in detection / PDH / synchronous detection

.. code:: python

    #reload to make sure settings are default ones
    from pyrpl import Pyrpl
    r = Pyrpl(hostname="192.168.1.100").rp

    #shortcut
    iq = r.iq0

    # modulation/demodulation frequency 25 MHz
    # two lowpass filters with 10 and 20 kHz bandwidth
    # input signal is analog input 1
    # input AC-coupled with cutoff frequency near 50 kHz
    # modulation amplitude 0.1 V
    # modulation goes to out1
    # output_signal is the demodulated quadrature 1
    # quadrature_1 is amplified by 10
    iq.setup(frequency=25e6, bandwidth=[10e3,20e3], gain=0.0,
             phase=0, acbandwidth=50000, amplitude=0.5,
             input='in1', output_direct='out1',
             output_signal='quadrature', quadrature_factor=10)

After this setup, the demodulated quadrature is available as the
output\_signal of iq0, and can serve for example as the input of a PID
module to stabilize the frequency of a laser to a reference cavity. The
module was tested and is in daily use in our lab. Frequencies as low as
20 Hz and as high as 50 MHz have been used for this technique. At the
present time, the functionality of a PDH-like detection as the one set
up above cannot be conveniently tested internally. We plan to upgrade
the IQ-module to VCO functionality in the near future, which will also
enable testing the PDH functionality.


Network analyzer
^^^^^^^^^^^^^^^^^^

When implementing complex functionality in the RedPitaya, the network
analyzer module is by far the most useful tool for diagnostics. The
network analyzer is able to probe the transfer function of any other
module or external device by exciting the device with a sine of variable
frequency and analyzing the resulting output from that device. This is
done by demodulating the device output (=network analyzer input) with
the same sine that was used for the excitation and a corresponding
cosine, lowpass-filtering, and averaging the two quadratures for a
well-defined number of cycles. From the two quadratures, one can extract
the magnitude and phase shift of the device's transfer function at the
probed frequencies. Let's illustrate the behaviour. For this example,
you should connect output 1 to input 1 of your RedPitaya, such that we
can compare the analog transfer function to a reference. Make sure you
put a 50 Ohm terminator in parallel with input 1.

.. code:: python

    # shortcut for na
    na = p.networkanalyzer
    na.iq_name = 'iq1'

    # setup network analyzer with the right parameters
    na.setup(start=1e3,stop=62.5e6,points=1001,rbw=1000, avg=1,
    amplitude=0.2,input='iq1',output_direct='off', acbandwidth=0)

    #take transfer functions. first: iq1 -> iq1, second iq1->out1->(your cable)->adc1
    iq1 = na.curve()
    na.setup(input='in1', output_direct='out1')
    in1 = na.curve()

    # get x-axis for plotting
    f = na.frequencies

    #plot
    from pyrpl.hardware_modules.iir.iir_theory import bodeplot
    %matplotlib inline
    bodeplot([(f, iq1, "iq1->iq1"), (f, in1, "iq1->out1->in1->iq1")], xlog=True)

If your cable is properly connected, you will see that both magnitudes
are near 0 dB over most of the frequency range. Near the Nyquist
frequency (62.5 MHz), one can see that the internal signal remains flat
while the analog signal is strongly attenuated, as it should be to avoid
aliasing. One can also see that the delay (phase lag) of the internal
signal is much less than the one through the analog signal path.

.. note:: The Network Analyzer is implemented as a software module, distinct \
from the iq module. This is the reason why networkanalyzer is accessed \
directly at the Pyrpl-object level *p.networkanalyzer* and not at the \
redpitaya level *p.rp.networkanalyzer*. However, an iq module is \
reserved whenever the network analyzer is acquiring data.

If you have executed the last example (PDH detection) in this python
session, iq0 should still send a modulation to out1, which is added to
the signal of the network analyzer, and sampled by input1. In this case,
you should see a little peak near the PDH modulation frequency, which
was 25 MHz in the example above.

Lorentzian bandpass filter
^^^^^^^^^^^^^^^^^^^^^^^^^^

The iq module can also be used as a bandpass filter with continuously
tunable phase. Let's measure the transfer function of such a bandpass
with the network analyzer:

.. code:: python

    # shortcut for na and bpf (bandpass filter)
    na = p.networkanalyzer
    bpf = p.rp.iq2

    # setup bandpass
    bpf.setup(frequency = 2.5e6, #center frequency
              bandwidth=1.e3, # the filter quality factor
              acbandwidth = 10e5, # ac filter to remove pot. input offsets
              phase=0, # nominal phase at center frequency (propagation phase lags not accounted for)
              gain=2.0, # peak gain = +6 dB
              output_direct='off',
              output_signal='output_direct',
              input='iq1')

    # setup the network analyzer
    na.setup(start=1e5, stop=4e6, points=201, rbw=100, avg=3,
                             amplitude=0.2, input='iq2',output_direct='off')

    # take transfer function
    tf1 = na.curve()

    # add a phase advance of 82.3 degrees and measure transfer function
    bpf.phase = 82.3
    tf2 = na.curve()

    f = na.frequencies

    #plot
    from pyrpl.hardware_modules.iir.iir_theory import bodeplot
    %matplotlib inline
    bodeplot([(f, tf1, "phase = 0.0"), (f, tf2, "phase = %.1f"%bpf.phase)])


.. note:: To measure the transfer function of an internal module, we cannot
use the *output_direct* property of the network ananlyzer (only 'out1',
'out2' or 'off' are allowed). To circumvent the problem, we set the input of
the module to be measured to the network analyzer's iq.


Frequency comparator module
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To lock the frequency of a VCO (Voltage controlled oscillator) to a
frequency reference defined by the RedPitaya, the IQ module contains the
frequency comparator block. This is how you set it up. You have to feed
the output of this module through a PID block to send it to the analog
output. As you will see, if your feedback is not already enabled when
you turn on the module, its integrator will rapidly saturate (-585 is
the maximum value here, while a value of the order of 1e-3 indicates a
reasonable frequency lock).

.. code:: python

    iq = p.rp.iq0

    # turn off pfd module for settings
    iq.pfd_on = False

    # local oscillator frequency
    iq.frequency = 33.7e6

    # local oscillator phase
    iq.phase = 0
    iq.input = 'in1'
    iq.output_direct = 'off'
    iq.output_signal = 'pfd'

    print("Before turning on:")
    print("Frequency difference error integral", iq.pfd_integral)

    print("After turning on:")
    iq.pfd_on = True
    for i in range(10):
        print("Frequency difference error integral", iq.pfd_integral)

"""
import sys
from time import sleep
from collections import OrderedDict
import numpy as np

from ..attributes import BoolRegister, FloatRegister, SelectRegister, \
    IntRegister, PhaseRegister, FrequencyRegister, FloatProperty, \
    FilterRegister, FilterProperty, GainRegister
from ..widgets.module_widgets import IqWidget
from ..pyrpl_utils import sorted_dict

from . import FilterModule


class IqGain(FloatProperty):
    """descriptor for the gain of the Iq module"""

    def get_value(self, obj):
        return obj._g1 / 2 ** 3

    def set_value(self, obj, val):
        obj._g1 = float(val) * 2 ** 3
        obj._g4 = float(val) * 2 ** 3
        return val


class IqAcbandwidth(FilterProperty):
    """descriptor for the acbandwidth of the Iq module"""

    def valid_frequencies(self, module):
        return [freq for freq in module.__class__.inputfilter.valid_frequencies(module) if freq >= 0]

    def get_value(self, obj):
        if obj is None:
            return self
        return - obj.inputfilter

    def set_value(self, instance, val):
        if np.iterable(val):
            val = val[0]
        val = float(val)
        instance.inputfilter = -val
        return val


class Iq(FilterModule):
    """
    A modulator/demodulator module.

    """
    _widget_class = IqWidget
    _setup_attributes = ["input",
                         "acbandwidth",
                         "frequency",
                         "bandwidth",
                         "quadrature_factor",
                         "output_signal",
                         "gain",
                         "amplitude",
                         "phase",
                         "output_direct",
                         "modulation_at_2f",
                         "demodulation_at_2f"]

    _gui_attributes = _setup_attributes  # + ["synchronize_iqs"]  # function calls auto-gui only works in develop-0.9.3 branch

    _delay = 5  # bare delay of IQ module with no filters set (cycles)

    _output_signals = sorted_dict(
        quadrature=0,
        output_direct=1,
        pfd=2,
        off=3,
        quadrature_hf=4)


    output_signals = _output_signals.keys()
    output_signal = SelectRegister(0x10C, options=_output_signals,
                                   doc="Signal to send back to DSP multiplexer")

    bandwidth = FilterRegister(0x124,
                               filterstages=0x230,
                               shiftbits=0x234,
                               minbw=0x238,
                               doc="Quadrature filter bandwidths [Hz]." \
                                   "0 = off, negative bandwidth = highpass")

    _valid_bandwidths = bandwidth.valid_frequencies

    @property
    def bandwidths(self):
        return self._valid_bandwidths(self)

    on = BoolRegister(0x100, 0,
                      doc="If set to False, turns off the module, e.g. to \
                      re-synchronize the phases")

    pfd_on = BoolRegister(0x100, 1,
                          doc="If True: Turns on the PFD module,\
                        if False: turns it off and resets integral")

    # raw flags, not useful in most cases since sin and cos-flag must be
    # written in the same clock cycle
    _modulation_sin_at_2f = BoolRegister(0x100, 2, default=False,
                                         doc="If True, this flag sets the "
                                             "frequency of the sine used "
                                             "for modulation to twice the "
                                             "fundamental frequency.")
    _modulation_cos_at_2f = BoolRegister(0x100, 3, default=False,
                                         doc="If True, this flag sets the "
                                             "frequency of the cosine used "
                                             "for modulation to twice the "
                                             "fundamental frequency.")
    _demodulation_sin_at_2f = BoolRegister(0x100, 4, default=False,
                                         doc="If True, this flag sets the "
                                             "frequency of the sine used "
                                             "for demodulation to twice the "
                                             "fundamental frequency.")
    _demodulation_cos_at_2f = BoolRegister(0x100, 5, default=False,
                                         doc="If True, this flag sets the "
                                             "frequency of the cosine used "
                                             "for demodulation to twice the "
                                             "fundamental frequency.")
    # helper registers for switching sin/cos flags at the same time
    modulation_at_2f = SelectRegister(0x100, bitmask=3<<2, options=dict(off=0, on=3<<2),
                                      default='off',
                                      doc="Sets the modulation frequency to "
                                          "twice the IQ module frequency")
    demodulation_at_2f = SelectRegister(0x100, bitmask=3<<4, options=dict(off=0, on=3<<4),
                                        default='off',
                                        doc="Sets the demodulation frequency to "
                                            "twice the IQ module frequency")

    _LUTSZ = IntRegister(0x200)
    _LUTBITS = IntRegister(0x204)
    _PHASEBITS = 32  # Register(0x208)
    _GAINBITS = 18  # Register(0x20C)
    _SIGNALBITS = 14  # Register(0x210)
    _LPFBITS = 24  # Register(0x214)
    _SHIFTBITS = 8  # Register(0x218)

    pfd_integral = FloatRegister(0x150, bits=_SIGNALBITS, norm=_SIGNALBITS,
                                 doc="value of the pfd integral [volts]")

    # for the phase to have the right sign, it must be inverted
    phase = PhaseRegister(0x104, bits=_PHASEBITS, invert=True,
                          doc="Phase shift between modulation \
                          and demodulation [degrees]")

    frequency = FrequencyRegister(0x108, bits=_PHASEBITS,
                                  doc="frequency of iq demodulation [Hz]")

    _g1 = GainRegister(0x110, bits=_GAINBITS, norm=2 ** _SHIFTBITS,
                        doc="gain1 of iq module [volts]")

    _g2 = GainRegister(0x114, bits=_GAINBITS, norm=2 ** _SHIFTBITS,
                        doc="gain2 of iq module [volts]")
    amplitude = GainRegister(0x114, bits=_GAINBITS, norm=2 ** (_GAINBITS - 1),
                              doc="amplitude of coherent modulation [volts]")

    _g3 = GainRegister(0x118, bits=_GAINBITS, norm=2 ** _SHIFTBITS,
                        doc="gain3 of iq module [volts]")
    quadrature_factor = GainRegister(0x118,
                                      bits=_GAINBITS,
                                      norm=1.0,
                                      default=1.0,
                                      #2 ** _SHIFTBITS,
                                      #  quadrature_factor of 1 corresponds
                                      # to lowest-possible gain,
                                      # where iq_signal is simply the input
                                      # tiemes a 1-V sine (possibly low-pass
                                      # filtered)
                                      doc="amplification factor of demodulated signal [a.u.]")

    _g4 = GainRegister(0x11C, bits=_GAINBITS, norm=2 ** _SHIFTBITS,
                        doc="gain4 of iq module [volts]")


    # def __init__(self, *args, **kwds): ## ?? I don't see the point ??
    #    super(IQ, self).__init__(*args, **kwds)

    # @property
    # def acbandwidths(self):
    acbandwidths = [0] + [int(2.371593461809983 * 2 ** n) for n in
                          range(1, 27)]  # only register that needs to be read to
    # guess the options... we need to fix that...
    # return self._valid_inputfilter_frequencies()
    # acbandwidths = FilterModule.inputfilter.valid_frequencies()

    gain = IqGain(doc="gain of the iq module (see drawing)")

    acbandwidth = IqAcbandwidth(doc="positive corner frequency of input high pass filter")

    def synchronize_iqs(self):
        """
        Synchronizes all iq modules.

        This establishes a zero phase offset between the outputs of all iq
        modules with commensurate frequencies. This function must be called
        after having set the last iq frequency in order to be effective.
        """
        self._synchronize(modules=['iq0', 'iq1', 'iq2'])
        self._logger.debug("All IQ modules synchronized!")

    def _setup(self): # the function is here for its docstring to be used by the metaclass.
        """
        Sets up an iq demodulator, refer to the drawing in the GUI for an explanation of the IQ layout.
        (just setting the attributes is OK).
        """
        self.synchronize_iqs()

    _na_averages = IntRegister(0x130,
                               doc='number of cycles to perform na-averaging over')
    _na_sleepcycles = IntRegister(0x134,
                                  doc='number of cycles to wait before starting to average')

    @property
    def _nadata(self): # reading two registers necessary because _na_averages is not cached
        return self._nadata_total / float(self._na_averages)

    @property
    def _nadata_total(self): #only one read operation--> twice faster than _nadata
        attempt = 0
        a, b, c, d = self._reads(0x140, 4)
        while not ((a >> 31 == 0) and (b >> 31 == 0)
                   and (c >> 31 == 0) and (d >> 31 == 0)):
            a, b, c, d = self._reads(0x140, 4)

            self._logger.warning('NA data not ready yet. Try again!')
            attempt += 1
            if attempt > 10:
                raise Exception("Trying to recover NA data while averaging is not finished. Some setting is wrong. ")
        sum = np.complex128(self._to_pyint(int(a) + (int(b) << 31), bitlength=62)) \
              + np.complex128(self._to_pyint(int(c) + (int(d) << 31), bitlength=62)) * 1j
        return sum

    # the implementation of network_analyzer is not identical to na_trace
    # there are still many bugs in it, which is why we will keep this function
    # in the gui
    def na_trace(
            self,
            start=0,  # start frequency
            stop=100e3,  # stop frequency
            points=1001,  # number of points
            rbw=100,  # resolution bandwidth, can be a list of 2 as well for second-order
            avg=1.0,  # averages
            amplitude=0.1,  # output amplitude in volts
            input='adc1',  # input signal
            output_direct='off',  # output signal
            acbandwidth=0,  # ac filter bandwidth, 0 disables filter, negative values represent lowpass
            sleeptimes=0.5,  # wait sleeptimes/rbw for quadratures to stabilize
            logscale=False,  # make a logarithmic frequency sweep
            stabilize=None,
            # if a float, output amplitude is adjusted dynamically so that input amplitude [V]=stabilize
            maxamplitude=1.0,  # amplitude can be limited
            ):
        # logger.info("This function will become obsolete in the distant "
        #                 "future. Start using the module RedPitaya.na "
        #                 "instead!")
        if logscale:
            x = np.logspace(
                np.log10(start),
                np.log10(stop),
                points,
                endpoint=True)
        else:
            x = np.linspace(start, stop, points, endpoint=True)
        y = np.zeros(points, dtype=np.complex128)
        amplitudes = np.zeros(points, dtype=np.float64)
        # preventive saturation
        maxamplitude = abs(maxamplitude)
        amplitude = abs(amplitude)
        if abs(amplitude) > maxamplitude:
            amplitude = maxamplitude
        self.setup(frequency=x[0],
                   bandwidth=rbw,
                   gain=0,
                   phase=0,
                   acbandwidth=-np.array(acbandwidth),
                   amplitude=0,
                   input=input,
                   output_direct=output_direct,
                   output_signal='output_direct')
        # take the discretized rbw (only using first filter cutoff)
        rbw = self.bandwidth[0]
        self._logger.info("Estimated acquisition time: %.1f s", float(avg + sleeptimes) * points / rbw)
        sys.stdout.flush()  # make sure the time is shown
        # setup averaging
        self._na_averages = np.int(np.round(125e6 / rbw * avg))
        self._na_sleepcycles = np.int(np.round(125e6 / rbw * sleeptimes))
        # compute rescaling factor
        rescale = 2.0 ** (-self._LPFBITS) * 4.0  # 4 is artefact of fpga code
        # obtained by measuring transfer function with bnc cable - could replace the inverse of 4 above
        # unityfactor = 0.23094044589192711
        try:
            self.amplitude = amplitude  # turn on NA inside try..except block
            for i in range(points):
                self.frequency = x[i]  # this triggers the NA acquisition
                sleep(1.0 / rbw * (avg + sleeptimes))
                x[i] = self.frequency  # get the actual (discretized) frequency
                y[i] = self._nadata
                amplitudes[i] = self.amplitude
                # normalize immediately
                if amplitudes[i] == 0:
                    y[i] *= rescale  # avoid division by zero
                else:
                    y[i] *= rescale / self.amplitude
                # set next amplitude if it has to change
                if stabilize is not None:
                    amplitude = stabilize / np.abs(y[i])
                if amplitude > maxamplitude:
                    amplitude = maxamplitude
                self.amplitude = amplitude
        # turn off the NA output, even in the case of exception (e.g. KeyboardInterrupt)
        except:
            self.amplitude = 0
            self._logger.info("NA output turned off due to an exception")
            raise
        else:
            self.amplitude = 0
        # in zero-span mode, change x-axis to approximate time. Time is very
        # rudely approximated here..
        if start == stop:
            x = np.linspace(
                0,
                1.0 / rbw * (avg + sleeptimes),
                points,
                endpoint=False)
        if stabilize is None:
            return x, y
        else:
            return x, y, amplitudes

    def transfer_function(self, frequencies, extradelay=0):
        """
        Returns a complex np.array containing the transfer function of the
        current IQ module setting for the given frequency array. The given
        transfer function is only relevant if the module is used as a
        bandpass filter, i.e. with the setting (gain != 0). If extradelay = 0,
        only the default delay is taken into account, i.e. the propagation
        delay from input to output_signal.

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
        quadrature_delay = 2  # the delay experienced by the signal when it
        # is represented as a quadrature (=lower frequency, less phaseshift)
        # the remaining delay of the module
        module_delay = self._delay - quadrature_delay
        frequencies = np.array(frequencies, dtype=np.complex)
        tf = np.array(frequencies * 0, dtype=np.complex) + self.gain
        # bandpass filter
        for f in self.bandwidth:
            if f == 0:
                continue
            elif f > 0:  # lowpass
                tf *= 1.0 / (1.0 + 1j * (frequencies - self.frequency) / f)
                quadrature_delay += 2
            elif f < 0:  # highpass
                tf *= 1.0 / (1.0 + 1j * f / (frequencies - self.frequency))
                quadrature_delay += 1  # one cycle extra delay per highpass
        # compute phase shift due to quadrature propagation delay
        quadrature_delay *= 8e-9 / self._frequency_correction
        tf *= np.exp(-1j * quadrature_delay * (frequencies - self.frequency) \
                     * 2 * np.pi)
        # input filter modelisation
        f = self.inputfilter  # no for loop here because only one filter stage
        if f > 0:  # lowpass
            tf /= (1.0 + 1j * frequencies / f)
            module_delay += 2  # two cycles extra delay per lowpass
        elif f < 0:  # highpass
            tf /= (1.0 + 1j * f / frequencies)
            module_delay += 1  # one cycle extra delay per highpass
        # compute delay
        delay = module_delay * 8e-9 / self._frequency_correction + extradelay
        # add phase shift contribution - not working, see instead formula below
        # delay -= self.phase/360.0/self.frequency
        tf *= np.exp(-1j * delay * frequencies * 2 * np.pi)
        # add delay from phase (incorrect formula or missing effect...)
        tf *= np.exp(1j * self.phase / 180.0 * np.pi)
        return tf
