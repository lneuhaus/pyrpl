` <http://lneuhaus.github.io/pyrpl/>`__
=======================================

|travis status| |code coverage| |Python versions on PyPI| |PyrRPL version on PyPI| |Documentation Status| |join chat on gitter| |License|

|Download PyRPL| |LGPLv3|

PyRPL (Python RedPitaya Lockbox) turns your RedPitaya into a powerful DSP device, especially suitable as a digital lockbox and measurement device in quantum optics experiments.

Website
-------

Get started by checking out the `official PyRPL website <http://lneuhaus.github.io/pyrpl/>`__.

Installation
------------

The easiest and fastest way to get PyRPL is to download and execute the `precompiled executable for windows <https://sourceforge.net/projects/pyrpl/files/latest/download>`__. This option requires no extra programs to be installed on the computer.

If instead you would like to use and/or modify the source code, make sure you have an installation of Python (2.7, 3.4, 3.5, or 3.6). If you are new to Python or unexperienced with fighting installation issues, it is recommended to install the `Anaconda <https://www.continuum.io/downloads>`__ Python distribution, which allows to install all PyRPL dependencies via

::

    conda install numpy scipy paramiko pandas nose pip pyqt qtpy pyqtgraph pyyaml

Check `this wiki page <https://github.com/lneuhaus/pyrpl/wiki/Installation:-Common-issues-with-anaconda>`__
for hints if you cannot execute conda in a terminal. Alternatively, if
you prefer creating a virtual environment for pyrpl, do so with the
following two commands

::

    conda create -y -n pyrpl-env numpy scipy paramiko pandas nose pip pyqt qtpy pyqtgraph pyyaml
    activate pyrpl-env

If you are not using Anaconda, you must manually install the python
package `PyQt5 <https://pypi.python.org/pypi/PyQt5>`__ or
`PyQt4 <https://pypi.python.org/pypi/PyQt4>`__, which requires a working
C compiler installation on the system.

Next, clone (if you have a `git
client <https://git-scm.com/downloads>`__ installed - recommended
option) the pyrpl repository to your computer with

::

    git clone https://github.com/lneuhaus/pyrpl.git

or `download and
extract <https://github.com/lneuhaus/pyrpl/archive/master.zip>`__ (if
you do not want to install git on your computer) the repository.

Install PyRPL by navigating with the command line terminal (the one
where the pyrpl-env environment is active in case you are using
anaconda) into the pyrpl root directory and typing

::

    python setup.py develop

Quick start
-----------

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

Issues
------

We collect a list of common problems in a `dedicated wiki
page <https://github.com/lneuhaus/pyrpl/wiki/Installation:-Common-issues-with-anaconda>`__.
If you do not find your problem listed there, please report all problems
or wishes as new issues on `this
page <https://github.com/lneuhaus/pyrpl/issues>`__, so we can fix it and
improve the future user experience.

Unit test
---------

If you want to check whether PyRPL works correctly on your machine,
navigate with a command line terminal into the pyrpl root directory and
type the following commands (by substituting the ip-address / hostname
of your Red Pitaya, of course)

::

    set REDPITAYA_HOSTNAME=your_redpitaya_ip_address
    nosetests

All tests should take about 3 minutes and finish without failures or
errors. If there are errors, please report the console output as an
issue (see the section "Issues" below for detailed explanations).

Next steps / documentation
--------------------------

The full PyRPL documentation is hosted at `http://pyrpl.readthedocs/io`_.
We are still in the process of creating an up-to-date version of the
documentation of the current code. If the current documentation is wrong
or insufficient, please post an
`issue <https://github.com/lneuhaus/pyrpl/issues>`__ and we will
prioritize documenting the part of code you need. You can find all
documentation in the subfolder
`"doc" <https://github.com/lneuhaus/pyrpl/blob/master/doc>`__. Get
started by reading our paper on PyRPL, reading the official `html
documentation <https://github.com/lneuhaus/pyrpl/blob/master/doc/sphinx/build/html/index.html>`__,
or going through the
`tutorial.ipynb <https://github.com/lneuhaus/pyrpl/blob/master/doc/tutorial.ipynb>`__
notebook.

Updates
-------

Since PyRPL is continuously improved, you should install upgrades if you
expect bugfixes by navigating into the pyrpl root directory on your
local harddisk computer and typing

::

    git pull

FPGA bitfile generation (only for developers)
---------------------------------------------

In case you would like to modify the logic running on the FPGA, you
should make sure that you are able to generate a working bitfile on your
machine. To do so, you must install Vivado 2015.4 `(64-bit
windows <windows%20web-installer%5D(https://www.xilinx.com/member/forms/download/xef.html?filename=Xilinx_Vivado_SDK_2015.4_1118_2_Win64.exe&akdm=1)%20or%20%5BLinux>`__](https://www.xilinx.com/member/forms/download/xef.html?filename=Xilinx\_Vivado\_SDK\_2015.4\_1118\_2\_Lin64.bin&akdm=1)
and `together with a working
license <https://github.com/lneuhaus/pyrpl/wiki/Installation:-How-to-get-the-right-license-for-Vivado-2015.4>`__.
Next, with a terminal in the pyrpl root directory, type

::

    cd pyrpl/fpga
    make

Compilation should take between 10 and 30 minutes, depending on your
machine. If there are no errors during compilation, the new bitfile
(pyrpl/fpga/red\_pitaya.bin) will be automatically used at the next
restart of PyRPL. The best way to getting started is to skim through the
very short Makefile in the fpga directory and to continue by reading the
files mentioned in the makefile and the refences therein. All verilog
source code is located in the subdirectory pyrpl/fpga/rtl/.

License
-------

Please read our license file
`LICENSE <https://github.com/lneuhaus/pyrpl/blob/master/LICENSE>`__ for
more information.

.. |travis status| image:: https://travis-ci.org/lneuhaus/pyrpl.svg?branch=master
   :target: https://travis-ci.org/lneuhaus/pyrpl
.. |code coverage| image:: https://codecov.io/github/lneuhaus/pyrpl/coverage.svg?branch=master
   :target: https://codecov.io/gh/lneuhaus/pyrpl
.. |Python versions on PyPI| image:: https://img.shields.io/pypi/pyversions/pyrpl.svg
   :target: https://pypi.python.org/pypi/pyrpl/
.. |PyrRPL version on PyPI| image:: https://img.shields.io/pypi/v/pyrpl.svg
   :target: https://pypi.python.org/pypi/pyrpl/
.. |Documentation Status| image:: https://readthedocs.org/projects/pyrpl/badge/?version=latest
   :target: http://pyrpl.readthedocs.io/en/latest/?badge=latest
.. |join chat on gitter| image:: https://badges.gitter.im/JoinChat.svg
   :target: https://gitter.im/lneuhaus/pyrpl
.. |License| image:: https://img.shields.io/pypi/l/pyrpl.svg
   :target: https://github.com/lneuhaus/pyrpl/blob/master/LICENSE
.. |Download PyRPL| image:: https://a.fsdn.com/con/app/sf-download-button
   :target: https://sourceforge.net/projects/pyrpl/files/
.. |LGPLv3| image:: https://www.gnu.org/graphics/gplv3-88x31.png
   :target: https://www.gnu.org/licenses/gpl.html
