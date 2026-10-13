Preparing a release
*******************

PyRPL publishes distributions through GitHub Actions. The package version in
``pyrpl/_version.py`` must match the release tag. Publishing a GitHub release
triggers ``.github/workflows/publish-pypi.yml``, which builds the source archive
and wheel, validates their metadata, and publishes them to PyPI using trusted
publishing.

Before creating the release, synchronize the development environment and run the
tests::

    uv sync --extra qt-pyqt5 --extra dev
    uv run pytest

You can validate the Python distributions locally as well::

    uv build
    uvx twine check dist/*

Use the ``Manual Binary Build`` workflow to build and smoke-test the standalone
applications. Its ``source_ref`` should identify the same commit as the release
tag. After checking its artifacts, run it with ``publish_release`` enabled to
attach the applications to the existing GitHub release.
