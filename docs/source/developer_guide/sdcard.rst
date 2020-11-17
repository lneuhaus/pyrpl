
SD card preparation
===================

Option 0:
Download and unzip the `Red Pitaya OS Version 0.92 image <https://sourceforge.net/projects/pyrpl/files/SD_Card_RedPitayaOS_v0.92.img.zip/download>`_. Flash this image on a >= 4 GB SD card using a tool like `Win32DiskImager <https://sourceforge.net/projects/win32diskimager/>`_, and insert the card into your Red Pitaya.


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
