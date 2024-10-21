###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#    Copyright (C) 2014-2016  Leonhard Neuhaus  (neuhaus@spectro.jussieu.fr)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################
"""
The spectrum analyzer measures the magnitude of an input signal versus
frequency. There are two working modes for the spectrum analyzer implemented in
pyrpl:

- iq mode: the input signal is demodulated around the center_frequency of
  the analysis window (using iq2). The slowly varying quadratures are
  subsequently sent to the 2 channels of the scope. The complex IQ time trace
  is built from the sum I(t) + iQ(t). The spectrum is then evaluated by
  performing a Fourier transforom of the the complex iq signal.
- baseband mode: up to 2 channels are available in baseband mode. The
  channels are digitized by the scope and the real traces are directly Fourier
  transformed. Since both channels are acquired simultaneously, it is also
  possible to retrieve the cross spectrum between channel 1 and channel 2 (the
  relative phase of the fourier transform coefficients is meaningful)

At the moment, the iq mode is deactivated since we haven't yet implemented
the sharp antialiasing filters required to avoid polluting the analysis
windows from aliased noise originating from outside the Nyquist frequency of
the scope acquisition. However, we are planning on implementing such a
filter with the iir module in the near future.

In the following example, we are going to demonstrate how to measure a
sinusoidal signal and a white noise originating from an asg

.. code :: python

    # let's use a module manager for the asg
    with p.asgs.pop('user') as asg:
        # setup a sine at 100 kHz
        asg.setup(frequency=1e5, waveform='sin', trigger_source='immediately', amplitude=1., offset=0)

        # setup the spectrumanalyzer in baseband mode
        p.spectrumanalyzer.setup(input1_baseband=asg, #note that input1_baseband!=input)
                                 baseband=True, # only mod eavailable right now
                                 span=1e6, # span of the analysis (/2 in iq mode)
                                 window=blackman # filter window)

        # the return format is (spectrum for channel 1, spectrum for channel 2,
        # real part of cross spectrum, imaginary part of cross spectrum):
        ch1, ch2, cross_re, cross_im = p.spectrumanalyzer.curve()

    # plot the spectrum
    import matplotlib.pyplot as plt
    %matplotlib inline
    plt.plot(p.spectrumanalyzer.frequencies, ch1)

We notice that the spectrum is peaked around 100 kHz (The width of the peak
is given by the residual bandwidth), and the height of the peak is 1.

The internal unit of the spectrum analyzer is V_pk^2, such that a 1 V sine
results in a 1 Vpk^2 peak in the spectrum. To convert the spectrum in units
of noise spectral density, a utility function is provided: data_to_unit()

.. code :: python

    # let's use a module manager for the asg
    with p.asgs.pop('user') as asg:
        # setup a white noise of variance 0.1 V
        asg.setup(frequency=1e5, waveform='noise', trigger_source='immediately', amplitude=0.1, offset=0)

        # setup the spectrumanalyzer in baseband mode and full span
        p.spectrumanalyzer.setup(input1_baseband=asg, baseband=True, span=125e6)

        # the return format is (spectrum for channel 1, spectrum for channel 2,
        # real part of cross spectrum, imaginary part of cross spectrum):
        ch1, ch2, cross_re, cross_im = p.spectrumanalyzer.curve()

    # convert to Vrms^2/Hz
    data = p.spectrumanalyzer.data_to_unit(ch1, 'Vrms^2/Hz', p.spectrumanalyzer.rbw)

    # plot the spectrum
    import matplotlib.pyplot as plt
    %matplotlib inline
    plt.plot(p.spectrumanalyzer.frequencies, data)

    # integrate spectrum from 0 to nyquist frequency
    df = p.spectrumanalyzer.frequencies[1] - p.spectrumanalyzer.frequencies[0]
    print(sum(data)*df)

As expected, the integral of the noise spectrum over the whole frequency
range gives the variance of the noise. To know more about spectrum analysis
in Pyrpl, and in particular, how the filtering windows are normalized, please
refer to the section :ref:`How a spectrum is computed in PyRPL`.
"""

import logging
logger = logging.getLogger(name=__name__)

