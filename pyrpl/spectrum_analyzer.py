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

from sshshell import SSHshell
from time import sleep
from matplotlib import pyplot
import math
import numpy
import numpy as np
import os
from pylab import *
import pandas
from PyQt4 import QtCore, QtGui
import json
import matplotlib
import matplotlib.pyplot as plt
import logging

from redpitaya_modules import NotReadyError, Scope, IQ



class SpectrumAnalyzer(object):
    """
    A spectrum analyzer is composed of an IQ demodulator, followed by a scope.
    The spectrum analyzer connections are made upon calling the function setup  
    """

    nyquist_margin = 2*pi #it looks like bandwidth of filters are then perfect

    spans = [1./nyquist_margin/s_time for s_time in Scope.sampling_times]

    def gauss(data_length, rbw, sampling_time):
        return np.exp(-(linspace(-sampling_time*rbw*data_length*pi,
                               sampling_time*rbw*data_length*pi,
                               data_length)) ** 2)

    _filter_windows = dict(gauss=gauss,
                           none=lambda points, rbw, sampling_time: np.ones(points))
    windows = _filter_windows.keys()
    inputs = IQ.inputs

    #_setup = False
    def __init__(self, rp=None):
        self.rp = rp
        self.center = 1e6
        self.avg = 1
        self.input = 'adc1'
        self.acbandwidth = 0
        self.window = "gauss"

        self._rbw = 0
        self._rbw_auto = False

        self.points = 1001
        self.span = 1e5
        self.rbw_auto = True
        self._setup = False

    @property
    def data_length(self):
        return int(self.points*self.nyquist_margin)

    @property
    def span(self):
        """
        Span can only be given by 1./sampling_time where sampling
        time is a valid scope sampling time.
        """

        return 1./self.nyquist_margin/self.scope.sampling_time

    @span.setter
    def span(self, val):
        val = float(val)
        self.scope.sampling_time = 1./self.nyquist_margin/val
        self.iq.bandwidth = [val, val]
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
        return self.iq.frequency

    @center.setter
    def center(self, val):
        self.iq.frequency = val
        return val

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
        return self.iq.input

    @input.setter
    def input(self, val):
        self.iq.input = val
        return val

    def setup(self,
              span=None,
              center=None,
              data_length=None,
              avg=None,
              window=None,
              acbandwidth=None,
              input=None):
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

        self.scope.input1 = 'iq2'
        self.scope.input2 = 'iq2_2'

        self.iq.output_signal = "quadrature"
        self.iq.quadrature_factor = 0.001

        self.scope.trigger_source = "immediately"
        self.scope.setup()

    @property
    def scope(self):
        return self.rp.scope

    @property
    def iq(self):
        return self.rp.iq2

    @property
    def sampling_time(self):
        return self.scope.sampling_time

    def filter_window(self):
        return self._filter_windows[self.window](self.data_length, self.rbw, self.sampling_time)

    def iq_data(self):
        res = self.scope.curve(1) + 1j * self.scope.curve(2) + 0.00012206662865236316*(1+1j)
        return res[:self.data_length]

    def filtered_iq_data(self):
        return self.iq_data()*self.filter_window()

    def useful_index(self):
        middle = self.data_length/2
        length = self.data_length/self.nyquist_margin
        return slice(middle - length/2, middle + length/2)

    def curve(self):
        if not self._setup:
            raise NotReadyError("Setup was never called")
        return 20*np.log10(np.roll(np.abs(np.fft.fft(self.filtered_iq_data())), self.data_length/2))\
                    [self.useful_index()]

    def freqs(self):
        return self.center + np.roll(np.fft.fftfreq(self.data_length,
                                                    self.sampling_time),
                                     self.data_length/2) \
                                    [self.useful_index()]
