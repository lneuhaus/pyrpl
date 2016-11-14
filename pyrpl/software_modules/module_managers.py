from . import SoftwareModule
from pyrpl.module_widgets import ModuleManagerWidget, IqManagerWidget, \
                                 ScopeManagerWidget

import copy


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

    widget_class = ModuleManagerWidget

    def init_module(self):
        module_list = [getattr(self.pyrpl.rp, name) for name in self.hardware_module_names]
        self.all_modules = copy.copy(module_list)
        self.free_modules = module_list
        self.busy_modules = []

    def pop(self, owner=None):
        """
        Owner is the name of the owner module for display (string)
        :param owner:
        :return:
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
    hardware_module_names = ['asg1', 'asg2']


class PidManager(ModuleManager):
    name = "pids"
    hardware_module_names = ['pid1', 'pid2', 'pid3']


class IqManager(ModuleManager):
    name = "iqs"
    widget_class = IqManagerWidget
    hardware_module_names = ['iq0', 'iq1', 'iq2']

class ScopeManager(ModuleManager):
    name = "scope"
    widget_class = ScopeManagerWidget
    hardware_module_names = ['scope']

