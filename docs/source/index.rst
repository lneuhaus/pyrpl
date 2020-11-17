.. pyrpl documentation master file, created by
   sphinx-quickstart on Fri Jul 08 23:10:33 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

*******************
What is PyRPL?
*******************


.. admonition:: PyRPL is an open-source software package providing many instruments on cheap FPGA hardware boards, e.g.:

   * oscilloscopes,
   * network analyzers,
   * lock-in amplifiers,
   * multiple automatic feedback controllers,
   * digital filters of very high order (24),
   * and much more.


.. admonition:: PyRPL currently runs exclusively on the Red Pitaya.

   The Red Pitaya (a.k.a. STEM Lab) (http://www.redpitaya.com, `see full documentation <http://redpitaya.readthedocs.io/en/latest/>`_) is an affordable (ca. 260 Euros) FPGA board with fast (125 MHz) analog inputs and outputs.


.. admonition:: PyRPL comes with a graphical user interface (GUI).

   See our :doc:`GUI manual <gui>` or the `video tutorial on youtube <https://www.youtube.com/watch?v=WnFkz1adhgs>`_.


.. admonition:: PyRPL has a convenient Python API.

   See :ref:`high_level_example` or :ref:`low_level_example`, and the :doc:`full API documentation <api>` .


.. admonition:: PyRPL `binary executables <https://sourceforge.net/projects/pyrpl/files>`__ for `Windows, <https://sourceforge.net/projects/pyrpl/files/pyrpl-windows.exe>`__ `Linux, <https://sourceforge.net/projects/pyrpl/files/pyrpl-linux>`__ or `Mac OS X <https://sourceforge.net/projects/pyrpl/files/pyrpl-mac>`__

   can be easily :ref:`downloaded <installing_pyrpl>` and run without any installation work.


.. admonition:: PyRPL's code is entirely public `on github <https://www.github.com/lneuhaus/pyrpl>`_ and can be customized,

   including the `Verilog source code for the FPGA <https://github.com/lneuhaus/pyrpl/tree/master/pyrpl/fpga>`_ which is based on the official Red Pitaya software version 0.95.


.. admonition:: PyRPL is already used in many research groups all over the world.

   See for yourself the :ref:`user_feedback`.


.. admonition:: PyRPL is free software and comes with the `GNU General Public License v3.0 <https://www.gnu.org/licenses/gpl.html>`_.

    Read the `license <https://github.com/lneuhaus/pyrpl/blob/master/LICENSE>`_ for more details!




.. _manual:

Manual
*******************

.. toctree::
   :maxdepth: 1
   :titlesonly:
   :hidden:

   installation
   gui
   api
   basics
   developer_guide/index
   contents

* :doc:`installation`
* :doc:`gui`
* :doc:`api`
* :doc:`basics`
* :doc:`developer_guide/index`
* :doc:`contents`


.. _low_level_example:

Low-level API example
************************

.. code-block:: python

    # import pyrpl library
    import pyrpl

    # create an interface to the Red Pitaya
    r = pyrpl.Pyrpl().redpitaya

    r.hk.led = 0b10101010  # change led pattern

    # measure a few signal values
    print("Voltage at analog input1: %.3f" % r.sampler.in1)
    print("Voltage at analog output2: %.3f" % r.sampler.out2)
    print("Voltage at the digital filter's output: %.3f" % r.sampler.iir)

    # output a function U(t) = 0.5 V * sin(2 pi * 10 MHz * t) to output2
    r.asg0.setup(waveform='sin',
                 amplitude=0.5,
                 frequency=10e6,
                 output_direct='out2')

    # demodulate the output signal from the arbitrary signal generator
    r.iq0.setup(input='asg0',   # demodulate the signal from asg0
                frequency=10e6,  # demodulaltion at 10 MHz
                bandwidth=1e5)  # demodulation bandwidth of 100 kHz

    # set up a PID controller on the demodulated signal and add result to out2
    r.pid0.setup(input='iq0',
                 output_direct='out2',  # add pid signal to output 2
                 setpoint=0.05, # pid setpoint of 50 mV
                 p=0.1,  # proportional gain factor of 0.1
                 i=100,  # integrator unity-gain-frequency of 100 Hz
                 input_filter = [3e3, 10e3])  # add 2 low-passes (3 and 10 kHz)

    # modify some parameters in real-time
    r.iq0.frequency += 2.3  # add 2.3 Hz to demodulation frequency
    r.pid0.i *= 2  # double the integrator unity-gain-frequency

    # take oscilloscope traces of the demodulated and pid signal
    data = r.scope.curve(input1='iq0', input2='pid0',
                         duration=1.0, trigger_source='immediately')


.. _high_level_example:

High-level API example
*************************

.. code-block:: python

    # import pyrpl library
    import pyrpl

    # create a Pyrpl object and store the configuration in a file 'filter-cavity.yml'
    p = pyrpl.Pyrpl(config='filter-cavity')

    # ... connect hardware (a Fabry-Perot cavity in this example) and
    #     configure its paramters with the PyRPL GUI that shows up

    # sweep the cavity length
    p.lockbox.sweep()

    # calibrate the cavity parameters
    p.lockbox.calibrate()

    # lock to the resonance with a predefined sequence
    p.lockbox.lock()

    # launch two different measurements simultaneously
    transfer_function = p.network_analyzer.single_async(
            input='lockbox.reflection', output='out2',
            start=1e3, stop=1e6, points=10000, rbw=1000)
    spectrum = p.spectrum_analyzer.single_async(
            input='in2', span=1e5, trace_averages=10)

    # wait for measurements to finish
    while not transfer_function.done() and not spectrum.done():
        # check whether lock was lost
        if not p.lockbox.is_locked():
            # re-lock the cavity
            p.lockbox.relock()
            # re-start measurements
            transfer_function = p.network_analyzer.single_async()
            spectrum = p.spectrum_analyzer.single_async()

    # display a measurement result in the curve browser
    p.curve_viewer.curve = transfer_function.result()


.. include:: user_feedback.rst


.. include:: publications.rst


.. include:: thanks.rst


.. |travis status| image:: https://travis-ci.org/lneuhaus/pyrpl.svg?branch=master
   :target: https://travis-ci.org/lneuhaus/pyrpl
.. |appveyor status| image:: https://ci.appveyor.com/api/projects/status/wv2acmg869acg5yy?svg=true
   :target: https://ci.appveyor.com/project/lneuhaus/pyrpl
.. |code coverage| image:: https://codecov.io/github/lneuhaus/pyrpl/coverage.svg?branch=master
   :target: https://codecov.io/gh/lneuhaus/pyrpl
.. |Python versions on PyPI| image:: https://img.shields.io/pypi/pyversions/pyrpl.svg
   :target: https://pypi.python.org/pypi/pyrpl/
.. |PyRPL version on PyPI| image:: https://img.shields.io/pypi/v/pyrpl.svg
   :target: https://pypi.python.org/pypi/pyrpl/
.. |Download pyrpl| image:: https://img.shields.io/sourceforge/dt/pyrpl.svg
   :target: https://sourceforge.net/projects/pyrpl/files/
.. |Documentation Status| image:: https://readthedocs.org/projects/pyrpl/badge/?version=latest
   :target: http://pyrpl.readthedocs.io/en/latest/
.. |join chat on gitter| image:: https://badges.gitter.im/JoinChat.svg
   :target: https://gitter.im/lneuhaus/pyrpl
.. |License| image:: https://img.shields.io/pypi/l/pyrpl.svg
   :target: https://github.com/lneuhaus/pyrpl/blob/master/LICENSE


Old documentation sections
**********************************************************

The old documentation is obsolete and will soon be deleted. Please refer to the more recent documentation in the :ref:`manual` section.

* :doc:`gallery/index`
* :doc:`user_guide/index`
* :doc:`reference_guide/index`
* :doc:`developer_guide/index`
* :doc:`indices_and_tables/index`
* :doc:`contents`


Current build status
***********************

|travis status| |appveyor status| |code coverage| |Python versions on PyPI| |PyRPL version on PyPI|

|Download pyrpl| |Documentation Status| |join chat on gitter| |License|


.. include:: changelog.rst