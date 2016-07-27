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


def rpk2psos(r, p, k, tol=0):
    """ transforms a residue-pole-k structure into parallel second order
    sections to be passed to iir filter as coefficients """
    logger.debug("r/p/k:")
    logger.debug("%s %s %s", r, p, k)
    r = list(r)
    p = list(p)
    if len(k) > 1:
        logger.warning("k too long. Ignoring rest of the list")
    linp = list()
    linr = list()
    quadsections = list()
    while len(p) > 0:
        pp = p.pop(0)
        rr = r.pop(0)
        logger.debug("r/p = %s / %s", rr, pp)
        if np.imag(pp) == 0.0:
            linp.append(pp)
            linr.append(rr)
        else:
            rrc = None
            ppc = None
            for i in range(0, len(p)):
                if np.abs(np.conjugate(pp) - p[i]) <= tol:
                    logger.debug("found and removed conjugate for p = %s", pp)
                    ppc = p.pop(i)
                    break
            for i in range(0, len(r)):
                if np.abs(np.conjugate(rr) - r[i]) <= tol:
                    logger.debug("found and removed conjugate for r = %s", rr)
                    rrc = r.pop(i)
                    break
            # quadsections.append([rr,pp])
            if rrc is None:
                logger.warning("Not enough conjugates found. Dont know what "
                               "to do with complex parameter rrc")
                rrc = np.conjugate(rr)
            if ppc is None:
                logger.warning("Not enough conjugates found. Dont know what "
                               "to do with complex parameter ppc")
                ppc = np.conjugate(pp)
            b, a = sig.invresz([rr, rrc], [pp, ppc], [])
            b = list(np.real(b))
            a = list(np.real(a))
            while len(b) < 3:
                b.append(0)
            if len(b) > 3:
                logger.warning("Quadsection too long. b=%s", b)
                b = b[:3]
            while len(a) < 3:
                a.append(0)
            if len(a) > 3:
                logger.warning("Warning: Quadsection too long. a=%s", a)
                a = a[:3]
            quadsections.append(np.array(b + a))

    logger.debug("Quadsections: %s", quadsections)
    logger.debug("linr: %s", linr)
    logger.debug("linp: %s", linp)
    if len(linr) == 0:
        result = quadsections
    else:
        pp = list()
        rr = list()
        linsections = list()
        uniq, mult = sig.unique_roots(linp, tol=tol, rtype='avg')
        for p in uniq[mult > 1]:
            pp = list()
            rr = list()
            for i in range(len(linp)):
                if np.abs(linp[i] - p) < tol:
                    pp.append(linp[i])
                    rr.append(linr[i])
            for ppp in pp:
                linp.remove(ppp)
            for rrr in rr:
                linr.remove(rrr)
            if len(pp) > 3:
                logger.warning("More than 2-fold occurence of real poles: %s",
                               pp)
            b, a = sig.invresz(rr, pp, [])
            linsections.append(np.array(sig.tf2sos(b, a)[0]))  # if there were
        # now all multiple occurences of poles should have disappeared from
        # linp
        logger.debug("Unique residues and poles: %s %s", linr, linp)
        while len(linr) > 2:
            # first extract double poles
            rr = [linr.pop(0), linr.pop(0)]
            pp = [linp.pop(0), linp.pop(0)]
            b, a = sig.invresz(rr, pp, [])
            linsections.append(np.array(sig.tf2sos(b, a)[0]))
        # last one will try to incorporate residual polynome
        if len(linp) > 0:
            b, a = sig.invresz(linr, linp, k)
            linsections.append(np.array(sig.tf2sos(b, a)[0]))
        elif len(k) > 0:
            b, a = sig.invresz(rr, pp, k)
            linsections[-1] = np.array(sig.tf2sos(b, a)[0])
        linsections = np.array(linsections)
        logger.debug("Linsections: %s", linsections)
        if len(quadsections) == 0:
            result = linsections
        else:
            result = np.concatenate((quadsections, linsections))
    return np.array(result)


def tf_inputfilter(frequencies, inputfilter):  # input filter modelisation
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


