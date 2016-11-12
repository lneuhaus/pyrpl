from pyrpl.modules import BaseModule

class SoftwareModule(BaseModule):
    """
    Module that doesn't communicate with the Redpitaya directly.
    """

    @property
    def shortname(self):
        return self.__class__.__name__.lower()

from .network_analyzer import NetworkAnalyzer