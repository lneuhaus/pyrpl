from __future__ import division
from . import Signal
from ....attributes import BoolProperty, FloatProperty, SelectProperty, \
    FloatAttribute, FilterAttribute, LongProperty, StringProperty, \
    ListFloatProperty, FrequencyProperty
from ....hardware_modules.asg import Asg1
from ....widgets.module_widgets import OutputSignalWidget
from ....hardware_modules.pid import Pid
from ....curvedb import CurveDB
from scipy import interpolate

import numpy as np


class GainProperty(FloatProperty):
    """
    Forwards the gain to the pid module when the lock is active. Otherwise,
    behaves as a property.
    """
    def set_value(self, instance, value):
        super(GainProperty, self).set_value(instance, value)
        if instance.mode == 'lock':
            instance.update_pid_gains(instance.current_input_lock,
                                      instance.current_variable_value)
        instance.lockbox._signal_launcher.update_transfer_function.emit(
            [instance])
    # def launch_signal(self, module, new_value_list):
    #     super(ProportionalGainProperty, self).launch_signal(module,
    #         new_value_list)
    #     module._widget.update_transfer_function()


class PIcornerAttribute(FloatAttribute):
    """
    Not implemented yet
    """
    def __set__(self, instance, value):
        pass


class AdditionalFilterAttribute(FilterAttribute):
    def valid_frequencies(self, instance):
        return instance.pid.__class__.inputfilter.valid_frequencies(
            instance.pid)

    def get_value(self, instance, owner):
        if instance is None:
            return self
        return instance.pid.inputfilter

    def set_value(self, instance, value):
        instance.pid.inputfilter = value
        instance.lockbox._signal_launcher.update_transfer_function.emit([
            instance])

    #def launch_signal(self, module, new_value_list):
    #    super(AdditionalFilterAttribute, self).launch_signal(module, new_value_list)
    #    module._widget.update_transfer_function()


class DisplayNameProperty(StringProperty):
    def set_value(self, obj, val):
        # name property is read-only
        return
    #     if obj.parent is not None:
    #         obj.parent._rename_output(obj, val)
    #     else:
    #         super(DisplayNameProperty, self).set_value(obj, val)


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
      - is_sweepable: boolean to decide whether using this output in a sweep is
        an option.
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
    _gui_attributes = ['unit',
                      'is_sweepable',
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

    _widget_class = OutputSignalWidget

    # options are updated each time the lockbox model is changed.

    # main attributes
    dc_gain = FloatProperty(default=1.0, min=-1e10, max=1e10)
    output_channel = SelectProperty(options=['out1', 'out2',
                                             'pwm0', 'pwm1'])
    unit = SelectProperty(default='V', options=lambda inst: inst.lockbox._units)

    is_sweepable = BoolProperty(default=True)
    assisted_design = AssistedDesignProperty(default=True)
    sweep_amplitude = FloatProperty(default=1.)
    sweep_offset = FloatProperty()
    sweep_frequency = FrequencyProperty(default=50)
    sweep_waveform = SelectProperty(options=Asg1.waveforms)
    # gain for the conversion V-->model variable in *unit*
    p = GainProperty(min=-1e10, max=1e10)
    i = GainProperty(min=-1e10, max=1e10)
    analog_filter_cutoff = AnalogFilterProperty(default=0)
    additional_filter = AdditionalFilterAttribute()
    extra_module = SelectProperty(['None', 'iir', 'pid', 'iq'])
    extra_module_state = SelectProperty(options=["None"])
    tf_type = TfTypeProperty(["flat", "filter", "curve"], default="filter")
    # tf_filter = CustomFilterRegister()
    desired_unity_gain_frequency = UnityGainProperty(default=100.0)
    tf_curve = TfCurveProperty()
    mode = SelectProperty(options=["unlock", "sweep", "lock"])

    def _init_module(self):
        self.display_name = "my_output"
        self._pid = None
        self._mode = "unlock"
        self.tf_type = 'flat'
        self.current_input_lock = None
        self.current_variable_value = 0
        self.current_variable_slope = 0

    def update_pid_gains(self, input, variable_value, factor=1.):
        """
        If current mode is "lock", updates the gains of the underlying pid module such that:
            - input.gain * pid.p * output.dc_gain = output.p
            - input.gain * pid.i * output.dc_gain = output.i
        """
        if isinstance(input, basestring):
            input = self.lockbox._get_input(input)

        self.current_input_lock = input
        self.current_variable_value = variable_value
        self.current_variable_slope = input.expected_slope(variable_value)

        self.pid.setpoint = input.expected_signal(variable_value)

        self.pid.p = self.p / (self.current_variable_slope*self.dc_gain)*factor
        self.pid.i = self.i / (self.current_variable_slope*self.dc_gain)*factor

    def assisted_gain_updated(self):
        if self.assisted_design:
            filter = self.analog_filter_cutoff
            if filter == 0:
                self.i = self.desired_unity_gain_frequency
                self.p = 0
            else:
                self.i = self.desired_unity_gain_frequency
                self.p = self.i / filter

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
            analog_tf = ampl*np.exp(1j*phase)
        # multiply by PID transfer function to get the loop transfer function
        # same as Pid.transfer_function(freqs) but avoids reading registers form FPGA
        result = analog_tf * Pid._transfer_function(
            freqs, p=self.p, i=self.i,
            frequency_correction=self.pid._frequency_correction,
            filter_values=self.additional_filter)
        return result

    def tf_freqs(self):
        """
        Frequency values to plot the transfer function. Frequency (abcissa) of
        the tf_curve if tf_type=="curve", else: logspace(0, 6, 20000)
        """
        if self.tf_type != 'curve':  # req axis should be that of the curve
            return np.logspace(0, 6, 2000)
        else:
            try:
                c = CurveDB.get(self.tf_curve)
            except:
                return None
            else:
                return c.data.index

    def lock(self, input, variable_value, factor=1.):
        """
        Closes the lock loop, using the required p and i parameters.
        """
        if isinstance(input, basestring):
            input = self.lockbox._get_input(input)
        self.mode = 'lock'
        self.update_pid_gains(input, variable_value, factor=factor)
        self.pid.input = input.signal()
        self._set_output()

    @property
    def is_locked(self):
        return True

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

    def update_for_model(self):
        pass
        #self.__class__.unit.change_options(self.lockbox.get_model( # ).units)

    @property
    def pid(self):
        if self._pid is None:
            self._pid = self.pyrpl.pids.pop(self.name)
        return self._pid

    def unlock(self):
        self.mode = 'unlock'
        self.pid.p = self.pid.i = 0
        
    def reset_ival(self):
        self.pid.ival = 0

    def sweep(self):
        self.mode = 'sweep'
        self.is_sweepable = True  # ... not handled in the gui for now
        if not self.is_sweepable:
            raise ValueError("output '%s' is not sweepable" % self.name)
        self.unlock()
        self.pid.i = 0
        self.pid.ival = 0
        self.pid.p = 1.
        self.pid.setpoint = 0.
        self.lockbox.asg.setup(amplitude=self.sweep_amplitude,
                               offset=self.sweep_offset,
                               frequency=self.sweep_frequency,
                               waveform=self.sweep_waveform)
        self.pid.input = self.lockbox.asg
        self._set_output()

    def _set_output(self):
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

    def clear(self):
        """
        Free up resources associated with the output
        """
        self.pyrpl.pids.free(self.pid)

    def set_ival(self, val):
        """
        sets the integrator value to val (in V)
        """
        self.pid.ival = val