def freqz(sys, w, dt=8e-9):
    """
    This function computes the frequency response of a discrete time zpk
    system at an array of frequencies.

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
    s = np.array(w, dtype=np.complex128) * 1j
    h = np.full(len(s), k, dtype=np.complex128)
    for i in range(max([len(z), len(p)])):
        # do multiplication and division alternatingly to avoid the unlikely
        # event of numerical overflow
        try:
            h *= s - np.log(z[i])/dt
        except IndexError:
            pass
        try:
            h /= s - np.log(p[i])/dt
        except IndexError:
            pass
    return h

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


def tf_continuous(sys, frequencies):
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
    sys = get_coefficients(sys, intermediatereturn='continuous')
    frequencies = np.asarray(frequencies, dtype=np.complex)
    return freqs(sys, frequencies * 2 * np.pi)


def tf_partialfraction(sys, frequencies):
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
    r, p, loops = get_coefficients(sys,
                           intermediatereturn='partialfraction')
    h = np.zeros(len(frequencies), dtype=np.complex128)
    for i in range(len(p)):
        h += freqs(([], [p[i]], r[i]), 2*np.pi*frequencies)
    return h


def tf_discrete(sys, frequencies, dt=8e-9, delay_per_cycle=8e-9,
                     zoh=True):
    """
    Returns the discrete transfer function realized by coefficients at
    frequencies.

    Parameters
    ----------
    rpz: np.array
        coefficients as returned from iir module (array of biquad coefficients)

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
    r, p = sys
    w = np.array(frequencies, dtype=np.complex128) * 2 * np.pi
    h = np.zeros(len(w), dtype=np.complex128)
    for i in range(len(p)):
        hh = freqz(([], [p[i]], r[i]), w, dt=dt)
        h += hh
    return h

def tf_discrete_(sys, frequencies, dt=8e-9, delay_per_cycle=8e-9,
                               zoh=True):
    r, p = sys
    w = np.array(frequencies, dtype=np.complex128) * 2 * np.pi
    h = np.zeros(len(w), dtype=np.complex128)
    for i in range(len(p)):
        hh = freqz(([], [p[i]], r[i]), w, dt=dt)
        h += hh
    return h


def tf_discrete_fast(coefficients, frequencies, dt=8e-9):
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


def tf_implemented(coefficients,
                   frequencies,
                   dt=8e-9,
                   delay_per_cycle=8e-9,
                   totalbits=320,
                   shiftbits=280,
                   zoh=False):
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
    if totalbits is None:
        fcoefficients = coefficients
    else:
        fcoefficients = finiteprecision(coefficients,
                                        totalbits=totalbits,
                                        shiftbits=shiftbits)

    # the higher stages have progressively more delay to the output
    delay_per_cycle_array = np.exp(-1j * delay_per_cycle * frequencies * 2 *
                                np.pi)
    # discrete frequency
    w = np.array(frequencies, dtype=np.float) * 2 * np.pi * dt
    b, a = sig.sos2tf(np.array([fcoefficients[0]]))
    ww, h = sig.freqz(b, a, worN=w)
    for i in range(1, len(coefficients)):
        b, a = sig.sos2tf(np.array([fcoefficients[i]]))
        ww, hh = sig.freqz(b, a, worN=w)
        if not zoh:
            h += hh * delay_per_cycle_array **i  # minimum delay implementation
        else:
            h += hh
    if zoh:  # zero order hold implementation: biquad-independent delay
        h *= np.exp(-1j * delay_per_cycle * frequencies * 2 * np.pi
                             * len(fcoefficients))
    return h


def finiteprecision(coeff, totalbits=32, shiftbits=16):
    res = coeff * 0 + coeff
    for x in np.nditer(res, op_flags=['readwrite']):
        xr = np.round(x * 2**shiftbits)
        xmax = 2**(totalbits - 1)
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
        x[...] = 2**(-shiftbits) * xr
    return res


