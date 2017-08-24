Hardware installation for PyRPL
*********************************

The `RedPitaya <http://redpitaya.readthedocs.io/en/latest/>`_ is an affordable FPGA board with fast analog inputs and outputs. 
Before starting, we need to prepare a bootable SD card for the RedPitaya. In principle, PyRPL is compatible with the lattest version of the RedPitaya OS, however, 
to prevent any compatibility issues, we provide here the version of the Redipatay OS against which PyRPL has been tested.

SD card preparation
===================

Option 0:
Download abd unzip the `Red Pitaya OS Version 0.92 image <https://sourceforge.net/projects/pyrpl/files/SD_Card_RedPitayaOS_v0.92.img.zip/download>`_. Flash this image on a >= 4 GB SD card using a tool like `Win32DiskImager <https://sourceforge.net/projects/win32diskimager/>`_, and insert the card into your Red Pitaya.

Option 1: flash the full image at once
--------------------------------------
For the SD card to be bootable by the redpitaya, several things need to be ensured (Fat32 formatting, boot flag on the right partition...), such that simply copying all required files onto the SD card is not enough to make it bootable. 
The simplest method is to copy bit by bit the content of an image file onto the sd card (including partition table and flags). On windows, this can be done with the software `Win32DiskImager <https://sourceforge.net/projects/win32diskimager/>`_. 
The next section provides a detailed procedure to make the SD card bootable starting from the list of files to be copied.


Option 2: Format and copy a list of files on the SD card
----------------------------------------------------------
The previous method can be problematic, for instance, if the capacity of the SD card is too small for the provided image file (Indeed, even empty space in the original 4 GB card has been included in the image file).
Hence, it can be advantageous to copy the files individually on the SD card, however, we need to pay attention to make the SD-card bootable. For this we need a Linux system. The following procedure assumes an `Ubuntu <https://www.ubuntu.com/>`_ system installed on a `virtualbox <https://www.virtualbox.org/>`_:
 #. Open the ubuntu virtualbox on a computer equipped with a SD card reader.
 #. To make sure the SD card will be visible in the virtualbox, we need to go to configuration/usb and enable the sd card reader.
 #. Open the ubuntu virtual machine and install gparted and dosfstools with the commands::
    sudo apt-get install gparted
    sudo apt-get install dosfstools
 #. Insert the sd card in the reader and launch gparted on the corresponding device (/dev/sdb in this case but the correct value can be found with "dmesg | tail")::
    sudo gparted /dev/sdb
 #. In the gparted interface, delete all existing partitions, create a partition map if there is not already one, then create 1 fat32 partition with the maximum space available. To execute these operations, it is necessary to unmount the corresponding partitions (can be done within gparted).
 #. Once formatted, right click to set the flag "boot" to that partition.
 #. Close gparted, remount the sd card (by simply unplugging/replugging it), and copy all files at the root of the sd card (normally mounted somewhere in /media/xxxx)


Communication with the Redpitaya
================================

To make sure the SD card is bootable, insert it into the slot of the Redpitaya and plug the power supply. Connect the redpitaya to your local network with an ethernet cable and enter the IP-adress of the repitaya into an internet browser.
The redpitaya welcome screen should show-up!

.. figure:: redpitaya_welcome.jpg
   :scale: 50 %
   :alt: Redpitaya welcome screen

   This is the Redpitaya welcome screen.


Quick start
=================

First, hook up your Red Pitaya / STEMlab to a LAN accessible from your
computer (follow the instructions for this on redpitya.com and make sure
you can access your Red Pitaya with a web browser by typing its
ip-address / hostname into the address bar). In an IPython console or
JuPyter notebook, type

::

    from pyrpl import Pyrpl
    p = Pyrpl(config='your_configuration_name', hostname='your_redpitaya_ip_address')

The GUI should open and you can start playing around with it. By calling
pyrpl with different strings for 'your\_configuration\_name', your
settings for a given configuration will be automatically remembered by
PyRPL. You can drop the hostname argument after the first call of a
given configuration. Different RedPitayas with different configuration
names can be run simultaneously.
