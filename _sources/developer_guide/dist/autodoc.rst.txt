Building the documentation
**************************

Install the documentation dependencies and build the Sphinx site from the
repository root::

    uv sync --extra docs
    uv run sphinx-build -b html docs/source docs/build/html

The generated site is written to ``docs/build/html``. The documentation GitHub
Actions workflow performs the corresponding build for published documentation.

Docstrings should follow the project's :doc:`../codingstyle` guidance so that
Sphinx can render the API reference consistently.
