###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#    Copyright (C) 2014-2016  Leonhard Neuhaus  (neuhaus@spectro.jussieu.fr)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################


import scipy.signal as sig
import numpy as np
import logging
from ...errors import ExpectedPyrplError

logger = logging.getLogger(name=__name__)

# this is not strictly needed
try:
    import matplotlib.pyplot as plt
except:
    pass

# this one is essentially a copy-paste from scipy 18 for being compatible with
# lower versions of scipy
def sos2zpk(sos):
    """
    Return zeros, poles, and gain of a series of second-order sections

    Parameters
    ----------
    sos : array_like
        Array of second-order filter coefficients, must have shape
        ``(n_sections, 6)``. See `sosfilt` for the SOS filter format
        specification.

    Returns
    -------
    z : ndarray
        Zeros of the transfer function.
    p : ndarray
        Poles of the transfer function.
    k : float
        System gain.

    Notes
    -----
    .. versionadded:: 0.16.0
    """
    sos = np.asarray(sos)
    n_sections = sos.shape[0]
    z = np.empty(n_sections*2, np.complex128)
    p = np.empty(n_sections*2, np.complex128)
    k = 1.
    for section in range(n_sections):
        b, a = sos[section, :3], sos[section, 3:]
        # remove leading zeros from numerator to avoid badcoefficient warning in scipy.signal.normaize
        while b[0] == 0:
            b = b[1:]
        # convert to transfer function
        zpk = sig.tf2zpk(b, a)
        z[2*section:2*(section+1)] = zpk[0]
        p[2*section:2*(section+1)] = zpk[1]
        k *= zpk[2]
    return z, p, k

# functions of general use
def freqs(sys, w):
    """
    This function computes the frequency response of a zpk system at an
    array of frequencies.

    It loosely mimicks 'scipy.signal.freqs'.

    Parameters
    ----------
    system: (zeros, poles, k)
        zeros and poles both in rad/s, k is the actual coefficient, not DC gain
    w: np.array
        frequencies in rad/s

    Returns
    -------
    np.array(..., dtype=complex) with the response
    """
    z, p, k = sys
    s = np.array(w, dtype=np.complex128) * 1j
    h = np.full(len(s), k, dtype=np.complex128)
    for i in range(max([len(z), len(p)])):
        # do multiplication and division alternatingly to avoid the unlikely
        # event of numerical overflow
        try:
            h *= s - z[i]
        except IndexError:
            pass
        try:
            h /= s - p[i]
        except IndexError:
            pass
    return h


def freqs_rp(r, p, c, w):
    """ same as freqs, but takes a list of residues and poles"""
    h = np.full(len(w), c, dtype=np.complex128)
    for i in range(len(p)):
        h += freqs(([], [p[i]], r[i]), w)
    return h


# this one is not tested, so probably not working satisfactorily
def freqz_(sys, w, dt=8e-9):
    """
    This function computes the frequency response of a zpk system at an
    array of frequencies.

    It loosely mimicks 'scipy.signal.frequresp'.

    Parameters
    ----------
    system: (zeros, poles, k)
        zeros and poles both in rad/s, k is the actual coefficient, not DC gain
    w: np.array
        frequencies in rad/s
    dt: sampling time

    Returns
    -------
    np.array(..., dtype=complex) with the response
    """
    z, p, k = sys
    b, a = sig.zpk2tf(z, p, k)
    _, h = sig.freqz(b, a, worN=w*dt)
    return h

