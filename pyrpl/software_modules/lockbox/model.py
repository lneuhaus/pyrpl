from pyrpl.modules import SoftwareModule
from .signals.input import InputDirect, InputPdh

class Model(SoftwareModule):
    """
    A physical model allowing to relate inputs in V into a physical parameter in *unit*. Several units are actually
    available to describe the model parameter (e.g. 'm', 'MHz' for detuning).
    inputs is a list of signal.Input objects (or derived classes such as signal.PDH)
    """
    parameter_name = ""
    units = []  # possible units to describe the physical param# eter to control e.g. ['m', 'MHz']
    inputs = [] # list of input signals that can be implemented


class DummyModel(Model):
    name = "dummy"
    units = ['m', 'MHz']
    pdh = InputPdh
    reflection   = InputDirect
    transmission = InputDirect