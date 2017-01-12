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


class HighFinesseInput(InputDirect):
    """
    Since the number of points in the scope is too small for high finesse cavities, the acquisition is performed in
    2 steps:
        1. Full scan with the actuator, full scope duration, trigged on asg
        2. Full scan with the actuator, smaller scope duration, trigged on input (level defined by previous scan).
    Scope states corresponding to 1 and 2 are "sweep" and "sweep_zoom"
    """

    def calibrate(self):
        print("high-finesse calibrate")
        curve = super(HighFinesseInput, self).acquire()
        scope = self.pyrpl.scopes.pop(self.name)
        try:
            if not "sweep_zoom" in scope.states:
                scope.duration/=100
                scope.trigger_source = "ch1_positive_edge"
                scope.save_state("sweep_zoom")
            else:
                scope.load_state("sweep_zoom")
            threshold = self.get_threshold(curve)
            scope.setup(threshold_ch1=threshold, input1=self.signal())
            print(threshold)
            curve = scope.curve()
            self.get_stats_from_curve(curve)
        finally:
            self.pyrpl.scopes.free(scope)
        if self.widget is not None:
            self.update_graph()

    def get_threshold(self, curve):
        return (curve.min() + curve.mean())/2


class HighFinesseReflection(HighFinesseInput, FPReflection):
    """
    Reflection for a FabryPerot. The only difference with FPReflection is that 
    acquire will be done in 2 steps (coarse, then fine)
    """
    section_name = 'hf_reflection'
    pass


class HighFinesseTransmission(HighFinesseInput, FPTransmission):
    """
    Reflection for a FabryPerot. The only difference with FPReflection is that
    acquire will be done in 2 steps (coarse, then fine)
    """
    section_name = 'hf_transmission'
    pass


class HighFinessePdh(HighFinesseInput, InputPdh):
    """
    Reflection for a FabryPerot. The only difference with FPReflection is that
    acquire will be done in 2 steps (coarse, then fine)
    """
    section_name = 'hf_pdh'

    signal = InputPdh.signal

        
class HighFinesseFabryPerot(FabryPerot):
    name = "HighFinesseFP"
    section_name = "high_finesse_fp"
    input_cls = [HighFinesseReflection, HighFinesseTransmission, HighFinessePdh]
    