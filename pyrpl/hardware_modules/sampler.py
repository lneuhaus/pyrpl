import numpy as np
from ..pyrpl_utils import time
from ..attributes import FloatRegister
from ..modules import HardwareModule
from . import DSP_INPUTS


class Sampler(HardwareModule):
    """ this module provides a sample of each signal.

    This is a momentary workaround, will be improved later on with an upgraded FPGA version """
    addr_base = 0x40300000

    def stats(self, signal="in1", t=1e-2):
        """
        computes the mean, standard deviation, min and max of the chosen signal over duration t

        Parameters
        ----------
        signal: input signal
        t: duration over which to average

        obsolete:
        n: equivalent number of FPGA clock cycles to average over

        Returns
        -------
        mean, stddev, max, min: mean and standard deviation of all samples

        """
        try:  # signal can be a string, or a module (whose name is the name of the signal we'll use)
            signal = signal.name
        except AttributeError:
            pass
        nn = 0
        cum = 0
        cumsq = 0
        max = -np.inf
        min = np.inf
        t0 = time()  # get start time
        while nn == 0 or time() < t0 + t:  # do at least one sample
            nn += 1
            value = self.__getattribute__(signal)
            cum += value
            cumsq += (value ** 2.0)
            if value > max:
                max = value
            if value < min:
                min = value
        nn = float(nn)
        mean = cum / nn
        variance = (cumsq / nn - mean**2.0)
        # while mathematically nonsense, this can happen numerically
        if variance < 0:
            # this means the variance is tiny and can be assumed zero
            variance = 0
        stddev = variance ** 0.5
        return mean, stddev, max, min

    def mean_stddev(self, signal="in1", t=1e-2):
        """
        computes the mean and standard deviation of the chosen signal

        Parameters
        ----------
        signal: input signal
        t: duration over which to average

        obsolete:
        n: equivalent number of FPGA clock cycles to average over

        Returns
        -------
        mean, stddev: mean and standard deviation of all samples

        """
        self._logger.warning("Sampler.mean_stddev() is obsolete. Please use "
                             "Sampler.stats() instead!")
        mean, stddev, max, min = self.stats(signal=signal, t=t)
        return mean, stddev

# generate one attribute in Sampler for each DSP signal
for inp, num in DSP_INPUTS.items():
    setattr(Sampler,
            inp,
            FloatRegister(
                0x10 + num * 0x10000,
                bits=14,
                norm=2 ** 13 - 1,
                doc="current value of " + inp))
