from pyrpl.attributes import IntRegister, SelectRegister, IORegister
from pyrpl.modules import HardwareModule

import numpy as np


class HK(HardwareModule):
    name = 'HK'
    gui_attributes = ["id", "led"]

    # We need all attributes to be there when the interpreter is done reading the class (for metaclass to workout)
    # see http://stackoverflow.com/questions/2265402/adding-class-attributes-using-a-for-loop-in-python
    for i in range(8):
        locals()['expansion_P' + str(i)] = IORegister(0x20, 0x18, 0x10, bit=i,
                                                      outputmode=True,
                                                      doc="positive digital io")
        locals()['expansion_N' + str(i)] = IORegister(0x24, 0x1C, 0x14, bit=i,
                                                      outputmode=True,
                                                      doc="positive digital io")

    def __init__(self, client, name, parent):
        super(HK, self).__init__(client, addr_base=0x40000000, parent=parent, name=name)

    id = SelectRegister(0x0, doc="device ID", options={"prototype0": 0,
                                                       "release1": 1})
    digital_loop = IntRegister(0x0C, doc="enables digital loop")
    led = IntRegister(0x30, doc="LED control with bits 1:8")
    # another option: access led as array of bools
    # led = [BoolRegister(0x30,bit=i,doc="LED "+str(i)) for i in range(8)]

    def _setup(self): # the function is here for its docstring to be used by the metaclass.
        """
        Sets the HouseKeeping module of the redpitaya up. (just setting the attributes is OK)
        """
        pass
