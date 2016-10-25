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

from __future__ import print_function
from time import sleep, time
import math
import numpy
import numpy as np
import os
import pandas
import matplotlib.pyplot as plt
import sys
import os
from . import iir
import logging
from collections import OrderedDict
from shutil import copyfile

from .redpitaya import RedPitaya
from .curvedb import CurveDB
from .memory import MemoryTree
from .model import Model
from .signal import *
from .models import *
#from .gui.pyrpl_gui import PyrplGui

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
pyrpl.py - high-level lockbox functionality

A lockbox is a device that converts a number of input signals into a number of
output signals suitable to stabilize a physical system in a desired state. This
task is generally divided into two steps:
1) bring the system close the desired state where it can be linearized
2) keep it there using linear control.

The task is further divided into several subtasks:
0a) Condition the input signals so that they are suitable for the next steps
 - offset removal
 - input filters
 - demodulation / lockin
 - inversion
0b) Estimate the system state from the past and present history of input and
output signals.
0c) Build a filter for the output signals such that they can be conveniently
addressed with higher-level lockbox logic.

1) As above: apply reasonable action to the outputs to approach the system to
the desired state. We generally call this the 'search' step.
- provide a number of algorithms/recipes to do this

2) As above: Turn on linear feedback. We call this the 'lock' step.
- connect the input signals with appropriate gain to the outputs
- the gain depends on the state of the system, so internal state representation
will remain useful here

This naturally divides the lockbox object into 3 subcomponents:
a) inputs
b) internal model
c) outputs

which will be interconnected by the algorithms that come with the model and
make optimal use of the available inputs and outputs. The job of the
configuration file is to provide a maximum of information about the inputs,
outputs and the physical system (=internal model) so that the lockbox is
effective and robust. The lockbox will usually require both a coarse-tuning
and an optimization step for optimum performance, which will both adjust the
various parameters for the best match between model and real system.

Let's make this reasoning more clear with an example:

A Fabry-Perot cavity is to be locked near resonance using a PDH scheme. The
incident laser beam goes through a phase modulator. The cavity contains a piezo
with estimated bandwidth 10 kHz (appearance of first resonance) and
a displacement of 350 nm/V that goes into the piezo amplifier. To limit the
effect of amplifier noise, we have inserted an RC lowpass between amplifier and
piezo with a cutoff frequency of 100 Hz. The laser contains another piezo with
estimated bandwidth of 50 kHz that changes the laser frequency by 5 MHz/V. An
RC filter provides a lowpass with 1kHz cutoff. Finally, the cavity can be tuned
through its temperature with a bandwidth slower than 0.1 Hz. We estimate from
thermal expansion coefficients that 1 V to the Peltier amplifier leading to 3 K
heating of the cavity spacer should lead to 30ppm/K*20cm*3K/V = 18 micron/V
length change. Both reflection and transmission of the cavity are available
error signals. The finesse of the cavity is 5000, and therefore there are
large regions of output signals where no useful error signal can be obtained.

We first generate a clean list of available inputs and outputs and some
parameters of the cavity that we know already:

inputs:
  in1:
    reflection
  in2:
    transmission
  # also possible
  # in2: pdh # for externally generated pdh
outputs:
  out1:
    # we insert a bias-T with separation frequency around 1 MHz behind out1
    # this allows us to use the fast output for both the piezo and PDH
    modulator:
      amplitude: 0.1
      frequency: 50e6
    cavitypiezo:
      # piezo specification: 7 micron/1000V
      # amplifier gain: 50
      # therefore effective DC gain: 350nm/V
      m_per_V: 350e-9
      bandwidth: 100.0
  out2:
    laserpiezo:
      Hz_per_V: 5e6
      bandwidth: 1e3
  pwm1:
    temperature:
      m_per_V: 18e-6
      bandwidth: 0.1
model:
  type: fabryperot
  wavelength: 1064e-9
  finesse: 5000
  # round-trip length in m (= twice the length for ordinary Fabry-Perot)
  length: 0.72
  lock: # lock methods in order of preferrence
    order:
      pdh
      reflection
      transmission
    # when approaching a resonance, we can either abruptly jump or smoothly
    # ramp from one error signal to another. We specify our preferrence with
    # the order of keywords after transition
    transition: [ramp, jump]
    # target value for our lock. The API provides many ways to adjust this at
    # runtime
    target:
      detuning: 0
  # search algorithms to use in order of preferrence, as available in model
  search:
    drift
    bounce