from ..module_attributes import *
from ..hardware_modules import Scope
from ..hardware_modules.dsp import all_inputs, InputSelectProperty
from ..acquisition_module import AcquisitionModule
from ..widgets.module_widgets import SpecAnWidget

import sys
import scipy.signal as sig
import scipy.fftpack as fft


# Some initial remarks about spectrum estimation:
# Main source: Oppenheim + Schaefer, Digital Signal Processing, 1975

class DisplayUnitProperty(SelectProperty):
    def set_value(self, obj, value):
        super(DisplayUnitProperty, self).set_value(obj, value)
        obj._emit_signal_by_name('unit_changed')

class CenterAttribute(FrequencyProperty):
    def get_value(self, instance):
        if instance is None:
            return self
        if instance.baseband:
            return 0.0
        else:
            return instance.iq.frequency

    def set_value(self, instance, value):
        if instance.baseband and value != 0:
            # former solution:
            # raise ValueError("Nonzero center frequency not allowed in "
            #                 "baseband mode.")
            # more automatic way:
            instance.baseband = False
        if not instance.baseband:
            instance.iq.frequency = value
        return value


class SpecAnAcBandwidth(FilterProperty):
    def valid_frequencies(self, module):
        return [freq for freq in
                module.iq.__class__.inputfilter.valid_frequencies(module.iq)
                if freq >= 0]


class RbwProperty(FilterProperty):
    def valid_frequencies(self, module):
        sample_rates = [1./st for st in Scope.sampling_times]
        return [module.equivalent_noise_bandwidth()*sr for sr in sample_rates]

    def get_value(self, obj):
        sampling_rate = 1./(8e-9*obj.decimation)
        return obj.equivalent_noise_bandwidth()*sampling_rate

    def set_value(self, obj, value):
        if np.iterable(value):
            value = value[0]
        sample_rate = value/obj.equivalent_noise_bandwidth()
        obj.decimation = int(round(1./(sample_rate*8e-9)))


class SpanFilterProperty(FilterProperty):
    def valid_frequencies(self, instance):
        return instance.spans

    def get_value(self, obj):
        #val = super(SpanFilterProperty, self).get_value(obj)
        #if np.iterable(val):
        #    return val[0] # maybe this should be the default behavior for
            # FilterAttributes... or make another Attribute type
        #else:
        #    return val
        return 1./(8e-9*obj.decimation)

    def set_value(self, obj, value):
        if np.iterable(value):
            value = value[0]
        sampling_time = 1./value
        obj.decimation = int(round(sampling_time/8e-9))


class DecimationProperty(SelectProperty):
    """
    Since the only integer number in [rbw, span, duration, decimation] is
    decimation, it is better to take it as the master property to avoid
    rounding problems.
    We don't want to use the scope property because when the scope is not
    slaved, the value could be anything.
    """

    def set_value(self, obj, value):
        super(DecimationProperty, self).set_value(obj, value)
        obj.__class__.span.value_updated(obj, obj.span)
        obj.__class__.rbw.value_updated(obj, obj.rbw)


class WindowProperty(SelectProperty):
    """
    Changing the filter window requires to recalculate the bandwidth
    """
    def set_value(self, obj, value):
        super(WindowProperty, self).set_value(obj, value)
        obj.__class__.rbw.refresh_options(obj)



