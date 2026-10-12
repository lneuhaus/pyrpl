"""
Plots DSP signals over long periods, read through the read-only SCPI server.

The scope records at most 16384 points of two signals. The SignalPlotter
records any number of DSP signals at intervals from 100 us to hours, either
continuously (a strip chart of the last ``duration`` seconds) or in blocks of
``points`` points started by an edge on a digital pin.

Each point is the mean of the signal over its interval: the board samples as
fast as it can during each interval, so the curve is free of aliasing and the
intervals follow each other without gap (continuous mode leaves a gap of about
one network round trip every CHUNK_DURATION seconds).

The data is read by pyrpl_scpi_server (see the user guide), in a background
thread, so that waiting for a trigger never blocks the GUI. With a simulated
Red Pitaya (hostname _FAKE_), a simulated source produces the data.
"""

import contextlib
import queue
import socket
import threading
from time import monotonic

import numpy as np
from qtpy import QtCore

from ..attributes import BaseProperty, FloatProperty, IntProperty, SelectProperty
from ..hardware_modules.dsp import DSP_INPUTS
from ..modules import Module, SignalLauncher
from ..scpi_client import ScpiClient
from ..widgets.module_widgets.signal_plotter_widget import SignalPlotterWidget

# continuous mode reads the server in blocks of about this duration (s)
CHUNK_DURATION = 0.25
# maximum number of values (points x channels) per request to the server
MAX_REQUEST_VALUES = 1_000_000
# interval (ms) at which the GUI thread collects new data
UPDATE_INTERVAL_MS = 100
SIMULATED_HOSTNAMES = ("_FAKE_", "_FAKE_REDPITAYA_")
TRIGGER_SOURCES = [f"DIO{i}_{side}" for side in "PN" for i in range(8)]


def _available_signals(module):
    """DSP signals of the loaded FPGA profile."""
    signals = list(DSP_INPUTS)
    with contextlib.suppress(AttributeError):
        signals = list(module.pyrpl.rp.fpga_profile.hardware.get("dsp_inputs", signals))
    return [signal for signal in signals if signal != "off"]


class ChannelsProperty(BaseProperty):
    """List of the plotted DSP signals."""

    def validate_and_normalize(self, obj, value):
        if isinstance(value, str):
            value = [value]
        available = _available_signals(obj)
        channels = []
        for channel in value or []:
            if channel not in available:
                obj._logger.warning("Signal %s is not available and is ignored.", channel)
            elif channel not in channels:
                channels.append(channel)
        return channels

    def get_value(self, obj):
        return list(super().get_value(obj))


class _ScpiSource:
    """Averaged acquisitions through pyrpl_scpi_server."""

    def __init__(self, hostname, port):
        self.client = ScpiClient(hostname, port)

    def configure(self, trigger_source=None, edge="rising", delay=0.0):
        self.client.set_averaging(True)
        # timeout 0: wait for the edge until stopped
        self.client.set_trigger(trigger_source, edge=edge, timeout=0, delay=delay)

    def acquire(self, n, interval, channels):
        return self.client.acquire(n, interval, *channels)

    def abort(self):
        """Interrupts a pending acquisition from another thread."""
        with contextlib.suppress(OSError):
            self.client.socket.shutdown(socket.SHUT_RDWR)
        with contextlib.suppress(OSError):
            self.client.close()


class _SimulatedSource:
    """Stands in for the server with a simulated Red Pitaya.

    Produces a slow sine per channel plus noise, in real time; a trigger
    "arrives" 0.1 s after each acquisition request."""

    TRIGGER_WAIT = 0.1

    def __init__(self):
        self._aborted = threading.Event()
        self._triggered = False
        self._delay = 0.0
        self._start = monotonic()

    def configure(self, trigger_source=None, edge="rising", delay=0.0):
        self._triggered = trigger_source is not None
        self._delay = delay

    def acquire(self, n, interval, channels):
        t_request = monotonic()
        wait = (self.TRIGGER_WAIT if self._triggered else 0.0) + self._delay + n * interval
        if self._aborted.wait(wait):
            raise ConnectionError("acquisition aborted")
        t_zero = t_request + (self.TRIGGER_WAIT if self._triggered else 0.0)
        t = self._delay + (np.arange(n) + 0.5) * interval
        phase = 2 * np.pi * 0.1 * (t_zero + t - self._start)
        rng = np.random.default_rng()
        values = np.array(
            [
                0.5 * np.sin(phase + i) + 0.01 * rng.standard_normal(n)
                for i, _ in enumerate(channels)
            ]
        )
        return t, values

    def abort(self):
        self._aborted.set()


