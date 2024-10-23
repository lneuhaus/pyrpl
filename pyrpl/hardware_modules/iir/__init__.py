"""
Sometimes it is interesting to realize even more complicated filters.
This is the case, for example, when a piezo resonance limits the maximum
gain of a feedback loop. For these situations, the IIR module can
implement filters with 'Infinite Impulse Response'
(https://en.wikipedia.org/wiki/Infinite_impulse_response). It is the
your task to choose the filter to be implemented by specifying the
complex values of the poles and zeros of the filter. In the current
version of pyrpl, the IIR module can implement IIR filters with the
following properties:

- strictly proper transfer function (number of poles > number of zeros)
- poles (zeros) either real or complex-conjugate pairs
- no three or more identical real poles (zeros)
- no two or more identical pairs of complex conjugate poles (zeros)
- pole and zero frequencies should be larger than :math:`\frac{f_\rm{nyquist}}{1000}` (but you can optimize the nyquist frequency of your filter by tuning the 'loops' parameter)
- the DC-gain of the filter must be 1.0. Despite the FPGA implemention being more flexible, we found this constraint rather practical. If you need different behavior, pass the IIR signal through a PID module and use its input filter and proportional gain. If you still need different behaviour, the file iir.py is a good starting point.
- total filter order <= 16 (realizable with 8 parallel biquads)
- a remaining bug limits the dynamic range to about 30 dB before internal saturation interferes with filter performance

Filters whose poles have a positive real part are unstable by design.
Zeros with positive real part lead to non-minimum phase lag.
Nevertheless, the IIR module will let you implement these filters.

In general the IIR module is still fragile in the sense that you should
verify the correct implementation of each filter you design. Usually you
can trust the simulated transfer function. It is nevertheless a good
idea to use the internal network analyzer module to actually measure the
IIR transfer function with an amplitude comparable to the signal you
expect to go through the filter, as to verify that no saturation of
internal filter signals limits its performance.

.. code:: python

    #reload to make sure settings are default ones
    from pyrpl import Pyrpl
    p = Pyrpl(hostname="192.168.1.100")

    #shortcut
    iir = p.rp.iir

    #print docstring of the setup function
    print(iir.setup.__doc__)

.. code:: python

    #prepare plot parameters
    %matplotlib inline
    import matplotlib
    matplotlib.rcParams['figure.figsize'] = (10, 6)

    #setup a complicated transfer function
    zeros = [ 4e4j+300, +2e5j+1000, +2e6j+3000]
    poles = [ 1e6, +5e4j+300, 1e5j+3000, 1e6j+30000]
    iir.setup(zeros=zeros, poles=poles, loops=None, plot=True)
    print("Filter sampling frequency: ", 125./iir.loops,"MHz")

If you try changing a few coefficients, you will see that your design
filter is not always properly realized. The bottleneck here is the
conversion from the analytical expression (poles and zeros) to the
filter coefficients, not the FPGA performance. This conversion is (among
other things) limited by floating point precision. We hope to provide a
more robust algorithm in future versions. If you can obtain filter
coefficients by another, preferrably analytical method, this might lead
to better results than our generic algorithm.

Let's check if the filter is really working as it is supposed:

.. code:: python

    # first thing to check if the filter is not ok
    print("IIR overflows before:", bool(iir.overflow))
    na = p.networkanalyzer

    # measure tf of iir filter
    iir.input = na.iq
    na.setup(iq_name='iq1', start=1e4, stop=3e6, points = 301, rbw=100, avg=1,
             amplitude=0.1, input='iir', output_direct='off', logscale=True)
    tf = na.curve()

    # first thing to check if the filter is not ok
    print("IIR overflows after:", bool(iir.overflow))

    # retrieve designed transfer function
    designdata = iir.transfer_function(na.frequencies)


    #plot with design data
    %matplotlib inline
    import matplotlib
    matplotlib.rcParams['figure.figsize'] = (10, 6)
    from pyrpl.hardware_modules.iir.iir_theory import bodeplot
    bodeplot([(na.frequencies, designdata, "designed system"),
    (na.frequencies, tf, "measured system")], xlog=True)

As you can see, the filter has trouble to realize large dynamic ranges.
With the current standard design software, it takes some 'practice' to
design transfer functions which are properly implemented by the code.
While most zeros are properly realized by the filter, you see that the
first two poles suffer from some kind of saturation. We are working on
an automatic rescaling of the coefficients to allow for optimum dynamic
range. From the overflow register printed above the plot, you can also
see that the network analyzer scan caused an internal overflow in the
filter. All these are signs that different parameters should be tried.

A straightforward way to impove filter performance is to adjust the
DC-gain and compensate it later with the gain of a subsequent PID
module. See for yourself what the parameter g=0.1 (instead of the
default value g=1.0) does here:

.. code:: python

    #rescale the filter by 20 fold reduction of DC gain
    iir.setup(zeros=zeros, poles=poles, g=0.1, loops=None, plot=False)

    # first thing to check if the filter is not ok
    print("IIR overflows before:", bool(iir.overflow))

    # measure tf of iir filter
    iir.input = na.iq
    tf = na.curve()

    # first thing to check if the filter is not ok
    print("IIR overflows after:", bool(iir.overflow))

    # retrieve designed transfer function
    designdata = iir.transfer_function(na.frequencies)


    #plot with design data
    %matplotlib inline
    import matplotlib
    matplotlib.rcParams['figure.figsize'] = (10, 6)
    from pyrpl.hardware_modules.iir.iir_theory import bodeplot
    bodeplot([(na.frequencies, designdata, "designed system"),
    (na.frequencies, tf, "measured system")], xlog=True)


You see that we have improved the second peak (and avoided internal
overflows) at the cost of increased noise in other regions. Of course
this noise can be reduced by increasing the NA averaging time. But maybe
it will be detrimental to your application? After all, IIR filter design
is far from trivial, but this tutorial should have given you enough
information to get started and maybe to improve the way we have
implemented the filter in pyrpl (e.g. by implementing automated filter
coefficient scaling).

If you plan to play more with the filter, these are the remaining
internal iir registers:

.. code:: python

    iir = p.rp.iir

    # useful diagnostic functions
    print("IIR on:", iir.on)
    print("IIR bypassed:", iir.shortcut)
    print("IIR copydata:", iir.copydata)
    print("IIR loops:", iir.loops)
    print("IIR overflows:", bin(iir.overflow))
    print("Coefficients (6 per biquad):")
    print(iir.coefficients)

    # set the unity transfer function to the filter
    iir._setup_unity()
"""
from .iir import IIR