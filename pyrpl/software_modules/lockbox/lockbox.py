from pyrpl.modules import SoftwareModule
from pyrpl.attributes import SelectProperty
from .model import Model
from .signals import OutputSignal, InputSignal
from pyrpl.widgets.module_widgets import LockboxWidget
from pyrpl.pyrpl_utils import  get_unique_name_list_from_class_list
from .sequence import Sequence

from collections import OrderedDict


all_models = OrderedDict([(model.name, model) for model in Model.__subclasses__()])


class ModelProperty(SelectProperty):
    """
    Lots of lockbox attributes need to be updated when model is changed
    """
    def set_value(self, obj, val):
        super(ModelProperty, self).set_value(obj, val)
        obj.model_changed()
        return val


class Lockbox(SoftwareModule):
    """
    A Module that allows to perform feedback on systems that are well described by a physical model.
    """
    section_name = 'lockbox'
    widget_class = LockboxWidget
    gui_attributes = ["model", "default_sweep_output"]
    setup_attributes = gui_attributes
    model = ModelProperty(options=all_models.keys())
    default_sweep_output = SelectProperty(options=["dummy"])

    def init_module(self):
        self.outputs = []
        self._asg = None
        self.inputs = []
        self.sequence = Sequence(self, 'sequence')
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
        self.sequence.update_outputs()
        if self.widget is not None:
            self.widget.add_output(output)
        return output

    def remove_output(self, output):
        output.clear()
        self.outputs.remove(output)
        self.sequence.update_outputs()
        if 'outputs' in self.c._keys():
            if output.name in self.c.outputs._keys():
                self.c.outputs._pop(output.name)
        if self.widget is not None:
            self.widget.remove_output(output)

    def rename_output(self, output, new_name):
        if hasattr(self, output.name):
            delattr(self, output.name)
        setattr(self, new_name, output)
        if output._autosave_active:
            output.c._rename(new_name)
        output._name = new_name
        if output.pid is not None:
            output.pid.owner = new_name
            if output.pid.widget is not None:
                output.pid.widget.show_ownership()
        self.sequence.update_outputs()
        self.update_output_names()

    def update_output_names(self):
        if self.widget is not None:
            self.widget.update_output_names()

    def unlock(self):
        for output in self.outputs:
            output.unlock()

    def get_model(self):
        return all_models[self.model](self)

    def model_changed(self):
        ### model should be redisplayed
        model = self.get_model()
        model.load_setup_attributes()
        if self.widget is not None:
            self.widget.change_model(model)

        ### outputs are only slightly affected by a change of model: only the unit of their DC-gain might become
        ### obsolete, in which case, it needs to be changed to some value...
        for output in self.outputs:
            output.update_for_model()

        ### inputs are intimately linked to the model used. When the model is changed, the policy is:
        ###  - keep inputs that have a name compatible with the new model.
        ###  - remove inputs that have a name unexpected in the new model
        ###  - add inputs from the new model that have a name not present in the old model
        model = self.get_model()
        names = get_unique_name_list_from_class_list(model.input_cls)
        intersect_names = []

        to_remove = [] # never iterate on a list that is being deleted
        for input in self.inputs:
            if not input.name in names:
                to_remove.append(input)
            else:
                intersect_names.append(input.name)
        for input in to_remove:
            self._remove_input(input)
        for name, cls in zip(names, model.input_cls):
            if not name in intersect_names:
                input = cls(self, name)
                self._add_input(input)
                input.load_setup_attributes()

        ### update stages: keep outputs unchanged, when input doesn't exist anymore, change it.
        self.sequence.update_inputs()


    def load_setup_attributes(self):
        """
        This function needs to be overwritten to retrieve the child module attributes as well
        """
        # load normal attributes (model, default_sweep_output)
        super(Lockbox, self).load_setup_attributes()

        # load outputs
        if self.c is not None:
            if 'outputs' in self.c._dict.keys():
                for name, output in self.c.outputs._dict.items():
                    if name!='states':
                        output = self.add_output()
                        output._autosave_active = False
                        self.rename_output(output, name)
                        output.load_setup_attributes()
                        output._autosave_active = True

        # load inputs
        for input in self.inputs:
            input.load_setup_attributes()

        # load sequence
        self.sequence.load_setup_attributes()

    def _remove_input(self, input):
        input.clear()
        if self.widget is not None:
            self.widget.remove_input(input)
        self.inputs.remove(input)

    def _add_input(self, input):
        self.inputs.append(input)
        setattr(self, input.name, input)
        if self.widget is not None:
            self.widget.add_input(input)


    def _setup(self):
        """
        Sets up the lockbox
        """
        for output in self.outputs:
            output._setup()

