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
                logger.warning("Not enough conjugates found. Dont know what to do with complex parameter rrc")
                rrc = np.conjugate(rr)
            if ppc is None:
                logger.warning("Not enough conjugates found. Dont know what to do with complex parameter ppc")
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
                logger.warning("More than 2-fold occurence of real poles: %s", pp)
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


"""def tf2plot(b,a,dt=8e-9,n=512,maxf=None,minf=100):
    if not maxf is None:
        n = np.linspace(minf,maxf,n)*2*np.pi*dt
    w, h = sig.freqz(b, a,worN=n)
    plt.title('Digital filter frequency response')
    plt.plot(w/(2*np.pi*dt), 20*np.log10(np.abs(h)))
    plt.title('Digital filter frequency response')
    plt.ylabel('Amplitude Response [dB]')
    plt.xlabel('Frequency (Hz)')
    plt.xscale("log")
    plt.grid()
    plt.show()"""


def psos2plot(sos, sys=None, dt=8e-9, n=2**14, maxf=1e6, minf=1000, name="", plot=False):
    toreturn = []
    if not maxf is None:
        n = np.linspace(minf, maxf, n) * 2 * np.pi * dt
    b, a = sig.sos2tf(np.array([sos[0]]))
    w, h = sig.freqz(b, a, worN=n)
    for i in range(1, len(sos)):
        b, a = sig.sos2tf(np.array([sos[i]]))
        w, hh = sig.freqz(b, a, worN=n)
        h += hh
    w = w / (2 * np.pi * dt)
    toreturn.append((w, h, name))
    if plot:
        plt.title('Digital filter frequency response')
        plt.plot(w, 20 * np.log10(np.abs(h)), label=name)
    if not sys is None:
        wc, hc = sig.freqresp(sys, w=w * 2 * np.pi)
        wc = wc / (2 * np.pi)
        if plot:
            plt.plot(wc, 20 * np.log10(np.abs(hc)), label="continuous system")
        toreturn.append((wc, hc, "continuous system"))
    if plot:
        plt.title('Digital filter frequency response')
        plt.ylabel('Amplitude Response [dB]')
        plt.xlabel('Frequency [Hz]')
        plt.xscale("log")
        plt.grid(True)
        # plt.legend()
        plt.show()
    return toreturn


def finiteprecision(coeff, totalbits=32, shiftbits=16):
    res = coeff * 0 + coeff
    for x in np.nditer(res, op_flags=['readwrite']):
        xr = np.round(x * 2**shiftbits)
        xmax = 2**(totalbits - 1)
        if xr == 0 and xr != 0:
            logger.warning("One value was rounded off to zero: Increase shiftbits!")
        elif xr > xmax - 1:
            xr = xmax - 1
            logger.warning("One value saturates positively: Increase totalbits!")
        elif xr < -xmax:
            xr = -xmax
            logger.warning("One value saturates negatively: Increase totalbits!")
        x[...] = 2**(-shiftbits) * xr
    return res


def get_coeff_old(
        sys,
        dt=8e-9,
        totalbits=64,
        shiftbits=32,
        tol=0,
        finiteprecision=False):
    zc, pc, kc = sys
    if zc == [] and pc == []:
        logger.warning("No poles or zeros defined, only constant multiplication!")
        coeff = np.zeros((1, 6), dtype=np.float64)
        coeff[0, 0] = kc
        coeff[:, 3] = 1.0
        return coeff
    bb, aa = sig.zpk2tf(zc, pc, kc)
    b, a, dtt = sig.cont2discrete((bb, aa), dt)
    b = b[0]
    r, p, k = sig.residuez(b, a, tol=tol)
    coeff = rpk2psos(r, p, k, tol=tol)
    logger.debug("Coefficients: %s", coeff)
    if finiteprecision:
        fcoeff = finiteprecision(
            coeff,
            totalbits=totalbits,
            shiftbits=shiftbits)
        logger.debug("Rounded coefficients: %s", fcoeff)
        return fcoeff
    else:
        return coeff


def get_coeff(
        sys,
        dt=8e-9,
        totalbits=64,
        shiftbits=32,
        tol=0,
        finiteprecision=False):
    """
    Allowed systems in zpk form (otherwise problems arise):
        - no complex poles or zeros without conjugate partner (otherwise the conjugate pole will be added)
        - no double complex poles or zeros
        - no more than two real poles or zero within the tolerance interval (impossible to implement with parallel SOS)
        - to guarantee proper functioning, real poles (especially at low frequency) shoud be spaced by a factor 2
        - no crazy scaling factors
        - scaling can be accomplished by choosing the loop number appropriately: if f is the max. frequency, then
          loops ~ 125 MHz / 10 / f  - the factor 10 is already the safety margin to have negligible phase lag due to loops
    """
    zc, pc, kc = sys
    if zc == [] and pc == []:
        logger.warning("Warning: No poles or zeros defined, only constant multiplication!")
        coeff = np.zeros((1, 6), dtype=np.float64)
        coeff[0, 0] = kc
        coeff[:, 3] = 1.0
        return coeff
    bb, aa = sig.zpk2tf(zc, pc, kc)
    logger.debug("Continuous polynome: %s %s", bb, aa)
    b, a, dtt = sig.cont2discrete((bb, aa), dt)
    b = b[0]
    logger.debug("Discrete polynome: %s %s", b, a)
    r, p, k = sig.residuez(b, a, tol=tol)
    coeff = rpk2psos(r, p, k, tol=tol)
    logger.debug("Coefficients: %s", coeff)
    if finiteprecision:
        fcoeff = finiteprecision(
            coeff,
            totalbits=totalbits,
            shiftbits=shiftbits)
        logger.debug("Rounded coefficients: %s", fcoeff)
        return fcoeff
    else:
        return coeff

