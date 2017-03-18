from ..lockbox import *
from ..signals import *


class InterferometerPort1(InputDirect):
    def expected_signal(self, phase):
        phase *= self.lockbox._setpoint_unit_in_unit('rad')
        return self.calibration_data.offset + self.calibration_data.amplitude * np.sin(phase)


class InterferometerPort2(InterferometerPort1):
    def expected_signal(self, phase):
        return super(InterferometerPort2, self).expected_signal(-phase)


class Interferometer(Lockbox):
    wavelength = FloatProperty(max=1., min=0., default=1.064e-6, increment=1e-9)
    _gui_attributes = ['wavelength']
    _setup_attributes = _gui_attributes

    # management of intput/output units
    # setpoint_variable = 'phase'
    setpoint_unit = SelectProperty(options=['deg',
                                            'rad'],
                                   default='deg')

    _output_units = ['V', 'm', 'nm']
    # must provide conversion from setpoint_unit into all other basic units
    # management of intput/output units
    @property
    def _deg_in_m(self):
        # factor 2 comes from assumption that beam is reflected off a mirror,
        # i. e. beam gets twice the phaseshift from the displacement
        return 2.0 * 360.0 / self.wavelength

    @property
    def _rad_in_m(self):
        # factor 2 comes from assumption that beam is reflected off a mirror,
        # i. e. beam gets twice the phaseshift from the displacement
        return 2.0 * 2.0 * np.pi / self.wavelength

    inputs = LockboxModuleDictProperty(port1=InterferometerPort1,
                                       port2=InterferometerPort2)


class PdhInterferometerPort1(InputIq, InterferometerPort1):
    def expected_signal(self, phase):
        # proportional to the derivative of the signal
        # i.e. sin(phase)+const. -> cos(phase)
        phase *= self.lockbox._setpoint_unit_in_unit('rad')
        return self.calibration_data.amplitude * np.cos(phase)

class PdhInterferometerPort2(InputIq, InterferometerPort2):
    def expected_signal(self, phase):
        # proportional to the derivative of the signal
        # i.e. sin(phase) -> cos(phase) = sin(phase+pi/2)
        phase *= self.lockbox._setpoint_unit_in_unit('rad')
        return - self.calibration_data.amplitude * np.cos(phase)


class PdhInterferometer(Interferometer):
    inputs = LockboxModuleDictProperty(port1=InterferometerPort1,
                                       pdh1=PdhInterferometerPort1)
