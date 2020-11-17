from .. import *
from .interferometer import Interferometer
from ....async_utils import TimeoutError

class Lorentz(object):
    """ base class for Lorentzian-like signals"""
    def _lorentz(self, x):
        """ lorentzian function """
        return 1.0 / (1.0 + x ** 2)

    def _lorentz_complex(self, x):
        """ complex-valued lorentzian function """
        return 1.0 / (1.0 + 1.0j * x)

    def _lorentz_slope(self, x):
        """ derivative of _lorentz"""
        return -2.0 * x * self._lorentz(x) ** 2

    def _lorentz_slope_normalized(self, x):
        """ derivative of _lorentz with maximum of 1.0 """
        return self._lorentz_slope(x) / np.abs(self._lorentz_slope(1.0 / np.sqrt(3)))

    def _lorentz_slope_slope(self, x):
        """ second derivative of _lorentz """
        return (-2.0 + 6.0 * x ** 2) * self._lorentz(x) ** 3


class FPReflection(InputSignal, Lorentz):
    def expected_signal(self, setpoint):
        detuning = setpoint * self.lockbox._setpoint_unit_in_unit('bandwidth')
        return self.calibration_data.max - (self.calibration_data.max -
                                            self.calibration_data.min) * \
                                           self._lorentz(detuning)

    # 'relative' scale of 100% is given by offresonant reflection, 0% by dark reflection (=0)
    @property
    def relative_mean(self):
        """
        returns the ratio between the measured mean value and the expected one.
        """
        # compute relative quantity
        return self.mean / self.calibration_data.max

    @property
    def relative_rms(self):
        """
        returns the ratio between the measured rms value and the expected mean.
        """
        # compute relative quantity
        return self.rms / self.calibration_data.max


class FPTransmission(FPReflection):
    def expected_signal(self, setpoint):
        detuning = setpoint * self.lockbox._setpoint_unit_in_unit('bandwidth')
        return self.calibration_data.min + (self.calibration_data.max -
                                            self.calibration_data.min) * \
                                            self._lorentz(detuning)


