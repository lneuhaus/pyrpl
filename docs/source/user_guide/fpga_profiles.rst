FPGA profiles and hardware tests
********************************

An FPGA profile binds a bitstream to its Python hardware contract: available
modules, capabilities, register-map constants, and timing metadata. The
``default`` profile remains the normal production profile. Specialized images
such as ``legacy``, ``no_iir``, ``iir32``, ``cordic``, ``cordic_vco``,
``arithmetic``, and the experimental ``pid_derivative`` profile must be
selected explicitly. The ``cordic`` profile
replaces the IIR with a standalone two-input phase detector, replaces the
legacy PFDs in IQ0 and IQ1 with integrated CORDICs, and disables the PID input
prefilters. IQ2 keeps its PFD and second quadrature output for the network and
spectrum analyzers.

Selecting a profile
===================

Applications can select a published profile directly::

    from pyrpl import Pyrpl

    pyrpl = Pyrpl(
        hostname="169.254.101.38",
        fpga_profile="pid_derivative",
        reloadfpga="auto",
    )

With ``reloadfpga="auto"``, PyRPL compares the requested profile with the
per-boot marker written after a successful load. It reloads the packaged image
when the marker is absent or names another profile. Startup then validates
hardware constants against the selected manifest.

External PID sample-and-hold
============================

In the ``default`` profile, each PID can use a synchronized expansion pin as
an active-high enable. For example::

    rp.pid0.pause_source = "external"
    rp.pid0.pause_pin = "P0"

The PID runs while P0 is high. While P0 is low, its controller state and
complete output are held rather than reset; they resume when P0 returns high.
Profile-specific input prefilters continue tracking the input while held.
Set ``pause_source="off"`` to disable this external control. The existing
``paused`` and ``pause_gains`` properties remain available independently.
The selected expansion pin should be configured as an input through ``rp.hk``.

Arithmetic module
=================

The ``arithmetic`` profile removes the IIR, keeps the PID input prefilters
disabled, enables the band-limited PID derivative, and uses DSP slot 4 for a
two-input arithmetic block. Both inputs can select any routed DSP signal::

    arithmetic = rp.arithmetic
    arithmetic.input = "in1"
    arithmetic.input_b = "in2"

Three operations are available::

    # a*x1**p + b*x2**q, with p and q independently equal to 1 or 2
    arithmetic.setup(
        operation="polynomial",
        coefficient_a=1.0,
        exponent_a=1,
        coefficient_b=0.5,
        exponent_b=2,
    )

    # a*x1*x2
    arithmetic.operation = "product"

    # a*x1/x2
    arithmetic.operation = "ratio"

Signals use normalized FPGA units and outputs saturate to the signed 14-bit
range. Set ``denominator_min`` to the smallest accepted denominator magnitude.
A smaller denominator saturates a nonzero ratio result and sets the read-only
``denominator_too_small`` status. Polynomial and product operations have four
cycles of latency. The divider accepts one input sample on every FPGA clock and
has sixteen cycles of latency.

``input_delay_a`` and ``input_delay_b`` add zero through seven cycles of delay.
For an approximate implementation of ``a*x + b*x**2 + c*x'``, configure a PID
for its proportional and derivative terms, route that PID to the first
arithmetic input, route ``x`` to the second input, square the second term, and
delay it to align approximately with the PID path.

CORDIC-controlled VCO
=====================

The ``cordic_vco`` profile extends ``cordic`` with an independently
configurable VCO input on all three IQ oscillators::

    rp.iq0.vco_input = "cordic"
    rp.iq0.vco_range = 2e6
    rp.iq0.vco_on = True

``vco_range`` is the frequency deviation in hertz for a +1 V routed input;
negative values reverse the tuning direction. The selected signal, product,
and effective frequency word are registered, giving the VCO control path a
three-cycle latency. Disable the loop with ``vco_on=False``. The ordinary
``cordic`` profile is unchanged and does not expose these controls.

Pytest profile behavior
=======================

Hardware pytest sessions use one FPGA profile at a time. The session fixture
currently passes ``reloadfpga=True``, so it loads the selected packaged image
at the start of every test process. It does not merely inspect the previously
loaded image and adapt to it.

The ``REDPITAYA_FPGA_PROFILE`` environment variable selects the profile. For
PowerShell::

    $env:REDPITAYA_HOSTNAME = "169.254.101.38"
    $env:REDPITAYA_FPGA_PROFILE = "pid_derivative"
    pytest pyrpl/test/test_hardware_modules/test_pid_na_iq.py

