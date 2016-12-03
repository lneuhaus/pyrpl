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
    def expected_signal(self, phase):
        return self.parameters['mean'] + .5*(self.parameters['max'] - self.parameters['min']) * \
                                    np.sin(phase)


class InterferometerPort2(InputDirect):
    def expected_signal(self, phase):
        return self.parameters['mean'] - .5*(self.parameters['max'] - self.parameters['min']) * \
                                    np.sin(phase)


class Inteferometer(Model):
    name = "interferometer"
    units = ['m', 'deg', 'rad']
    wavelength = FloatProperty()
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