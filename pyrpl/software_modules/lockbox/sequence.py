from __future__ import division
from . import LockboxModule
from ...attributes import SelectProperty, FloatProperty, BoolProperty, StringProperty, \
                            ListStageOuputProperty, ModuleListProperty
from ...widgets.module_widgets import LockboxSequenceWidget, LockboxStageWidget

from collections import OrderedDict


class Stage(LockboxModule):
    """
    A stage is a single step in the lock acquisition process
    """
    _setup_attributes = ['input',
                         'variable_value',
                         'output_on',
                         'duration',
                         'function_call',
                         'factor']
    _gui_attributes = _setup_attributes
    _widget_class = LockboxStageWidget
    input = SelectProperty()
    output_on = ListStageOuputProperty()
    variable_value = FloatProperty(min=-1e6, max=1e6)
    duration = FloatProperty(min=0, max=1e6)
    function_call = StringProperty()
    factor = FloatProperty(default=1., min=-1e6, max=1e6)

    def _load_setup_attributes(self):
        pass

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
            try:
                func(**self.get_setup_attributes())
            except TypeError:
                func()
        self.lockbox.state = self.name
        #if self.lockbox._widget is not None:
        #    self.lockbox._widget.show_lock(self)


class Sequence(LockboxModule):
    """ A sequence is a list of Stages """
    _widget_class = LockboxSequenceWidget
    stages = ModuleListProperty(Stage)
    stages._widget_class = LockboxSequenceWidget

    def add_stage(self):
        """
        Stages can be added at will.
        """
        stage = self.add_stage_no_save()
        stage.name = stage.name  # triggers a save in the config file...
        return stage

    def add_stage_no_save(self):
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
        if new_name in self.stage_names and self.get_stage(new_name)!=stage:
            raise ValueError("Name %s already exists for a stage"%new_name)
        if hasattr(self, stage.name):
            delattr(self, stage.name)
        setattr(self, new_name, stage)
        if stage._autosave_active:
            stage.c # make sure stage config section is created ?
            stage.c._rename(new_name)
        stage._name = new_name
        self.update_stage_names()

    def update_stage_names(self):
        self.lockbox._signal_launcher.stage_renamed.emit()

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

    # def _load_setup_attributes(self):
    #     #import pdb
    #     #pdb.set_trace()
    #     self.remove_all_stages()
    #     if self.c is not None:
    #         if 'stages' in self.c._dict.keys():
    #             for name, stage in self.c.stages._dict.items():
    #                 if name!='states':
    #                     stage = self.add_stage_no_save() # don't make a duplicate entry in the config file
    #                     stage._autosave_active = False
    #                     self.rename_stage(stage, name)
    #                     stage._load_setup_attributes()
    #                     stage._autosave_active = True
    #     if len(self.stages)==0:
    #         self.add_stage()
    #
