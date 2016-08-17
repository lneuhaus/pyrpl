import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *

class FPMembranes(FabryPerot):
    def reset_ival(self):
        pass
        #self.outputs['current'].pid.ival = 0
