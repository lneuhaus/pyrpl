from pyrpl.software_modules.lockbox.signal import Signal

from . import *
from ..pyrpl_utils import sleep

import logging

logger = logging.getLogger(name=__name__)


class FabryPerotTemperatureControl(Model):
    """
    Model for a Fabry-Perot cavity in lorentzian approximation
    with temperature control with PWM output
    """

    # the internal variable for state specification
    _variable = 'detuning'

    gui_buttons = Model.gui_buttons + ["zoom"]

    export_to_parent = Model.export_to_parent + ['R0', 'relative_pdh_rms']

    # lorentzian functions
    def _lorentz(self, x):
        return 1.0 / (1.0 + x ** 2)

    def _lorentz_slope(self, x):
        return -2.0*x / (1.0 + x ** 2)**2

    def _lorentz_slope_normalized(self, x):
        # max slope occurs at x +- 1/sqrt(3)
        return self._lorentz_slope(x) / \
               np.abs(self._lorentz_slope(1/np.sqrt(3)))

    def _lorentz_slope_slope(self, x):
        return (-2.0+6.0*x**2) / (1.0 + x ** 2)**3

    def _lorentz_slope_normalized_slope(self, x):
        """ slope of normalized slope (!= normalized slope of slope) """
        return (-2.0+6.0*x**2) / (1.0 + x ** 2)**3  \
               / abs(self._lorentz_slope(np.sqrt(3)))

    def _pdh_normalized(self, x, sbfreq=10.0, phase=0, eta=1):
        # pdh only has appreciable slope for detunings between -0.5 and 0.5
        # unless you are using it for very exotic purposes..
        # incident beam: laser field
        # a at x,
        # 1j*a*rel at x+sbfreq
        # 1j*a*rel at x-sbfreq
        # in the end we will only consider cross-terms so the parameter rel will be normalized out
        # all three fields incident on cavity
        # eta is ratio between input mirror transmission and total loss (including this transmission),
        # i.e. between 0 and 1. While there is a residual dependence on eta, it is very weak and
        # can be neglected for all practical purposes.
        # intracavity field a_cav, incident field a_in, reflected field a_ref    #
        # a_cav(x) = a_in(x)*sqrt(eta)/(1+1j*x)
        # a_ref(x) = -1 + eta/(1+1j*x)
        def a_ref(x):
            return 1 - eta / (1 + 1j * x)

        # reflected intensity = abs(sum_of_reflected_fields)**2
        # components oscillating at sbfreq: cross-terms of central lorentz with either sideband
        i_ref = np.conjugate(a_ref(x)) * 1j * a_ref(x + sbfreq) \
                + a_ref(x) * np.conjugate(1j * a_ref(x - sbfreq))
        # we demodulate with phase phi, i.e. multiply i_ref by e**(1j*phase), and take the real part
        # normalization constant is very close to 1/eta
        return np.real(i_ref * np.exp(1j * phase)) / eta

    def transmission(self, x):
        " transmission of the Fabry-Perot "
        return self._lorentz(x) * self._config.resonant_transmission

    def reflection(self, x):
        " reflection of the Fabry-Perot"
        offres = self._config.offresonant_reflection
        res = self._config.resonant_reflection
        return (res-offres) * self._lorentz(x) + offres

    def pdh(self, x):
        sbfreq = self.signals["pdh"]._config.setup.frequency \
                 * self.detuning_per_Hz
        return self._pdh_normalized(x, sbfreq=sbfreq) \
               * self._config.peak_pdh

    @property
    def R0(self):
        " reflection coefficient on resonance "
        return self._config.resonant_reflection / \
               self._config.offresonant_reflection

    @property
    def T0(self):
        " transmission coefficient on resonance "
        return self._config.resonant_reflection / \
               self._config.offresonant_reflection

    @property
    def detuning_per_m(self):
        " detuning of +-1 corresponds to the half-maximum intracavity power "
        linewidth = self._config.wavelength / 2 / self._config.finesse
        return 1.0 / (linewidth / 2)

    @property
    def detuning_per_Hz(self):
        " detuning of +-1 corresponds to the half-maximum intracavity power "
        fsr = 2.99792458e8 / 2 / self._config.length
        linewidth = fsr / self._config.finesse
        return 1.0 / (linewidth / 2)

    @property
    def detuning(self):
        detuning = self.variable
        # force the sign of detuning to be the right one,
        # because reflection and transmission are even functions
        if self.state['set']['detuning'] * detuning < 0:
            self.logger.debug("Detuning estimation converged to wrong sign. "
                              "Sign was corrected. ")
            return detuning * -1
        else:
            return detuning

    def lock(self,
             detuning=None,
             factor=None,
             firststage=None,
             laststage=None,
             thread=False):
        ### This function is almost a one-to-one duplicate of Model.lock (
        # except for the **kwargs that is read online). This is a major
        # source of bug !!!!

        # firststage will allow timer-based recursive iteration over stages
        # i.e. calling lock(firststage = nexstage) from within this code
        stages = self._config.lock.stages._keys()
        if firststage:
            if not firststage in stages:
                self.logger.error("Firststage %s not found in stages: %s",
                                  firstage, stages)
            else:
                stages = stages[stages.index(firststage):]
        for stage in stages:
            self.logger.debug("Lock stage: %s", stage)
            self.current_stage = stage
            self.stage_changed_hook(stage)  # Some hook function
            if stage.startswith("call_"):
                try:
                    lockfn = self.__getattribute__(stage[len('call_'):])
                except AttributeError:
                    logger.error("Lock stage %s: model has no function %s.",
                                 stage, stage[len('call_'):])
                    raise
            else:
                # use _lock by default
                lockfn = self._lock
            parameters = dict(detuning=detuning, factor=factor)
            parameters.update((self._config.lock.stages[stage]))
            try:
                stime = parameters.pop("time")
            except KeyError:
                stime = 0
            if stage == laststage or stage == stages[-1]:
                if detuning:
                    parameters['detuning'] = detuning
                if factor:
                    parameters['factor'] = factor
                try:
                    return lockfn(**parameters)
                except TypeError:  # function doesnt accept kwargs
                    raise
                    return lockfn()

            else:
                if thread:
                    # immediately execute current step (in another thread)
                    t0 = threading.Timer(0,
                                         lockfn,
                                         kwargs=parameters)
                    t0.start()  # bug here: lockfn must accept kwargs
                    # and launch timer for nextstage
                    nextstage = stages[stages.index(stage) + 1]
                    t1 = threading.Timer(stime,
                                         self.lock,
                                         kwargs=dict(
                                             detuning=detuning,
                                             factor=factor,
                                             firststage=nextstage,
                                             laststage=laststage,
                                             thread=thread))
                    t1.start()
                    return None
                else:
                    try:
                        lockfn(**parameters)
                    except TypeError:  # function doesnt accept kwargs
                        lockfn()
                    sleep(stime) #time.## Changed to pyrpl_utils.sleep,
                    #  which basically doesn't freeze the gui

    def save_current_gain(self, outputs=None):
        """saves the current gain setting as default one (for all outputs
        unless a list of outputs is given, similar to _lock) """

        self._lock(outputs=outputs, _savegain=True, detuning=self.state[
            'set']['detuning'])

    def calibrate(self, inputs=None, scopeparams={}):
        """
        Calibrates by performing a sweep as defined for the outputs and
        recording and saving min and max of each input. Then zooms in by
        triggering a shorter acquisition on the error signal and finishes by
        defining the extracted parameters for each of the scanned error
        signals. See config file example for configuration.

        Parameters
        -------
        inputs: list
            list of input signals to calibrate. All inputs are used if None.
        scopeparams: dict
            optional parameters for signal acquisition during calibration
            that are temporarily written to _config

        Returns
        -------
        curves: list
            list of all acquired curves
        """
        # decide which secondary signal is to be recorded along the input
        if 'secondsignal' not in scopeparams:
            # automatically find the first sweeping output
            for o in self.outputs.values():
                if 'sweep' in o._config._keys():
                    scopeparams['secondsignal'] = o._name
                    break
        # coarse calibration as defined in model
        coarsecurves = super(FabryPerot, self).calibrate(inputs, scopeparams)
        # zoom in - basically another version of calibrate with zoom factors
        # and triggering on the signal
        duration = coarsecurves[0].params["duration"]  # for zooming
        if inputs is None:
            inputs = self.inputs.values()  # all inputs by default
        curves = []
        for sig in inputs:
            if not isinstance(sig, Signal):
                sig = self.signals[sig]
            sigscopeparams = dict(scopeparams)
            sigscopeparams.update({
                    'trigger_source': 'ch1_positive_edge',
                    'threshold': sig._config.max *
                              self._config.calibrate.relative_threshold,
                    'duration': duration
                              * self._config.calibrate.zoomfactor,
                    'timeout': duration*10})
            curves += super(FabryPerot, self).calibrate(
                inputs=[sig], scopeparams=sigscopeparams)
            if sig._name == 'reflection':
                self._config["offresonant_reflection"] = sig._config.max
                self._config["resonant_reflection"] = sig._config.min
            if sig._name == 'transmission':
                self._config["resonant_transmission"] = sig._config.max
            if sig._name == 'pdh':
                self._config["peak_pdh"] = (sig._config.max - sig._config.min)/2
            if sig._name == 'lmsd':
                sig._config.peak = (sig._config.max - sig._config.min)/2
        for c in curves:
            for cc in coarsecurves:
                if cc.name == c.name:
                    c.add_child(cc)
        return curves

    def setup_pdh(self, **kwargs):
        return super(FabryPerot, self).setup_iq(inputsignal='pdh', **kwargs)

    def sweep(self):
        duration = super(FabryPerot, self).sweep()
        self._parent.rp.scope.setup(trigger_source='asg1',
                                    duration=duration)
        if "scopegui" in self._parent.c._dict:
            if self._parent.c.scopegui.auto_run_continuous:
                self._parent.rp.scope_widget.run_continuous()

    def zoom(self):
        dur = self.sweep()
        scope = self._parent.rp.scope
        curve = scope.curve()
        curve_pos_times = curve[len(curve)/2:]
        scope.trigger_delay = scope.times[len(curve)/2 + curve_pos_times.argmax()]
        scope.duration = scope.duration*10/self._config.finesse
        self._parent.rp.scope_widget.run_continuous()

    def relative_reflection(self):
        self.inputs["reflection"]._acquire()
        return self.inputs["reflection"].mean / self.reflection(1000)

    def relative_pdh_rms(self, avg=50):
        """ Returns the pdh rms normalized by the peak amplitude of pdh.
        With fpm cavity settings (typical), avg=50 yields values that
        scatter less than a percent. Best way to optimize a pdh lock.

        Parameters
        ----------
        avg: int
            number of traces to average over

        Returns
        -------
        rms normalized by amplitude of pdh error signal. For a full-scale
        oscillation of a pdh error signal, one finds typical values of the
        order of sqrt(2)/2 = 0.71, while a good lock has values typically
        below 10 percent.
        """
        if avg > 1:
            sum = 0
            for i in range(avg):
                sum += self.relative_pdh_rms(avg=1)**2
            return np.sqrt(sum/avg)
        else:
            self.signals["pdh"]._acquire()
            rms = self.signals["pdh"].rms
            relrms = rms / self._config.peak_pdh
            if hasattr(self, '_pdh_rms_log'):
                # this is a logger for the lock quality. It must be
                # implemented by the user to fit into the local existing
                # datalogging architecture.
                self._pdh_rms_log.log(relrms)
            return relrms

    def islocked(self):
        """ returns True if cavity is locked """
        input = None
        for i in self.inputs.keys():
            if i == "reflection" or i == "transmission":
                input = i
                break
        if input is None:
            raise KeyError("No transmission or reflection signal found.")
        self.inputs[input]._acquire()
        mean = self.inputs[input].mean
        set = abs(self.state["set"][self._variable])
        error_threshold = self._config.lock.error_threshold
        thresholdvalue = self.__getattribute__(input)(set + error_threshold)
        if input == "reflection":
            return (mean <= thresholdvalue)
        else:
            return (mean >= thresholdvalue)

