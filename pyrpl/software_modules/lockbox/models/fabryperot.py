from ..signals import *
from ..model import *


class FPTransmission(InputDirect):
    _section_name = 'transmission'

    def expected_signal(self, variable):
        return self.min + (self.max - self.min) * self.model.lorentz(variable)


class FPReflection(InputDirect):
    _section_name = 'reflection'

    def expected_signal(self, variable):
        return self.max - (self.max - self.min) * self.model.lorentz(variable)

class InputAnalogPdh(InputDirect):
    _section_name = 'analog_pdh'
    mod_freq = FrequencyProperty()
    _setup_attributes = InputDirect._setup_attributes + ['mod_freq']
    _gui_attributes = InputDirect._gui_attributes + ['mod_freq']

    def expected_signal(self, variable):
        offset = 0.5 * (self.max + self.min)
        amplitude = 0.5 * (self.max - self.min)
        # we neglect offset here because it should really be zero on resonance
        return amplitude * self._pdh_normalized(variable,
                                    sbfreq=self.mod_freq/self.model.bandwidth,
                                    phase=0,
                                    eta=self.model.eta)

    def _pdh_normalized(self, x, sbfreq=10.0, phase=0, eta=1):
        """  returns a pdh error signal at for a number of detunings x. """
        # pdh only has appreciable slope for detunings between -0.5 and 0.5
        # unless you are using it for very exotic purposes..
        # The incident beam is composed of three laser fields:
        # a at x,
        # 1j*a*rel at x+sbfreq
        # 1j*a*rel at x-sbfreq
        # In the end we will only consider cross-terms so the parameter rel will be normalized out.
        # All three fields are incident on the cavity:
        # eta is ratio between input mirror transmission and total loss (including this transmission),
        # i.e. between 0 and 1. While there is a residual dependence on eta, it is very weak and
        # can be neglected for all practical purposes.
        # intracavity field a_cav, incident field a_in, reflected field a_ref    #
        # a_cav(x) = a_in(x)*sqrt(eta)/(1+1j*x)
        # a_ref(x) = -1 + eta/(1+1j*x)
        def a_ref(x):
            """complex lorentzian reflection"""
            return 1 - eta / (1 + 1j * x)
        # reflected intensity = abs(sum_of_reflected_fields)**2
        # components oscillating at sbfreq: cross-terms of central lorentz with either sideband
        i_ref = np.conjugate(a_ref(x)) * 1j * a_ref(x + sbfreq) \
                + a_ref(x) * np.conjugate(1j * a_ref(x - sbfreq))
        # we demodulate with phase phi, i.e. multiply i_ref by e**(1j*phase), and take the real part
        # normalization constant is very close to 1/eta
        return np.real(i_ref * np.exp(1j * phase)) / eta


class InputPdh(InputIq, InputAnalogPdh):
    _section_name = 'pdh'

    def is_locked(self, loglevel=logging.INFO):
        # simply perform the is_locked with the reflection error signal
        return self.lockbox.is_locked(self.lockbox.reflection,
                                      loglevel=loglevel)


class FabryPerot(Model):
    name = "FabryPerot"
    _section_name = "fabryperot"
    units = ['m', 'Hz', 'nm', 'MHz']
    _setup_attributes = ["wavelength", "finesse", "length", 'eta']
    _gui_attributes = _setup_attributes
    wavelength = FloatProperty(max=10000, min=0, default=1.064e-6)
    finesse = FloatProperty(max=1e7, min=0, default=10000)
    # approximate length (not taking into account small variations of the
    # order of the wavelength)
    length = FloatProperty(max=10e12, min=0, default=1.0)
    # eta is the ratio between input mirror transmission and the sum of
    # transmission and loss: T/(T+P)
    eta = FloatProperty(min=0., max=1., default=1.)
    variable = 'detuning'

    input_cls = [FPTransmission, FPReflection]#, InputPdh]

    def lorentz(self, x):
        return 1.0 / (1.0 + x ** 2)

    @property
    def free_spectral_range(self):
        return 2.998e8/(2.*self.length)

    @property
    def linewidth(self):
        return self.free_spectral_range / self.finesse

    @property
    def bandwidth(self):
        return self.linewidth/2.0



