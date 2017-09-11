Basics of PyRPL
*****************

This section presents the basic architecture of PyRPL.

Motivation
===========

Available hardware borads featuring FPGAs, CPUs and analog in- and outputs makes it possible to use digital signal processing (DSP) 
to control quantum optics experiments. Running open-source software on this hardware has many advantages:

- Lab space: small size, less different devices
- Money: cheap hardware, free software
- Time: connect cables once, re-wire digitally automate experiments work from home
- Automated measurements incite to take more data-points perform experiments more reproducibly
  record additional, auxiliary data
- Functionality beyond analog electronics
- Modify or customize instrument functionality

Hardware Platform - Red Pitaya
===============================

At the moment, Red Pitaya is the only hardware platform supported by PyRPL.

.. image:: redpitaya.jpg
   :scale: 100 %
   :alt: The redpitaya board
   :align: center

The RedPitaya board is an affordable FPGA + CPU board running a Linux operating system. The FPGA is running at a clock rate of 125 MSps and 
it is interfaced with 2 analog inputs and 2 analog outputs (14 bits, 125 MSps). The minimum input-output latency is of the order of 200 ns and
the effective resolution is 12 bits for inputs and 13 bits for outputs. 4 slow analog inputs and outputs and 16 I/O ports are also available. 
Visit the The Red Pitaya homepage (http://www.redpitaya.com) for more details on the platform.

Software Infrastructure
=======================

The FPGA functionalities of PyRPL are organized in various DSP modules. These modules can be configured and arbitrarily connected together 
using a python package running on a client computer. This design offers a lot of flexibility in the design and control of various experimental 
setups without having to recompile the FPGA code each time a different fonctionality is needed. A fast ethernet interface maps all FPGA registers 
to Python variables. The read/write time is around 250 microseconds for a typical LAN connection. High-level functionalities are achieved by 
performing successive operations on the FPGA registers using the Python API. A Graphical User Interface is also provided to easily visualize and 
modify the different FPGA registers. We provide a description of the different software components below.

.. image:: software_architecture.jpg
   :scale: 100 %
   :alt: PyRPL software architecture
   :align: center

FPGA modules
------------

At the moment, the FPGA code provided with PyRPL implements various Digital Signal Processing modules:

+--------------+------------+--------------------------------------------------------+
|  Module name |# available | Short description                                      |
+==============+============+========================================================+
|  Scope       | 1          | A 16384 points, 2 channels oscilloscope                |
|              |            | capable of monitoring internal or external signals     |
+--------------+------------+--------------------------------------------------------+
| ASG          | 2          | An arbitrary signal generator capable of generating    |
|              |            | various waveforms, and even gaussian white noise       |
+--------------+------------+--------------------------------------------------------+
| IQ modulator/| 3          | An internal frequency reference is used to digitally   |
|              |            | demodulate a given input signal. The frequency         | 
|              |            | reference can be outputed to serve as a driving signal.| 
|              |            | The slowly varying quadratures can also be used to     |
|              |            | remodulate the internal reference, turning the module  |
| demodulator  |            | into a very narrow bandpass filter. For more details,  |
|              |            | see this page :ref:`Iq Widget` for more details        |
+--------------+------------+--------------------------------------------------------+

