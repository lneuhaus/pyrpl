from pyrpl.modules import SoftwareModule
from pyrpl.attributes import SelectProperty
from .model import Model
from .signals import OutputSignal, InputSignal
from pyrpl.widgets.module_widgets import LockboxWidget
from pyrpl.pyrpl_utils import  get_unique_name_list_from_class_list

from collections import OrderedDict


all_models = OrderedDict([(model.name, model) for model in Model.__subclasses__()])


class Lockbox(SoftwareModule):
    """
    A Module that allows to perform feedback on systems that are well described by a physical model.
    """
    section_name = 'lockbox'
    widget_class = LockboxWidget
    gui_attributes = ["model", "default_sweep_output"]
    setup_attributes = gui_attributes
    model = SelectProperty(options=all_models.keys())
    default_sweep_output = SelectProperty(options=["dummy"])

    def init_module(self):
        self.outputs = []
        self._asg = None
        self.model_changed()

    @property
    def asg(self):
        if self._asg==None:
            self._asg = self.pyrpl.asgs.pop(self.name)
        return self._asg

    def sweep(self, output=None):
        """
        Performs a sweep of one of the output. If no output is specified, the default sweep_output is used.
        """
        self.unlock
        if output is None:
            output = self.default_sweep_output
        self._asg.output = output

#    def get_unique_output_id(self):
#        """
#        returns the smallest id that is unoccupied by an output
#        """
#        i = 1
#        while i in [output.id for output in self.outputs]:
#            i+=1
#        return i

    def add_output(self):
        """
        Outputs of the lockbox are added dynamically (for now, inputs are defined by the model).
        """
        output = OutputSignal(self)
        # output.name = 'output' + str(self.get_unique_output_id())
        self.outputs.append(output)
        setattr(self, output.name, output)
        # self.__class__.default_sweep_output.change_options([output.name for output in self.outputs])
        if self.widget is not None:
            self.widget.add_output(output)
        return output

    def rename_output(self, output, new_name):
        setattr(self, new_name, output)
        if hasattr(self, output.name):
            delattr(self, output.name)
        if output._autosave_active:
            output.c._rename(new_name)
        output._name = new_name
        if output.pid is not None:
            output.pid.owner = new_name
            if output.pid.widget is not None:
                output.pid.widget.show_ownership()
        self.update_output_names()

    def update_output_names(self):
        if self.widget is not None:
            self.widget.update_output_names()

    def remove_output(self, output):
        output.clear()
        self.outputs.remove(output)
        if self.widget is not None:
            self.widget.remove_output(output)

    def unlock(self):
        for output in self.outputs:
            output.unlock()

    def get_model(self):
        return all_models[self.model](self)

    def model_changed(self):
        for output in self.outputs:
            output.update_for_model()
        self.inputs = []
        # for name, input_cls in [(name, cls) for (name, cls) in self.get_model().__class__.__dict__.items() if \
        #                 isinstance(cls, type) and issubclass(cls, InputSignal)]:
        model = self.get_model()
        names = get_unique_name_list_from_class_list(model.input_cls)
        for name, cls in zip(names, model.input_cls):
            self.inputs.append(cls(self, name))

        #for name, output_cls in [(name, cls) for (name, cls) in self.get_model().__class__.__dict__.items() if \
        #                   isinstance(cls, type) and issubclass(cls, OutputSignal)]:
        #    self.outputs.append(output_cls(self, name))

    def load_setup_attributes(self):
        """
        This function needs to be overwritten to retrieve the child module attributes as well
        """
        super(Lockbox, self).load_setup_attributes()
        if self.c is not None:
            if 'outputs' in self.c._dict.keys():
                for name, output in self.c.outputs._dict.items():
                    if name!='states':
                        output = self.add_output()
                        output._autosave_active = False
                        output.name = name
                        output.load_setup_attributes()
                        output._autosave_active = True
        for input in self.inputs:
            input.load_setup_attributes()

    def _setup(self):
        """
        Sets up the lockbox
        """
        for output in self.outputs:
            output._setup()

