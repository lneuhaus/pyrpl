from pyrpl.software_modules.lockbox import *
from pyrpl.software_modules.lockbox.models import Interferometer

from pyrpl.attributes import *




class Pll(Interferometer):


    # management of intput/output units
    # setpoint_variable = 'phase'


    # must provide conversion from setpoint_unit into all other basic units
    # management of intput/output units



    inputs = LockboxModuleDictProperty(
                                       cordicerror=InputDirect,
                                       errorfastpiezo=InputFromOutput,
                                        errorslowpiezo=InputFromOutput
                                       )

    outputs = LockboxModuleDictProperty(
                                        slow_piezo=PiezoOutput,
                                        fast_piezo=PiezoOutput,
                                        temperature=PiezoOutput
                                        )
                                        #piezo2=PiezoOutput)








