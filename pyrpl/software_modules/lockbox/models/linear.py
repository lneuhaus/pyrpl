from ..signals import *
from ..model import *


class LinearInputDirect(InputDirect):
    _section_name = "linear_input"

    def expected_signal(self, variable):
        return self.model.slope*variable + self.model.signal_at_0


class Linear(Model):
    """
    A simple linear dependance of variable vs input
    """
    name = "Linear"
    _section_name = "linear"
    units = ['m', 'deg', 'rad']
    slope = FloatProperty(min=-1e10, max=1e10, default=1)
    signal_at_0 = FloatProperty(min=-1e10, max=1e10, default=0)
    #wavelength = FloatProperty(max=10000, min=0, default=1.064)
    _setup_attributes = []  # ['wavelength']
    _gui_attributes = _setup_attributes
    variable = 'x'

    input_cls = [LinearInputDirect]