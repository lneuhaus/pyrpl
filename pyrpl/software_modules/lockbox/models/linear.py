from ..signals import *
from ..lockbox import Lockbox


class LinearInputDirect(InputDirect):
    _section_name = "linear_input"

    slope = FloatProperty(min=-1e10, max=1e10, default=1)
    signal_at_0 = FloatProperty(min=-1e10, max=1e10, default=0)

    def expected_signal(self, variable):
        return self.slope*variable + self.signal_at_0


class Linear(Lockbox):
    """
    A simple linear dependance of variable vs input
    """
    name = "Linear"
    _section_name = "linear"
    units = ['m', 'deg', 'rad']
    variable = 'x'
    input_cls = [LinearInputDirect]
