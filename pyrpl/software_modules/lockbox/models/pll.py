from pyrpl.software_modules.lockbox import *
from pyrpl.software_modules.lockbox.models import Interferometer
from pyrpl.software_modules.lockbox.models.interferometer import InterferometerPort1, PdhInterferometerPort1
from pyrpl.attributes import *
import numpy




class SlowOutputProperty(FloatProperty):
    def __init__(self, **kwds):
        super(SlowOutputProperty, self).__init__(**kwds)

    def get_value(self, obj):
        if obj is None:
            return self
        return (obj.pyrpl.rp.pid0.ival+1.)*0.9 # Ival goes from -1 to +1 while pwm goes from 0 to 1.8V

    def set_value(self, obj, val):
        if val > self.max:
            obj._logger.warning("Coarse cannot go above max. value of %s!",
                                self.max)
        if val < self.min:
            obj._logger.warning("Coarse cannot go above min. value of %s!",
                                self.min)

            obj.pyrpl.rp.pid0.ival = (val/0.9-1.)


class InputFromOutput0(InputFromOutput):
    input_signal = InputSelectProperty(
        options=(lambda instance:
                 ['lockbox0.outputs.' + k for k in instance.lockbox.outputs.keys()]),
        doc="lockbox signal used as input")


class Suiveur(Interferometer):

    #slow_output = PWMRegister(adress = 0)
    slow_output = SlowOutputProperty(max=1.8, min=0., default=0, increment=1e-2)
    _gui_attributes = ["slow_output"]
    _setup_attributes = _gui_attributes

    # management of intput/output units
    # setpoint_variable = 'phase'


    # must provide conversion from setpoint_unit into all other basic units
    # management of intput/output units



    inputs = LockboxModuleDictProperty(
                                       errorsignal1=InputDirect,
                                       errorsignal2=InputDirect,
                                       errorfastpiezo=InputFromOutput0,
                                        errorslowpiezo=InputFromOutput0
                                       )

    outputs = LockboxModuleDictProperty(
                                        slow_piezo=PiezoOutput,
                                        fast_piezo=PiezoOutput,
                                        temperature=PiezoOutput
                                        )
                                        #piezo2=PiezoOutput)












