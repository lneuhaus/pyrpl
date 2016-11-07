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

from . import SoftwareModule
from pyrpl.sshshell import SSHshell
from time import sleep
from matplotlib import pyplot
import math
import numpy

from numpy import pi, linspace
import scipy.signal as sig
import numpy as np
import os
from pylab import *
import pandas
from PyQt4 import QtCore, QtGui
import json
import matplotlib
import matplotlib.pyplot as plt
import logging

from pyrpl.hardware_modules import NotReadyError, Scope, DspModule

# Some initial remarks about spectrum estimation:
# Main source: Oppenheim + Schaefer, Digital Signal Processing, 1975



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

    nyquist_margin = 2 #*pi #it looks like bandwidth of filters are then # perfect

    # spans = [1./nyquist_margin/s_time for s_time in Scope.sampling_times]

    windows = ['blackman', 'flattop', 'boxcar', 'hamming']  # more can be
    # added here (see http://docs.scipy.org/doc/scipy/reference/generated
    # /scipy.signal.get_window.html#scipy.signal.get_window)
    inputs = DspModule.inputs

    #_setup = False
    def __init__(self, rp=None):
    
        #it looks like bandwidth of filters are then perfect
        self.nyquist_margin = 1.0 #2*pi - we will take care of the rbw
        # estimation in the rbw property, since this may depend on other
        # things as well (such as filter type)
        self.spans = [np.ceil(1. / self.nyquist_margin / s_time)
                      for s_time in Scope.sampling_times]
        
        self.rp = rp
        self.center = 0
        self.avg = 10
        self.input = 'adc1'
        self.acbandwidth = 0
        self.window = "flattop"

        self._rbw = 0
        self._rbw_auto = False

        self.points = Scope.data_length
        self.span = 1e5
        self.rbw_auto = True
        self._setup = False

    @property
    def data_length(self):
        return int(self.points) #*self.nyquist_margin)

    @property
    def span(self):
        """
        Span can only be given by 1./sampling_time where sampling
        time is a valid scope sampling time.
        """
        return np.ceil(1./self.nyquist_margin/self.scope.sampling_time)

    @span.setter
    def span(self, val):
        val = float(val)
        self.scope.sampling_time = 1./self.nyquist_margin/val
        return val

    @property
    def rbw_auto(self):
        return self._rbw_auto

    @rbw_auto.setter
    def rbw_auto(self, val):
        self._rbw_auto = val
        if val:
            self.span = self.span
        return val

    @property
    def center(self):
        return 0.0

    @center.setter
    def center(self, val):
        pass

    @property
    def rbw(self):
        if self.rbw_auto:
            self._rbw = self.span/self.points
        return self._rbw

    @rbw.setter
    def rbw(self, val):
        if not self.rbw_auto:
            self._rbw = val
        return val

    @property
    def input(self):
        return self.scope.input1

    @input.setter
    def input(self, val):
        self.scope.input1 = val
        return val

    def setup(self,
              span=None,
              center=None,
              data_length=None,
              avg=None,
              window=None,
              acbandwidth=None,
              input=None):
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
        self._setup = True
        if span is not None:
            self.span = span
        if center is not None:
            self.center = center
        if data_length is not None:
            self.data_length = data_length
        if avg is not None:
            self.avg = avg
        if window is not None:
            self.window = window
        if acbandwidth is not None:
            self.acbandwidth = acbandwidth
        if input is not None:
            self.input = input

        self.scope.trigger_source = "immediately"

        # this is crucial!!! no wonder we had problems with aliasing..
        self.scope.average = True

        self.scope.setup()

    @property
    def scope(self):
        return self.rp.scope

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
        res = self.scope.curve(1)
        return res[:self.data_length]

    def filtered_iq_data(self):
        """
        :return: the product between the complex iq data and the filter_window
        """
        return self.iq_data()*self.filter_window()

    def useful_index(self):
        """
        :return: a slice containing the portion of the spectrum between start and stop
        """
        middle = int(self.data_length/2)
        length = self.points#self.data_length/self.nyquist_margin
        #return slice(middle - length/2, middle + length/2 + 1)
        return slice(middle, middle + length / 2 + 1)

    def curve(self):
        """
        Get a spectrum from the device. It is mandatory to call setup() before curve()
        :return:
        """
        if not self._setup:
            raise NotReadyError("Setup was never called")
        return np.roll(np.abs(np.fft.fft(self.filtered_iq_data()))**2,
                                int(self.data_length//2))[self.useful_index()]

    def freqs(self):
        """
        :return: frequency array
        """
        return self.center + np.roll(np.fft.fftfreq(self.data_length,
                                                    self.sampling_time),
                                     self.data_length/2)[self.useful_index()]

    def data_to_dBm(self, data):
        return 10.0 * np.log10(data) + 30.0
