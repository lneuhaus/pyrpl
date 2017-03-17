from __future__ import division
from . import LockboxModule
from ...attributes import SelectProperty, FloatProperty, BoolProperty, \
    StringProperty
from ...module_attributes import *
from ...widgets.module_widgets import ReducedModuleWidget, \
    LockboxSequenceWidget, LockboxStageWidget, StageOutputWidget

from PyQt4 import QtCore

from collections import OrderedDict

class StageSignalLauncher(SignalLauncher):
    stage_created = QtCore.pyqtSignal(list)
    stage_deleted = QtCore.pyqtSignal(list)
    #stage_renamed = QtCore.pyqtSignal()

class StageOutput(LockboxModule):
    _setup_attributes = ['lock_on',
                         'reset_offset',
                         'offset']
    _gui_attributes = _setup_attributes
    _widget_class = StageOutputWidget
    lock_on = BoolIgnoreProperty(default=False)
    reset_offset = BoolProperty(default=False)
    offset = FloatProperty(default=0, min=-1., max=1.)


class Stage(LockboxModule):
    """
    A stage is a single step in the lock acquisition process
    """
    _gui_attributes = ['input',
                       'setpoint',
                       'duration',
                       'function_call',
                       'gain_factor']
    _setup_attributes = _gui_attributes + ['outputs']
    _widget_class = LockboxStageWidget
    _signal_launcher = StageSignalLauncher

    input = SelectProperty(ignore_errors=True,
                           options=lambda stage: stage.lockbox.inputs.keys())
    setpoint = FloatProperty(default=0, min=-1e6, max=1e6)

    duration = FloatProperty(default=0, min=0, max=1e6)
    function_call = StringProperty()

    gain_factor = FloatProperty(default=1., min=-1e6, max=1e6)

    # outputs is a dict, containing an entry of StageOutput per Lockbox output
    # (initialized in _init_module)
    outputs = ModuleDictProperty(module_cls=LockboxModule)

    def _init_module(self):
        super(Stage, self)._init_module()
        for output in self.lockbox.outputs:
            self.outputs[output.name] = StageOutput
        self._signal_launcher.stage_created.emit([self])
        self.parent._signal_launcher.stage_created.emit([self])
        self.lockbox._logger.debug("Stage %s initialized"%self.name)

    def _clear(self):
        self.lockbox._logger.debug("Deleting stage %s"%self.name)
        self._signal_launcher.stage_deleted.emit([self])
        self.parent._signal_launcher.stage_deleted.emit([self])
        super(Stage, self)._clear()

    @property
    def _states(self):
        """
        Returns the config file branch corresponding to the saved states of the module.
        """
        return self.c._root._get_or_create("stage_" + str(self.name) + "_states")

    def enable(self):
        """
        Setup the lockbox parameters according to this stage
        """
        for output in self.lockbox.outputs:
            setting = self.outputs[output.name]
            if setting.lock_on == 'true':
                output.lock(input=self.input,
                            setpoint=self.setpoint,
                            offset=setting.offset
                                if setting.reset_offset else None,
                            factor=self.factor)
            elif setting.lock_on == 'false':
                output.unlock()
            #elif setting.lock_on == 'ignore':
            #    pass
        if self.function_call!="":
            try:
                func = getattr(self.lockbox, self.function_call)
            except AttributeError:
                self._logger.warning("Could not find the function '%s'  called "
                                     "in stage %s in the Lockbox class. "
                                     "Please specify a valid function name "
                                     "to call!", self.function_call, self.name)
            else:
                try:
                    func(self)
                except TypeError:
                    func()
        self.lockbox.current_state = self.name
