.. pyrpl documentation master file, created by
   sphinx-quickstart on Fri Jul 08 23:10:33 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to pyrpl's documentation!
*********************************

The `Red Pitaya (a.k.a. STEM Lab) <http://www.redpitaya.com>`_ `(see full documentation) <http://redpitaya.readthedocs.io/en/latest/>`_ is an affordable FPGA board with fast analog inputs and outputs. This makes it interesting also for quantum optics experiments.

The software package PyRPL (Python RedPitaya Lockbox) is an implementation of many devices that are needed for optics experiments every day.
Its user interface and all high-level functionality is written in python, but an essential part of the software is hidden in a custom FPGA design (based on the official RedPitaya software version 0.95).
While most users probably never want to touch the FPGA design, the Verilog source code is provided together with this package and may be modified to customize the software to your needs.

.. toctree::
   :maxdepth: 2

   gallery/index
   user_guide/index
   reference_guide/index
   developer_guide/index
   indices_and_tables/index

