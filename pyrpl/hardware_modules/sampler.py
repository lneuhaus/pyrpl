from pyrpl.attributes import FloatRegister
from pyrpl.modules import HardwareModule
from . import DSP_INPUTS

from time import time

class Sampler(HardwareModule):
    """ this module provides a sample of each signal.

    This is a momentary workaround, will be improved later on with an upgraded FPGA version """

    section_name = 'sampler'
    addr_base = 0x40300000

    def mean_stddev(self, signal="asg1", t = 1e-2):
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
        try:  # signal can be a string, or a module (whose name is the name of the signal we'll use)
            signal = signal.name
        except AttributeError:
            pass
        t0 = time()  # get start time
        nn = 0
        cum = 0
        cumsq = 0
        #while time()-t0 < n*8e-9:
        while time() < t0 + t:
            nn += 1
            value = self.__getattribute__(signal)
            cum += value
            cumsq += value ** 2
        mean = float(cum) / nn
        stddev = (float(cumsq) / nn - mean ** 2) ** 0.5
        return mean, stddev

for inp, num in DSP_INPUTS.items():
    setattr(Sampler,
            inp,
            FloatRegister(
                0x10 + num * 0x10000,
                bits=14,
                norm=2 ** 13 - 1,
                doc="output signal " + inp))