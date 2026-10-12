"""Tests of the SignalPlotter module with its simulated data source."""

import logging

import numpy as np

from ..async_utils import sleep
from ..curvedb import CurveDB
from ..software_modules.signal_plotter import SignalPlotter, _SimulatedSource
from .test_base import TestPyrpl

logger = logging.getLogger(name=__name__)


class FailingSource(_SimulatedSource):
    def acquire(self, n, interval, channels):
        raise ConnectionError("server unreachable")


class TestSignalPlotter(TestPyrpl):
    def make_plotter(self, source=_SimulatedSource, **settings):
        plotter = SignalPlotter(self.pyrpl, name="signalplotter_test")
        # the simulated source also on hardware: the tests check the module,
        # not the SCPI server (see test_scpi_server.py)
        plotter._make_source = source
        for name, value in settings.items():
            setattr(plotter, name, value)
        return plotter

    def wait_for(self, condition, timeout=5.0):
        for _ in range(int(timeout / 0.05)):
            if condition():
                return True
            sleep(0.05)
        return condition()

    def test_channels_are_validated(self):
        plotter = self.make_plotter()
        try:
            plotter.channels = ["in2", "not_a_signal", "in1", "in2"]
            assert plotter.channels == ["in2", "in1"]
            assert set(plotter.channels) <= set(plotter.signal_options)
            assert "off" not in plotter.signal_options
        finally:
            plotter._clear()

    def test_continuous(self):
        plotter = self.make_plotter(
            channels=["in1", "in2"], mode="continuous", interval=0.01, duration=0.6
        )
        curves = []
        try:
            plotter.start()
            assert plotter.running
            assert self.wait_for(lambda: len(plotter.times) > 0 and plotter.times[-1] > 1.0)
            plotter.stop()
            assert not plotter.running
            t = plotter.times
            assert set(plotter.data) == {"in1", "in2"}
            assert all(len(v) == len(t) for v in plotter.data.values())
            assert np.all(np.diff(t) > 0)
            # only the last `duration` seconds are kept
            assert t[-1] - t[0] <= 0.6 + 1e-9
            np.testing.assert_allclose(np.median(np.diff(t)), 0.01, rtol=0.2)

            curves = plotter.save_curve()
            assert [c.params["channel"] for c in curves] == ["in1", "in2"]
            np.testing.assert_allclose(curves[0].data[0], t)
            assert [child.pk for child in curves[0].childs] == [curves[1].pk]
        finally:
            plotter._clear()
            if curves:
                curves[0].delete()  # also deletes its children

    def test_settings_restart_and_clear(self):
        plotter = self.make_plotter(channels=["in1"], interval=0.01)
        try:
            plotter.start()
            assert self.wait_for(lambda: len(plotter.times) > 0)
            plotter.channels = ["in1", "out1"]  # restarts with the new channels
            assert plotter.running
            assert self.wait_for(lambda: "out1" in plotter.data and len(plotter.times) > 0)
            plotter.stop()
            plotter.clear()
            assert len(plotter.times) == 0
        finally:
            plotter._clear()

    def test_triggered_blocks(self):
        plotter = self.make_plotter(
            channels=["in1"], mode="triggered", interval=0.001, points=50, trigger_delay=0.002
        )
        try:
            plotter.start()
            assert plotter.status.startswith("waiting for rising edge on DIO0_P")
            assert self.wait_for(lambda: len(plotter.times) == 50)
            plotter.stop()
            # time relative to the edge, centre of each averaging interval
            np.testing.assert_allclose(plotter.times[0], 0.002 + 0.0005)
            np.testing.assert_allclose(np.diff(plotter.times), 0.001)
        finally:
            plotter._clear()

    def test_errors_stop_the_acquisition(self):
        plotter = self.make_plotter(source=FailingSource, channels=["in1"])
        try:
            plotter.start()
            assert self.wait_for(lambda: not plotter.running)
            assert plotter.status == "error: ConnectionError: server unreachable"
        finally:
            plotter._clear()

    def test_save_without_data(self):
        plotter = self.make_plotter()
        try:
            n_curves = len(CurveDB.all())
            assert plotter.save_curve() == []
            assert len(CurveDB.all()) == n_curves
        finally:
            plotter._clear()
