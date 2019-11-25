import numpy as np
from ..modules import HardwareModule
from ..attributes import PWMRegister, FloatRegister, IntRegister, SelectRegister


class AMS(HardwareModule):
    """mostly deprecated module (redpitaya has removed adc support).
    only here for dac2 and dac3"""
    addr_base = 0x40400000

    _setup_attributes = ['trigger_source']

    # attention: writing to dac0 and dac1 has no effect
    # only write to dac2 and 3 to set output voltages
    # to modify dac0 and dac1, connect a r.pwm0.input='pid0'
    # and let the pid module determine the voltage
    dac0 = PWMRegister(0x20, doc="PWM output 0 [V]")
    dac1 = PWMRegister(0x24, doc="PWM output 1 [V]")
    dac2 = PWMRegister(0x28, doc="PWM output 2 [V]")
    dac3 = PWMRegister(0x2C, doc="PWM output 3 [V]")

    # max positive has all but sign bits high (2**11), occurs for 0.5 V
    _xadc_norm = 2 ** 12 / 0.5
    # ADC voltage is behind a voltage divider formed by 30k and 4.99 k resistors
    _xadc_norm *= 4990.0 / 34990.0
    # experimentally found there was a discrepancy of 0.5 (maybe different resistors)
    _xadc_norm *= 0.5

    vadc0 = FloatRegister(0x0, bits=12, norm=_xadc_norm, signed=True,
                          doc="slow analog in voltage 0 (V)")
    vadc1 = FloatRegister(0x4, bits=12, norm=_xadc_norm, signed=True,
                          doc="slow analog in voltage 1 (V)")
    vadc2 = FloatRegister(0x8, bits=12, norm=_xadc_norm, signed=True,
                          doc="slow analog in voltage 2 (V)")
    vadc3 = FloatRegister(0xC, bits=12, norm=_xadc_norm, signed=True,
                          doc="slow analog in voltage 3 (V)")

    trigger_source = SelectRegister(
        0x50,
        default='auto',
        doc='selects which trigger signals can start a slow adc acquisition '
            'conversion',
        bitmask=0x00FF,
        options={'off': 0,
                 'trig0': 1<<3,
                 'trig1': 1<<4,
                 'auto': 1<<8,
                 },
    )

    @property
    def vadcs(self):
        """
        Returns an array of all four XADC voltages.
        """
        x = np.array(self._reads(0x0, 4), dtype=np.float)
        x[x >= 2 ** 11] -= 2 ** 12
        return x * (1.0 / self._xadc_norm)

    def vadcs_n(self, n):
        """
        Returns n arrays of all four XADC voltages.
        """
        return np.array([self.vadcs for i in range(n)])

    def vadcs_mean(self, n):
        """
        Returns the mean of n arrays of all four XADC voltages.
        """
        return np.mean(self.vadcs_n(n), axis=0)

    # all these registers have no meaning in the most recent FPGA version
    # because the XADC is set up to only measure the external slow ADCs
    # vsupply = FloatRegister(0x10, bits=12, norm=2 ** 12 * 4.99 / 60.99, signed=False,
    #                       doc="USB power supply voltage (5V) monitor")
    #
    # _raw_temperature = IntRegister(0x30, bits=12, doc="FPGA temperature raw XADC value")
    # @property
    # def temperature(self):
    #     return float(self._raw_temperature) / 2 ** 12 * 503.975 - 273.15
    #
    # vccpint = FloatRegister(0x34, bits=12, norm=2 ** 12 / 3.0, signed=False)
    # vccpaux = FloatRegister(0x38, bits=12, norm=2 ** 12 / 3.0, signed=False)
    # vccbram = FloatRegister(0x3C, bits=12, norm=2 ** 12 / 3.0, signed=False)
    # vccint = FloatRegister(0x40, bits=12, norm=2 ** 12 / 3.0, signed=False)
    # vccaux = FloatRegister(0x44, bits=12, norm=2 ** 12 / 3.0, signed=False)
    # vccddr = FloatRegister(0x48, bits=12, norm=2 ** 12 / 3.0, signed=False)
    #
    # @property
    # def info(self):
    #     return {name: getattr(self, name) for name in [
    #         'vadc0',
    #         'vadc1',
    #         'vadc2',
    #         'vadc3',
    #         'temperature',
    #         'vsupply',
    #         'vccpint',
    #         'vccpaux',
    #         'vccbram',
    #         'vccint',
    #         'vccaux',
    #         'vccddr',
    #     ]}

    def _setup(self): # the function is here for its docstring to be used by the metaclass.
        """
        sets up the AMS (just setting the attributes is OK)
        """
        pass
