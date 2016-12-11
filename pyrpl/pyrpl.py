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

import logging
import os
from shutil import copyfile

from .widgets.pyrpl_widget import PyrplWidget

from . import software_modules
from .memory import MemoryTree
from .redpitaya import RedPitaya
from .pyrpl_utils import get_unique_name_list_from_class_list

## Something has to be done with this docstring... I would like to wait for lockbox to be implemented before doing it...
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


class Pyrpl(object):
    """
    Higher level object, in charge of loading the right hardware and software
    module, depending on the configuration described in a config file.

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

    def _getpath(self, filename):
        p, f = os.path.split(filename)
        if not p:  # no path specified -> search in configdir
            filename = os.path.join(self._configdir, filename)
        if not filename.endswith(".yml"):
            filename = filename + ".yml"
        return filename

    def _setloglevel(self):
        """ sets the log level to the one specified in config file"""
        try:
            level = self.c.pyrpl.loglevel
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

    def __init__(self, config="default", source=None):
        # logger initialisation
        self.logger = logging.getLogger(name=__name__)
        config = self._getpath(config)
        if source is not None:
            if os.path.isfile(config):
                self.logger.warning("Config file already exists. Source file "
                                    + "specification is ignored")
            else:
                copyfile(self._getpath(source), config)
        # configuration is retrieved from config file
        self.c = MemoryTree(config)
        # set global logging level if specified in config file
        self._setloglevel()
        # configuration is retrieved from config file
        self.c = MemoryTree(config)
        # set global logging level if specified in config file
        self._setloglevel()

        # Eventually, could become optional...
        # initialize RedPitaya object with the configured parameters
        if 'redpitaya' in self.c._keys():
            self.rp = RedPitaya(config=self.c, **self.c.redpitaya._dict)
        else:
            self.rp = None

        self.software_modules = []
        self.load_software_modules()

        for module in self.hardware_modules:  # setup hardware modules with config file keys
            if module.owner is None: # (only modules that are not slaved by software modules)
                # if module.name in self.c._keys():
                    try:
                        module.load_setup_attributes() # **self.c[module.name])
                    except BaseException as e:
                        self.logger.warning('Something went wrong when loading attributes of module "%s"'%module.name)
        if self.c.pyrpl.gui:
            widget = self.create_widget()
            widget.show()

    def load_software_modules(self):
        """
        load all software modules defined as root element of the config file.
        """
        soft_mod_names = self.c.pyrpl.modules#[mod for mod in self.c._keys() if not mod in ("pyrpl", "redpitaya")]
        soft_mod_names = ['AsgManager',
                          'IqManager',
                          'PidManager',
                          'ScopeManager',
                          'IirManager'] + soft_mod_names
        module_classes = [getattr(software_modules, cls_name) for cls_name in soft_mod_names]
        module_names = get_unique_name_list_from_class_list(module_classes)
        for cls, name in zip(module_classes, module_names):
            # ModuleClass = getattr(software_modules, module_name)
            module = cls(self, name)
            try:
                module.load_setup_attributes() # attributes are loaded but the module is not "setup"
            except BaseException as e:
                self.logger.warning("problem loading attributes of module " + name + "\n" + str(e))
            """
            if module.name in self.c._keys():
                kwds = self.c[module.name]
                if kwds is None:
                    kwds = dict()
                module.load_setup_attributes(**kwds) # first, setup software modules...
            """
            setattr(self, module.name, module) # todo --> use self instead
            self.software_modules.append(module)

    @property
    def hardware_modules(self):
        """
        List of all hardware modules loaded in this configuration.
        """
        if self.rp is not None:
            return list(self.rp.modules.values())
        else:
            return []

    @property
    def modules(self):
        return self.hardware_modules + self.software_modules

    def create_widget(self):
        """
        Creates the top-level widget
        """

        self.widget = PyrplWidget(self)
        return self.widget

