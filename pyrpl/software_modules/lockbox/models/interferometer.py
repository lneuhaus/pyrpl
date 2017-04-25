from .. import *


class InterferometerPort1(InputDirect):
    @property
    def plot_range(self):
        maxval = np.pi*self.lockbox._unit_in_setpoint_unit('rad')
        return np.linspace(-maxval, maxval, 200)

    def expected_signal(self, phase):
        phase *= self.lockbox._setpoint_unit_in_unit('rad')
        return self.calibration_data.offset + self.calibration_data.amplitude * np.sin(phase)

    def expected_setpoint(self, transmission):
        sinvalue = (transmission - self.calibration_data.offset) / self.calibration_data.amplitude
        if sinvalue > 1.0:
            sinvalue = 1.0
        elif sinvalue < -1.0:
            sinvalue = -1.0
        phase = np.arcsin(sinvalue)
        phase /= self.lockbox._setpoint_unit_in_unit('rad')
        return phase


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

    _output_units = ['m', 'nm']
    # must provide conversion from setpoint_unit into all other basic units
    # management of intput/output units
    _rad_in_deg = 180.0 / np.pi  # only internally needed

    @property
    def _deg_in_m(self):
        # factor 2 comes from assumption that beam is reflected off a mirror,
        # i. e. beam gets twice the phaseshift from the displacement
        return self.wavelength / 360.0 / 2.0

    @property
    def _rad_in_m(self):
        # factor 2 comes from assumption that beam is reflected off a mirror,
        # i. e. beam gets twice the phaseshift from the displacement
        return self._rad_in_deg * self._deg_in_m

    inputs = LockboxModuleDictProperty(port1=InterferometerPort1,
                                       port2=InterferometerPort2)

    outputs = LockboxModuleDictProperty(piezo=PiezoOutput)
                                        #piezo2=PiezoOutput)


class PdhInterferometerPort1(InterferometerPort1, InputIq):
    def expected_signal(self, phase):
        # proportional to the derivative of the signal
        # i.e. sin(phase)+const. -> cos(phase)
        phase *= self.lockbox._setpoint_unit_in_unit('rad')
        return self.calibration_data.amplitude * np.cos(phase)


class PdhInterferometerPort2(InterferometerPort2, InputIq):
    def expected_signal(self, phase):
        # proportional to the derivative of the signal
        # i.e. sin(phase) -> cos(phase) = sin(phase+pi/2)
        phase *= self.lockbox._setpoint_unit_in_unit('rad')
        return - self.calibration_data.amplitude * np.cos(phase)


class PdhInterferometer(Interferometer):
    inputs = LockboxModuleDictProperty(port1=InterferometerPort1,
                                       pdh1=PdhInterferometerPort1)
