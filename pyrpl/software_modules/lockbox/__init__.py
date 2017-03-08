from ...modules import Module
from ...module_attributes import ModuleContainerProperty


class LockboxModule(Module):
    @property
    def lockbox(self):
        parent = self
        while not isinstance(parent, Lockbox):
            parent = parent.parent
        return parent

class LockboxModuleContainerProperty(ModuleContainerProperty):
    default_module_cls = LockboxModule


from .lockbox import Lockbox
