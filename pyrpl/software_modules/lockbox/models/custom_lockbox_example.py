from pyrpl.software_modules.lockbox.signals import *
from pyrpl.software_modules.lockbox import Lockbox

class CustomInput(InputDirect):
    """ A custom input signal for our customized lockbox. Please refer to the documentation on the default API of
    InputSignals"""
    def expected_signal(self, variable):
        # for example, assume that our analog signal is proportional to the square of the variable
        return self.min + self.lockbox.custom_attribute * variable**2

class CustomLockbox(Lockbox):
    """ A custom lockbox class that can be used to implement customized feedback controllers"""
    _setup_attributes = Lockbox._setup_attributes + ["custom_attribute"]
    _gui_attributes = Lockbox._setup_attributes + ["custom_attribute"]
    custom_attribute = FloatAttribute(default=1.0, increment=0.01, min=1e-5, max=1e5)
    units = Lockbox.units + ['mV']
    variable = 'detuning'

    input_cls = [CustomInput]

    # overwrite any lockbox functions here or add new ones
    def custom_function(self):
        self.sweep()
        self.unlock()
        self.lock()
