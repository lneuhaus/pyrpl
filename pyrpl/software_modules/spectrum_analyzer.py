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
from pyrpl.attributes import BoolProperty, FloatProperty, FloatAttribute, SelectAttribute, BoolAttribute, \
                             FrequencyAttribute, LongProperty, SelectProperty, FilterProperty, StringProperty, \
                             FilterAttribute, SelectProperty
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
from ..widgets.module_widgets import SpecAnWidget

from ..errors import NotReadyError
from ..hardware_modules import Scope, DspModule
from ..modules import SignalLauncher


# Some initial remarks about spectrum estimation:
# Main source: Oppenheim + Schaefer, Digital Signal Processing, 1975

"""
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
"""

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

"""
class SpecAnInputAttribute(SelectAttribute):
    def get_value(self, instance, owner):
        if instance is None:
            return self
        return instance._input

    def set_value(self, instance, value):
        # Careful: the scope needs to be slaved for the time of this operation.
        instance._input = value
        if instance.baseband:
            instance.scope.input1 = instance._input
        else:
            instance.scope.input1 = instance.iq.name
            instance.scope.input2 = instance.iq_quadraturesignal # not very consistent with previous line, but anyways,
                                                                 # the implementation is likely to be temporary...
            instance.iq.input = instance._input
        return instance._input
"""

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
        return [freq for freq in module.iq.__class__.inputfilter.valid_frequencies(module.iq) if freq >= 0]


class SpanFilterProperty(FilterProperty):
    def valid_frequencies(self, instance):
        return instance.spans

    def get_value(self, instance, owner):
        val = super(SpanFilterProperty, self).get_value(instance, owner)
        if np.iterable(val):
            return val[0] # maybe this should be the default behavior for FilterAttributes... or make another Attribute type
        else:
            return val


class SignalLauncherSpectrumAnalyzer(SignalLauncher):
    """ class that takes care of emitting signals to update all possible specan displays """
    _max_refresh_rate = 25

    update_display = QtCore.pyqtSignal()
    autoscale_display = QtCore.pyqtSignal()

    def __init__(self, module):
        super(SignalLauncherSpectrumAnalyzer, self).__init__(module)
        self.timer_continuous = QtCore.QTimer()
        self.timer_continuous.setInterval(1000./self._max_refresh_rate)
        self.timer_continuous.timeout.connect(self.check_for_curves)
        self.timer_continuous.setSingleShot(True)
        self.first_display = True

    def kill_timers(self):
        """
        kill all timers
        """
        self.timer_continuous.stop()

    def run_continuous(self):
        """
        periodically checks for curve.
        """
        self.first_display = True
        self.module.setup()
        self.timer_continuous.start()

    def stop(self):
        self.timer_continuous.stop()

    def run_single(self):
        self.module.setup()
        self.first_display = True
        self.timer_continuous.start()

    def check_for_curves(self):
        """
        This function is called periodically by a timer when in run_continuous mode.
        1/ Check if curves are ready.
        2/ If so, plots them on the graph
        3/ Restarts the timer.
        """
        #if self.module.running_continuous:
        if self.module.acquire_one_curve():  # true if new data to plot
                                             # are available
            self.update_display.emit()
        else:  # curve not ready, wait for next timer iteration
            self.timer_continuous.start()
        if self.module.current_average>=self.module.avg:
            self.module.running_single = False
        if self.module.is_running() and \
                (not self.timer_continuous.isActive()):
            self.timer_continuous.start()
        if self.first_display:
            self.first_display = False
            self.autoscale_display.emit()


class RunningContinuousProperty(BoolProperty):
    """
    Nothing to do unless widget exists
    """
    def set_value(self, module, val):
        super(RunningContinuousProperty, self).set_value(module, val)
        if val:
            module._signal_launcher.run_continuous()
        else:
            module._signal_launcher.stop()
            module.scope.owner = None

