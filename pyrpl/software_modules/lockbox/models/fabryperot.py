from ..lockbox import *
from ..signals import *


class FPReflection(InputDirect):
    def expected_signal(self, variable):
        return self.calibration_data.max - (self.calibration_data.max - self.calibration_data.min) * self._lorentz(variable)
    def _lorentz(self, x):
        return 1.0 / (1.0 + x ** 2)

class FPTransmission(FPReflection):
    def expected_signal(self, variable):
        return self.calibration_data.min + (self.calibration_data.max - self.calibration_data.min) * self._lorentz(variable)

class FPAnalogPdh(InputDirect):
    mod_freq = FrequencyProperty()
    _setup_attributes = InputDirect._setup_attributes + ['mod_freq']
    _gui_attributes = InputDirect._gui_attributes + ['mod_freq']

    def expected_signal(self, variable):
        # we neglect offset here because it should really be zero on resonance
        return self.calibration_data.amplitude * self._pdh_normalized(variable,
                                    sbfreq=self.mod_freq/self.lockbox.bandwidth,
                                    phase=0,
                                    eta=self.lockbox.eta)

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


class FPPdh(InputIq, FPAnalogPdh):
    def is_locked(self, loglevel=logging.INFO):
        # simply perform the is_locked with the reflection error signal
        return self.lockbox.is_locked(self.lockbox.inputs.reflection,
                                      loglevel=loglevel)


class FabryPerot(Lockbox):
    units = ['m', 'Hz', 'nm', 'MHz']
    _gui_attributes = ["wavelength", "finesse", "length", "eta"]
    _setup_attributes = _gui_attributes
    wavelength = FloatProperty(max=1., min=0., default=1.064e-6, increment=1e-9)
    finesse = FloatProperty(max=1e7, min=0, default=10000)
    # approximate length in m (not taking into account small variations of the
    # order of the wavelength)
    length = FloatProperty(max=10e12, min=0, default=1.0)
    # eta is the ratio between input mirror transmission and the sum of
    # transmission and loss: T/(T+P)
    eta = FloatProperty(min=0., max=1., default=1.)
    variable = 'detuning'

    inputs = LockboxModuleDictProperty(transmission=FPTransmission,
                                       reflection=FPReflection,
                                       pdh=FPPdh)

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
        curve = super(HighFinesseInput, self).sweep_acquire()
        with self.pyrpl.scopes.pop(self.name) as scope:
            scope.load_state("autosweep")
            if "sweep_zoom" in scope.states:
                scope.load_state("sweep_zoom")
            else:
                scope.duration /= 100
                scope.trigger_source = "ch1_positive_edge"
            threshold = self.get_threshold(curve)
            scope.setup(threshold_ch1=threshold, input1=self.signal())
            self._logger.debug("calibration threshold: %f", threshold)
            scope.save_state("autosweep_zoom") # save state for debugging or modification
            curve1, curve2 = scope.curve(timeout=5./self.lockbox.asg.frequency)  # give some time if trigger is missed
            self.get_stats_from_curve(curve1)
        # log calibration values
        self._logger.info("%s high-finesse calibration successful - "
                          "Min: %.3f  Max: %.3f  Mean: %.3f  Rms: %.3f",
                          self.name,
                          self.min, self.max, self.mean, self.rms)
        # update graph in lockbox
        self.lockbox._signal_launcher.input_calibrated.emit([self])

    def get_threshold(self, curve):
        """ returns a reasonable scope threshold for the interesting part of this curve """
        return (curve.min() + curve.mean()) / 2


class HighFinesseReflection(HighFinesseInput, FPReflection):
    """
    Reflection for a FabryPerot. The only difference with FPReflection is that
    acquire will be done in 2 steps (coarse, then fine)
    """
    pass


class HighFinesseTransmission(HighFinesseInput, FPTransmission):
    """
    Reflection for a FabryPerot. The only difference with FPReflection is that
    acquire will be done in 2 steps (coarse, then fine)
    """
    pass


class HighFinessePdh(HighFinesseInput, FPPdh):
    """
    Reflection for a FabryPerot. The only difference with FPReflection is that
    acquire will be done in 2 steps (coarse, then fine)
    """
    # the signal is the one from pdh (otherwise maybe overwritten by the one from HighFinesseInput)
    #signal = InputPdh.signal


class HighFinesseFabryPerot(FabryPerot):
    _setup_attributes = ["inputs", "sequence"]  # this ensures that sequence is loaded at the very end (i.e. after inputs)

    inputs = LockboxModuleDictProperty(LockboxModule,
                                     transmission=HighFinesseTransmission,
                                     reflection=HighFinesseReflection,
                                     pdh=HighFinessePdh)
