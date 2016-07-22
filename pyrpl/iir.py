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
    frequencies = np.array(frequencies, dtype=np.complex)
    wc, hc = sig.freqresp(sys, w=frequencies * 2 * np.pi)
    return hc


def tf_before_partialfraction(sys, frequencies, dt=8e-9, continuous=False,
                              method="gbt", alpha=0.5):
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
        zc, pc, kc = sys
        zc = np.array(zc, dtype=np.complex128)
        pc = np.array(pc, dtype=np.complex128)
        kc = np.complex128(kc)
        bb, aa = sig.zpk2tf(zc, pc, kc)
        if continuous:
            w = np.array(frequencies, dtype=np.float) * 2 * np.pi  # * dt
            ww, h = sig.freqs(bb, aa, worN=w)
            return h
        b, a, dtt = sig.cont2discrete((bb, aa), dt, method=method, alpha=alpha)
        b = b[0]
        w = np.array(frequencies, dtype=np.float) * 2 * np.pi * dt
        ww, h = sig.freqz(b, a, worN=w)
        return h


def tf_discrete(coefficients, frequencies, dt=8e-9, delay_per_cycle=8e-9,
                zoh=True):
    """
    Returns the discrete transfer function realized by coefficients at
    frequencies.

    Parameters
    ----------
    coefficients: np.array
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
    # the higher stages have progressively more delay to the output
    delay_per_cycle_array = np.exp(-1j * delay_per_cycle * frequencies * 2 *
                                np.pi)
    # discrete frequency
    w = np.array(frequencies, dtype=np.float) * 2 * np.pi * dt
    b, a = sig.sos2tf(np.array([coefficients[0]]))
    ww, h = sig.freqz(b, a, worN=w)
    for i in range(1, len(coefficients)):
        b, a = sig.sos2tf(np.array([coefficients[i]]))
        ww, hh = sig.freqz(b, a, worN=w)
        if not zoh:
            h += hh * delay_per_cycle_array **i  # minimum delay implementation
        else:
            h += hh
    if zoh:  # zero order hold implementation: biquad-independent delay
        h *= np.exp(-1j * delay_per_cycle * frequencies * 2 * np.pi
                             * len(coefficients))
    return h


def tf_implemented(coefficients,
                   frequencies,
                   dt=8e-9,
                   totalbits=32,
                   shiftbits=16,
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
    fcoefficients = finiteprecision(coefficients,
                                    totalbits=totalbits,
                                    shiftbits=shiftbits)
    return tf_discrete(fcoefficients, frequencies, dt=dt, zoh=zoh)


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


def get_coeff(
        sys,
        dt=8e-9,
        tol=0,
        method="gbt",
        alpha=0.5,
        mindelay=True):
    """
    Allowed systems in zpk form (otherwise problems arise):
        - no complex poles or zeros without conjugate partner (otherwise the
          conjugate pole will be added)
        - no double complex poles or zeros
        - no more than two real poles or zero within the tolerance interval
          (impossible to implement with parallel SOS)
        - to guarantee proper functioning, real poles (especially at low
          frequency) shoud be spaced by a factor 2
        - no crazy scaling factors
        - scaling can be accomplished by choosing the loop number
          appropriately: if f is the max. frequency, then
          loops ~ 125 MHz / 10 / f  - the factor 10 is already the safety
          margin to have negligible phase lag due to loops
    """
    zc, pc, kc = sys
    if zc == [] and pc == []:
        logger.warning("Warning: No poles or zeros defined, only constant "
                       "multiplication!")
        coeff = np.zeros((1, 6), dtype=np.float64)
        coeff[0, 0] = kc
        coeff[:, 3] = 1.0
        return coeff
    # critical step: conversion through tf is main source of design error
    # better algorithm (analytical) or higher numerical precision would help
    # a lot here
    zc = np.array(zc, dtype=np.complex128)
    pc = np.array(pc, dtype=np.complex128)
    kc = np.complex128(kc)
    bb, aa = sig.zpk2tf(zc, pc, kc)
    logger.debug("Continuous polynome: %s %s", bb, aa)
    b, a, dtt = sig.cont2discrete((bb, aa), dt, method=method, alpha=alpha)
    b = b[0]
    logger.debug("Discrete polynome: %s %s", b, a)
    r, p, k = sig.residuez(b, a, tol=tol)
    coeff = rpk2psos(r, p, k, tol=tol)
    logger.debug("Coefficients: %s", coeff)
    if mindelay:
        # at last, minimize the delay of the filter by placing high frequency
        # poles at slots with minimum delay
        return minimize_delay(coeff)
    else:
        return coeff


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


def make_proper_tf(zeros, poles, loops=None, _minloops=3, tol=1e-3):
    """
    Makes sure that a systel is strictly proper and that all complex
    poles/zeros have conjugate parters.

    Parameters
    ----------
    zeros: list of zeros
    poles: list of poles
    loops: number of loops to implement. Can be None for autodetection.
    _minloops: minimum number of loops that is acceptable
    tol: tolerance for matching complex conjugate partners

    Returns
    -------
    (zeros, poles, minloops) - the corrected lists of poles/zeros and the
    number of loops that are minimally needed for implementation
    """
    # part 1: make sure each complex pole/zero has a conjugate partner
    results = []
    minlooplist = []  # count at the same time how many biquads are needed
    for data in [zeros, poles]:
        minloops = 0
        data = list(data)  # make a copy of the original data
        gooddata = []
        while data:
            datum = data.pop()
            gooddata.append(datum)
            if np.imag(datum) == 0:
                # real pole/zero -> needs half a biquad
                minloops += 0.5
            else:
                minloops += 1
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
        # overwrite original data with the corrected one
        results.append(gooddata)
        minlooplist.append(minloops)
    zeros, poles = results[0], results[1]

    # get the number of loops after anticipated pole addition (see part 2)
    minloops = minlooplist[1]  # only need to reason w.r.t. poles
    if len(zeros)-len(poles) >= 0:
        # add half a biquad per excess zero
        minloops += (len(zeros) - len(poles) + 1) * 0.5
    minloops = int(np.ceil(minloops))
    if minloops < _minloops: # absolute minimum for proper functioning
        minloops = _minloops
    if loops is None:
        loops = minloops
    elif minloops > loops:
        logger.warning("Cannot implement filter with %s loops. "
                       "Minimum of %s is needed! ", loops, minloops)
        loops = minloops

    # part 2: make sure the transfer function is strictly proper
    # if we must add a pole, place it at the nyquist frequency
    extrapole = -125e6 / loops
    added = 0
    while len(zeros) >= len(poles):
        poles.append(extrapole)
        logger.warning("Specified IIR transfer function was not "
                       "strictly proper. Automatically added a pole at %s Hz.",
                       -1*extrapole)
        added += 1
        # if more poles must be added, make sure we have no 2 poles at the
        # same frequency
        if added % 2 == 0:
            extrapole /= 2
    return zeros, poles, minloops


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


def prewarp(sys, dt=8e-9):
    """ prewarps frequencies in order to correct warping effect in discrete
    time conversion """
    def timedilatation(w):
        """ accounts for effective time dilatation due to warping effect """
        freq = w / 2.0 / np.pi
        if np.imag(freq) == 0:
            freq = np.abs(freq)
            return 1.0  # do not prewarm real poles/zeros
        else:
            freq = np.abs(np.imag(freq))
        if freq == 0:
            return 1.0
        else:
            correction = np.tan(np.pi * freq * dt) / freq / np.pi / dt
            if correction <= 0:
                logger.warning("Negative correction factor %s obtained "
                               "during prewarp for frequency %s. "
                               "Setting correction factor to 1!",
                               correction, freq)
                return 1.0
            elif correction > 2.0:
                logger.warning("Correction factor %s > 2 obtained"
                               "during prewarp for frequency %s. "
                               "Setting correction factor to 1 but this "
                               "seems wrong!",
                               correction, freq)
                return 1.0
            else:
                return correction
    # apply timedilatation() to all zeros and poles
    zeros, poles, k = sys
    zc = list(zeros)  # make copies
    pc = list(poles)
    for x in [zc, pc]:
        for i in range(len(x)):
            correction = timedilatation(x[i])
            logger.debug("Warp correction of %s at frequency %s "
                         "automatically applied.",
                         correction, x[i] / 2 / np.pi)
            x[i] *= correction
    return zc, pc, k