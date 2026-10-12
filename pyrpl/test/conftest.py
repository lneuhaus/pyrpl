# conftest.py - pytest automatically discovers fixtures from this file
import contextlib
import logging
import os
import socket
from collections import namedtuple
from shutil import copyfile

import pytest

from .. import Pyrpl, RedPitaya, global_config
from ..async_utils import sleep
from ..directories import default_config_dir, user_config_dir
from ..pyrpl_utils import time

logger = logging.getLogger(name=__name__)


def pytest_report_header(config):
    """Make Qt/NumPy differences visible in hardware-test diagnostics."""
    import numpy as np
    import qtpy

    return f"PyRPL runtime: Qt={qtpy.API_NAME}, NumPy={np.__version__}"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_fpga(*capabilities): skip unless the selected FPGA profile provides them",
    )


# Global state to determine what we need to build
_source_config_file = "nosetests_source.yml"
_require_full_pyrpl = False

# A container to standardize what the fixture returns
# rp is always present; pyrpl is None if running in light mode
HardwareSession = namedtuple("HardwareSession", ["rp", "pyrpl", "read_time", "write_time"])


def _test_target_overrides():
    """Return environment-selected hardware target as explicit constructor options.

    RedPitaya deliberately gives persisted configuration values priority over
    environment variables.  The pytest source configuration contains a fake
    hostname, however, so tests must forward their target selection as explicit
    constructor arguments (the highest-priority configuration source).
    """
    environment_options = {
        "hostname": "REDPITAYA_HOSTNAME",
        "fpga_profile": "REDPITAYA_FPGA_PROFILE",
    }
    return {
        option: os.environ[variable]
        for option, variable in environment_options.items()
        if variable in os.environ
    }


def _reset_test_source_config(source_name):
    """Restore a user-side test source from its packaged template."""
    packaged_source = os.path.join(default_config_dir, source_name)
    user_source = os.path.join(user_config_dir, source_name)
    copyfile(packaged_source, user_source)
    return packaged_source


def pytest_collection_modifyitems(session, config, items):
    """
    Hook called after test collection.
    Determines if we need the full Pyrpl app or just the RedPitaya driver.
    """
    global _source_config_file
    global _require_full_pyrpl

    found_attribute = False
    found_lockbox = False
    found_heavy_test = False

    for item in items:
        test_file = item.fspath.basename

        # If we find any file that ISN'T TestRedpitaya, we assume we need full Pyrpl

        if test_file not in [
            "test_redpitaya.py",
            "test_pyqtgraph_benchmark.py",
            "test_registers.py",
            "test_scpi_redpitaya.py",
            "test_scpi_server.py",
        ]:
            found_heavy_test = True

        if test_file == "test_attribute.py":
            found_attribute = True
        elif test_file == "test_lockbox.py":
            found_lockbox = True

    _require_full_pyrpl = found_heavy_test

    # Config selection logic
    if found_attribute:
        _source_config_file = "nosetests_source_dummy_module.yml"
    elif found_lockbox:
        _source_config_file = "nosetests_source_lockbox.yml"

    mode = "FULL PYRPL APP" if _require_full_pyrpl else "LIGHT REDPITAYA DRIVER"
    logger.info(f"Test Collection Complete. Mode: {mode}")


def _apply_keepalive(rp_object):
    """Helper to apply the GitHub Actions/NAT fix to any RedPitaya object"""
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
def hardware_session():
    """
    Creates either a full Pyrpl instance OR just a RedPitaya instance
    depending on the test requirements.
    """
    pyrpl_obj = None
    rp_obj = None
    tmp_file = "nosetests_config.yml"
    tmp_conf = os.path.join(user_config_dir, tmp_file)
    target_overrides = _test_target_overrides()
    source_template = _reset_test_source_config(_source_config_file)

    # Cleanup start
    if os.path.isfile(tmp_conf):
        with contextlib.suppress(OSError):
            os.remove(tmp_conf)

    if _require_full_pyrpl:
        # --- HEAVY PATH ---
        logger.info(f"Initializing Full Pyrpl with source: {_source_config_file}")
        pyrpl_obj = Pyrpl(
            config=tmp_file,
            source=source_template,
            reloadfpga=True,
            **target_overrides,
        )
        rp_obj = pyrpl_obj.rp
    else:
        # --- LIGHT PATH ---
        logger.info("Initializing Light RedPitaya (No Pyrpl App config)")
        rp_obj = RedPitaya(
            config=None,
            autostart=True,
            reloadfpga=True,
            **target_overrides,
        )

    os.environ.setdefault("PYRPL_BITSTREAM_LABEL", rp_obj.fpga_profile.id)

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
    with contextlib.suppress(OSError):
        _reset_test_source_config(_source_config_file)

    # Wait for file to be fully deleted
    max_attempts = 10
    for _ in range(max_attempts):
        if not os.path.exists(tmp_conf):
            break
        sleep(0.1)


@pytest.fixture(autouse=True)
def require_fpga_capabilities(request, hardware_session):
    """Skip tests whose declared FPGA capabilities are unavailable."""
    marker = request.node.get_closest_marker("requires_fpga")
    if marker is None:
        return
    required = set(marker.args)
    missing = required - hardware_session.rp.fpga_profile.capabilities
    if missing:
        pytest.skip(
            f"FPGA profile {hardware_session.rp.fpga_profile.id!r} lacks capabilities: "
            f"{', '.join(sorted(missing))}"
        )


@pytest.fixture(scope="session", autouse=True)
def pyrpl_session_sanity(hardware_session):
    """
    Global hardware sanity check.
    Runs exactly once per pytest session, no matter what tests are selected.
    """

    logger.info("Running session sanity checks...")

    read_time = hardware_session.read_time
    write_time = hardware_session.write_time
    pyrpl = hardware_session.pyrpl

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

    if pyrpl is None and _require_full_pyrpl:
        pytest.exit("Pyrpl instance was not created!", returncode=1)

    logger.info("Hardware sanity checks passed.")
