from collections import OrderedDict
from ..attributes import BoolRegister, SelectProperty, SelectProperty, SelectRegister
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

def all_inputs_keys(instance):
    """ collects all available logical inputs, composed of all
    dsp inputs and all submodule inputs, such as lockbox signals etc."""
    # options is a mapping from option names to the setting of _input
    signals = list(DSP_INPUTS.keys())
    if instance is not None:
        try:
            pyrpl = instance.pyrpl
        except AttributeError:
            pass
        else:
            if hasattr(pyrpl, 'software_modules'):
                for module in pyrpl.software_modules:
                    try:
                        module_signals = module.signals
                    except AttributeError:
                        if isinstance(module, SignalModule):
                            module_signals = {module.name: module}
                        else:
                            continue
                    for name, signal in module_signals.items():
                        signals.append(signal.name)
                        signal = signal.parent
                        while signal != pyrpl:
                            signals[-1] = signal.name + '.' + signals[-1]
                            signal = signal.parent
    return signals


def all_inputs(instance):
    """ collects all available logical inputs, composed of all
    dsp inputs and all submodule inputs, such as lockbox signals etc."""
    # options is a mapping from option names to the setting of _input
    signals = OrderedDict()
    for k in all_inputs_keys(instance):
        if k in DSP_INPUTS:
            signals[k] = DSP_INPUTS[k]
        elif instance is not None:
            try:
                signals[k] = recursive_getattr(instance.pyrpl, k+'.signal')()
            except AttributeError:
                pass
    for i in range(4):  # avoid closed loops by maximum depth of iteration
        for signal in signals:
            if signals[signal] not in signals:
                pass
            elif signals[signal] == signal:  # points to its own key
                signals[signal] = 'off'
            else:  # signal points to the key of another signal
                signals[signal] = signals[signals[signal]]  # resolve pointer
    return signals


class InputSelectProperty(SelectProperty):
    """ a select register that stores logical signals if possible,
    otherwise the underlying dsp signals"""
    def __init__(self, options=all_inputs_keys, **kwargs):
        SelectProperty.__init__(self, options=options, **kwargs)

    def validate_and_normalize(self, obj, value):
        if isinstance(value, SignalModule):
            # try to construct the path from the pyrpl module
            pyrpl, rp = value.pyrpl, value.pyrpl.rp
            name = value.name
            fullname = name
            module = value.parent
            while (module != pyrpl) and (module != rp):
                fullname = module.name + '.' + fullname
                module = module.parent
            # take this path as the input signal key if allowed
            if fullname in self.options(obj):
                value = fullname
            # try to remove the preceding stuff from name (allows shortcuts)
            elif name in self.options(obj):
                value = name
            # otherwise take the corresponding dsp signal
            else:
                value = value.signal()
        else:
            options = self.options(obj)
            if value not in options:
                # if not an option, try to remove preceding text from options
                # and see if a match is possible
                options = [o for o in self.options(obj) if o.endswith(value)]
                if len(options) > 0:
                    value, oldvalue = options[0], value
                    if len(options) > 1:
                        obj._logger.warning("%s.%s was ambiguously assigned "
                                            "the input %s from %s. Possible "
                                            "values were %s.",
                                            obj.name, self.name, value,
                                            oldvalue, options)
        return super(InputSelectProperty, self).validate_and_normalize(obj, value)


class InputSelectRegister(InputSelectProperty, SelectRegister):
    def __init__(self, address, options=all_inputs, **kwargs):
        SelectRegister.__init__(self, address, options=options, **kwargs)


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
