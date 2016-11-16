from pyrpl.attributes import FloatRegister
from pyrpl.modules import HardwareModule
from . import DSP_INPUTS


class Sampler(HardwareModule):
    def __init__(self, client, name, parent):
        self.name = "sampler"
        super(Sampler, self).__init__(client,
            addr_base=0x40300000,
            parent=parent,
            name=name)
for inp, num in DSP_INPUTS.items():
    setattr(Sampler,
            inp,
            FloatRegister(
                0x10 + num * 0x10000,
                bits=14,
                norm=2 ** 13 - 1,
                doc="output signal " + inp))