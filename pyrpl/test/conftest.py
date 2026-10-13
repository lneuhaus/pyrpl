# conftest.py - pytest automatically discovers fixtures from this file
import contextlib
import logging
import os
import socket
from collections import namedtuple

import pytest

from .. import Pyrpl, RedPitaya, global_config
from ..async_utils import sleep
from ..directories import user_config_dir
from ..pyrpl_utils import time

logger = logging.getLogger(name=__name__)


def pytest_report_header(config):
    """Make Qt/NumPy differences visible in hardware-test diagnostics."""
    import numpy as np
    import qtpy

    return f"PyRPL runtime: Qt={qtpy.API_NAME}, NumPy={np.__version__}"


# A container to standardize what the fixture returns
# rp is always present; pyrpl is None if running in light mode
HardwareSession = namedtuple("HardwareSession", ["rp", "pyrpl", "read_time", "write_time"])

# Test files that only need the RedPitaya driver, not the full Pyrpl app
LIGHT_TEST_FILES = ["test_redpitaya.py", "test_pyqtgraph_benchmark.py", "test_registers.py"]
SIMULATED_HOSTNAMES = ("_FAKE_", "_FAKE_REDPITAYA_")


def _real_board():
    """True when REDPITAYA_HOSTNAME designates a physical Red Pitaya."""
    return os.environ.get("REDPITAYA_HOSTNAME", "") not in ("", *SIMULATED_HOSTNAMES)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "hardware: uses the Red Pitaya session (added automatically to every test "
        "that depends on the hardware_session fixture)",
    )
    config.addinivalue_line(
        "markers",
        "simulation: a hardware test that also passes on a simulated (_FAKE_) Red Pitaya",
    )
    # Without a board, the session uses the simulated Red Pitaya instead of
    # asking for a hostname in a GUI.
    if not _real_board():
        os.environ["REDPITAYA_HOSTNAME"] = "_FAKE_"


def pytest_collection_modifyitems(session, config, items):
    """Marks the tests that use the Red Pitaya session.

    Without a real board (REDPITAYA_HOSTNAME unset or _FAKE_), hardware tests
    are skipped, except those marked simulation. Select the tests to run with
    -m hardware (board tests) or -m "not hardware or simulation" (no board).
    """
    real_board = _real_board()
    skip = pytest.mark.skip(reason="needs a real Red Pitaya: set REDPITAYA_HOSTNAME")
    for item in items:
        if "hardware_session" not in item.fixturenames:
            continue
        item.add_marker(pytest.mark.hardware)
        if not real_board and item.get_closest_marker("simulation") is None:
            item.add_marker(skip)


def _session_mode(items):
    """Returns (full Pyrpl app needed, source config file) for the tests to run."""
    files = {
        item.fspath.basename
        for item in items
        if "hardware_session" in item.fixturenames and item.get_closest_marker("skip") is None
    }
    require_full_pyrpl = any(name not in LIGHT_TEST_FILES for name in files)
    if "test_attribute.py" in files:
        source_config_file = "nosetests_source_dummy_module.yml"
    elif "test_lockbox.py" in files:
        source_config_file = "nosetests_source_lockbox.yml"
    else:
        source_config_file = "nosetests_source.yml"
    return require_full_pyrpl, source_config_file


