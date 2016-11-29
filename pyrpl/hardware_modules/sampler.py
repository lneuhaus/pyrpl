from pyrpl.attributes import FloatRegister
from pyrpl.modules import HardwareModule
from . import DSP_INPUTS


class Sampler(HardwareModule):
    name = 'sampler'
    addr_base = 0x40300000

for inp, num in DSP_INPUTS.items():
    setattr(Sampler,
            inp,
            FloatRegister(
                0x10 + num * 0x10000,
                bits=14,
                norm=2 ** 13 - 1,
                doc="output signal " + inp))