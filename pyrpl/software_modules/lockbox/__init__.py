from ...modules import Module
from ...module_attributes import ModuleProperty, ModuleDictProperty


class LockboxModule(Module):
    @property
    def lockbox(self):
        parent = self
        while not isinstance(parent, Lockbox):
            parent = parent.parent
        return parent

class LockboxModuleDictProperty(ModuleDictProperty):
    default_module_cls = LockboxModule


from .lockbox import Lockbox
