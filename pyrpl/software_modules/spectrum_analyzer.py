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
from ..attributes import BoolProperty, FloatProperty, FloatAttribute,  \
    SelectAttribute, BoolAttribute, FrequencyAttribute, LongProperty, \
    SelectProperty, FilterProperty, StringProperty, FilterAttribute, \
    SelectProperty
from ..modules import SoftwareModule
from ..module_attributes import *
from pyrpl.acquisition_manager import AcquisitionManager, AcquisitionModule

import scipy.signal as sig
import scipy.fftpack
import numpy as np
import os
from pylab import *
import pandas
from PyQt4 import QtCore, QtGui

from ..widgets.module_widgets import SpecAnWidget

from ..errors import NotReadyError
from ..hardware_modules import Scope, DspModule
from ..modules import SignalLauncher


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


class SignalLauncherSpectrumAnalyzer(SignalLauncher):
    """ class that takes care of emitting signals to update all possible
    specan displays """
    #_max_refresh_rate = 25

    #update_display = QtCore.pyqtSignal()
    #autoscale_display = QtCore.pyqtSignal()


    def connect_widget(self, widget):
        """
        In addition to connecting the module to the widget, also connect the
        acquisition manager. (At some point, we should make a separation
        between module widget and acquisition manager widget).
        """
        super(SignalLauncherSpectrumAnalyzer, self).connect_widget(widget)
        self.module.run._signal_launcher.connect_widget(widget)


class SAAcquisitionManager(AcquisitionManager):
    def _init_module(self):
        super(SAAcquisitionManager, self)._init_module()
        self._timer.timeout.connect(self._check_for_curves)

    def _check_for_curves(self):
        """
        Acquires one curve and adds it to the average.
        returns True if new data are available for plotting.
        """
        # several seconds... In the mean time, no other event can be
        # treated. That's why the gui freezes...
        if self._module.curve_ready():
            if len(self.data_avg[1]) != self._module._real_points:
                # for instance, if running_state pause was reloaded...
                print("restarting ",  self._module._real_points)
                self._restart_averaging()
            self.data_current[0] = self._module.frequencies
            self.data_current[1] = self._module.curve()
            self._do_average()
            self._emit_signal_by_name('display_curve', list(self.data_avg))
            if self.running_state in  ['running_continuous',
                                       'running_single']:
                self._module.setup()
            if self.running_state == 'running_continuous':
                self._timer.start()
            if self.running_state == 'running_single':
                if self.current_avg<self.avg:
                    self._timer.start()
        else:
            if self.running_state in ['running_continuous',
                                      'running_single']:
                self._timer.start()

    def _do_average(self):
        self.data_avg[0] = self.data_current[0]
        self.data_avg[1] = (self.current_avg * self.data_avg[1] \
                         +  self.data_current[1]) / (self.current_avg + 1)
        self.current_avg += 1
        if self.current_avg > self.avg:
            self.current_avg = self.avg

    def _restart_averaging(self):
        points = self._module._real_points
        self.data_current = np.zeros((2, points))
        self.data_avg = np.zeros((2, points))
        self.current_avg = 0


