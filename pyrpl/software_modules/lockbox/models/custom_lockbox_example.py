# these imports are the standard imports for required for derived lockboxes
from pyrpl.software_modules.lockbox.signals import *
from pyrpl.software_modules.lockbox import *
from pyrpl.attributes import *


# Any InputSignal must define a class that contains the function "expected_signal(variable)" that returns the expected
# signal value as a function of the variable value. This function ensures that the correct setpoint and a reasonable
# gain is chosen (from the derivative of expected_signal) when this signal is used for feedback.
class CustomInputClass(InputSignal):
    """ A custom input signal for our customized lockbox. Please refer to the documentation on the default API of
    InputSignals"""
    def expected_signal(self, variable):
        # For example, assume that our analog signal is proportional to the square of the variable
        return self.min + self.lockbox.custom_attribute * variable**2

    # If possible, you should explicitely define the derivative of expected_signal(variable). Otherwise, the derivative
    # is estimated numerically which might lead to inaccuracies and excess delay.
    def expected_slope(self, variable):
        return 2.0 * self.lockbox.custom_attribute * variable

    # A customized calibration method can be used to implement custom calibrations. The calibration method of the
    # InputSignal class retrieves min, max, mean, rms of the input signal during a sweep and saves them as class
    # attributes, such that they can be used by expected_signal().
    def calibrate(self):
        """ This is a simplified calibration method. InputSignal.calibrate works better than this in most cases. """
        self.lockbox.sweep()
        # get a curve of the signal during the sweep
        curve = self.acquire()
        # fill self.mean, min, max, rms with values from acquired curve.
        self.get_stats_from_curve(curve=curve)


class CustomLockbox(Lockbox):
    """ A custom lockbox class that can be used to implement customized feedback controllers"""

    # this syntax for the definition of inputs and outputs allows to conveniently access inputs in the API
    inputs = ModuleContainerProperty(LockboxModule,
                                     custom_input_name=CustomInputClass)

    # the name of the variable to be stabilized to a setpoint. inputs.expected_signal(variable) returns the expected
    # signal as a function of this variable
    variable = 'displacement'

    # attributes are defined by descriptors
    custom_attribute = FloatProperty(default=1.0, increment=0.01, min=1e-5, max=1e5)

    # list of attributes that are mandatory to define lockbox state. setup_attributes of all base classes and of all
    # submodules are automatically added to the list by the metaclass of Module
    _setup_attributes = ["custom_attribute"]
    # attributes that are displayed in the gui. _gui_attributes from base classes are also added.
    _gui_attributes = ["custom_attribute"]

    # if nonstandard units are to be used to specify the gain of the outputs, their conversion to Volts must be defined
    # by a property called _unitname_per_V
    _mV_per_V = 1000.0

    # overwrite any lockbox functions here or add new ones
    def custom_function(self):
        self.calibrate_all()
        self.unlock()
        self.lock()