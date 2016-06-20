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

# buglist: in lock_opt, it is inconvenient to always specify sof and pdh. unlocks when only pdh is changed
# unspecified parameters should rather be left unchanged instead of being
# set to 0 or 1


from sshshell import SSHshell
from time import sleep, time
from matplotlib import pyplot
import math
import numpy
import numpy as np
import os
import rpyc
from pylab import *
import pandas
from PyQt4 import QtCore, QtGui
import json
import matplotlib
import matplotlib.pyplot as plt
import sys
import iir

from .redpitaya import RedPitaya
from .curvedb import CurveDB

"""
channels:
Any input or output channel can be set to 0. This disables the channel and
    the affected features will obviously not work.
input channels: 1 (input 1), 2 (input 2), 3 (result of demodulation of either input)
output channels: 1 (output 1), 2 (output 2), 3 (DAC0 PWM, not implemented yet)
units:
all frequencies in Hz
all voltages in V
'relative_'-prefix means values are between 0 and 1
no unit means direct sampling value, usually between -8192 and 8191 (14bits), can be float if averaging is used
'name' in the following refers to the name you give to the lockbox you are configuring
for example: name = 'filter_cavity_2'
Tuning instructions:
You need one dictionary named CONSTANTS_name containing all parameters in this file.
The setup procedure will consist in filling it with the right parameters.
Some parameters will be stored automatically in the registry under
HKEY_CURRENT_USER\Software\rplockbox\constants\'lockbox_name'.
You start off by copying the example CONSTANTS_FPF2 and changing FPF2 to your cavity name.
1) add the new dictionary to the dictionary of lockboxes below: CONSTANTS = dict(FPF2=CONSTANTS_FPF2, name=CONSTANTS_name)
2) Go through your new dictionary paragraph by paragraph. Once you think you have the right parameters in the
    first paragraph, load this code in an ipython console with the command:
        from rplockbox_fpf2 import RPLockbox
        r = RPLockbox(cavity = 'name')
    If the first paragraph is set up correctly, your code should be loaded without error message.
3) The second paragraph deals with the inputs and outputs. You shoud at least connect the reflection photodiode to
    input 1 or 2 and the piezo amplifier input to output 1 or 2. In the dictionary, put the corresponding channel
    number behind reflection_input and coarse_output. Set the limit output voltages of the red pitaya to
    coarse_min_V and coarse_max_V. To continue, your cavity needs to be aligned and the RedPitaya
    connected to all signals. You should make a quick check that everything is properly connected:
    Execute r.get_mean("reflection_Volt"). The function should return the mean voltage at the reflection input.
    Execute r.coarse = 0. The coarse output should go to its minimum value.
    Execute r.coarse = 1. The coarse output should go to its maximum value.
    Now its time to calibrate the offsets of the RedPitaya. Turn off or block the laser and type
        r.darknoise()
    Then turn on the laser and type
        r.offresonant()
    It is good practice to execute r.darknoise() before each measurement run to account for possible drifts of the
    analog electronics of the RedPitaya. Since the RedPitaya does not know when you block the laser, you have to
    implement an automatization of this yourself.
    The option "find_coarse_redefine_means"=True executes r.offresonant() before each coarse resonance search
    to account for possible laser power drifts. It is assumed that the laser is on when you search for a resonance.
    You should now attempt a coarse search. Try
        r.find_coarse()
    If it returns immediately that the resonance was found at a round value near 0, you probably forgot to close
    the web application in your browser with the RedPitaya (find_coarse() uses the scope trigger, and if the
    web application uses it as well, this prevents our code from working properly).
    Once a find_coarse() procedure works, you should spend a few minutes to make it as fast as possible.
    To do so, simply change "coarse_searchtime" by factors of 2 while monitoring the find_coarse time.
    You should quickly find an optimum. You can also perform this search with r.optimize_find_coarse(),
    but you have to manually enter the found value into your constants dictionary.
    When this is done, we can try a first side-of-fringe lock. Set 'pdh_input' = 0 for now, reload the program
    and type
        r.lock()
    The code will first call find_coarse() and you should see the familiar output when a resonance is found. Then
    the code sets coarse to a slightly higher value than at the resonance, defines a pid setpoint which corresponds to
    the offresonant power constants["times find_coarse_threshold"], and turns on an integrator with a very low value.
    If you have a scope monitor of the lock output, you should see this value slowly drifting downwards until it
    encounters the side of a resonance and stays there. You now have to optimize the drift gain.
    Try r.lock(drifti = xx) with different values for xx. If the drift goes upwards, reverse the sign of drifti.
    If it drifts too slow, increase the value. If it passes over the resonance, decrease the value. The optimum
    value should be written to lock_driftgain in the constants dictionary so you can just call r.lock().
    Once the drift works fine, you can optimize the gain when the lock is in place. Call
        r.lock(setpoint = 0.5, locki = xx)
    and try different values. The code will drift into a resonance,
    then progressively change the setpoint to obtain the desired relative reflection. As it does so, it
    linearly ramps up lockgain to the desired value. If this ramping takes too long, shorten the value of
    lock_ramptime.
    If everything goes well, you now have a working side of fringe lock. If this is enough, skip the next section
    dealing with PDH detection.
    In case you really want to set up a PDH detection, continue here. Otherwise go to the last paragraph.
"""

"""
useful relations:
----------------------------------
i_real = i_set * isr_correction
slope_times_i_real = i_optimal_real * slope = i_optimal_set * isr_correction * slope
i_set = i_opt * sof
therefore:
sof = i_set/i_opt = _iset * slope * isr_correction / slope_times_i_real
---------------------------------
"""


PDHSTAGE = 4
SOFSTAGE = 3
DRIFTSTAGE = 2
COARSEFINDSTAGE = 1
UNLOCKEDSTAGE = 0

CONSTANTS_DEFAULT = dict(
    lockbox_name="default_cavity",
    verbosity=True,
    lock_upper_threshold=0.9,
    lock_lower_threshold=0.0,
    # detect that laser is off and return immediately for relock of prior
    # cavities
    relative_reflection_off=0.01,

)

CONSTANTS = {'default': CONSTANTS_DEFAULT}


class Lockbox(object):
    def __init__(self, config="default"):
        """generic lockbox object, no implementation-dependent details here
        """
        self.c = MemoryTree(config=config)

    def _sortedseries(self, X, Y):
        xs = np.array([x for (x, y) in sorted(zip(X, Y))], dtype=np.float64)
        ys = np.array([y for (x, y) in sorted(zip(X, Y))], dtype=np.float64)
        return pandas.Series(ys, index=xs)

    def _fastparams(self):
        return self._params(*args, **kwargs)

    def _params(self):
        return dict()

    def fastparams(self, postfix=""):
        dic = self._fastparams()
        params = dict()
        for key in dic.keys():
            params[key + postfix] = dic[key]
        return params

    def params(self, postfix=""):
        dic = dict()
        dic.update(self._params())
        for k in self.constants.keys():
            dic["rp_constants_" + k] = self.constants[k]
        params = dict()
        for key in dic.keys():
            params[key + postfix] = dic[key]
        return params


