Installation
*************

Preparing the hardware
=========================

For PyRPL to work, you must have a working `Red Pitaya / StemLab <http://www.redpitaya.com>`_ (`official documentation <http://redpitaya.readthedocs.io/en/latest/>`_) connected to the same local area network (LAN) as the computer PyRPL is running on. PyRPL is compatible with all operating system versions of the Red Pitaya and does not require any customization of the Red Pitaya. If you have not already set up your Red Pitaya:

* download and unzip the `Red Pitaya OS Version 0.92 image <https://sourceforge.net/projects/pyrpl/files/SD_Card_RedPitayaOS_v0.92.img.zip/download>`_,
* flash this image on 4 GB (or larger) micro SD card using `Win32DiskImager <https://sourceforge.net/projects/win32diskimager/>`_ (see a `step-by-step guide for all operating systems <http://redpitaya.readthedocs.io/en/latest/quickStart/SDcard/SDcard.html>`_), and insert the card into your Red Pitaya, and
* connect the Red Pitaya to your LAN and connect its power supply.

:doc:`user_guide/installation/hardware_installation` gives more detailed instructions in case you are experiencing any trouble.


.. _installing_pyrpl:

Installing PyRPL
=================

The easiest and fastest way to get PyRPL running is to download and execute the latest precompiled executable for

* **windows**: `pyrpl-windows.exe <https://sourceforge.net/projects/pyrpl/files/pyrpl-windows.exe>`__,
* **linux**: `pyrpl-linux <https://sourceforge.net/projects/pyrpl/files/pyrpl-linux>`__, or
* **Mac OS X**: `pyrpl-mac <https://sourceforge.net/projects/pyrpl/files/pyrpl-mac>`__.

If you prefer an installation from source code, go to :ref:`installation_from_source`.


Compiling the FPGA code (optional)
===================================

A ready-to-use FPGA bitfile comes with PyRPL. If you want to build your own, possibly customized bitfile, go to :doc:`developer_guide/fpga_compilation`.