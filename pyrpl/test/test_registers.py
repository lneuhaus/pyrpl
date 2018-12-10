import logging
logger = logging.getLogger(name=__name__)
from pyrpl.modules import Module
from pyrpl.attributes import *
from .test_redpitaya import TestRedpitaya


class TestRegisters(TestRedpitaya):
    """ This test verifies that all registers behave as expected.

    The test is not only useful to test the python interface,
    but also checks that the fpga is not behaving stragely,
    i.e. loosing data or writing the wrong data. Thus, it is the
    principal test to execute on new fpga designs. """
    def test_generator(self):
        if self.r is None:
            assert False
        for modulekey, module in self.r.__dict__.items():
            if isinstance(module, Module):
                logger.info("Scanning module %s...", modulekey)
                for regkey, regclass in type(module).__dict__.items():
                    if isinstance(regclass, BaseRegister):
                        logger.info("Scanning register %s...", regkey)
                        yield self.register_validation, module, modulekey, \
                              regclass, regkey

    def register_validation(self, module, modulekey, reg, regkey):
        logger.debug("%s %s", modulekey, regkey)
        if type(reg) is BaseRegister:
            # try to read
            value = module.__getattribute__(regkey)
            # make sure Register represents an int
            if not isinstance(value, int):
                assert False, 'wrong type: int != %s' % str(type(value))
            # write back to it to test setter
            module.__setattr__(regkey, value)
            newvalue = module.__getattribute__(regkey)
            assert value == newvalue, \
                "Mismatch: value=" + str(value) + " new value = " + str(
                    newvalue)
        if type(reg) is LongRegister:
            # try to read
            value = module.__getattribute__(regkey)
            # make sure Register represents an int
            if not isinstance(value, int) and not isinstance(value, long):
                assert False, 'wrong type: int/long != %s' % str(type(value))
            # write back to it to test setter
            module.__setattr__(regkey, value)
            newvalue = module.__getattribute__(regkey)
            if regkey not in ["current_timestamp"]:
                assert value == newvalue, "Mismatch: value=" + str(value) \
                                          + " new value = " + str(newvalue)
        if type(reg) is BoolRegister or type(reg) is IORegister:
            # try to read
            value = module.__getattribute__(regkey)
            # make sure Register represents an int
            if type(value) != bool:
                assert False
            # exclude read-only registers
            if regkey in ['_reset_writestate_machine',
                          '_trigger_armed',
                          '_trigger_delay_running',
                          'pretrig_ok',
                          'armed',
                          'on']:
                return
            # write opposite value and confirm it has changed
            module.__setattr__(regkey, not value)
            if value == module.__getattribute__(regkey):
                assert False
            # write back original value and check for equality
            module.__setattr__(regkey, value)
            if value != module.__getattribute__(regkey):
                assert False
        if type(reg) is FloatRegister:
            # try to read
            value = module.__getattribute__(regkey)
            # make sure Register represents a float
            if not isinstance(value, float):
                assert False
            # exclude read-only registers
            if regkey in ['pfd_integral',
                          'ch1_firstpoint',
                          'ch2_firstpoint',
                          'voltage_out1',
                          'voltage_out2',
                          'voltage_in1',
                          'voltage_in2',
                          'firstpoint',
                          'lastpoint'
                          ] or modulekey == 'sampler':
                return
            # write something different and confirm change
            if value == 0:
                write = 1e10
            else:
                write = 0
            module.__setattr__(regkey, write)
            if value == module.__getattribute__(regkey):
                assert False
            # write sth negative
            write = -1e10
            module.__setattr__(regkey, write)
            if module.__getattribute__(regkey) >= 0:
                if reg.signed:
                    assert False
                else:
                    # unsigned registers should use absolute value and
                    # therefore not be zero when assigned large negative values
                    if module.__getattribute__(regkey) == 0:
                        assert False
            # set back original value
            module.__setattr__(regkey, value)
            if value != module.__getattribute__(regkey):
                assert False
        if type(reg) is PhaseRegister:
            # try to read
            value = module.__getattribute__(regkey)
            # make sure Register represents a float
            if not isinstance(value, float):
                assert False
            # make sure any random phase has an error below 1e-6 degrees !
            if regkey not in ['scopetriggerphase']:
                for phase in np.linspace(-1234, 5678, 90):
                    module.__setattr__(regkey, phase)
                    diff = abs(module.__getattribute__(regkey) - (phase % 360))
                    bits = getattr(module.__class__, regkey).bits
                    thr = 360.0/2**bits/2  # factor 2 because rounding is used
                    if diff > thr:
                        assert False, \
                            "at phase " + str(phase) + ": diff = " + str(diff)
            # set back original value
            module.__setattr__(regkey, value)
            if value != module.__getattribute__(regkey):
                assert False
        if type(reg) is FrequencyRegister:
            # try to read
            value = module.__getattribute__(regkey)
            # make sure Register represents a float
            if not isinstance(value, float):
                assert False
            # make sure any frequency has an error below 100 mHz!
            if regkey not in []:
                for freq in [0, 1, 10, 1e2, 1e3, 1e4, 1e5, 1e6, 1e7,
                             125e6 / 2]:  # FrequencyRegisters are now limited.
                    module.__setattr__(regkey, freq)
                    diff = abs(module.__getattribute__(regkey) - freq)
                    if diff > 0.1:
                        assert False, \
                            "at freq " + str(freq) + ": diff = " + str(diff)
            # set back original value
            module.__setattr__(regkey, value)
            if value != module.__getattribute__(regkey):
                assert False
        if type(reg) is SelectRegister:
            # try to read
            value = module.__getattribute__(regkey)
            # make sure Register represents an int
            if not isinstance((sorted(reg.options(module))[0]), type(value)):
                assert False
            # exclude read-only registers
            if regkey in ["id"]:
                return
            # try all options and confirm change that they are saved
            for option in sorted(reg.options(module)):
                module.__setattr__(regkey, option)
                if option != module.__getattribute__(regkey):
                    assert False
            # set back original value
            module.__setattr__(regkey, value)
            if value != module.__getattribute__(regkey):
                assert False
        return