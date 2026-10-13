Installing PyRPL
*********************************


Running the precompiled application (easiest)
==============================================

Download the latest application for Windows, macOS, or Linux from the
`PyRPL releases page <https://github.com/pyrpl-fpga/pyrpl/releases>`__.
This option does not require a separate Python installation.


.. _installation_from_source:

Installing the Python package with uv (recommended)
=====================================================

`uv <https://docs.astral.sh/uv/>`__ can install Python, create an isolated
environment, and install PyRPL. PyRPL supports Python 3.8 through 3.13;
Python 3.12 is a conservative choice with broad Qt support::

    uv python install 3.12
    uv venv --python 3.12
    uv pip install "pyrpl[qt-pyqt5]"

Run PyRPL without activating the environment::

    uv run python -m pyrpl your_configuration_name

PyRPL requires one Qt binding. You can replace ``qt-pyqt5`` with
``qt-pyqt6``, ``qt-pyside2``, or ``qt-pyside6``.


Installing from a source checkout
==================================

Clone the repository and synchronize a development environment::

    git clone https://github.com/pyrpl-fpga/pyrpl.git
    cd pyrpl
    uv sync --extra qt-pyqt5 --extra dev

Run PyRPL and the test suite through uv::

    uv run python -m pyrpl your_configuration_name
    uv run pytest


Using venv and pip
==================

Standard Python environments remain supported. Create and activate a virtual
environment using your platform's Python documentation, then install PyRPL::

    python -m pip install "pyrpl[qt-pyqt5]"

From a source checkout, use an editable installation for development::

    python -m pip install -e ".[qt-pyqt5,dev]"


Using an existing conda installation (optional)
================================================

If your laboratory already uses conda, let conda manage Python and the virtual
environment, then install PyRPL and its dependencies from PyPI::

    conda create -n pyrpl-env python=3.12 pip
    conda activate pyrpl-env
    python -m pip install "pyrpl[qt-pyqt5]"

A separate conda package is not required.
