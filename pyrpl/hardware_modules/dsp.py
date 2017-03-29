from collections import OrderedDict
from ..attributes import BoolRegister, SelectProperty, SelectProperty, SelectRegister
from ..module_attributes import InputSelectRegister
from ..modules import HardwareModule, SignalModule
from ..pyrpl_utils import sorted_dict, recursive_getattr, recursive_setattr


# order here determines the order in the GUI etc.
DSP_INPUTS = OrderedDict([
    ('in1', 10), #same as asg
    ('in2', 11),
    ('out1', 12),
    ('out2', 13),
    ('iq0', 5),
    ('iq1', 6),
    ('iq2', 7),
    ('iq2_2', 14),
    ('pid0', 0),
    ('pid1', 1),
    ('pid2', 2),
    ('asg0', 8),
    ('asg1', 9),
    ('trig', 3),
    ('iir', 4),
    # ('scope0', 8), #same as asg0 by design
    # ('scope1', 9), #same as asg1 by design
    ('off', 15)])


def all_inputs(instance):
    """ collects all available logical inputs, composed of all
    dsp inputs and all submodule inputs, such as lockbox signals etc."""
    # options is a mapping from option names to the setting of _input
    signals = OrderedDict(DSP_INPUTS)
    if instance is not None:
        try:
            pyrpl = instance.pyrpl
        except AttributeError:
            pass
        else:
            for module in pyrpl.software_modules:
                try:
                    module_signals = module.signals
                except AttributeError:
                    pass
                else:
                    for key, value in module_signals.items():
                        signals[module.name + '.' + key] = value.signal()
    for signal in signals:
        while signals[signal] in signals:  # signal points to another key
            if signals[signal] == signal:  # a) signal points to its own key
                signals[signal] = 'off'
            else:  # b) signal points to the key of another signal
                signals[signal] = signals[signals[signal]]  # resolve the pointer
    return signals


def all_output_directs(instance):
    return sorted_dict(off=0, out1=1, out2=2, both=3,
                       sort_by_values=True)


def dsp_addr_base(name):
    # find address from name
    number = DSP_INPUTS[name]
    return 0x40300000 + number * 0x10000


class DspModule(HardwareModule, SignalModule):
    def __init__(self, rp, name):
        self._number = DSP_INPUTS[name]
        self.addr_base = dsp_addr_base(name)
        super(DspModule, self).__init__(rp, name)

    _delay = 0  # delay of the module from input to output_signal (in cycles)

    @property
    def inputs(self):
        return all_inputs(self).keys()

    input = InputSelectRegister(0x0,
                                options=all_inputs,
                                doc="selects the input signal of the module")

    @property
    def output_directs(self):
        return all_output_directs(self).keys()

    output_direct = SelectRegister(0x4,
                                   options=all_output_directs,
                                   doc="selects to which analog output the "
                                       "module signal is sent directly")

    out1_saturated = BoolRegister(0x8, 0, doc="True if out1 is saturated")

    out2_saturated = BoolRegister(0x8, 1, doc="True if out2 is saturated")
