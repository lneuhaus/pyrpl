from __future__ import division
from pyrpl.attributes import SelectProperty, FloatProperty, BoolProperty, StringProperty, \
                            ListStageOuputProperty
from pyrpl.modules import SoftwareModule
from pyrpl.widgets.module_widgets import LockboxSequenceWidget, LockboxStageWidget

from collections import OrderedDict


class Sequence(SoftwareModule):
    _widget_class = LockboxSequenceWidget
    _section_name = 'sequence'

    def _init_module(self):
        self.stages = []
        self.lockbox = self.parent

    def get_unique_stage_name(self):
        idx = len(self.stages) + 1
        name = 'stage' + str(idx)
        while name in self.stage_names:
            idx+=1
            name = 'stage' + str(idx)
        return name

    @property
    def stage_names(self):
        return [stage.name for stage in self.stages]

    def add_stage(self):
        """
        Stages can be added at will.
        """
        stage = self._add_stage_no_save()
        stage.name = stage.name  # triggers a save in the config file...
        return stage

    def _add_stage_no_save(self):
        """
        Adds a stage in the sequence without touching the config file
        """
        stage = Stage(self)
        stage._autosave_active = False
        stage.update_inputs()
        stage.update_outputs()
        stage._name = self.get_unique_stage_name()
        self.stages.append(stage)
        setattr(self, stage.name, stage)
        # self.__class__.default_sweep_output.change_options([output.name for output in self.outputs])
        self.lockbox._signal_launcher.stage_created.emit([stage])
        stage._autosave_active = True
        return stage

    def rename_stage(self, stage, new_name):
        self.lockbox.rename_stage(stage, new_name)

    def update_stage_names(self):
        self.lockbox._signal_launcher.stage_renamed.emit()
        #if self.widget is not None:
        #    self.widget.update_stage_names()

    def remove_stage(self, stage, allow_last_stage=False):
        if isinstance(stage, basestring):
            stage = self.get_stage(stage)
        if not allow_last_stage:
            if len(self.stages)<=1:
                raise ValueError("At least one stage should remain in the sequence")
        self.stages.remove(stage)
        if hasattr(self, stage.name):
            delattr(self, stage.name)
        if "stages" in self.c._keys():
            if stage.name in self.c.stages._keys():
                self.c.stages._pop(stage.name)
        self.lockbox._signal_launcher.stage_deleted.emit([stage])
        #if stage._widget is not None:
        #   self._widget.remove_stage(stage)

    def remove_all_stages(self):
        to_remove = [] # never iterate on a list that s being deleted
        for stage in self.stages:
            to_remove.append(stage)
        for stage in to_remove:
            self.remove_stage(stage, allow_last_stage=True)

    def load_setup_attributes(self):
        #import pdb
        #pdb.set_trace()
        self.remove_all_stages()
        if self.c is not None:
            if 'stages' in self.c._dict.keys():
                for name, stage in self.c.stages._dict.items():
                    if name!='states':
                        stage = self._add_stage_no_save() # don't make a duplicate entry in the config file
                        stage._autosave_active = False
                        self.rename_stage(stage, name)
                        stage.load_setup_attributes()
                        stage._autosave_active = True
        if len(self.stages)==0:
            self.add_stage()

    def save_state(self, name, state_branch=None):
        if state_branch is None:
            state_branch = self.c_states
        state_branch[name] = OrderedDict()
        for stage in self.stages:
            stage.save_state(stage.name, getattr(state_branch, name))

    def load_state(self, name, state_section=None):
        if state_section is None:
            state_section = self.c_states
        self.remove_all_stages()
        for stage_section in state_section[name].values():
            stage = self.add_stage()
            stage._autosave_active = False
            stage.set_setup_attributes(**stage_section)
            stage._autosave_active = True

    def update_outputs(self):
        for stage in self.stages:
            stage.update_outputs()

    def update_inputs(self):
        for stage in self.stages:
            stage.update_inputs()

    def get_stage(self, name):
        """
        retieves a stage by name
        """
        if not name in self.stage_names:
            raise ValueError(stage_name + " is not a valid stage name")
        return self.stages[self.stage_names.index(name)]


class StageNameProperty(StringProperty):
    def set_value(self, obj, val):
        if obj.parent is not None:
            obj.parent.rename_stage(obj, val)
        else:
            super(StageNameProperty, self).set_value(obj, val)


class Stage(SoftwareModule):
    """
    A stage is a single step in the lock acquisition process
    """
    _setup_attributes = ['name',
                      'input',
                      'variable_value',
                      'output_on',
                      'duration',
                      'function_call',
                      'factor']
    _gui_attributes = _setup_attributes
    _section_name = 'stage'
    name = StageNameProperty(default='my_stage')
    _widget_class = LockboxStageWidget
    input = SelectProperty()
    output_on = ListStageOuputProperty()
    variable_value = FloatProperty(min=-1e6, max=1e6)
    duration = FloatProperty(min=0, max=1e6)
    function_call = StringProperty()
    factor = FloatProperty(default=1., min=-1e6, max=1e6)

    def _init_module(self):
        self.lockbox = self.parent.parent
        self.update_inputs()
        self.update_outputs()

    def update_inputs(self):
        """
        Updates the list of possible inputs to be in sync with the existing inputs in the model
        """
        input_names = [input.name for input in self.lockbox.inputs]
        self.__class__.input.change_options(self, input_names)

    def update_outputs(self):
        """
        Updates the list of outputs to be in sync with the existing outputs in the lockbox
        """

        output_names = [output.name for output in self.lockbox.outputs]
        new_output_on = dict()
        for name in output_names:
            if not name in self.output_on:
                new_output_on[name] = (True, False, 0)
            else:
                new_output_on[name] = self.output_on[name]
        self.output_on = new_output_on

    def set_setup_attributes(self, **kwds):
        try:
            super(Stage, self).set_setup_attributes(**kwds)
        finally:
            self.update_outputs()
            self.update_inputs()

    def _setup(self):
        """
        Setup the lockbox parameters according to this stage
        """
        for output in self.lockbox.outputs:
            (on, offset_enable, offset) = self.output_on[output.name]
            if offset_enable:
                output.set_ival(offset)
            if on:
                output.lock(self.input, self.variable_value, factor=self.factor)
            else:
                output.unlock()
        if self.function_call!="":
            func = getattr(self.lockbox.model, self.function_call)
            func(self.factor)
        self.lockbox.state = self.name
        #if self.lockbox._widget is not None:
        #    self.lockbox._widget.show_lock(self)
