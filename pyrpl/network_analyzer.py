import numpy as np
import sys
from time import sleep, time

from redpitaya_modules import NotReadyError


class NetworkAnalyzer(object):
    def __init__(self, rp):
        self.rp = rp
        self.iq_name = 'iq1'
        self.start = 1
        self.stop = 100000
        self.points = 1001
        self.rbw = 100
        self.avg = 1
        self.amplitude = 0.01
        self.input = 'adc1'
        self.output_direct = 'out1'
        self.acbandwidth = 0
        self.sleeptimes = 0.5
        self.logscale = False
        self.stabilize = False # if False, no stabilization, if float,
        #input amplitude is kept at a constant voltage
        self.maxamplitude = 1.0
        self._setup = False

    @property
    def params(self):
        return dict(start=self.start,
                    stop=self.stop,
                    avg=self.avg,
                    rbw=self.rbw,
                    points=self.points,
                    input=self.input,
                    output_direct=self.output_direct,
                    stabilize=self.stabilize,
                    acbandwidth=self.acbandwidth,
                    amplitude=self.amplitude,
                    logscale=self.logscale)

    @property
    def iq(self):
        return getattr(self.rp, self.iq_name)

    @property
    def output_directs(self):
        return self.iq.output_directs

    @property
    def inputs(self):
        return self.iq.inputs

    def setup(  self,
                iq_name=None,
                start=None,     # start frequency
                stop=None,  # stop frequency
                points=None, # number of points
                rbw=None,     # resolution bandwidth, can be a list of 2 as well for second-order
                avg=None,     # averages
                amplitude=None, #output amplitude in volts
                input=None, # input signal
                output_direct=None, # output signal
                acbandwidth=None, # ac filter bandwidth, 0 disables filter, negative values represent lowpass
                sleeptimes=None, # wait sleeptimes/rbw for quadratures to stabilize
                logscale=None, # make a logarithmic frequency sweep
                stabilize=None, # if a float, output amplitude is adjusted dynamically so that input amplitude [V]=stabilize
                maxamplitude=None): # amplitude can be limited):
        """
        Sets up an acquisition (parameters with value None are left unchanged)

        Parameters
        ----------
        iq_name
        start
        stop
        points
        rbw
        avg
        amplitude
        input
        output_direct
        acbandwidth
        sleeptimes
        logscale
        stabilize
        maxamplitude

        Returns
        -------
        None
        """
        if start is not None: self.start = start
        if stop is not None: self.stop = stop
        if points is not None: self.points = points
        if rbw is not None: self.rbw = rbw
        if avg is not None: self.avg = avg
        if amplitude is not None: self.amplitude = amplitude
        if input is not None: self.input = input
        if output_direct is not None: self.output_direct = output_direct
        if acbandwidth is not None: self.acbandwidth = acbandwidth
        if sleeptimes is not None: self.sleeptimes = sleeptimes
        if logscale is not None: self.logscale = logscale
        if stabilize is not None: self.stabilize = stabilize
        if maxamplitude is not None: self.maxamplitude = maxamplitude

        self._setup = True

        if self.logscale:
            self.x = np.logspace(
                np.log10(self.start),
                np.log10(self.stop),
                self.points,
                endpoint=True)
        else:
            self.x = np.linspace(self.start, self.stop, self.points, endpoint=True)

        #self.y = np.zeros(self.points, dtype=np.complex128)
        #self.drive_amplitudes = np.zeros(self.points, dtype=np.float64)

        # preventive saturation
        maxamplitude = abs(self.maxamplitude)
        amplitude = abs(self.amplitude)
        if amplitude>maxamplitude:
            amplitude = maxamplitude
        self.iq.setup(frequency=self.x[0],
                 bandwidth=self.rbw,
                 gain=0,
                 phase=0,
                 acbandwidth=-np.array(self.acbandwidth),
                 amplitude=amplitude,
                 input=self.input,
                 output_direct=self.output_direct,
                 output_signal='output_direct')

        # take the discretized rbw (only using first filter cutoff)
        rbw = self.iq.bandwidth[0]
        #self.iq._logger.info("Estimated acquisition time: %.1f s",
        #                  float(self.avg + self.sleeptimes) * self.points / self.rbw)
        #sys.stdout.flush()  # make sure the time is shown
        # setup averaging
        self.iq._na_averages = np.int(np.round(125e6 / self.rbw * self.avg))
        self._na_sleepcycles = np.int(np.round(125e6 / self.rbw * self.sleeptimes))
        # compute rescaling factor
        rescale = 2.0 ** (-self.iq._LPFBITS) * 4.0  # 4 is artefact of fpga code
        # obtained by measuring transfer function with bnc cable - could replace the inverse of 4 above
        # unityfactor = 0.23094044589192711

        #try:


        self._rescale = 2.0 ** (-self.iq._LPFBITS) * 4.0  # 4 is artefact of fpga code
        self.current_point = 0

        #self.iq.amplitude = self.amplitude  # turn on NA inside try..except block
        self.iq.frequency = self.x[0]  # this triggers the NA acquisition
        self.time_last_point = time()


    @property
    def current_freq(self):
        return self.iq.frequency

    @property
    def rbw(self):
        return self.iq.bandwidth[0]

    @rbw.setter
    def rbw(self, val):
        self.iq.bandwidth = val
        return val

    @property
    def amplitude(self):
        return self._amplitude

    @amplitude.setter
    def amplitude(self, val):
        self.iq.amplitude = val
        self._amplitude = self.iq.amplitude
        return val

    @property
    def iq_names(self):
        return ["iq0", "iq1", "iq2"]

    @property
    def time_per_point(self):
        return 1.0 / self.rbw * (self.avg + self.sleeptimes)

    def get_current_point(self):
        """blocks until time_per_point is reached"""
        current_time = time()
        duration = current_time - self.time_last_point
        remaining = self.time_per_point - duration
        if remaining >= 0:
            sleep(remaining)
        x = self.iq.frequency  # get the actual (discretized) frequency
        y = self.iq._nadata
        amp = self.amplitude
        # normalize immediately
        if amp == 0:
            y *= self._rescale  # avoid division by zero
        else:
            y *= self._rescale / amp
        return x, y, amp

    def prepare_for_next_point(self, last_normalized_val):
        """
        set everything for next point
        """
        if self.stabilize is not False:
            amplitude_next = self.stabilize / np.abs(y)
        else:
            amplitude_next = self.amplitude
        if amplitude_next > self.maxamplitude:
            amplitude_next = self.maxamplitude
        self.iq.amplitude = amplitude_next
        self.current_point += 1
        if self.current_point < self.points:
            self.iq.frequency = self.x[self.current_point]
        self.time_last_point = time()  # check averaging time from now

    def values(self):
        """
        Returns
        -------
        A generator of successive values for the na curve.
        The generator can be used in a for loop:
        for val in na.values():
            print val
        or individual values can be fetched succesively by calling
        values = na.values()
        val1 = values.next()
        val2 = values.next()

        values are made of a triplet (freq, complex_amplitude, amplitude)
        """
        try:
            #for point in xrange(self.points):
            while self.current_point<self.points:
                #self.current_point = point
                x, y, amp = self.get_current_point()
                if self.start == self.stop:
                    x = time()
                self.prepare_for_next_point(y)
                yield (x, y, amp)
        except Exception as e:
            self.iq._logger.info("NA output turned off due to an exception")
            raise e
        finally:
            self.iq.amplitude = 0
            self.iq.frequency = self.x[0]

    def curve(self):
        """
        Once setup has been called, this acquires a curve.
        Returns
        -------
        (array of frequencies, array of complex ampl, array of amplitudes)
        """
        if not self._setup:
            raise NotReadyError("call setup() before first curve")
        xs = np.zeros(self.points, dtype=float)
        ys = np.zeros(self.points, dtype=complex)
        amps = np.zeros(self.points, dtype=float)
        for index, (x, y, amp) in enumerate(self.values()):
            xs[index] = x
            ys[index] = y
            amps[index] = amp
        return xs, ys, amps
