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

   See our :doc:`screenshot gallery <gallery/index>`.


.. admonition:: PyRPL has a convenient Python API.

   See :ref:`high_level_example` or :ref:`low_level_example`.


.. admonition:: PyRPL :ref:`binary executables for windows and linux <installing_pyrpl>`

   can be easily :ref:`downloaded <installing_pyrpl>` and run without any installation work.


.. admonition:: PyRPL's code is entirely public `on github <https://www.github.com/lneuhaus/pyrpl>`_ and may be customized,

   including the Verilog source code for the FPGA which is based on the official RedPitaya software version 0.95.


.. admonition:: PyRPL is free software and comes with the `GNU General Public License v3.0 <https://www.gnu.org/licenses/gpl.html>_.

    Read the `license <https://github.com/lneuhaus/pyrpl/blob/master/LICENSE>`_!


.. _manual:

Manual
*******************

* :doc:`gallery/index`
* :doc:`installation`
* :doc:`gui`
* :doc:`api`
* :doc:`developer_guide/index`
* :doc:`contents`


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

    # make a number of simultaneous measurements
    transfer_function = p.network_analyzer.single_async(
            input='lockbox.reflection', output='out2',
            start=1e3, stop=1e6, points=10000, rbw=1000)
    spectrum = p.spectrum_analyzer.single_async(
            input='in2', span=1e5, trace_averages=10)

    # wait for measurements to finish
    while not transfer_function.done() and not spectrum.done():
        # check whether lock was lost
        if not p.lockbox.is_locked():
            # re-lock
            p.lockbox.relock()
            # re-start measurements
            transfer_function = p.network_analyzer.single_async()
            spectrum = p.spectrum_analyzer.single_async()

    # display a measurement result in the curve browser
    p.curve_viewer.curve = transfer_function



.. _low_level_example:

Low-level API example
************************

.. code-block:: python

    # import pyrpl library
    import pyrpl

    # create an interface to the Red Pitaya
    r = pyrpl.Pyrpl().redpitaya

    # measure some signal values (instantaneously)
    print("Voltage at input1: %f"% r.sampler.in1)
    print("Voltage at output2: %f"% r.sampler.out2)

    # set up a lock-in amplifier
    r.iq0.setup(input='in1', output='out1',
                frequency=1e7, amplitude=0.1, bandwidth=1e5)

    # set up a PID controller on the lock-in signal
    r.pid0.setup(input='iq0', output='out2',
                 setpoint=0.1, # pid setpoint
                 p=0.1,  # proportional gain
                 i=100,  # integrator unit-gain frequency
                 input_filter = [2e3, 10e3]  # add two low-pass filters at 2 and 10 kHz
                 )

    # take oscilloscope traces of the lock-in and the pid output signals
    data = r.scope.curve(input1='iq0', input2='pid0',
                         duration=0.1, trigger_source='immediately')



Old documentation sections (new ones in :ref:`manual`)
**********************************************************

* :doc:`gallery/index`
* :doc:`user_guide/index`
* :doc:`reference_guide/index`
* :doc:`developer_guide/index`
* :doc:`indices_and_tables/index`
* :doc:`contents`
