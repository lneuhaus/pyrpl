"""Tests of the SCPI server management in RedPitaya, with a fake ssh shell."""

import hashlib
import logging
from pathlib import Path

import pytest

from ..fpga_profiles import get_fpga_profile
from ..redpitaya import RedPitaya, defaultparameters

BINARY = Path(__file__).parents[1] / "monitor_server" / "pyrpl_scpi_server"


class FakeSsh:
    def __init__(self, running_cmdline="", remote_md5=""):
        self.running_cmdline = running_cmdline
        self.remote_md5 = remote_md5
        self.commands = []

    def ask(self, question=""):
        self.commands.append(question)
        if question.startswith("cat /proc/"):
            return question + "\r\n" + self.running_cmdline + "\r\nroot@rp:~# "
        if question.startswith("md5sum"):
            return self.remote_md5
        if question.startswith("nohup "):
            # the server starts with the requested command line
            self.running_cmdline = question[len("nohup ") :].split(" > ")[0] + " "
        if question.startswith("killall pyrpl_scpi_server"):
            self.running_cmdline = ""
        return ""


def make_redpitaya(ssh, profile="no_iir", **parameters):
    rp = RedPitaya.__new__(RedPitaya)
    rp.parameters = dict(defaultparameters, hostname="rp", delay=0, **parameters)
    rp.fpga_profile = get_fpga_profile(profile)
    rp.logger = logging.getLogger(__name__)
    rp.ssh = ssh
    rp.uploads = []
    rp.put_file = lambda source, destination: rp.uploads.append((source, destination))
    return rp


def local_md5():
    return hashlib.md5(BINARY.read_bytes()).hexdigest()


def test_binary_is_packaged():
    # ELF, 32 bit, little endian, ARM
    header = BINARY.read_bytes()[:20]
    assert header[:6] == b"\x7fELF\x01\x01"
    assert header[18] == 0x28


def test_command_lists_profile_signals():
    rp = make_redpitaya(FakeSsh(), scpi_port=5025)
    command = rp._scpi_server_command()
    assert command.startswith("//opt//pyrpl//pyrpl_scpi_server -p 5025 -i no_iir -s ")
    signals = dict(item.split("=") for item in command.split(" -s ")[1].split(","))
    assert signals["in1"] == "10"
    assert signals["pid0"] == "0"
    assert signals["iq2_2"] == "14"
    assert "iir" not in signals  # not part of the no_iir profile


def test_disabled_by_default():
    ssh = FakeSsh()
    rp = make_redpitaya(ssh)
    assert rp.parameters["scpi_server"] is False
    rp.startscpiserver()
    assert ssh.commands == []


def test_start_installs_and_starts():
    ssh = FakeSsh(remote_md5="0" * 32)
    rp = make_redpitaya(ssh, scpi_server=True)
    rp.startscpiserver()
    assert rp.uploads == [(str(BINARY), "//opt//pyrpl//pyrpl_scpi_server")]
    assert "systemctl stop redpitaya_scpi 2>/dev/null" in ssh.commands
    started = [c for c in ssh.commands if c.startswith("nohup ")]
    assert len(started) == 1
    assert rp._scpi_server_command() in started[0]
    assert started[0].endswith("&")


def test_running_server_is_kept():
    """A new PyRPL session must not drop the connections of other programs."""
    rp = make_redpitaya(FakeSsh(remote_md5=local_md5()), scpi_server=True)
    rp.ssh.running_cmdline = rp._scpi_server_command() + " "
    rp.startscpiserver()
    assert rp.uploads == []
    assert not any(c.startswith(("nohup", "killall")) for c in rp.ssh.commands)


@pytest.mark.parametrize("change", [{"scpi_port": 5001}, {"profile": "default"}])
def test_server_with_other_settings_is_restarted(change):
    old = make_redpitaya(FakeSsh())
    cmdline = old._scpi_server_command() + " "
    profile = change.pop("profile", "no_iir")
    rp = make_redpitaya(
        FakeSsh(running_cmdline=cmdline, remote_md5=local_md5()),
        profile=profile,
        scpi_server=True,
        **change,
    )
    rp.startscpiserver()
    assert rp.ssh.commands.index("killall pyrpl_scpi_server 2>/dev/null") < next(
        i for i, c in enumerate(rp.ssh.commands) if c.startswith("nohup ")
    )
