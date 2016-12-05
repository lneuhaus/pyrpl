from pyrpl.attributes import SelectProperty, FloatProperty, BoolProperty, DynamicSelectProperty, StringProperty
from pyrpl.modules import SoftwareModule
from pyrpl.widgets.module_widgets import LockboxSequenceWidget, LockboxStageWidget

class Sequence(SoftwareModule):
    widget_class = LockboxSequenceWidget
    section_name = 'sequence'

    def init_module(self):
        self.stages = []

    def add_stage(self):
        """
        Stages can be added at will.
        """
        stage = Stage(self)
        self.stages.append(stage)
        setattr(self, stage.name, stage)
        # self.__class__.default_sweep_output.change_options([output.name for output in self.outputs])
        if self.widget is not None:
            self.widget.add_stage(stage)
        return stage

    def rename_stage(self, name):
        pass

    def remove_stage(self, stage):
        pass


class Stage(SoftwareModule):
    """
    A stage is a single step in the lock acquisition process
    """
    gui_attributes = ['input', 'parameter_value', 'start_offset_enabled', 'start_offset', 'duration', 'function_call']
    section_name = 'stage'
    name = StringProperty(default='my_stage')
    widget_class = LockboxStageWidget
    input = DynamicSelectProperty()
    outputs = []
    parameter_value = FloatProperty()
    start_offset_enabled = BoolProperty()
    start_offset = FloatProperty()
    duration = FloatProperty()
    function_call = StringProperty()

    def init_module(self):
        self.lockbox = self.parent.parent
        self.__class__.input.change_options(self, [input.name for input in self.lockbox.inputs])


