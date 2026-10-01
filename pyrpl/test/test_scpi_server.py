"""Tests of the read-only SCPI server, run natively with a simulated memory map.

The server is compiled with the host gcc and started with -m, which maps a
regular file instead of /dev/mem: the HK block (0x1000 bytes) followed by the
DSP block (0x100000 bytes). The tests write register values into that file.
"""

import mmap
import os
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from ..hardware_modules.dsp import DSP_INPUTS
from ..scpi_client import ScpiClient, ScpiError

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("gcc") is None,
    reason="the SCPI server needs a POSIX host with gcc",
)

SOURCE = Path(__file__).parents[1] / "monitor_server" / "pyrpl_scpi_server.c"
HK_SIZE = 0x1000
DSP_SIZE = 0x100000
HK_EXP_P_DIR, HK_EXP_P_IN, HK_EXP_N_IN = 0x10, 0x20, 0x24


class FakeMemory:
    def __init__(self, path):
        with open(path, "wb") as f:
            f.truncate(HK_SIZE + DSP_SIZE)
        self.file = open(path, "r+b")  # noqa: SIM115 - closed by the fixture
        self.map = mmap.mmap(self.file.fileno(), HK_SIZE + DSP_SIZE)

    def write(self, offset, value):
        self.map[offset : offset + 4] = struct.pack("<I", value & 0xFFFFFFFF)

    def set_signal(self, name, raw):
        self.write(HK_SIZE + DSP_INPUTS[name] * 0x10000 + 0x10, raw & 0x3FFF)

    def set_pin(self, pin, side, state):
        offset = HK_EXP_P_IN if side == "P" else HK_EXP_N_IN
        current = struct.unpack("<I", self.map[offset : offset + 4])[0]
        mask = 1 << pin
        self.write(offset, current | mask if state else current & ~mask)

    def close(self):
        self.map.close()
        self.file.close()