class SpectrumAnalyzer(AcquisitionModule, SoftwareModule):
    """
    A spectrum analyzer is composed of an IQ demodulator, followed by a scope.
    The spectrum analyzer connections are made upon calling the function setup.
    """
    _widget_class = SpecAnWidget

    run = ModuleProperty(SAAcquisitionManager)

    _gui_attributes = ["input",
                         "baseband",
                         "center",
                         "span",
                         "points",
                         "window",
                         "acbandwidth"]
    _setup_attributes = _gui_attributes + ["run"]
    _callback_attributes = _gui_attributes

    # numerical values
    nyquist_margin = 1.0
    if_filter_bandwidth_per_span = 1.0
    quadrature_factor = 0.001

    # select_attributes list of options
    def spans(nyquist_margin):
        # see http://stackoverflow.com/questions/13905741/accessing-class-variables-from-a-list-comprehension-in-the-class-definition
        return [int(np.ceil(1. / nyquist_margin / s_time))
             for s_time in Scope.sampling_times]
    spans = spans(nyquist_margin)

    windows = ['blackman', 'flattop', 'boxcar', 'hamming']  # more can be
    # added here (see http://docs.scipy.org/doc/scipy/reference/generated
    # /scipy.signal.get_window.html#scipy.signal.get_window)
    inputs = DspModule.inputs

    # attributes
    baseband = BoolProperty()
    span = SpanFilterProperty(doc="""
        Span can only be given by 1./sampling_time where sampling
        time is a valid scope sampling time.
        """)
    center = CenterAttribute()
    points = LongProperty()
    window = SelectProperty(options=windows)
    input = SelectProperty(options=inputs)
    acbandwidth = SpecAnAcBandwidth()

    _signal_launcher = SignalLauncherSpectrumAnalyzer

    # functions
    def _init_module(self):
        super(SpectrumAnalyzer, self)._init_module()
        self.rp = self.pyrpl.rp
        self.acbandwidth = 0
        self.baseband = False
        self.center = 0
        self.window = "flattop"
        self.points = Scope.data_length
        self._is_setup = False
        self.run._restart_averaging()

    @property
    def iq(self):
        if not hasattr(self, '_iq'):
            self._iq = self.pyrpl.rp.iq2  # can't use the normal pop
            # mechanism because we specifically want the customized iq2
            self._iq.owner = self.name
        return self._iq

    iq_quadraturesignal = 'iq2_2'

    def _callback(self):
        """
        When a setup_attribute is touched, stop acquisition
        :return:
        """
        self.run.stop()

    @property
    def data_length(self):
        return int(self.points)  # *self.nyquist_margin)

    @property
    def sampling_time(self):
        return 1. / self.nyquist_margin / self.span

    def _setup(self):
        """
        Set things up for a spectrum acquisition. Between setup(**kwds) and
        curve(), the spectrum analyzer takes ownership over the scope.
        """
        self._is_setup = True
        # setup iq module
        if not self.baseband:
            self.iq.setup(
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
        self.scope.sampling_time = self.sampling_time # only duration can be
        #  used within setup
        if self.baseband:
            self.scope.input1 = self.input
        else:
            self.scope.input1 = self.iq
            self.scope.input1 = self.iq_quadraturesignal
        self.scope.setup(average=True,
                         trigger_source="immediately",
                         run=dict(rolling_mode=False))

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

    def iq_data(self, timeout):
        """
        :return: complex iq time trace
        """
        #timeout = self.scope.duration * 2 # leave some margin
        res = np.asarray(self.scope.curve(1, timeout=None),
                         dtype=np.complex)
        if not self.baseband:
            res += 1j*self.scope.curve(2, timeout=None)
        return res[:self.data_length]

    def filtered_iq_data(self, timeout):
        """
        :return: the product between the complex iq data and the filter_window
        """
        return self.iq_data(timeout) * np.asarray(self.filter_window(),
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

    def curve(self, timeout=None):
        """
        Get a spectrum from the device. It is mandatory to call setup() before
        curve()
            If timeout>0:  runs until data is ready or timeout expires
            If timeout is None: timeout is auto-set to twice scope.duration
            If timeout is <0, throws ValueError
        No averaging is done at this stage (averaging only occurs within the
        asynchronous mode of operation run_...)
        """
        if timeout is not None and timeout<0:
            raise(ValueError('Timeout needs to be None or >0'))
        if not self._is_setup:
            raise NotReadyError("Setup was never called")
        SLEEP_TIME = 0.001
        total_sleep = 0
        res = scipy.fftpack.fftshift(np.abs(scipy.fftpack.fft(
            self.filtered_iq_data(timeout))) ** 2)[self.useful_index()]
        if not self.run.continuous:
            self.pyrpl.scopes.free(self.scope)
        return res

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
