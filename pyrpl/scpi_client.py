###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################
"""Client for the read-only PyRPL SCPI server (monitor_server/pyrpl_scpi_server.c).

The module only depends on the standard library and numpy, so that it can be
copied into another acquisition program that does not install PyRPL.

Example::

    from pyrpl.scpi_client import ScpiClient

    with ScpiClient("rp-f0xxxx.local") as rp:
        in1, pid0 = rp.values("in1", "pid0")
        rp.set_trigger("DIO0_P", edge="rising", timeout=5.0)
        t, (in1, pid0) = rp.acquire(1000, 1e-5, "in1", "pid0")
"""

import socket

import numpy as np

TERMINATION = b"\r\n"


class ScpiError(RuntimeError):
    """Raised when the server answers a query with ERR!."""


class ScpiClient:
    def __init__(self, hostname, port=5000, timeout=5.0):
        """Connects to the PyRPL SCPI server.

        timeout: socket timeout in seconds for quick queries. Triggered
        acquisitions extend it automatically by the trigger timeout and the
        acquisition duration."""
        self.timeout = timeout
        self._buffer = b""
        self._trigger_timeout = 1.0
        self._trigger_delay = 0.0
        self._averaging = False
        self.socket = socket.create_connection((hostname, port), timeout=timeout)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def close(self):
        self.socket.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # low level communication
    def write(self, command):
        self.socket.sendall(command.encode("ascii") + b"\n")

    def _readline(self, timeout):
        self.socket.settimeout(timeout)
        while TERMINATION not in self._buffer:
            chunk = self.socket.recv(65536)
            if not chunk:
                raise ConnectionError("The SCPI server closed the connection")
            self._buffer += chunk
        line, self._buffer = self._buffer.split(TERMINATION, 1)
        return line.decode("ascii")

    def ask(self, query, timeout=None):
        """Sends one query and returns its answer, raises ScpiError on ERR!."""
        self.write(query)
        answer = self._readline(self.timeout if timeout is None else timeout)
        if answer == "ERR!":
            self.write("SYST:ERR?")
            raise ScpiError(f"{query}: {self._readline(self.timeout)}")
        return answer

    def check_error(self):
        """Raises ScpiError if a command (not a query) failed."""
        error = self.ask("SYST:ERR?")
        if not error.startswith("0,"):
            raise ScpiError(error)

    # high level functions
    @property
    def idn(self):
        return self.ask("*IDN?")

    @property
    def signals(self):
        """Names of the DSP signals available in the loaded FPGA profile."""
        return self.ask("SIG:LIST?").split(",")

    @staticmethod
    def _floats(answer):
        return np.array(answer.split(","), dtype=float)

    def values(self, *signals):
        """Current values of the signals (in PyRPL units, +-1 full scale).

        The signals are read back to back, within about 1 us. Returns a float
        for a single signal, else a numpy array."""
        values = self._floats(self.ask("SIG:VAL? " + ",".join(signals)))
        return values[0] if len(signals) == 1 else values

    def raw(self, *signals):
        """Current raw 14 bit values (signed integers) of the signals."""
        values = np.array(self.ask("SIG:RAW? " + ",".join(signals)).split(","), dtype=int)
        return values[0] if len(signals) == 1 else values

    def stats(self, duration, *signals):
        """Samples the signals as fast as possible on the board for duration (s).

        Returns an array of shape (len(signals), 4) with mean, std, min, max."""
        answer = self.ask(
            f"SIG:STAT? {duration:g}," + ",".join(signals), timeout=self.timeout + duration
        )
        return self._floats(answer).reshape(len(signals), 4)

    def set_trigger(self, source=None, edge="rising", timeout=1.0, delay=0.0):
        """Configures the trigger of acquire().

        source: None (no trigger) or a digital pin "DIO0_P" ... "DIO7_N"
        edge: "rising", "falling" or "both"
        timeout: s to wait for the edge, 0 waits forever
        delay: s between the edge and the first sample"""
        self.write(
            f"TRIG:SOUR {source or 'NONE'};TRIG:EDGE {edge};TRIG:TIM {timeout:g};TRIG:DEL {delay:g}"
        )
        self.check_error()
        self._trigger_timeout = timeout
        self._trigger_delay = delay

    def set_averaging(self, on=True):
        """Makes each point of acquire() the mean of the signals over its interval.

        The board samples as fast as it can during each interval, and the
        intervals follow each other without gap. The time of a point is then
        the centre of its interval. Requires an interval > 0."""
        self.write(f"SIG:ACQ:AVER {'ON' if on else 'OFF'}")
        self.check_error()
        self._averaging = bool(on)

    def acquire(self, n, interval, *signals):
        """Acquires n points of the signals, one every interval seconds.

        Starts on the trigger edge configured with set_trigger(), immediately
        without trigger. The timing is software timed on the board: expect
        jitter of the order of a microsecond, more if Linux preempts the server.

        Returns (t, values): t has shape (n,) and holds the sample times in s
        relative to the trigger edge, values has shape (len(signals), n)."""
        duration = self._trigger_delay + interval * (n if self._averaging else n - 1)
        if self._trigger_timeout == 0:
            timeout = None  # wait forever
        else:
            timeout = self.timeout + self._trigger_timeout + duration
        answer = self.ask(f"SIG:ACQ? {n},{interval:g}," + ",".join(signals), timeout=timeout)
        data = self._floats(answer).reshape(n, len(signals) + 1)
        return data[:, 0], data[:, 1:].T

    def pin(self, pin):
        """State (0 or 1) of a digital pin "DIO0_P" ... "DIO7_N"."""
        return int(self.ask(f"DIG:PIN? {pin}"))