@pytest.fixture(scope="module")
def binary(tmp_path_factory):
    path = tmp_path_factory.mktemp("scpi") / "pyrpl_scpi_server"
    subprocess.run(
        [
            "gcc",
            "-std=gnu99",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-o",
            str(path),
            str(SOURCE),
            "-lm",
        ],
        check=True,
    )
    return path


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(binary, tmp_path):
    memory = FakeMemory(tmp_path / "memory")
    port = free_port()
    signals = "in1=10,in2=11,pid0=0,iq0=5"
    process = subprocess.Popen(
        [
            str(binary),
            "-p",
            str(port),
            "-i",
            "test_profile",
            "-s",
            signals,
            "-m",
            str(tmp_path / "memory"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.1).close()
            break
        except OSError:
            time.sleep(0.02)
    else:
        process.kill()
        pytest.fail(f"server did not start: {process.stdout.read()}")
    yield memory, port
    process.terminate()
    process.wait(timeout=5)
    memory.close()


@pytest.fixture
def client(server):
    memory, port = server
    with ScpiClient("127.0.0.1", port) as c:
        yield memory, c


def test_identification(client):
    _, c = client
    assert c.idn.startswith("PYRPL,pyrpl_scpi_server,test_profile,")
    assert c.signals == ["in1", "in2", "pid0", "iq0"]


def test_values_and_scaling(client):
    memory, c = client
    memory.set_signal("in1", 8191)
    memory.set_signal("in2", -8192)
    memory.set_signal("pid0", 0x1000)
    assert c.values("in1") == pytest.approx(1.0)
    assert c.values("in2") == pytest.approx(-8192 / 8191)
    np.testing.assert_allclose(c.values("pid0", "in1"), [4096 / 8191, 1.0], rtol=1e-5)
    np.testing.assert_array_equal(c.raw("in1", "in2", "pid0"), [8191, -8192, 4096])
    # upper register bits are not part of the signal
    memory.write(HK_SIZE + DSP_INPUTS["iq0"] * 0x10000 + 0x10, 0xFFFF0005)
    assert c.raw("iq0") == 5


def test_scpi_syntax(client):
    memory, c = client
    memory.set_signal("in1", 100)
    assert c.ask(":signal:raw? IN1") == "100"
    assert c.ask("SIGNAL:RAW? in1;*IDN?").split(";")[0] == "100"


def test_errors(client):
    _, c = client
    with pytest.raises(ScpiError, match="Unknown signal"):
        c.values("in3")
    with pytest.raises(ScpiError, match="Undefined header"):
        c.ask("SIG:WRITE? in1")
    # signals that are not in the profile list cannot be read
    with pytest.raises(ScpiError):
        c.values("asg0")
    c.write("TRIG:SOUR DIO9_P")
    with pytest.raises(ScpiError, match="Trigger source"):
        c.check_error()
    assert c.ask("SYST:ERR?") == '0,"No error"'
    # the connection is still in sync
    assert c.values("in1") == 0


def test_stats(client):
    memory, c = client
    memory.set_signal("in1", 8191)
    memory.set_signal("in2", -8191)
    stats = c.stats(0.01, "in1", "in2")
    np.testing.assert_allclose(stats, [[1, 0, 1, 1], [-1, 0, -1, -1]], atol=1e-6)


def test_untriggered_acquisition(client):
    memory, c = client
    memory.set_signal("in1", 8191)
    t, (in1, pid0) = c.acquire(50, 1e-3, "in1", "pid0")
    assert t.shape == in1.shape == pid0.shape == (50,)
    np.testing.assert_allclose(in1, 1.0)
    np.testing.assert_allclose(np.diff(t), 1e-3, atol=5e-4)


def test_triggered_acquisition(client):
    memory, c = client
    memory.set_pin(3, "N", 0)
    c.set_trigger("DIO3_N", edge="rising", timeout=5.0, delay=2e-3)
    assert c.ask("TRIG:SOUR?") == "DIO3_N"
    assert c.ask("TRIG:EDGE?") == "RISING"

    def fire():
        time.sleep(0.2)
        memory.set_signal("in1", 4000)
        memory.set_pin(3, "N", 1)

    thread = threading.Thread(target=fire)
    start = time.monotonic()
    thread.start()
    t, (in1,) = c.acquire(10, 1e-3, "in1")
    thread.join()
    assert time.monotonic() - start >= 0.2
    assert t[0] == pytest.approx(2e-3, abs=1e-3)
    np.testing.assert_allclose(in1, 4000 / 8191)


def test_trigger_timeout(client):
    memory, c = client
    memory.set_pin(0, "P", 0)
    c.set_trigger("DIO0_P", timeout=0.1)
    with pytest.raises(ScpiError, match="Trigger timeout"):
        c.acquire(1, 0, "in1")
    c.set_trigger(None)
    assert c.ask("TRIG:SOUR?") == "NONE"
    assert c.acquire(1, 0, "in1")[1].shape == (1, 1)


def test_digital_pins(client):
    memory, c = client
    memory.set_pin(5, "P", 1)
    assert c.pin("DIO5_P") == 1
    assert c.pin("DIO5_N") == 0
    assert c.ask("DIG:PIN:DIR? DIO5_P") == "IN"
    memory.write(HK_EXP_P_DIR, 1 << 5)
    assert c.ask("DIG:PIN:DIR? DIO5_P") == "OUT"


def test_clients_are_independent(server):
    """A client waiting for a trigger does not block another one."""
    memory, port = server
    memory.set_signal("in2", 1234)
    with ScpiClient("127.0.0.1", port) as waiting, ScpiClient("127.0.0.1", port) as other:
        waiting.set_trigger("DIO1_P", timeout=2.0)
        waiting.write("SIG:ACQ? 1,0,in1")
        assert other.raw("in2") == 1234
        assert other.ask("TRIG:SOUR?") == "NONE"  # settings are per connection
        time.sleep(0.1)  # let the first server process start waiting for the edge
        memory.set_pin(1, "P", 1)
        assert len(waiting._readline(5).split(",")) == 2


def test_server_never_writes(client, tmp_path):
    memory, c = client
    before = bytes(memory.map)
    c.values("in1", "in2")
    c.stats(0.001, "in1")
    c.acquire(5, 0, "pid0")
    assert bytes(memory.map) == before
    assert os.path.getsize(tmp_path / "memory") == HK_SIZE + DSP_SIZE
