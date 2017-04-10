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
                         "output_direct"]
    _gui_attributes = _setup_attributes

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

    def _setup(self): # the function is here for its docstring to be used by the metaclass.
        """
        Sets up an iq demodulator, refer to the drawing in the GUI for an explanation of the IQ layout.
        (just setting the attributes is OK).
        """
        pass

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
