How a spectrum is computed in PyRPL
**********************************************************

Inspiration comes from Oppenheim & Schaefer 1975 and from
`Agilent <http://cp.literature.agilent.com/litweb/pdf/5952-0292.pdf>`__

The spectrum analyzer in Pyrpl estimates the spectrum of internal or
external signals by performing Fast-Fourier Transforms of traces
recorded by the scope. Since in the current version of Pyrpl, the stream
of data from the scope is made of discontiguous segments of 2^14
samples, we are currently using the
`Bartlett <https://en.wikipedia.org/wiki/Bartlett%27s_method>`__ method,
which consists in the following steps:

1. Each segment is multiplied by a symmetric window function of the same
   size.
2. The DFT of individual segments is performed. The segment is padded 
   before the FFT by a number of 0s to provide more points in the estimated 
   spectrum than in the original time segment.
3. The square modulus of the resulting periodograms are averaged to give
   the estimate of the spectrum, with the same size as the initial
   time-segments.

A variant of this method is the
`Welch <https://en.wikipedia.org/wiki/Welch%27s_method>`__ method, in
which the segments are allowed to be overlapping with each other. The
advantage is that when a narrow windowing function (ie a large number of
"points-per-bandwidth" in the frequency domain) is used, the points far
from the center of the time-segments have basically no weight in the
result. With overlapping segments, it is basically possible to move the
meaningful part of the window over all the available data. This is the
basic principle of real-time spectrum analyzers. This cannot be
implemented "as is" since the longest adjacent time-traces at our
disposal is 2^14 sample long.

However, a possible improvement, which would not require any changes of
the underlying FPGA code would be to apply the welch method with
subsegments smaller than the initial scope traces: for instance we would
extract 2^13 points subsegments, and we could shift the subsegment by up
to 2^13 points. With such a method, even with an infinitely narrow
windowing function, we would only "loose" half of the acquired data.
This could be immediately implemented with the Welch method implemented
in
`scipy <https://docs.scipy.org/doc/scipy-0.14.0/reference/generated/scipy.signal.welch.html>`__.

In the following, we discuss the normalization of windowing functions,
and then, the basic principle of operation of the two modes "iq" and
"baseband".



Definitions
-----------

+----------------------------------------+----------------------------------------------------+
|name                                    |          definition                                |
+========================================+====================================================+
|  Original time series                  | x[k], 0<=k<N                                       |
+----------------------------------------+----------------------------------------------------+ 
| Fourier Transform                      | X[r] = sum_k x[k] exp(-2 i pi r k/N)               |
+----------------------------------------+----------------------------------------------------+
|Inverse Fourier Transform (equivalently)|x[k] = 1/N sum_r X[r] exp(2 i pi k r/N)             |
+----------------------------------------+----------------------------------------------------+
|Time window                             |          w[k]                                      |
+----------------------------------------+----------------------------------------------------+
|Fourier transformed time window         |          W[r]                                      |
+----------------------------------------+----------------------------------------------------+
|Singly averaged spectrum (in V_pk)      | Y[r]=sum_k x[k] w[k] exp(-2 i pi r k/N)            |
+----------------------------------------+----------------------------------------------------+
|Singly averaged spectrum (in Vrms^2/Hz) | Z(r) = \|Y(r)\|^2/ (2 rbw)                         |
+----------------------------------------+----------------------------------------------------+

We can show that the Fourier transform of the product is the convolution of the Fourier 
Transforms, such that:

