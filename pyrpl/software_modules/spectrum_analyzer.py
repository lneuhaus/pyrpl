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

from pyrpl.attributes import BoolProperty, FloatProperty, FloatAttribute, SelectAttribute, BoolAttribute, \
                             FrequencyAttribute, LongProperty, SelectProperty, FilterProperty, StringProperty, \
                             FilterAttribute
from pyrpl.sshshell import SSHshell
from time import sleep
from matplotlib import pyplot
import math
import numpy
from . import SoftwareModule

from numpy import pi, linspace
import scipy.signal as sig
import scipy.fftpack
import numpy as np
import os
from pylab import *
import pandas
from PyQt4 import QtCore, QtGui
import json
import matplotlib
import matplotlib.pyplot as plt
import logging
from pyrpl.widgets.module_widgets import SpecAnWidget

from pyrpl.errors import NotReadyError
from pyrpl.hardware_modules import Scope, DspModule


# Some initial remarks about spectrum estimation:
# Main source: Oppenheim + Schaefer, Digital Signal Processing, 1975

class SpanAttribute(FilterAttribute):
    def valid_frequencies(self, instance):
        return instance.spans

    def get_value(self, instance, owner):
        if instance is None:
            return self
        return  np.ceil(1. / instance.nyquist_margin / instance.scope.sampling_time)

    def set_value(self, instance, value):
        if np.iterable(value):
            val = float(value[0])
        else:
            val = float(value)
        instance.scope.sampling_time = 1. / instance.nyquist_margin / val
        return val

class RbwAttribute(FloatAttribute):
    def get_value(self, instance, owner):
        if instance is None:
            return self
        if instance.rbw_auto:
            instance._rbw = instance.span / instance.points
        return instance._rbw

    def set_value(self, instance, val):
        if not instance.rbw_auto:
            instance._rbw = val
        return val

class SpecAnInputAttribute(SelectAttribute):
    def get_value(self, instance, owner):
        if instance is None:
            return self
        return instance._input

    def set_value(self, instance, value):
        instance._input = value
        if instance.baseband:
            instance.scope.input1 = instance._input
        else:
            instance.scope.input1 = instance.iq.name
            instance.scope.input2 = instance.iq_quadraturesignal # not very consistent with previous line, but anyways,
                                                                 # the implementation is likely to be temporary...
            instance.iq.input = instance._input
        return instance._input


class RbwAutoAttribute(BoolAttribute):
    def get_value(self, instance, owner):
        if instance is None:
            return self
        return instance._rbw_auto

    def set_value(self, instance, value):
        instance._rbw_auto = value
        if value:
            instance.span = instance.span
        return value

class CenterAttrbute(FrequencyAttribute):
    def get_value(self, instance, owner):
        if instance is None:
            return self
        if instance.baseband:
            return 0.0
        else:
            return instance.iq.frequency

    def set_value(self, instance, value):
        if instance.baseband and value != 0:
            raise ValueError("Nonzero center frequency not allowed in "
                             "baseband mode.")
        if not instance.baseband:
            instance.iq.frequency = value
        return value


class SpecAnAcBandwidth(FilterProperty):
    def valid_frequencies(self, module):
        return [freq for freq in module.iq.__class__.inputfilter.valid_frequencies(module.iq) if freq >= 0]