def get_coefficients(
        sys,
        loops=None,
        dt=8e-9,
        minloops=4,
        maxloops=255,
        iirstages=16,
        tol=1e-3,
        prewarp=False,
        intermediatereturn=None):
    """

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
    zeros, poles, gain = sys

    # clean the filter specification so we can work with it and find the
    # right number of loops
    zeros, poles, loops = make_proper_tf(zeros,
                                         poles,
                                         loops=loops,
                                         minloops=minloops,
                                         maxloops=maxloops,
                                         iirstages=iirstages,
                                         tol=tol)

    # get factor in front of ratio of zeros and poles
    # scale to angular frequencies
    z, p, k = rescale(zeros, poles, gain)

    if intermediatereturn == 'continuous':
        return z, p, k

    # pre-account for frequency distortion of bilinear transformation
    if prewarp:
        z, p = prewarp(z, p, dt=loops*dt)

    # perform the partial fraction expansion to get first order sections
    r = residues(z, p, k)

    if intermediatereturn == 'partialfraction':
        return r, p, loops

    # transform to discrete time
    r, p = cont2discrete(r, p, dt=dt*loops)

    if intermediatereturn == 'discrete':
        return r, p, loops

    # convert (r, p) into biquad coefficients
    coefficients = rp2sos(r, p)

    # rearrange second order sections for minimum delay
    coefficients = minimize_delay(coefficients)

    return coefficients, loops


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
    r = np.asarray(r, dtype=np.complex128)
    p = np.exp(np.asarray(p, dtype=np.complex128) * dt)
    return r, p


def rp2sos(r, p, tol=0):
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
        logger.warning("Warning: No poles or zeros defined. Filter will be "
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
    while(len(pc) > 0):
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
                logger.warning("Conjugate partner for pole %s deviates from "
                               "expected value by %s > %s",
                               pp, diff[index], tol)
            complexp.append((pp + np.conjugate(pc.pop(index))) / 2.0)
            complexr.append((rr + np.conjugate(rc.pop(index))) / 2.0)
    complexp = np.asarray(complexp, dtype=np.complex128)
    complexr = np.asarray(complexr, dtype=np.complex128)
    realp = np.asarray(realp, dtype=np.complex128)
    realr = np.asarray(realr, dtype=np.complex128)
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
    coefficients[:len(complexp), 0] = 2.0*np.real(complexr)
    coefficients[:len(complexp), 1] = -2.0 * np.real(
        complexr * np.conjugate(complexp))
    coefficients[:len(complexp), 4] = 2.0 * np.real(complexp)
    coefficients[:len(complexp), 5] = -1.0*np.abs(complexp)**2
    # for a pair of real poles, residues (p1, p2) and (r1, r2), we find
    #     b0 = r1 + r2
    #     b1 = - r1*p2 - r2*p1
    #     a1 = p1 + p2
    #     a2 = -p1*p2
    # make number of poles even
    if len(realp) % 2 != 0:
        realp.append(0)
        realr.append(0)
    # implement coefficients
    for i in range(len(realp)//2):
        p1, p2 = realp[2*i], realp[2*i+1]
        r1, r2 = realr[2 * i], realr[2*i+1]
        coefficients[len(complexp):, 0] = r1+r2
        coefficients[len(complexp):, 1] = -r1*p2 -r2*p1
        coefficients[len(complexp):, 4] = p1+p2
        coefficients[len(complexp):, 5] = -p1*p2
    # that finishes the design
    return coefficients


def minimize_delay(coefficients):
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
    newcoefficients = [c for (rank,c) in sorted(zip(ranks, list(coefficients)),
                                                 key=lambda pair: -pair[0])]
    return np.array(newcoefficients)


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
        ax1.plot(f*1e-3, np.log10(np.abs(tf))*20, label=label)
    if xlog:
        ax1.set_xscale('log')
    ax1.set_ylabel('Magnitude [dB]')
    ax2 = plt.subplot(212, sharex=ax1)
    for i, (f, tf) in enumerate(data):
        ax2.plot(f*1e-3, np.angle(tf, deg=True))
    ax2.set_xlabel('Frequency [kHz]')
    ax2.set_ylabel('Phase [deg]')
    plt.tight_layout()
    if len(labels) > 0:
        leg = ax1.legend(loc='best', framealpha=0.5)
        leg.draggable(state=True)
    plt.show()


def make_proper_tf(zeros, poles, loops=None,
                   minloops=4, maxloops=255, iirstages=16, tol=1e-3):
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
                    if np.abs(np.conjugate(datum)-candidate)<tol:
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
    if len(zeros)-len(poles) >= 0:
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


def rescale(zeros, poles, gain):
    """ rescales poles and zeros with 2pi and returns the prefactor
    corresponding to dc-gain gain"""
    zeros = [zz * 2 * np.pi for zz in zeros]
    poles = [pp * 2 * np.pi for pp in poles]
    k = gain
    for pp in poles:
        if pp != 0:
            k *= np.abs(pp)
    for zz in zeros:
        if zz != 0:
            k /= np.abs(zz)
    return zeros, poles, k


def prewarp(z, p, dt=8e-9):
    """ prewarps frequencies in order to correct warping effect in discrete
    time conversion """
    def timedilatation(w):
        """ accounts for effective time dilatation due to warping effect """
        if np.imag(w) == 0:
            w = np.abs(w)
            #return 1.0  # do not prewarp real poles/zeros
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
