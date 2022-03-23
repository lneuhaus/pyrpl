Installing PyRPL
*********************************


Running from binary files (fastest)
====================================

The easiest and fastest way to get PyRPL running is to download and execute the `precompiled executable for windows "pyrpl-windows.exe" <https://sourceforge.net/projects/pyrpl/files/pyrpl-windows.exe>`__ or `linux "pyrpl-linux" <https://sourceforge.net/projects/pyrpl/files/pyrpl-linux>`__. This option requires no extra programs to be installed on the computer. If you want the Pyrpl binaries for a Mac, please let us know `by creating a new issue <https://www.github.com/lneuhaus/pyrpl/issues/new>`_ and we will prepare them for you.



.. _installation_from_source:

Running the Python source code
===================================

If you would like to use and/or modify the source code, make sure you have an installation of Python (2.7, 3.4, 3.5, or 3.6).


Prerequisites: Getting the right Python installation
-------------------------------------------------------

There are many ways to get the Python working with Pyrpl. The following list is non-exhaustive

.. _anaconda_installation:

Option 1: Installation from Anaconda
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are new to Python or unexperienced with fighting installation issues, it is recommended to install the `Anaconda <https://www.continuum.io/downloads>`__ Python distribution, which allows to install all PyRPL dependencies via::

    conda install numpy scipy paramiko pandas nose pip pyqt qtpy pyqtgraph pyyaml nbconvert

Check :ref:`anaconda_problems` for hints if you cannot execute conda in a terminal. Alternatively, if you prefer creating a virtual environment for pyrpl, do so with the following two commands::

    conda create -y -n pyrpl-env numpy scipy paramiko pandas nose pip pyqt qtpy pyqtgraph pyyaml nbconvert
    activate pyrpl-env


Option 2: Installation on a regular (non-Anaconda) python version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are not using Anaconda, installing all Python packages required to run pyrpl can be difficult, frustrating and time-consuming, at least on Windows systems, so even if you have Python (should be one of the versions 2.7, 3.4, 3.5, or 3.6) already installed, you should reconsider ":ref:`anaconda_installation`", especially since Anaconda can be installed to work side-by-side with pre-existing Python installations if the (default) installation option to not modify environment variables is chosen.

The main reason for the difficulty to work without Anaconda on windows is that you need a C-compiler that works in harmony with the python package manager "pip" to compile the C-extensions of these packages. A workaround is to indivitually download and install the `precompiled Python wheels by Christoph Gohlke <http://www.lfd.uci.edu/~gohlke/pythonlibs/>`_. You should install the following packages this way before attempting installing Pyrpl: numpy, scipy, paramiko, pandas, PyQt4, pyqtgraph.

Even if you have a working C-compiler on your system, you must manually install the python package `PyQt5 <https://pypi.python.org/pypi/PyQt5>`__ or `PyQt4 <https://pypi.python.org/pypi/PyQt4>`__, since this package is not mangaged by the python package manager "pip".

All remaining dependencies will be automatically installed by setuptools when Pyrpl is installed (see the section :ref:`actual_installation`).


.. _actual_installation:

Downloading and installing PyRPL from source
-------------------------------------------------------

Various channels are available to obtain the PyRPL source code.


Option 1: Installation with pip (recommended, for standard users)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have pip correctly installed, executing the following line in a command line should install pyrpl and all missing dependencies::

    pip install pyrpl



Option 2: From github.com (for developers and tinkerers)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have a `git client <https://git-scm.com/downloads>`__ installed (recommended), clone the pyrpl repository to your computer with::

    git clone https://github.com/lneuhaus/pyrpl.git YOUR_PYRPL_DESTINATION_FOLDER

If you do not want to install git on your computer, just download and extract the repository `from github.com <https://github.com/lneuhaus/pyrpl/archive/master.zip>`__ () the repository.

Install PyRPL by navigating with the command line terminal (the one where the pyrpl-env environment is active in case you are using anaconda) into the pyrpl root directory and typing::

    python setup.py develop

