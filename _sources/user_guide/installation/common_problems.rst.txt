Common installation problems
******************************


The ``uv`` command is not available
====================================

Install uv by following its `official installation instructions
<https://docs.astral.sh/uv/getting-started/installation/>`__. Close and reopen
the terminal if the installer changed your ``PATH``.


PyRPL cannot find a Qt binding
==============================

Install exactly one of PyRPL's Qt extras. PyQt5 is the default documented
choice::

    uv pip install "pyrpl[qt-pyqt5]"

The alternatives are ``qt-pyqt6``, ``qt-pyside2``, and ``qt-pyside6``.


PyRPL was installed but cannot be imported
===========================================

Run Python in the same environment in which PyRPL was installed. From a uv
project or a directory containing the ``.venv`` created by ``uv venv``, use::

    uv run python -c "import pyrpl; print(pyrpl.__version__)"

If you use conda, activate the environment before running Python::

    conda activate pyrpl-env
    python -c "import pyrpl; print(pyrpl.__version__)"
