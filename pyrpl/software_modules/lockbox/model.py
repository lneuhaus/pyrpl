from pyrpl.modules import SoftwareModule


class Model(SoftwareModule):
    """
    A physical model allowing to relate inputs in V into a physical parameter in *unit*. Several units are actually
    available to describe the model parameter (e.g. 'm', 'MHz' for detuning).
    inputs is a list of signal.Input objects (or derived classes such as signal.PDH)
    """
    _section_name = 'model'
    parameter_name = ""
    units = []  # possible units to describe the physical parameter to control
    #  e.g. ['m', 'MHz']
    input_cls = []  # list of input signals that can be implemented