class _AcquisitionThread(threading.Thread):
    """Reads the source until stopped and queues the results.

    Queue items: ("continuous", t, values), ("block", t, values) or
    ("error", message). In continuous mode t is relative to the start of the
    acquisition, in triggered mode to the trigger edge."""

    def __init__(self, source, channels, mode, interval, points, trigger):
        super().__init__(name="SignalPlotter acquisition", daemon=True)
        self.source = source
        self.channels = list(channels)
        self.mode = mode
        self.interval = interval
        self.points = points
        self.trigger = trigger  # (source, edge, delay)
        self.results = queue.Queue()
        self._stop_requested = threading.Event()

    def run(self):
        try:
            if self.mode == "continuous":
                self._run_continuous()
            else:
                self._run_triggered()
        except Exception as error:  # reported to the GUI thread
            if not self._stop_requested.is_set():
                self.results.put(("error", f"{type(error).__name__}: {error}"))
        finally:
            self.source.abort()

    def _run_continuous(self):
        self.source.configure(None)
        max_points = max(1, MAX_REQUEST_VALUES // len(self.channels))
        chunk = int(min(max_points, max(1, round(CHUNK_DURATION / self.interval))))
        start = monotonic()
        while not self._stop_requested.is_set():
            t_request = monotonic() - start
            t, values = self.source.acquire(chunk, self.interval, self.channels)
            self.results.put(("continuous", t_request + t, values))

    def _run_triggered(self):
        self.source.configure(*self.trigger)
        while not self._stop_requested.is_set():
            t, values = self.source.acquire(self.points, self.interval, self.channels)
            self.results.put(("block", t, values))

    def stop(self):
        self._stop_requested.set()
        self.source.abort()


class SignalLauncherSignalPlotter(SignalLauncher):
    new_data = QtCore.Signal()  # the plotted data changed
    status_changed = QtCore.Signal(str)

    def __init__(self, module):
        super().__init__(module)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(UPDATE_INTERVAL_MS)
        self.timer.timeout.connect(module._collect_results)

    def _clear(self):
        self.timer.stop()
        super()._clear()


class SignalPlotter(Module):
    """
    Plots DSP signals over long periods, read through the SCPI server.

    - mode "continuous": strip chart of the last ``duration`` seconds.
    - mode "triggered": blocks of ``points`` points, each started by an edge
      on ``trigger_source``; the last block is shown.

    Each point is the mean of the signal over ``interval`` seconds. The SCPI
    server is started on the Red Pitaya if needed.
    """

    _widget_class = SignalPlotterWidget
    _signal_launcher = SignalLauncherSignalPlotter
    _setup_attributes = [
        "channels",
        "mode",
        "interval",
        "duration",
        "points",
        "trigger_source",
        "trigger_edge",
        "trigger_delay",
    ]
    _gui_attributes = [
        "mode",
        "interval",
        "duration",
        "points",
        "trigger_source",
        "trigger_edge",
        "trigger_delay",
        "start",
        "stop",
        "clear",
        "save_curve",
    ]

    channels = ChannelsProperty(default=["in1", "in2"], call_setup=True, doc="plotted signals")
    mode = SelectProperty(
        options=["continuous", "triggered"],
        default="continuous",
        call_setup=True,
        doc="continuous strip chart, or blocks started by a trigger edge",
    )
    interval = FloatProperty(
        min=1e-4,
        max=3600.0,
        default=0.01,
        increment=1e-4,
        log_increment=True,
        call_setup=True,
        doc="time per point (s); each point is the mean over this interval",
    )
    duration = FloatProperty(
        min=0.01,
        max=1e7,
        default=60.0,
        increment=1.0,
        log_increment=True,
        doc="continuous mode: time span kept and shown (s)",
    )
    points = IntProperty(
        min=1,
        max=MAX_REQUEST_VALUES,
        default=1000,
        call_setup=True,
        doc="triggered mode: number of points per block",
    )
    trigger_source = SelectProperty(
        options=TRIGGER_SOURCES, default="DIO0_P", call_setup=True, doc="triggered mode: pin"
    )
    trigger_edge = SelectProperty(
        options=["rising", "falling", "both"], default="rising", call_setup=True
    )
    trigger_delay = FloatProperty(
        min=0.0,
        max=3600.0,
        default=0.0,
        increment=1e-3,
        call_setup=True,
        doc="triggered mode: time between the edge and the first point (s)",
    )

    def __init__(self, parent, name=None):
        self._acquisition = None
        self.times = np.zeros(0)
        self.data = {}  # channel -> values
        self.status = "stopped"
        super().__init__(parent, name=name)

    @property
    def running(self):
        return self._acquisition is not None

    @property
    def signal_options(self):
        """DSP signals that can be plotted."""
        return _available_signals(self)

    # acquisition control
    def start(self):
        """Starts (or restarts) the acquisition, clearing the data."""
        self._stop_acquisition()
        self.clear()
        if not self.channels:
            self._set_status("no channel selected")
            return
        try:
            source = self._make_source()
        except Exception as error:
            self._set_status(f"cannot connect to the SCPI server: {error}")
            self._logger.error("SignalPlotter: %s", self.status)
            return
        self._acquisition = _AcquisitionThread(
            source,
            self.channels,
            self.mode,
            self.interval,
            self.points,
            (self.trigger_source, self.trigger_edge, self.trigger_delay),
        )
        self._acquisition.start()
        self._signal_launcher.timer.start()
        if self.mode == "continuous":
            self._set_status("running")
        else:
            self._set_status(f"waiting for {self.trigger_edge} edge on {self.trigger_source}")

    def stop(self):
        """Stops the acquisition; the data is kept."""
        was_running = self.running
        self._collect_results()  # keep what was already acquired
        self._stop_acquisition()
        if was_running:
            self._set_status("stopped")

    def clear(self):
        """Clears the recorded data."""
        self.times = np.zeros(0)
        self.data = {channel: np.zeros(0) for channel in self.channels}
        self._signal_launcher.new_data.emit()

    def save_curve(self):
        """Saves the recorded data, one curve per channel.

        The first channel is the parent curve, the others its children.
        Returns the list of curves."""
        if len(self.times) == 0:
            self._logger.warning("SignalPlotter: no data to save.")
            return []
        params = self.setup_attributes
        params["x_unit"] = "s"
        params["y_unit"] = "V"
        curves = []
        for channel, values in self.data.items():
            curve = self._save_curve(
                self.times,
                values,
                name=f"{self.name} {channel}",
                channel=channel,
                **params,
            )
            if curves:
                curves[0].add_child(curve)
            curves.append(curve)
        return curves

    def _setup(self):
        # a new setting invalidates the recorded data: restart if running
        if self.running:
            self.start()
        else:
            self.clear()

    def _make_source(self):
        rp = self.pyrpl.rp
        if rp.parameters["hostname"] in SIMULATED_HOSTNAMES or not hasattr(rp, "ssh"):
            return _SimulatedSource()
        # starts the server, or keeps it if it already runs with these settings
        rp.parameters["scpi_server"] = True
        rp.startscpiserver()
        return _ScpiSource(rp.parameters["hostname"], rp.parameters["scpi_port"])

    def _stop_acquisition(self):
        self._signal_launcher.timer.stop()
        if self._acquisition is not None:
            self._acquisition.stop()
            self._acquisition.join(timeout=5)
            self._acquisition = None

    def _set_status(self, status):
        self.status = status
        self._signal_launcher.status_changed.emit(status)

    def _collect_results(self):
        """Moves the queued results into the plotted data (GUI thread)."""
        if self._acquisition is None:
            return
        changed = False
        results = self._acquisition.results
        while True:
            try:
                kind, *payload = results.get_nowait()
            except queue.Empty:
                break
            if kind == "error":
                self._stop_acquisition()
                self._set_status(f"error: {payload[0]}")
                self._logger.error("SignalPlotter: %s", payload[0])
                break
            t, values = payload
            if kind == "block":
                self.times = t
                self.data = dict(zip(self.channels, values))
                self._set_status(f"block of {len(t)} points received, waiting for next edge")
            else:
                self._append(t, values)
            changed = True
        if changed:
            self._signal_launcher.new_data.emit()

    def _append(self, t, values):
        times = np.concatenate([self.times, t])
        keep = times >= times[-1] - self.duration
        self.times = times[keep]
        for channel, new_values in zip(self.channels, values):
            old = self.data.get(channel, np.zeros(0))
            self.data[channel] = np.concatenate([old, new_values])[keep]

    def _clear(self):
        self._stop_acquisition()
        super()._clear()
