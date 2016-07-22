import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *
from ..curvedb import CurveDB
from .. import fitting
from pyqtgraph.Qt import QtCore
from pyinstruments.datalogger.models import SensingDevice

class FPM(FabryPerot):
    """ custom class for the measurement fabry perot of the ZPM experiment """

    export_to_parent = FabryPerot.export_to_parent \
                       + ["relative_pdh_rms", "relative_reflection",
                          "setup_ringdown", "teardown_ringdown", "sweep"]

    def setup(self):
        super(FPM, self).setup()
        # compatibility with other code
        self._parent.constants = self._parent.c.constants

    def setup_pdh(self, **kwargs):
        o = self.outputs["slow"]
        o.output_offset = o._config.lastoffset

        # instantiate the function generator for pdh - may take a few tries..
        from pyinstruments.pyhardwaredb import instrument
        from visa import VisaIOError
        signal = self.inputs["pdh"]
        pdh_instrument = signal._config.setup.generator
        for i in range(5):
            try:
                self._generator = instrument(pdh_instrument)
            except VisaIOError:
                self.logger.warning("VI_ERROR_IO occured with " \
                      + pdh_instrument + \
                      " again in attempt %d. Trying again...", i)
            else:
                break
        from pyinstruments.datalogger.models import SensingDevice
        self._coarse_voltage_log = SensingDevice(
            name="fpm_2p_coarse[V]")  # logbook for coarse voltage to estimate drift rates for example
        self._pdh_rms_log = SensingDevice(
            name="pdh_rms_rel")  # logbook for pdh rms
        self._enable_pdh()

    @property
    def pdh_enabled(self):
        self._generator.channel_idx = 1
        return self._generator.output_enabled

    def _enable_pdh(self, phase=None, frequency=None):
        signal = self.inputs["pdh"]
        if phase is None:
            phase = signal._config.setup.phase
        phase = phase % 360.0
        if frequency is None:
            frequency = signal._config.setup.frequency
        if not self.pdh_enabled or phase != self._generator.phase\
                or frequency != self._generator.frequency:
            self._generator.recall(1)
            self._generator.phaseinit()
            # realign the phase of the two generators just in case
            # (once problems were observed after a few weeks)
            for i in range(2):
                self._generator.channel_idx = i + 1
                self._generator.output_enabled = False
                self._generator.waveform = "SIN"
                self._generator.impedance = 50
                self._generator.offset = 0
                self._generator.frequency = frequency
                if i == 0:  # modulator output to EOM
                    self._generator.phase = 0
                    self._generator.amplitude = \
                        signal._config.setup.amplitude
                else:  # demodulator output
                    self._generator.phase = phase
                    self._generator.amplitude = 1.4
                self._generator.output_enabled = True
                self._generator.phaseinit()
        #return super(RPLockbox_FPM, self)._setup_pdh()

    def _disable_pdh(self, sbfreq=None):
        signal = self.inputs["pdh"]
        for i in range(2):
            self._generator.channel_idx = i + 1
            self._generator.output_enabled = False
        if not sbfreq is None:
            self._generator.channel_idx = 1
            self._generator.waveform = "SIN"
            self._generator.impedance = 50
            self._generator.offset = 0
            self._generator.frequency = sbfreq
            self._generator.phase = 0
            self._generator.amplitude = \
                signal._config.setup.amplitude_for_finesse
            self._generator.output_enabled = True
        #return super(RPLockbox_FPM, self)._disable_pdh()

    @property
    def coarse(self):
        return self._parent.slow.output_offset

    @coarse.setter
    def coarse(self, v):
        self._parent.slow.output_offset = v

    def setup_ringdown(self,
                       frequency=3.578312e6,
                       amplitude=0.1,
                       duration=1.0):
        output = self._config._root.outputs.fastpiezo.redpitaya_output
        self._parent.rp.asg1.setup(
            frequency=frequency,
            amplitude=amplitude,
            cycles_per_burst=int(np.round(frequency*duration)),
            output_direct=output,
            trigger_source="ext_positive_edge")

    def teardown_ringdown(self):
        self._parent.rp.asg1.disable_advanced_trigger()

    def center_on_resonance(self, start=-1, coarse='slow'):
        self.unlock()
        self.sweep()
        coarsepid = self.outputs[coarse].pid
        coarse.ival = -1
        coarsebw = sorted(self.outputs[coarse]._config.analogfilter.lowpass)

    def find_coarse(self, actuator='slow', modulator='piezo', factor=0.5,
                    quadrature_factor=0.25, duration=50.0, offset=0.8):
        self.unlock()
        modulator = self.outputs[modulator]
        actuator = self.outputs[actuator]
        # immediately put the actuator towards end rail so its capacitor can
        # start charging
        actuator.pid.ival = actuator._config.max_voltage

        # turn off pdh
        self._disable_pdh()

        # generate modulation
        if not hasattr(actuator, 'iq'):
            actuator.iq = self._parent.rp.iqs.pop()
        iq = actuator.iq
        f = modulator._config.sweep.frequency
        bw = f/2
        acbw = 5
        while bw < acbw * 2:
            bw *= 2
        # optimal phase for demodulation
        p = -np.angle(modulator._analogfilter(f), deg=True)
        iq.setup(frequency=f,
                 phase=p,
                 amplitude=modulator._config.sweep.amplitude,
                 output_direct=modulator._config.redpitaya_output,
                 output_signal="quadrature",
                 quadrature_factor=quadrature_factor,
                 input=self.inputs['reflection'].redpitaya_input,
                 gain=0,
                 acbandwidth=acbw,
                 bandwidth=[bw, bw])

        # setup the scope to show the interesting signals
        self._parent.rp.scope.input1 = iq
        self._parent.rp.scope.input2 = actuator.pid
        self._parent.rp.scope.duration = 8.0
        # the resulting signal in iq.name will be negative if the resonance
        # is at the low end and positive at the high end of piezo
        # this is inversed because the resonance dip goes towards negative
        # voltage
        # thus, we must apply positive gain as long as actuator and piezo
        # move the cavity length in the same direction
        # we must express slope in calibunits-reversed
        calibunit = actuator._config.calibrationunits
        span_per_V = modulator._config[calibunit]
        span = modulator._config.sweep.amplitude * span_per_V
        span *= abs(modulator._analogfilter(f))  # lowpass correction
        # slope is 1V per span - roughly since we dont know the amplitude
        slope = - 1.0/span  # inversion cause reflection is negative
        # estimate integrator sweep rate - electrical i-gain
        i_gain = -actuator._config.lock.unity_gain_frequency/slope
        # sweep rate is 2*pi*i_gain*setpoint
        # therefore duraton = 2V/sweeprate
        setpoint = 0.05  # 1.0 / duration / np.pi / i_gain
        # set input already here
        actuator.pid.input = iq
        actuator.lock(slope,
                      setpoint=setpoint,
                      input=None,  # no signal has been configured so we set
                                   # input manually
                      factor=factor,
                      offset=offset,
                      second_integrator=0,
                      setup_iir=False,
                      skipskip=True)

    def sweep(self):
        self._parent.slow.off(ival=False)
        if hasattr(self._parent.slow, 'iq'):
            self._parent.slow.iq.amplitude = 0
        return super(FPM, self).sweep()


