Prepare a new release
**********************

The process of deploying new releases is automated in the file :code:`.travis.yml` and
is triggered when a new tag is created on github.com. This page contains what to do if
you want to manually deploy a new release.

First, we install a bunch of programs::

    conda create -y -n py34 python=3.4 numpy scipy paramiko pandas nose pip pyqt qtpy
    activate py34
    python setup.py develop
    pip install pyinstaller

Then, for the actual build::

    # do everything in python 3.4 for compatibility reasons
    activate py34

    # Readme file must be converted from Markdown to ReStructuredText to be displayed correctly on Pip
    pandoc --from=markdown --to=rst --output=README.rst README.md

    # Next, we must build the distributions (we provide source and binary):
    python setup.py sdist
    python setup.py bdist_wheel --universal

    # Last, make a windows executable file
    pyinstaller pyrpl.spec

    # Eventually we upload the distribution using twine:
    twine upload dist/*
