from . import iir_theory #, bodefit
from .. import FilterModule
from ...attributes import IntRegister, BoolRegister, ComplexProperty, \
    FloatProperty, StringProperty, CurveSelectProperty, \
    GainRegister, ConstantIntRegister, FloatAttributeListProperty, \
    ComplexAttributeListProperty, BoolProperty, SelectProperty
from ...widgets.module_widgets import IirWidget
from ...modules import SignalLauncher

import numpy as np
from qtpy import QtCore
from scipy.signal import freqz


class SignalLauncherIir(SignalLauncher):
    update_plot = QtCore.Signal()


class OverflowProperty(StringProperty):
    def get_value(self, obj):
        value = obj.overflow_bitfield
        if value == 0:
            text = 'no overflow'
        elif bool(value & 0b1111111):
            text = "sum and internal saturation"
        elif bool(value & 0b1000000):
            text = 'sum saturation'
        elif bool(value & 0b0111111):
            text = 'internal saturation'
        else:
            text = 'unknown overflow %d'%value
        return text

    def validate_and_normalize(self, obj, value):
        # this is a read-only property, but it has to be read to reset it
        return self.get_value(obj)

    def set_value(self, obj, value):
        # this is a read-only property, but it has to be read to reset it
        self.launch_signal(obj, value)


# The properties zeros/poles are the master properties to store zeros or
# poles. For user interface reasons, we divide these lists into its real and
# complex parts (slave properties). IirListProperty is for zeros/poles,
# IirFloatListProperty and IirComplexListProperty are for the real/complex
# parts. These custom classes are intended to keep the master and slave in
# synchrony.
class IirListProperty(ComplexProperty):
    """
    master property to store zeros and poles
    """
    default = []

    def set_value(self, obj, value):
        """
        the master's setter writes its value to the slave lists
        """
        real, complex = [], []
        for v in value:
            # separate real from complex values
            if np.imag(v) == 0:
                real.append(v.real)
            else:
                complex.append(v)
        # avoid calling setup twice
        with obj.do_setup:
            setattr(obj, 'complex_' + self.name, complex)
            setattr(obj, 'real_' + self.name, real)
        # this property should have call_setup=True, such that obj._setup()
        # is called automatically after this function

    def get_value(self, obj):
        """
        the master's getter collects its value from the real and complex list
        """
        return list(getattr(obj, 'complex_'+self.name) + getattr(obj, 'real_'+self.name))

    def validate_and_normalize(self, obj, value):
        """
        Converts the value in a list of float numbers.
        """
        if not np.iterable(value):
            value = [value]
        return [self.validate_and_normalize_element(obj, val) for val in value]

    def validate_and_normalize_element(self, obj, val):
        return super(IirListProperty, self).validate_and_normalize(obj, val)


class IirFloatListProperty(FloatAttributeListProperty):
    """
    slave property to store real part of zeros and poles
    """
    def value_updated(self, obj, value=None, appendix=[]):
        super(IirFloatListProperty, self).value_updated(obj,
                                                        value=value,
                                                        appendix=appendix)
        pole_or_zero = self.name.split('_')[1]  # 2nd part of name is pole/zero
        # forward value_updated to master
        getattr(obj.__class__, pole_or_zero).value_updated(obj)

    def validate_and_normalize_element(self, obj, val):
        """
        makes sure that real poles are strictly positive. val=0 is turned into val=-1.
        """
        val = FloatAttributeListProperty.validate_and_normalize_element(self, obj, val)
        pole_or_zero = self.name.split('_')[1]  # 2nd part of name is pole/zero
        if val > 0 and pole_or_zero == 'pole':
            obj._logger.warning('Real pole %s has a positive real part. '
                                'This will lead to unstable behavior. '
                                'The value was changed to %s. ',
                                val, val*-1)
            val *= -1
        if val == 0:
            obj._logger.warning('Real %s %s has a real part of zero. This will lead to '
                                'unstable behavior. The value was changed to %s. ',
                                pole_or_zero, val, -1)
            val = -1
        return val

    def list_changed(self, module, operation, index, value=None):
        """ make sure that only one element from one of the four lists is selected at once"""
        if operation == 'select':
            # unselect all others
            if not hasattr(module, '_selecting') or not getattr(module, '_selecting'):
                try:
                    setattr(module, '_selecting', True)
                    for name in [start+'_'+end for start in ['real', 'complex'] for end in ['poles', 'zeros']]:
                        if name != self.name:
                            getattr(module, name).selected = None
                            module._logger.debug('%s.selected = None', name)
                    setattr(module, '_selected_pole_or_zero', self.name)
                    setattr(module, '_selected_index', index)
                finally:
                    setattr(module, '_selecting', False)
                module._signal_launcher.update_plot.emit()
        super(IirFloatListProperty, self).list_changed(module, operation, index, value=value)


