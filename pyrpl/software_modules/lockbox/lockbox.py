from pyrpl.modules import SoftwareModule
from pyrpl.attributes import SelectProperty
from .model import Model
from .signals import OutputSignal

from collections import OrderedDict


all_models = OrderedDict([(model.name, model) for model in Model.__subclasses__()])


class Lockbox(SoftwareModule):
    """
    A Module that allows to perform feedback on systems that are well described by a physical model.
    """
    name = 'lockbox'
    gui_attributes = ["model", "default_sweep_output"]
    model = SelectProperty(options=all_models.keys())
    default_sweep_output = SelectProperty(options=["dummy"])

    def init_module(self):
        self.outputs = []
        self._asg = None

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

    def add_output(self):
        """
        Outputs of the lockbox are added dynamically (for now, inputs are defined by the model).
        """
        output = OutputSignal(self)
        self.outputs.append(output)
        setattr(self, output.name, output)
        self.__class__.default_sweep_output.change_options([output.name for output in self.outputs])

    def unlock(self):
        for output in self.outputs:
            output.unlock()

    def get_model(self):
        return all_models[self.model](self)

    def model_changed(self):
        for output in self.outputs:
            output.update_for_model()
        self.inputs = self.get_model()