"""
def get_coeff_continuous(sys,dt=8e-9,totalbits=64,shiftbits=32,tol=0):
    zc,pc,kc = sys
    bb,aa = sig.zpk2tf(zc,pc,kc)
    rr,pp,kk = sig.residue(bb,aa,tol=tol)
    coeffc = rpk2psos(rr,pp,kk,tol=tol)
    coeff = list()
    for c in list(coeffc):
        print "Section coefficients (continuous):",c
        b,a,dtt  = sig.cont2discrete((c[0:3],c[3:6]),dt)
        b = b[0]
        print "Discrete a,b:", b,a
        cd=np.zeros(6,dtype=np.complex128)
        for i in range(6):
            if i<3 and i<len(b):
                cd[i] = b[i]
            elif i>=3 and i-3<len(a):
                cd[i] = a[i-3]
            else:
                cd[i] = 0
        print "Section coefficients (discrete):",cd
        coeff.append(cd)
    coeff = np.array(coeff)
    fcoeff = coeff#finiteprecision(coeff,totalbits=totalbits,shiftbits=shiftbits)
    print "Coefficients: ",coeff
    return fcoeff,coeff
"""


def bodeplot(data, xlog=False):
    """ plots a bode plot of the data x, y
    
    parameters
    -----------------
    data:    a list of tuples (f, tf[, label]) where f are frequencies and tf complex transfer data
    xlog:    sets xaxis to logscale
    figure:
    """
    ax1 = plt.subplot(211);
    if len(data[0]) == 3: #unpack the labels from data
        newdata = []
        labels = []
        for (f, tf, label) in data:
            newdata.append((f,tf))
            labels.append(label)
        data = newdata
    for i,(f,tf) in enumerate(data):
        if len(labels)>i:
            label = labels[i]
        else:
            label=""
        ax1.plot(f*1e-3, np.log10(np.abs(tf))*20, label=label)
    if xlog:
        ax1.set_xscale('log');
    ax1.set_ylabel('Magnitude [dB]');
    ax2 = plt.subplot(212, sharex=ax1);
    for i,(f,tf) in enumerate(data):
        ax2.plot(f*1e-3, np.angle(tf, deg=True));
    ax2.set_xlabel('Frequency [kHz]');
    ax2.set_ylabel('Phase [deg]');
    plt.tight_layout()
    if len(labels)>0:
        ax1.legend(loc='best')
    plt.show()

# Example
def example():
    plt.close()
    pc = 2.0 * np.pi * np.array([(-0.5 - 13428.513784154658j),
                                 (-0.5 + 13428.513784154658j),
                                 (-10000 + 0j),
                                 (-11e4 + 0j)],
                                dtype=np.complex128)
    zc = 2.0 * np.pi * np.array([0], dtype=np.complex128)
    kc = -124184264.61183095 * 1e12
    sys = (zc, pc, kc)
    shift = 40
    total = 60
    f, c = get_coeff(sys, dt=8e-9, totalbits=total, shiftbits=shift)
    f10, c10 = get_coeff(sys, dt=200e-9, totalbits=total, shiftbits=shift)
    psos2plot(c, sys, n=2**16, maxf=50e6, dt=8e-9, name="unrounded 8ns")
    psos2plot(f10, None, n=2**16, maxf=50e6, dt=200e-9, name="rounded 200ns")
    l = plt.legend()

"""Example from ipython notebook
bp.poles=[(-12.0000000999999-19631.489456573287j),(-1000-100631j),(-10-500631j),-50000,(-500-22631j),-1e6]
bp.zeros = [(-100.000000-60000.108400821522j),(-10.000000-200000.108400821522j),(-500-21031j)]
bp.k=1000000*50000*6*1e6
#b.zeros=[100000]
#b.zeros.remove(0)
print bp.poles
print bp.zeros
bp.refresh()
plt.close()
loops = 30
dt=8e-9*loops
(zc,pc,kc) = bp.zpk
sys=(zc,pc,kc*1e5)
print sys
shift=25
total=46
f,c=get_coeff(sys,dt=loops*8e-9,totalbits=total,shiftbits=shift,tol=1e-6,finiteprecision=False)
#f10,c10 = get_coeff(sys,dt=200e-9,totalbits=total,shiftbits=shift,tol=1e-6)
psos2plot(c,sys,n=2**16,maxf=50e6,dt=loops*8e-9,name="unrounded dt="+str(int(dt*1e9))+"ns")
psos2plot(f,None,n=2**16,maxf=50e6,dt=loops*8e-9,name="rounded dt="+str(int(dt*1e9))+"ns")
l=plt.legend()
#p.iir_coefficients = c
p.reset=True
p.iir_coefficients = c
p.iir_loops = loops
p.reset=False
print max((p.iir_coefficients[0:len(c)] - c).flatten())
"""