class FPAnalogPdh(InputSignal, Lorentz):
    mod_freq = FrequencyProperty()
    _setup_attributes = InputDirect._setup_attributes + ['mod_freq']
    _gui_attributes = InputDirect._gui_attributes + ['mod_freq']

    def is_locked(self, loglevel=logging.INFO):
        # simply perform the is_locked with the reflection error signal
        return self.lockbox.inputs.reflection.is_locked(loglevel=loglevel)

    def expected_signal(self, setpoint):
        # we neglect offset here because it should really be zero on resonance
        detuning = setpoint * self.lockbox._setpoint_unit_in_unit('bandwidth')
        return self.calibration_data.amplitude * self._pdh_normalized(detuning,
                                    sbfreq=self.mod_freq
                                           / self.lockbox._bandwidth_in_Hz,
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
            return 1.0 - eta * self._lorentz_complex(x)
        # reflected intensity = abs(sum_of_reflected_fields)**2
        # components oscillating at sbfreq: cross-terms of central lorentz with either sideband
        i_ref = np.conjugate(a_ref(x)) * 1j * a_ref(x + sbfreq) \
                + a_ref(x) * np.conjugate(1j * a_ref(x - sbfreq))
        # we demodulate with phase phi, i.e. multiply i_ref by e**(1j*phase), and take the real part
        # normalization constant is very close to 1/eta
        return np.real(i_ref * np.exp(1j * phase)) / eta


class FPPdh(InputIq, FPAnalogPdh):
    """ Same as analog pdh signal, but generated from IQ module """
    pass


class FPTilt(InputSignal, Lorentz):
    """ Error signal for tilt-locking schemes, e.g.
    https://arxiv.org/pdf/1410.8773.pdf """
    def _tilt_normalized(self, detuning):
        """ do the math and you'll see that the tilt error signal is simply
        the derivative of the cavity lorentzian"""
        return self._lorentz_slope_normalized(detuning)

    def expected_signal(self, setpoint):
        """ expected error signal is centered around zero on purpose"""
        detuning = setpoint * self.lockbox._setpoint_unit_in_unit('bandwidth')
        return self.calibration_data.amplitude * self._tilt_normalized(detuning)

    def is_locked(self, loglevel=logging.INFO):
        # simply perform the is_locked with the reflection error signal since
        # error signal is zero on resonance
        return self.lockbox.inputs.reflection.is_locked(loglevel=loglevel)


class FabryPerot(Interferometer):
    _gui_attributes = ["finesse", "round_trip_length", "eta"]
    _setup_attributes = _gui_attributes

    inputs = LockboxModuleDictProperty(transmission=FPTransmission,
                                       reflection=FPReflection,
                                       pdh=FPPdh)

    finesse = FloatProperty(max=1e7, min=0, default=10000)
    # approximate length in m (not taking into account small variations of the
    # order of the wavelength)
    round_trip_length = FloatProperty(max=10e12, min=0, default=1.0)
    # eta is the ratio between input mirror transmission and the sum of
    # transmission and loss: T/(T+P)
    eta = FloatProperty(min=0., max=1., default=1.)

    @property
    def free_spectral_range(self):
        """ returns the cavity free spectral range in Hz """
        return 2.998e8 / self.round_trip_length

    # management of intput/output units
    # setpoint_variable = 'detuning'
    setpoint_unit = SelectProperty(options=['bandwidth',
                                            'linewidth',
                                            'rel_reflection'],
                                   default='bandwidth',
                                   doc="""
                               Unit in which the setpoint of the lock is given: "
                               - linewidth: FWHM"
                               - bandwidth: HWHM"
                               """)
    # TODO: implement these nonlinear conversions, requires modified logic
    # - rel_reflection: 0=resonance, 1=infintely far away, negative=other side of the resonance
    #- rel_transmission: 1=resonance, 0=infinitely far away, negative=other side of the resonance

    _output_units = ['V', 'm', 'Hz', 'nm', 'MHz']

    # must provide conversion from setpoint_unit into all other basic units
    @property
    def _linewidth_in_m(self):
        return self.wavelength / self.finesse / 2.0

    @property
    def _linewidth_in_Hz(self):
        return self.free_spectral_range / self.finesse

    @property
    def _bandwidth_in_Hz(self):
        return self._linewidth_in_Hz / 2.0

    @property
    def _bandwidth_in_m(self):
        # linewidth (in m) = lambda/(2*finesse)
        # bandwidth = linewidth/2
        return self._linewidth_in_m / 2.0


class HighFinesseInput(InputSignal):
    """
    Since the number of points in the scope is too small for high finesse cavities, the acquisition is performed in
    2 steps:
        1. Full scan with the actuator, full scope duration, trigged on asg
        2. Full scan with the actuator, smaller scope duration, trigged on input (level defined by previous scan).
    Scope states corresponding to 1 and 2 are "sweep" and "sweep_zoom"
    """
    def sweep_acquire_zoom(self, threshold, input2=None):
        try:
            with self.pyrpl.scopes.pop(self.name) as scope:
                self.lockbox.unlock()  # turn off sweep
                scope.load_state("autosweep")
                if "sweep_zoom" in scope.states:
                    scope.load_state("sweep_zoom")
                else:
                    # zoom by finesse/20
                    scope.duration /= (self.lockbox.finesse/20.0)
                    scope.trigger_source = "ch1_negative_edge"
                    scope.hysteresis = 0.002
                    scope.trigger_delay = 0.0
                scope.setup(threshold=threshold,
                            input1=self.signal())
                if input2 is not None:
                    scope.input2 = input2
                scope.save_state("autosweep_zoom")  # save state for debugging or modification
                self._logger.debug("calibration threshold: %f", threshold)
                curves = scope.curve_async()
                self.lockbox._sweep()  # start sweep only after arming the scope
                # give some extra (10x) timeout time in case the trigger is missed
                try:
                    curve1, curve2 = curves.await_result(timeout=100./self.lockbox.asg.frequency+scope.duration)
                except TimeoutError:
                    # scope is blocked
                    self._logger.warning("Signal %s could not be calibrated because no trigger was detected while "
                                         "sweeping the cavity before the expiration of a timeout of %.1e s!",
                                         self.name, 100./self.lockbox.asg.frequency+scope.duration)
                    return None, None, None
                times = scope.times
                self.calibration_data._asg_phase = self.lockbox.asg.scopetriggerphase
                return curve1, curve2, times
        except InsufficientResourceError:
            # scope is blocked
            self._logger.warning("No free scopes left for sweep_acquire_zoom. ")
            return None, None, None

    def calibrate(self, autosave=False):
        # take a first coarse calibration for trigger threshold estimation
        curve0, _ = super(HighFinesseInput, self).sweep_acquire()
        if curve0 is None:
            self._logger.warning('Aborting calibration because no scope is available...')
            return None
        curve1, _, times = self.sweep_acquire_zoom(
            threshold=self.get_threshold(curve0))
        curve1 -= self.calibration_data._analog_offset
        self.calibration_data.get_stats_from_curve(curve1)
        # log calibration values
        self._logger.info("%s high-finesse calibration successful - "
                          "Min: %.3f  Max: %.3f  Mean: %.3f  Rms: %.3f",
                          self.name,
                          self.calibration_data.min,
                          self.calibration_data.max,
                          self.calibration_data.mean,
                          self.calibration_data.rms)
        # update graph in lockbox
        self.lockbox._signal_launcher.input_calibrated.emit([self])
        if autosave:
            params = self.calibration_data.setup_attributes
            params['name'] = self.name + "_calibration"
            newcurve = self._save_curve(times, curve1, **params)
            self.calibration_data.curve = newcurve
            return newcurve
        else:
            return None

    def get_threshold_empirical(self, curve):
        """ returns a reasonable scope threshold for the interesting part of this curve """
        calibration_params = self.calibration_data.setup_attributes
        self.calibration_data.get_stats_from_curve(curve)
        threshold = self.expected_signal(1.0*self.lockbox._unit_in_setpoint_unit('bandwidth'))
        self.calibration_data.setup_attributes = calibration_params
        return threshold

    def get_threshold_theoretical(self, curve):
        """ returns a reasonable scope threshold for the interesting part of this curve """
        calibration_params = self.calibration_data.setup_attributes
        self.calibration_data.get_stats_from_curve(curve)
        eta = max(0.0, min(self.lockbox.eta, 1.0))
        self.calibration_data.min = (1.0-eta) * self.calibration_data.max
        threshold = self.expected_signal(1.0*self.lockbox._unit_in_setpoint_unit('bandwidth'))
        self.calibration_data.setup_attributes = calibration_params
        return threshold

    get_threshold = get_threshold_empirical


class HighFinesseReflection(HighFinesseInput, FPReflection):
    """
    Reflection for a FabryPerot. The only difference with FPReflection is that
    acquire will be done in 2 steps (coarse, then fine)
    """
    pass


class HighFinesseTransmission(HighFinesseInput, FPTransmission):
    pass

class HighFinesseAnalogPdh(HighFinesseInput, FPAnalogPdh):
    def calibrate(self, trigger_signal="reflection", autosave=False):
        trigger_signal = self.lockbox.inputs[trigger_signal]
        # take a first coarse calibration for trigger threshold estimation
        curve0, _ = trigger_signal.sweep_acquire()
        if curve0 is None:
            self._logger.warning('Aborting calibration because no scope is available...')
            return None
        # take the zoomed trace by triggering on the trigger_signal
        curve1, curve2, times = trigger_signal.sweep_acquire_zoom(
            threshold=trigger_signal.get_threshold(curve0),
            input2=self.signal())
        curve1 -= trigger_signal.calibration_data._analog_offset
        curve2 -= self.calibration_data._analog_offset
        self.calibration_data.get_stats_from_curve(curve2)
        self.calibration_data._asg_phase = trigger_signal.calibration_data._asg_phase
        # log calibration values
        self._logger.info("%s high-finesse calibration successful - "
                          "Min: %.3f  Max: %.3f  Mean: %.3f  Rms: %.3f",
                          self.name,
                          self.calibration_data.min,
                          self.calibration_data.max,
                          self.calibration_data.mean,
                          self.calibration_data.rms)
        # update graph in lockbox
        self.lockbox._signal_launcher.input_calibrated.emit([self])
        if autosave:
            # pdh curve
            params = self.calibration_data.setup_attributes
            params['name'] = self.name + "_calibration"
            newcurve = self._save_curve(times, curve2, **params)
            # trigger signal curve
            params = trigger_signal.calibration_data.setup_attributes
            params['name'] = trigger_signal.name + "_calibration"
            trigcurve = self._save_curve(times, curve1, **params)
            newcurve.add_child(trigcurve)
            self.calibration_data.curve = newcurve
            return newcurve
        else:
            return None

class HighFinessePdh(HighFinesseAnalogPdh, FPPdh):
    pass


class HighFinesseFabryPerot(FabryPerot):
    _setup_attributes = ["inputs", "sequence"]
    # this ensures that sequence is loaded at the very end (i.e. after inputs)

    inputs = LockboxModuleDictProperty(transmission=HighFinesseTransmission,
                                       reflection=HighFinesseReflection,
                                       pdh=HighFinessePdh)
