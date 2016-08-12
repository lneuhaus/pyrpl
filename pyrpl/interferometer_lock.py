# Code in this file make a RedPitaya device into 2 channel interferometer lock, which can lock to arbitrary phase.
#
import os
#
from .redpitaya import RedPitaya
from .memory import MemoryTree
#
#####
class InterferometerLock():
    def __init__(self, config='default'):
        self._configdir = os.path.join(os.path.dirname(__file__), "i_config")
        self._configfile = os.path.join(self._configdir, config + '.yml')
        self.c = MemoryTree(self._configfile)
        self.rp = RedPitaya(**self.c.redpitaya._dict)
        print(self.rp)