class SpectrumAnalyzer(SoftwareModule):
    """
    A spectrum analyzer is composed of an IQ demodulator, followed by a scope.
    The spectrum analyzer connections are made upon calling the function setup.

    Example 1:
      r = RedPitayaGui("1.1.1.1")
      sa = SpectrumAnalyzer(r)
      sa.setup(span=1000, center=100000)
      curve = sa.curve()
      freqs = sa.freqs()

    Example 2:
      r = RedPitayaGui("1.1.1.1")
      sa = SpectrumAnalyzer(r)
      sa.span = 1000
      sa.center = 100000
      sa.setup()
      curve = sa.curve()
      freqs = sa.freqs()
    """
    name = 'spectrum_analyzer'
    widget_class = SpecAnWidget

    gui_attributes = ["input",
                      "baseband",
                      "center",
                      "span",
                      "points",
                      "rbw_auto",
                      "rbw",
                      "window",
                      "avg",
                      "acbandwidth",
                      "curve_name"]
    setup_attributes = gui_attributes

    nyquist_margin = 1.0
    # see http://stackoverflow.com/questions/13905741/accessing-class-variables-from-a-list-comprehension-in-the-class-definition
    def spans(nyquist_margin):
        return [int(np.ceil(1. / nyquist_margin / s_time))
             for s_time in Scope.sampling_times]
    spans = spans(nyquist_margin)

    if_filter_bandwidth_per_span = 1.0


    # spans = [1./nyquist_margin/s_time for s_time in Scope.sampling_times]
    quadrature_factor = 0.001

    windows = ['blackman', 'flattop', 'boxcar', 'hamming']  # more can be
    # added here (see http://docs.scipy.org/doc/scipy/reference/generated
    # /scipy.signal.get_window.html#scipy.signal.get_window)
    inputs = DspModule.inputs

    # _setup = False
    def init_module(self):
        self._iq = None
        self.rp = self.pyrpl.rp
        self._parent = self.rp # very weird, now the correct way would be to use the ModuleManagers...

        self._rbw = 0
        self._rbw_auto = False
        self.acbandwidth = 0
        self.baseband = False
        self.center = 0
        self.avg = 10
        self.window = "flattop"
        self.points = Scope.data_length
        """ # intializing stuffs while scope is not reserved modifies the parameters of the scope...

        self.input = 'adc1'
        self.span = 1e5
        self.rbw_auto = True
        """
        self._is_setup = False


    @property
    def iq(self):
        if self._iq is None:
            self._iq = self.pyrpl.rp.iq2# can't use the normal pop mechanism because we specifically want the customized iq2
            self._iq.owner = self.name
        return self._iq

    iq_quadraturesignal = 'iq2_2'

    baseband = BoolProperty()

    @property
    def data_length(self):
        return int(self.points)  # *self.nyquist_margin)

    span = SpanAttribute(doc="""
        Span can only be given by 1./sampling_time where sampling
        time is a valid scope sampling time.
        """)

    rbw_auto = RbwAutoAttribute()
    center = CenterAttrbute()
    points = LongProperty()
    rbw = RbwAttribute()
    window = SelectProperty(options=windows)
    input = SpecAnInputAttribute(options=inputs)
    avg = LongProperty()
    acbandwidth = SpecAnAcBandwidth()
    curve_name = StringProperty()

    def setup(self,
              span=None,
              center=None,
              points=None,
              avg=None,
              window=None,
              acbandwidth=None,
              input=None,
              baseband=None,
              curve_name=None,
              rbw_auto=None):
        """
        :param span: span of the analysis
        :param center: center frequency
        :param data_length: number of points
        :param avg: not in use now
        :param window: "gauss" for now
        :param acbandwidth: bandwidth of the input highpass filter
        :param input: input channel
        :return:
        """
        self._is_setup = True

        if self.scope.owner != self.name:
            self.pyrpl.scopes.pop(self.name)

        if span is not None:
            self.span = span
        if center is not None:
            self.center = center
        if points is not None:
            self.data_length = points
        if avg is not None:
            self.avg = avg
        if window is not None:
            self.window = window
        if acbandwidth is not None:
            self.acbandwidth = acbandwidth
        if input is not None:
            self.input = input
        else:
            self.input = self.input
        if rbw_auto is not None:
            self.rbw_auto = rbw_auto
        if baseband is not None:
            self.baseband = baseband
        if curve_name is not None:
            self.curve_name = curve_name

        # setup iq module
        if not self.baseband:
            self.iq.setup(
                bandwidth=[self.span*self.if_filter_bandwidth_per_span]*4,
                gain=0,
                phase=0,
                acbandwidth=self.acbandwidth,
                amplitude=0,
                output_direct='off',
                output_signal='quadrature',
                quadrature_factor=self.quadrature_factor)

        self.scope.trigger_source = "immediately"
        self.scope.average = True
        self.scope.setup()

    def curve_ready(self):
        return self.scope.curve_ready()

    @property
    def scope(self):
        return self.rp.scope

    @property
    def duration(self):
        return self.scope.duration

    @property
    def sampling_time(self):
        """
        :return: scope sampling time
        """
        return self.scope.sampling_time

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

    def iq_data(self):
        """
        :return: complex iq time trace
        """
        timeout = self.scope.duration * 2 # leave some margin
        res = np.asarray(self.scope.curve(1, timeout=timeout),
                         dtype=np.complex)
        if not self.baseband:
            res += 1j*self.scope.curve(2, timeout=timeout)
        return res[:self.data_length]

    def filtered_iq_data(self):
        """
        :return: the product between the complex iq data and the filter_window
        """
        return self.iq_data() * np.asarray(self.filter_window(),
                                           dtype=np.complex)

    def useful_index(self):
        """
        :return: a slice containing the portion of the spectrum between start and stop
        """
        middle = int(self.data_length / 2)
        length = self.points  # self.data_length/self.nyquist_margin
        if self.baseband:
            return slice(middle, middle + length / 2 + 1)
        else:
            return slice(middle - length/2, middle + length/2 + 1)

    def curve(self):
        """
        Get a spectrum from the device. It is mandatory to call setup() before curve()
        :return:
        """
        if not self._is_setup:
            raise NotReadyError("Setup was never called")
        res = scipy.fftpack.fftshift(np.abs(scipy.fftpack  .fft(self.filtered_iq_data())) ** 2)[self.useful_index()]
        self.pyrpl.scopes.free(self.scope)
        return res

    def freqs(self):
        """
        :return: frequency array
        """
        return self.center + scipy.fftpack.fftshift(scipy.fftpack.fftfreq(self.data_length,
                                  self.sampling_time))[self.useful_index()]

    def data_to_dBm(self, data):
        # replace values whose log doesnt exist
        data[data <= 0] = 1e-100
        return 10.0 * np.log10(data) + 30.0