class IirComplexListProperty(IirFloatListProperty,
                             ComplexAttributeListProperty):
    """
    slave property to store complex part of zeros and poles
    """
    def validate_and_normalize_element(self, obj, val):
        """
        real part should be strictly negative. imaginary part is in principle arbitrary,
        but will be kept positive for simplicity.
        """
        val = ComplexAttributeListProperty.validate_and_normalize_element(self, obj, val)
        re = val.real
        im = val.imag
        pole_or_zero = self.name.split('_')[1]  # 2nd part of name is pole/zero
        if re > 0 and pole_or_zero == 'pole':
            re *= -1
            obj._logger.warning('Real pole %s has a positive real part. '
                                'This will lead to unstable behavior. '
                                'The value was changed to %s. ',
                                val, )
        if re == 0:
            re = -1
            obj._logger.warning('Real %s %s has a real part of zero. This will lead to '
                                'unstable behavior. The value was changed to %s. ',
                                pole_or_zero, val, complex(re, im))
        if im < 0:
            im *= -1
            obj._logger.info('Imaginary part of complex %s %s was inverted for simplicity. '
                             'New value is %s.',
                             pole_or_zero, val, complex(re, im))
        return complex(re, im)


class TfTypeProperty(SelectProperty):
    def value_updated(self, module, value=None, appendix=[]):
        super(TfTypeProperty, self).value_updated(module,
                                                  value=value)
        module._signal_launcher.update_plot.emit()

