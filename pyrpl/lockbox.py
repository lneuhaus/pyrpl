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

CONSTANTS_DEFAULT = dict(
    lockbox_name="default_cavity",
    verbosity=True,
    lock_upper_threshold=0.9,
    lock_lower_threshold=0.0,
    lock_step=50,
    lock_range=7000,
    lock_predelay=0.05,
    lock_postdelay=0.2,
    find_signal="reflection",
    #find_signal = "pdh",
    offset1=0,
    offset2=0,
    mean_reflection=100,
    mean_pdh=0,
    redefine_means_on_sweep=True,
    amplitude_reflection=0.0,
    amplitude_pdh=0.0,
    find_fine_offset=0,
)

CONSTANTS = CONSTANTS_DEFAULT


class Lockbox(object):

    def __init__(self, constants=None):
        """generic lockbox object, no implementation-dependent details here
        """
        self.logger = logging.getLogger(name=__name__)
        if constants is None:
            self.constants = CONSTANTS
        else:
            self.constants = constants
        c = self._get_constants()
        if not c == dict():
            self.logger.info("Obtained the following constants from memory: %s", c)
            self.constants.update(c)
        self.trace_reflection = np.zeros(0)
        self.trace_pdh = np.zeros(0)
        self.trace_time = np.zeros(0)
        self.trace_outi = np.zeros(0)
        self.trace_outq = np.zeros(0)
        self.plotindex = 0

    def _get_constants(self):
        settings = QtCore.QSettings("rplockbox", "constants")
        kwds_str = str(
            settings.value(
                self.constants["lockbox_name"]).toString())
        kwds = dict()
        if kwds_str != "" and not kwds_str is None:
            kwds = json.loads(kwds_str)
            if kwds is None:
                kwds = dict()
            for k in kwds.keys():
                if k in self.constants:
                    self.constants[k] = kwds[k]
        return kwds

    def _save_constants(self, constants):
        settings = QtCore.QSettings("rplockbox", "constants")
        write_constants = self._get_constants()
        write_constants.update(constants)
        settings.setValue(
            self.constants["lockbox_name"],
            json.dumps(write_constants))
        self._get_constants()

    def find_offsets(self, avg=100):
        self.logger.warning("Make sure all light is off for this measurement")
        reflection = np.zeros(avg)
        pdh = np.zeros(avg)
        for i in range(len(reflection)):
            reflection[i] = self.reflection
            pdh[i] = self.pdh
        constants = dict(offset_reflection=reflection.mean(),
                         offset_pdh=pdh.mean())
        self.constants.update(constants)
        self._save_constants(constants)

    """@property
    def reflection(self):
        return 0
    """

    def relative_reflection(self, refl=None):
        if refl is None:
            refl = self.reflection
        return float(refl - self.constants["offset_reflection"]) / float(
            self.constants["mean_reflection"] - self.constants["offset_reflection"])

    """@property
    def pdh(self):
        return 0
    """

    def align_acoustic(
            self,
            normalfrequency=10000.0,
            sosfrequency=2000,
            verbose=True):
        from sound import sinus
        from time import sleep
        while True:
            r = self.relative_reflection()
            if verbose:
                self.logger.debug(r)
            if r > 0.8:
                df = sosfrequency
                sinus(df, 0.05)
                sinus(df, 0.05)
                sinus(df, 0.05)
                sleep(0.2)
                sinus(df, 0.2)
                sinus(df, 0.2)
                sinus(df, 0.2)
                sleep(0.2)
                sinus(df, 0.05)
                sinus(df, 0.05)
                sinus(df, 0.05)
                self.relock()
            else:
                sinus(normalfrequency * r, 0.05)

    @property
    def coarse(self):
        if hasattr(self, '_coarse') and not self._coarse is None:
            return self._coarse
        else:
            if "lastcoarse" in self.constants:
                self._coarse = self.constants["lastcoarse"]
            else:
                self._coarse = None
            return self._coarse

    @coarse.setter
    def coarse(self, v):
        """implement coarse setting here"""
        self._coarse = v
        self._save_constants(dict(lastcoarse=v))

    @property
    def fine(self):
        if hasattr(self, '_fine'):
            return self._fine
        else:
            self._fine = None
            return self._fine

    @fine.setter
    def fine(self, v):
        """implement fine setting here"""
        self._fine = v

    def get_buffers(self):
        """fill the buffers of all trace_xxx variables with their current values"""
        pass

    def sweep_setup(self):
        """setup for a sweep measurement, outputs one sin wave on fine output and prepares scope for acquisition """
        pass

    def sweep_trig(self, frequency=None, trigger_source=8):
        """trigs one sweep measurement, optionally with changed frequency and trigger_source"""
        pass

    def sweep_acquire(self, plot=True, data_shorten=False, amplitude=None):
        """acquires the data of both inputs during one sweep"""
        if not amplitude is None:
            amplitude *= 8191.0
        self.sweep_setup(amplitude=amplitude)
        sleep(self.sweep_trig())
        self.get_buffers(data_shorten=data_shorten)
        if self.constants["redefine_means_on_sweep"]:
            constants = dict(mean_reflection=self.trace_reflection.mean(),
                             mean_pdh=self.trace_pdh.mean(),
                             max_pdh=self.trace_pdh.max(),
                             min_pdh=self.trace_pdh.min(),
                             )
            self.constants.update(constants)
            self._save_constants(constants)

        if plot:
            self.plot(self.trace_time[:len(self.trace_outi)], self.trace_outi)
            self.plot(self.trace_time, self.trace_pdh)
            self.plot(self.trace_time, self.trace_reflection)

    def pid_reset(self):
        """resets all integrator registers of pid but keeps pid on"""
        pass

    def pid_off(self):
        """turns pid off and resets integrator memory"""
        pass

    def pid_ilimit(self):
        """turns pid on with limited integrator gain"""
        pass

    def pid_on(self):
        """turns pid on and boosts integrator gain"""
        pass

    @property
    def pid_setpoint(self):
        """ setpoint for locking """
        return self._setpoint

    @pid_setpoint.setter
    def pid_setpoint(self, v):
        self._setpoint = v

    def find_setpoint(self):
        sp = self.get_pdh
        """ returns the optimal setpoint to be used for locking """
        return sp

    def find_fine(self):
        """ finds the fine offset of a resonance in range"""
        self.pid_off()
        self.sweep_acquire(plot=True, data_shorten=True)
        reflection = pandas.Series(
            self.trace_reflection,
            index=self.trace_outi)
        xup = reflection.iloc[:len(reflection) // 2].argmin()
        xdown = reflection.iloc[len(reflection) // 2:].argmin()
        x0 = (xup + xdown) / 2
        r0 = self.relative_reflection(reflection.min())
        hysteresis = (xup - xdown) / 2
        self.logger.info("x0: %s hysteresis: %s R0: %s", x0, hysteresis, r0)
        if self.islocked(r0):
            return x0 + self.constants["find_fine_offset"]
        else:
            return None

    def find_coarse(self):
        """ finds the coarse offset of a resonance in range """
        pass

    def recenter(self):
        pass

    def islocked(self, refl=None):
        if refl is None:
            refl = self.relative_reflection()
        if refl < self.constants["lock_upper_threshold"] and refl > self.constants[
                "lock_lower_threshold"]:
            return True
        else:
            return False

    def lock(self, detuning=0):
        # reset PID
        self.pid_off()

        # find out where the resonance is expected
        x0 = self.find_fine()
        if x0 is None:
            coarse = self.find_coarse()
            if coarse is None:
                self.logger.error("No coarse offset for resonance found")
                return False
            else:
                self.coarse = coarse
                x0 = self.find_fine()
                if x0 is None:
                    self.logger.error("No fine offset for resonance found")
                    return False
        self.pid_setpoint = self.find_setpoint() + detuning
        islocked = False
        for i in range(
                0,
                self.constants["lock_range"],
                self.constants["lock_step"]):
            for j in [i, -i]:
                self.pid_off()
                self.fine = x0 + j
                sleep(self.constants["lock_predelay"])
                if self.constants["verbosity"]:
                    self.logger.info("Trying to lock at offset %s...", self.fine)
                self.pid_ilimit()
                sleep(self.constants["lock_postdelay"])
                islocked = self.islocked()
                if islocked:
                    break
            if islocked:
                break

        if not self.islocked():
            self.logger.error("Unable to acquire lock")
            return False

        self.logger.info("Lock acquired. Boosting integrator gain...")
        self.pid_on()

        if not self.islocked():
            self.logger.error( "Unable to boost integrator gain. Lock attempt failed.")
            return False

        self.logger.error( "Integrator gain boosted. Recentering fine offset..."

        if self.constants["lock_auto_recenter"]:
            if self.recenter():
                self.logger.info("Recentered successfully")
            else:
                self.logger.error("Recentering failed")
                return False
        self.logger.info("Locked. Relative reflection on resonance: %.2f" % self.relative_reflection())
        return True

    def plot(self, x, y, label=None):
        self.plotindex += 1
        mycolors = [
            'blue',
            'green',
            'red',
            'black',
            'purple',
            'orange',
            'black',
            'yellow',
            'darkgreen',
            'darkblue',
            'brown',
            'pink',
            'blue',
            'red']
        BORDERS = 0.08
        FONTSIZE = 16
        LARGEFONTSIZE = 20
        OUTFILEDIR = "plots/"
        MARKERSIZE = 1.0
        # MARKER='+'
        MARKER = '.'
        FILLSTYLE = 'bottom'
        LINESTYLE = '+'
        LINEWIDTH = 1
        AXESLINEWIDTH = 4
        DPI = 600
        dat = plt.plot(x, y, 'bo')
        plot_color = mycolors[self.plotindex % len(mycolors)]
        plot_marker = MARKER
        plot_markersize = MARKERSIZE
        plot_linestyle = LINESTYLE
        plot_linewidth = LINEWIDTH
        plot_fillstyle = FILLSTYLE
        plot_continuous = False
        if plot_continuous:
            markerstyle = ''
            linestyle = plot_linestyle
        else:
            markerstyle = plot_marker
            linestyle = ''
        plt.setp(
            dat,
            color=plot_color,
            ls=linestyle,
            lw=plot_linewidth,
            marker=markerstyle,
            markersize=plot_markersize,
            fillstyle=FILLSTYLE,
            antialiased=True,
            label=label)
        plt.show()
