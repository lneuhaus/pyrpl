[<img src="https://pyrpl-fpga.github.io/pyrpl/_static/logo.png" width="250" alt="PyRPL">](https://www.pyrpl.org/)
[![GitHub Actions CI](https://github.com/pyrpl-fpga/pyrpl/actions/workflows/ci.yml/badge.svg)](https://github.com/pyrpl-fpga/pyrpl/actions)
[![code coverage](https://codecov.io/github/pyrpl-fpga/pyrpl/coverage.svg?branch=master "Code coverage")](https://codecov.io/gh/pyrpl-fpga/pyrpl)
[![Python versions](https://img.shields.io/badge/python-3.8%20|%203.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13-blue.svg)](https://github.com/pyrpl-fpga/pyrpl)
[![Documentation Status](https://img.shields.io/badge/docs-github%20pages-blue)](https://pyrpl-fpga.github.io/pyrpl/)
[![join chat on gitter](https://badges.gitter.im/JoinChat.svg "Join chat on gitter")](https://gitter.im/lneuhaus/pyrpl)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/pyrpl-fpga/pyrpl/blob/master/LICENSE)
[![GitHub downloads](https://img.shields.io/github/downloads/pyrpl-fpga/pyrpl/total)](https://github.com/pyrpl-fpga/pyrpl/releases/latest)
[![GitHub release](https://img.shields.io/github/v/release/pyrpl-fpga/pyrpl)](https://github.com/pyrpl-fpga/pyrpl/releases/latest)

PyRPL (Python RedPitaya Lockbox) turns your RedPitaya into a powerful DSP device, especially suitable as a digital lockbox and measurement device in quantum optics experiments. A detailed scientific article describing PyRPL's architecture and functions can be found here:

[Python Red Pitaya Lockbox (PyRPL): An open source software package for digital feedback control in quantum optics experiments](https://pubs.aip.org/aip/rsi/article-abstract/95/3/033003/3269904/Python-Red-Pitaya-Lockbox-PyRPL-An-open-source?redirectedFrom=fulltext)

## Website
The official PyRPL website address is [http://pyrpl.readthedocs.io/](http://pyrpl.readthedocs.io).

## Installation
The easiest way to run PyRPL is to download the latest precompiled application for
Windows, macOS, or Linux from the [releases page](https://github.com/pyrpl-fpga/pyrpl/releases).
It does not require a separate Python installation.

For a Python installation, we recommend [uv](https://docs.astral.sh/uv/). PyRPL
supports Python 3.8 through 3.13; Python 3.12 is a conservative choice with broad Qt
support:

```bash
uv python install 3.12
uv venv --python 3.12
uv pip install "pyrpl[qt-pyqt5]"
uv run python -m pyrpl your_configuration_name
```

PyRPL requires one Qt binding. You can replace `qt-pyqt5` with `qt-pyqt6`,
`qt-pyside2`, or `qt-pyside6`.

To work on the source code:

```bash
git clone https://github.com/pyrpl-fpga/pyrpl.git
cd pyrpl
uv sync --extra qt-pyqt5 --extra dev
uv run pytest
```

Standard `venv` and pip remain supported. Create and activate a virtual environment,
then run `python -m pip install "pyrpl[qt-pyqt5]"`, or install a checkout with
`python -m pip install -e ".[qt-pyqt5]"`.

If your laboratory already uses conda, it can manage the environment while pip installs
PyRPL from PyPI:

```bash
conda create -n pyrpl-env python=3.12 pip
conda activate pyrpl-env
python -m pip install "pyrpl[qt-pyqt5]"
```

## Installation with Optional Dependencies

### For Testing

```bash
uv sync --extra qt-pyqt5 --extra test
```

### For IPython/Jupyter Support

```bash
uv sync --extra qt-pyqt5 --extra ipython
```

### For Development (all dependencies)

```bash
uv sync --extra qt-pyqt5 --extra dev
```


## Quick start
First, hook up your Red Pitaya / STEMlab to a LAN accessible from your computer (follow the instructions for this on redpitya.com and make sure you can access your Red Pitaya with a web browser by typing its ip-address /  hostname into the address bar).
In a command line terminal, type
```
python -m pyrpl your_configuration_name
```
A GUI should open, let you configure the RedPitaya device you would like to use, and you can start playing around with pyrpl. Different strings for 'your_configuration_name' create different configurations that will be automatically remembered by PyRPL, for example if you have several different redpitayas. Different RedPitayas with different configuration names can be run simultaneously in separate terminals.
A GUI should open, let you configure the RedPitaya device you would like to use, and you can start playing around with pyrpl. Different strings for 'your_configuration_name' create different configurations that will be automatically remembered by PyRPL, for example if you have several different redpitayas. Different RedPitayas with different configuration names can be run simultaneously in separate terminals.

## Issues
We collect a list of common problems on the [documentation website](http://pyrpl-fpga.github.io/pyrpl//en/latest/user_guide/installation/common_problems.html). If you do not find your problem listed there, please report all problems or wishes as new issues on [this page](https://github.com/pyrpl-fpga/pyrpl/issues), so we can fix it and improve the future user experience.

## Unit test
If you want to check whether PyRPL works correctly on your machine, navigate with a command line terminal into the pyrpl root directory and type the  following commands (by substituting the ip-address / hostname of your Red Pitaya, of course)
```
uv sync --extra qt-pyqt5 --extra test
set REDPITAYA_HOSTNAME=your_redpitaya_ip_address
uv run pytest
```
All tests should take about 3 minutes and finish without failures or errors. If there are errors, please report the console output as an issue (see the section "Issues" below for detailed explanations).

Hardware tests use one FPGA profile per pytest session. Select a published
profile with `REDPITAYA_FPGA_PROFILE`; the test fixture loads its bitstream and
skips tests whose `requires_fpga` capabilities are unavailable:

```bat
set REDPITAYA_HOSTNAME=169.254.101.38
set REDPITAYA_FPGA_PROFILE=pid_derivative
uv run pytest pyrpl\test\test_hardware_modules\test_pid_na_iq.py
```

In PowerShell, use `$env:REDPITAYA_FPGA_PROFILE = "pid_derivative"`. The
`PYRPL_BITSTREAM_LABEL` variable only labels saved frequency-response results;
it does not select an FPGA image. See the
[FPGA profile and test documentation](pyrpl/fpga/README.md#testing-fpga-profiles)
for staging development builds and testing multiple profiles.

The experimental `arithmetic` profile replaces the IIR with a two-input
polynomial, multiplier, and protected divider, and enables the band-limited
PID derivative. Build it with `pyrpl\fpga\make_bin.bat arithmetic`; after
publishing it, select it with `REDPITAYA_FPGA_PROFILE=arithmetic`.

## Next steps / documentation
The full html documentation is hosted at [http://pyrpl-fpga.github.io/pyrpl/](http://pyrpl-fpga.github.io/pyrpl/). Alternatively, you can download a .pdf version at [https://media.readthedocs.org/pdf/pyrpl/latest/pyrpl.pdf](https://media.readthedocs.org/pdf/pyrpl/latest/pyrpl.pdf). We are still in the process of creating an fully up-to-date version of the documentation of the current code. If the current documentation is wrong or insufficient, please post an [issue](https://github.com/pyrpl-fpga/pyrpl/issues/new) and we will prioritize documenting the part of code you need.

## Updates
Since PyRPL is continuously improved, you should install upgrades if you expect bugfixes. 
If you have cloned the GitHub repository (recommended for bleeding-edge updates), navigate into the pyrpl root directory on your local harddisk computer and type
```
git pull
```

## FPGA bitfile generation (only for developers)
In case you would like to modify the logic running on the FPGA, you should make sure that you are able to [generate a working bitfile on your machine](http://pyrpl-fpga.github.io/pyrpl//en/latest/developer_guide/fpga_compilation.html). In short, to do so, you must install Vivado 2024.2 [(64-bit windows](windows web-installer](https://www.xilinx.com/member/forms/download/xef.html?filename=Xilinx_Vivado_SDK_2024.2_1118_2_Win64.exe&akdm=1) or [Linux)](https://www.xilinx.com/member/forms/download/xef.html?filename=Xilinx_Vivado_SDK_2024.2_1118_2_Lin64.bin&akdm=1) [together with a working license](http://pyrpl-fpga.github.io/pyrpl//en/latest/developer_guide/fpga_compilation.html#fpga-license). Next, with a terminal in the pyrpl root directory, type
```
cd pyrpl/fpga
make
```
Compilation should take between 10 and 30 minutes, depending on your machine. If there are no errors during compilation, the new bitfile will be in the (pyrpl/fpga/out) repository. If you replace the (pyrpl/fpga/red_pitaya.bin), it will be automatically used at the next restart of PyRPL. The best way to getting started is to skim through the very short Makefile in the fpga directory and to continue by reading the files mentioned in the makefile and the refences therein. All verilog source code is located in the subdirectory pyrpl/fpga/rtl/. 

## License
Please read our license file [LICENSE](https://github.com/pyrpl-fpga/pyrpl/blob/master/LICENSE) for more information. 
