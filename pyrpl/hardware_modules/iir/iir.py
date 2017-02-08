from . import iir_theory #, bodefit
from .. import FilterModule
from pyrpl.attributes import IntRegister, BoolRegister, ListComplexProperty, FloatProperty
from pyrpl.widgets.module_widgets import IirWidget
from pyrpl.modules import SignalLauncher

import numpy as np
from PyQt4 import QtCore, QtGui


class SignalLauncherIir(SignalLauncher):
    update_plot = QtCore.pyqtSignal()


class IIR(FilterModule):
    _section_name = 'iir'
    iirfilter = None  # will be set by setup()
    _minloops = 5  # minimum number of loops for correct behaviour
    _maxloops = 1023
    # the first biquad (self.coefficients[0] has _delay cycles of delay
    # from input to output_signal. Biquad self.coefficients[i] has
    # _delay+i cycles of delay.
    _delay = 5  # empirically found. Counting cycles gave me 7.

    # parameters for scipy.signal.cont2discrete
    _method = 'gbt'  # method to go from continuous to discrete coefficients
    _alpha = 0.5  # alpha parameter for method (scipy.signal.cont2discrete)

    # invert denominator coefficients to convert from scipy notation to
    # the fpga-implemented notation (following Oppenheim and Schaefer: DSP)
    _invert = True

    _IIRBITS = IntRegister(0x200)

    _IIRSHIFT = IntRegister(0x204)

    _IIRSTAGES = IntRegister(0x208)

    _widget_class = IirWidget

    _setup_attributes = ["input",
                       "loops",
                       "zeros",
                       "poles",
                       "gain",
                       "output_direct",
                       "inputfilter"]
    _gui_attributes = _setup_attributes
    _callback_attributes = _gui_attributes
    """
    parameter_names = ["loops",
                       "on",
                       "shortcut",
                       "coefficients",
                       "input",
                       "output_direct"]
    """

    loops = IntRegister(0x100, doc="Decimation factor of IIR w.r.t. 125 MHz. " \
                                   + "Must be at least 3. ")

    on = BoolRegister(0x104, 0, doc="IIR is on")

    zeros = ListComplexProperty()
    poles = ListComplexProperty()
    gain =  FloatProperty()

    shortcut = BoolRegister(0x104, 1, doc="IIR is bypassed")

    # obsolete
    # copydata = BoolRegister(0x104, 2,
    #            doc="If True: coefficients are being copied from memory")

    overflow = IntRegister(0x108,
                           doc="Bitmask for various overflow conditions")

    def _init_module(self):
        self._signal_launcher = SignalLauncherIir(self)

    @property
    def output_saturation(self):
        """ returns True if the output of the IIR filter has saturated since
        the last reset """
        return bool(self.overflow & 1 << 6)

    @property
    def internal_overflow(self):
        """ returns True if the IIR filter has experienced an internal
        overflow (leading to saturation) since the last reset"""
        overflow = bool(self.overflow & 0b111111)
        if overflow:
            self._logger.info("Internal overflow has occured. Bit pattern "
                              "%s", bin(self.overflow))
        return overflow

    def _from_double(self, v, bitlength=64, shift=0):
        v = int(np.round(v * 2 ** shift))
        v = v & (2 ** bitlength - 1)
        hi = (v >> 32) & ((1 << 32) - 1)
        lo = (v >> 0) & ((1 << 32) - 1)
        return hi, lo

    def _to_double(self, hi, lo, bitlength=64, shift=0):
        hi = int(hi) & ((1 << (bitlength - 32)) - 1)
        lo = int(lo) & ((1 << 32) - 1)
        v = int((hi << 32) + lo)
        if v >> (bitlength - 1) != 0:  # sign bit is set
            v = v - 2 ** bitlength
        v = np.float64(v) / 2 ** shift
        return v

    @property
    def coefficients(self):
        l = self.loops
        if l == 0:
            return np.array([])
        elif l > self._IIRSTAGES:
            l = self._IIRSTAGES
        # data = np.array([v for v in self._reads(0x8000, 8 * l)])
        # coefficient readback has been disabled to save FPGA resources.
        if hasattr(self, '_writtendata'):
            data = self._writtendata
        else:
            return None # raising an exception here will even screw-up things like hasattr(iir, "coefficients")
            # raise ValueError("Readback of coefficients not enabled. " \
            #                 + "You must set coefficients before reading them.")
        coefficients = np.zeros((l, 6), dtype=np.float64)
        bitlength = self._IIRBITS
        shift = self._IIRSHIFT
        for i in range(l):
            for j in range(6):
                if j == 2:
                    coefficients[i, j] = 0
                elif j == 3:
                    coefficients[i, j] = 1.0
                else:
                    if j > 3:
                        k = j - 2
                    else:
                        k = j
                    coefficients[i, j] = self._to_double(
                        data[i * 8 + 2 * k + 1],
                        data[i * 8 + 2 * k],
                        bitlength=bitlength,
                        shift=shift)
                    if j > 3 and self._invert:
                        coefficients[i, j] *= -1
        return coefficients

    @coefficients.setter
    def coefficients(self, v):
        bitlength = self._IIRBITS
        shift = self._IIRSHIFT
        stages = self._IIRSTAGES
        v = np.array([vv for vv in v], dtype=np.float64)
        l = len(v)
        if l > stages:
            raise Exception(
                "Error: Filter contains too many sections to be implemented")
        data = np.zeros(stages * 8, dtype=np.uint32)
        for i in range(l):
            for j in range(6):
                if j == 2:
                    if v[i, j] != 0:
                        self._logger.warning("Attention: b_2 (" + str(i) \
                                             + ") is not zero but " + str(v[i, j]))
                elif j == 3:
                    if v[i, j] != 1:
                        self._logger.warning("Attention: a_0 (" + str(i) \
                                             + ") is not one but " + str(v[i, j]))
                else:
                    if j > 3:
                        k = j - 2
                        if self._invert:
                            v[i, j] *= -1
                    else:
                        k = j
                    hi, lo = self._from_double(
                        v[i, j], bitlength=bitlength, shift=shift)
                    data[i * 8 + k * 2 + 1] = hi
                    data[i * 8 + k * 2] = lo
        data = [int(d) for d in data]
        self._writes(0x8000, data)
        self._writtendata = data

    def _setup_unity(self):
        """sets the IIR filter transfer function unity"""
        c = np.zeros((self._IIRSTAGES, 6), dtype=np.float64)
        c[0, 0] = 1.0
        c[:, 3] = 1.0
        self.coefficients = c
        self.loops = 1

    def _setup_zero(self):
        """sets the IIR filter transfer function zero"""
        c = np.zeros((self._IIRSTAGES, 6), dtype=np.float64)
        c[:, 3] = 1.0
        self.coefficients = c
        self.loops = 1

    def _setup(self):
        """
        Setup an IIR filter

        the transfer function of the filter will be (k ensures DC-gain = g):

                  (s-2*pi*z[0])*(s-2*pi*z[1])...
        H(s) = k*-------------------
                  (s-2*pi*p[0])*(s-2*pi*p[1])...

        returns
        --------------------------------------------------
        coefficients   data to be passed to iir.bodeplot to plot the
                       realized transfer function
        """
        if self._IIRSTAGES == 0:
            raise Exception("Error: This FPGA bitfile does not support IIR "
                            "filters! Please use an IIR version!")
        self.on = False
        self.shortcut = False
        # design the filter
        self.iirfilter = iir_theory.IirFilter(zeros=self.zeros,
                                              poles=self.poles,
                                              gain=self.gain,
                                              loops=self.loops,
                                              dt=8e-9 * self._frequency_correction,
                                              minloops=self._minloops,
                                              maxloops=self._maxloops,
                                              iirstages=self._IIRSTAGES,
                                              totalbits=self._IIRBITS,
                                              shiftbits=self._IIRSHIFT,
                                              inputfilter=0,
                                              moduledelay=self._delay)
        # set loops in fpga
        self.loops = self.iirfilter.loops
        # write to the coefficients register
        self.coefficients = self.iirfilter.coefficients
        self._logger.info("Filter sampling frequency is %.3s MHz",
                          1e-6 / self.sampling_time)
        # low-pass filter the input signal with a first order filter with
        # cutoff near the sampling rate - decreases aliasing and achieves
        # higher internal data precision (3 extra bits) through averaging

        #if inputfilter is None:
        #    self.inputfilter = 125e6 * self._frequency_correction / self.loops
        #else:
        #    self.inputfilter = inputfilter
        self.iirfilter.inputfilter = self.inputfilter  # update model
        self._logger.info("IIR anti-aliasing input filter set to: %s MHz",
                          self.iirfilter.inputfilter * 1e-6)
        # connect the module
        #if input is not None:
        #    self.input = input
        #if output_direct is not None:
        #    self.output_direct = output_direct
        # switch it on only once everything is set up
        self.on = True ### wsa turnon before...
        self._logger.info("IIR filter ready")
        # compute design error
        dev = (np.abs((self.coefficients[0:len(self.iirfilter.coefficients)] -
                       self.iirfilter.coefficients).flatten()))
        maxdev = max(dev)
        reldev = maxdev / \
                 abs(self.iirfilter.coefficients.flatten()[np.argmax(dev)])
        if reldev > 0.05:
            self._logger.warning(
                "Maximum deviation from design coefficients: %.4g "
                "(relative: %.4g)", maxdev, reldev)
        else:
            self._logger.info("Maximum deviation from design coefficients: "
                              "%.4g (relative: %.4g)", maxdev, reldev)
        if bool(self.overflow):
            self._logger.warning("IIR Overflow detected. Pattern: %s",
                                 bin(self.overflow))
        else:
            self._logger.info("IIR Overflow pattern: %s", bin(self.overflow))

        self._signal_launcher.update_plot.emit()
        """ # obviously have to do something with that...
        if designdata or plot:
            maxf = 125e6 / self.loops
            fs = np.linspace(maxf / 1000, maxf, 2001, endpoint=True)
            designdata = self.iirfilter.designdata
            if plot:
                iir.bodeplot(designdata, xlog=True)
            return designdata
        else:
            return None
        """
    def setup_old(
            self,
            zeros,
            poles,
            gain=1.0,
            input=None,
            output_direct=None,
            loops=None,
            plot=False,
            designdata=False,
            turn_on=True,
            inputfilter=0,  # disabled by default
            tol=1e-3,
            prewarp=True):
        """Setup an IIR filter

        the transfer function of the filter will be (k ensures DC-gain = g):

                  (s-2*pi*z[0])*(s-2*pi*z[1])...
        H(s) = k*-------------------
                  (s-2*pi*p[0])*(s-2*pi*p[1])...

        parameters
        --------------------------------------------------
        zeros:         list of zeros in the complex plane, maximum 16
        poles:         list of zeros in the complex plane, maxumum 16
        gain:          DC-gain
        input:         input signal
        output_direct: send directly to an analog output?
        loops:         clock cycles per loop of the filter. must be at least 3
                       and at most 255. set None for autosetting loops
        turn_on:       automatically turn on the filter after setup
        plot:          if True, plots the theoretical and implemented transfer
                       functions
        designdata:    if True, returns various design transfer functions in a
                       format that can be passed to iir.bodeplot
        inputfilter:   the bandwidth of the input filter for anti-aliasing.
                       If None, it is set to the sampling frequency.
        tol:           tolerance for matching conjugate poles or zeros into
                       pairs, 1e-3 is okay
        prewarp:       Enables prewarping of frequencies. Strongly recommended.

        returns
        --------------------------------------------------
        coefficients   data to be passed to iir.bodeplot to plot the
                       realized transfer function
        """
        if self._IIRSTAGES == 0:
            raise Exception("Error: This FPGA bitfile does not support IIR "
                            "filters! Please use an IIR version!")
        self.on = False
        self.shortcut = False
        # design the filter
        self.iirfilter = iir_theory.IirFilter(zeros=zeros,
                                              poles=poles,
                                              gain=gain,
                                              loops=loops,
                                              dt=8e-9 * self._frequency_correction,
                                              minloops=self._minloops,
                                              maxloops=self._maxloops,
                                              iirstages=self._IIRSTAGES,
                                              totalbits=self._IIRBITS,
                                              shiftbits=self._IIRSHIFT,
                                              inputfilter=0,
                                              moduledelay=self._delay)
        # set loops in fpga
        self.loops = self.iirfilter.loops
        # write to the coefficients register
        self.coefficients = self.iirfilter.coefficients
        self._logger.info("Filter sampling frequency is %.3s MHz",
                          1e-6 / self.sampling_time)
        # low-pass filter the input signal with a first order filter with
        # cutoff near the sampling rate - decreases aliasing and achieves
        # higher internal data precision (3 extra bits) through averaging
        if inputfilter is None:
            self.inputfilter = 125e6 * self._frequency_correction / self.loops
        else:
            self.inputfilter = inputfilter
        self.iirfilter.inputfilter = self.inputfilter  # update model
        self._logger.info("IIR anti-aliasing input filter set to: %s MHz",
                          self.iirfilter.inputfilter * 1e-6)
        # connect the module
        if input is not None:
            self.input = input
        if output_direct is not None:
            self.output_direct = output_direct
        # switch it on only once everything is set up
        self.on = turn_on
        self._logger.info("IIR filter ready")
        # compute design error
        dev = (np.abs((self.coefficients[0:len(self.iirfilter.coefficients)] -
                       self.iirfilter.coefficients).flatten()))
        maxdev = max(dev)
        reldev = maxdev / \
                 abs(self.iirfilter.coefficients.flatten()[np.argmax(dev)])
        if reldev > 0.05:
            self._logger.warning(
                "Maximum deviation from design coefficients: %.4g "
                "(relative: %.4g)", maxdev, reldev)
        else:
            self._logger.info("Maximum deviation from design coefficients: "
                              "%.4g (relative: %.4g)", maxdev, reldev)
        if bool(self.overflow):
            self._logger.warning("IIR Overflow detected. Pattern: %s",
                                 bin(self.overflow))
        else:
            self._logger.info("IIR Overflow pattern: %s", bin(self.overflow))
        if designdata or plot:
            maxf = 125e6 / self.loops
            fs = np.linspace(maxf / 1000, maxf, 2001, endpoint=True)
            designdata = self.iirfilter.designdata
            if plot:
                iir_theory.bodeplot(designdata, xlog=True)
            return designdata
        else:
            return None

    @property
    def sampling_time(self):
        return 8e-9 / self._frequency_correction * self.loops

    ### this function is pretty much obsolete now. use self.iirfilter.tf_...
    def transfer_function(self, frequencies, extradelay=0, kind='final'):
        """
        Returns a complex np.array containing the transfer function of the
        current IIR module setting for the given frequency array. The
        best-possible estimation of delays is automatically performed for
        all kinds of transfer function. The setting of 'shortcut' is ignored
        for this computation, i.e. the theoretical and measured transfer
        functions can only agree if shortcut is False.

        Parameters
        ----------
        frequencies: np.array or float
            Frequencies to compute the transfer function for
        extradelay: float
            External delay to add to the transfer function (in s). If zero,
            only the delay for internal propagation from input to
            output_signal is used. If the module is fed to analog inputs and
            outputs, an extra delay of the order of 150 ns must be passed as
            an argument for the correct delay modelisation.
        kind: str
            The IIR filter design is composed of a number of steps. Each
            step slightly modifies the transfer function to adapt it to
            the implementation of the IIR. The various intermediate transfer
            functions can be helpful to debug the iir filter.

            kind should be one of the following (default is 'implemented'):
            - 'all': returns a list of data to be passed to iir.bodeplot
              with all important kinds of transfer functions for debugging
            - 'continuous': the designed transfer function in continuous time
            - 'before_partialfraction_continuous': continuous filter just
              before partial fraction expansion of the coefficients. The
              partial fraction expansion introduces a large numerical error for
              higher order filters, so this is a good place to check whether
              this is a problem for a particular filter design
            - 'before_partialfraction_discrete': discretized filter just before
              partial fraction expansion of the coefficients. The partial
              fraction expansion introduces a large numerical error for higher
              order filters, so this is a good place to check whether this is
              a problem for a particular filter design
            - 'before_partialfraction_discrete_zoh': same as previous,
              but zero order hold assumption is used to transform from
              continuous to discrete
            - 'discrete': the transfer function after transformation to
              discrete time
            - 'discrete_samplehold': same as discrete, but zero delay
              between subsequent biquads is assumed
            - 'highprecision': hypothetical transfer function assuming that
              64 bit fixed point numbers were used in the fpga (decimal point
              at bit 48)
            - 'implemented': transfer function after rounding the
              coefficients to the precision of the fpga

        Returns
        -------
        tf: np.array(..., dtype=np.complex)
            The complex open loop transfer function of the module.
        If kind=='all', a list of plotdata tuples is returned that can be
        passed directly to iir.bodeplot().
        """
        # frequencies = np.array(frequencies, dtype=np.float)
        # take average delay to be half the loops since this is the
        # expectation value for the delay (plus internal propagation delay)
        # module_delay = self._delay + self.loops / 2.0
        tf = self.iirfilter.__getattribute__('tf_' + kind)(frequencies)
        # for f in [self.inputfilter]:  # only one filter at the moment
        #    if f == 0:
        #        continue
        #    if f > 0:  # lowpass
        #        tf /= (1.0 + 1j*frequencies/f)
        #        module_delay += 2  # two cycles extra delay per lowpass
        #    elif f < 0:  # highpass
        #        tf /= (1.0 + 1j*f/frequencies)
        #        # plus is correct here since f already has a minus sign
        #        module_delay += 1  # one cycle extra delay per highpass
        ## add delay
        # delay = module_delay * 8e-9 / self._frequency_correction + extradelay
        # tf *= np.exp(-1j*delay*frequencies*2*np.pi)
        return tf

    bf = None

    # def bodefit(self, id):
    #    """ launches the gui to fit a transfer function and allows to use
    #    the fit transfer function as IIR filter loop shape

    #   Parameters
    #    ----------
    #    id: int
    #      id of the curve containing the transfer function to work on
    #    """
    #    self.bf = bodefit.BodeFitIIRGuiOptimisation(id)
    #    self.bf.lockbox = self._rp
    #    self.bf.iir = self
    #    return self.bf