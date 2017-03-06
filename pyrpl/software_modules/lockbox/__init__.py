from ...modules import SoftwareModule


class LockboxModule(SoftwareModule):
    @property
    def lockbox(self):
        parent = self
        while not isinstance(parent, Lockbox):
            parent = parent.parent
        return parent

from .lockbox import Lockbox