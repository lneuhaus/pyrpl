from __future__ import division
from . import LockboxModule
from ...attributes import SelectProperty, FloatProperty, BoolProperty, StringProperty, \
                            ListStageOuputProperty
from ...module_attributes import *
from ...widgets.module_widgets import LockboxSequenceWidget, LockboxStageWidget

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
    lock_on = SelectProperty(default='false', options=['true', 'false', 'ignore'])
    reset_offset = SelectProperty(default=False, options=[True, False])
    offset = FloatProperty(default=0, min=-1., max=1.)



class Stage(LockboxModule):
    """
    A stage is a single step in the lock acquisition process
    """
    _setup_attributes = ['input',
                         'setpoint',
                         'duration',
                         'function_call',
                         'gain_factor'] #,
                         #'outputs']
    _gui_attributes = _setup_attributes
    _widget_class = LockboxStageWidget
    _signal_launcher = StageSignalLauncher

    input = SelectProperty(options=lambda stage: stage.lockbox.inputs.keys())
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

    def _clear(self):
        self._signal_launcher.stage_deleted.emit([self])
        self.parent._signal_launcher.stage_deleted.emit([self])
        super(Stage, self)._clear()

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
        self.lockbox.state = self
