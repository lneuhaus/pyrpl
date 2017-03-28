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

import logging
logger = logging.getLogger(name=__name__)

from ..module_attributes import *
from ..acquisition_module import AcquisitionModule
from ..widgets.module_widgets import SpecAnWidget
from ..hardware_modules import Scope, DspModule

import scipy.signal as sig
import scipy.fftpack
from pylab import *

# Some initial remarks about spectrum estimation:
# Main source: Oppenheim + Schaefer, Digital Signal Processing, 1975

#class RbwAttribute(FloatAttribute):
#    def get_value(self, instance, owner):
#        if instance is None:
#            return self
#        if instance.rbw_auto:
#            instance._rbw = instance.span / instance.points
#        return instance._rbw
#
#    def set_value(self, instance, val):
#        if not instance.rbw_auto:
#            instance._rbw = val
#        return val


#class RbwAutoAttribute(BoolAttribute):
#    def get_value(self, instance, owner):
#        if instance is None:
#            return self
#        return instance._rbw_auto

#    def set_value(self, instance, value):
#        instance._rbw_auto = value
#        if value:
#            instance.span = instance.span
#        return value


class CenterAttribute(FrequencyAttribute):
    def get_value(self, instance, owner):
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


class SpanFilterProperty(FilterProperty):
    def valid_frequencies(self, instance):
        return instance.spans

    def get_value(self, instance, owner):
        val = super(SpanFilterProperty, self).get_value(instance, owner)
        if np.iterable(val):
            return val[0] # maybe this should be the default behavior for
            # FilterAttributes... or make another Attribute type
        else:
            return val


class SpectrumAnalyzer(AcquisitionModule):
    """
    A spectrum analyzer is composed of an IQ demodulator, followed by a scope.
    The spectrum analyzer connections are made upon calling the function setup.
    """
    _widget_class = SpecAnWidget
    _gui_attributes = ["input",
                       "baseband",
                       "center",
                       "span",
                       "points",
                       "window",
                       "acbandwidth",
                       "unit"]
    _setup_attributes = _gui_attributes

    # numerical values
    nyquist_margin = 1.0
    if_filter_bandwidth_per_span = 1.0
    quadrature_factor = 0.1# 0.001 #  it looks like 0.001 is now rounded to
    # 0...

    # unit Vpk is such that the level of a peak in the spectrum indicates the
    # correct voltage amplitude of a coherent signal (linear scale)
    # more units can be added as needed, but need to guarantee that conversion
    # is done as well (see implementation in lockbox for example)
    unit = SelectProperty(default="Vpk",
                          options=["Vpk"])

    # select_attributes list of options
    def spans(nyquist_margin):
        # see http://stackoverflow.com/questions/13905741/
        return [int(np.ceil(1. / nyquist_margin / s_time))
             for s_time in Scope.sampling_times]
    spans = spans(nyquist_margin)

    windows = ['blackman', 'flattop', 'boxcar', 'hamming']  # more can be
    # added here (see http://docs.scipy.org/doc/scipy/reference/generated
    # /scipy.signal.get_window.html#scipy.signal.get_window)
    inputs = DspModule.inputs

    # attributes
    baseband = BoolProperty(call_setup=True)
    span = SpanFilterProperty(doc="""
        Span can only be given by 1./sampling_time where sampling
        time is a valid scope sampling time.
        """,
        call_setup=True)
    center = CenterAttribute(call_setup=True)
    points = LongProperty(default=16384, call_setup=True)
    window = SelectProperty(options=windows, call_setup=True)
    input = SelectProperty(options=inputs, call_setup=True)
    acbandwidth = SpecAnAcBandwidth(call_setup=True)

    # _signal_launcher = SignalLauncherSpectrumAnalyzer

    # functions
    def _init_module(self):
        self.acbandwidth = 0
        self.baseband = False
        self.center = 0
        self.window = "flattop"
        self.points = Scope.data_length
        self._is_setup = False
        super(SpectrumAnalyzer, self)._init_module()
        self.rp = self.pyrpl.rp


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
        return int(self.points)  # *self.nyquist_margin)

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
        window = sig.get_window(self.window, self.data_length, fftbins=False)
        # empirical value for scaling flattop to sqrt(W)/V
        filterfactor = np.sqrt(50)
        # norm by datalength, by sqrt(50 Ohm), and something related to
        # filter
        normfactor = 1.0 / self.data_length / np.sqrt(50.0) * filterfactor
        return window * normfactor

    def _get_iq_data(self):
        """
        :return: complex iq time trace
        """
        res = self.scope._get_curve()
        if self.baseband:
            return res[0][:self.data_length]
        else:
            return (res[0] + 1j*res[1])[:self.data_length]
#            res += 1j*self.scope.curve(2, timeout=None)
#        return res[:self.data_length]

    def _get_filtered_iq_data(self):
        """
        :return: the product between the complex iq data and the filter_window
        """
        return self._get_iq_data() * np.asarray(self.filter_window(),
                                            dtype=np.complex)

    def useful_index(self):
        """
        :return: a slice containing the portion of the spectrum between start
        and stop
        """
        middle = int(self.data_length / 2)
        length = self.points  # self.data_length/self.nyquist_margin
        if self.baseband:
            return slice(middle, int(middle + length / 2 + 1))
        else:
            return slice(int(middle - length/2), int(middle + length/2 + 1))

    @property
    def _real_points(self):
        """
        In baseband, only half of the points are returned
        :return: the real number of points that will eventually be returned
        """
        return self.points/2 if self.baseband else self.points

    @property
    def frequencies(self):
        """
        :return: frequency array
        """
        return self.center + scipy.fftpack.fftshift( scipy.fftpack.fftfreq(
                                  self.data_length,
                                  self.sampling_time))[self.useful_index()]

    def data_to_dBm(self, data):
        # replace values whose log doesnt exist
        data[data <= 0] = 1e-100
        # conversion to dBm scale
        return 10.0 * np.log10(data) + 30.0

    # Concrete implementation of AcquisitionModule methods
    # ----------------------------------------------------

    @property
    def data_x(self):
        return self.frequencies

    def _get_curve(self):
        """
        Simply pack together channel 1 and channel 2 curves in a numpy array
        """
        res = scipy.fftpack.fftshift(np.abs(scipy.fftpack.fft(
            self._get_filtered_iq_data())) ** 2)[self.useful_index()]
        if not self.running_state in ["running_single", "running_continuous"]:
            self.pyrpl.scopes.free(self.scope)
        return res

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

    def _start_acquisition(self):
        autosave_backup = self._autosave_active
        # setup iq module
        if not self.baseband:
            self.iq.setup( # for som reason, this takes 300 ms to do
                input = self.input,
                bandwidth=[self.span*self.if_filter_bandwidth_per_span]*4,
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
            input1 = self.input
            input2 = self.input
        else:
            input1 = self.iq
            input2 = self.iq_quadraturesignal
        self.scope.setup(input1=input1,
                         input2=input2,
                         average=True,
                         duration=self.scope.data_length*self.sampling_time,
                         trigger_source="immediately",
                         ch1_active=True,
                         ch2_active=True,
                         rolling_mode=False,
                         running_state='stopped')
        return self.scope._start_acquisition()