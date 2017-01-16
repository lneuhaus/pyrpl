from collections import OrderedDict

from ..attributes import SelectAttribute, SelectRegister, BoolRegister
from ..modules import HardwareModule
from ..pyrpl_utils import sorted_dict

DSP_INPUTS = sorted_dict(
    pid1=0,
    pid2=1,
    pid3=2,
    pid4=3,
    iir=4,
    iq1=5,
    iq2=6,
    iq3=7,
    asg1=8,
    asg2=9,
    # scope1 = 8, #same as asg1 by design
    # scope2 = 9, #same as asg2 by design
    in1=10, #same as asg
    in2=11,
    out1=12,
    out2=13,
    iq3_2=14,
    off=15)

class DspInputAttribute(SelectAttribute):
    "selects the input signal of the module"
    def get_value(self, instance, owner):
        if instance is None:
            return self
        else:
            return instance._input

    def set_value(self, instance, value):
        # allow to directly pass another dspmodule as input
        # if isinstance(value, HardwareModule) and hasattr(value, 'name'): # (asg is HardwareModule but not DspModule)
        #    instance._input = value.name
        #else:
        instance._input = value
        return value

class DspModule(HardwareModule):
    _delay = 0  # delay of the module from input to output_signal (in cycles)

    _inputs = sorted_dict(DSP_INPUTS, sort_by_values=True)
    inputs = _inputs.keys()

    _output_directs = sorted_dict(off=0,
                                  out1=1,
                                  out2=2,
                                  both=3)
    output_directs = _output_directs.keys()

    _input = SelectRegister(0x0, options=_inputs,
                           doc="selects the input signal of the module")

    input = DspInputAttribute(_inputs)

    output_direct = SelectRegister(0x4, options=_output_directs,
                            doc="selects to which analog output the module \
                            signal is sent directly")

    out1_saturated = BoolRegister(0x8, 0, doc="True if out1 is saturated")

    out2_saturated = BoolRegister(0x8, 1, doc="True if out2 is saturated")

    section_name = "dspmodule"

    addr_base = None

    def __init__(self, rp, name):
        self._number = self._inputs[name]  # find address from name
        self.addr_base = 0x40300000 + self._number * 0x10000
        super(DspModule, self).__init__(rp, name)

    def init_module(self):
        pass
    """
    def __init__(self, client, name, parent): # for consistency, all HardwareModule creators have the same signature
        self._number = self._inputs[name]
        super(DspModule, self).__init__(client,
            addr_base=0x40300000+self._number*0x10000,
            parent=parent, name=name)
    """