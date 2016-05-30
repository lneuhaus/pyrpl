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

from redpitaya_modules import NotReadyError

class Span(object):
    def __init__(self, default=100):
        self.default = default
        
    def __set__(self, obj, val):
        obj._span = val
        return val

    def __get__(self, obj, objtype=None):
        if not hasattr(obj, "_span"):
            obj._span = self.default
        return obj._span

class BW(object):
    points_per_bw = 10
    def __get__(self, obj, objtype=None):
        return obj.span*1./(self.points_per_bw*obj.n_points)

    def __set__(self, obj, val):
        obj.span = val*(self.points_per_bw*obj.n_points)
        return val


class SpectrumAnalyzer(object):
    """
    A spectrum analyzer is composed of an IQ demodulator, followed by a scope.
    The spectrum analyzer connections are made upon calling the function setup  
    """
    _setup = False
    def setup(self,
              center=1e6,
              span=100,
              window='gauss',
              scope_ch=1,
              iq_nr=1):
        self._setup = True
        self.window = window

    @property
    def n_points(self):
        return 16392#self.scope.data_length

    """
    span and bw are linked together
    """
    span = Span()
    bw = BW()

    def filter_window(self):
        if self.window=='gauss':
            x = linspace(-1,
                         1,
                         self.n_points,
                         True)
            return exp(-(x*BW.points_per_bw)**2)

    def curve(self):
        if not self._setup:
            raise NotReadyError("Setup was never called")
        return np.fft(self.scope.curve(self.scope_ch)*self.filter_window)