Having selected fabryperot as modeltype, the code will automatically search
for a class named fabryperot in the file model.py to provide for the internal
state representation and all algorithms. You can create your own model by
adding other classes to this file, or by inheriting from existing ones and
adding further functionality. The naming of all other configuration parameters
is linked to the model, since all functionality that makes use of these para-
meters is implemented there. Another very often used model type is
"interferometer". The only difference is here that

"""


#def pyrpl(config="default"):
#    """ returns a Pyrpl object based on configfile 'config' """
#    c = MemoryTree(os.path.join(os.path.join(os.path.dirname(__file__),
#                                             "config"), config + ".yml"))
#    model = getmodel(c.model.modeltype)
#    return type("Pyrpl", (Lockbox, model), {})(config=config)


def getmodel(modeltype):
    try:
        m = globals()[modeltype]
        if type(m) == type:
            return m
    except KeyError:
        pass
    # try to find a similar model with lowercase spelling
    for k in globals():
        if k.lower() == modeltype.lower():
            m = globals()[k]
            if type(m) == type:
                return m
    logger.error("Model %s not found in model definition file %s",
                 modeltype, __file__)


class Lockbox(object):
    """generic lockbox object, no implementation-dependent details here

    A lockbox has a MemoryTree to remember information. The memoryTree
    furthermore defines one model of the physical system that is controlled.

    Parameters
    ----------
    config: str
        Name of the config file. No .yml extension is needed. The file
        should be located in the config directory.
    source: str
        If None, it is ignored. Else, the file 'source' is taken as a
        template config file and copied to 'config' if that file does
        not exist.
    """
    _configdir = os.path.join(os.path.dirname(__file__), "config")
    _signalinit = {"inputs": Signal, "outputs": Signal}, {}

    def _getpath(self, filename):
        p, f = os.path.split(filename)
        if not p:  # no path specified -> search in configdir
            filename = os.path.join(self._configdir, filename)
        if not filename.endswith(".yml"):
            filename = filename + ".yml"
        return filename

    def __init__(self, config="default", source=None):
        # logger initialisation
        self.logger = logging.getLogger(name=__name__)
        config = self._getpath(config)
        if source is not None:
            if os.path.isfile(config):
               self.logger.warning("Config file already exists. Source file "
                                   +"specification is ignored")
            else:
                copyfile(getpath(source), config)
        # configuration is retrieved from config file
        self.c = MemoryTree(config)
        # set global logging level if specified in config file
        self._setloglevel()
        # make input and output signals
        self._makesignals()
        # find and setup the model
        self.model = getmodel(self.c.model.modeltype)(self)
        self.model.setup()
        # create shortcuts for public model functions
        for fname in self.model.export_to_parent:
            self.__setattr__(fname, self.model.__getattribute__(fname))
        self.logger.info("Lockbox '%s' initialized!", self.c.general.name)
        self.persistent_props = [] # list of properties to monitor
        self.timer_persistent_properties = QtCore.QTimer()
        self.timer_persistent_properties.setInterval(1000)
        self.timer_persistent_properties.timeout.connect(self.store_properties)
        self.timer_persistent_properties.start()

    def _setloglevel(self):
        """ sets the log level to the one specified in config file"""
        try:
            level = self.c.general.loglevel
            loglevels = {"notset": logging.NOTSET,
                         "debug": logging.DEBUG,
                         "info": logging.INFO,
                         "warning": logging.WARNING,
                         "error": logging.ERROR,
                         "critical": logging.CRITICAL}
            level = loglevels[level]
        except:
            pass
        else:
            logging.getLogger(name='pyrpl').setLevel(level)

    def _makesignals(self, *args, **kwargs):
        """ Instantiates all signals from config file.
        Optional arguments are passed to the signal class initialization. """
        signalclasses, signalparameters = self._signalinit
        for signaltype, signalclass in signalclasses.items():
            # generalized version of: self.inputs = [reflection, transmission]
            signaldict = OrderedDict()
            self.__setattr__(signaltype, signaldict)
            for k in self.c[signaltype].keys():
                self.logger.debug("Creating %s signal %s...", signaltype, k)
                # generalization of:
                # self.reflection = Signal(self.c, "inputs.reflection")
                signal = signalclass(self.c,
                                     signaltype+"."+k,
                                     **signalparameters)
                signaldict[k] = signal
                self.__setattr__(k, signal)

    @property
    def signals(self):
        """ returns a dictionary containing all signals, i.e. all inputs and
        outputs """
        sigdict = dict()
        signals, _ = self._signalinit
        for s in signals.keys():
            sigdict.update(self.__getattribute__(s))
        return sigdict

    def _fastparams(self):
        """ implement custom fastparams here """
        return dict()

    def get_offset(self):
        """ Execute this function to record the offsets for all input
        signals. If signal.offset_subtraction is true in the config file,
        the signal value 0 will from then on correspond to the measured
        offset. Before any locking configuration, this function should be
        executed in order to take the analog offsets of redpitaya inputs
        into account. """
        for input in self.inputs.values():
            input.get_offset()

    def _params(self):
        """ implement custom params here """
        params = {}
        params.update(self._fastparams())
        return params

    def _deriveddict(self, original, prefix="", postfix=""):
        """ adds a pre- and postfix to keys of original dict and flattens hierarchical dicts"""
        result = {}
        for key in original.keys():
            if isinstance(original[key], dict):
                result.update(self._deriveddict(original[key],
                                                prefix=prefix+key+".",
                                                postfix=postfix))
            else:
                result[prefix+key+postfix] = original[key]
        return result

    def fastparams(self, postfix=""):
        """ returns a dict with fastparams as defined in _fastparams. This
        is typically of interest when the significant lockbox settings are
        to be saved along with some acquired data. """
        return self._deriveddict(self._fastparams(), postfix=postfix)

    def params(self, postfix=""):
        """returns a dict with params as defined in _params
        and all configuration data. This is intended to produce a record of
        all lockbox settings at the moment of acquisition. """
        params = self._params()
        params.update(self._deriveddict(self.c._data, prefix="c."))
        return self._deriveddict(params, postfix=postfix)

    def register_persistent_properties(self,
                                       module,
                                       name,
                                       properties,
                                       retrieve_existing=True):
        """
        Stores the properties of an object in a config file for persistence
        over several sessions.

        module: object with some properties that we would like to monitor
        name: name of the section to use in the config file
        properties: list of properties (by name) to monitor
        retrieve_existing: if values exist in the store, retrieves the
        existing ones
        """

        self.persistent_props.append((module, name, properties))
        if retrieve_existing:
            try:
                dic = self.c[name]
            except KeyError:
                pass
            else:
                for prop in properties:
                    if prop in dic:
                        print("setting ", module, prop, dic[prop])
                        setattr(module, prop, dic[prop])

    def store_properties(self):
        for module, name, properties in self.persistent_props:
            new_dic = OrderedDict()
            for prop in properties:
                new_dic[prop] = getattr(module, prop)
            try:
                dic = self.c[name]
            except KeyError:
                self.c[name] = {}
                dic = {}
            if dic!=new_dic:
                for key, val in new_dic.iteritems():
                    getattr(self.c, name)[key] = val # somehow self.c[name][key]
                    #doesn't work


class Pyrpl(Lockbox):
    """
    The fundamental Python RedPitaya Lockbox API object. After having
    created your configuration file "myconfig.yml", create the lockbox
    object with lockbox = Pyrpl("myconfig"). Please refer to the
    tutorial for a much more thorough discussion of the Pyrpl class, because
    its most useful attributes are created dynamically depending on the
    configuration file settings.

    Parameters
    ----------
    config: str
        The filename of the config file. No .yml extension is needed. By
        default, Pyrpl will search the config file in the config
        subdirectory of the pyrpl module.
    source: str
        If you specify a source filename, Pyrpl will copy the source to
        the filename specified through the config parameter if that
        file does not exist yet. If the config parameter points to a
        valid file, the source argument is ignored.
    """
    def __init__(self, config="default", source=None):
        # we need the configuration for RedPitaya initialization
        self.c = MemoryTree(os.path.join(self._configdir, config+".yml"))
        # set loglevel if specified in file
        self._setloglevel()
        # initialize RedPitaya object with the configured parameters
        self.rp = RedPitaya(**self.c.redpitaya._dict)
        # signal class and optional arguments are passed through this argument
        self._signalinit = {"inputs": RPSignal, "outputs": RPOutputSignal}, \
                           {"parent": self,
                            "restartscope": self._setupscope}
        # Lockbox initialization
        super(Pyrpl, self).__init__(config=config)
        # initialize scope with predefined parameters
        if self.c.redpitaya.gui:
            self._startgui()

    def _startgui(self):
        from .gui import RedPitayaGui
        if not isinstance(self.rp, RedPitayaGui):
            self.rp.__class__ = RedPitayaGui
            self.logger.debug("Seting up gui")
            self.rp.setup_gui()
            self.rp.gui()
        self.pyrpl_model = PyrplGui(self)
        self.rp.add_dock_widget(self.pyrpl_model, "Pyrpl model")

        self.set_window_position()
        self.timer_save_gui_params = QtCore.QTimer()
        self.timer_save_gui_params.setInterval(1000)
        self.timer_save_gui_params.timeout.connect(self._save_window_position)
        self.timer_save_gui_params.timeout.connect(self.save_gui_params)
        self.timer_save_gui_params.start()

        self._setupscope()
        self.rp.main_window.setWindowTitle(self.c.general.name)

    def save_gui_params(self):
        pass # not sure if params should be autosaved or not ...
        #for module in self.rp.all_gui_modules:
        #    dic = module.get_state()
        #    self.c[module.name] = dic

    def _setupscope(self):
        if "scope" in self.c._dict:
            self.rp.scope.setup(**self.c.scope._dict)
        if "sccopegui" in self.c._dict:
            if self.c.scopegui.auto_run_continuous:
                r.rp.scope_widget.run_continuous()

    def _save_window_position(self):
        if self.c["dock_positions"]!=bytes(self.rp.main_window.saveState()):
            self.c["dock_positions"] = bytes(self.rp.main_window.saveState())
        try:
            _ = self.c.scopegui
        except KeyError:
            self.c["scopegui"] = dict()
        try:
            if self.c.scopegui["coordinates"]!=self.rp.window_position:
                self.c.scopegui["coordinates"] = self.rp.window_position
        except:
            self.logger.warning("Gui is not started. Cannot save position.")

    def set_window_position(self):
        if "dock_positions" in self.c._keys():
            if not self.rp.main_window.restoreState(self.c.dock_positions):
                self.logger.warning("Sorry, " + \
                    "there was a problem with the restoration of Dock positions")
        try:
            coordinates = self.c["scopegui"]["coordinates"]
        except KeyError:
            coordinates = [0, 0, 800, 600]
        try:
            self.rp.window_position = coordinates
            self._lock_window_position()
        except:
            self.logger.warning("Gui is not started. Cannot save position.")

class Trash(object):

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

    # interface for bodeplot_susceptibility5

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

class Trash_Pyrpl_FP(Pyrpl):
    def find_coarse(self, start=0.0, stop=1.0):
        """ finds the coarse offset of a resonance in range """
        # define search parameters
        step = 0.5 * self._get_min_step("coarse")
        stopinterval = self.constants["coarse_searchprecision"]  # 2.0*step

        delay = 1.0 / self.constants["coarse_bandwidth"]
        initial_delay = min([10.0, 10 * delay])

        searchtime = self.constants["coarse_searchtime"]

        print ("Waiting for coarse value to settle...")
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
            print ("Coarse threshold set to %d" % self.s.threshold_ch2)
            trigger_source = 5
        elif self.constants["reflection_input"] == 1:
            self.s.threshold_ch1 = find_coarse_threshold
            print ("Coarse threshold set to %d" % self.s.threshold_ch1)
            trigger_source = 3

        print ("Starting resonance search...")
        for act_iteration in range(
                self.constants["find_coarse_max_iterations"]):
            # upwards search
            self.s.arm(trigger_source=trigger_source)
            print ("sweeping upwards...")
            steps, delay = self._get_stepdelay(
                "coarse", stop - start, searchtime)
            for c in np.linspace(start, stop, steps):
                if (self.s.trigger_source == 0):
                    """resonance passed in positive direction"""
                    print ("Passed upwards at %.4f" % c)
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
            print ("sweeping downwards...")
            steps, delay = self._get_stepdelay(
                "coarse", stop - start, searchtime)
            for c in np.linspace(stop, start, steps):
                if (self.s.trigger_source == 0):
                    """resonance passed in negativedirection"""
                    print ("Passed downwards at %.4f" % c)
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
                print ("Resonance located at %.4f" % self.coarse)
                self.scope_reset()
                return self.coarse
        # if we arrive here, the search must have failed...
        self.scope_reset()
        return None

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
            print ("Relock iteration:", i)
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
                print ("Measuring signals for phase=", p)
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
                        print ("fgenphase has been auto-set to", fgenphase, "degrees")
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

        print ("Optimal parameters recommendation:")
        print ("pdh_phase:  ", optphase)
        print ("pdh_factor: ", optgain)
        print ("current pdh_max", amplitudes1.max() * 8192.0)

    def align_acoustic(
            self,
            normalfrequency=20000.0,
            sosfrequency=3000.,
            verbose=True):
        from sound import sinus
        while True:
            r = self.relative_reflection
            if verbose:
                print (r)
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