class SpectrumAnalyzer(AcquisitionModule):
    """
    A spectrum analyzer is composed of an IQ demodulator, followed by a scope.
    The spectrum analyzer connections are made upon calling the function setup.
    """
    _widget_class = SpecAnWidget
    _gui_attributes = ["input",
                       "center",
                       "baseband",
                       "span",
                       "rbw",
                       #"points",
                       "window",
                       "acbandwidth",
                       "display_unit",
                       "display_input1_baseband",
                       "display_input2_baseband",
                       "input1_baseband",
                       "input2_baseband",
                       "display_cross_amplitude",
                       ]#"display_cross_phase"]
    _setup_attributes =["input",
                       "center",
                       "baseband",
                        # better to set baseband after center,
                        # otherwise, asking for baseband explicitly would be
                        # overwritten by non-zero center
                       "span",
                       #"rbw",
                       #"points",
                       "window",
                       "acbandwidth",
                       "display_unit",
                       "curve_unit",
                       "display_input1_baseband",
                       "display_input2_baseband",
                       "input1_baseband",
                       "input2_baseband",
                       "display_cross_amplitude",]
                       #"display_cross_phase"]
    PADDING_FACTOR = 16
    # numerical values
    nyquist_margin = 1.0
    if_filter_bandwidth_per_span = 1.0
    _enb_cached = dict() # Equivalent noise bandwidth for filter windows

    quadrature_factor = 1.# 0.1*1024

    # unit Vpk is such that the level of a peak in the spectrum indicates the
    # correct voltage amplitude of a coherent signal (linear scale)
    # more units can be added as needed, but need to guarantee that conversion
    # is done as well (see implementation in lockbox for example)
    display_unit = DisplayUnitProperty(default="dB(Vpk^2)",
                          options=["Vpk^2",
                                   "dB(Vpk^2)",
                                   "Vpk",
                                   "Vrms^2",
                                   "dB(Vrms^2)",
                                   "Vrms",
                                   "Vrms^2/Hz",
                                   "dB(Vrms^2/Hz)",
                                   "Vrms/sqrt(Hz)"],
                          ignore_errors=True)

    # curve_unit is only used to have a parameter 'curve_unit' in saved curves.
    # If >1 options are implemented, you should ensure that _get_curve takes it
    # into account.
    curve_unit = SelectProperty(default="Vpk^2", options=["Vpk^2"], ignore_errors=True)

    # select_attributes list of options
    def spans(nyquist_margin):
        # see http://stackoverflow.com/questions/13905741/
        # [int(np.ceil(1. / nyquist_margin / s_time))
        return [1./s_time \
             for s_time in Scope.sampling_times]
    spans = spans(nyquist_margin)

    windows = ['blackman', 'flattop', 'boxcar', 'hamming', 'gaussian']  # more
    # can be
    # added here (see http://docs.scipy.org/doc/scipy/reference/generated
    # /scipy.signal.get_window.html#scipy.signal.get_window)
    @property
    def inputs(self):
        return all_inputs(self).keys()

    # attributes
    baseband = BoolProperty(default=True, call_setup=True)
    span = SpanFilterProperty(doc="""
        Span can only be given by 1./sampling_time where sampling
        time is a valid scope sampling time.
        """,
        call_setup=True)
    center = CenterAttribute(call_setup=True)
    # points = IntProperty(default=16384, call_setup=True)
    window = WindowProperty(options=windows, call_setup=True)
    input = InputSelectProperty(options=all_inputs,
                                default='in1',
                                call_setup=True,
                                ignore_errors=True)
    input1_baseband = InputSelectProperty(options=all_inputs,
                                          default='in1',
                                          call_setup=True,
                                          ignore_errors=True,
                                          doc="input1 for baseband mode")
    input2_baseband = InputSelectProperty(options=all_inputs,
                                          default='in2',
                                          call_setup=True,
                                          ignore_errors=True,
                                          doc="input2 for baseband mode")
    display_input1_baseband = BoolProperty(default=True,
                                           doc="should input1 spectrum be "
                                               "displayed in "
                                               "baseband-mode?")
    display_input2_baseband = BoolProperty(default=True,
                                           doc="should input2 spectrum be "
                                               "displayed in "
                                               "baseband-mode?")
    display_cross_amplitude = BoolProperty(default=True,
                                           doc="should cross-spectrum "
                                               "amplitude be displayed "
                                               "in baseband-mode?")
    display_cross_phase = BoolProperty(default=False,
                                       doc="should cross-spectrum amplitude"
                                              " be displayed in "
                                              "baseband-mode?")
    rbw = RbwProperty(doc="Residual Bandwidth, this is a readonly "
                            "attribute, only span can be changed.")

    decimation = DecimationProperty(options=Scope.decimations,
                                    doc="Decimation setting for the "
                                            "scope.")

    acbandwidth = SpecAnAcBandwidth(call_setup=True)

    def __init__(self, parent, name=None):
        super(SpectrumAnalyzer, self).__init__(parent, name=name)
        self._transfer_function_square_cached = None

    @property
    def iq(self):
        if not hasattr(self, '_iq'):
            self._iq = self.pyrpl.rp.iq2  # can't use the normal pop
            # mechanism because we specifically want the customized iq2
            self._iq.owner = self.name
        return self._iq

    iq_quadraturesignal = 'iq2_2'

    def _remaining_duration(self):
        """
        Duration before next scope curve will be ready.
        """
        return self.scope._remaining_duration()

    @property
    def data_length(self):
        return self.scope.data_length
        #return int(self.points)  # *self.nyquist_margin)

    @property
    def sampling_time(self):
        return 1. / self.nyquist_margin / self.span

    def _remaining_duration(self):
        return self.scope._remaining_duration()

    def curve_ready(self):
        return self.scope.curve_ready()

    @property
    def scope(self):
        return self.pyrpl.rp.scope

    @property
    def duration(self):
        return self.scope.duration

    def filter_window(self):
        """
        :return: filter window
        """
        if self.window=='gaussian':
            #  a tuple with the std is needed for Gaussian window
            window_name = ('gaussian', self.data_length/10)
        else:
            window_name = self.window
        window = sig.get_window(window_name, self.data_length, fftbins=False)
        # empirical value for scaling flattop to sqrt(W)/V
        window/=(np.sum(window)/2)
        return window

    def _get_iq_data(self):
        """
        :return: complex iq time trace
        """
        res = self.scope._get_trace()

        if self.baseband:
            return res[0][:self.data_length] + 1j*res[1][:self.data_length]
        else:
            return (res[0] + 1j*res[1])[:self.data_length]