class SpectrumAnalyzer(SoftwareModule):
    """
    A spectrum analyzer is composed of an IQ demodulator, followed by a scope.
    The spectrum analyzer connections are made upon calling the function setup.

    """
    _section_name = 'spectrum_analyzer'
    _widget_class = SpecAnWidget

    _setup_attributes = ["input",
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
    _gui_attributes = _setup_attributes

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
    rbw_auto = RbwAutoAttribute()
    running_continuous = RunningContinuousProperty()
    center = CenterAttribute()
    points = LongProperty()
    rbw = RbwAttribute()
    window = SelectProperty(options=windows)
    input = SelectProperty(options=inputs)
    avg = LongProperty()
    acbandwidth = SpecAnAcBandwidth()
    curve_name = StringProperty()

    _signal_launcher = SignalLauncherSpectrumAnalyzer

    # functions
    def _init_module(self):
        self._iq = None
        self.rp = self.pyrpl.rp

        self._rbw = 0
        self._rbw_auto = False
        self.acbandwidth = 0
        self.baseband = False
        self.center = 0
        self.avg = 10
        self.window = "flattop"
        self.points = Scope.data_length
        self.running_single = False
        self.restart_averaging()
        """ # intializing stuff while scope is not reserved modifies the
        parameters of the scope...

        self.input = 'in1'
        self.span = 1e5
        self.rbw_auto = True
        """
        self._is_setup = False
        self.data = None

    @property
    def iq(self):
        if self._iq is None:
            self._iq = self.pyrpl.rp.iq2  # can't use the normal pop
            # mechanism because we specifically want the customized iq2
            self._iq.owner = self.name
        return self._iq

    iq_quadraturesignal = 'iq2_2'

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
                         rolling_mode=False)

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
        res = scipy.fftpack.fftshift(np.abs(scipy.fftpack.fft(self.filtered_iq_data(timeout))) ** 2)[self.useful_index()]
        if not self.running_continuous:
            self.pyrpl.scopes.free(self.scope)
        return res

    @property
    def frequencies(self):
        """
        :return: frequency array
        """
        return self.center + scipy.fftpack.fftshift(scipy.fftpack.fftfreq(self.data_length,
                                  self.sampling_time))[self.useful_index()]

    def data_to_dBm(self, data):
        # replace values whose log doesnt exist
        data[data <= 0] = 1e-100
        # conversion to dBm scale
        return 10.0 * np.log10(data) + 30.0

    def save_curve(self):
        """
        Saves the curve(s) that is (are) currently displayed in the gui in the db_system. Also, returns the list
        [curve_ch1, curve_ch2]...
        """
        params = self.get_setup_attributes()
        for attr in ["current_average", "running_continuous",
                     "running_single"]:
            params[attr] = self.__getattribute__(attr)
        params.update(name=params['curve_name'])
        curve = self._save_curve(self.frequencies,
                                 self.data,
                                 **params)
        return curve

    def run_continuous(self):
        """
        Continuously feeds the gui with new curves from the scope. Once ready, datas are located in self.last_datas.
        """
        self.running_continuous = True

    def stop(self):
        """
        Stops the current acquisition.
        """
        self.running_single = False
        self.running_continuous = False


    def restart_averaging(self):
        """
        Restarts the curve averaging.
        """
        self.data = np.zeros(len(self.frequencies))
        self.current_average = 0

    def is_running(self):
        """
        :return:  True if running_continuous or running_single
        """
        return self.running_continuous or self.running_single

    def acquire_one_curve(self):
        """
        Acquires one curve and adds it to the average.
        returns True if new data are available for plotting.
        """
        # several seconds... In the mean time, no other event can be
        # treated. That's why the gui freezes...
        if self.curve_ready():
            newdata = self.curve()
            if self.data is None:
                self.data = newdata
            else:
                self.data = (self.current_average * self.data \
                     + newdata) / (self.current_average + 1)
            self.current_average += 1
            # let current_average be maximally equal to avg -> yields best real-time averaging mode
            if self.current_average > self.avg:
                self.current_average = self.avg
            if self.is_running():
                self.setup()
            return True
        else:
            return False

        #if self.running_continuous and not self.scope._trigger_delay_running:
        #    self.setup()
        #    print(self.curve_ready())
        #return do_plot

    def run_single(self):
        """
        Feeds gui with one new curve from the scope. Once ready, data are
        located in self.last_datas.
        """
        self.stop()
        self.restart_averaging()
        self.running_single = True
        self.setup()
        self._signal_launcher.run_single()

