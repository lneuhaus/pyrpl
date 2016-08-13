import numpy as np
import sys
from time import sleep, time
import logging

from .redpitaya_modules import NotReadyError


class NetworkAnalyzer(object):
    """
    Using an IQ module, the network analyzer can measure the complex coherent
    response between an output and any signal in the redpitaya.

    2 ways to use the NetworkAnalyzer:
      exemple 1:
            r = RedPitaya("1.1.1.1")
            na = NetworkAnalyzer(r)
            curve = na.curve(start=100, stop=1000, rbw=10...)
      exemple 2:
            na.start = 100
            na.stop = 1000
            curve = na.curve(rbw=10)
      exemple 3:
            na.setup(start=100, stop=1000, ...)
            for freq, response, amplitude in na.values():
                print response
    """

    def __init__(self, rp):
        self._logger = logging.getLogger(__name__)
        self.rp = rp
        self.start = 200
        self.stop = 50000
        self.points = 1001
        self.rbw = 200
        self.avg = 1
        self.amplitude = 0.01
        self.input = 'adc1'
        self.output_direct = 'off'
        self.acbandwidth = 0
        self.sleeptimes = 0.5
        self.logscale = False
        self.stabilize = False  # if False, no stabilization, if float,
        #input amplitude is kept at a constant voltage
        self.maxamplitude = 1.0
        self._setup = False

    @property
    def params(self):
        """
        Parameters to save.
        """
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
        """
        underlying iq module.
        """
        if not hasattr(self, '_iq'):
            self._iq = self.rp.iqs.pop()
        return self._iq

    @property
    def output_directs(self):
        return self.iq.output_directs

    @property
    def inputs(self):
        return self.iq.inputs

    @property
    def acbandwidth(self):
        return self.iq.inputfilter*-1

    @acbandwidth.setter
    def acbandwidth(self, v):
        self.iq.inputfilter = v*-1

    def setup(  self,
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
        start: frequency start
        stop: frequency stop
        points: number of points
        rbw: inverse averaging time per point
        avg: number of points to average before moving to the next
        amplitude: output amplitude (V)
        input: input signal
        output_direct: output drive
        acbandwidth: bandwidth of the input high pass filter
        sleeptimes: the number of averages to wait before acquiring new data
                    for the next point.
        logscale: should the frequency scan be distributed logarithmically?
        stabilize: if float, stabilizes the drive amplitude such that the
                    input remains constant
        at input [V]=stabilize. If False, then no stabilization
        maxamplitude: limit to the output amplitude

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

        # preventive saturation
        maxamplitude = abs(self.maxamplitude)
        amplitude = abs(self.amplitude)
        if amplitude > maxamplitude:
            amplitude = maxamplitude
        self.iq.setup(frequency=self.x[0],
                      bandwidth=self.rbw,
                      gain=0,
                      phase=0,
                      acbandwidth=self.acbandwidth,
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
        # obtained by measuring transfer function with bnc cable - could replace the inverse of 4 above
        # unityfactor = 0.23094044589192711
        self._rescale = 2.0 ** (-self.iq._LPFBITS) * 4.0  # 4 is artefact of fpga code
        self.current_point = 0
        self.iq.frequency = self.x[0]  # this triggers the NA acquisition
        self.time_last_point = time()

    @property
    def current_freq(self):
        """
        current frequency during the scan
        """

        return self.iq.frequency

    @property
    def rbw(self):
        """
        rbw of the underlying iq
        """
        return self.iq.bandwidth[0]

    @rbw.setter
    def rbw(self, val):
        try:
            val = list(val)
        except:
            val = [val, val]  # preferentially choose second order filter
        self.iq.bandwidth = val
        return val

    @property
    def amplitude(self):
        return self._amplitude

    @amplitude.setter
    def amplitude(self, val):
        # the na easily messes up other functionaliy by outputting a sine.
        # self.iq.amplitude = val
        #self._amplitude = self.iq.amplitude
        self._amplitude = val

    @property
    def time_per_point(self):
        return 1.0 / self.rbw * (self.avg + self.sleeptimes)

    def get_current_point(self):
        """
        This function fetches the current point on the redpitaya.
        The function blocks until the time since the last point has reached
        time_per_point
        """

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
        # correct for network analyzer transfer function (AC-filter and delay)
        y /= self.transfer_function(x)
        return x, y, amp

    def prepare_for_next_point(self, last_normalized_val):
        """
        Sets everything for next point
        """

        if self.stabilize is not False:
            amplitude_next = self.stabilize / np.abs(last_normalized_val)
        else:
            amplitude_next = self.amplitude
        if amplitude_next > self.maxamplitude:
            amplitude_next = self.maxamplitude
        self.iq.amplitude = amplitude_next
        self.current_point += 1
        if self.current_point < self.points:
            # writing to iq.frequency triggers the acquisition
            self.iq.frequency = self.x[self.current_point]
        else:
            # turn off the modulation when done
            self.iq.amplitude = 0
        self.time_last_point = time()  # check averaging time from now

    def values(self):
        """
        Returns
        -------
        A generator of successive values for the na curve.
        The generator can be used in a for loop:
        for val in na.values():
            print val
        or individual values can be fetched successively by calling
        values = na.values()
        val1 = values.next()
        val2 = values.next()

        values are made of a triplet (freq, complex_response, amplitude)
        """

        try:
            #for point in xrange(self.points):
            while self.current_point < self.points:
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

    def curve(self,
              start=None,  # start frequency
              stop=None,  # stop frequency
              points=None,  # number of points
              rbw=None,  # resolution bandwidth, can be a list of 2 as well for second-order
              avg=None,  # averages
              amplitude=None,  # output amplitude in volts
              input=None,  # input signal
              output_direct=None,  # output signal
              acbandwidth=None,  # ac filter bandwidth, 0 disables filter, negative values represent lowpass
              sleeptimes=None,  # wait sleeptimes/rbw for quadratures to stabilize
              logscale=None,  # make a logarithmic frequency sweep
              stabilize=None,
              # if a float, output amplitude is adjusted dynamically so that input amplitude [V]=stabilize
              maxamplitude=None):  # amplitude can be limited):
        """
        High level function: this sets up the na and acquires a curve. See setup for the explanation of parameters.

        Returns
        -------
        (array of frequencies, array of complex ampl, array of amplitudes)
        """

        self.setup( start=start,  # start frequency
                    stop=stop,  # stop frequency
                    points=points,  # number of points
                    rbw=rbw,  # resolution bandwidth, can be a list of 2 as well for second-order
                    avg=avg,  # averages
                    amplitude=amplitude,  # output amplitude in volts
                    input=input,  # input signal
                    output_direct=output_direct,  # output signal
                    acbandwidth=acbandwidth,  # ac filter bandwidth, 0 disables filter, negative values represent lowpass
                    sleeptimes=sleeptimes,  # wait sleeptimes/rbw for quadratures to stabilize
                    logscale=logscale,  # make a logarithmic frequency sweep
                    stabilize=stabilize,
                    # if a float, output amplitude is adjusted dynamically so that input amplitude [V]=stabilize
                    maxamplitude=maxamplitude)
        #if not self._setup:
        #    raise NotReadyError("call setup() before first curve")
        xs = np.zeros(self.points, dtype=float)
        ys = np.zeros(self.points, dtype=complex)
        amps = np.zeros(self.points, dtype=float)

        self._logger.info("Estimated acquisition time: %.1f s",
                          self.time_per_point * (self.points+1))
        sys.stdout.flush()  # make sure the time is shown immediately

        # set pseudo-acquisition of first point to supress transient effects
        self.iq.amplitude = self.amplitude
        self.iq.frequency = self.start
        sleep(self.time_per_point)

        for index, (x, y, amp) in enumerate(self.values()):
            xs[index] = x
            ys[index] = y
            amps[index] = amp
        return xs, ys, amps

    # delay observed with measurements of the na transfer function
    # expected is something between 3 and 4, so it is okay
    _delay = 3.0

    def transfer_function(self, frequencies, extradelay=0):
        """
        Returns a complex np.array containing the transfer function of the
        current IQ module setting for the given frequency array. The given
        transfer function is only relevant if the module is used as a
        bandpass filter, i.e. with the setting (gain != 0). If extradelay = 0,
        only the default delay is taken into account, i.e. the propagation
        delay from input to output_signal.

        Parameters
        ----------
        frequencies: np.array or float
            Frequencies to compute the transfer function for
        extradelay: float
            External delay to add to the transfer function (in s). If zero,
            only the delay for internal propagation from input to
            output_signal is used. If the module is fed to analog inputs and
            outputs, an extra delay of the order of 200 ns must be passed as
            an argument for the correct delay modelisation.

        Returns
        -------
        tf: np.array(..., dtype=np.complex)
            The complex open loop transfer function of the module.
        """
        module_delay = self._delay
        frequencies = np.array(np.array(frequencies, dtype=np.float),
                               dtype=np.complex)
        tf = np.array(frequencies*0, dtype=np.complex) + 1.0
        # input filter modelisation
        f = self.iq.inputfilter  # no for loop here because only one filter
        # stage
        if f > 0:  # lowpass
            tf /= (1.0 + 1j * frequencies / f)
            module_delay += 2  # two cycles extra delay per lowpass
        elif f < 0:  # highpass
            tf /= (1.0 + 1j * f / frequencies)
            module_delay += 1  # one cycle extra delay per highpass
        # add delay
        delay = module_delay * 8e-9 / self.iq._frequency_correction + \
                extradelay
        tf *= np.exp(-1j * delay * frequencies * 2 * np.pi)
        # add delay from phase (incorrect formula or missing effect...)
        return tf