For ``cmd.exe``::

    set REDPITAYA_HOSTNAME=169.254.101.38
    set REDPITAYA_FPGA_PROFILE=pid_derivative
    pytest pyrpl\test\test_hardware_modules\test_pid_na_iq.py

There must be no spaces around ``=`` in the ``cmd.exe`` form.

Tests declare optional hardware requirements with a marker such as::

    @pytest.mark.requires_fpga("pid_derivative")

After loading the selected profile, an autouse fixture compares these markers
with the capabilities in its manifest. Tests with missing capabilities are
reported as skipped; unmarked tests run normally. For example, run only the
derivative tests with::

    pytest pyrpl/test/test_hardware_modules/test_pid_na_iq.py -k pid_derivative

Because the connection and FPGA profile are session-scoped, testing several
profiles requires separate pytest invocations. PowerShell can run them in
sequence::

    foreach ($profile in @("default", "legacy", "no_iir", "iir32", "pid_derivative", "arithmetic", "cordic", "cordic_vco")) {
        $env:REDPITAYA_FPGA_PROFILE = $profile
        pytest pyrpl/test/test_hardware_modules
    }

Development builds
==================

Only profiles staged under ``pyrpl/fpga/bitstreams`` are selectable at
runtime. After compiling a development profile, create its manifest and stage
its binary before testing::

    cd pyrpl/fpga
    make_bin.bat pid_derivative
    python publish_fpga_profile.py pid_derivative

For the arithmetic profile, use ``make_bin.bat arithmetic`` followed by
``python publish_fpga_profile.py arithmetic``. Its standalone RTL test can be
run before the full build with ``run_arithmetic_tb.bat``.

For the CORDIC profile, use ``make_bin.bat cordic`` and then
``python publish_fpga_profile.py cordic``. Once loaded, ``rp.cordic.input``
selects I and ``rp.cordic.input_q`` independently selects Q. The routed output
is ``atan2(Q, I)`` expressed in turns.

To process one IQ module directly, set ``rp.cordic.input_pair`` to ``"iq0"``,
``"iq1"``, or ``"iq2"``. The CORDIC then receives both filtered quadratures
through a local FPGA connection, independently of the IQ's ``output_signal``
setting. Select ``"independent"`` (the default) to use ``input`` and
``input_q`` instead.

IQ0 and IQ1 can also calculate phase concurrently without sharing the
standalone module::

    rp.iq0.output_signal = "cordic"
    phase_turns = rp.iq0.cordic_phase
    phase_radians = rp.iq0.cordic_phase_radians
    phase_degrees = rp.iq0.cordic_phase_degrees

The standalone ``rp.cordic`` remains available for independently routed
inputs such as ``in1`` and ``in2``.

For timing closure, all three IQ modulators in ``cordic`` and ``cordic_vco``
register their second multiplier products before adding them. This adds one
8 ns cycle to the remodulated/direct IQ output. The profile metadata models
the additional cycle; demodulated quadrature and integrated-CORDIC latency are
unchanged. The Network Analyzer correction delay is correspondingly four
cycles in these profiles.

For the combined profile, replace ``cordic`` with ``cordic_vco`` in both
commands. Its IQ modules additionally expose ``vco_input``, ``vco_range``,
and ``vco_on``.

Publishing makes the build selectable and records checksums. The staged
bitstream should still pass timing and hardware tests before its generated
artifacts are committed.

Result labels
=============

Frequency-response artifacts use the selected profile ID by default. Override
only their directory label with, for example::

    $env:PYRPL_BITSTREAM_LABEL = "pid_derivative_candidate_1"

``PYRPL_BITSTREAM_LABEL`` does not select, load, or identify the FPGA profile.
Use ``REDPITAYA_FPGA_PROFILE`` for that purpose.

Derivative cutoff cache
=======================

The ``pid_derivative`` Python model numerically calculates the exact discrete
3 dB roll-off frequency associated with each shift-filter setting. The helper uses
``@lru_cache(maxsize=None)`` so a shift value is calculated only once in a
Python process. Although the cache has no eviction limit, the hardware exposes
only 24 shift values, so it contains at most 24 practical entries. The cache
stores calculated Python values only; it never represents or replaces FPGA
state.