class Pyrpl(Lockbox):

    def __init__(self, constants=None, cavity='FPF2', reloadfpga=True):
        """red pitaya lockbox object"""
        super(Pyrpl, self).__init__(constants=constants, cavity=cavity)
        # initialize RedPitaya object
        self.rp = RedPitaya(
            hostname=self.constants["hostname"],
            autostart=True,
            reloadfpga=reloadfpga,
            filename=self.constants["fpgafile"],
            dirname=self.constants["fpgadir"],
            frequency_correction=self.constants["frequency_correction"])
        self.constants["reloadfpga"] = reloadfpga
        # shortcuts
        self.fa = self.rp.asga  # output channel 1
        self.fb = self.rp.asgb  # output channel 2
        if self.constants["coarse_output"] == 1:
            self.f = self.fa
        elif self.constants["coarse_output"] == 2:
            self.f = self.fb
        elif self.constants["lock_output"] == 1:
            self.f = self.fa
            print "Lock output will be used for coarse sweep"
        elif self.constants["lock_output"] == 2:
            self.f = self.fb
            print "Lock output will be used for coarse sweep"
        else:
            print "Coarse output >2 not implemented yet!!!"
        self.s = self.rp.scope
        self.hk = self.rp.hk
        self.ams = self.rp.ams
        self.iq = self.rp.pid11  # for iq it can be any one..
        # initialize pid attribution depending on configuration
        self.sof = self._get_pid(
            input=self.constants["reflection_input"],
            output=self.constants["lock_output"])
        if "lock_aux_output" in self.constants and self.constants[
                "lock_aux_output"] != 0:
            self.sof_aux = self._get_pid(
                input=self.constants["reflection_input"],
                output=self.constants["lock_aux_output"])
        else:
            self.sof_aux = None
        self.setup_pdh(turn_off=True)
        self.setup_pdh(turn_off=False)  # creates the objets for pdh
        self.setup_pdh(turn_off=True)
        self.stage = -1  # means the cavity was never locked
        self.alarmtime = 0
        # lockbox-related initialization
        self.scope_reset()
        t0 = time()
        for i in range(100):
            self.coarse = self.coarse  # set coarse to its last value
        t1 = time()
        self.commdelay = max([(t1 - t0) / 100.0, 1e-5])
        print "Communication time estimate: ", self.commdelay * 1e3, "ms"
        print "FPGA at %.2f degrees celsius" % self.rp.ams.temp
        print self.constants["lockbox_name"], "initialized!"

    def _get_pid(self, input=1, output=1):
        pid = self._get_pid_item(input=input, output=output)
        if "pid_filter" in self.constants:
            pid.filter = self.constants["pid_filter"]
        return pid

    def _get_pid_item(self, input=1, output=1):
        if input == 1 and output == 1:
            return self.rp.pid11
        elif input == 1 and output == 2:
            return self.rp.pid21
        elif input == 2 and output == 1:
            return self.rp.pid12
        elif input == 2 and output == 2:
            return self.rp.pid22
        elif input == 3 and output == 1:
            if self.rp.pid11.inputiq:
                return self.rp.pid11
            elif self.rp.pid12.inputiq:
                return self.rp.pid12
        elif input == 3 and output == 2:
            if self.rp.pid22.inputiq:
                return self.rp.pid22
            elif self.rp.pid21.inputiq:
                return self.rp.pid21
        return None  # no pid found

    """auxiliary functions for signal treatment"""

    def _get_min_step(self, output="coarse"):
        if output == "coarse":
            if (self.constants["coarse_output"] ==
                    1 or self.constants["coarse_output"] == 2):
                resolution = 14
                mi = self.constants["coarse_min_volt"]
                ma = self.constants["coarse_max_volt"]
                range = 2.0
                return (1.0 / 2**resolution / (np.abs(ma - mi) / range))
            else:  # DAC output, incomplete
                resolution = 10
                range = 1.8
                return (1.0 / 2**resolution * range)
        elif output == "lock" or "pid":
            return 1

    def _get_stepdelay(self, output, range, duration, instructions=1):
        range = np.abs(range)
        minstep = self._get_min_step(output=output)
        deadtime = range / minstep * self.commdelay * instructions
        if deadtime < duration:  # best option: move by min_step and wait in between
            steps = np.round(range / minstep) + 1
            delay = (duration - deadtime) / steps
        else:  # worse option: make larger steps to do it in time
            delay = self.constants["min_delay"]
            deadtime += delay
            steps = np.round(range / minstep / (deadtime / duration)) + 1
        if steps < 2:  # do at least 2 steps
            steps = 2
        return steps, delay

    def _get_one_signal(self, signal_number=1, type="input"):
        if type == "input" and signal_number == 1:
            return self.s.adc1
        elif type == "input" and signal_number == 2:
            return self.s.adc2
        elif type == "quadrature" and signal_number == 1:
            return self.s.iq1
        elif type == "quadrature" and signal_number == 2:
            return self.s.iq2
        elif type == "output" and signal_number == 1:
            return self.s.dac1
        elif type == "output" and signal_number == 2:
            return self.s.dac2
        else:
            return None

    def _get_signal(
            self,
            signal_number,
            type='input',
            avg=0,
            do_rms=False,
            minmax=False,
            trace=False,
            trace_frequency=10e3):
        # avg = 0: take a whole scope trace of coherent data
        # avg >0: take avg individual samples, not necessarily uniformly spaced
        # in time
        if avg == 1:
            return self._get_one_signal(signal_number=signal_number, type=type)
        if type == 'output':  # swap signal 1 and 2 as scope channel 2 records output 1 and the other way around
            if signal_number == 1:
                signal_number = 2
            elif signal_number == 2:
                signal_number = 1
        self.scope_reset()
        beforestate = [
            self.s.dac2_on_ch1,
            self.s.quadrature_on_ch1,
            self.s.dac1_on_ch2,
            self.s.quadrature_on_ch2]
        if signal_number == 1:
            if type == 'input':
                self.s.dac2_on_ch1 = False
            elif type == 'output':
                self.s.dac2_on_ch1 = True
            elif type == 'quadrature':
                self.s.quadrature_on_ch1 = True
        elif signal_number == 2:
            if type == 'input':
                self.s.dac1_on_ch2 = False
            elif type == 'output':
                self.s.dac1_on_ch2 = True
            elif type == 'quadrature':
                self.s.quadrature_on_ch2 = True
        if trace:
            data = self.rp.getbuffer(self.s.rawdata_ch2)
            self.s.arm(frequency=trace_frequency, trigger_source=1)
            sleep(1.0 / self.s.frequency)
            if signal_number == 1:
                data = self.rp.getbuffer(self.s.data_ch1)
            else:
                data = self.rp.getbuffer(self.s.data_ch2)
        if avg == 0:
            self.s.arm(
                frequency=self.constants["mean_measurement_frequency"],
                trigger_source=1)
            sleep(1.0 / self.s.frequency)
            if signal_number == 1:
                data = self.rp.getbuffer(self.s.rawdata_ch1)
            else:
                data = self.rp.getbuffer(self.s.rawdata_ch2)
        else:
            data = np.zeros(avg, dtype=np.float)
            for i in range(avg):
                if signal_number == 1:
                    data[i] = self.s.onedata_ch1
                else:
                    data[i] = self.s.onedata_ch2
        self.s.dac2_on_ch1 = beforestate[0]
        self.s.quadrature_on_ch1 = beforestate[1]
        self.s.dac1_on_ch2 = beforestate[2]
        self.s.quadrature_on_ch2 = beforestate[3]

        if trace:
            times = self.rp.getbuffer(self.s.times)
            return pandas.Series(data, index=times)
        mean = data.mean()
        if do_rms and not minmax:
            rms = np.sqrt((data**2).mean() - mean**2)
            return mean, rms
        elif minmax and not do_rms:
            min = data.min()
            max = data.max()
            return mean, min, max
        elif minmax and do_rms:
            rms = np.sqrt((data**2).mean() - mean**2)
            min = data.min()
            max = data.max()
            return mean, rms, min, max
        else:
            return mean

    def get_mean(self, signal="reflection", avg=0, rms=False, minmax=False):
        if signal == 1 or signal == 2:
            return self._get_signal(
                signal_number=signal,
                type="input",
                avg=avg,
                do_rms=rms,
                minmax=minmax)
        elif signal == 3:
            return self._get_signal(
                signal_number=1,
                type="quadrature",
                avg=avg,
                do_rms=rms,
                minmax=minmax)
        elif signal == "reflection":
            return self._get_signal(
                signal_number=self.constants["reflection_input"],
                type="input",
                avg=avg,
                do_rms=rms,
                minmax=minmax)
        elif signal == "pdh" or signal == "lock":
            channel = self.constants[signal + "_input"]
            if channel == 3:
                return self._get_signal(
                    signal_number=1,
                    type="quadrature",
                    avg=avg,
                    do_rms=rms,
                    minmax=minmax)
            else:
                return self._get_signal(
                    signal_number=channel,
                    type="input",
                    avg=avg,
                    do_rms=rms,
                    minmax=minmax)
        elif signal == "output":
            channel = self.constants["lock_output"]
            return self._get_signal(
                signal_number=channel,
                type="output",
                avg=avg,
                do_rms=rms,
                minmax=minmax)
        else:
            return None

    @property
    def reflection(self):
        return self.get_mean("reflection", avg=1)

    @property
    def reflection_V(self):
        return self.get_mean("reflection", avg=1) / 8191.0

    @property
    def reflection_mW(self):
        return (
            self.get_mean(
                "reflection",
                avg=1) - self.constants["dark_reflection"]) * self.constants["calibration_slope"]

    def _relative_reflection(self, refl):
        return float(refl - self.constants["dark_reflection"]) / float(
            self.constants["offres_reflection"] - self.constants["dark_reflection"])

    @property
    def relative_reflection(self):
        return self._relative_reflection(self.reflection)

    @property
    def laser_off(self):
        if (self.relative_reflection < self.constants[
                "relative_reflection_off"]):
            print "Laser is off, aborting..."
            return True
        else:
            return False

    @property
    def pdh(self):
        return self.get_mean("pdh", avg=1)

    @property
    def pdh_V(self):
        return self.get_mean("pdh", avg=1) / 8191.0

    def _relative_pdh(self, pdh):
        return float(pdh - self.constants["offset_pdh"])\
            / float(self.pdh_max - self.constants["offset_pdh"])

    @property
    def relative_pdh(self):
        return self._relative_pdh(self.pdh)

    @property
    def d(self):  # diagnostics
        r, rrms = self.get_mean("reflection", avg=0, rms=True)
        p, prms = self.get_mean("pdh", avg=0, rms=True)
        print "rel. reflection = {0} +- {1}".format(self._relative_reflection(r), self._relative_reflection(rrms + self.constants["dark_reflection"]))
        print "pdh signal      = {0} +- {1}".format(p, prms)
        print "rel. pdh signal      = {0} +- {1}".format(p / self.pdh_max, prms / self.pdh_max)
        return r, rrms, p, prms

    def errorsignals(self, frequency=None):
        input = list()
        inputnames = list()
        dacmode = False
        if self.constants["reflection_input"] == 1 or self.constants[
                "reflection_input"] == 2:
            input.append(self.constants["reflection_input"])
            inputnames.append("error reflection")
        if self.constants["pdh_input"] == 1 or self.constants[
                "pdh_input"] == 2:
            input.append(self.constants["pdh_input"])
            inputnames.append("error pdh")
        elif self.constants["pdh_input"] == 3:
            pdhinput = 3 - self.constants["reflection_input"]
            input.append(pdhinput)
            inputnames.append("error pdh")
            dacmode = True
            if pdhinput == 1:
                self.s.quadratures_on_ch1 = True
            elif pdhinput == 2:
                self.s.quadratures_on_ch2 = True
        if frequency is None:
            frequency = 1000.0
        c2, c3 = self.scope_trace(input=input,
                                  frequency=frequency,
                                  trigger_source=1,
                                  name_prefix=inputnames,
                                  dacmode=dacmode)
        c2.data -= np.float(self.constants["dark_reflection"]) / 8192.0
        c3.data -= np.float(self.constants["offset_pdh"]) / 8192.0
        fp = self.fastparams()
        c2.params.update(fp)
        c3.params.update(fp)
        c2.save()
        c3.save()
        if "last_sbreflection_curve" in self.constants:
            CurveDB.objects.get(
                pk=self.constants["last_sbreflection_curve"]).add_child(c2)
        elif "last_reflection_curve" in self.constants:
            CurveDB.objects.get(
                pk=self.constants["last_reflection_curve"]).add_child(c2)
        if "last_pdh_curve" in self.constants:
            CurveDB.objects.get(
                pk=self.constants["last_pdh_curve"]).add_child(c3)
        if "last_calibration_reflection" in self.constants:
            CurveDB.objects.get(
                pk=self.constants["last_calibration_reflection"]).add_child(c2)
        if "last_calibration_pdh" in self.constants:
            CurveDB.objects.get(
                pk=self.constants["last_calibration_pdh"]).add_child(c3)

    @property
    def output(self):
        return self.get_mean("output", avg=1)

    @property
    def output_V(self):
        return self.get_mean("output", avg=1) / 8191.0

    @output.setter
    def output(self, v):
        v = int(np.round(v))
        self.f.onedata = 0
        self.f.trigger_source = 0
        self.f.sm_reset = True
        self.f.offset = v

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
        """minimum allowed = 0, maximul =1, default coarse output is Out2"""
        if v > 1.0:
            v = 1.0
        elif v < 0.0:
            v = 0.0
        self._coarse_setter(v)

    def _coarse_setter(self, v):
        setV = self.constants["coarse_min_volt"] * \
            (1.0 - v) + self.constants["coarse_max_volt"] * v
        set = int(np.round(setV * 8191))
        # if self.constants["verbosity"]:
        # print "Setting coarse to %.2f"%setV+" V == %d"%set
        """implement coarsesetting here"""
        if self.constants["coarse_output"] == 1:
            f = self.fa
        elif self.constants["coarse_output"] == 2:
            f = self.fb
        else:
            print "coarse_output > 2 not yet implemented.. Coarse does not work in this configuration."
            return
        f.onedata = 0
        f.trigger_source = 0
        f.sm_reset = True
        f.offset = set
        self._coarse = v

    def darknoise(self, avg=0):
        print "Make sure all light is off for this measurement"
        reflection = self.get_mean("reflection", avg=avg)
        pdh = self.get_mean("pdh", avg=avg)
        constants = dict(
            last_dark_reflection=self.constants["dark_reflection"],
            last_dark_pdh=self.constants["dark_pdh"],
            dark_reflection=reflection,
            dark_pdh=pdh)
        self.constants.update(constants)
        self._save_constants(constants)
        print "execute _pdh_offset(avg=0) for", self.constants["lockbox_name"], "manually please!"
        # if "laststage" in self.constants and self.constants["laststage"]>=PDHSTAGE:
        #    pdhstate=self.pdhon
        #    self.setup_pdh()
        #    self._pdh_offset(avg=avg) #optional, but very useful here
        #    self.setup_pdh(turn_off=(not pdhstate))
        print "Darknoise of", self.constants["lockbox_name"], "successfully acquired!"

    def offresonant(self, avg=0, override_laseroff=False):
        print "make sure cavity is unlocked here"
        if self.laser_off and not override_laseroff:
            if self.reflection < 500:
                return
        reflection = self.get_mean("reflection", avg=avg)
        pdh = self.get_mean("pdh", avg=avg)
        constants = dict(offres_reflection=reflection,
                         offres_pdh=pdh)
        self.setup_pdh(turn_off=True)
        self.setup_pdh()
        pdh = self.get_mean("pdh", avg=avg)
        self.setup_pdh(turn_off=True)
        constants.update(dict(offset_pdh=pdh))
        self.constants.update(constants)
        self._save_constants(constants)

    def calibrate_power(self, power):
        """
        calibrates everything in units of power
        """
        r = self.get_mean(signal="reflection") - \
            self.constants["dark_reflection"]
        constants = dict(
            calibration_power=power,
            calibration_reflection=r,
            calibration_slope=power / r)
        self.constants.update(constants)
        self._save_constants(constants)
        print "Lockbox input will saturate around ", self.constants["calibration_slope"] * 8191.5, "mW"

    @property
    def power(self):
        r = self.get_mean(signal="reflection") - \
            self.constants["dark_reflection"]
        return r * self.constants["calibration_slope"]

    @property
    def power_offresonant(self):
        r = self.constants["offres_reflection"] - \
            self.constants["dark_reflection"]
        return r * self.constants["calibration_slope"]

    def resonant(self, avg=0):
        print "make sure cavity is locked here"
        reflection = self.get_mean("reflection", avg=avg)
        pdh = self.get_mean("pdh", avg=avg)
        constants = dict(res_reflection=reflection,
                         res_pdh=pdh)
        self.constants.update(constants)
        self._save_constants(constants)

    def _pdh_offset(self, avg=0):
        print "taking new pdh offsets"
        pdh = self.get_mean("pdh", avg=avg)
        constants = dict(offset_pdh=pdh)
        self.constants.update(constants)
        self._save_constants(constants)

    @property
    def _outlen(self):
        decimation = self.s.data_decimation
        lastpoint = self.f.lastpoint
        return np.round(float(self.f.lastpoint + 1) /
                        float(self.s.data_decimation)) % self.s.data_length

    @property
    def _outi(self):
        points = self._outlen
        d = np.cos(np.linspace(0.0, 2 * np.pi, points,
                               endpoint=False)) * float(-(2**13 - 1))
        return d

    @property
    def _outq(self):
        decimation = self.s.data_decimation
        lastpoint = self.f.lastpoint
        points = np.long(
            np.round(
                float(
                    self.f.lastpoint +
                    1) /
                float(
                    self.s.data_decimation)))
        d = np.sin(np.linspace(0.0, 2 * np.pi, points,
                               endpoint=False)) * float(-(2**13 - 1))
        return d

    def _outsin(self, amplitude=None):
        if amplitude is None:
            amplitude = self.constants["sweep_amplitude"]
        points = self._outlen
        d = amplitude * np.cos(np.linspace(0.0, 2 * np.pi,
                                           points, endpoint=False)) * float(-(2**13 - 1))
        return d

    def _outramp(self, amplitude=None):
        if amplitude is None:
            amplitude = self.constants["sweep_amplitude"]
        points = self._outlen
        d = amplitude * (np.abs((np.linspace(-2.0, 2.0, points,
                                             endpoint=False))) - 1.0) * float(-(2**13 - 1))
        return d

    def _outhalframp(self, amplitude=None):
        if amplitude is None:
            amplitude = self.constants["sweep_amplitude"]
        points = self._outlen
        d = amplitude * np.linspace(-8192.0, 8191.0, points, endpoint=True)
        return d

    def _get_buffers(self, data_shorten=False):
        """fill the buffers of all trace_xxx variables with their current values"""
        self.trace_1 = self.rp.getbuffer(self.s.data_ch1_current)
        self.trace_2 = self.rp.getbuffer(self.s.data_ch2_current)
        self.trace_time = self.rp.getbuffer(self.s.times)
        self.trace_outi = self._outi
        if data_shorten:
            data_length = self._outlen
            self.trace_1 = self.trace_1[0:data_length]
            self.trace_2 = self.trace_2[0:data_length]
            self.trace_time = self.trace_time[0:data_length]
        # self.scope_reset()

    def _sweep_setup(self, amplitude=None, frequency=None, dacmode=0):
        """setup for a sweep measurement, outputs one sin wave on fine output and prepares scope for acquisition """
        if amplitude is None:
            amplitude = self.constants["sweep_amplitude"]
        else:
            amplitude = amplitude / 8191.0
        if frequency is None:
            frequency = self.constants["sweep_frequency"]
        self.f.setup_cosine(
            frequency=frequency,
            amplitude=amplitude,
            onetimetrigger=True)
        self.s.setup(frequency=frequency, trigger_source=8, dacmode=dacmode)

    def sweep_coarse(
            self,
            amplitude=None,
            frequency=None,
            waveform="ramp",
            offset=None,
            onetimetrigger=False):
        """waveform is either ramp or sine
           amplitude = 1.0 corresponds to full coarse range
        """
        self.unlock(jump=0)
        if amplitude is None:
            amplitude = self.constants["sweep_amplitude"]
        mi = self.constants["coarse_min_volt"]
        ma = self.constants["coarse_max_volt"]
        if offset is None:
            self.coarse = (ma + mi) / 4.0 + 0.5
        else:
            self.coarse = offset
        rel_amplitude = np.abs(ma - mi) / 2.0 * amplitude
        if frequency is None:
            frequency = self.constants["sweep_frequency"]

        if self.constants["coarse_output"] == 1:
            f = self.fa
        elif self.constants["coarse_output"] == 2:
            f = self.fb
        else:
            print "Coarse sweep for output", self.constants["coarse_output"], "not implemented!"
            return
        if waveform == "ramp":
            f.setup_ramp(
                frequency=frequency,
                amplitude=amplitude,
                onetimetrigger=onetimetrigger,
                offset=f.offset)
        else:
            f.setup_cosine(
                frequency=frequency,
                amplitude=amplitude,
                onetimetrigger=onetimetrigger,
                offset=f.offset)
        f.trig(frequency=frequency)
        return (1.0 / f.frequency)

    def sweep_coarse_quit(self):
        self.coarse = self._coarse
        self.f.scale = 0

    def scope_reset(self):
        self.s.setup(
            frequency=self.constants["mean_measurement_frequency"],
            trigger_source=1,
            dacmode=False)

    def scope_curves(self, name_prefix=""):
        self._get_buffers()
        c1 = CurveDB.create(self.trace_time, self.trace_1 / 8192.)
        c2 = CurveDB.create(self.trace_time, self.trace_2 / 8192.)
        c1.name = name_prefix + "channel1"
        c1.save()
        c2.name = name_prefix + "channel2"
        c2.save()
        # c1.add_child(c2)
        return c1, c2

    def scope_trace(
            self,
            input=[
                1,
                2],
            frequency=1000.0,
            trigger_source=1,
            name_prefix="",
            dacmode=False):
        """
        acquires the data of an input during one sweep
        input is the number of input, can be a list of two
        """
        if isinstance(input, list):
            input = input[:2]
        else:
            input = [input]
        if isinstance(name_prefix, list):
            name_prefix = name_prefix[:2]
        else:
            name_prefix = [name_prefix]
        if len(name_prefix) < len(input):
            name_prefix.append(name_prefix[0])
        self.s.setup(
            frequency=frequency,
            trigger_source=trigger_source,
            dacmode=dacmode)
        self.s.arm(
            trigger_source=trigger_source,
            trigger_delay=int(
                self.s.data_length / 2))
        if trigger_source == 1:
            sleep(0.5 / self.s.frequency)
            self.s.sw_trig()
        sleep(1.0 / self.s.frequency)
        t0 = time()
        while (self.s.trigger_source != 0):
            sleep(0.01)
            if time() - t0 > 20:
                break
        curves = list()
        self._get_buffers()
        for i in range(len(input)):
            if input[i] == 1:
                c = CurveDB.create(self.trace_time, self.trace_1 / 8192.)
            else:
                c = CurveDB.create(self.trace_time, self.trace_2 / 8192.)
            c.name = name_prefix[i] + " channel " + str(input[i])
            c.params.update(
                dict(
                    input=input[i],
                    frequency=frequency,
                    trigger_source=trigger_source))
            c.save()
            curves.append(c)
        return tuple(curves)

    def sweep_acquire(
            self,
            input=1,
            output=1,
            frequency=None,
            amplitude=None,
            waveform=None,
            data_shorten=True):
        """
        acquires the data of an input during one sweep
        """
        if output == 2:
            f = self.fb
        else:
            f = self.fa

        if amplitude is None:
            amplitude = self.constants["sweep_amplitude"]
        # amplitude *= 8191.0 #convert from volts to counts - now this is
        # implemented in monitor.py already
        if frequency is None:
            frequency = self.constants["sweep_frequency"]
        if waveform is None:
            waveform = self.constants["sweep_waveform"]
        if waveform == "ramp":
            f.setup_ramp(
                frequency=frequency,
                amplitude=amplitude,
                onetimetrigger=True)
        elif waveform == "halframp":
            f.setup_halframp(
                frequency=frequency,
                amplitude=amplitude,
                onetimetrigger=True)
        else:  # "sine"
            f.setup_cosine(
                frequency=frequency,
                amplitude=amplitude,
                onetimetrigger=True)

        self.s.setup(frequency=frequency, trigger_source=8, dacmode=False)
        if input == output or input - 2 == output:
            if output == 1:
                self.s.dac1_on_ch2 = True
            elif output == 2:
                self.s.dac2_on_ch1 = True
        if input == 3:
            self.s.quadrature_on_ch1 = True
            input = 1
        elif input == 4:
            self.s.quadrature_on_ch2 = True
            input = 2
        self.s.arm(frequency=frequency, trigger_source=8)
        f.trig(frequency=frequency)
        sleep(1.0 / self.s.frequency)
        if data_shorten:
            data_length = self._outlen
        else:
            data_length = None  # means unlimited for np.arrays
        if input == 1:
            indata = self.rp.getbuffer(self.s.data_ch1_current)[0:data_length]
        elif input == 2:
            indata = self.rp.getbuffer(self.s.data_ch2_current)[0:data_length]
        if input == 1 and output == 1:
            outdata = self.rp.getbuffer(self.s.data_ch2_current)[0:data_length]
        elif input == 2 and output == 2:
            outdata = self.rp.getbuffer(self.s.data_ch1_current)[0:data_length]
        else:
            if waveform == "ramp":
                outdata = self._outramp(amplitude=amplitude)
            elif waveform == "halframp":
                outdata = self._outhalframp(amplitude=amplitude)
            else:
                outdata = self._outsin(amplitude=amplitude)
        return self._sortedseries(outdata, indata)

    def quadratures_acquire(self, frequency=None, times=False):
        if frequency is None:
            frequency = self.constants["mean_measurement_frequency"]
        self.s.setup(frequency=frequency, trigger_source=0)
        self.s.quadrature_on_ch1 = True
        self.s.quadrature_on_ch2 = True
        self.s.trigger_source = 1
        sleep(1.0 / self.s.frequency)
        q1 = np.roll(self.rp.getbuffer(self.s.rawdata_ch1), -
                     (self.s.write_pointer_current + 1))
        q2 = np.roll(self.rp.getbuffer(self.s.rawdata_ch2), -
                     (self.s.write_pointer_current + 1))
        if times:
            t = self.rp.getbuffer(self.s.times)
        # self.s.arm(frequency=frequency,trigger_source=1)
        if times:
            return (q1, q2, t)
        else:
            return (q1, q2)

    def spectrum_trace(
            self,
            name="rp_spectrum",
            input=1,
            frequency=1e3,
            kaiserbeta=15.0,
            avg=1):
        sumspectrum = None
        for i in range(avg):
            self.s.setup(frequency=frequency, trigger_source=0)
            self.s.trigger_source = 1
            sleep(1.0 / self.s.frequency)
            if input == 1:
                data = np.roll(self.rp.getbuffer(
                    self.s.rawdata_ch1), -(self.s.write_pointer_current + 1))
            else:
                data = np.roll(self.rp.getbuffer(
                    self.s.rawdata_ch2), -(self.s.write_pointer_current + 1))
            dt = 8e-9 * self.s.data_decimation
            wdata = data * np.kaiser(len(data), kaiserbeta)
            spectrum = np.fft.rfft(wdata)**2
            if sumspectrum is None:
                sumspectrum = spectrum
            else:
                sumspectrum += spectrum
        frequencies = np.fft.rfftfreq(len(data), d=dt)
        sumspectrum /= avg
        c = CurveDB.create(frequencies, sumspectrum)
        c.name = name
        c.params.update(dict(rp_input=input,
                             rp_frequency=self.s.frequency,
                             rp_kaiserbeta=kaiserbeta,
                             rp_avg=avg
                             ))
        c.save()
        return c

    def na_trace(
            self,
            input=1,
            output=1,
            start=0,
            stop=100e3,
            points=1001,
            rbw=100,
            avg=1.0,
            amplitude=0.1,
            autosave=True,
            name="rpna_curve",
            sleeptimes=0.5,
            stabilized=None,
            maxamplitude=0.2):
        """records the complex transfer function between start and stop frequency, returns a pandas series"""
        print "Estimated acquisition time:", self.iq.na_time(points=points, rbw=rbw, avg=avg), "s"
        sys.stdout.flush()  # flush the message to the screen
        if stabilized is None:
            x, y = self.iq.na_trace(input=input, output=output, start=start, stop=stop,
                                    points=points, rbw=rbw, avg=avg, amplitude=amplitude, sleeptimes=sleeptimes)
        else:
            x, y, z = self.iq.na_trace_stabilized(input=input, output=output, start=start, stop=stop, points=points, rbw=rbw,
                                                  avg=avg, amplitude=amplitude, sleeptimes=sleeptimes, maxamplitude=maxamplitude, stabilized=stabilized)
            zz = self.rp.getbuffer(z)
        xx = self.rp.getbuffer(x)
        yy = self.rp.getbuffer(y)
        saturation_db = -20. * np.log10(amplitude)
        if autosave:
            c = CurveDB.create(xx, yy)
            c.name = name
            d = dict(
                start=start,
                stop=stop,
                input=input,
                output=output,
                points=points,
                rbw=rbw,
                avg=avg,
                amplitude=amplitude,
                saturation_db=saturation_db,
                hostname=self.constants["hostname"],
                stabilized=stabilized,
                maxamplitude=maxamplitude,
                type="RPNAcurve")
            c.params.update(d)
            c.save()
            if not stabilized is None:
                d = CurveDB.create(xx, zz, name="amplitudes")
                d.save()
                c.add_child(d)
            return c
        else:
            return pandas.Series(yy, index=xx)

    def na_reset(self):
        self.iq.iq_channel = 1
        self.iq.iq_constantgain = 0

    def optimize_gain(
            self,
            output=None,
            deviation=0.3,
            p_or_i="p",
            points=31,
            avg=0):
        if not self.islocked:
            self.relock()
        if output is None:
            output = self.constants["lock_output"]
        if self.stage == PDHSTAGE:
            input = self.constants["pdh_input"]
        else:
            input = self.constants["reflection_input"]
        pid = self._get_pid(input=input, output=output)
        # proportional part
        gains = list()
        rrms = list()
        prms = list()
        if p_or_i == "i":
            center = pid.integral
        else:
            center = pid.proportional
        if self.constants["verbosity"]:
            print "Input:", input, "Output:", output, "Actual", p_or_i, "gain:", center
        for g in np.linspace(0, 1, points / 2 + 1, endpoint=True):
            for sign in [1.0, -1.0]:
                self.relock()
                gain = np.round(center * (1.0 + deviation * g * sign))
                if p_or_i == "i":
                    pid.integral = gain
                else:
                    pid.proportional = gain
                if self.islocked:
                    if input == self.constants["pdh_input"]:
                        p, pms = self.get_mean(signal="pdh", avg=avg, rms=True)
                        prms.append(pms)
                    r, rms = self.get_mean(
                        signal="reflection", avg=avg, rms=True)
                    rrms.append(rms)
                    gains.append(gain)
        if p_or_i == "i":
            pid.integral = center
        else:
            pid.proportional = center
        norm_r = self.constants["offres_reflection"] - \
            self.constants["dark_reflection"]
        data_refl = self._sortedseries(gains, rrms) / norm_r
        if input == self.constants["pdh_input"]:
            norm_p = self.pdh_max - self.constants["offset_pdh"]
            data_pdh = self._sortedseries(gains, prms) / norm_p
            return data_pdh, data_refl
        return data_refl

    @property
    def pdhon(self):
        return self._pdhon

    @property
    def pdh_max(self):
        # return self.constants["pdh_max"]
        # return
        # self.constants["pdh_max"]*self.constants["offres_reflection"]/self.constants["offres_reflection_optimum"]
        return self.constants["pdh_max"]  # _last

    def setup_pdh(self, turn_off=False):
        if turn_off:
            self._disable_pdh()
            self._pdhon = False
        else:
            if not self.pdhon:
                self._setup_pdh()
                self._pdhon = True

    def _setup_pdh(self):
        pass

    def _disable_pdh(self):
        pass

    @property
    def islocked(self):
        return self._islocked(verbose=False)

    def _islocked(self, refl=None, verbose=True):
        return (not self.issaturated)

    @property
    def issaturated(self):
        """returns true if any of the outputs have reached saturation since the last call of this function"""
        return (self.rp.pid11.saturated or self.rp.pid22.saturated)

    def unlock(self, jump=None):
        #self.stage = UNLOCKEDSTAGE
        # unlock and make a coarse jump away from the resonance if desired
        for pid in [
                self.rp.pid11,
                self.rp.pid12,
                self.rp.pid21,
                self.rp.pid22]:
            pid.reset = True
            pid.integral = 0
            pid.proportional = 0
            pid.derivative = 0
            pid.reset = False
        self.na_reset()
        self.setup_pdh(turn_off=True)
        # self.iq.iq_set(channel=1,frequency=0,phase=180,bandwidth=0.5e3,gain=0.00)
        # self.iq.iq_channel=0
        self.output = 0
        if jump is None:
            self.coarse += self.constants["unlock_jump"]
        else:
            self.coarse += jump

    def _params(self):
        r, rrms, rmin, rmax = self.get_mean(
            signal="reflection", rms=True, minmax=True)
        p, prms, pmin, pmax = self.get_mean(
            signal="pdh", rms=True, minmax=True)
        dic = dict()
        dic.update({
            "rp_relative_reflection": self._relative_reflection(r),
            "rp_reflection_mean": r,
            "rp_reflection_rms": rrms,
            "rp_reflection_min": rmin,
            "rp_reflection_max": rmax,
            "rp_relative_pdh": self._relative_pdh(p),
            "rp_offres_reflection": self.constants["offres_reflection"],
            "rp_pdh_mean": p,
            "rp_pdh_rms": prms,
            "rp_pdh_min": pmin,
            "rp_pdh_max": pmax,
            "rp_getdetuning": self.get_detuning(),
            "rp_pdhon": self.pdhon,
            "rp_stage": self.stage,
            "rp_islocked": self.islocked,
            "rp_waslocked": self.waslocked,
            "rp_waslocked_since": self._waslocked(gettime=True),
        })
        for pid, pidname in [(self.rp.pid11, "pid11"),
                             (self.rp.pid12, "pid12"),
                             (self.rp.pid21, "pid21"),
                             (self.rp.pid22, "pid22")]:
            dic.update({"rp_" + pidname + "_proportional": pid.proportional,
                        "rp_" + pidname + "_integral": pid.integral,
                        "rp_" + pidname + "_derivative": pid.derivative,
                        "rp_" + pidname + "_setpoint": pid.setpoint,
                        "rp_" + pidname + "_reset": pid.reset})
        return dic

    def _fastparams(self):
        r, rrms, rmin, rmax = self.get_mean(
            signal="reflection", rms=True, minmax=True)
        p, prms, pmin, pmax = self.get_mean(
            signal="pdh", rms=True, minmax=True)
        return dict({"rp_relative_reflection": self._relative_reflection(r),
                     "rp_relative_pdh": self._relative_pdh(p),
                     "rp_power_offres": self.power_offresonant,
                     "rp_getdetuning": self.get_detuning(),
                     "rp_stage": self.stage,
                     "rp_islocked": self.islocked,
                     "rp_waslocked": self.waslocked,
                     "rp_waslocked_since": self._waslocked(gettime=True),
                     "rp_gain_p": self.gain_p,
                     "rp_gain_i": self.gain_i,
                     })

    @property
    def gain_p(self):
        if self.stage >= SOFSTAGE:
            return self.pidpdh.proportional
        else:
            return self.sof.proportional

    @property
    def gain_i(self):
        if self.stage >= SOFSTAGE:
            return self.pidpdh.integral
        else:
            return self.sof.integral

