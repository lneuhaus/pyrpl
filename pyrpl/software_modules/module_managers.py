import logging
logger = logging.getLogger(name=__name__)
from ..widgets.module_widgets import ModuleManagerWidget, AsgManagerWidget, PidManagerWidget, IqManagerWidget, \
    ScopeManagerWidget, IirManagerWidget
from ..modules import Module


class InsufficientResourceError(ValueError):
    """
    This exception is raised when trying to pop a module while there is none
    left.
    """
    pass

class ModuleManager(Module):
    """
    Manages access to hardware modules. It is created from a list of
    hardware_modules to manage. For HardwareModules, ti is the manager module
    that is actually displayed in the gui.

    provides the following functions:
      - pop(owner): gives the last module in the list that is currently
      available, and locks it with the string "user" as owner of the
      hardware module
      - free(module): frees the module by reseting its user to None.
      (and enabling back its gui if any).
    """
    _widget_class = ModuleManagerWidget
    _reserved_modules = [] # list-of
    # _int with instrument index that should
    # NOT be available via pop()

    @property
    def hardware_module_names(self):
        """
        Looks in RedPitaya.modules to find how many modules are present.
        :return: list of all module names in redpitaya instance with a name
        looking like:
          - some_module
          - or some_module1, some_module2, some_module3 ...
        """

        return [key for key in self.pyrpl.rp.modules.keys() if key[
                                :-1]==self.name[:-1] or key==self.name[:-1]]

    def __init__(self, parent, name=None):
        super(ModuleManager, self).__init__(parent, name=name)
        self.all_modules = [getattr(self.pyrpl.rp, name) for name in
                             self.hardware_module_names]

    def pop(self, owner=None):
        """
        returns the first available module (starting from the end of the list)
        :param owner: (string): name of the module that is reserving the
        resource leave None if the gui shouldn't be disabled. If no
        available module left, returns None.

        To make sure the module will be freed afterwards, use the context
        manager construct:
        with pyrpl.mod_mag.pop('owner') as mod:
            mod.do_something()
        # module automatically freed at this point
        """
        n = len(self.all_modules)
        for index in range(n):
            index = n - index - 1 # count backwards to reserve last module 1st
            if not index in self._reserved_modules:
                module = self.all_modules[index]
                if module.owner is None:
                    module.owner = owner # this changes the module's visibility
                    return module
        raise InsufficientResourceError('No more ' + self.name + ' left.')

    def free(self, module):
        if module.owner is not None:
            module.owner = None

    def n_modules(self):
        """
        returns the total number of modules
        """
        return len(self.all_modules)

    def n_available(self):
        """
        returns the number of modules still available
        """
        total = 0
        for index, module in enumerate(self.all_modules):  # start with
            if not index in self._reserved_modules:
                if module.owner is None:
                    total += 1
        return total

    @property
    def c(self):
        # no config file section for ModuleManagers
        # otherwise, empty sections such as iqss->iqs would be created
        return None


class Asgs(ModuleManager):
    _widget_class = AsgManagerWidget


class Pids(ModuleManager):
    _widget_class = PidManagerWidget


class Iqs(ModuleManager):
    _widget_class = IqManagerWidget
    _reserved_modules = [2] # iq2 is reserved for spectrum_analyzer


class Scopes(ModuleManager):
    """
    Only one scope, but it should be protected by the slave/owner mechanism.
    """
    _widget_class = ScopeManagerWidget


class Iirs(ModuleManager):
    """
    Only one iir, but it should be protected by the slave/owner mechanism.
    """
    _widget_class = IirManagerWidget


class Trigs(ModuleManager):
    """
    Only one trig, but it should be protected by the slave/owner mechanism.
    """
    pass #_widget_class = IirManagerWidget