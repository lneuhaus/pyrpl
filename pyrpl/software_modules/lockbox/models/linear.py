from .. import *


class LinearInputDirect(InputDirect):
    slope = FloatProperty(min=-1e10, max=1e10, default=1)
    signal_at_0 = FloatProperty(min=-1e10, max=1e10, default=0)

    def expected_signal(self, variable):
        return self.slope * variable + self.signal_at_0


class Linear(Lockbox):
    """
    A simple linear dependance of variable vs input
    """
    #name = "Linear"
    _units = ['m', 'deg', 'rad']
    variable = 'x'
