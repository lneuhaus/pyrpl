from __future__ import division
from pyrpl.modules import SoftwareModule, SignalLauncher
from pyrpl.attributes import SelectProperty, BoolProperty, StringProperty
from .model import Model
from .models import *
from .signals import OutputSignal, InputSignal
from pyrpl.widgets.module_widgets import LockboxWidget
from pyrpl.pyrpl_utils import get_unique_name_list_from_class_list
from .sequence import Sequence

from collections import OrderedDict
from PyQt4 import QtCore

def all_subclasses(cls):
    return cls.__subclasses__() + [g for s in cls.__subclasses__()
                                   for g in all_subclasses(s)]
    
def all_models():
    return OrderedDict([(model.name, model) for model in
                                 all_subclasses(Model)])


class ModelProperty(SelectProperty):
    """
    Lots of lockbox attributes need to be updated when model is changed
    """
    def set_value(self, obj, val):
        super(ModelProperty, self).set_value(obj, val)
        obj.model_changed()
        return val


class SignalLauncherLockbox(SignalLauncher):
    """
    A SignalLauncher for the lockbox
    """
    output_created = QtCore.pyqtSignal(list)
    output_deleted = QtCore.pyqtSignal(list)
    output_renamed = QtCore.pyqtSignal()
    stage_created = QtCore.pyqtSignal(list)
    stage_deleted = QtCore.pyqtSignal(list)
    stage_renamed = QtCore.pyqtSignal()
    model_changed = QtCore.pyqtSignal()
    state_changed = QtCore.pyqtSignal()
    add_input = QtCore.pyqtSignal(list)
    remove_input = QtCore.pyqtSignal(list)
    update_transfer_function = QtCore.pyqtSignal(list)

    def __init__(self, module):
        super(SignalLauncherLockbox, self).__init__(module)
        self.timer_lock = QtCore.QTimer()
        self.timer_lock.timeout.connect(self.module.goto_next)
        self.timer_lock.setSingleShot(True)

    def kill_timers(self):
        """
        kill all timers
        """
        self.timer_lock.stop()

    # state_changed = QtCore.pyqtSignal() # need to change the color of buttons in the widget
    # state is now a standard Property, signals are caught by the update_attribute_by_name function of the widget.


