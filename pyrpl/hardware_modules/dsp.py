from collections import OrderedDict
from ..attributes import SelectAttribute, SelectRegister, BoolRegister, SelectProperty
from ..modules import HardwareModule, SignalModule
from ..pyrpl_utils import sorted_dict, recursive_getattribute, recursive_setattr


DSP_INPUTS = sorted_dict(
    pid0=0,
    pid1=1,
    pid2=2,
    trig=3,
    iir=4,
    iq0=5,
    iq1=6,
    iq2=7,
    asg0=8,
    asg1=9,
    # scope0 = 8, #same as asg0 by design
    # scope1 = 9, #same as asg1 by design
    in1=10, #same as asg
    in2=11,
    out1=12,
    out2=13,
    iq2_2=14,
    off=15)


class DspInputAttribute(SelectProperty):
    "selects the input signal of the module"
    def __init__(self,
                 default=None,
                 doc="",
                 ignore_errors=False,
                 call_setup=False):
        super(SelectProperty, self).__init__(default=default,
                                             doc=doc,
                                             ignore_errors=ignore_errors,
                                             call_setup=call_setup)
        if not hasattr(self, 'default'):
           self.default = self.options(None).keys()[0]

    register = '_input'

    def options(self, instance):
        """ collects all available logical inputs, composed of all
        dsp inputs and all submodule inputs, such as lockbox signals etc."""
        # options is a mapping from option names to the setting of _input
        if instance is None:
            signals = sorted_dict({k: k for k in DSP_INPUTS.keys()})
        else:
            signals = sorted_dict({k: k for k in instance._inputs.keys()})
            if instance is not None:
                for module in instance.pyrpl.software_modules:
                    try:
                        module_signals = module.signals
                    except AttributeError:
                        pass
                    else:
                        for key, value in module_signals.items():
                            signals[module.name + '.' + key] = value.signal()
        return signals

    def set_value(self, instance, value):
        try:
            value = value.signal()
        except AttributeError:
            pass
        super(DspInputAttribute, self).set_value(instance, value)
        recursive_setattr(instance,
                          self.register,
                          self.options(instance)[value])

    def get_value(self, instance, owner):
        value = super(DspInputAttribute, self).get_value(instance, owner)
        # make sure the setting corresponds to the register setting
        current = recursive_getattribute(instance, self.register)
        if current == self.options(instance)[value]:
            return value
        else:
            return current


class DspModule(HardwareModule, SignalModule):
    _delay = 0  # delay of the module from input to output_signal (in cycles)

    _output_directs = sorted_dict(off=0,
                                  out1=1,
                                  out2=2,
                                  both=3)
    output_directs = _output_directs.keys()

    _inputs = sorted_dict(DSP_INPUTS, sort_by_values=True)
    _input = SelectRegister(0x0, options=_inputs,
                            doc="selects the input signal of the module")

    input = DspInputAttribute(_inputs)

    inputs = _inputs.keys()


    output_direct = SelectRegister(0x4,
                                   options=_output_directs,
                                   doc="selects to which analog output the "
                                       "module signal is sent directly")

    out1_saturated = BoolRegister(0x8, 0, doc="True if out1 is saturated")

    out2_saturated = BoolRegister(0x8, 1, doc="True if out2 is saturated")

    addr_base = None

    def __init__(self, rp, name):
        self._number = self._inputs[name]  # find address from name
        self.addr_base = 0x40300000 + self._number * 0x10000
        super(DspModule, self).__init__(rp, name)
