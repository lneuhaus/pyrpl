import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *


class LMSD(FabryPerot):
    export_to_parent = ['unlock', 'sweep', 'islocked',
                        'save_current_gain', 'calibrate',
                        'lock_tilt', 'lock_transmission', 'lock']

    def lmsd(self, detuning):
        return self.pdh(detuning)