def residues(z, p, k):
    """ this function uses the residue method (Heaviside Cover-up method)
        to perform the partial fraction expansion of a rational function
        defined by zeros, poles and a prefactor k. No intermediate
        conversion into a polynome is performed, which makes this function
        less prone to finite precision issues. In the current version,
        no pole value may occur twice and the number of poles must be
        strictly greater than the number of zeros.

        Returns
        -------
        np.array(dtype=np.complex128) containing the numerator array a of the
        expansion

            product_i( s - z[i] )                 a[j]
        k ------------------------- =  sum_j ( ---------- )
            product_j( s - p[j] )               s - p[j]
    """
    # first we should ensure that there are no double poles
    if len(np.unique(p)) < len(p):
        raise ValueError("residues() received a list of poles where some "
                         "values appear twice. This cannot be implemented "
                         "at the time being.")
    # next we split off a constant term if applicable
    if len(p) > len(z):  # strictly proper
        c = 0
    elif len(p) == len(z):  # proper
        c = k
    else:
        raise ValueError("Specified transfer function is not proper! ")
    # so the initial polynom H becomes
    # H = N/Q = k*Q/Q + P/Q, where degree(P) < degree(Q)
    # to find P from N, we have
    # H = N/Q = (k*Q+P)/Q, thus
    # P = N - k*Q
    # the kQ part will be zero at all pole locations, thus can be dropped here
    # without problems
    #
    # actually doing the math (or checking wikipedia) reveals a simple formula
    # for a[i] that is implemented here:
    # https://en.wikipedia.org/wiki/Partial_fraction_decomposition#Residue_method
    #
    # Say the original fraction can be written as P(s) / Q(s), where
    # P is the polynome of zeros, including the prefactor k, and Q the
    # polynome of poles. Then
    # a[i] = P(p[i])/Q'([p[i]). Furthermore, Q'(p[i]) is the value of the
    # polynome Q without the factor that contains p[i].
    a = np.full(len(p), k, dtype=np.complex128)
    for i in range(len(a)):
        for j in range(len(p)):
            # do multiplication and division alternatingly to avoid the unlikely
            # event of numerical overflow
            try:
                a[i] *= p[i] - z[j]
            except IndexError:
                pass
            if i != j:
                a[i] /= p[i] - p[j]
    return a, c


def cont2discrete(r, p, c, dt=8e-9):
    """
    Transforms residue and pole from continuous to discrete time

    Parameters
    ----------
    r: residues
    p: poles
    dt: sampling time

    Returns
    -------
    (r, p) with the transformation applied
    """
    r = np.asarray(r, dtype=np.complex128) * dt
    p = np.exp(np.asarray(p, dtype=np.complex128) * dt)
    return r, p, c


def discrete2cont(r, p, c, dt=8e-9):
    """
    Transforms residues and poles from discrete time to continuous

    Parameters
    ----------
    r: residues
    p: poles
    c: constant term to be carried along
    dt: sampling time (s)

    Returns
    -------
    r, p with the transformation applied
    """
    r = np.array(r, dtype=np.complex128) / dt
    p = np.log(np.array(p, dtype=np.complex128)) / dt
    return r, p, c


def bodeplot(data, xlog=True):
    """ plots a bode plot of the data x, y

    parameters
    -----------------
    data:    a list of tuples (f, tf[, label]) where f are frequencies and tf
             complex transfer data, and label the label for data
    xlog:    sets xaxis to logscale
    figure:
    """
    try:
        ax1 = plt.subplot(211)
    except:
        raise ExpectedPyrplError("No installation of matplotlib found. "
                                 "Please install matplotlib in order to use "
                                 "this feature.")
    if len(data[0]) == 3:  # unpack the labels from data
        newdata = []
        labels = []
        for (f, tf, label) in data:
            newdata.append((f, tf))
            labels.append(label)
        data = newdata
    for i, (f, tf) in enumerate(data):
        if len(labels) > i:
            label = labels[i]
        else:
            label = ""
        ax1.plot(f, np.log10(np.abs(tf)) * 20, label=label)
    if xlog:
        ax1.set_xscale('log')
    ax1.set_ylabel('Magnitude [dB]')
    ax2 = plt.subplot(212, sharex=ax1)
    for i, (f, tf) in enumerate(data):
        ax2.plot(f, np.angle(tf, deg=True))
    ax2.set_xlabel('Frequency [Hz]')
    ax2.set_ylabel('Phase [deg]')
    plt.tight_layout()
    if len(labels) > 0:
        leg = ax1.legend(loc='best', framealpha=0.5)
        leg.set_draggable(True)
    plt.show()


