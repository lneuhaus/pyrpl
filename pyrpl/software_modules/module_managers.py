from . import SoftwareModule
from pyrpl.redpitaya import RedPitaya
from pyrpl.module_widgets import ModuleManagerWidget, IqManagerWidget,\
                                 ScopeManagerWidget
from pyrpl.hardware_modules import Scope
import copy
import numpy as np


class ModuleManager(SoftwareModule):
    """
    Manages access to hardware modules. It is created from a list of
    hardware_modules to manage. For HardwareModules, ti is the manager module that is
    actually displayed in the gui.

    provides the following functions:
      - pop(owner): gives the last module in the list that is currently available,
      and locks it with the string "user" as owner of the hardware module
      - free(module): frees the module by reseting its user to None. (and enabling
      back its gui if any).
    """

    name = "some_modules"
    widget_class = ModuleManagerWidget

    @property
    def hardware_module_names(self):
        """
        Looks in RedPitaya.modules to find how many modules are present.
        :return: list of all module names in redpitaya instance with a name looking like:
          - some_module
          - or some_module1, some_module2, some_module3 ...
        """

        return [key for key in self.pyrpl.rp.modules.keys() if key[:-1]==self.name[:-1] or key==self.name[:-1]]

    def init_module(self):
        module_list = [getattr(self.pyrpl.rp, name) for name in self.hardware_module_names]
        self.all_modules = copy.copy(module_list)
        self.free_modules = module_list
        self.busy_modules = []

    def pop(self, owner=None):
        """
        returns the first available module (starting from the end of the list)
        :param owner: (string): name of the module that is reserving the resource
        leave None if the gui shouldn't be disabled
        """
        module = self.free_modules.pop()
        module.owner = owner
        self.busy_modules.append(module)
        if self.widget is not None:
            self.widget.show_ownership()
        return module

    def free(self, module):
        if module in self.busy_modules:
            module.owner = None
            self.busy_modules.remove(module)
            self.free_modules.append(module)
        if self.widget is not None:
            self.widget.show_ownership()


class AsgManager(ModuleManager):
    name = "asgs"
    # hardware_module_names = ["asg1", "asg2"]  # The same info would be duplicated from redpitaya.py

class PidManager(ModuleManager):
    name = "pids"
    # hardware_module_names = ["pid1", "pid2", "pid3", "pid4"]  # The same info would be duplicated from redpitaya.py


class IqManager(ModuleManager):
    name = "iqs"
    widget_class = IqManagerWidget
    # hardware_module_names = ["iq1", "iq2", "iq3"]  # The same info would be duplicated from redpitaya.py


class ScopeManager(ModuleManager):
    """
    Only one scope, but it should be protected by the slave/owner mechanism.
    """

    name = "scopes"
    widget_class = ScopeManagerWidget
    # hardware_module_names = ["scope"]  # The same info would be duplicated from redpitaya.py