def _apply_keepalive(rp_object):
    """Helper to apply the GitHub Actions/NAT fix to any RedPitaya object"""
    if not hasattr(rp_object, "ssh"):
        return  # simulated Red Pitaya: no connection to keep alive

    # 1. SSH Transport KeepAlive
    try:
        if hasattr(rp_object.ssh, "scp") and hasattr(rp_object.ssh.scp, "transport"):
            rp_object.ssh.scp.transport.set_keepalive(30)
            logger.info("SSH KeepAlive enabled (30s).")
    except (AttributeError, OSError, RuntimeError) as e:
        logger.warning(f"SSH KeepAlive failed: {e}")

    # 2. Socket KeepAlive
    try:
        sock = rp_object.client
        if not hasattr(sock, "setsockopt") and hasattr(sock, "socket"):
            sock = sock.socket

        if hasattr(sock, "setsockopt"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Linux/macOS specific
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            if hasattr(socket, "TCP_KEEPINTVL"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            if hasattr(socket, "TCP_KEEPCNT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
            logger.info("Socket (Port 2222) KeepAlive enabled.")
        else:
            logger.warning("Could not enable Socket KeepAlive: setsockopt method missing.")
    except (AttributeError, OSError, RuntimeError) as e:
        logger.warning(f"Error setting Socket KeepAlive: {e}")

    # ---------------------------------------------------------


@pytest.fixture(scope="session")
def hardware_session(request):
    """
    Creates either a full Pyrpl instance OR just a RedPitaya instance
    depending on the test requirements.

    The session is only created when a selected test uses it, so tests that
    do not need a Red Pitaya never connect to one.
    """
    require_full_pyrpl, source_config_file = _session_mode(request.session.items)
    pyrpl_obj = None
    rp_obj = None
    tmp_file = "nosetests_config.yml"
    tmp_conf = os.path.join(user_config_dir, tmp_file)

    # Cleanup start
    if os.path.isfile(tmp_conf):
        with contextlib.suppress(OSError):
            os.remove(tmp_conf)

    if require_full_pyrpl:
        # --- HEAVY PATH ---
        logger.info(f"Initializing Full Pyrpl with source: {source_config_file}")
        pyrpl_obj = Pyrpl(config=tmp_file, source=source_config_file, reloadfpga=True)
        rp_obj = pyrpl_obj.rp
    else:
        # --- LIGHT PATH ---
        logger.info("Initializing Light RedPitaya (No Pyrpl App config)")
        # This uses environment variables or defaults defined in RedPitaya class
        # Assuming 'hostname' is handled by RedPitaya's internal logic checking env vars
        rp_obj = RedPitaya(config=None, autostart=True, reloadfpga=True)

    # --- APPLY FIXES ---
    _apply_keepalive(rp_obj)

    # --- TIMING ---
    # We allow 'r.hk.led' to act as a warmup and timing test
    N = 10
    t0 = time()
    for _i in range(N):
        _ = rp_obj.hk.led
    read_time = (time() - t0) / float(N)

    t0 = time()
    for _i in range(N):
        rp_obj.hk.led = 0
    write_time = (time() - t0) / float(N)

    print(f"Est. Read/Write: {read_time * 1000.0:.1f} ms / {write_time * 1000.0:.1f} ms")
    _check_session(read_time, write_time, pyrpl_obj, require_full_pyrpl)

    # Yield the container
    yield HardwareSession(rp=rp_obj, pyrpl=pyrpl_obj, read_time=read_time, write_time=write_time)

    # --- TEARDOWN ---
    logger.info("Tearing down hardware session...")
    if pyrpl_obj:
        with contextlib.suppress(AttributeError, OSError, RuntimeError):
            pyrpl_obj._clear()
    else:
        # If we only made the RP, we close it manually
        with contextlib.suppress(AttributeError, OSError, RuntimeError):
            rp_obj.end_all()

    sleep(0.2)
    if os.path.isfile(tmp_conf):
        with contextlib.suppress(OSError):
            os.remove(tmp_conf)

    # Wait for file to be fully deleted
    max_attempts = 10
    for _ in range(max_attempts):
        if not os.path.exists(tmp_conf):
            break
        sleep(0.1)


def _check_session(read_time, write_time, pyrpl, require_full_pyrpl):
    """Hardware sanity check, run once when the session is created."""
    logger.info("Running session sanity checks...")

    try:
        maxtime = global_config.test.max_communication_time
    except (AttributeError, KeyError, TypeError):
        pytest.exit(
            "Error with global config file. Delete global_config.yml and retry!",
            returncode=1,
        )

    if read_time >= maxtime:
        pytest.exit(
            f"Read operation too slow: {read_time:e}s (expected < {maxtime:e}s)",
            returncode=1,
        )

    if write_time >= maxtime:
        pytest.exit(
            f"Write operation too slow: {write_time:e}s (expected < {maxtime:e}s)",
            returncode=1,
        )

    if pyrpl is None and require_full_pyrpl:
        pytest.exit("Pyrpl instance was not created!", returncode=1)

    logger.info("Hardware sanity checks passed.")
