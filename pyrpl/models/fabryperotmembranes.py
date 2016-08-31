import numpy as np
import scipy
import logging
import time
logger = logging.getLogger(name=__name__)
from . import *
from ..pyrpl_utils import sleep

class FPMembranes(FabryPerot):
    gui_buttons = FabryPerot.gui_buttons + ["sweep_pzt_direct"]

    def reset_ival(self):
        pass
        #self.outputs['current'].pid.ival = 0

    def sweep_pzt_direct(self):
        rp = self._parent.rp
        #old_val = rp.pid3.ival

        #rp.pid3.ival = old_val
        rp.pid2.p = 1
        rp.pid2.input = 'asg1'
        rp.pid2.i = 0
        rp.pid2.ival = 0

        rp.pid1.i = rp.pid1.p = 0

        rp.pid3.p = 0

    def add_piezo_pwm(self, **kwds):
        pid3 = self._parent.rp.pid3
        pid3.input = "pid2"
        pid3.i = -0.0046

    def zoom(self):
        self.sweep_pzt_direct()
        rp = self._parent.rp
        rp.scope_widget.stop()

        threshold = self.inputs['transmission']._config.max * 0.7

        scope = rp.scope
        scope.setup()
        for val in np.linspace(-1, 1, 100):
            rp.pid3.ival = val
            scope.setup()

            curve = scope.curve()
            if np.max(curve)>threshold:
                break
        scope.input2 = 'iq0'
        rp.scope_widget.run_continuous()