class IirFilter(object):
    """
    Computes coefficients and predicts transfer functions of an IIR filter.

    Parameters
    ----------
    sys: (zeros, poles, gain)
        zeros: list of complex zeros
        poles: list of complex poles
        gain:  DC-gain

        zeros/poles with nonzero imaginary part should come in complex
        conjugate pairs, otherwise the conjugate zero/pole will
        automatically be added. After this, the number of poles should
        exceed the number of zeros at least by one, otherwise a real pole
        near the Nyquist frequency will automatically be added until there
        are more poles than zeros.

    loops: int or None
        the number of FPGA cycles per filter sample. None tries to
        automatically find the value leading to the highest possible
        sampling frequency. If the numerical precision of the filter
        coefficients in the FPGA is the limiting, manually setting a higher
        value of loops may improve the filter performance.

    dt: float
        the FPGA clock frequency. Should be very close to 8e-9

    minoops: int
        minimum number of loops (constant of the FPGA design)

    maxloops: int
        maximum number of loops (constant of the FPGA design)

    tol: float
        tolerancee for matching conjugate pole/zero pairs. 1e-3 is okay.

    intermediatereturn: str or None
        if set to a valid option, the algorithm will stop at the specified
        step and return an intermediate result for debugging. Valid options are


    Returns
    -------
    coefficients

    coefficients is an array of float arrays of length six, which hold the
    filter coefficients to be passed directly to the iir module

    :py:attr:`IirFilter.loops` of the :py:class:`IirFilter` instance is
    automatically corrected to a number of loops compatible with the
    implemented design.
    """

    def __init__(self,
                 zeros,
                 poles,
                 gain,
                 loops=None,
                 dt=8e-9,
                 minloops=4,
                 maxloops=1023,
                 iirstages=16,
                 totalbits=32,
                 shiftbits=29,
                 tol=1e-3,
                 frequencies=None,
                 inputfilter=0,
                 moduledelay=5):
        self._sys = zeros, poles, gain
        self.loops = loops
        self.dt = dt
        self.minloops = minloops
        self.maxloops = maxloops
        self.iirstages = iirstages
        self.totalbits = totalbits
        self.shiftbits = shiftbits
        self.tol = tol
        if frequencies is not None:
            self._frequencies = np.asarray(frequencies, dtype=np.complex128)
        if inputfilter is None:
            self.inputfilter = 0
        else:
            self.inputfilter = inputfilter
        self.moduledelay = moduledelay
        _ = self.coefficients  # compute coefficients immediately

    @property
    def sys(self):
        return self._sys

    @sys.setter
    def sys(self, v):
        # it is easiest to just create a new object when the specification
        # has changed
        z, p, g = v
        self.__init__(z, p, g,
                      loops=self.loops,
                      dt=self.dt,
                      minloops=self.minloops,
                      maxloops=self.maxloops,
                      iirstages=self.iirstages,
                      totalbits=self.totalbits,
                      shiftbits=self.shiftbits,
                      tol=self.tol,
                      frequencies=self.frequencies,
                      inputfilter=self.inputfilter,
                      moduledelay=self.moduledelay)
        logger.warning("Setter of sys will soone be deprecated. Create a new "
                       "instance of 'IirFilter' instead! ")

    @property
    def coefficients(self):
        """
        Computes and returns the coefficients of the IIR filter set by :py:attr:`IirFilter.sys`.

        Parameters
        ----------
        sys: (zeros, poles, gain)
            zeros: list of complex zeros
            poles: list of complex poles
            gain:  DC-gain

            zeros/poles with nonzero imaginary part should come in complex
            conjugate pairs, otherwise the conjugate zero/pole will
            automatically be added. After this, the number of poles should
            exceed the number of zeros at least by one, otherwise a real pole
            near the nyquist frequency will automatically be added until there
            are more poles than zeros.

        loops: int or None
            the number of FPGA cycles per filter sample. None tries to
            automatically find the value leading to the highest possible
            sampling frequency. If the numerical precision of the filter
            coefficients in the FPGA is the limiting, manually setting a higher
            value of loops may improve the filter performance.

        dt: float
            the FPGA clock frequency. Should be very close to 8e-9

        minloops: int
            minimum number of loops (constant of the FPGA design)

        maxloops: int
            maximum number of loops (constant of the FPGA design)

        tol: float
            tolerancee for matching conjugate pole/zero pairs. 1e-3 is okay.

        intermediatereturn: str or None
            if set to a valid option, the algorithm will stop at the specified
            step and return an intermediate result for debugging. Valid options are


        Returns
        -------
        coefficients

        coefficients is an array of float arrays of length six, which hold the
        filter coefficients to be passed directly to the iir module

        :py:attr:`IirFilter.loops` of the :py:class:`IirFilter` instance is
        automatically corrected to a number of loops compatible with the
        implemented design.
        """
        if hasattr(self, '_coefficients'):
            return self._coefficients

        # clean the filter specification so we can work with it and find the
        # right number of loops
        zeros, poles, gain = self.proper_sys
        # this isnt really necessary as rescaled_sys will call proper_sys

        # get factor in front of ratio of zeros and poles
        # scale to angular frequencies
        z, p, k = self.rescaled_sys  # 'tf_continuous'

        # pre-account for frequency distortion of bilinear transformation
        # - this step is obsolete in the current algorithm
        # if prewarp:
        #    z, p = prewarp(z, p, dt=loops * dt)

        # perform the partial fraction expansion to get first order sections
        """
        r, c = residues(z, p, k)

        self.rp_continuous = r, p, c  # 'tf_partialfraction'

        # transform to discrete time
        rd, pd, cd = cont2discrete(r, p, c, dt=self.dt * self.loops)
        """
        zd = np.exp(np.asarray(z, dtype=np.complex128)*self.dt*self.loops)
        pd = np.exp(np.asarray(p, dtype=np.complex128)*self.dt*self.loops)
        rd, cd = residues(zd, pd, k)

        self.rp_discrete = rd, pd, cd  # 'tf_discrete'

        # convert (r, p) into biquad coefficients
        coefficients = self.rp2coefficients(rd, pd, cd, tol=self.tol)

        # rearrange second order sections for minimum delay
        coefficients = self.minimize_delay(coefficients) # 'tf_implemented_perfect'
        self._coefficients = coefficients
        _ = self.finiteprecision()  # 'tf_implemented'
        return coefficients

    @property
    def proper_sys(self):
        """
        Makes sure that a system is strictly proper and that all complex
        poles/zeros have conjugate parters.

        Parameters
        ----------
        zeros: list of zeros
        poles: list of poles
        loops: number of loops to implement. Can be None for autodetection.
        minloops: minimum number of loops that is acceptable
        maxloops: minimum number of loops that is acceptable
        iirstages: number of biquads available for implementation
        tol: tolerance for matching complex conjugate partners

        Returns
        -------
        (zeros, poles, minloops) - the corrected lists of poles/zeros and the
        number of loops that are minimally needed for implementation
        """
        if hasattr(self, '_proper_sys'):
            return self._proper_sys
        zeros, poles, gain = self.sys
        loops = self.loops
        minloops, maxloops, iirstages, tol = self.minloops, self.maxloops, \
                                             self.iirstages, self.tol
        # part 1: make sure each complex pole/zero has a conjugate partner
        results = []
        looplist = []  # count at the same time how many biquads are needed
        for data in [zeros, poles]:
            actloops = 0
            data = list(data)  # make a copy of the original data
            gooddata = []
            while data:
                datum = data.pop()
                gooddata.append(datum)
                if np.imag(datum) == 0:
                    # real pole/zero -> needs half a biquad
                    actloops += 0.5
                else:
                    actloops += 1
                    # find conjugate partner
                    found = False
                    for candidate in data:
                        if np.abs(np.conjugate(datum) - candidate) < tol:
                            # conjugate partner found - remove it from original
                            # list and add it to the
                            gooddata.append(data.pop(data.index(candidate)))
                            found = True
                            break
                    if not found:
                        logger.debug("Pole/zero %s had no complex conjugate "
                                     "partner. It was added automatically.",
                                     datum)
                        gooddata.append(np.conjugate(datum))
                        # attention to an issue here: Often
                        # datum != np.conjugate(np.conjugate(datum))
                        # therefore we should consider replacing the original pole
                        # by its double conjugate to have matched pairs (the
                        # error only appears in the first conjugation)
            # overwrite original data with the corrected one
            results.append(gooddata)
            looplist.append(actloops)
        zeros, poles = results[0], results[1]

        # get the number of loops after anticipated pole addition (see part 2)
        actloops = looplist[1]  # only need to reason w.r.t. poles
        if len(zeros) - len(poles) >= 0:
            # add half a biquad per excess zero
            actloops += (len(zeros) - len(poles) + 1) * 0.5
        # each pair of poles needs one biquad
        actloops = int(np.ceil(actloops))
        if actloops > iirstages:
            raise Exception("Error: desired filter order is too high to "
                            "be implemented.")
        if actloops < minloops:
            actloops = minloops
        # actloops now contains the necessary number of loops
        if loops is None:
            loops = actloops
        elif loops < actloops:
            logger.warning("Cannot implement filter with %s loops. "
                           "Minimum of %s is needed! ", loops, actloops)
            loops = actloops
        if loops > maxloops:
            logger.info("Maximum loops number is %s. This value "
                           "will be tried instead of specified value "
                           "%s.", maxloops, loops)
            loops = maxloops

        # part 2: make sure the transfer function is strictly proper
        # if we must add a pole, place it at the nyquist frequency
        extrapole = -125e6 / loops / 2
        while len(zeros) > len(poles):
            poles.append(extrapole)
            logger.debug("Specified IIR transfer function was not "
                         "proper. Automatically added a pole at %s Hz.",
                         extrapole)
            # if more poles must be added, make sure we have no 2 poles at the
            # same frequency
            extrapole /= 2
        self.loops = loops
        self._proper_sys = (zeros, poles, gain)
        return self._proper_sys

    @property
    def rescaled_sys(self):
        """ rescales poles and zeros with 2pi and returns the prefactor
        corresponding to dc-gain gain"""
        if hasattr(self, '_rescaled_sys'):
            return self._rescaled_sys
        zeros, poles, gain = self.proper_sys
        zeros = [zz * 2 * np.pi for zz in zeros]
        poles = [pp * 2 * np.pi for pp in poles]
        k = gain
        for pp in poles:
            if pp != 0:
                k *= np.abs(pp)
        for zz in zeros:
            if zz != 0:
                k /= np.abs(zz)
        self._rescaled_sys = zeros, poles, k
        return self._rescaled_sys

    def prewarp(self, z, p, dt=8e-9):
        """ prewarps frequencies in order to correct warping effect in discrete
        time conversion """

        def timedilatation(w):
            """ accounts for effective time dilatation due to warping effect """
            if np.imag(w) == 0:
                w = np.abs(w)
                # return 1.0  # do not prewarp real poles/zeros
            else:
                w = np.abs(np.imag(w))
            if w == 0:
                return 1.0
            else:
                correction = np.tan(w / 2 * dt) / w * 2.0 / dt
                if correction <= 0:
                    logger.warning("Negative correction factor %s obtained "
                                   "during prewarp for frequency %s. "
                                   "Setting correction factor to 1!",
                                   correction, w / 2 / np.pi)
                    return 1.0
                elif correction > 2.0:
                    logger.warning("Correction factor %s > 2 obtained"
                                   "during prewarp for frequency %s. "
                                   "Setting correction factor to 1 but this "
                                   "seems wrong!",
                                   correction, w / 2 / np.pi)
                    return 1.0
                else:
                    return correction

        # apply timedilatation() to all zeros and poles
        zc = list(z)  # make copies
        pc = list(p)
        for x in [zc, pc]:
            for i in range(len(x)):
                correction = timedilatation(x[i])
                logger.debug("Warp correction of %s at frequency %s "
                             "automatically applied.",
                             correction, x[i] / 2 / np.pi)
                x[i] *= correction
        return zc, pc

    def rp2coefficients(self, r, p, c, tol=0):
        """
        Pairs residues and corresponding poles into second order sections.

        Parameters
        ----------
        r: array with numerator coefficient
        p: array with poles
        tol: tolerance for combining complex conjugate pairs.

        Returns
        -------
        coefficients: array((N, 6), dtype=np.float64) where N is number of biquads
        """
        N = int(np.ceil(float(len(p)) / 2.0))  # needed biquads
        if c != 0:
            N += 1
        if N == 0:
            logger.warning(
                "Warning: No poles or zeros defined. Filter will be "
                "turned off!")
            coefficients = np.zeros((1, 6), dtype=np.float64)
            coefficients[0, 0] = 0
            coefficients[:, 3] = 1.0
            return coefficients

        # prepare coefficient array
        coefficients = np.zeros((N, 6), dtype=np.float64)
        coefficients[0, 0] = 0
        coefficients[:, 3] = 1.0

        #  make lists
        rc = list(r)
        pc = list(p)
        # separate poles and residues into ones with zero and with nonzero
        # imaginary part, only counting imaginary poles and residues once

        # we should really migrate this to scipy.signal._cplxreal
        complexp = []
        complexr = []
        realp = []
        realr = []
        while (len(pc) > 0):
            pp = pc.pop(0)
            rr = rc.pop(0)
            if np.imag(pp) == 0:
                realp.append(pp)
                realr.append(rr)
            else:
                # find closest-matching index
                diff = np.abs(np.asarray(pc) - np.conjugate(pp))
                index = np.argmin(diff)
                if diff[index] > tol:
                    logger.warning(
                        "Conjugate partner for pole %s deviates from "
                        "expected value by %s > %s",
                        pp, diff[index], tol)
                complexp.append((pp + np.conjugate(pc.pop(index))) / 2.0)
                complexr.append((rr + np.conjugate(rc.pop(index))) / 2.0)
        complexp = np.asarray(complexp, dtype=np.complex128)
        complexr = np.asarray(complexr, dtype=np.complex128)
        # 1)  filter coefficients come as an array of 6-vectors
        #     [b0, b1, 0.0, 1.0, a1, a2]
        #
        # 2)  each of the implemented biquad filters will output
        #     y[n] = b0*x[n] + b1*x[n-1] + a1*y[n-1] + b2*y[n-2]
        #     This can be rewritten
        #     1.0*y[n] - a1*y[n-1] - b2*y[n-2] = b0*x[n] + b1*x[n-1] + 0*x[n-2]
        #     this is equivalent to
        #
        #                          b0 + b1*z^-1
        #     Y(z)/X(z) =  ----------------------------
        #                     1.0 - a1*z^-1 - a2*z^-1
        #
        # 3) The design started in continuous time, where we have the partial
        #    fraction expansion as a starting point:
        #
        #                                 a[k]
        #     Y(s)/X(s) =  sum_(k=1)^N ----------
        #                               s - p[k]
        #
        #  4) Oppenheim+Schaefer 1975 p 203 states that 3) is transformed to
        #
        #                                     dt * a[k]
        #     Y(s)/X(s) =  sum_(k=1)^N ------------------------
        #                                1 - exp(p[k]*dt)*z^-1
        #
        #  5) The previous transformation (in cont2discrete has already done this:
        #        p -> exp(p*dt),   a -> a*dt, so we already have
        #
        #                                    a[k]
        #     Y(z)/X(z) =  sum_(k=1)^N ------------------
        #                                1 - p[k]*z^-1
        #
        #  6) Thus, we just have to merge two conjugate first-order sections into
        #     one second order section. As can be easily verified, we multiply a
        #     section from 5) by its complex conjugate and compare coefficients
        #     with the ones from 2)::
        #
        #     b0 = 2.0*real(a)
        #     b1 = -2.0 * real(a*conjugate(p))
        #     a1 = 2.0*real(p)
        #     a2 = -abs(p)**2
        # we must invert the denominator for comatibility with scipy
        # when the coefficients are written to the FPGA, the inversion is undone
        invert = -1.0
        coefficients[:len(complexp), 0] = 2.0 * np.real(complexr)
        coefficients[:len(complexp), 1] = \
            -2.0 * np.real(complexr * np.conjugate(complexp))
        coefficients[:len(complexp), 4] = 2.0 * np.real(complexp) * invert
        coefficients[:len(complexp), 5] = -1.0 * np.abs(complexp) ** 2 * invert
        # for a pair of real poles, residues (p1, p2) and (r1, r2), we find
        #     b0 = r1 + r2
        #     b1 = - r1*p2 - r2*p1
        #     a1 = p1 + p2
        #     a2 = -p1*p2
        # make number of poles even
        if len(realp) % 2 != 0:
            realp.append(0)
            realr.append(0)
        realp = np.asarray(np.real(realp), dtype=np.float64)
        realr = np.asarray(np.real(realr), dtype=np.float64)
        # realp = np.asarray((realp), dtype=np.float64)
        # realr = np.asarray((realr), dtype=np.float64)

        # implement coefficients - order is the one from specification of poles
        # The function minimize_delay will sort the sections such that the once
        # with highest frequency polez/zeros will be computed last, thereby
        # minimizing delay.
        for i in range(len(realp) // 2):
            p1, p2 = realp[2 * i], realp[2 * i + 1]
            r1, r2 = realr[2 * i], realr[2 * i + 1]
            coefficients[len(complexp)+i, 0] = r1 + r2
            coefficients[len(complexp)+i, 1] = -r1 * p2 - r2 * p1
            coefficients[len(complexp)+i, 4] = (p1 + p2) * invert
            coefficients[len(complexp)+i, 5] = (-p1 * p2) * invert
        # finish the design by adding a constant term if needed
        if c != 0:
            coefficients[-1, 0] = c
        return coefficients

    def minimize_delay(self, coefficients=None):
        """
        Minimizes the delay of coefficients by rearranging the biquads in an
        optimal way (highest frequency poles get minimum delay.

        Parameters
        ----------
        coefficients

        Returns
        -------
        new coefficients
        """
        if coefficients is None:
            coefficients = self.coefficients
        ranks = list()
        for c in list(coefficients):
            # empty sections (numerator is 0) are ranked 0
            if (c[0:3] == 0).all():
                ranks.append(0)
            else:

                z, p, k = sos2zpk([c])
                # compute something proportional to the frequency of the pole
                ppp = [np.abs(np.log(pp)) for pp in p if pp != 0]
                if not ppp:
                    f = 1e20  # no pole -> superfast
                else:
                    f = np.max(ppp)
                ranks.append(f)
        newcoefficients = [c for (rank, c) in
                           sorted(zip(ranks, list(coefficients)),
                                  key=lambda pair: -pair[0])]
        return np.array(newcoefficients)

    def finiteprecision(self, coeff=None, totalbits=None, shiftbits=None):
        if coeff is None:
            coeff = self.coefficients
        if totalbits is None:
            totalbits = self.totalbits
        if shiftbits is None:
            shiftbits = self.shiftbits
        res = coeff * 0 + coeff  # weird way to make a copy of coeff
        for x in np.nditer(res, op_flags=['readwrite']):
            xr = np.round(x * 2 ** shiftbits)
            xmax = 2 ** (totalbits - 1)
            if xr == 0 and xr != 0:
                logger.warning("One value was rounded off to zero: Increase "
                               "shiftbits in fpga design if this is a "
                               "problem!")
            elif xr > xmax - 1:
                xr = xmax - 1
                logger.warning("One value saturates positively: Increase "
                               "totalbits or decrease gain!")
            elif xr < -xmax:
                xr = -xmax
                logger.warning("One value saturates negatively: Increase "
                               "totalbits or decrease gain!")
            x[...] = 2 ** (-shiftbits) * xr
        return res

    @property
    def coefficients_rounded(self):
        if hasattr(self, '_fcoefficients'):
            return self._fcoefficients
        self._fcoefficients = self.finiteprecision()
        return self._fcoefficients

    def tf_inputfilter(self, inputfilter=None, frequencies=None):  # input
        # anti aliasing filter and additional delay model
        # delay comes from latency in fpga + on average half sampling time
        moduledelay = self.moduledelay + self.loops / 2.0
        if inputfilter is None:
            inputfilter = self.inputfilter
        if frequencies is None:
            frequencies = self.frequencies
        frequencies = np.asarray(frequencies, dtype=complex)
        try:
            len(inputfilter)
        except:
            inputfilter = [inputfilter]  # make it iterable
        tf = frequencies*0 + 1.0
        for f in inputfilter:
            if f > 0:  # lowpass
                tf /= (1.0 + 1j * frequencies / f)
                moduledelay += 1
            elif f < 0:  # highpass
                tf /= (1.0 + 1j * f / frequencies)
                moduledelay += 2
        # add delay
        delay = moduledelay * self.dt  # + extradelay
        tf *= np.exp(-1j*delay*frequencies*2*np.pi)
        return tf

    @property
    def designdata(self):
        return [(self.frequencies, self.tf_continuous(), 'continuous'),
                (self.frequencies, self.tf_partialfraction(),
                 'partialfraction'),
                (self.frequencies, self.tf_discrete(), 'discrete'),
                (self.frequencies, self.tf_coefficients(),
                    'coefficients'),
                (self.frequencies, self.tf_rounded(), 'rounded'),
                #(self.frequencies, self.tf_delay(), 'rounded+delay'),
                (self.frequencies, self.tf_final(),
                 'final')]

    def tf_continuous(self, frequencies=None):
        """
        Returns the continuous transfer function of sys at frequencies.

        Parameters
        ----------
        sys: tuple
            (zeros, poles, gain)
            zeros: list of complex zeros
            poles: list of complex poles
            gain: float

        frequencies: np.array
            frequencies to compute the transfer function for
        Returns
        -------
        np.array(..., dtype=complex)
        """
        if frequencies is None:
            frequencies = self.frequencies
        frequencies = np.asarray(frequencies, dtype=np.float64)
        h = freqs(self.rescaled_sys, frequencies * 2 * np.pi)
        return h * self.tf_inputfilter(frequencies=frequencies)

    def tf_partialfraction(self, frequencies=None):
        """
        Returns the transfer function just before the partial fraction
        expansion for frequencies.

        Parameters
        ----------
        sys: (poles, zeros, k)
        dt:  sampling time
        continuous: if True, returns the transfer function in continuous
                    time domain, if False converts to discrete one
        method: method for scipy.signal.cont2discrete
        alpha:  alpha for above method (see scipy documentation)

        Returns
        -------
        np.array(..., dtype=complex)
        """
        # this code is more or less a direct copy of get_coeff()
        if frequencies is None:
            frequencies = self.frequencies
        frequencies = np.asarray(frequencies, dtype=np.complex128)
        r, p, c = self.rp_continuous
        h = freqs_rp(r, p, c, frequencies*2*np.pi)
        return h * self.tf_inputfilter(frequencies=frequencies)

    def tf_discrete(self, rp_discrete=None, frequencies=None):
        """
        Returns the discrete transfer function realized by coefficients at
        frequencies.

        Parameters
        ----------
        rpz: np.array
            coefficients as returned from iir module (array of biquad
            coefficients)

        frequencies: np.array
            frequencies to compute the transfer function for

        dt: float
            discrete sampling time (seconds)

        delay_per_cycle: float
            the biquad at coefficients[i] experiences an extra
            delay of i*delay_per_cycle

        zoh: bool
            If true, zero-order hold implementation is assumed. Otherwise,
            the delay is expected to depend on the index of biquad.

        Returns
        -------
        np.array(..., dtype=complex)
        """
        if frequencies is None:
            frequencies = self.frequencies
        frequencies = np.asarray(frequencies, dtype=np.complex128)
        if rp_discrete is None:
            r, p, c = self.rp_discrete
        else:
            r, p, c = rp_discrete
        rc, pc, cc = discrete2cont(r, p, c, dt=self.dt * self.loops)
        h = freqs_rp(rc, pc, cc, frequencies * 2 * np.pi)
        return h * self.tf_inputfilter(frequencies=frequencies)

    def tf_coefficients(self, frequencies=None, coefficients=None,
                                delay=False):
        """
        computes implemented transfer function - assuming no delay and
        infinite precision (actually floating-point precision)
        Returns the discrete transfer function realized by coefficients at
        frequencies.

        Parameters
        ----------
        coefficients: np.array
            coefficients as returned from iir module

        frequencies: np.array
            frequencies to compute the transfer function for

        dt: float
            discrete sampling time (seconds)

        zoh: bool
            If true, zero-order hold implementation is assumed. Otherwise,
            the delay is expected to depend on the index of biquad.

        Returns
        -------
        np.array(..., dtype=complex)
        """
        if frequencies is None:
            frequencies = self.frequencies
        frequencies = np.asarray(frequencies, dtype=np.float64)
        if coefficients is None:
            fcoefficients = self.coefficients
        else:
            fcoefficients = coefficients
        # discrete frequency
        w = frequencies * 2 * np.pi * self.dt * self.loops
        # the higher stages have progressively more delay to the output
        if delay:
            delay_per_cycle = np.exp(-1j * self.dt * frequencies * 2 * np.pi)
        h = np.zeros(len(w), dtype=np.complex128)
        for i in range(len(fcoefficients)):
            sos = np.asarray(fcoefficients[i], dtype=np.float64)
            # later we can use sig.sosfreqz (very recent function, dont want
            #  to update scipy now)
            ww, hh = sig.freqz(sos[:3], sos[3:], worN=np.asarray(w,
                                                           dtype=np.float64))
            if delay:
                hh *= delay_per_cycle ** (i + 1)
            h += hh
        return h

    def tf_rounded(self, frequencies=None, delay=False):
        """
        Returns the discrete transfer function realized by coefficients at
        frequencies.

        Parameters
        ----------
        coefficients: np.array
            coefficients as returned from iir module

        frequencies: np.array
            frequencies to compute the transfer function for

        dt: float
            discrete sampling time (seconds)

        zoh: bool
            If true, zero-order hold implementation is assumed. Otherwise,
            the delay is expected to depend on the index of biquad.

        Returns
        -------
        np.array(..., dtype=complex)
        """
        return self.tf_coefficients(frequencies=frequencies,
                                    coefficients=self.coefficients_rounded,
                                    delay=delay)

    def tf_final(self, frequencies=None):
        """
        Returns the discrete transfer function realized by coefficients at
        frequencies.

        Parameters
        ----------
        coefficients: np.array
            coefficients as returned from iir module

        frequencies: np.array
            frequencies to compute the transfer function for

        dt: float
            discrete sampling time (seconds)

        zoh: bool
            If true, zero-order hold implementation is assumed. Otherwise,
            the delay is expected to depend on the index of biquad.

        Returns
        -------
        np.array(..., dtype=complex)
        """
        return self.tf_rounded(frequencies=frequencies, delay=True) * \
               self.tf_inputfilter(frequencies=frequencies)

    @property
    def sampling_rate(self):
        return 1.0/(self.dt * self.loops)

    @property
    def frequencies(self):
        if hasattr(self, '_frequencies') and self._frequencies is not None:
            return self._frequencies
        z, p, k = self.proper_sys
        pz = list(np.abs(z)) + list(np.abs(p))
        start = min([self.sampling_rate/1000.0] + pz)
        stop = max([self.sampling_rate] + pz)
        # 1000 points / decade
        points = int(np.ceil(np.log10(stop/start)*1000))
        self._frequencies = np.array(np.logspace(np.log10(start),
                                                 np.log10(stop),
                                                 points, endpoint=True),
                                     dtype=np.complex128)
        return self._frequencies


