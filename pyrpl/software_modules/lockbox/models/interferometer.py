from ..lockbox import *
from ..signals import *


class InterferometerPort1(InputDirect):
    def expected_signal(self, phase):
        phase *= self.lockbox._unit_per_setpoint_unit('rad')
        return self.calibration_data.offset + self.calibration_data.amplitude * np.sin(phase)


class InterferometerPort2(InterferometerPort1):
    def expected_signal(self, phase):
        return super(InterferometerPort2, self).expected_signal(-phase)


class Interferometer(Lockbox):
    wavelength = FloatProperty(max=1., min=0., default=1.064e-6, increment=1e-9)
    _gui_attributes = ['wavelength']
    _setup_attributes = _gui_attributes

    # management of intput/output units
    setpoint_variable = 'phase'
    setpoint_unit = 'deg'
    _output_units = ['V', 'm'] #, 'Hz']
    _rad_per_deg = np.pi/180.0  # only used internally
    @property
    def _m_per_deg(self):
        # factor 2 comes from assumption that beam is reflected off a mirror,
        # i. e. beam gets twice the phaseshift from the displacement
        return self.wavelength / 360.0 * 2.0
    #@property
    #def _Hz_per_deg(self):
    #    return self.free_spectral_range / 360.0

    inputs = LockboxModuleDictProperty(port1=InterferometerPort1,
                                       port2=InterferometerPort2)

    # pdh = InputPdh
    #    port1 = InterferometerPort1 # any attribute of type InputSignal will be instantiated in the model
    #    port2 = InterferometerPort2
    """
    @property
    def phase(self):
        if not hasattr(self, '_phase'):
            self._phase = 0
        return self._phase

    @phase.setter
    def phase(self, val):
        self._phase = val
        return val
    """

class PdhInterferometerPort1(InputIq, InterferometerPort1):
    def expected_signal(self, phase):
        # proportional to the derivative of the signal
        # i.e. sin(phase)+const. -> cos(phase)
        phase *= self.lockbox._unit_per_setpoint_unit('rad')
        return self.calibration_data.amplitude * np.cos(phase)

class PdhInterferometerPort2(InputIq, InterferometerPort2):
    def expected_signal(self, phase):
        # proportional to the derivative of the signal
        # i.e. sin(phase) -> cos(phase) = sin(phase+pi/2)
        phase *= self.lockbox._unit_per_setpoint_unit('rad')
        return - self.calibration_data.amplitude * np.cos(phase)


class PdhInterferometer(Interferometer):
    inputs = LockboxModuleDictProperty(port1=InterferometerPort1,
                                       pdh1=PdhInterferometerPort1)
