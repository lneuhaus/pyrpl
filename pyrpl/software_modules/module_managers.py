import logging
logger = logging.getLogger(name=__name__)
from ..widgets.module_widgets import ModuleManagerWidget, IqManagerWidget,\
                                 ScopeManagerWidget, IirManagerWidget
from . import SoftwareModule


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

    section_name = "some_modules"
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
        self.all_modules = [getattr(self.pyrpl.rp, name) for name in self.hardware_module_names]

    def pop(self, owner=None):
        """
        returns the first available module (starting from the end of the list)
        :param owner: (string): name of the module that is reserving the resource
        leave None if the gui shouldn't be disabled.
        If no available module left, returns None.
        """
        for module in self.all_modules[-1::-1]: # start with largest index module
            if module.owner is None:
                module.owner = owner # this changes the visibility of the module
                return module
        return None

    def free(self, module):
        if module.owner is not None:
            module.owner = None

    @property
    def c(self):
        # no config file section for ModuleManagers
        # otherwise, empty sections such as iqss->iqs would be created
        return None

class AsgManager(ModuleManager):
    section_name = "asgs"
    # hardware_module_names = ["asg1", "asg2"]  # The same info would be duplicated from redpitaya.py

class PidManager(ModuleManager):
    section_name = "pids"
    # hardware_module_names = ["pid1", "pid2", "pid3", "pid4"]  # The same info would be duplicated from redpitaya.py


class IqManager(ModuleManager):
    section_name = "iqs"
    widget_class = IqManagerWidget
    # hardware_module_names = ["iq1", "iq2", "iq3"]  # The same info would be duplicated from redpitaya.py


class ScopeManager(ModuleManager):
    """
    Only one scope, but it should be protected by the slave/owner mechanism.
    """

    section_name = "scopes"
    widget_class = ScopeManagerWidget
    # hardware_module_names = ["scope"]  # The same info would be duplicated from redpitaya.py

class IirManager(ModuleManager):
    """
    Only one iir, but it should be protected by the slave/owner mechanism.
    """

    section_name = "iirs"
    widget_class = IirManagerWidget