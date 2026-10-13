Hardware installation for PyRPL
*********************************

The `Red Pitaya <https://redpitaya.readthedocs.io/en/latest/>`_ is an affordable FPGA board with fast analog inputs and outputs. PyRPL implements a large number of measurement and real-time feedback instruments for this platform. For PyRPL to work, you must have a working `Red Pitaya / STEMlab <https://www.redpitaya.com/>`_ connected to the same local area network (LAN) as the computer PyRPL is running on. If you have not already set up your Red Pitaya, follow :ref:`sdcard_official` and then run :ref:`sdcard_check`.


.. _sdcard_official:

Follow the official documentation
==================================
Follow the quick-start steps in the `official Red Pitaya documentation <https://redpitaya.readthedocs.io/en/latest/>`_ until you can access the Red Pitaya from your computer. You are then ready for :ref:`installing_pyrpl`.



.. _sdcard_check:

Check that it is working
================================

The fastest way to check that the Red Pitaya is working is to launch PyRPL and let it automatically discover the Red Pitaya device. If this does not work, you may want to ensure that the Red Pitaya and SD card are actually working together.

To make sure the SD card is bootable, insert it into the slot of the Red Pitaya and plug in the power supply. Connect the Red Pitaya to your local network with an ethernet cable and enter its IP address in a web browser. The Red Pitaya welcome screen should show up.

.. figure:: redpitaya_welcome.jpg
   :scale: 50 %
   :alt: Redpitaya welcome screen

   This is the Redpitaya welcome screen.