class HighFinesseInput(InputDirect):
    """
    Since the number of points in the scope is too small for high finesse cavities, the acquisition is performed in
    2 steps:
        1. Full scan with the actuator, full scope duration, trigged on asg
        2. Full scan with the actuator, smaller scope duration, trigged on input (level defined by previous scan).
    Scope states corresponding to 1 and 2 are "sweep" and "sweep_zoom"
    """

    def calibrate(self):
        print("high-finesse calibrate")
        curve = super(HighFinesseInput, self).acquire()
        scope = self.pyrpl.scopes.pop(self.name)
        try:
            if not "sweep_zoom" in scope.states:
                scope.duration /= 100
                scope.trigger_source = "ch1_positive_edge"
                scope.save_state("sweep_zoom")
            else:
                scope.load_state("sweep_zoom")
            threshold = self.get_threshold(curve)
            scope.setup(threshold_ch1=threshold, input1=self.signal())
            print(threshold)
            curve = scope.curve()
            self.get_stats_from_curve(curve)
        finally:
            self.pyrpl.scopes.free(scope)
        if self._widget is not None:
            self.update_graph()

    def get_threshold(self, curve):
        return (curve.min() + curve.mean()) / 2


class HighFinesseReflection(HighFinesseInput, FPReflection):
    """
    Reflection for a FabryPerot. The only difference with FPReflection is that
    acquire will be done in 2 steps (coarse, then fine)
    """
    _section_name = 'hf_reflection'
    pass


class HighFinesseTransmission(HighFinesseInput, FPTransmission):
    """
    Reflection for a FabryPerot. The only difference with FPReflection is that
    acquire will be done in 2 steps (coarse, then fine)
    """
    _section_name = 'hf_transmission'
    pass


class HighFinessePdh(HighFinesseInput, InputPdh):
    """
    Reflection for a FabryPerot. The only difference with FPReflection is that
    acquire will be done in 2 steps (coarse, then fine)
    """
    _section_name = 'hf_pdh'
    signal = InputPdh.signal


class HighFinesseFabryPerot(FabryPerot):
    name = "HighFinesseFP"
    _section_name = "high_finesse_fp"
    input_cls = [HighFinesseReflection, HighFinesseTransmission,
                 HighFinessePdh]


class PTempProperty(FloatProperty):
    def set_value(self, module, val):
        super(PTempProperty, self).set_value(module, val)
        module.pid_temp.p = val


class ITempProperty(FloatProperty):
    def set_value(self, module, val):
        super(ITempProperty, self).set_value(module, val)
        module.pid_temp.i = val


class FabryPerotTemperatureControlOld(FabryPerot):
    # optional
    # input_cls = [HighFinesseReflection, HighFinesseTransmission,
    #             HighFinessePdh]
    name = "FabryPerotTemperatureControlOld"
    _gui_attributes = ["wavelength", "finesse", "length", 'eta'] \
                      + ['p_temp', 'i_temp']
    _setup_attributes = _gui_attributes
    p_temp = FloatProperty(max=1e6, min=-1e6)
    i_temp = FloatProperty(max=1e6, min=-1e6)

    def _init_module(self):
        self.pid_temp = self.pyrpl.pids.pop('temperature_control')
        self.pwm_temp = self.pyrpl.rp.pwm1
        self.pwm_temp.input = self.pid_temp
        self.unlock_temperature(1.)

    def lock_temperature(self, factor):
        self.pid_temp.output_direct = 'off'
        self.pid_temp.input = "out1"
        self.pid_temp.p = self.p_temp
        self.pid_temp.i = self.i_temp
        self.pid_temp.inputfilter = [10, 100, 100, 100]

    def unlock_temperature(self, factor):
        self.pid_temp.output_direct = 'off'
        self.pid_temp.ival = 0
        self.pid_temp.p = 0
        self.pid_temp.i = 0

class FabryPerotTemperatureControl(FabryPerot):
    name = "FabryPerotTemperatureControl"
    input_cls = FabryPerot.input_cls + [InputFromOutput]

    def lock_temperature(self, factor):
        self.pyrpl.lockbox.out_temp.lock(
            input='input_from_output',
            variable_value=0)
