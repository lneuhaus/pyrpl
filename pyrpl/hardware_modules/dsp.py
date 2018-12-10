from collections import OrderedDict
from ..attributes import BoolRegister, SelectProperty, SelectProperty, SelectRegister, IntRegister, FloatRegister, BaseRegister, BoolProperty
from ..modules import HardwareModule, SignalModule
from ..pyrpl_utils import sorted_dict, recursive_getattr, recursive_setattr
from ..errors import ExpectedPyrplError

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
        except (AttributeError, ExpectedPyrplError):
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


class PauseRegister(BoolRegister):
    """
    A bool register whose bit number is the containing module dsp number.
    """
    def __init__(self, address=0xC, bitmask=None, invert=False, **kwargs):
            assert type(invert) == bool
            self.invert = invert
            BaseRegister.__init__(self, address=address, bitmask=bitmask)
            BoolProperty.__init__(self, **kwargs)

    def to_python(self, obj, value):
        bit = obj._number
        value = bool((value >> bit) & 1)
        if self.invert:
            value = not value
        return value

    def from_python(self, obj, val):
        bit = obj._number
        if self.invert:
            val = not val
        if val:
            towrite = obj._read(self.address) | (1 << bit)
        else:
            towrite = obj._read(self.address) & (~(1 << bit))
        return towrite


class DspModule(HardwareModule, SignalModule):
    """
    A module with an input and an auxiliary output_direct signal.

    DSP modules can be chained one after the other by setting the input port
    of module *B* to module 'A'. e.g:

    .. code-block:: python

        from pyrpl import Pyrpl

        r = Pyrpl().redpitaya

        # Route the signal from analog input 'in1' to pid0 then pid1, then
        # monitor the result on the scope:
        r.pid0.input = 'in1'
        r.pid1.input = 'pid0'
        r.scope.input1 = r.pid1  # modules can also be resolved by object

    An auxiliary output can be used to output a signal to the DACs. All
    signals routed to the same DAC are summed together.

    .. code-block:: python

        # output the signal to analog output 1:
        r.pid1.output_direct = 'out1'

        # the modulation output of iq0 will be summed with the previous signal
        r.iq0.output_direct = 'out1'
    """

    def __init__(self, rp, name):
        self._number = DSP_INPUTS[name]
        self.addr_base = dsp_addr_base(name)
        super(DspModule, self).__init__(rp, name)

    _delay = 0  # delay of the module from input to output_signal (in cycles)

    @property
    def inputs(self):
        self._logger.warning("Deprecation warning: DspModule.inputs "
                             "will soon be removed. Use "
                             "DspModule.input_options instead!")
        return all_inputs(self).keys()

    input = InputSelectRegister(0x0,
                                options=all_inputs,
                                doc="selects the input signal of the module")

    @property
    def output_directs(self):
        self._logger.warning("Deprecation warning: DspModule.output_directs"
                             "will soon be removed. Use "
                             "DspModule.output_direct_options instead!")
        return all_output_directs(self).keys()

    output_direct = SelectRegister(0x4,
                                   options=all_output_directs,
                                   doc="selects to which analog output the "
                                       "module signal is sent directly")

    out1_saturated = BoolRegister(0x8, 0, doc="True if out1 is saturated")

    out2_saturated = BoolRegister(0x8, 1, doc="True if out2 is saturated")

    _sync = IntRegister(0xC,
                        doc="Allows to synchronize different dsp modules. "
                            "Each DSP module is represented by the bit at "
                            "the index module._number. Setting the bits of the "
                            "modules to syncronize to zero and back to one "
                            "causes these modules to syncronize. Currently "
                            "this functionality is only implemented for iq "
                            "modules.")

    _paused = PauseRegister(0xC,
                            invert=True,
                            doc="If True, the module is paused. What this "
                                "means in detail depends on the functionality "
                                "of the module.")

    def _synchronize(self, modules=[]):
        """
        synchronizes the given list of modules.

        If an empty list is given (default), all modules are syncronized.
        """
        # store current value
        sync_stored = self._sync
        if not modules:
            sync_reset = 0  # sync all modules
        else:
            sync_reset = sync_stored  # start with current state
            for module in modules:
                if isinstance(module, DspModule):
                    bit = module._number
                elif isinstance(module, str):
                    bit = DSP_INPUTS[module]
                elif isinstance(module, int):
                    bit = module
                else:
                    self._logger.warning("Module specified by %s has unknown "
                                         "type. This may lead to unwanted "
                                         "behavior!", module)
                    bit = module
                # disable the bit of the module
                sync_reset = sync_reset & (~(1 << bit))
        # write the reset register value to enable sync mode
        self._sync = sync_reset
        # restore the previous state of the modules
        self._sync = sync_stored

    current_output_signal = FloatRegister(0x10,
                                          bits=14,
                                          norm=2 ** 13 - 1,
                                          doc="current value of output_signal "
                                              "as returned by the sampler "
                                              "module")
