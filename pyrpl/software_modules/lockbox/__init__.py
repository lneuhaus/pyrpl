from ...modules import SoftwareModule
from ...attributes import ModuleContainerProperty


class LockboxModule(SoftwareModule):
    @property
    def lockbox(self):
        parent = self
        while not isinstance(parent, Lockbox):
            parent = parent.parent
        return parent

class LockboxModuleContainerProperty(ModuleContainerProperty):
    default_module_cls = LockboxModule


from .lockbox import Lockbox