Y[r] = 1/N sum_r' X[r'] W[r-r']     (1)


To make sure the windowing function is well normalized, and to define 
the noise equivalent bandwidth of a given windowing function, 
we will study the 2 limiting cases where the initial time series is either 
a sinusoid or a gaussian distributed white noise.

Sinusoidal input
----------------

To simplify the calculations, we assume the period of the sinusoid is a multiple 
of the sampling rate:

x[k] = cos[2 pi m k/N]

= 1/2 (exp[i 2 pi m k/N] + exp[-2 pi i (N - m) k/N])

We obtain the Fourier transform:

X[r] = N/2 (delta[r-m] + delta[r-(N-m)]).

We deduce using (1), that the estimated spectrum is:

Y[r] = 1/2 (W[r - m] + W[r - (N-m)])

With the discrete fourier transform convention used here, we need to pay attention that 
the DC-component is for r=0, and the “negative frequencies” are actually located in the second 
half of the interval [N/2, N]. If we take the single sided convention where the negative frequency 
side is simply ignored, the correct normalization in terms of V_pk (for which the maximum of the 
spectrum corresponds to the amplitude of the sinusoid) is the one for where max(W[r]) = 2.

Moreover, a reasonable windowing function will only have non-zero Fourier components on the few bins 
around DC, such that if we measure a pure sinusoid with a frequency far from 0, there wont be any significant 
overlap between the two terms, and we will measure 2 distinct peaks in the positive and negative 
frequency regions, each of them with the shape of the Fourier transform of the windowing function. 
Since the maximum of W[r] is located in r=0, we finally have:

sum_k w[k] = 2


White noise input
-----------------

Once the normalization of the filter window has been imposed by the previous condition, 
we need to define the bandwidth of the window such that noise measurements integrated 
over frequency give the right variances.

Let's take a white noise of variance 1. 

<x[k] x[k']> = delta(k-k').

We would like the total spectrum in units of Vrms^2/Hz, integrated from 0 to Nyquist frequency 
to yield the same variance of 1. This is ensured by the Equivalent noise bandwidth of the filter window. 
To convert from V_pk^2 to V_rms^2/Hz, the spectrum is divided by the residual bandwidth of the filter window.

Let's calculate:

sum_r <|Y[r]|^2> = (...) = N sum_k w[k]^2 <|x[k]|^2>

If we remind that x[k] is a white noise following <|x[k]|^2> = 1, we get:

sum_r <|Y[r]|^2> = N sum_k w[k]^2

So, since we want:

sum_r <|Z[r]|^2> df = 2, (indeed, we want to work with single-sided spectra, such that integrating over positive frequencies is enough)

with df the frequency step in the FFT, we need to choose:

rbw = N sum_k w[k]^2 df /4

In order to use dimensionless parameters for the filter windows, we can introduce the equivalent noise bandwidth:

ENBW = sum_k w[k]^2/(sum_k w[k])^2 = 1/4 sum_k w[k]^2

Finally, we get the expression of the rbw:

rbw = sample_rate ENBW

IQ mode
-------

In iq mode, the signal to measure is fed inside an iq module, and thus,
multiplied by two sinusoids in quadrature with each other, and at the
frequency ``center_freq``. The resulting I and Q signals are then
filtered by 4 first order filters in series with each other, with cutoff
frequencies given by ``span``. Finally, these signals are measured
simultaneously with the 2 channels of the scope, and we form the complex
time serie c\_n = I\_n + i Q\_n. The procedure described above is
applied to extract the periodogram from the complex time-serie.

Since the data are complex, there are as many independent values in the
FFT than in the initial data (in other words, negative frequencies are
not redundant with positive frequency). In fact, the result is an
estimation of the spectrum in the interval [center\_freq - span/2,
center\_freq + span/2].

Baseband
--------

In baseband mode, the signal to measure is directly fed to the scope and
the procedure described above is applied directly. There are 2
consequences of the fact that the data are real:

1. The negative frequency components are complex conjugated (and thus
   redundant) wrt the positive ones. We thus throw away the negative
   frequencies, and only get a measurement on the interval [0, span/2]
2. The second scope channel can be used to measure another signal.

It is very interesting to measure simultaneously 2 signals, because we
can look for correlations between them. In the frequency domains, these
correlations are most easily represented by the cross-spectrum. We
estimate the cross-spectrum by performing the product
``conjugate(fft1)*fft2``, where ``fft1`` and ``fft2`` are the DFTs of
the individual scope channels before taking their modulus square.

Hence, in baseband mode, the method ``curve()`` returns a 4x2^13 array
with the following content: - spectrum1 - spectrum2 - real part of cross
spectrum - imaginary part of cross spectrum

Proposal for a cleaner interface for spectrum analyzer:
-------------------------------------------------------

To avoid baseband/2-channels acquisition from becoming a big mess, I
suggest the following:

-  The return type of the method ``curve`` should depend as little as
   possible from the particular settings of the instrument
   (``channel2_baseband_active``, ``display_units``). That was the idea
   with scope, and I think that makes things much cleaner.
   Unfortunately, for ``baseband``, making 2 parallel piplines such as
   ``curve_iq``, ``curve_baseband`` is not so trivial, because
   ``curve()`` is already part of the ``AcquisitionModule``. So I think
   we will have to live with the fact that ``curve()`` returns 2
   different kinds of data in ``baseband`` and ``iq-mode``.
-  Moreover, in baseband, we clearly want both individual spectra +
   cross-spectrum to be calculated from the beginning, since once the
   ``abs()`` of the ``ffts`` is taken, it is already too late to compute
   ``conjugate(fft1)*fft2``
-  Finally, I suggest to return all spectra with only one "internal
   unit" which would be ``V_pk^2``: indeed, contrary to rms-values
   unittesting doesn't require any conversion with peak values,
   moreover, averaging is straightforward with a quadratic unit,
   finally, ``.../Hz`` requires a conversion-factor involving the
   bandwidth for unittesting with coherent signals

I suggest the following return values for ``curve()``:

-  In normal (iq-mode): ``curve()`` returns a real valued 1D-array with
   the normal spectrum in ``V_pk^2``

-  In baseband: ``curve()`` returns a 4xN/2-real valued array with
   ``(spectrum1, spectrum2, cross_spectrum_real, cross_spectrum_imag)``.
   Otherwise, manipulating a complex array for the 2 real spectra is
   painful and inefficient.

Leo: Seems okay to me. One can always add functions like spectrum1() or
cross\_spectrum\_complex() which will take at most two lines. Same for
the units, I won't insist on rms, its just a matter of multiplying
sqrt(1/2). However, I suggest that we then have 3-4 buttons in the gui
to select which spectra and cross-spectra are displayed.

Yes, I am actually working on the gui right now: There will be a
baseband-area, where one can choose ``display_input1_baseband``,
``input1_baseband``, ``display_input2_baseband``, ``input2_baseband``,
``display_cross_spectrum``, 'display\_cross\_spectrum\_phase'. And a
"iq-area" where one can choose ``center_frequency`` and ``input``. I
guess this is no problem if we have the 3 distinct attributes ``input``,
``input1_baseband`` and ``input2_baseband``, it makes thing more
symmetric...

IQ mode with proper anti-aliasing filter
----------------------------------------

When the IQ mode is used, a part of the broadband spectrum of the two
quadratures is to be sampled at a significantly reduced sampling rate in
order to increase the number of points in the spectrum, and thereby
resolution bandwidth. Aliasing occurs if significant signals above the
scope sampling rate are thereby under-sampled by the scope, and results
in ghost peaks in the spectrum. The ordinary way to get rid of this
effect is to use excessive digital low-pass filtering with cutoff
frequencies slightly below the scope sampling rate, such that any peaks
outside the band of interest will be rounded off to zero. The following
code implements the design of such a low-pass filter (we choose an
elliptical filter for maximum steepness):

::

    import numpy as np
    from scipy import signal
    import matplotlib.pyplot as plt

    # the overall decimation value
    decimation = 8

    # elliptical filter runs at ell_factor times the decimated scope sampling rate
    ell_factor = 4

    wp = 0.8/ell_factor # passband ends at xx% of nyquist frequency
    ws = 1.0/ell_factor # stopband starts at yy% of nyquist frequency
    gpass = 5. # jitter in passband (dB)
    gstop = 20.*np.log10(2**14)  # attenuation in stopband (dB)
    #gstop = 60  #60 dB attenuation would only require a 6th order filter
    N, Wn = signal.ellipord(wp=wp, ws=ws, gpass=gpass, gstop=gstop, analog=False)  # get filter order
    z, p, k = signal.ellip(N, gpass, gstop, Wn, 'low', False, output='zpk')  # get coefficients for implementation
    b, a = signal.ellip(N, gpass, gstop, Wn, 'low', False, output='ba')  # get coefficients for plotting
    w, h = signal.freqz(b, a, worN=2**16)
    ww = np.pi / 62.5  # scale factor for frequency axis (original frequency axis goes up to 2 pi)

    # extent w to see what happens at higher frequencies
    w = np.linspace(0, np.pi, decimation/ell_factor*2**16, endpoint=False)
    # fold the response of the elliptical filter
    hext = []
    for i in range(decimation/ell_factor):
        if i%2 ==0:
            hext += list(h)
        else:
            hext += reversed(list(h))
    h = np.array(hext)
    # elliptical filter
    h_abs = 20 * np.log10(abs(h))

    # 4th order lowpass filter after IQ block with cutoff of decimated scope sampling rate
    cutoff = np.pi/decimation
    butter = 1.0/(1.+1j*w/cutoff)**4
    butter_abs = 20 * np.log10(abs(butter))

    # moving average decimation filter
    M = float(decimation) # moving average filter length
    mavg = np.sin(w*float(M)/2.0)/(sin(w/2.0)*float(M))
    mavg_abs = 20 * np.log10(abs(mavg))

    # plot everything together and individual parts
    h_tot = h_abs + mavg_abs + butter_abs
    plt.plot(w/ww, h_tot, label="all")
    plt.plot(w/ww, h_abs, label="elliptic filter")
    plt.plot(w/ww, butter_abs, label="butterworth filter")
    plt.plot(w/ww, mavg_abs, label="moving average filter")


    plt.title('Elliptical lowpass filter of order %d, decimation %d, ell_factor %d'%(N, decimation, ell_factor))
    plt.xlabel('Frequency (MHz)')
    plt.ylabel('Amplitude (dB)')
    plt.grid(which='both', axis='both')
    plt.fill([ws/ww*np.pi/decimation*ell_factor, max(w/ww), max(w/ww), ws*np.pi/ww/decimation*ell_factor], [max(h_abs), max(h_abs), -gstop, -gstop], '0.9', lw=0) # stop
    plt.fill([wp/ww*np.pi/decimation*ell_factor, min(w/ww), min(w/ww), wp*np.pi/ww/decimation*ell_factor], [min(h_abs), min(h_abs), -gpass, -gpass], '0.9', lw=0) # stop
    plt.axis([min(w/ww), max(w/ww), min(h_abs)-5, max(h_abs)+5])
    plt.legend()
    plt.show()
    plt.savefig('c://lneuhaus//github//pyrpl//doc//specan_filter.png',DPI=300)

    print "Final biquad coefficients [b0, b1, b2, a0, a1, a2]:"
    for biquad in signal.zpk2sos(z, p, k):
        print biquad

.. figure:: https://github.com/lneuhaus/pyrpl/blob/master/doc/specan_filter.png
   :alt: Resulting filter

   Resulting filter

We see that a filter of 8th order, consisting of 4 sequential biquads is
required. Since we do not require the span / sampling rate of the
spectrum analyzer to be above roughly 5 MHz, we may implement the four
biquads sequentially. Furthermore, for even lower values of the span,
the filter can be fed with a reduced clock rate equal to the scope
decimation factor divided by the variable 'decimation' in the filter
design code above (4 in the example). For the aliasing of the lowpass
filter passband not to cause problems in this case, we must in addition
use the 4th order butterworth lowpass already available from the IQ
module and the moving average filter of the scope. Then, as the plot
shows, we can be sure that no aliasing occurs, given that no aliasing
from the ADCs is present (should be guaranteed by analog Red Pitaya
design).

The problem with our scheme is the complexity of introducing 2 (for the
two quadratures) 4-fold biquads. This will not fit into the current
design and must therefore be postponed to after the FPGA cleanup.

We could however opt for another temporary option, applicable only to
stationary signals: Measure the spectrum twice or thrice with slightly
shifted IQ demodulation frequency (at +- 10% of span and the actual
center, as required above), and only plot the pointwise-minimum (with
respect to the final frequency axis) of the obtained traces. This is
simple and should be very effective (also to reduce the central peak at
the demodulation freuqency), so i suggest we give it a try. Furthermore,
it prepares the user that IQ spectra will only have 80% of the points in
baseband mode, which will remain so after the implementation of the
lowpass filter. The plot above shows that we do not have to worry about
aliasing from multiple spans away if the bandwidth if the IQ module is
se to the scope sampling rate (or slightly below). I am not aware that
this method is used anywhere else, but do not see any serious problem
with it.