class IIR(FilterModule):
    _signal_launcher = SignalLauncherIir
    iirfilter = None  # will be set by setup()
    _minloops = 3  # minimum number of loops for correct behaviour
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

    _IIRBITS = ConstantIntRegister(0x200)

    _IIRSHIFT = ConstantIntRegister(0x204)

    _IIRSTAGES = ConstantIntRegister(0x208)

    _widget_class = IirWidget

    _setup_attributes = ["input",
                         "loops",
                         "zeros",
                         "poles",
                         "output_direct",
                         "inputfilter",
                         "gain",
                         "on",
                         "bypass",
                         "data_curve",
                         "plot_data",
                         "plot_data_times_filter"]

    _gui_attributes = ["input",
                       "loops",
                       "complex_zeros",
                       "complex_poles",
                       "real_zeros",
                       "real_poles",
                       "output_direct",
                       "inputfilter",
                       "gain",
                       "on",
                       "bypass",
                       "overflow",
                       "data_curve",
                       "data_curve_name",
                       "plot_data",
                       "plot_data_times_filter",
                       "plot_measurement",
                       "measure_transfer_function",
                       "tf_type"
                       # for debugging
                       # "_setup_unity",
                       # "_setup_zero",
                       ]

    loops = IntRegister(0x100,
                        doc="Decimation factor of IIR w.r.t. 125 MHz. Must be "
                            "at least %d. " % _minloops,
                        default=_minloops,
                        min=_minloops,
                        max=_maxloops,
                        call_setup=True)

    on = BoolRegister(0x104, 0,
                      doc="IIR is on",
                      default=False)

    bypass = BoolRegister(0x104, 1,
                          doc="IIR is bypassed",
                          default=False)  # fpga register name: shortcut

    # principal storage of the pole/zero data, _setup is called through
    # zeros/poles defined just below
    complex_poles = IirComplexListProperty(default=[],
                                           default_element=10000.0j-1000.0,
                                           log_increment=True)
    complex_zeros = IirComplexListProperty(default=[],
                                           default_element=10000.0j-1000.0,
                                           log_increment=True)
    real_poles = IirFloatListProperty(default=[],
                                      default_element=-10000.0,
                                      log_increment=True)
    real_zeros = IirFloatListProperty(default=[],
                                      default_element=-10000.0,
                                      log_increment=True)

    # convenience properties to manipulate combined list
    zeros = IirListProperty(call_setup=True)
    poles = IirListProperty(call_setup=True)

    gain = FloatProperty(min=-1e20, max=1e20,
                         default=1.0,
                         increment=1e-20,
                         log_increment=True,
                         call_setup=True
                         )

    overflow_bitfield = IntRegister(0x108,
                                    doc="Bitmask for various overflow conditions")

    overflow = OverflowProperty(doc="a string indicating the overflow status "
                                    "of the iir module")

    tf_type = TfTypeProperty(default='final',
                             options=['continuous',
                                      'discrete',
                                      'coefficients',
                                       'rounded',
                                       'final'],
                                    doc="Type of transfer-function to use in "
                                        "plot (see iir_theory for details)",
                                    call_setup=False)

    data_curve = CurveSelectProperty(doc="NA curve id to use as a basis for "
                                         "the graphical filter design",
                                     no_curve_first=True,
                                     call_setup=True,
                                     default=-1)

    data_curve_name = StringProperty(doc="Name of the selected data curve. ")

    plot_data = BoolProperty(default=True, call_setup=True, doc="Enables plotting the selected data_curve. ")

    plot_data_times_filter = BoolProperty(default=True, call_setup=True, doc="Enables plotting the product of selected data_curve and iir filter. ")

    plot_measurement = BoolProperty(default=True, call_setup=True, doc="Enables plotting the measured transfer function. ")

    @property
    def output_saturation(self):
        """ returns True if the output of the IIR filter has saturated since
        the last reset """
        return bool(self.overflow_bitfield & 1 << 6)

    @property
    def internal_overflow(self):
        """ returns True if the IIR filter has experienced an internal
        overflow (leading to saturation) since the last reset"""
        overflow = bool(self.overflow_bitfield & 0b111111)
        if overflow:
            self._logger.info("Internal overflow has occured. Bit pattern "
                              "%s", bin(self.overflow_bitfield))
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
        if v is None:
            v = []
            self._logger.warning("Iir coefficient was set to None. "
                                 "and converted to an empty list. ")
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

    def measure_transfer_function(self):
        self._logger.info("Starting NA acquisition. To modify measurement "
                          "parameters, change the state \"iir_measurement\" "
                          "of the NA. ")
        with self.pyrpl.networkanalyzer as na:
            try:
                na.load_state('iir_measurement')
            except KeyError:
                if hasattr(self, '_module_widget'):
                    freqs = self._module_widget.frequencies
                else:
                    freqs = np.logspace(2, np.log10(5e6), 2000)
                mi, ma = min(freqs), max(freqs)
                na.setup(start_freq=mi,
                         stop_freq=ma,
                         points=501,
                         rbw=500,
                         avg_per_point=1,
                         trace_average=1,
                         amplitude=1.,
                         input=self,
                         output_direct='off',
                         acbandwidth=100,
                         logscale=True)
                na.save_state("iir_measurement")
            former_input = self.input
            try:
                # set input to be the NA output and take the data
                self.input = 'networkanalyzer'
                data = na.single()
                self._measurement_data = na.frequencies, data
            finally:
                self.input = former_input
        self._logger.info("NA acquisition finished.")
        # re-plot
        self._signal_launcher.update_plot.emit()
        return self._measurement_data

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
        Setup an IIR filter.

        the transfer function of the filter will be (k ensures DC-gain = g):

                  (s-2*pi*z[0])*(s-2*pi*z[1])...
        H(s) = k*-------------------
                  (s-2*pi*p[0])*(s-2*pi*p[1])...
        """
        with self.do_setup:
            if self._IIRSTAGES == 0:
                raise Exception("Error: This FPGA bitfile does not support IIR "
                                "filters! Please use an IIR version!")
            self.on = False
            # don't mess with bypass parameter
            #self.bypass = False
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
            self._logger.debug("Filter sampling frequency is %.3s MHz",
                              self.sampling_frequency*1e-6)
            # low-pass filter the input signal with a first order filter with
            # cutoff near the sampling rate - decreases aliasing and achieves
            # higher internal data precision (3 extra bits) through averaging

            #if inputfilter is None:
            #    self.inputfilter = 125e6 * self._frequency_correction / self.loops
            #else:
            #    self.inputfilter = inputfilter
            self.iirfilter.inputfilter = self.inputfilter  # update model
            self._logger.debug("IIR anti-aliasing input filter set to: %s MHz",
                              self.iirfilter.inputfilter * 1e-6)
            if any(np.real(self.poles)>0):
                self._logger.warning("Pole with positive real part detected"
                                     "filter will be unstable.")

            # connect the module
            #if input is not None:
            #    self.input = input
            #if output_direct is not None:
            #    self.output_direct = output_direct
            # switch it on only once everything is set up
            self.on = True ### wsa turnon before...
            self._logger.debug("IIR filter ready")
            # compute design error
            dev = (np.abs((self.coefficients[0:len(self.iirfilter.coefficients)] -
                           self.iirfilter.coefficients).flatten()))
            maxdev = max(dev)
            reldev = maxdev / abs(self.iirfilter.coefficients.flatten()[np.argmax(dev)])
            if reldev > 0.05:
                self._logger.warning(
                    "Maximum deviation from design coefficients: %.4g "
                    "(relative: %.4g)", maxdev, reldev)
            else:
                self._logger.debug("Maximum deviation from design coefficients: "
                                   "%.4g (relative: %.4g)", maxdev, reldev)
            if bool(self.overflow_bitfield):
                self._logger.warning("IIR Overflow detected. Pattern: %s",
                                     bin(self.overflow_bitfield))
            else:
                self._logger.debug("IIR Overflow pattern: %s",
                                   bin(self.overflow_bitfield))
            self._signal_launcher.update_plot.emit()
            # update curve name
            try: self.data_curve_name = self._data_curve_object.name
            except AttributeError: pass

    @property
    def sampling_time(self):
        return 8e-9 / self._frequency_correction * self.loops

    @property
    def sampling_frequency(self):
        return 1.0/self.sampling_time

    def select_pole_or_zero(self,
                            value,
                            logdist=True,
                            search_in=[start+'_'+end
                                       for start in ['real', 'complex']
                                       for end in ['poles', 'zeros']]):
        """
        selects the pole or zero closest to value

        logdist=True computes the distance in logarithmic units
        search_in may be used to restrict the search to certain sublists
        """
        mindist = None
        for name in search_in:
            for element in getattr(self, name):
                if name.startswith('complex'):
                    # complex values are ordered by their imaginary part
                    elementvalue = element.imag
                else:
                    elementvalue = element
                if logdist:
                    dist = abs(abs(value)/abs(elementvalue))
                    if dist < 1.0:
                        dist = 1.0/dist
                else:
                    dist = abs(abs(value)-abs(elementvalue))
                # extract element with minimum distance
                if mindist is None or dist < mindist:
                    mindist = dist
                    bestmatch = element
                    bestname = name
        if mindist is None:
            # nothing found, select nothing
            self.complex_poles.selected = None
        else:
            getattr(self, bestname).select(bestmatch)


    def transfer_function_by_kind(self, frequencies, kind):
        """
        Returns a complex np.array containing the transfer function of the
        current IIR module setting for the given frequency array. The
        best-possible estimation of delays is automatically performed for
        all kinds of transfer function. The setting of 'bypass' is ignored
        for this computation, i.e. the theoretical and measured transfer
        functions can only agree if bypass is False.

        Parameters
        ----------
        frequencies: np.array or float
            Frequencies to compute the transfer function for
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
        :param frequencies:
        :param kind:
        :return:
        """
        try:
            tf = getattr(self.iirfilter, 'tf_' + kind)(frequencies=frequencies)
        except AttributeError:
            # happens when no iir filter is created
            tf = frequencies*0+1e-12
        return tf

    ### this function is pretty much obsolete now. use self.iirfilter.tf_...
    def transfer_function(self, frequencies, extradelay=0):
        """
        Returns a complex np.array containing the transfer function of the
        current IIR module setting for the given frequency array. The
        best-possible estimation of delays is automatically performed for
        all kinds of transfer function. The setting of 'bypass' is ignored
        for this computation, i.e. the theoretical and measured transfer
        functions can only agree if bypass is False.

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

        Returns
        -------
        tf: np.array(..., dtype=complex)
            The complex open loop transfer function of the module.
        If kind=='all', a list of plotdata tuples is returned that can be
        passed directly to iir.bodeplot().
        """
        # frequencies = np.array(frequencies, dtype=np.float)
        # take average delay to be half the loops since this is the
        # expectation value for the delay (plus internal propagation delay)
        # module_delay = self._delay + self.loops / 2.0

        return self.iirfilter.tf_final(frequencies)


    def simulate_filter_float(self, xs, biquad="all"):
        """
        plots the response of the iir filter to a time series xs (sampling time
        is dt*loops
        :param freq:
        :return:
        """
        if biquad=='all':
            coefs = self.coefficients
        else:
            coefs = [self.coefficients[biquad]]

        ys = np.zeros(len(xs))
        ys_biquad = np.zeros((len(coefs), 2))
        for index in range(2, len(xs)):
            for index_biquad, (b0, b1, _, _, a1, a2) in enumerate(coefs):
                adder = -  a1 * ys_biquad[index_biquad, 0] - a2 * ys_biquad[index_biquad, 1]

                y = b0 * xs[index] + b1 * xs[index - 1] + adder
                ys[index] += y
                ys_biquad[index_biquad, 1] = ys_biquad[index_biquad, 0]
                ys_biquad[index_biquad, 0] = y
        return ys

    def simulate_filter_int(self, xs, biquad="all"):
        """
        plots the response of the iir filter to a time series xs (sampling time
        is dt*loops
        :param freq:
        :return:
        """
        print("yo")

        if biquad == 'all':
            coefs = self.coefficients
        else:
            coefs = [self.coefficients[biquad]]
        coefs = np.array(coefs)

        coefs = np.asarray(coefs*(2**self._IIRSHIFT), dtype=np.int64)


        if xs.dtype != int:
            raise TypeError("expected an integer input array")

        if any(xs > 2**13 - 1):
            raise ValueError("input should not exceed 2**13 - 1 = 8191")

        if any(xs < -2**13):
            raise ValueError("input should not exceed -2**13 = -8192")



        xs = xs*2**3 # pre-filters change the signal from 14 to 17 bits
        xs = xs*2**(-self._IIRBITS + 17 + self._IIRSHIFT + 1)


        ys = np.zeros(len(xs), dtype=np.int64)
        ys_biquad = np.zeros((len(coefs), 2), dtype=np.int64)

        for index in range(2, len(xs)):
            for index_biquad, (b0, b1, _, _, a1, a2) in enumerate(coefs):
                p_ay1 = self._product_sat(-a1, ys_biquad[index_biquad, 0])
                p_ay2 = self._product_sat(-a2, ys_biquad[index_biquad, 1])
                p_bx0 = self._product_sat(b0, xs[index])
                p_bx1 = self._product_sat(b1, xs[index - 1])
                y = self._saturate(p_ay1 + p_ay2 + p_bx0 + p_bx1, bits=self._IIRBITS)
                ys[index] += y
                ys_biquad[index_biquad, 1] = ys_biquad[index_biquad, 0]
                ys_biquad[index_biquad, 0] = y

        return ys//2**(self._IIRBITS - 14)


    def measure_time_domain_response(self, freq, biquad='all'):
        from pyrpl.async_utils import sleep, wait

        if biquad=='all':
            coefs = self.coefficients
        else:
            coefs = [self.coefficients[biquad]]
        self.coefficients = coefs

        with self.pyrpl.asgs.pop("iir_measurement") as asg:
            asg.trigger_source = "off"
            asg.frequency = freq
            asg.amplitude = 1
            asg.offset=0
            asg.output_direct = 'off'

            old_input = self.input
            self.input = asg

            with self.pyrpl.scopes.pop("iir_measurement") as scope:
                scope.input1 = asg
                scope.input2 = self
                scope.trigger_source = "ch1_positive_edge"
                scope.threshold = 0.01
                scope.duration = 100./freq
                times = scope.times
                scope.rolling_mode = False

                res = scope.single_async()
                sleep(0.1)
                asg.trigger_source = 'immediately'
                sleep(0.1)
                ch1, ch2 = wait(res)
                self.input = old_input
        self._setup()
        return times, ch2

    def plot_biquads_tf(self, axes=None, plot_experiment=True):
        """Plots the transfer function of each biquad. if
        plot_experiment is True, superimpose the measured transfer functions
        (using the networkanalyzer)"""
        freqs = np.logspace(1, 7, 1001)
        z_all = np.zeros(len(freqs), dtype=complex)
        axes = None
        tfs = []
        freqs_all = []
        labels = []
        for b0, b1, _, _, a1, a2 in self.coefficients:
            if any((b0, b1, a1, a2)):
                f, z = freqz((b0, b1), (1, a1, a2),
                             worN=2 * np.pi * freqs * self.iirfilter.dt *
                                  self.loops)
                z_all += z
                tfs.append(z)
                freqs_all.append(freqs)
                labels.append(f"b0={b0:.5f}, b1={b1:.5f}, a1={a1:.5f}, " \
                               f"a2={a2:.5f}")
                if plot_experiment:
                    coeffs = np.zeros((5, 6))
                    coeffs[:, 2] = 0
                    coeffs[:, 3] = 1
                    coeffs[0] = (b0, b1, 0., 1., a1, a2)
                    self.coefficients = coeffs
                    freqs_na, z_na = self.measure_transfer_function()
                    tfs.append(z_na)
                    freqs_all.append(freqs_na)
                    labels.append("measured")
        self._setup()
        iir_theory.bodeplot(np.transpose([freqs_all, tfs, labels]))
        return axes

    def _digitize14bits(self, val):
        """
        digitize with a 14 bits resolution
        :param val:
        :return:
        """
        return int(np.floor(val*2**13))

    def _product_sat(self, factor1_i, factor2_i):
        result = (factor1_i*factor2_i)//(2**self._IIRSHIFT)
        assert(np.abs(result - np.float64(factor1_i) * np.float64(
            factor2_i)/(2**self._IIRSHIFT)) < 1)
        return self._saturate(result, bits=self._IIRBITS)

    def _saturate(self, val, bits):
        if val > 2**bits - 1:
            raise OverflowError(f"Overflox in saturate with {val} > {2**bits - 1}")
        if val < -2 ** bits:
                raise OverflowError(f"Overflox in saturate with {val} < {-2**bits}")
        return val

    def format_coefs_verilog(self):
        n = 0
        for b0, b1, _, _, a1, a2 in np.asarray(
                        self.coefficients*2**self._IIRSHIFT, dtype=int):
            print("iir_coefficients[", 2*n, "]<=", b0, ";")
            n+=1
            print("iir_coefficients[", 2*n, "]<=", b1, ";")
            n+=1
            print("iir_coefficients[", 2*n, "]<=", -a1, ";")
            n+=1
            print("iir_coefficients[", 2*n, "]<=", -a2, ";")
            n+=1