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

from pyrpl.software_modules import Module
import logging
from .signal import logger
import os

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

class Lockbox(Module):
    """generic lockbox object, no implementation-dependent details here

    A lockbox defines one model of the physical system that is controlled."""


    def __init__(self, rp):
        self.logger = logging.getLogger(name=__name__)
        self.rp = rp
        # make input and output signals
        self._makesignals()
        # find and setup the model
        self.model = getmodel(self.c.model.modeltype)(self)
        self.model.setup()

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