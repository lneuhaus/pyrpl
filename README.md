# <img src="https://github.com/lneuhaus/pyrpl/blob/master/logo.png" width="250" alt="PyRPL">
![travis status](https://travis-ci.com/lneuhaus/pyrpl.svg?token=Au8JgYk93p9iq2p6bSTp&branch=master "Travis status")
![code coverage](https://codecov.io/github/lneuhaus/pyrpl/coverage.svg?branch=master "Code coverage")
PyRPL (Python RedPitaya Lockbox) turns your RedPitaya into a powerful DSP device, especially suitable as a digital lockbox and measurement device in quantum optics experiments.

## Website
To get started, please check out the official [PyRPL website](http://lneuhaus.github.io/pyrpl/).

## Installation
Make sure you have an installation of Python (2.7 or 3.5). If you are new to Python or unexperienced with fighting installation issues, it is  recommended to install the [Anaconda](https://www.continuum.io/downloads)  Python distribution, which allows to install all PyRPL dependencies with the command
```
conda install numpy scipy paramiko pandas nose pip pyqt qtpy pyqtgraph pyyaml
```
If you are using virtual environments in conda, you can alternatively
create and activate a virtual environment for pyrpl with the following two commands
```
conda create -y -n pyrpl-env numpy scipy paramiko pandas nose pip pyqt qtpy pyqtgraph pyyaml
activate pyrpl-env
```
Check [this wiki page](https://github.com/lneuhaus/pyrpl/wiki/Installation:-Common-issues-with-anaconda) for hints if you cannot execute conda in a terminal. If you are not using Anaconda, you must manually install the python package [PyQt5](https://pypi.python.org/pypi/PyQt5) or [PyQt4](https://pypi.python.org/pypi/PyQt4), which requires a working C compiler installation on the system.

Next, clone (if you have a [git client](https://git-scm.com/downloads) installed - recommended option) the pyrpl repository to your computer with 
```
git clone https://github.com/lneuhaus/pyrpl.git
```
or [download and extract](https://github.com/lneuhaus/pyrpl/archive/master.zip) (if you do not want to install git on your computer) the repository. 

Install PyRPL by navigating with the command line terminal (the one where the pyrpl-env environment is active in case you are using anaconda) into the pyrpl root directory and typing
```
python setup.py develop
```

## Quick start
First, hook up your Red Pitaya / STEMlab to a LAN accessible from your computer (follow the instructions for this on redpitya.com and make sure you can access your Red Pitaya with a web browser by typing its ip-address /  hostname into the address bar).
In an IPython console or JuPyter notebook, type
```
from pyrpl import Pyrpl
p = Pyrpl(config='your_configuration_name', hostname='your_redpitaya_ip_address')
```
The GUI should open and you can start playing around with it. By calling pyrpl with different strings for 'your_configuration_name', your settings for a given configuration will be automatically remembered by PyRPL. You can drop the hostname argument after the first call of a given configuration. Different RedPitayas with different configuration names can be run simultaneously. 

## Issues
We collect a list of common problems in a [dedicated wiki page]
(https://github.com/lneuhaus/pyrpl/wiki/Installation:-Common-issues-with
-anaconda). If you do not find your problem listed there, please report all problems or wishes as new issues on [this page](https://github.com/lneuhaus/pyrpl/issues), so we can fix it and improve the future user experience.

## Unit test
If you want to check whether PyRPL works correctly on your machine, navigate with a command line terminal into the pyrpl root directory and type the  following commands (by substituting the ip-address / hostname of your Red Pitaya, of course)
```
set REDPITAYA_HOSTNAME=your_redpitaya_ip_address
nosetests
```
All tests should take about 3 minutes and finish without failures or errors. If there are errors, please report the console output as an issue (see the section "Issues" below for detailed explanations).

## Next steps / documentation
We are still in the process of creating an up-to-date version of the documentation of the current code. If the current documentation is wrong or insufficient, please post an [issue](https://github.com/lneuhaus/pyrpl/issues) and we will prioritize documenting the part of code you need. 
You can find all documentation in the subfolder ["doc"](https://github.com/lneuhaus/pyrpl/blob/master/doc). Get started by reading our paper on PyRPL, reading the official [html documentation](https://github.com/lneuhaus/pyrpl/blob/master/doc/sphinx/build/html/index.html), or going through the [tutorial.ipynb](https://github.com/lneuhaus/pyrpl/blob/master/doc/tutorial.ipynb) notebook. 

## Updates
Since PyRPL is continuously improved, you should install upgrades if you expect bugfixes by navigating into the pyrpl root directory on your local harddisk computer and typing
```
git pull
```

## FPGA bitfile generation (only for developers)
In case you would like to modify the logic running on the FPGA, you should make sure that you are able to generate a working bitfile on your machine. To do so, you must install Vivado 2015.4  [(64-bit windows](windows web-installer](https://www.xilinx.com/member/forms/download/xef.html?filename=Xilinx_Vivado_SDK_2015.4_1118_2_Win64.exe&akdm=1) or [Linux)](https://www.xilinx.com/member/forms/download/xef.html?filename=Xilinx_Vivado_SDK_2015.4_1118_2_Lin64.bin&akdm=1) and [together with a working license](https://github.com/lneuhaus/pyrpl/wiki/Installation:-How-to-get-the-right-license-for-Vivado-2015.4). Next, with a terminal in the pyrpl root directory, type
```
cd pyrpl/fpga
make
```
Compilation should take between 10 and 30 minutes, depending on your machine. If there are no errors during compilation, the new bitfile (pyrpl/fpga/red_pitaya.bin) will be automatically used at the next restart of PyRPL. The best way to getting started is to skim through the very short Makefile in the fpga directory and to continue by reading the files mentioned in the makefile and the refences therein. All verilog source code is located in the subdirectory pyrpl/fpga/rtl/. 

## License
Please read our license file [LICENSE](https://github.com/lneuhaus/pyrpl/blob/master/LICENSE) for more information. 
