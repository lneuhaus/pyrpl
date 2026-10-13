Unittests
***********************

The tests live in ``pyrpl/test`` and run with pytest. They fall in three
groups:

* **Tests without hardware**, for example the IIR theory, the memory tree or
  the parameter edge cases. They run anywhere.
* **Hardware tests**: every test that uses the ``hardware_session`` fixture,
  directly or through the ``TestPyrpl`` base class, is marked ``hardware``
  automatically. They need a Red Pitaya.
* **Simulation tests**: hardware tests also marked ``simulation``. They pass
  on the simulated Red Pitaya (hostname ``_FAKE_``), so they run without a
  board too.

The board is selected with the environment variable ``REDPITAYA_HOSTNAME``.
When it is not set, or set to ``_FAKE_``, the tests use the simulated Red
Pitaya and skip the hardware tests that are not marked ``simulation``.

Running the tests
=================

Without a board::

    pytest pyrpl/test

With a board (Windows: ``set REDPITAYA_HOSTNAME=rp-xxxxxx.local``)::

    REDPITAYA_HOSTNAME=rp-xxxxxx.local pytest pyrpl/test

Only the hardware tests, or only the tests that do not need a board::

    pytest pyrpl/test -m hardware
    pytest pyrpl/test -m "not hardware or simulation"

The Red Pitaya session is only created when a selected test uses it, so the
tests without hardware never connect to a board. When it is created, the FPGA
is reprogrammed and the communication speed is checked against
``test.max_communication_time`` of the global configuration.

A hardware test that should also run on the simulated Red Pitaya gets the
``simulation`` marker, for a whole file with::

    pytestmark = pytest.mark.simulation

Only add it after checking that the test passes with
``REDPITAYA_HOSTNAME=_FAKE_``: the simulated Red Pitaya only models a part of
the register map.

Continuous integration
======================

The ``CI`` workflow (``.github/workflows/ci.yml``) has two test jobs:

* ``unit`` runs the tests without hardware and the simulation tests on every
  supported Python version, on GitHub-hosted runners.
* ``hardware`` runs the hardware tests once, on a single Python version, on
  the self-hosted runner connected to the Red Pitaya. It is skipped when the
  board is offline; run the workflow manually once it is connected.

Both use ``pytest-timeout``, so that a hanging test fails instead of blocking
the job until its timeout.