# IIR section
    def setup_iir(
            self,
            sys,
            input=1,
            output=1,
            acbandwidth=None,
            loops=None,
            plot=True,
            save=False,
            turn_on=True,
            tol=1e-6):
        """Setup an IIR filter
        -----------------------------
        sys = (z,p,k)
        z = list of zeros in the complex plane, maximum 16
        p = list of zeros in the complex plane, maxumum 16
        k = overall gain
        the transfer function of the filter will be:
                  (z-z_0)*(z-z_1)...
        H(s) = k*-------------------
                  (z-p_0)*(z-p_1)...
        input:        input channel
        output:       output channel. If set to 0, direct output is disabled (for passing through PID module)
        acbandwidth:  if none, direct input is used, otherwise a high-pass is inserted before
        loops:        clock cycles per loop of the filter. must be at least 3
        turn_on:      automatically turn on the filter after setup
        plot:         if True, plots the theoretical and implemented transfer functions
        save:         if True, saves the predicted transfer functions to the database
        tol:          tolerance for matching conjugate poles or zeros into pairs, 1e-6 is okay
        """
        iq = self.iq
        if iq.iir_stages == 0:
            print "Error: This FPGA bitfile does not support IIR filters! Please use an IIR version!"
        iq.iir_channel = 0
        ch = iq.iq_channel
        iq.iq_channel = iq.iq_channels
        iq.iq_reset = True
        iq.iir_shortcut = False
        iq.iir_copydata = True

        # nasty bugfix here: needs cleanup of fpga code. avoids disconnecting
        # iq0 from its real input
        if input == 3 or input == 4:
            iq.iq_channel = 0
            if iq.iq_inputchannel == 1:
                input = 4
            elif iq.iq_inputchannel == 2:
                input = 3
            iq.iq_channel = iq.iq_channels

        iq.iq_advanced_inputchannel = input
        if output == 0:
            iq.iq_outputchannel = 1
            iq.iq_direct = False
        else:
            iq.iq_outputchannel = output
            iq.iq_direct = True
        if acbandwidth is None:
            iq.iq_accoupled = False
        else:
            iq.iq_accoupled = True
            if input == 2:
                iq.iq_acbandwidth2 = acbandwidth
            else:
                iq.iq_acbandwidth1 = acbandwidth

        iirbits = iq.iir_bits
        iirshift = iq.iir_shift
        z, p, k = sys
        preliminary_loops = int(max([len(p), len(z)]) + 1 / 2)
        if preliminary_loops > iq.iir_stages:
            print "Error: desired filter order cannot be implemented."
        c = iir.get_coeff(sys, dt=preliminary_loops * 8e-9,
                          totalbits=iirbits, shiftbits=iirshift,
                          tol=tol, finiteprecision=False)
        minimum_loops = len(c)
        if minimum_loops < 3:
            minimum_loops = 3
        if loops is None:
            loops = 3
        elif loops > 255:
            loops = 255
        loops = max([loops, minimum_loops])
        dt = loops * 8e-9 / iq._frequency_correction
        c = iir.get_coeff(sys, dt=dt,
                          totalbits=iirbits, shiftbits=iirshift,
                          tol=tol, finiteprecision=False)
        iq.iir_coefficients = c
        iq.iir_loops = loops
        f = np.array(self.rp.getbuffer(iq.iir_coefficients))
        self.iir_on = turn_on
        iq.iq_channel = ch
        # Diagnostics here
        if plot or save:
            if isinstance(plot, int):
                plt.figure(plot)
            else:
                plt.figure()
            tfs = iir.psos2plot(c, sys, n=2**16, maxf=5e6, dt=dt,
                                name="discrete system (dt=" + str(int(dt * 1e9)) + "ns)")
            tfs += iir.psos2plot(f, None, n=2**16, maxf=5e6,
                                 dt=dt, name="implemented system")
            plt.legend()
        if save:
            if not plot:
                plt.close()
            curves = list()
            for tf in tfs:
                w, h, name = tf
                curve = CurveDB.create(w, h)
                curve.name = name
                z, p, k = sys
                curve.params["iir_loops"] = loops
                curve.params["iir_zeros"] = str(z)
                curve.params["iir_poles"] = str(p)
                curve.params["iir_k"] = k
                curve.save()
                curves.append(curve)
            for curve in curves[:-1]:
                curves[-1].add_child(curve)
        print "IIR filter ready"
        print "Maximum deviation from design coefficients: ", max((f[0:len(c)] - c).flatten())
        print "Overflow pattern: ", bin(iq.iir_overflow)
        if save:
            return f, curves[-1]
        else:
            return f

    @property
    def iir_on(self):
        return not self.iq.iir_reset

    @iir_on.setter
    def iir_on(self, v):
        self.iq.iir_reset = not v

    def init_iir(
            self,
            plot=False,
            save=False,
            tol=1e-3,
            input=None,
            output=None):
        if input is None:
            if self.stage >= PDHSTAGE:
                input = self.constants["pdh_input"]
            else:
                input = self.constants["reflection_input"]
        if output is None:
            if hasattr(self, "pidpdh"):
                self.pidpdh.inputiqnumber = 0
            self.sof.inputiqnumber = 0
        else:
            self._get_pid(input=input, output=output).inputiqnumber = 0
        z, p, g = self.constants["iir_zpg"]
        z = [zz * 2 * np.pi for zz in z]
        p = [pp * 2 * np.pi for pp in p]
        k = g
        for pp in p:
            if pp != 0:
                k *= np.abs(pp)
        for zz in z:
            if zz != 0:
                k /= np.abs(zz)
        if "iir_loops" in self.constants:
            loops = self.constants["iir_loops"]
        else:
            loops = None
        if "iir_accbandwidth" in self.constants:
            acbandwidth = self.constants["iir_acbandwidth"]
        else:
            acbandwidth = 0

        ret = self.setup_iir(
            (z,
             p,
             k),
            acbandwidth=acbandwidth,
            input=input,
            output=0,
            loops=loops,
            turn_on=True,
            plot=plot,
            tol=tol,
            save=save)
        if output is None:
            if hasattr(self, "pidpdh"):
                if self.stage >= PDHSTAGE:
                    self.pidpdh.inputiqnumber = 2
                    self.sof.inputiqnumber = 0
                else:
                    self.pidpdh.inputiqnumber = 0
                    self.sof.inputiqnumber = 2
            else:
                self.sof.inputiqnumber = 2
        else:
            self._get_pid(input=input, output=output).inputiqnumber = 2
        if save:
            f, c = ret
            c.params.update(self.fastparams())
            c.save()
        return ret

    def tune_relock(self, fast=False):
        self.relock()

    def tune_iir(self, id=None, fit=None, pid="sof", input=None, output=None):
        from bodeplot_susceptibility5 import PZKSusceptibility
        self.bode = PZKSusceptibility(id=id)
        if not fit is None:
            self.bode.loadfit(id=fit)
        self.bode.lockbox = self
        if isinstance(pid, str):
            self.bode.pid = getattr(self, pid)
        else:
            self.bode.pid = pid
            self.bode.input = input
            self.bode.output = output

    def set_optimal_gains(self, save=True):
        # while not self.islocked:
        #    if self.sof.reset:
        #        self.lock(laststage = 3)
        #    else:
        #        self.lock(laststage = 3,sof_i = self.sof.integral,sof_p = self.sof.proportional,
        # sof_aux_i = self.sof_aux.integral,sof_aux_p =
        # self.sof_aux.proportional)
        if self.sof.integral != 0 or self.sof.proportional != 0:
            print "Estimating gains from sof lock..."
            if isinstance(self.slope, float) or isinstance(self.slope, double):
                slope = self.slope
            else:
                slope = self.slope(
                    signal="reflection",
                    value=self.sof.setpoint)
            d = dict(
                lock_i_times_slope=float(
                    self.sof.integral) *
                slope *
                self.constants["isr_correction"],
                lock_p_times_slope=float(
                    self.sof.proportional) *
                slope,
                slope_optimum=slope)
            print "lock_i_times_slope: ", float(self.sof.integral) * slope * self.constants["isr_correction"]
            print "lock_p_times_slope: ", float(self.sof.proportional) * slope
            if not self.sof_aux is None:
                d.update(
                    dict(
                        lock_aux_i_times_slope=float(
                            self.sof_aux.integral) *
                        slope *
                        self.constants["isr_correction"],
                        lock_aux_p_times_slope=float(
                            self.sof_aux.proportional) *
                        slope))
                print "lock_aux_i_times_slope: ", float(self.sof_aux.integral) * slope * self.constants["isr_correction"]
                print "lock_aux_p_times_slope: ", float(self.sof_aux.proportional) * slope
        elif self.pidpdh.integral != 0 or self.pidpdh.proportional != 0:
            print "Estimating gains from PDH lock..."
            slope = self.slope(signal="pdh", value=self.pidpdh.setpoint)
            d = dict(
                lock_i_times_slope=float(
                    self.pidpdh.integral) *
                slope *
                self.constants["isr_correction"],
                lock_p_times_slope=float(
                    self.pidpdh.proportional) *
                slope,
                slope_optimum=slope)
            print "lock_i_times_slope: ", float(self.pidpdh.integral) * slope * self.constants["isr_correction"]
            print "lock_p_times_slope: ", float(self.pidpdh.proportional) * slope
            if not self.sof_aux is None:
                d.update(
                    dict(
                        lock_aux_i_times_slope=float(
                            self.pidpdh_aux.integral) *
                        slope *
                        self.constants["isr_correction"],
                        lock_aux_p_times_slope=float(
                            self.pidpdh_aux.proportional) *
                        slope))
                print "lock_aux_i_times_slope: ", float(self.pidpdh_aux.integral) * slope * self.constants["isr_correction"]
                print "lock_aux_p_times_slope: ", float(self.pidpdh_aux.proportional) * slope
        else:
            print "The cavity must be locked in order to set optimum gains!"
        if save:
            self.constants.update(d)
            self._save_constants(d)


