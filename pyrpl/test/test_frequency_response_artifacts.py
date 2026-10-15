import numpy as np
import pytest

from pyrpl.test import frequency_response_artifacts
from pyrpl.test.frequency_response_artifacts import fit_residual_delay


def test_fit_residual_delay_extracts_delay_and_phase_offset():
    frequencies = np.geomspace(1e3, 10e6, 101)
    delay = 4.8e-9
    phase_offset = 0.17
    reference = 1.0 / (1.0 + 1j * frequencies / 2e6)
    measured = reference * np.exp(1j * phase_offset - 2j * np.pi * frequencies * delay)

    fit = fit_residual_delay(frequencies, measured, reference)

    assert fit["delay_seconds"] == pytest.approx(delay, rel=1e-10)
    assert fit["delay_standard_error_seconds"] == pytest.approx(0, abs=1e-20)
    assert fit["phase_offset_radians"] == pytest.approx(phase_offset, rel=1e-10)
    assert fit["r_squared"] == pytest.approx(1.0)


def test_fit_residual_delay_ignores_response_zeros():
    frequencies = np.linspace(0, 10e6, 21)
    delay = 12e-9
    reference = np.ones(frequencies.size, dtype=complex)
    measured = np.exp(-2j * np.pi * frequencies * delay)
    reference[7] = 0
    measured[7] = 1j  # Arbitrary phase at a point where theory is zero.

    fit = fit_residual_delay(frequencies, measured, reference)

    assert fit["points_used"] == frequencies.size - 1
    assert fit["delay_seconds"] == pytest.approx(delay, rel=1e-10)


def test_artifacts_are_not_saved_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PYRPL_RESPONSE_RESULTS_DIR", str(tmp_path))
    monkeypatch.setattr(frequency_response_artifacts, "SAVE_PLOT", False)
    frequencies = np.linspace(1, 10, 5)
    assert (
        frequency_response_artifacts.save_frequency_response(
            "nothing", frequencies, frequencies, frequencies
        )
        is None
    )
    assert list(tmp_path.iterdir()) == []


def test_artifacts_are_saved_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("PYRPL_RESPONSE_RESULTS_DIR", str(tmp_path))
    monkeypatch.setenv("PYRPL_BITSTREAM_LABEL", "label")
    monkeypatch.setattr(frequency_response_artifacts, "SAVE_PLOT", True)
    frequencies = np.linspace(1, 10, 5)
    stem = frequency_response_artifacts.save_frequency_response(
        "response", frequencies, frequencies, 2 * frequencies
    )
    assert stem == tmp_path / "label" / "response"
    for suffix in (".npz", ".csv", ".json", ".png"):
        assert stem.with_suffix(suffix).is_file()
