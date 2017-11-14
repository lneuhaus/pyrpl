from __future__ import division

import numpy as np
from scipy import interpolate

from ...software_modules.lockbox.input import Signal
from ...attributes import BoolProperty, FloatProperty, SelectProperty, \
    FilterProperty, FrequencyProperty, IntProperty
from ...curvedb import CurveDB
from ...hardware_modules.asg import Asg0, Asg1
from ...hardware_modules.pid import Pid
from ...widgets.module_widgets import OutputSignalWidget


class AdditionalFilterAttribute(FilterProperty):
    # proxy to the pid inputfilter attribute that emits a signal when changed
    def valid_frequencies(self, obj):
        return obj.pid.__class__.inputfilter.valid_frequencies(obj.pid)

    def get_value(self, obj):
        return obj.pid.inputfilter

    def set_value(self, obj, value):
        obj.pid.inputfilter = value
        obj.lockbox._signal_launcher.update_transfer_function.emit([obj])


class OutputSignal(Signal):
    """
    As many output signals as desired can be added to the lockbox. Each
    output defines:
      - name: the name of the output.
      - dc_gain: how much the model's variable is expected to change for 1 V
        on the output (in *unit*)
      - unit: see above, should be one of the units available in the model.
      - sweep_amplitude/offset/frequency/waveform: what properties to use when
        sweeping the output
      - output_channel: what physical output is used.
      - p/i: the gains to use in a loop: those values are to be understood as
        full loop gains (p in [1], i in [Hz])
      - additional_filter: a filter (4 cut-off frequencies) to add to the loop
        (in sweep and lock mode)
      - extra_module: extra module to add just before the output (usually iir).
      - extra_module_state: name of the state to use for the extra_module.
      - tf_curve: the index of the curve describing the analog transfer
        function behind the output.
      - tf_filter: alternatively, the analog transfer function can be specified
        by a filter (4 cut-off frequencies).
      - desired_unity_gain_frequency: desired value for unity gain frequency.
      - tf_type: ["flat", "curve", "filter"], how is the analog transfer
        function specified.
    """
    _widget_class = OutputSignalWidget
    _gui_attributes = ['unit',
                      'sweep_amplitude',
                      'sweep_offset',
                      'sweep_frequency',
                      'sweep_waveform',
                      'dc_gain',
                      'output_channel',
                      'p',
                      'i',
                      'additional_filter',
                      'analog_filter_cutoff',
                      'extra_module',
                      'extra_module_state',
                      'desired_unity_gain_frequency',
                      'max_voltage',
                      'min_voltage']
    _setup_attributes = _gui_attributes + ['assisted_design', 'tf_curve',
                                           'tf_type']
    # main attributes
    dc_gain = FloatProperty(default=1.0, min=-1e10, max=1e10, call_setup=True)
    output_channel = SelectProperty(options=['out1', 'out2',
                                             'pwm0', 'pwm1'])
    unit = SelectProperty(default='V/V',
                          options=lambda inst:
                          [u+"/V" for u in inst.lockbox._output_units],
                          call_setup=True,
                          ignore_errors=True)
    tf_type = SelectProperty(["flat", "filter", "curve"],
                             default="filter",
                             call_setup=True)
    tf_curve = IntProperty(call_setup=True)
    # sweep properties
    sweep_amplitude = FloatProperty(default=1., min=-1, max=1, call_setup=True)
    sweep_offset = FloatProperty(default=0.0, min=-1, max=1, call_setup=True)
    sweep_frequency = FrequencyProperty(default=50.0, call_setup=True)
    sweep_waveform = SelectProperty(options=Asg1.waveforms, default='ramp', call_setup=True)
    # gain properties
    assisted_design = BoolProperty(default=True, call_setup=True)
    desired_unity_gain_frequency = FrequencyProperty(default=100.0, min=0, max=1e10, call_setup=True)
    analog_filter_cutoff = FrequencyProperty(default=0, min=0, max=1e10, increment=0.1, call_setup=True)
    p = FloatProperty(min=-1e10, max=1e10, call_setup=True)
    i = FloatProperty(min=-1e10, max=1e10, call_setup=True)
    # additional filter properties
    additional_filter = AdditionalFilterAttribute() #call_setup=True)
    extra_module = SelectProperty(['None', 'iir', 'pid', 'iq'], call_setup=True)
    extra_module_state = SelectProperty(options=['None'], call_setup=True)
    # internal state of the output
    current_state = SelectProperty(options=['lock', 'unlock', 'sweep'],
                                   default='unlock')
    max_voltage = FloatProperty(default=1.0, min=-1.0, max=1.0,
                                call_setup=True,
                                doc="positive saturation voltage")
    min_voltage = FloatProperty(default=-1.0,
                                min=-1.0, max=1.0,
                                call_setup=True,
                                doc="negative saturation voltage")

    def signal(self):
        return self.pid.name

    @property
    def pid(self):
        if not hasattr(self, '_pid') or self._pid is None:
            self._pid = self.pyrpl.pids.pop(self.name)
            self._setup_pid_output()
        return self._pid

    @property
    def is_saturated(self):
        """
        Returns
        -------
        True: if the output has saturated
        False: otherwise
        """
        ival, max, min = self.pid.ival, self.max_voltage, \
                         self.min_voltage
        sample = getattr(self.pyrpl.rp.sampler, self.pid.name)
        # criterion for saturation: integrator value saturated
        # and current value (including pid) as well
        if (ival > max or ival < min) and (sample > max or sample < min):
            return True
        else:
            return False

    def _setup_pid_output(self):
        self.pid.max_voltage = self.max_voltage
        self.pid.min_voltage = self.min_voltage
        if self.output_channel.startswith('out'):
            self.pid.output_direct = self.output_channel
            for pwm in [self.pyrpl.rp.pwm0, self.pyrpl.rp.pwm1]:
                if pwm.input == self.pid.name:
                    pwm.input = 'off'
        elif self.output_channel.startswith('pwm'):
            self.pid.output_direct = 'off'
            pwm = getattr(self.pyrpl.rp, self.output_channel)
            pwm.input = self.pid
        else:
            raise NotImplementedError(
                "Selected output_channel '%s' is not implemented"
                % self.output_channel)

    def _clear(self):
        """
        Free up resources associated with the output
        """
        self.pyrpl.pids.free(self.pid)
        self._pid = None
        super(OutputSignal, self)._clear()

    def unlock(self, reset_offset=False):
        self.pid.p = 0
        self.pid.i = 0
        if reset_offset:
            self.pid.ival = 0
        self.current_state = 'unlock'
        # benefit from the occasion and do proper initialization
        self._setup_pid_output()

    def sweep(self):
        self.unlock(reset_offset=True)
        self.pid.input = self.lockbox.asg
        self.lockbox.asg.setup(amplitude=self.sweep_amplitude,
                               offset=self.sweep_offset,
                               frequency=self.sweep_frequency,
                               waveform=self.sweep_waveform,
                               trigger_source='immediately',
                               cycles_per_burst=0)
        self.pid.setpoint = 0.
        self.pid.p = 1.
        self.current_state = 'sweep'

    def lock(self, input=None, setpoint=None, offset=None, gain_factor=None):
        """
        Closes the lock loop, using the required p and i parameters.
        """
        # store lock parameters in case an update is requested
        self._lock_input = self._lock_input if input is None else input
        self._lock_setpoint = self._lock_setpoint if setpoint is None else setpoint
        self._lock_gain_factor = self._lock_gain_factor if gain_factor is None else gain_factor
        # Parameter 'offset' is not internally stored because another call to 'lock()'
        # shouldnt reset the offset by default as this would un-lock an existing lock
        #self._setup_pid_output()  # optional to ensure that pid output is properly set
        self._setup_pid_lock(input=self._lock_input,
                             setpoint=self._lock_setpoint,
                             offset=offset,
                             gain_factor=self._lock_gain_factor)
        self.current_state = 'lock'

    def _setup_pid_lock(self, input, setpoint, offset=None, gain_factor=1.0):
        """
        If current mode is "lock", updates the gains of the underlying pid module such that:
            - input.gain * pid.p * output.dc_gain = output.p
            - input.gain * pid.i * output.dc_gain = output.i
        """
        if isinstance(input, str):  # used to be basestring
            input = self.lockbox.inputs[input]

        # The total loop is composed of the pid and external components.
        # The external parts are 1) the output with the predefined gain and 2)
        # the input (error signal) with a setpoint-dependent slope.
        # 1) model the output: dc_gain converted into units of setpoint_unit_per_V
        output_unit = self.unit.split('/')[0]
        external_loop_gain = self.dc_gain * self.lockbox._unit_in_setpoint_unit(output_unit)
        # 2) model the input: slope comes in units of V_per_setpoint_unit,
        # which cancels previous unit and we end up with a dimensionless ext. gain.
        external_loop_gain *= input.expected_slope(setpoint)

        # we should avoid setting gains to infinity
        if external_loop_gain == 0:
            self._logger.warning("External loop gain for output %s is zero. "
                                 "Skipping pid lock for this step. ",
                                 self.name)
            if offset is not None:
                self.pid.ival = offset
        else:  # write values to pid module
            # set gains to zero before switching setpoint and input,
            # to avoid huge gains while transiting
            self.pid.p = 0
            self.pid.i = 0
            self.pid.setpoint = input.expected_signal(setpoint) + input.calibration_data._analog_offset
            self.pid.input = input.signal()
            # set offset if applicable
            if offset is not None:
                self.pid.ival = offset
            # set gains
            self.pid.p = self.p / external_loop_gain * gain_factor
            self.pid.i = self.i / external_loop_gain * gain_factor

    def _setup_offset(self, offset):
        self.pid.ival = offset

    def _setup(self):
        # synchronize assisted_design parameters with p/i setting
        self._setup_ongoing = True
        if self.assisted_design:
            self.i = self.desired_unity_gain_frequency
            if self.analog_filter_cutoff == 0:
                self.p = 0
            else:
                self.p = self.i / self.analog_filter_cutoff
        else:
            self.desired_unity_gain_frequency = self.i
            if self.p == 0:
                self.analog_filter_cutoff = 0
            else:
                self.analog_filter_cutoff = self.i / self.p
        self._setup_ongoing = False
        # re-enable lock/sweep/unlock with new parameters
        if self.current_state == 'sweep':
            self.sweep()
        elif self.current_state == 'unlock':
            self.unlock()
        elif self.current_state == 'lock':
            self.lock()
        # plot current transfer function
        self.lockbox._signal_launcher.update_transfer_function.emit([self])


    ##############################
    # transfer function plotting #
    ##############################
    def tf_freqs(self):
        """
        Frequency values to plot the transfer function. Frequency (abcissa) of
        the tf_curve if tf_type=="curve", else: logspace(0, 6, 20000)
        """
        if self.tf_type == 'curve':  # req axis should be that of the curve
            try:
                c = CurveDB.get(self.tf_curve)
            except:
                self._logger.warning("Cannot load specified transfer function %s",
                                     self.tf_curve)
            else:
                return c.data.index
        # by default
        return np.logspace(0, 6, 2000)

    def transfer_function(self, freqs):
        """
        Returns the design transfer function for the output
        """
        analog_tf = np.ones(len(freqs), dtype=complex)
        if self.tf_type == 'filter':
            # use logic implemented in PID to simulate analog filters
            analog_tf = Pid._filter_transfer_function(freqs, self.analog_filter_cutoff)
        if self.tf_type == 'curve':
            curve = CurveDB.get(self.tf_curve)
            x = curve.data.index
            y = curve.data.values
            # sample the curve transfer function at the requested frequencies
            ampl = interpolate.interp1d(x, abs(y))(freqs)
            phase = interpolate.interp1d(x, np.unwrap(np.angle(y)))(freqs)
            analog_tf = ampl * np.exp(1j * phase)
        # multiply by PID transfer function to get the loop transfer function
        # same as Pid.transfer_function(freqs) but avoids reading registers form FPGA
        result = analog_tf * Pid._transfer_function(
            freqs, p=self.p, i=self.i,
            frequency_correction=self.pid._frequency_correction,
            filter_values=self.additional_filter)
        return result


    # TODO: re-implement this function for if an iir filter is set
    # def setup_iir(self, **kwargs):
    #     """
    #     Inserts an iir filter before the output pid. For correct routing,
    #     the pid input must be set correctly, as the iir filter will reuse
    #     the pid input setting as its own input and send its output through
    #     the pid.
    #
    #     Parameters
    #     ----------
    #     kwargs: dict
    #         Any kwargs that are accepted by IIR.setup(). By default,
    #         the output's iir section in the config file is used for these
    #         parameters.
    #
    #     Returns
    #     -------
    #     None
    #     """
    #     # load data from config file
    #     try:
    #         iirconfig = self._config.iir._dict
    #     except KeyError:
    #         logger.debug("No iir filter was defined for output %s. ",
    #                      self._name)
    #         return
    #     else:
    #         logger.debug("Setting up IIR filter for output %s. ", self._name)
    #     # overwrite defaults with kwargs
    #     iirconfig.update(kwargs)
    #     if 'curve' in iirconfig:
    #         iirconfig.update(bodefit.iirparams_from_curve(
    #             id=iirconfig.pop('curve')))
    #     else:
    #         # workaround for complex numbers from yaml
    #         iirconfig["zeros"] = [complex(n) for n in iirconfig.pop("zeros")]
    #         iirconfig["poles"] = [complex(n) for n in iirconfig.pop("poles")]
    #     # get module
    #     if not hasattr(self, "iir"):
    #         self.iir = self._rp.iirs.pop()
    #         logger.debug("IIR filter retrieved for output %s. ", self._name)
    #     # output_direct off, since iir goes through pid
    #     iirconfig["output_direct"] = "off"
    #     # input setting -> copy the pid input if it is not erroneously on iir
    #     pidinput = self.pid.input
    #     if pidinput != 'iir':
    #         iirconfig["input"] = pidinput
    #     # setup
    #     self.iir.setup(**iirconfig)
    #     # route iir output through pid
    #     self.pid.input = self.iir.name

class PiezoOutput(OutputSignal):
    unit = SelectProperty(default='m/V',
                          options=lambda inst:
                          [u + "/V" for u in inst.lockbox._output_units],
                          call_setup=True)
