Releases
********

Version 0.9.9.1 (August 6, 2026)
=================================

- include dynamically imported lockbox models in PyInstaller executables
- prevent frozen-app import failures from being obscured by an invalid fallback
  import
- make PyQt5 selection deterministic when other Qt bindings are installed in
  the build environment
- smoke-test the Windows executable before publishing a binary release

Version 0.9.9.0 (August 5, 2026)
=================================

- add compatibility with Red Pitaya OS 3, including FPGA overlay loading and
  automatic installation of the compatible hard-float monitor server
- improve Red Pitaya OS-version detection and command-output parsing
- disable Nagle's algorithm for monitor-server requests to avoid delayed small
  register transactions, especially on Windows
- allow lockbox inputs and outputs to be added and removed dynamically and
  persist their selected signal classes
- make lockbox widgets robust to unconfigured inputs and Qt tab initialization,
  and isolate lockbox/PID state between tests
- keep constant scope traces visible when they coincide with a grid line
- modernize imports and formatting and update the test suite for Python 3.13

Version 0.9.8.0
===============

- add compatibility with Red Pitaya Gen 2
- add smarter ``reloadfpga="auto"`` startup behavior, reloading the FPGA image
  only when the PyRPL bitfile is not already loaded
- improve and modernize the documentation
- improve SSH connection handling
- support Python through version 3.13; Python 3.14 is not yet supported because
  of changes to ``asyncio``
- modernize continuous integration and testing; remote hardware tests can
  remain sensitive to network latency between GitHub-hosted runners and the
  Red Pitaya

Version 0.9.5.0
===============

- merges the "0.9.3-develop" branch with accumulated upgrades from over 2 years
- last version to support Python 2.7 (though not running tests anymore)
- tested on Python 3.6 and 3.7
- significant improvements to IIR filter module

Version 0.9.4.0
===============

- smoother transitions of output voltages during lockbox stage transitions
- extend automatic Red Pitaya discovery to multiple network adapters and
  STEMlab OS 0.98
- improve the documentation hosted on `pyrpl.org <https://www.pyrpl.org>`_ and
  provide a `video tutorial <https://www.youtube.com/watch?v=WnFkz1adhgs>`_
- automatically generate Windows, Linux, and macOS binaries for releases and
  publish them on `SourceForge <https://sourceforge.net/projects/pyrpl/files/>`_

Version 0.9.3.x and earlier
===========================

There are no release notes for PyRPL versions prior to version 0.9.4.0.

