from pyrpl.attributes import IntRegister, SelectRegister, IORegister
from pyrpl.modules import HardwareModule

import numpy as np


class HK(HardwareModule):
    name = 'HK'
    gui_attributes = ["id", "led"]

    def __new__(cls, *args, **kwargs):
        """ make the needed input output registers. Workaround to make
        descriptors work """
        for i in range(8):
            setattr(cls,
                    'expansion_P' + str(i),
                    IORegister(0x20, 0x18, 0x10, bit=i,
                               outputmode=True,
                               doc="positive digital io"))
            setattr(cls,
                    'expansion_N' + str(i),
                    IORegister(0x24, 0x1C, 0x14, bit=i,
                               outputmode=True,
                               doc="positive digital io"))
        return super(HK, cls).__new__(cls)  # , *args, **kwargs

    def __init__(self, client, name, parent):
        super(HK, self).__init__(client, addr_base=0x40000000, parent=parent, name=name)

    id = SelectRegister(0x0, doc="device ID", options={"prototype0": 0,
                                                       "release1": 1})
    digital_loop = IntRegister(0x0C, doc="enables digital loop")
    led = IntRegister(0x30, doc="LED control with bits 1:8")
    # another option: access led as array of bools
    # led = [BoolRegister(0x30,bit=i,doc="LED "+str(i)) for i in range(8)]

