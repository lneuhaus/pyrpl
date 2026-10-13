Installation
*************

Preparing the hardware
=========================

For PyRPL to work, you need a working `Red Pitaya / STEMlab <https://www.redpitaya.com/>`_ connected to the same local area network (LAN) as the computer running PyRPL.
If you have not already set up your Red Pitaya, follow the current `official Red Pitaya quick-start documentation <https://redpitaya.readthedocs.io/en/latest/>`_ and make sure you can reach the board from your computer.

:doc:`user_guide/installation/hardware_installation` gives more detailed instructions in case you are experiencing any trouble.


.. _installing_pyrpl:

Installing PyRPL
=================

The easiest and fastest way to get PyRPL running is to download and execute the latest precompiled executable from the `PyRPL releases page <https://github.com/pyrpl-fpga/pyrpl/releases>`__.

For a Python installation, we recommend uv with Python 3.12 and PyQt5::

   uv python install 3.12
   uv venv --python 3.12
   uv pip install "pyrpl[qt-pyqt5]"

See :ref:`installation_from_source` for the complete uv workflow, pip and conda
alternatives, and development-source installation.


Compiling the FPGA code (optional)
===================================

A ready-to-use FPGA bitfile comes with PyRPL. If you want to build your own, possibly customized bitfile, go to :doc:`developer_guide/fpga_compilation`.