class Lockbox(SoftwareModule):
    """
    A Module that allows to perform feedback on systems that are well described by a physical model.
    """
    section_name = 'lockbox'
    widget_class = LockboxWidget
    gui_attributes = ["model_name", "default_sweep_output", "auto_relock"]
    setup_attributes = gui_attributes
    model_name = ModelProperty(options=all_models().keys())
    auto_relock = BoolProperty()
    default_sweep_output = SelectProperty(options=[])

    def init_module(self):
        self.signal_launcher = SignalLauncherLockbox(self)
        self.outputs = []
        # self.__class__.default_sweep_output.change_options(self, ['dummy']) # dirty... something needs to be done with this attribute class
        self._asg = None
        self.inputs = []
        self.sequence = Sequence(self, 'sequence')
        self.__class__.model_name.change_options(self, sorted(all_models().keys()))
        self.model_name = sorted(all_models().keys())[0]
        self.model_changed()
        self.state = "unlock"
        # self.add_output() # adding it now creates problem when loading an output named "output1". It is eventually
        # added inside (after) load_setup_attribute

    @property
    def asg(self):
        if self._asg==None:
            self._asg = self.pyrpl.asgs.pop(self.name)
        return self._asg

    @property
    def output_names(self):
        return [output.name for output in self.outputs]

    def sweep(self):
        """
        Performs a sweep of one of the output. No output default kwds to avoid problems when use as a slot.
        """
        self.unlock()
        # if output is None:
        for output in self.outputs:
            output.reset_ival()
        
        index = self.output_names.index(self.default_sweep_output)
        output = self.outputs[index]
        output.sweep()
        self.state = "sweep"

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, val):
        if not val in ['unlock', 'sweep'] + [stage.name for stage in self.sequence.stages]:
            raise ValueError("State should be either unlock, or a valid stage name")
        self._state = val
        # To avoid explicit reference to gui here, one could consider using a DynamicSelectAttribute...
        self.signal_launcher.state_changed.emit()
        return val

    @property
    def stage_names(self):
        return self.sequence.stage_names

    def goto_next(self):
        """
        Goes to the stage immediately after the current one
        """
        if self.state=='sweep' or self.state=='unlock':
            index = 0
        else:
            index = self.stage_names.index(self.state) + 1
        stage = self.stage_names[index]
        self.goto(stage)
        self.signal_launcher.timer_lock.setInterval(self.get_stage(stage).duration*1000)
        if index + 1 < len(self.sequence.stages):
            self.signal_launcher.timer_lock.start()

    def goto(self, stage_name):
        """
        Sets up the lockbox to the stage named stage_name
        """
        self.get_stage(stage_name).setup()

    def lock(self):
        """
        Launches the full lock sequence, stage by stage until the end.
        """
        self.unlock()
        self.goto_next()

    def get_unique_output_name(self):
        idx = 1
        name = 'output' + str(idx)
        while (name in self.output_names):
            idx += 1
            name = 'output' + str(idx)
        return name

    def add_output(self):
        """
        Outputs of the lockbox are added dynamically (for now, inputs are defined by the model).
        """
        output = self._add_output_no_save()
        output.name = output.name  # trigers the write in the config file
        return output

    def _add_output_no_save(self):
        """
        Adds and returns and output without touching the config file (useful when loading an output from the config
        file)
        """
        if self.pyrpl.pids.n_available()<1:
            raise ValueError("All pids are currently in use. Cannot create any more outputs.")
        output = OutputSignal(self)
        output._name = self.get_unique_output_name() # doesn't trigger write in the config file
        self.outputs.append(output)
        setattr(self, output.name, output)
        self.sequence.update_outputs()
        self.__class__.default_sweep_output.change_options(self, [out.name for out in self.outputs])
        """
        if self.widget is not None:
            # Since adding/removing outputs corresponds to dynamic creation of Modules, our attribute's based way of
            # hiding gui update is not effective. Since this is a highly exceptional situation, I don't find it too
            # bad.
            self.widget.add_output(output)
        """
        self.signal_launcher.output_created.emit([output])
        return output

    def remove_output(self, output, allow_remove_last=False):
        """
        Removes and clear output from the list of outputs. if allow_remove_last is left to False, an exception is raised
        when trying to remove the last output.
        """
        if isinstance(output, basestring):
            output = self.get_output(output)
        if not allow_remove_last:
            if len(self.outputs)<=1:
                raise ValueError("There has to be at least one output.")
        if hasattr(self, output.name):
            delattr(self, output.name)
        output.clear()
        self.outputs.remove(output)
        self.sequence.update_outputs()
        if 'outputs' in self.c._keys():
            if output.name in self.c.outputs._keys():
                self.c.outputs._pop(output.name)

        self.__class__.default_sweep_output.change_options(self, [output.name for output in self.outputs])
        """
        if self.widget is not None:
            # Since adding/removing outputs corresponds to dynamic creation of Modules, our attribute's based way of
            # hiding gui update is not effective. Since this is a highly exceptional situation, I don't find it too
            # bad.
            self.widget.remove_output(output)
        """
        self.signal_launcher.output_deleted.emit([output])

    def remove_all_outputs(self):
        """
        Removes all outputs, even the last one.
        """
        while(len(self.outputs)>0):
            self.remove_output(self.outputs[-1], allow_remove_last=True)

    def rename_output(self, output, new_name):
        """
        This changes the name of the output in many different places: lockbox attribute, config file, pid's owner
        """
        if new_name in self.output_names and self.get_output(new_name)!=output:
            raise ValueError("Name %s already exists for an output"%new_name)
        if hasattr(self, output.name):
            delattr(self, output.name)
        setattr(self, new_name, output)
        if output._autosave_active:
            output.c._rename(new_name)
        output._name = new_name
        if output.pid is not None:
            output.pid.owner = new_name
        self.sequence.update_outputs()
        self.__class__.default_sweep_output.change_options(self, [out.name for out in self.outputs])
        self.signal_launcher.output_renamed.emit()
        # --> This also launches the appropriate signal...
        # self.update_output_names()

    #def update_output_names(self):
    #    """
    #    if self.widget is not None:
    #        # Could be done in BaseModule name property...
    #        self.widget.update_output_names()
    #    """
    #    self.__class__.default_sweep_output.change_options(self, [out.name for out in self.outputs])
    #    self.signal_launcher.output_renamed.emit()

    def add_stage(self):
        """
        adds a stage to the lockbox sequence
        """
        return self.sequence.add_stage()

    def remove_stage(self, stage):
        """
        Removes stage from the lockbox seequence
        """
        self.sequence.remove_stage(stage)

    def rename_stage(self, stage, new_name):
        if new_name in self.stage_names and self.get_stage(new_name)!=stage:
            raise ValueError("Name %s already exists for a stage"%new_name)
        if hasattr(self.sequence, stage.name):
            delattr(self.sequence, stage.name)
        setattr(self.sequence, new_name, stage)
        if stage._autosave_active:
            stage.c # make sure stage config section is created ?
            stage.c._rename(new_name)
        stage._name = new_name
        self.signal_launcher.stage_renamed.emit()

    def remove_all_stages(self):
        self.sequence.remove_all_stages()

    def unlock(self):
        """
        Unlocks all outputs, without touching the integrator value.
        """
        self.state = 'unlock'
        self.signal_launcher.timer_lock.stop()
        for output in self.outputs:
            output.unlock()

    def model_changed(self):
        ### model should be redisplayed
        self.model = all_models()[self.model_name](self)
        self.model.load_setup_attributes()
        #if self.widget is not None:
        #    self.widget.change_model(self.model)

        ### outputs are only slightly affected by a change of model: only the unit of their DC-gain might become
        ### obsolete, in which case, it needs to be changed to some value...
        for output in self.outputs:
            output.update_for_model()

        ### inputs are intimately linked to the model used. When the model is changed, the policy is:
        ###  - keep inputs that have a name compatible with the new model.
        ###  - remove inputs that have a name unexpected in the new model
        ###  - add inputs from the new model that have a name not present in the old model
        names = get_unique_name_list_from_class_list(self.model.input_cls)
        intersect_names = []

        to_remove = [] # never iterate on a list that is being deleted
        for input in self.inputs:
            if not input.name in names:
                to_remove.append(input)
            else:
                intersect_names.append(input.name)
        for input in to_remove:
            self._remove_input(input)
        for name, cls in zip(names, self.model.input_cls):
            if not name in intersect_names:
                input = cls(self, name)
                self._add_input(input)
                input.load_setup_attributes()
                input.setup()

        ### update stages: keep outputs unchanged, when input doesn't exist anymore, change it.
        self.sequence.update_inputs()
        self.signal_launcher.model_changed.emit()

    def load_setup_attributes(self):
        """
        This function needs to be overwritten to retrieve the child module attributes as well
        """
        self.remove_all_outputs()
        # load outputs
        if self.c is not None:
            if 'outputs' in self.c._dict.keys():
                for name, output in self.c.outputs._dict.items():
                    if name != 'states':
                        output = self._add_output_no_save()
                        output._autosave_active = False
                        self.rename_output(output, name)
                        output.load_setup_attributes()
                        output._autosave_active = True
        if len(self.outputs)==0:
            self.add_output()  # add at least one output

        # load inputs
        for input in self.inputs:
            input._autosave_active = False
            input.load_setup_attributes()
            input._autosave_active = True

        # load normal attributes (model, default_sweep_output)
        super(Lockbox, self).load_setup_attributes()

        # load sequence
        self.sequence._autosave_active = False
        self.sequence.load_setup_attributes()
        self.sequence._autosave_active = True

    def _remove_input(self, input):
        input.clear()
        self.inputs.remove(input)
        self.signal_launcher.remove_input.emit([input])

    def _add_input(self, input):
        self.inputs.append(input)
        setattr(self, input.name, input)
        self.signal_launcher.add_input.emit([input])

    def _setup(self):
        """
        Sets up the lockbox
        """
        for output in self.outputs:
            output._setup()

    def get_input(self, name):
        """
        retrieves an input by name
        """
        return self.inputs[[input.name for input in self.inputs].index(name)]

    def get_output(self, name):
        """
        retrieves an output by name
        """
        return self.outputs[[output.name for output in self.outputs].index(name)]

    def get_stage(self, name):
        """
        retieves a stage by name
        """
        return self.sequence.get_stage(name)

    def calibrate_all(self):
        """
        Calibrates successively all inputs
        """
        for input in self.inputs:
            input.calibrate()