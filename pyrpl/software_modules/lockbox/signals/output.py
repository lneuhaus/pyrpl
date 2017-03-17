from __future__ import division
from scipy import interpolate
import numpy as np
from .input import Signal
from ....attributes import BoolProperty, FloatProperty, SelectProperty, \
    FloatAttribute, FilterAttribute, LongProperty, StringProperty, \
    ListFloatProperty, FrequencyProperty
from ....hardware_modules.asg import Asg1
from ....widgets.module_widgets import OutputSignalWidget
from ....hardware_modules.pid import Pid
from ....curvedb import CurveDB
from .. import LockboxModule, LockboxModuleDictProperty


class GainProperty(FloatProperty):
    """
    Forwards the gain to the pid module when the lock is active. Otherwise,
    behaves as a property.
    """
    def set_value(self, obj, value):
        super(GainProperty, self).set_value(obj, value)
        if obj.current_state == 'lock':
            obj._setup_pid_lock(obj.current_input_lock,
                                obj.current_variable_value)
        obj.lockbox._signal_launcher.update_transfer_function.emit([obj])


class AdditionalFilterAttribute(FilterAttribute):
    # proxy to the pid inputfilter attribute that emits a signal when changed
    def valid_frequencies(self, obj):
        return obj.pid.__class__.inputfilter.valid_frequencies(obj.pid)

    def get_value(self, obj, owner):
        return obj.pid.inputfilter

    def set_value(self, obj, value):
        obj.pid.inputfilter = value
        obj.lockbox._signal_launcher.update_transfer_function.emit([obj])


class AssistedDesignProperty(BoolProperty):
    def set_value(self, obj, val):
        super(AssistedDesignProperty, self).set_value(obj, val)
        obj.assisted_gain_updated()
        return val

    #def launch_signal(self, module, new_value_list):
    #    super(AssistedDesignProperty, self).launch_signal(module, new_value_list)
    #    module._widget.set_assisted_design(module.assisted_design)


class AnalogFilterProperty(FloatProperty): #ListFloatProperty):
    def set_value(self, obj, val):
        super(AnalogFilterProperty, self).set_value(obj, val)
        obj.assisted_gain_updated()
        obj.lockbox._signal_launcher.update_transfer_function.emit([obj])


class UnityGainProperty(FrequencyProperty):
    def set_value(self, obj, val):
        super(UnityGainProperty, self).set_value(obj, val)
        obj.assisted_gain_updated()


class TfTypeProperty(SelectProperty):
    def set_value(self, obj, val):
        super(TfTypeProperty, self).set_value(obj, val)
        obj.lockbox._signal_launcher.update_transfer_function.emit([obj])

    #def launch_signal(self, module, new_value_list):
        #super(TfTypeProperty, self).launch_signal(module, new_value_list)
        #module._widget.update_transfer_function()
        #module._widget.change_analog_tf()