#            res += 1j*self.scope.curve(2, timeout=None)
#        return res[:self.data_length]

    def _get_filtered_iq_data(self):
        """
        :return: the product between the complex iq data and the filter_window
        """
        return self._get_iq_data() * np.asarray(self.filter_window(),
                                            dtype=complex)

    def useful_index_obsolete(self):
        """
        :return: a slice containing the portion of the spectrum between start
        and stop
        """
        middle = int(self.data_length / 2)
        length = self.points  # self.data_length/self.nyquist_margin
        if self.baseband:
            return slice(middle-1, middle + length/2 + 1)#slice(middle,
            # int(middle + length /
            #  2 +
            #  1))
        else:
            return slice(int(middle - length/2), int(middle + length/2 + 1))

    @property
    def _real_points(self):
        """
        In baseband, only half of the points are returned
        :return: the real number of points that will eventually be returned
        """
        points = int(self.data_length * self.PADDING_FACTOR)
        return points//2 + 1 if self.baseband else points

    @property
    def frequencies(self):
        """
        :return: frequency array
        """
        if self.baseband:
            return np.fft.rfftfreq(self.data_length*self.PADDING_FACTOR,
                                   self.sampling_time)
        else:
            return self.center + fft.fftshift( fft.fftfreq(
                                  self.data_length*self.PADDING_FACTOR,
                                  self.sampling_time)) #[self.useful_index()]

    def data_to_dBm(self, data): # will become obsolete
        # replace values whose log doesnt exist
        data[data <= 0] = 1e-100
        # conversion to dBm scale
        return 10.0 * np.log10(data) + 30.0

    def data_to_unit(self, data, unit, rbw):
        """
        Converts the array 'data', assumed to be in 'Vpk^2', into the
        specified unit. Unit can be anything in ['Vpk^2', 'dB(Vpk^2)',
        'Vrms^2', 'dB(Vrms^2)', 'Vrms', 'Vrms^2/Hz'].
        Since some units require a rbw for the conversion, it is an explicit
        argument of the function.
        """
        data = abs(data)
        if unit == 'Vpk^2':
            return data
        if unit == 'dB(Vpk^2)':
            # need to add epsilon to avoid divergence of logarithm
            return 10 * np.log10(data + sys.float_info.epsilon)
        if unit == 'Vpk':
            return np.sqrt(data)

        if unit == 'Vrms^2':
            return data / 2
        if unit == 'dB(Vrms^2)':
            # need to add epsilon to avoid divergence of logarithm
            return 10 * np.log10(data / 2 + sys.float_info.epsilon)
        if unit == 'Vrms':
            return np.sqrt(data) / np.sqrt(2)

        if unit == 'Vrms^2/Hz':
            return data / 2 / rbw
        if unit == 'dB(Vrms^2/Hz)':
            # need to add epsilon to avoid divergence of logarithm
            return 10 * np.log10(data / 2 / rbw + sys.float_info.epsilon)
        if unit == 'Vrms/sqrt(Hz)':
            return np.sqrt(data) / np.sqrt(2) / rbw

    def data_to_display_unit(self, data, rbw):
        """
        Converts the array 'data', assumed to be in 'Vpk^2', into display
        units.
        Since some units require a rbw for the conversion, it is an explicit
        argument of the function.
        """
        return self.data_to_unit(data, self.display_unit, rbw)

    def transfer_function_iq(self, frequencies):
        # transfer function calculations
        tf_iq = np.ones(len(frequencies), dtype=complex)
        # iq transfer_function
        if not self.baseband:
            displaced_freqs = frequencies - self.center
            for f in self._iq_bandwidth():
                if f == 0:
                    continue
                elif f > 0:  # lowpass
                    tf_iq *= 1.0 / (
                        1.0 + 1j * displaced_freqs / f)
                    # quadrature_delay += 2
                elif f < 0:  # highpass
                    tf_iq *= 1.0 / (
                        1.0 + 1j * f / displaced_freqs)
                    # quadrature_delay += 1  # one cycle extra delay per
                    # highpass
        return tf_iq

    def transfer_function_scope(self, frequencies):
        # scope transfer function
        if not self.baseband:
            displaced_freqs = frequencies - self.center
        else:
            displaced_freqs = frequencies
        if self._scope_decimation()>1:
            norm_freq = self._scope_decimation()*displaced_freqs/125e6
            return np.sinc(norm_freq)
        else:
            return np.ones(len(displaced_freqs))

    def transfer_function(self, frequencies):
        """
        Transfer function from the generation of quadratures to their
        sampling, including scope decimation. At the moment, delays are not
        taken into account (and the phase response is not guaranteed to be
        exact.
        """
        return self.transfer_function_iq(frequencies) * \
               self.transfer_function_scope(frequencies)


    # Concrete implementation of AcquisitionModule methods
    # ----------------------------------------------------

    def _get_run_attributes(self):
        params = super(SpectrumAnalyzer, self)._get_run_attributes()
        params['rbw'] = self.rbw
        return params

    def _free_up_resources(self):
        self.scope.free()

    def _prepare_averaging(self):
        super(SpectrumAnalyzer, self)._prepare_averaging()
        self.current_avg = 0
        if self.baseband:
            self.data_avg = np.zeros((4, self._real_points))
        else:
            self.data_avg = np.zeros(self._real_points)
        self.data_x = np.copy(self.frequencies)

    def _get_trace(self):
        """
        No transfer_function correction
        :return:
        """
        iq_data = self._get_filtered_iq_data() # get iq data (from scope)
        if not self.running_state in ["running_single", "running_continuous"]:
            self.pyrpl.scopes.free(self.scope) # free scope if not continuous
        if self.baseband:
            # In baseband, where the 2 real inputs are stored in the real and
            # imaginary part of iq_data, we need to make 2 different FFTs. Of
            # course, we could do it naively by calling twice fft, however,
            # this is not optimal:
            # x = rand(10000)
            # y = rand(10000)
            # %timeit fft.fft(x)    # --> 74.3 us (143 us with numpy)
            # %timeit fft.fft(x + 1j*y) # --> 163 us (182 us with numpy)
            # A convenient option described in Oppenheim/Schafer  p.
            # 333-334 consists in taking the right combinations of
            # negative/positive/real/imaginary part of the complex fft,
            # however, an optimized function for real FFT is already provided:
            # %timeit fft.rfft(x)       # --> 63 us (72.7 us with numpy)
            # --> In fact, we will use numpy.rfft insead of
            # scipy.fft.rfft because the output
            # format is directly a complex array, and thus, easier to handle.
            fft1 = np.fft.rfft(np.real(iq_data),
                                       self.data_length*self.PADDING_FACTOR)
            fft2 = np.fft.rfft(np.imag(iq_data),
                                       self.data_length*self.PADDING_FACTOR)
            cross_spectrum = np.conjugate(fft1)*fft2

            res = np.array([abs(fft1)**2,
                            abs(fft2)**2,
                            np.real(cross_spectrum),
                            np.imag(cross_spectrum)])
            # at some point, we need to cache the tf for performance
            self._last_curve_raw = res # for debugging purpose
            return res/abs(self.transfer_function(self.frequencies))**2
        else:
            # Realize the complex fft of iq data
            res = fft.fftshift(fft.fft(iq_data,
                                        self.data_length*self.PADDING_FACTOR))
            # at some point we need to cache the tf for performance
            self._last_curve_raw = np.abs(res)**2 # for debugging purpose
            return self._last_curve_raw/abs(self.transfer_function(
                self.frequencies))**2
            #/ abs(self.transfer_function(
                #self.frequencies))**2
            # [self.useful_index()]

    def _remaining_time(self):
        """
        :returns curve duration - ellapsed duration since last setup() call.
        """
        return self.scope._remaining_time()

    def _data_ready(self):
        """
        :return: True if curve is ready in the hardware, False otherwise.
        """
        return self.scope._data_ready()

    def _iq_bandwidth(self):
        return self.iq.__class__.bandwidth.validate_and_normalize(
            self.iq,
            [self.span*self.if_filter_bandwidth_per_span]*4)

    def _scope_decimation(self):
        return self.scope.__class__.decimation.validate_and_normalize(
                    self.scope,
                    int(round(self.sampling_time/8e-9)))

    def _scope_duration(self):
        return self._scope_decimation()*8e-9*self.data_length

    def _start_trace_acquisition(self):
        autosave_backup = self._autosave_active
        # setup iq module
        if not self.baseband:
            #raise NotImplementedError("iq mode is not supported in the "
            #                          "current release of Pyrpl.")
            self.iq.setup(
                input = self.input,
                bandwidth=self._iq_bandwidth(),
                gain=0,
                phase=0,
                acbandwidth=self.acbandwidth,
                amplitude=0,
                output_direct='off',
                output_signal='quadrature',
                quadrature_factor=self.quadrature_factor)
        # change scope ownership in order not to mess up the scope
        # configuration
        if self.scope.owner != self.name:
            self.pyrpl.scopes.pop(self.name)
        # setup scope
        if self.baseband:
            input1 = self.input1_baseband
            input2 = self.input2_baseband
        else:
            input1 = self.iq
            input2 = self.iq_quadraturesignal
        self.scope.setup(input1=input1,
                         input2=input2,
                         average=True,
                         duration=self.scope.data_length*self._scope_decimation()*8e-9,
                         trigger_source="immediately",
                         ch1_active=True,
                         ch2_active=True,
                         rolling_mode=False)
        self.scope.stop()
        return self.scope._start_trace_acquisition()

    def save_curve(self):
        """
        Saves the curve(s) that is (are) currently displayed in the gui in
        the db_system. Also, returns the list [curve_ch1, curve_ch2]...
        """
        """
        Saves the curve(s) that is (are) currently displayed in the gui in
        the db_system. Also, returns the list [curve_ch1, curve_ch2]...
        """
        if not self.baseband:
            return super(SpectrumAnalyzer, self)._save_curve(self.data_x,
                                                  self.data_avg,
                                                  **self.setup_attributes)
        else:
            d = self.setup_attributes
            curves = [None, None]
            sp1, sp2, cross_real, cross_imag = self.data_avg
            for ch, active in [(0, self.display_input1_baseband),
                               (1, self.display_input2_baseband)]:
                if active:
                    d.update({'ch': ch,
                              'name': self.curve_name + ' ch' + str(ch + 1)})
                    curves[ch] = self._save_curve(self.data_x,
                                                  self.data_avg[ch],
                                                  **d)
            if self.display_cross_amplitude:
                d.update({'ch': 'cross',
                          'name': self.curve_name + ' cross'})
                curves.append(self._save_curve(self.data_x,
                                              self.data_avg[2] +
                                               1j*self.data_avg[3],
                                              **d))
            return curves

    def equivalent_noise_bandwidth(self):
        """Returns the equivalent noise bandwidth of the current window. To
        get the residual bandwidth, this number has to be multiplied by the
        sample rate."""

        if not self.window in self._enb_cached:
            filter_window = self.filter_window()
            self._enb_cached[self.window] = (sum(filter_window ** 2)) / \
                                            (sum(filter_window) ** 2)

        return self._enb_cached[self.window]
