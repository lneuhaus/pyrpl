from . import Signal
from pyrpl.attributes import BoolProperty, FloatProperty, SelectProperty, FloatAttribute, FilterAttribute, LongProperty,\
                             StringProperty
from pyrpl.hardware_modules.asg import Asg1
from pyrpl.widgets.module_widgets import OutputSignalWidget


class ProportionalGainProperty(FloatProperty):
    """
    Forwards the gain to the pid module when the lock is active. Otherwise, behaves as a property.
    """
    def set_value(self, instance, value):
        super(ProportionalGainProperty, self).set_value(instance, value)
        if instance.is_locked:
            instance.pid.p = value


class IntegralGainProperty(FloatProperty):
    """
    Forwards the gain to the pid module when the lock is active. Otherwise, behaves as a property.
    """
    def set_value(self, instance, value):
        super(IntegralGainProperty, self).set_value(instance, value)
        if instance.is_locked:
            instance.pid.i = value


class PIcornerAttribute(FloatAttribute):
    def __set__(self, instance, value):
        pass


class AdditionalFilterAttribute(FilterAttribute):
    def valid_frequencies(self, instance):
        return instance.pid.__class__.inputfilter.valid_frequencies(instance.pid)

    def get_value(self, instance, owner):
        if instance is None:
            return self
        return instance.pid.inputfilter

    def set_value(self, instance, value):
        instance.pid.inputfilter = value


class DisplayNameProperty(StringProperty):
    def set_value(self, obj, val):
        if obj.parent is not None:
            obj.parent.rename_output(obj, val)
        else:
            super(DisplayNameProperty, self).set_value(obj, val)


class OutputSignal(Signal):
    """
    As many output signal as desired can be added to the lockbox. Each output defines:
      - name: the name of the output.
      - dc_gain: how much the model's variable is expected to change for 1 V on the output (in *unit*)
      - unit: see above, should be one of the units available in the model.
      - is_sweepable: boolean to decide whether using this output in a sweep is an option.
      - sweep_amplitude/offset/frequency/waveform: what properties to use when sweeping the output
      - output_channel: what physical output is used.
      - p/i: the gains to use in a loop: those values are to be understood as full loop gains (p in [1], i in [Hz])
      - additional_filter: a filter (4 cut-off frequencies) to add to the loop (in sweep and lock mode)
      - extra_module: extra module to add just before the output (usually iir).
      - extra_module_state: name of the state to use for the extra_module.
      - tf_curve: the index of the curve describing the analog transfer function behind the output.
      - tf_filter: alternatively, the analog transfer function can be specified by a filter (4 cut-off frequencies).
      - unity_gain_desired: desired value for unity gain frequency.
      - tf_type: ["flat", "curve", "filter"], how is the analog transfer function specified.
    """
    section_name = 'output'
    gui_attributes = [# 'unit',
                      'name',
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
                      'extra_module',
                      'extra_module_state',
                      'unity_gain_desired',
                      'tf_type',
                      'tf_curve']
    setup_attributes = gui_attributes

    widget_class = OutputSignalWidget
    name = DisplayNameProperty()
    # unit = SelectProperty(options=[]) # options are updated each time the lockbox model is changed.
    is_sweepable = BoolProperty()
    sweep_amplitude = FloatProperty()
    sweep_offset = FloatProperty()
    sweep_frequency = FloatProperty()
    sweep_waveform = SelectProperty(options=Asg1.waveforms)
    dc_gain = FloatProperty() # gain for the conversion V-->model variable in *unit*
    output_channel = SelectProperty(options=['dac1', 'dac2']) # at some point, we should add pwms...
    p = ProportionalGainProperty()
    i = ProportionalGainProperty()
    additional_filter = AdditionalFilterAttribute()
    extra_module = SelectProperty(['None', 'iir', 'pid', 'iq'])
    extra_module_state = SelectProperty(options=["None"])
    tf_type = SelectProperty(["flat", "curve", "filter"])
    # tf_filter = CustomFilterRegister()
    unity_gain_desired = FloatProperty()
    tf_curve = LongProperty()

    def init_module(self):
        self.display_name = "my_output"
        self._pid = None
        self.lockbox = self.parent
        self.name = 'output' # will be updated in add_output of parent module

 #   @property
 #   def id(self): # it would be more convenient to compute name from output, but class attribute name can't be a
 #                 # property since it used to define the save section
 #       return int(self.name.strip('output'))


    @property
    def is_locked(self):
        return True

    def update_for_model(self):
        pass#self.__class__.unit.change_options(self.lockbox.get_model().units)

    @property
    def pid(self):
        if self._pid is None:
            self._pid = self.pyrpl.pids.pop(self.name)
        return self._pid

    def unlock(self):
        self.pid.p = self.pid.i = 0

    def sweep(self):
        if not self.is_sweepable:
            raise ValueError("output '%s' is not sweepable"%self.name)
        self.unlock()
        self.pid.p = 1.
        self.lockbox.asg.setup(amplitude=self.sweep_amplitude,
                               offset=self.sweep_offset,
                               frequency=self.sweep_frequency,
                               waveform=self.sweep_waveform)

    def clear(self):
        """
        Free up resources associated with the output
        """
        self.pyrpl.pids.free(self.pid)