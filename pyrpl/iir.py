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
import matplotlib.pyplot as plt
import numpy as np
import logging
logger = logging.getLogger(name=__name__)

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
    np.array(..., dtype=np.complex) with the response
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
    np.array(..., dtype=np.complex) with the response
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
        strictly greated than the number of zeros.

        Returns
        -------
        np.array(dtype=np.complex128) containing the numerator array a of the
        expansion

            product_i( s - z[i] )               a[i]
        k ------------------------- =  sum ( ---------- )
            product_j( s - p[j] )             s - p[j]
    """
    # first we should ensure that there are no double poles
    if len(np.unique(p)) < len(p):
        raise ValueError("Residues received a list of poles where some "
                         "values appear twice. This cannot be implemented "
                         "at the time being.")
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
    return a


def cont2discrete(r, p, dt=8e-9):
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
    return r, p


def discrete2cont(r, p, dt=8e-9):
    """
    Transforms residues and poles from discrete time to continuous

    Parameters
    ----------
    r: residues
    p: poles
    dt: sampling time (s)

    Returns
    -------
    r, p with the transformation applied
    """
    r = np.array(r, dtype=np.complex128) / dt
    p = np.log(np.array(p, dtype=np.complex128)) / dt
    return r, p


def bodeplot(data, xlog=False):
    """ plots a bode plot of the data x, y

    parameters
    -----------------
    data:    a list of tuples (f, tf[, label]) where f are frequencies and tf
             complex transfer data, and label the label for data
    xlog:    sets xaxis to logscale
    figure:
    """
    ax1 = plt.subplot(211)
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
        ax1.plot(f * 1e-3, np.log10(np.abs(tf)) * 20, label=label)
    if xlog:
        ax1.set_xscale('log')
    ax1.set_ylabel('Magnitude [dB]')
    ax2 = plt.subplot(212, sharex=ax1)
    for i, (f, tf) in enumerate(data):
        ax2.plot(f * 1e-3, np.angle(tf, deg=True))
    ax2.set_xlabel('Frequency [kHz]')
    ax2.set_ylabel('Phase [deg]')
    plt.tight_layout()
    if len(labels) > 0:
        leg = ax1.legend(loc='best', framealpha=0.5)
        leg.draggable(state=True)
    plt.show()


class IirFilter(object):
    def __init__(self,
                 zeros,
                 poles,
                 gain,
                 loops=None,
                 dt=8e-9,
                 minloops=4,
                 maxloops=255,
                 iirstages=16,
                 tol=1e-3):
        self.sys = zeros, poles, gain
        self.loops = loops
        self.dt = dt
        self.minloops = minloops
        self.maxloops = maxloops
        self.iirstages = iirstages
        self.tol = tol

    @property
    def coefficients(self):
        """
        Returns the coefficients of the IIR filter

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
        coefficients, loops

        coefficients is an array of float arrays of length six, which hold the
        filter coefficients to be passed directly to the iir module

        loops is the number of loops for the implemented design.
        """
        if hasattr(self, '_coefficients'):
            return self._coefficients

        # clean the filter specification so we can work with it and find the
        # right number of loops
        zeros, poles, self.loops = self.proper_sys

        # get factor in front of ratio of zeros and poles
        # scale to angular frequencies
        z, p, k = self.rescaled_sys

        # pre-account for frequency distortion of bilinear transformation
        #if prewarp:
        #    z, p = prewarp(z, p, dt=loops * dt)

        # perform the partial fraction expansion to get first order sections
        r = residues(z, p, k)

        self.rp_continuous = r, p

        # transform to discrete time
        rd, pd = cont2discrete(r, p, dt=self.dt * self.loops)
        self.rp_discrete = rd, pd

        # convert (r, p) into biquad coefficients
        coefficients = self.rp2coefficients(rd, pd, tol=self.tol)

        # rearrange second order sections for minimum delay
        coefficients = self.minimize_delay(coefficients)
        self._coefficients = coefficients
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
        zeros, poles, loops = self.zeros, self.poles, self.loops
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
            logger.warning("Maximum loops number is %s. This value "
                           "will be tried instead of specified value "
                           "%s.", maxloops, loops)
            loops = maxloops

        # part 2: make sure the transfer function is strictly proper
        # if we must add a pole, place it at the nyquist frequency
        extrapole = -125e6 / loops
        while len(zeros) >= len(poles):
            poles.append(extrapole)
            logger.warning("Specified IIR transfer function was not "
                           "strictly proper. Automatically added a pole at %s Hz.",
                           extrapole)
            # if more poles must be added, make sure we have no 2 poles at the
            # same frequency
            extrapole /= 2
        return zeros, poles, loops

    @property
    def rescaled_sys(self):
        """ rescales poles and zeros with 2pi and returns the prefactor
        corresponding to dc-gain gain"""
        if hasattr(self, '_rescaled_sys'):
            return self._rescaled_sys
        zeros, poles, gain = self.sys
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

    def rp2coefficients(self, r, p, tol=0):
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
        coefficients[:len(complexp), 1] = -2.0 * np.real(
            complexr * np.conjugate(complexp))
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
        realp = np.asarray(realp, dtype=np.complex128)
        realr = np.asarray(realr, dtype=np.complex128)
        # implement coefficients
        for i in range(len(realp) // 2):
            p1, p2 = realp[2 * i], realp[2 * i + 1]
            r1, r2 = realr[2 * i], realr[2 * i + 1]
            coefficients[len(complexp):, 0] = np.real(r1 + r2)
            coefficients[len(complexp):, 1] = np.real(-r1 * p2 - r2 * p1)
            coefficients[len(complexp):, 4] = np.real(p1 + p2) * invert
            coefficients[len(complexp):, 5] = np.real(-p1 * p2) * invert
        # that finishes the design
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
        newcoefficients = list()
        ranks = list()
        for c in list(coefficients):
            # empty sections (numerator is 0) are ranked 0
            if (c[0:3] == 0).all():
                ranks.append(0)
            else:
                z, p, k = sig.sos2zpk([c])
                # compute something proportional to the frequency of the pole
                f = np.max([np.abs(np.log(pp)) for pp in p if pp != 0])
                ranks.append(f)
        newcoefficients = [c for (rank, c) in
                           sorted(zip(ranks, list(coefficients)),
                                  key=lambda pair: -pair[0])]
        return np.array(newcoefficients)

    def finiteprecision(self, coeff=None, totalbits=None, shiftbits=None):
        if coeff is None:
            coeff = self.coefficients
        if totalbits is None:
            totalbis = self.totalbits
        if shiftbits is None:
            shiftbits = self.shiftbits
        res = coeff * 0 + coeff
        for x in np.nditer(res, op_flags=['readwrite']):
            xr = np.round(x * 2 ** shiftbits)
            xmax = 2 ** (totalbits - 1)
            if xr == 0 and xr != 0:
                logger.warning("One value was rounded off to zero: Increase "
                               "shiftbits!")
            elif xr > xmax - 1:
                xr = xmax - 1
                logger.warning("One value saturates positively: Increase "
                               "totalbits!")
            elif xr < -xmax:
                xr = -xmax
                logger.warning("One value saturates negatively: Increase "
                               "totalbits!")
            x[...] = 2 ** (-shiftbits) * xr
        return res

    @property
    def coefficients_rounded(self):
        if hasattr(self, '_fcoefficients'):
            return self._fcoefficients
        self._fcoefficients = self.finiteprecision()
        return self._fcoefficients

    def tf_inputfilter(self, frequencies, inputfilter):  # input filte model
        frequencies = np.array(frequencies, dtype=np.complex)
        try:
            len(inputfilter)
        except:
            inputfilter = [inputfilter]  # make it iterable
        tf = frequencies*0 + 1.0
        for f in inputfilter:
            if f > 0:  # lowpass
                tf /= (1.0 + 1j * frequencies / f)
            elif f < 0:  # highpass
                tf /= (1.0 + 1j * f / frequencies)
        return tf

    def tf_continuous(self, frequencies):
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
        np.array(..., dtype=np.complex)
        """
        frequencies = np.asarray(frequencies, dtype=np.complex)
        return freqs(self.rescaled_sys, frequencies * 2 * np.pi)

    def tf_partialfraction(self, frequencies):
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
        np.array(..., dtype=np.complex)
        """
        # this code is more or less a direct copy of get_coeff()
        # frequencies = np.array(frequencies, dtype=np.complex)
        r, p = self.rp_continuous
        h = np.zeros(len(frequencies), dtype=np.complex128)
        for i in range(len(p)):
            h += freqs(([], [p[i]], r[i]), 2*np.pi*frequencies)
        return h

    def tf_discrete(self, frequencies):
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
        np.array(..., dtype=np.complex)
        """
        r, p = self.rp_discrete
        w = np.array(frequencies, dtype=np.complex128) * 2 * np.pi
        h = np.zeros(len(w), dtype=np.complex128)
        for i in range(len(p)):
            hh = freqz(([], [p[i]], r[i]), w, dt=self.dt * self.loops)
            h += hh
        return h

    # not used at the moment
    #def tf_discrete_(self,
    #                 sys, frequencies, dt=8e-9, delay_per_cycle=8e-9,
    #                               zoh=True):
    #    r, p = sys
    #    w = np.array(frequencies, dtype=np.complex128) * 2 * np.pi
    #    h = np.zeros(len(w), dtype=np.complex128)
    #    for i in range(len(p)):
    #        hh = freqz(([], [p[i]], r[i]), w, dt=dt)
    #        h += hh
    #    return h

    # neiher used
    def tf_discrete_fast(self, coefficients, frequencies, dt=8e-9):
        """
        Returns the discrete transfer function realized by coefficients at
        frequencies. For optimisation purpuses only (faster computation),
        as not delay is taken into account.

        Parameters
        ----------
        coefficients: np.array
            coefficients as returned from iir module (array of biquad coefficients)

        frequencies: np.array
            frequencies to compute the transfer function for

        dt: float
            discrete sampling time (seconds)

        Returns
        -------
        np.array(..., dtype=np.complex)
        """
        # discrete frequency
        w = np.array(frequencies, dtype=np.float) * 2 * np.pi * dt
        b, a = sig.sos2tf(np.array([coefficients[0]]))
        ww, h = sig.freqz(b, a, worN=w)
        for i in range(1, len(coefficients)):
            b, a = sig.sos2tf(np.array([coefficients[i]]))
            ww, hh = sig.freqz(b, a, worN=w)
            h += hh
        return h

    def tf_implemented(self, frequencies):
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
        np.array(..., dtype=np.complex)
        """
        if self.totalbits is None:
            fcoefficients = self.coefficients
        else:
            fcoefficients = self.coefficients_rounded
        # the higher stages have progressively more delay to the output
        delay_per_cycle_array = np.exp(-1j * self.dt * frequencies * 2 * np.pi)
        # discrete frequency
        w = np.array(frequencies, dtype=np.float) * 2 * np.pi * self.dt
        b, a = sig.sos2tf(np.asarray([fcoefficients[0]]))
        ww, h = sig.freqz(b, a, worN=w)
        for i in range(1, len(fcoefficients)):
            b, a = sig.sos2tf(np.asarray([fcoefficients[i]]))
            ww, hh = sig.freqz(b, a, worN=w)
            if not zoh:
                h += hh * delay_per_cycle_array**i  # minimum delay implementation
            else:
                h += hh
        if zoh:  # zero order hold implementation: biquad-independent delay
            h *= np.exp(-1j * self.dt * frequencies * 2 * np.pi * len(
                fcoefficients))
        return h


    def tf_implemented_perfect(self, frequencies):
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
        np.array(..., dtype=np.complex)
        """
        fcoefficients = self.coefficients
        # the higher stages have progressively more delay to the output
        # discrete frequency
        w = np.array(frequencies, dtype=np.float) * 2 * np.pi * self.dt
        b, a = sig.sos2tf(np.asarray([fcoefficients[0]]))
        ww, h = sig.freqz(b, a, worN=w)
        for i in range(1, len(fcoefficients)):
            b, a = sig.sos2tf(np.asarray([fcoefficients[i]]))
            ww, hh = sig.freqz(b, a, worN=w)
            h += hh
        return h
