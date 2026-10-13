Building standalone applications
********************************

Standalone applications are built by the ``Manual Binary Build`` GitHub Actions
workflow for Windows, macOS, and Linux. This is the preferred release process
because it builds and smoke-tests each application on its target platform.

To test a build locally from the project root::

    uv sync --extra qt-pyqt5 --extra dev
    uv run pyinstaller --clean pyrpl.spec

The result is written below ``dist/``. Keep ``pyrpl.spec`` synchronized with
package-data changes so that the FPGA bitfile, monitor server, and other runtime
files are included.
