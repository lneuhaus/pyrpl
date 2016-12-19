from pyrpl.modules import SoftwareModule
from .signals.input import InputDirect, InputPdh
from pyrpl.attributes import FloatProperty

import numpy as np


class Model(SoftwareModule):
    """
    A physical model allowing to relate inputs in V into a physical parameter in *unit*. Several units are actually
    available to describe the model parameter (e.g. 'm', 'MHz' for detuning).
    inputs is a list of signal.Input objects (or derived classes such as signal.PDH)
    """
    section_name = 'model'
    parameter_name = ""
    units = []  # possible units to describe the physical parameter to control e.g. ['m', 'MHz']
    input_cls = [] # list of input signals that can be implemented


class InterferometerPort1(InputDirect):
    name = 'port1'
    def expected_signal(self, phase):
        return self.mean + .5*(self.max - self.min) * \
                                    np.sin(phase)


class InterferometerPort2(InputDirect):
    name = 'port2'
    def expected_signal(self, phase):
        return self.mean - .5*(self.max - self.min) * \
                                    np.sin(phase)


class Inteferometer(Model):
    name = "interferometer"
    section_name = "interferometer"
    units = ['m', 'deg', 'rad']
    wavelength = FloatProperty(max=10000, min=0)
    gui_attributes = ['wavelength']
    setup_attributes = gui_attributes
    variable = 'phase'

    input_cls = [InterferometerPort1, InterferometerPort2]
    # pdh = InputPdh
#    port1 = InterferometerPort1 # any attribute of type InputSignal will be instantiated in the model
#    port2 = InterferometerPort2
    """
    @property
    def phase(self):
        if not hasattr(self, '_phase'):
            self._phase = 0
        return self._phase

    @phase.setter
    def phase(self, val):
        self._phase = val
        return val
    """

class FPTransmission(InputDirect):
    section_name = 'transmission'
    def expected_signal(self, variable):
        return self.min + (self.max - self.min)*self.model.lorentz(variable)


class FPReflection(InputDirect):
    section_name = 'reflection'

    def expected_signal(self, variable):
        return self.max - (self.max - self.min)*self.model.lorentz(variable)


class FabryPerot(Model):
    name = "FabryPerot"
    section_name = "fabryperot"
    units = ['m', 'MHz', 'nm']
    gui_attributes = ["wavelength", "finesse", "length", 'eta']
    setup_attributes = gui_attributes
    wavelength = FloatProperty(max=10000,min=0)
    finesse = FloatProperty(max=1e7, min=0)
    length = FloatProperty(max=10e12, min=0)
    eta    = FloatProperty(min=0., max=1.)
    # approximate length (not taking into account small variations of the order of wavelength)
    variable = 'detuning'

    input_cls = [FPTransmission, FPReflection, InputPdh]

    def lorentz(self, x):
        return 1.0 / (1.0 + x ** 2)