class Pyrpl_FP(Pyrpl):

    def find_coarse(self, start=0.0, stop=1.0):
        """ finds the coarse offset of a resonance in range """
        # define search parameters
        step = 0.5 * self._get_min_step("coarse")
        stopinterval = self.constants["coarse_searchprecision"]  # 2.0*step

        delay = 1.0 / self.constants["coarse_bandwidth"]
        initial_delay = min([10.0, 10 * delay])

        searchtime = self.constants["coarse_searchtime"]

        print "Waiting for coarse value to settle..."
        self.unlock()
        self.coarse = start
        sleep(initial_delay)

        self.scope_reset()
        self.s.frequency = 10e6
        #self.fine = 0

        if self.constants["find_coarse_redefine_means"]:
            self.offresonant()

        find_coarse_threshold = int(
            self.constants["dark_reflection"] +
            self.constants["find_coarse_upper_threshold"] *
            (
                self.constants["offres_reflection"] -
                self.constants["dark_reflection"]))
        if self.constants["reflection_input"] == 2:
            self.s.threshold_ch2 = find_coarse_threshold
            print "Coarse threshold set to %d" % self.s.threshold_ch2
            trigger_source = 5
        elif self.constants["reflection_input"] == 1:
            self.s.threshold_ch1 = find_coarse_threshold
            print "Coarse threshold set to %d" % self.s.threshold_ch1
            trigger_source = 3

        print "Starting resonance search..."
        for act_iteration in range(
                self.constants["find_coarse_max_iterations"]):
            # upwards search
            self.s.arm(trigger_source=trigger_source)
            print "sweeping upwards..."
            steps, delay = self._get_stepdelay(
                "coarse", stop - start, searchtime)
            for c in np.linspace(start, stop, steps):
                if (self.s.trigger_source == 0):
                    """resonance passed in positive direction"""
                    print "Passed upwards at %.4f" % c
                    break
                else:
                    self.coarse = c
                    sleep(delay)
            # wait a bit more if necessary
            for i in range(int(initial_delay / self.commdelay)):
                if (self.s.trigger_source == 0):
                    break
                else:
                    sleep(delay)
            if not stop == self.coarse:
                stop = self.coarse
                #searchtime *= self.constants["find_coarse_slowdown"]
            # downwards
            self.s.arm(trigger_source=trigger_source)
            print "sweeping downwards..."
            steps, delay = self._get_stepdelay(
                "coarse", stop - start, searchtime)
            for c in np.linspace(stop, start, steps):
                if (self.s.trigger_source == 0):
                    """resonance passed in negativedirection"""
                    print "Passed downwards at %.4f" % c
                    break
                else:
                    self.coarse = c
                    sleep(delay)
            # wait a bit more if necessary
            for i in range(int(initial_delay / self.commdelay)):
                if (self.s.trigger_source == 0):
                    break
                else:
                    sleep(delay)
            if not start == self.coarse:
                start = self.coarse
                #searchtime *= self.constants["find_coarse_slowdown"]
            if (stop - start) < stopinterval:
                self.coarse = (stop + start) / 2
                print "Resonance located at %.4f" % self.coarse
                self.scope_reset()
                return self.coarse
        # if we arrive here, the search must have failed...
        self.scope_reset()
        return None

    def _set_unlockalarm(self, threshold=None):
        if not self.islocked:
            self.s.arm(trigger_source=0)
            return
        if threshold is None:
            threshold = self.constants["lock_upper_threshold"]
        d = self.constants["dark_reflection"]
        r = self.constants["offres_reflection"]
        threshold = d + (r - d) * threshold
        self.scope_reset()
        self.s.frequency = 10e6
        if self.constants["reflection_input"] == 2:
            self.s.threshold_ch2 = threshold
            print "Coarse threshold set to %d" % self.s.threshold_ch2
            trigger_source = 4  # ch2 pos edge
        elif self.constants["reflection_input"] == 1:
            self.s.threshold_ch1 = threshold
            print "Coarse threshold set to %d" % self.s.threshold_ch1
            trigger_source = 2  # ch1 pos edge
        self.s.arm(trigger_source=trigger_source)
        self.alarmtime = time()

    def _waslocked(self, gettime=False):
        if gettime:
            if self.s.trigger_source != 0 and self.islocked:  # cavity still locked
                return self.alarmtime
            else:
                return time()
        else:
            if self.s.trigger_source != 0 and self.islocked:  # cavity still locked
                return True
            else:
                return False

    @property
    def waslocked(self):
        return self._waslocked(gettime=False)

    def _islocked(self, refl=None, verbose=True):
        if refl is None:
            refl = self.relative_reflection
        if verbose:
            r, rms = self.get_mean("reflection", avg=0, rms=True)
            print "rel. reflection = {0} +- {1}".format(self._relative_reflection(r), self._relative_reflection(rms + self.constants["dark_reflection"]))
        if refl <= self.constants["lock_upper_threshold"] and refl >= self.constants[
                "lock_lower_threshold"]:
            return True
        elif (self.sof.integral != 0) and self.stage > COARSEFINDSTAGE \
                and (self._relative_reflection(self.sof.setpoint) > self.constants["lock_upper_threshold"])\
                and (refl < 0.5 + 0.5 * self._relative_reflection(self.sof.setpoint)):
            print "Locked very far from resonance, beyond lock thresholds..."
            return True
        else:
            return False

    @property
    def R0(self):
        """resonant reflection coefficient of the cavity - depends on modulation depth for pdh sidebands"""
        if self.pdhon:
            return self.constants["cavity_R0_pdh"]
        else:
            return self.constants["cavity_R0"]

    def from_detuning(self, detuning_in_bandwidths, signal="reflection"):
        if signal == "reflection":
            cavity_R0 = self.R0
            rd = self.constants["dark_reflection"]
            r0 = self.constants["offres_reflection"]
            scale = (r0 - rd) * (1.0 - cavity_R0)
            return r0 - scale / (1.0 + detuning_in_bandwidths**2)
        elif signal == "pdh":
            pdhmax = self.pdh_max
            if self.constants["pdh_offsetcorrection"]:
                offset_pdh = self.constants["offset_pdh"]
            else:
                offset_pdh = 0
            return offset_pdh + pdhmax * 2 * detuning_in_bandwidths / \
                (1.0 + detuning_in_bandwidths**2)

    def to_detuning(self, value=None, signal="reflection"):
        if signal == "reflection":
            if value is None:
                value = self.reflection
            cavity_R0 = self.R0
            rd = self.constants["dark_reflection"]
            r0 = self.constants["offres_reflection"]
            scale = (r0 - rd) * (1.0 - cavity_R0)
            if r0 == value:
                return 100.0
            else:
                return np.sqrt(np.abs(scale / (r0 - value) - 1.0))
        elif signal == "pdh":
            if value is None:
                value = self.pdh
            if self.constants["pdh_offsetcorrection"]:
                value -= self.constants["offset_pdh"]
            pdhmax = self.pdh_max
            if value == 0:
                detuning_in_bandwidths = 0
            else:
                detuning_in_bandwidths = (
                    1.0 - np.sqrt(np.max([0, 1.0 - (value / pdhmax)**2]))) / (value / pdhmax)
            return detuning_in_bandwidths

    def get_detuning(self):
        if self.sof.integral != 0:
            actdetuning = self.to_detuning(
                value=self.sof.setpoint, signal="reflection")
        elif self.pidpdh.integral != 0:
            actdetuning = self.to_detuning(
                value=self.pidpdh.setpoint, signal="pdh")
        else:
            actdetuning = self.to_detuning(value=None, signal="reflection")
            # if actdetuning > 10: #avoid divergence issues
            #    actdetuning = 10.0
        return actdetuning

    def slope(self, value=None, signal="reflection"):
        if signal == "reflection":
            if value is None:
                value = self.reflection
            cavity_R0 = self.R0
            rd = self.constants["dark_reflection"]
            r0 = self.constants["offres_reflection"]
            scale = (r0 - rd) * (1.0 - cavity_R0)
            """
            reflection is offresonant value minus scaled lorentzian
            reflection = r0 - scale/(1.0+detuning_in_bandwidths**2)
            -> invert to obtain a formula for detuning_in_bandwidths
            plut the calculated value into the first (sof) derivative of relfection to obtain the scaled slope
            """
            #detuning_in_bandwidths = np.sqrt(np.abs(scale/(r0-value)-1.0))
            detuning_in_bandwidths = self.to_detuning(
                value=value, signal="reflection")
            slope = 2 * scale * detuning_in_bandwidths / \
                (1.0 + detuning_in_bandwidths**2)**2
            # if maxcorrection: #correct for gain enhancement by the resonance
            # at large detunings
            if self.constants["sof_maxcorrection"]:
                d2 = detuning_in_bandwidths**2
                excessgain = (1. + d2) * np.sqrt(1.0 + 5 * \
                              d2 + 4 * d2**2) / (1.0 + 4 * d2)
                slope *= excessgain
        elif signal == "pdh":
            if value is None:
                value = self.pdh
            """pdh signal is - when the detuning is betzeen -1 and +1 cavity bandwidths -
               proportional to first derivative of the reflection. Its slope is proportional to the second one.
               We will estimate the detuning through the pdh signal (since reflection at resonance has zero slope
               it is not a robust estimator for the detuning)
               pdh = pdhmax*16./9.*np.sqrt(3)*detuning_in_bandwidths/(1.0+detuning_in_bandwidths**2)**2
               since we need to find the solution of a 4th grade polynom, an iterative approach is faster than an
               analytical one:"""
            pdhmax = self.pdh_max
            detuning_in_bandwidths = self.to_detuning(
                value=value, signal="pdh")
            slope = 2 * pdhmax * (1.0 - detuning_in_bandwidths**2) / \
                (1.0 + detuning_in_bandwidths**2)**2
        if np.abs(slope) < np.abs(
                self.constants["slope_lower_limit"] *
                self.constants["slope_optimum"]):
            if slope < 0:
                slope = np.abs(
                    self.constants["slope_lower_limit"] * self.constants["slope_optimum"]) * (-1.0)
            else:
                slope = np.abs(
                    self.constants["slope_lower_limit"] *
                    self.constants["slope_optimum"])
        return slope

    def lock_opt(self, detuning=None, sof=None, pdh=None, time=0):
        aux = ("lock_aux_output" in self.constants) and (
            self.constants["lock_aux_output"] != 0)
        if pdh != 0 and not self.pdhon:  # turn on the pdh if necessary
            self.setup_pdh()
        if detuning is None:
            detuning = self.get_detuning()
        if time == -1:
            sof_sp = np.round(
                self.from_detuning(
                    detuning,
                    signal="reflection"))
            pdh_sp = np.round(self.from_detuning(detuning, signal="pdh"))
            sof_slope = self.slope(sof_sp, signal="reflection")
            pdh_slope = self.slope(pdh_sp, signal="pdh")
            self.sof.setpoint = sof_sp
            self.pidpdh.setpoint = pdh_sp
            sofintegral = self.constants[
                "lock_i_times_slope"] / self.constants["isr_correction"] / sof_slope * sof
            if np.abs(sofintegral) <= 0.5:
                self.sof.integral = np.sign(sofintegral)
            else:
                self.sof.integral = np.round(sofintegral)
            self.sof.proportional = np.round(
                self.constants["lock_p_times_slope"] / sof_slope * sof)
            pdhintegral = self.constants[
                "lock_i_times_slope"] / self.constants["isr_correction"] / pdh_slope * pdh
            if np.abs(pdhintegral) <= 0.5:
                self.pidpdh.integral = np.sign(pdhintegral)
            else:
                self.pidpdh.integral = np.round(pdhintegral)
            self.pidpdh.proportional = np.round(
                self.constants["lock_p_times_slope"] / pdh_slope * pdh)
            if aux:
                self.sof_aux.setpoint = sof_sp
                self.pidpdh_aux.setpoint = pdh_sp
                self.sof_aux.integral = np.round(
                    self.constants["lock_aux_i_times_slope"] /
                    self.constants["isr_correction"] /
                    sof_slope *
                    sof)
                self.sof_aux.proportional = np.round(
                    self.constants["lock_aux_p_times_slope"] / sof_slope * sof)
                self.pidpdh_aux.integral = np.round(
                    self.constants["lock_aux_i_times_slope"] /
                    self.constants["isr_correction"] /
                    pdh_slope *
                    pdh)
                self.pidpdh_aux.proportional = np.round(
                    self.constants["lock_aux_p_times_slope"] / pdh_slope * pdh)
            return
        else:
            if aux:
                instructions = 12
            else:
                instructions = 6
            actdetuning = self.get_detuning()
            sof_sp = self.from_detuning(actdetuning, signal="reflection")
            pdh_sp = self.from_detuning(actdetuning, signal="pdh")
            sof_slope = self.slope(sof_sp, signal="reflection")
            pdh_slope = self.slope(pdh_sp, signal="pdh")
            actsof = self.sof.integral * sof_slope / \
                self.constants["lock_i_times_slope"] * self.constants["isr_correction"]
            if actdetuning < self.to_detuning(
                    value=self.pdh_max, signal="pdh"):
                actpdh = self.pidpdh.integral * pdh_slope / \
                    self.constants["lock_i_times_slope"] * self.constants["isr_correction"]
            else:
                actpdh = 0
            if sof is None:
                sof = actsof
            if pdh is None:
                pdh = actpdh
            if pdh == 0 and sof == 0:
                sof = 1.0
            steps, delay = self._get_stepdelay(
                output="pid", range=8192.0, duration=time, instructions=instructions)
            if self.constants["verbosity"]:
                print "SOF-SP,I,P,PDH-SP,I,P:"
            for f in linspace(0.0, 1.0, steps, endpoint=True):
                self.lock_opt(detuning=f *
                              detuning +
                              (1.0 -
                               f) *
                              actdetuning, sof=f *
                              sof +
                              (1.0 -
                               f) *
                              actsof, pdh=f *
                              pdh +
                              (1.0 -
                                  f) *
                              actpdh, time=-
                              1)
                if self.constants["verbosity"]:
                    print self.sof.setpoint, self.sof.integral, self.sof.proportional, self.pidpdh.setpoint, self.pidpdh.integral, self.pidpdh.proportional
                sleep(delay)
            return

    def unlock(self, jump=None):
        # unlock and make a coarse jump away from the resonance if desired
        #self.stage = UNLOCKEDSTAGE
        super(Pyrpl_FP, self).unlock(jump=jump)

    def lock(self, detuning=None, laststage=None):
        if laststage is None:
            laststage = self.constants["laststage"]
        if detuning is None:
            if laststage == PDHSTAGE:
                detuning = self.constants["pdh_detuning"]
            elif laststage == SOFSTAGE:
                detuning = self.constants["sof_detuning"]
            elif laststage == DRIFTSTAGE:
                detuning = self.constants["drift_detuning"]

        self.stage = 0  # initialization
        self.unlock()  # unlock such that all controllers are off
        r0, rms = self.get_mean(
            "reflection", avg=0, rms=True)  # measure reflection

        if self.stage == laststage:
            return True
        self.stage += 1  # coarse search
        print "Stage", self.stage, "- Coarse search"
        self.find_coarse()

        if self.stage == laststage:
            return True
        self.stage += 1  # drift into resonance
        print "Stage", self.stage, "- Drift into resonance"
        # *self.get_min_step("coarse") #go on high_voltage side of the resonance
        self.coarse += self.constants["drift_jump"]

        # this is a bugfix. you can erase this paragraph and stuff still works but there is an internal saturation
        # which may limit maximum lock duration
        if laststage >= PDHSTAGE:
            self.pidpdh.reg_integral = self.output
        else:
            self.sof.reg_integral = self.output
        self.output = 0

        timeout = time() + self.constants["drift_time"]
        self.lock_opt(
            detuning=self.constants["drift_detuning"],
            time=0,
            sof=self.constants["drift_factor"])
        while time() < timeout:
            if self.reflection < self.from_detuning(
                    self.constants["drift_detuning"] + rms,
                    signal="reflection"):
                break
            else:
                sleep(self.commdelay)
        self._islocked(verbose=True)
        print "Drift completed"

        if self.stage == laststage:
            self._set_unlockalarm()
            return True
        self.stage += 1  # lock on the fringe
        print "Stage", self.stage, "- Side Of Fringe lock"
        if laststage > self.stage:  # is this an intermediary step? -> in this case we need sof lock within monotonous pdh region
            sofdetuning = 1.0
        else:
            sofdetuning = detuning
        self.lock_opt(detuning=sofdetuning, time=self.constants["sof_time"])
        print "Final sof lock reached"
        self._islocked(verbose=True)

        if self.stage == laststage:
            self._set_unlockalarm()
            return True
        self.stage += 1  # pdh lock

        print "Stage", self.stage, "- PDH lock"
        self.setup_pdh()
        p0 = self.get_mean(signal="pdh")
        self.lock_opt(detuning=0.7, time=self.constants["pdh_time"] * 0.25)
        if self.constants["pdh_offsetcorrection"]:
            offset_pdh = self.constants["offset_pdh"]
        else:
            offset_pdh = 0
        if self.islocked:
            # max([np.abs(pmin-offset_pdh),np.abs(pmax-offset_pdh)])
            self.constants["pdh_max_last"] = p0 - offset_pdh
        self.lock_opt(
            detuning=detuning,
            sof=0.0,
            pdh=1.0,
            time=self.constants["pdh_time"] *
            0.75)
        print "Final pdh lock reached. Lock completed"
        self._set_unlockalarm()
        return self._islocked(verbose=True)

    def relock(self, detuning=None, sof=0, pdh=0):
        """
        Standard function for locking the cavity. Unlike lock, this function does not unlock the cavity if this is
        not necessary. If a relock is necessary, the last parameters are used, unless a change is specified in the
        parameters. If no last parameters are found, it cals lock without argument.
        Parameters
        --------------
        detuning: the desired detuning in units of cavity bandwidths. None goes back to last detuning. If t
        sof: the desired sof gain factor.
        pdh: the desired pdh gain factor.
        """
        # make sure sof and pdh yield a good lock
        if self.laser_off:
            return False
        if self.stage == -1:  # cavity has never been locked
            self.lock(detuning=detuning)
        laststage = self.stage
        if sof == 0 and pdh == 0:
            if laststage >= PDHSTAGE:
                sof, pdh = 0, 1
            else:
                sof, pdh = 1, 0
        if self.islocked:
            self.lock_opt(detuning=detuning, sof=sof, pdh=pdh,
                          time=self.constants["relocktime"])
        for i in range(5):
            print "Relock iteration:", i
            if self.laser_off:
                return False
            if self.islocked:
                break
            else:
                self.lock(detuning=detuning, laststage=laststage)
                self.lock_opt(
                    detuning=detuning,
                    sof=sof,
                    pdh=pdh,
                    time=self.constants["relocktime"])
                continue
        if not self.waslocked:
            self._set_unlockalarm()
        return self.islocked

    def _raw_lock(
            self,
            drift_sp=None,
            drift_i=None,
            drift_p=None,
            drift_aux_i=None,
            drift_aux_p=None,
            sof_sp=None,
            sof_i=None,
            sof_p=None,
            sof_aux_i=None,
            sof_aux_p=None,
            pdh_sp=None,
            pdh_i=None,
            pdh_p=None,
            pdh_aux_i=None,
            pdh_aux_p=None,
            laststage=None):
        """Earlier version of lock, still works
        This function defines explicitely the gains and setpoints to be used in each stage of the lock sequence
        There is no automatic gain optimization which renders manual tuning sometimes more comfortable
        """
        if laststage is None:
            laststage = self.constants["laststage"]
        self.stage = 0  # initialization
        while self.islocked:
            self.unlock()  # unlock such that all controllers are off
        r0, rms = self.get_mean(
            "reflection", avg=0, rms=True)  # measure reflection

        if self.stage == laststage:
            return
        self.stage += 1  # coarse search
        print "Stage", self.stage, "- Coarse search"
        self.find_coarse()

        if self.stage == laststage:
            return
        self.stage += 1  # drift into resonance
        print "Stage", self.stage, "- Drift into resonance"
        # *self.get_min_step("coarse") #go on high_voltage side of the resonance
        self.coarse += self.constants["drift_jump"]
        rd = self.constants["dark_reflection"]
        th = self.constants["lock_upper_threshold"]
        if drift_sp is None:
            drift_sp = self.constants["drift_sp"]
        # setpoint is upper threshold for considering the cavity locked
        drift_sp = (r0 - rd) * drift_sp + rd
        self.sof.setpoint = r0 - rms
        #drift_sp = (r0-rd)*drift_sp+rd
        #self.pid.setpoint = drift_sp
        print "Drift setpoint set to", self.sof.setpoint
        if drift_i is None:
            drift_i = self.constants["drift_i"]
        if drift_p is None:
            drift_p = self.constants["drift_p"]
        if drift_aux_i is None:
            drift_aux_i = self.constants["drift_aux_i"]
        if drift_aux_p is None:
            drift_aux_p = self.constants["drift_aux_p"]
        self.sof.integral = drift_i
        self.sof.proportional = drift_p
        self.sof.reset = False

        if "lock_aux_output" in self.constants and self.constants[
                "lock_aux_output"] != 0:
            self.sof_aux.setpoint = self.sof.setpoint
            self.sof_aux.integral = drift_aux_i
            self.sof_aux.proportional = drift_aux_p
            self.sof_aux.reset = False
        timeout = time() + self.constants["drift_time"]
        while time() < timeout:
            if self.reflection < r0 - 3 * rms:  # drift has worked!
                break
            else:
                sleep(self.commdelay)
        self.sof.setpoint = drift_sp
        if "lock_aux_output" in self.constants and self.constants[
                "lock_aux_output"] != 0:
            self.sof_aux.setpoint = self.sof.setpoint
        self._islocked(verbose=True)

        if self.stage == laststage:
            self._set_unlockalarm()
            return
        self.stage += 1  # lock on the fringe
        print "Stage", self.stage, "- Side Of Fringe lock"
        if sof_sp is None:
            sof_sp = self.constants["sof_sp"]
        sof_sp = sof_sp * (r0 - rd) + rd
        if sof_i is None:
            sof_i = self.constants["sof_i"]
        if sof_p is None:
            sof_p = self.constants["sof_p"]

        if not self.sof_aux is None:
            if sof_aux_i is None:
                sof_aux_i = self.constants["sof_aux_i"]
            if sof_aux_p is None:
                sof_aux_p = self.constants["sof_aux_p"]
            extrainstructions = 3

        # if sof_time is None:
        sof_time = self.constants["sof_time"]
        # linearly ramp up all signals
        steps, delay = self._get_stepdelay(
            output="pid", range=sof_sp - drift_sp, duration=sof_time, instructions=3 + extrainstructions)
        print "Approaching sof setpoint ", sof_sp, "in", steps, "steps of", delay * 1e3, "ms"

        for f in linspace(0.0, 1.0, steps, endpoint=True):
            self.sof.setpoint = np.round(f * sof_sp + (1.0 - f) * drift_sp)
            self.sof.integral = np.round(f * sof_i + (1.0 - f) * drift_i)
            self.sof.proportional = np.round(f * sof_p + (1.0 - f) * drift_p)
            if not self.sof_aux is None:
                self.sof_aux.setpoint = self.sof.setpoint
                self.sof_aux.integral = np.round(
                    f * sof_aux_i + (1.0 - f) * drift_aux_i)
                self.sof_aux.proportional = np.round(
                    f * sof_aux_p + (1.0 - f) * drift_aux_p)
            if self.constants["verbosity"]:
                print "SP,I,P:", self.sof.setpoint, self.sof.integral, self.sof.proportional
            sleep(delay)
        print "Final sof lock reached"
        self._islocked(verbose=True)

        if self.stage == laststage:
            self._set_unlockalarm()
            return
        self.stage += 1  # pdh lock

        print "Stage", self.stage, "- PDH lock"
        self.setup_pdh()
        self.pidpdh.reset = False
        if "lock_aux_output" in self.constants and self.constants[
                "lock_aux_output"] != 0:
            self.pidpdh_aux.reset = False
            extrainstructions += 3
        else:
            self.pidpdh_aux = None

        # estimate pdh setpoint equivalent
        p0, prms = self.get_mean("pdh", avg=0, rms=True)
        if pdh_sp is None:
            pdh_sp = self.constants["pdh_sp"]
        if self.constants["pdh_offsetcorrection"]:
            pdh_sp += self.constants["offset_pdh"]
        if pdh_i is None:
            pdh_i = self.constants["pdh_i"]
        if pdh_p is None:
            pdh_p = self.constants["pdh_p"]
        if pdh_aux_i is None:
            pdh_aux_i = self.constants["pdh_aux_i"]
        if pdh_aux_p is None:
            pdh_aux_p = self.constants["pdh_aux_p"]
        pdh_time = self.constants["pdh_time"]
        steps, delay = self._get_stepdelay(output="pid", range=max([abs(p0 - pdh_sp), abs(pdh_i), abs(
            pdh_p), abs(sof_i), abs(sof_p)]), duration=pdh_time, instructions=6 + extrainstructions)
        if pdh_i * sof_i < 0 or pdh_p * sof_p < 0:
            inverted = -1
        else:
            inverted = 1
        if p0 * inverted < 0:
            print "Please check that the sign of PDH gain is correct! It is probably wrong..."
        print "Approaching pdh setpoint ", pdh_sp, "from", p0, "in", steps, "steps of", delay * 1e3, "ms"
        for f in linspace(0.0, 1.0, steps, endpoint=True):
            self.pidpdh.setpoint = np.round(f * pdh_sp + (1.0 - f) * p0)
            self.pidpdh.integral = np.round(f * pdh_i)
            self.pidpdh.proportional = np.round(f * pdh_p)
            self.sof.setpoint = np.round((1.0 - f) * sof_sp)
            self.sof.integral = np.round((1.0 - f) * sof_i)
            self.sof.proportional = np.round((1.0 - f) * sof_p)
            if not self.pidpdh_aux is None:
                self.pidpdh_aux.setpoint = self.pidpdh.setpoint
                self.pidpdh_aux.integral = np.round(f * pdh_aux_i)
                self.pidpdh_aux.proportional = np.round(f * pdh_aux_p)
                self.sof_aux.setpoint = self.sof.setpoint
                self.sof_aux.integral = np.round((1.0 - f) * sof_aux_i)
                self.sof_aux.proportional = np.round((1.0 - f) * sof_aux_p)
            if self.constants["verbosity"]:
                print "SP,I,P:", self.pidpdh.setpoint, self.pidpdh.integral, self.pidpdh.proportional
            sleep(delay)
        print "Final pdh lock reached. Lock completed"
        self._set_unlockalarm()
        return self._islocked(verbose=True)

    @property
    def pdhon(self):
        self.iq.iq_channel = 0
        return (self.iq.iq_constantgain != 0)

    def _setup_pdh(self):
        if (self.constants["pdh_input"] == 3):  # means internal demodulation
            self.iq.iq_set_advanced(
                channel=0,
                frequency=self.constants["pdh_frequency"],
                phase=self.constants["pdh_phase"],
                bandwidth=self.constants["pdh_bandwidth"],
                constantgain=self.constants["pdh_amplitude"],
                gain=0,
                accoupled=True,
                acbandwidth=1000.0,
                inputport=self.constants["rf_input"],
                outputport=self.constants["rf_output"],
            )
            self.iq.iq_i0_factor = np.round(
                self.constants["pdh_factor"] *
                self.constants["pdh_referencereflection"] /
                (
                    self.constants["offres_reflection"] -
                    self.constants["dark_reflection"]))
            if self.constants["reflection_input"] == 1:
                # need to find the free pid controllers (the ones not used for
                # sof locking)
                free_input = 2
            else:
                free_input = 1
            self.pidpdh = self._get_pid(
                input=free_input, output=self.constants["lock_output"])
            self.pidpdh.inputiq = True
            if self.constants["lock_aux_output"] != 0:
                self.pidpdh_aux = self._get_pid(
                    input=free_input, output=self.constants["lock_aux_output"])
                self.pidpdh_aux.inputiq = True
        else:  # means demodulation is performed externally. Send analog pdh signal directly to pid controller
            self.pidpdh = self._get_pid(
                input=self.constants["pdh_input"],
                output=self.constants["lock_output"])
            self.pidpdh.inputiq = False
            if self.constants["lock_aux_output"] != 0:
                self.pidpdh_aux = self._get_pid(
                    input=self.constants["pdh_input"],
                    output=self.constants["lock_aux_output"])
                self.pidpdh_aux.inputiq = False
        return

    def _disable_pdh(self):
        if (self.constants["pdh_input"] == 3):  # means internal demodulation
            self.iq.iq_channel = 0
            self.iq.iq_constantgain = 0
        return

    def optimize_pdh(
            self,
            start=0,
            stop=360,
            steps=37,
            sweepamplitude=0.3,
            sweepfrequency=10):
        fgenphase = None
        c1 = self.find_coarse()
        c2 = self.find_coarse()
        self.coarse = (c1 + c2) / 2.0
        self.sweep_coarse(
            amplitude=sweepamplitude,
            frequency=sweepfrequency,
            offset=self.coarse)
        self.setup_pdh()
        self.iq.iq_channel = 0
        self.iq.iq_scope_select = 0
        d = self.constants["dark_reflection"]
        r = self.constants["offres_reflection"]
        threshold = self.constants["find_coarse_upper_threshold"] * (r - d) + d
        if self.constants["reflection_input"] == 1:
            self.s.quadrature_on_ch1 = False
            self.s.quadrature_on_ch2 = True
            trigger_source = 2
            self.s.threshold_ch1 = threshold
        # print "Remember to subtract 90 degrees from the final phase before
        # putting it in the dictionary"
            phasecorrection = 90  # since we observe quadrature2 instead of quadrature1,
            # we must apply a phase shift to correct for this quadrature swapping
            # because the error signal will be based on quadrature 1
        else:
            self.s.quadrature_on_ch1 = True
            self.s.quadrature_on_ch2 = False
            trigger_source = 4
            self.s.threshold_ch2 = threshold
            phacecorrection = 0

        self.s.setup(
            frequency=self.f.frequency *
            self.constants["cavity_finesse"] /
            30.0,
            trigger_source=self.s.trigger_source,
            dacmode=True)
        delay = 1.0 / self.s.frequency

        cc = CurveDB()
        cc.name = "PDH phase optimisation"
        cc.params.update(self.constants)
        if cc.params["fpgadir"] is None:
            cc.params.pop("fpgadir")
        cc.save()
        ccref = CurveDB()
        ccref.name = "relfection curves"
        ccref.save()
        cc.add_child(ccref)
        ccpdh = CurveDB()
        ccpdh.name = "pdh curves"
        ccpdh.save()
        cc.add_child(ccpdh)

        phases = np.linspace(start, stop, steps)
        amplitudes1 = phases * 0
        amplitudes2 = phases * 0
        for i, p in enumerate(phases):
            if self.constants["verbosity"]:
                print "Measuring signals for phase=", p
            self.constants["pdh_phase"] = p - phasecorrection
            self.setup_pdh()
            self.s.arm(trigger_source=trigger_source, trigger_delay=0.5)
            while True:
                if self.s.trigger_source == 0:
                    # make sure all curves are taken on ascending slope of
                    # function generator
                    scopetrigphase = self.f.scopetrigger_phase
                    if fgenphase is None:  # if it was not defined
                        fgenphase = (scopetrigphase - 90.0) % 180.0
                        print "fgenphase has been auto-set to", fgenphase, "degrees"
                    if (fgenphase <= scopetrigphase) and (
                            scopetrigphase < fgenphase + 180.0):
                        break
                    else:
                        self.s.arm(
                            trigger_source=trigger_source,
                            trigger_delay=0.5)
                        continue
                sleep(delay)
            c1, c2 = self.scope_curves(name_prefix="phase=" + str(p) + " ")
            if self.constants["reflection_input"] == 1:
                cr = c1
                cp = c2
            else:
                cr = c2
                cp = c1
            ccref.add_child(cr)
            ccpdh.add_child(cp)
            cp.params["scopetrigphase"] = scopetrigphase
            cp.save()
            cut = int(np.round(float(len(cp.data)) / 2.))
            d1 = cp.data.iloc[:cut]
            d2 = cp.data.iloc[cut:]
            amplitudes1[i] = d1[d1.abs().argmax()]
            amplitudes2[i] = d2[d2.abs().argmax()]

        c1 = CurveDB.create(phases, amplitudes1)
        c1.name = "maximum pdh amplitude1 vs phase"
        c1.save()
        cc.add_child(c1)
        c2 = CurveDB.create(phases, amplitudes2)
        c2.name = "maximum pdh amplitude2 vs phase"
        c2.save()
        cc.add_child(c2)
        optphase = phases[amplitudes1.argmin()]
        optgain = 1.0 / amplitudes1.max() * self.constants["pdh_factor"]
        #self.constants["pdh_phase"] = optphase
        #self.constants["pdh_factor"] = optgain
        self.constants["pdh_phase"] = optphase
        self.setup_pdh()

        print "Optimal parameters recommendation:"
        print "pdh_phase:  ", optphase
        print "pdh_factor: ", optgain
        print "current pdh_max", amplitudes1.max() * 8192.0

    def align_acoustic(
            self,
            normalfrequency=20000.0,
            sosfrequency=3000.,
            verbose=True):
        from sound import sinus
        while True:
            r = self.relative_reflection
            if verbose:
                print r
            if r > 0.8:
                df = sosfrequency
                sinus(df, 0.02)
                sinus(df, 0.02)
                sinus(df, 0.02)
                sleep(0.1)
                sinus(df, 0.1)
                sinus(df, 0.1)
                sinus(df, 0.1)
                sleep(0.1)
                sinus(df, 0.02)
                sinus(df, 0.02)
                sinus(df, 0.02)
                self.relock()
            else:
                sinus(normalfrequency * r, 0.05)