class FPM_LMSD(FPM):
    export_to_parent = FPM.export_to_parent \
                       + ["lock_lmsd", "setup_lmsd"]
    #def setup(self):
    #    super(FPM_LMSD, self).setup()
    #    self._parent.constants = self._parent.c.constants

    def setup_lmsd(self):
        self._disable_pdh()
        self.setup_iq(input='lmsd')
        if 'lmsd_quadrature' not in self.inputs:
            self._config._root.inputs['lmsd_quadrature'] = {'redpitaya_input':
                                                                'iq2_2'}
            # execution of Pyrpl._makesignals is required here
            logger.error("LMSD Configuration was incomplete. Please restart "
                         "pyrpl now and the problem should disappear. ")
        self.unlock()

    def setup_lmsd_external(self):
        self._disable_pdh()
        if not hasattr(self, 'l'):
            from pyrpl import Pyrpl
            self.l = Pyrpl('lmsd')
            self._parent.l = self.l
        self.unlock()

    @property
    def lmsd_frequency(self):
        return self.l.lmsd.iq.frequency

    @lmsd_frequency.setter
    def lmsd_frequency(self, v):
        self.l.lmsd.iq.frequency = v
        self.l.lmsd._config.setup.frequency = v

    def lock_lmsd(self, gain=0.01, sleeptime=1.0):
        from time import sleep
        self.unlock()
        self.l.unlock()
        self.l.piezo.pid.input="iq2"
        self.l.piezo.pid.setpoint = 0
        self.l.piezo.pid.i = 0
        self.l.piezo.pid.ival = 0
        self.l.piezo.pid.p = 1.0
        self.piezo = self.outputs["piezo"]
        self.piezo.pid.input = 'adc1'
        self.piezo.pid.setpoint = 0.6
        self.piezo.pid.ival = 3.0
        sleep(0.03)
        self.piezo.pid.i = gain
        sleep(sleeptime)
        self.piezo.pid.setpoint = 0.42

    def _lmsd(self, detuning, phi=0, xmax=10):
        try:
            len(detuning)
        except:
            pass
        else:
            return np.array([self._lmsd(d, phi=phi, xmax=xmax) for d in \
                    detuning])
        """ lmsd error signal"""
        N = 300
        t = np.linspace(0, 2*np.pi, N, endpoint=False)
        x = np.sin(t)*xmax
        R = self._lorentz(x-detuning)
        prod = R*np.sin(t+phi/180.0*np.pi)
        errsig = np.mean(prod)
        return errsig

    def _lmsd_normalized(self, detuning, phi=0, xmax=10):
        if xmax > 1.5:
            return self._lmsd(detuning, phi=phi, xmax=xmax) / \
                   self._lmsd(xmax-0.5, phi=0, xmax=xmax)
        elif xmax > 0.5:
            return self._lmsd(detuning, phi=phi, xmax=xmax) / \
                   self._lmsd(xmax, phi=0, xmax=xmax)
        else:
            return self._lmsd(detuning, phi=phi, xmax=xmax) / \
                   self._lmsd(0.5,  phi=0, xmax=xmax)

    def lmsd(self, detuning):
        return self._lmsd_normalized(detuning,
                                     phi=self.inputs['lmsd']._config.phi,
                                     xmax=self.inputs['lmsd']._config.xmax) \
               * self.inputs['lmsd']._config.peak

    def calibrate(self):
        return super(FPM_LMSD, self).calibrate(inputs=['lmsd'])
        self.fit('lmsd')

    def fit_lmsd(self, manualfit=True, autoset=True):
        """ attempts a fit of input's last calibration curve with the input's
        model"""
        input = 'lmsd'
        if not isinstance(input, Signal):
            input = self.inputs[input]
        signalfn = self.__getattribute__('_'+input._name+'_normalized')
        c = CurveDB.get(input._config.curve)
        data = c.data
        t = c.data.index.values
        def fitfn(variable_per_time, t0, offset, scale, xmax, phi):
            scale
            variables = (t-t0) * variable_per_time
            return np.array(offset + scale * signalfn(variables,
                                                      phi=phi, xmax=xmax),
                            dtype=np.double)
        # a very naive guess - should be refined with 'input_guess' function
        try:
            v_per_t = self.inputs['lmsd']._config.variable_per_time
        except:
            v_per_t = 10.0 / (t.max() - t.min())
        try:
            t0 = self.inputs['lmsd']._config.t0
        except:
            t0 = 0
        guess = {'variable_per_time': v_per_t,
                 't0': t0,
                 'offset': 0,
                 'scale': self.inputs["lmsd"]._config.peak,
                 'xmax': self.inputs["lmsd"]._config.xmax
                 }
        try:
            guessfn = self.__getattribute__(input._name + '_guess')
        except AttributeError:
            self.logger.warning("No function %s to guess fit "
                                "parameters is defined. Writing one will "
                                "improve fit performance. ",
                                input._name + '_guess')
        else:
            guess.update(guessfn())
        fitter = fitting.Fit(data, fitfn, manualguess_params=guess,
                    fixed_params={'offset': 0,
                                  'phi': self.inputs['lmsd']._config.phi},
                    graphicalfit=manualfit, autofit=True)
        fitcurve = CurveDB.create(fitter.fitdata, name='fit_'+input._name)
        fitcurve.params.update(fitter.getparams())
        try:
            postfn = self.__getattribute__(input._name + '_postfit')
        except AttributeError:
            self.logger.warning("No function %s to use fit "
                                "parameters is defined. Writing one will "
                                "improve calibration results. ",
                                input._name + '_postfit')
        else:
            fitcurve.params.update(postfn())
        fitcurve.save()
        c.add_child(fitcurve)
        if autoset and fitter.gfit_concluded:
            self.inputs['lmsd']._config.peak = fitcurve.params["scale"]
            self.inputs['lmsd']._config.xmax = fitcurve.params["xmax"]
            self.inputs['lmsd']._config.variable_per_time = fitcurve.params[
                "variable_per_time"]
        return fitcurve

    def lmsd_quadrature(self, detuning):
        return self.pdh(detuning, phase=np.pi / 2)

    def calibrate_lmsd(self, autoset=True):
        """ sweep is provided by other lockbox"""
        self.inputs['lmsd']._acquire(secondsignal='lmsd_quadrature')
        lmsd = self.inputs['lmsd'].curve
        lmsd_quadrature = self.inputs['lmsd_quadrature'].curve
        complex_lmsd = lmsd.data + 1j * lmsd_quadrature.data
        max = complex_lmsd.loc[complex_lmsd.abs().argmax()]
        phase = np.angle(max, deg=True)
        self.logger.info('Recommended phase correction for lmsd: %s degrees',
                         phase)
        qfactor = self.inputs['lmsd'].iq.quadrature_factor * 0.8 / abs(max)
        self.logger.info('Recommended quadrature factor: %s',
                         qfactor)
        if autoset:
            self._config._root.inputs.lmsd.setup.phase -= phase
            self._config._root.inputs.lmsd.setup.quadrature_factor = qfactor
            self.setup_lmsd()
            self.logger.info('Autoset of iq parameters was executed.')
        return phase, qfactor


    @property
    def frequency(self):
        return self.inputs["lmsd"].iq.frequency

    @frequency.setter
    def frequency(self, v):
        self.inputs["lmsd"].iq.frequency = v
        self.inputs["lmsd"]._config.setup.frequency = v

    def adjustfrequency(self, timeout=-1, minstep=None, threshold=None):
        if hasattr(self, 'ftimer'):
            if timeout > 0:
                self.ftimer.stop()
        else:
            self.ftimer = QtCore.QTimer()
        if not hasattr(self, 'fthreshold'):
            self.fthreshold = threshold or 0.1
        if not hasattr(self, 'fminstep'):
            self.fminstep = minstep or 0.015
        self._parent.rp.scope.setup()
        c1 = self._parent.rp.scope.curve(ch=1)
        c2 = self._parent.rp.scope.curve(ch=2)
        c = c2/c1
        rel = c[c is not np.nan].mean()
        if rel > self.fthreshold:
            self.inputs['lmsd'].iq.frequency += self.fminstep
        elif rel < -self.fthreshold:
            self.inputs['lmsd'].iq.frequency -= self.fminstep
        print (rel, self.frequency)
        if timeout == 0:
            return
        elif timeout > 0:
            self.ftimeout = timeout
            self.ftimer.timeout.connect(self.adjustfrequency)
            self.ftimer.start(self.ftimeout)

    def adjustphase(self, timeout=-1, minstep=None, threshold=None):
        if not hasattr(self, 'lasttime'):
            self.lasttime = 0
        if not hasattr(self, 'ftimeout'):
            self.ftimeout = 10000
        if hasattr(self, 'ftimer'):
            if timeout > 0:
                self.ftimer.stop()
        else:
            self.ftimer = QtCore.QTimer()
        if not hasattr(self, 'fthreshold'):
            self.fthreshold = threshold or 0.1
        if not hasattr(self, 'fminstep'):
            self.fminstep = minstep or 3
        from time import time
        if time()-self.ftimeout/1000 < self.lasttime:
            return
        self._parent.rp.scope.setup()
        c1 = self._parent.rp.scope.curve(ch=1)
        c2 = self._parent.rp.scope.curve(ch=2)
        c = c2 / c1
        rel = c[c is not np.nan].mean()
        if rel > self.fthreshold:
            self.inputs['lmsd'].iq.phase += self.fminstep
        elif rel < -self.fthreshold:
            self.inputs['lmsd'].iq.phase -= self.fminstep
        self.lasttime = time()
        print (rel)
        if timeout == 0:
            return
        elif timeout > 0:
            self.ftimeout = timeout
            self.ftimer.timeout.connect(self.adjustphase)
            self.ftimer.start(self.ftimeout)


    def estimate_amplitude(self):
        x, y = self.rrp.iq0.na_trace(input='iq2', output_direct='out2',
                                start=688000,
                     stop=690000, rbw=[75,75], points=101, amplitude=0.1,
                     logscale=False, avg=1)
        m = np.mean(y.abs())
        self.amplogger.log(m)
        return m

    def correct_amplitude(self):
        m = self.estimate_amplitude()
        gain = self._config.pll.amp_gain
        self.rrp.iq2.amplitude *= (m/self._config.pll.amp_setpoint)**gain
        return m

    def estimate_angle(self):
        m = np.zeros(self._config.pll.na_samples, dtype=np.complex)
        for i in range(len(m)):
            self.rrp.iq2.frequency = self.rrp.iq2.frequency
            m[i] = r.lmsd.iq._nadata
        angle = (np.angle(m * 1j, deg=True) % 180 - 90).mean()
        self.phaselogger.log(angle)
        return angle

    def correct_angle(self):
        angle = self.estimate_angle()
        self.rrp.iq2.phase -= angle
        return angle

    def setup_pll(self, timeout=1.0):
        if not hasattr(self, 'rrp'):
            #self._parent.rp.make_a_slave() # make a new interface to avoid conflicts
            self.rrp = self._parent.rp
        self.phaselogger = SensingDevice(name='pll_phase')
        self.amplogger = SensingDevice(name='pll_amplitude')
        self.pll_timeout = timeout or 1.0
        iq = self.rrp.iq2
        t0 = time.time()
        # setup na measurement of both quadratures
        p = self.estimate_angle()
        a = self.estimate_amplitude()
        print "Current phase: %f" % p
        print "Current amplitude: %f" % a
        if whileloop:
            while True:
                if time.time() - self.pll_timeout < t0:
                    time.sleep(0.001)
                    continue
                else:
                    self.pll_step()
                    t0 = time.time()
        else:
            if hasattr(self, 'timer'):
                self.timer.stop()
                self.timer.timeout.disconnect()
            else:
                self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.pll_step)
            self.timer.start(int(timeout * 1000))

    # stop the whole thing with:
    # r.model.timer.stop()
    def pll_step(self):
        p = self.correct_angle()
        a = self.correct_amplitude()
        if self.pll_sound:
            from ..sound import sine
            sine(2000, duration=0.05)
            self.logger.info('phase: %s, amplitude%s', p, a)


    ################# old version ############################
    #def setup_pll(self, timeout=1.0, gain=1, threshold=0.1,
    #                  whileloop=False, sound=False):
    #    self.pll_gain = gain or self.pll_gain
    #    self.pll_threshold = threshold or self.pll_threshold
    #    self.pll_timeout = timeout or 1.0
    #    self.pll_sound = sound
    #    iq = self.inputs['lmsd'].iq
    #    t0 = time.time()
    #    # setup na measurement of both quadratures
    #    iq._na_averages = np.int(np.round(125e6 * self.pll_timeout))
    #    iq._na_sleepcycles = 0
    #    # trigger
    #    iq.frequency = iq.frequency
    #    if whileloop:
    #        while True:
    #            if time.time() - self.pll_timeout < t0:
    #                time.sleep(0.001)
    #                continue
    #            else:
    #                self.pll_step()
    #                t0 = time.time()
    #   else:
    #       if hasattr(self, 'timer'):
    #           self.timer.stop()
    #           self.timer.timeout.disconnect()
    #       else:
    #           self.timer = QtCore.QTimer()
    #       self.timer.timeout.connect(self.pll_step)
    #       self.timer.start(int(timeout * 1000))

    # r.model.timer.stop()
    #def pll_step(self):
    #    iq = self.inputs['lmsd'].iq
    #    # get data from accumulator
    #    y = iq._nadata
    #    if y != 0:
    #        # stabilizing action
    #        phase = np.angle(y, deg=True)
    #        iq.phase -= self.pll_gain * phase
    #    # diagnostics
    #    if self.pll_sound:
    #        from ..sound import sine
    #        sine(2000, duration=0.05)
    #        self.logger.info('y=%s, iqphase=%s, pllphase=%s',
    #                         y, iq.phase, phase)
    #    # trigger accumulator for next step
    #    iq.frequency = iq.frequency