class TfCurveProperty(LongProperty):
    def set_value(self, obj, val):
        super(TfCurveProperty, self).set_value(obj, val)
    #def launch_signal(self, module, new_value_list):
    #    super(TfCurveProperty, self).launch_signal(module, new_value_list)
    #    module._widget.update_transfer_function()
    #    module._widget.change_analog_tf()


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
                      'desired_unity_gain_frequency']
    _setup_attributes = _gui_attributes + ['assisted_design', 'tf_curve',
                                           'tf_type']
    # main attributes
    dc_gain = FloatProperty(default=1.0, min=-1e10, max=1e10, call_setup=True)
    output_channel = SelectProperty(options=['out1', 'out2',
                                             'pwm0', 'pwm1'])
    unit = SelectProperty(default='V/V',
                          options=lambda inst:
                          [u+"/V" for u in inst.lockbox._output_units],
                          call_setup=True)
    tf_type = TfTypeProperty(["flat", "filter", "curve"], default="filter")
    tf_curve = TfCurveProperty()
    # sweep properties
    sweep_amplitude = FloatProperty(default=1., min=-1, max=1, call_setup=True)
    sweep_offset = FloatProperty(default=0.0, min=-1, max=1, call_setup=True)
    sweep_frequency = FrequencyProperty(default=50.0, call_setup=True)
    sweep_waveform = SelectProperty(options=Asg1.waveforms, default='ramp', call_setup=True)
    # gain properties
    assisted_design = AssistedDesignProperty(default=True, call_setup=True)
    desired_unity_gain_frequency = UnityGainProperty(default=100.0, min=0, max=1e10, call_setup=True)
    analog_filter_cutoff = AnalogFilterProperty(default=0, min=0, max=1e10, increment=0.1, call_setup=True)
    p = GainProperty(min=-1e10, max=1e10, call_setup=True)
    i = GainProperty(min=-1e10, max=1e10, call_setup=True)
    # additional filter properties
    additional_filter = AdditionalFilterAttribute(call_setup=True)
    extra_module = SelectProperty(['None', 'iir', 'pid', 'iq'], call_setup=True)
    extra_module_state = SelectProperty(options=['None'], call_setup=True)
    # internal state of the output
    current_state = SelectProperty(options=['lock', 'unlock', 'sweep'], default='unlock')

    def assisted_gain_updated(self):
        if self.assisted_design:
            filter = self.analog_filter_cutoff
            if filter == 0:
                self.i = self.desired_unity_gain_frequency
                self.p = 0
            else:
                self.i = self.desired_unity_gain_frequency
                self.p = self.i / filter

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
        ival, max, min = self.pid.ival, self.pid.max_voltage, \
                         self.pid.min_voltage
        if ival > max or ival < min:
            return True
        else:
            return False

    def _setup_pid_output(self):
        if self.output_channel.startswith('out'):
            self.pid.output_direct = self.output_channel
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
        super(OutputSignal, self)._clear()

    def unlock(self, reset_offset=False):
        self.pid.p = 0
        self.pid.i = 0
        if reset_offset:
            self.pid.ival = 0
        self.current_state = 'unlock'

    def sweep(self):
        self.unlock(reset_offset=True)
        self._setup_pid_output()
        self.pid.input = self.lockbox.asg
        self.lockbox.asg.setup(amplitude=self.sweep_amplitude,
                               offset=self.sweep_offset,
                               frequency=self.sweep_frequency,
                               waveform=self.sweep_waveform)
        self.pid.setpoint = 0.
        self.pid.p = 1.
        self.current_state = 'sweep'

    def lock(self, input=None, setpoint=None, offset=None, factor=None):
        """
        Closes the lock loop, using the required p and i parameters.
        """
        # store lock parameters in case an update is requested
        self._lock_input = input or self._lock_input
        self._lock_setpoint = setpoint or self._lock_setpoint
        self._lock_factor = factor or self._lock_factor
        # Parameter 'offset' is not internally stored because another call to 'lock()'
        # shouldnt reset the offset by default as this would un-lock an existing lock
        self._setup_pid_output()  # optional to ensure that pid output is properly set
        self._setup_pid_lock(input=self._lock_input,
                             setpoint=self._lock_setpoint,
                             offset=offset,
                             factor=self._lock_factor)
        self.current_state = 'lock'

    def _setup_pid_lock(self, input, setpoint, offset=None, factor=1.0):
        """
        If current mode is "lock", updates the gains of the underlying pid module such that:
            - input.gain * pid.p * output.dc_gain = output.p
            - input.gain * pid.i * output.dc_gain = output.i
        """
        if isinstance(input, basestring):
            input = self.lockbox.inputs[input]
        # The total loop gain is composed of gains of pid and external components.
        # The external loop is composed of input slope (in units V_per_setpoint_unit, e. g. V/degree)
        # and output gain (in units 'self.unit', e.g. m/V). We need it in units of V/V.
        output_unit = self.unit.split('/')[0]
        setpoint_unit_per_output_unit = getattr(self.lockbox,
                                                "variable_per_"+output_unit)
        external_loop_gain = input.expected_slope(setpoint)\
                             * self.dc_gain \
                             * setpoint_unit_per_output_unit
        # write values to pid module
        self.pid.setpoint = input.expected_signal(setpoint)
        self.pid.p = self.p / external_loop_gain * factor
        self.pid.i = self.i / external_loop_gain * factor
        self.pid.input = input.signal()
        # offset is the last thing that is modified to guarantee the offset setting with the gains
        if offset is not None:
            self.pid.ival = offset

    def _setup(self):
        if self.current_state == 'sweep':
            self.sweep()
        elif self.current_state == 'unlock':
            self.unlock()
        elif self.current_state == 'lock':
            self.lock()

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

