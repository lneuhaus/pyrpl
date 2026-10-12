"""Save reproducible artifacts from hardware frequency-response tests."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def fit_residual_delay(frequencies, measured, reference, minimum_relative_magnitude=1e-3):
    """Fit a pure delay between a measured and reference transfer function.

    The phase of ``measured / reference`` is fitted to

    ``phase(f) = phase_offset - 2 * pi * f * delay``.

    Points close to a zero of either transfer function are excluded because
    their phase is dominated by noise.  A free phase offset prevents a
    frequency-independent phase error from biasing the fitted delay.

    Returns
    -------
    dict
        JSON-serializable fit results. ``delay_seconds`` is positive when the
        measured response lags the reference response.
    """
    frequencies = np.asarray(frequencies, dtype=float)
    measured = np.asarray(measured, dtype=complex)
    reference = np.asarray(reference, dtype=complex)
    if not (frequencies.shape == measured.shape == reference.shape):
        raise ValueError("frequencies, measured and reference must have the same shape")
    if frequencies.ndim != 1:
        raise ValueError("frequency-response arrays must be one-dimensional")
    if minimum_relative_magnitude < 0:
        raise ValueError("minimum_relative_magnitude must be non-negative")

    measured_magnitude = np.abs(measured)
    reference_magnitude = np.abs(reference)
    finite = (
        np.isfinite(frequencies)
        & np.isfinite(measured.real)
        & np.isfinite(measured.imag)
        & np.isfinite(reference.real)
        & np.isfinite(reference.imag)
    )
    if np.any(finite):
        measured_floor = minimum_relative_magnitude * np.max(measured_magnitude[finite])
        reference_floor = minimum_relative_magnitude * np.max(reference_magnitude[finite])
        valid = (
            finite
            & (measured_magnitude > measured_floor)
            & (reference_magnitude > reference_floor)
        )
    else:
        valid = finite

    if np.count_nonzero(valid) < 3:
        raise ValueError("at least three finite, non-zero response points are required")

    # Sort before unwrapping: callers normally provide increasing frequency,
    # but making that requirement explicit here avoids an incorrect phase fit.
    order = np.argsort(frequencies[valid])
    fit_frequencies = frequencies[valid][order]
    phase = np.unwrap(np.angle((measured[valid] / reference[valid])[order]))

    # Centre frequency for numerical conditioning, then convert the fitted
    # intercept back to its value at f=0.
    frequency_centre = float(np.mean(fit_frequencies))
    centred_frequency = fit_frequencies - frequency_centre
    design = np.column_stack((centred_frequency, np.ones(phase.size)))
    slope, centred_intercept = np.linalg.lstsq(design, phase, rcond=None)[0]
    fitted_phase = design @ np.array([slope, centred_intercept])
    residual = phase - fitted_phase
    total_variation = np.sum((phase - np.mean(phase)) ** 2)
    residual_variation = np.sum(residual**2)
    r_squared = 1.0 - residual_variation / total_variation if total_variation > 0 else 1.0
    delay_seconds = -float(slope) / (2.0 * np.pi)
    if phase.size > 2 and np.sum(centred_frequency**2) > 0:
        slope_standard_error = np.sqrt(
            residual_variation / (phase.size - 2) / np.sum(centred_frequency**2)
        )
        delay_standard_error_seconds = float(slope_standard_error / (2.0 * np.pi))
    else:
        delay_standard_error_seconds = float("nan")
    phase_offset = float(centred_intercept - slope * frequency_centre)

    return {
        "points_used": int(phase.size),
        "points_total": int(frequencies.size),
        "frequency_min_hz": float(fit_frequencies[0]),
        "frequency_max_hz": float(fit_frequencies[-1]),
        "delay_seconds": delay_seconds,
        "delay_nanoseconds": delay_seconds * 1e9,
        "delay_standard_error_seconds": delay_standard_error_seconds,
        "delay_standard_error_nanoseconds": delay_standard_error_seconds * 1e9,
        "phase_offset_radians": phase_offset,
        "phase_offset_degrees": phase_offset * 180.0 / np.pi,
        "phase_residual_rms_radians": float(np.sqrt(np.mean(residual**2))),
        "phase_residual_rms_degrees": float(np.sqrt(np.mean(residual**2)) * 180.0 / np.pi),
        "r_squared": float(r_squared),
    }


def _safe_name(value):
    """Return a filename-safe representation of a test or bitstream name."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_.") or "unnamed"


def _json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


def save_frequency_response(name, frequencies, measured, theory, metadata=None):
    """Save numeric data, summary statistics, and a comparison plot.

    ``PYRPL_BITSTREAM_LABEL`` selects the subdirectory used for a run, for
    example ``old`` or ``new``. ``PYRPL_RESPONSE_RESULTS_DIR`` can override
    the default ``.pyrpl_test_results/frequency_response`` output directory.
    """
    frequencies = np.asarray(frequencies, dtype=float)
    measured = np.asarray(measured, dtype=complex)
    theory = np.asarray(theory, dtype=complex)
    if not (frequencies.shape == measured.shape == theory.shape):
        raise ValueError("frequencies, measured and theory must have the same shape")

    difference = measured - theory
    absolute_error = np.abs(difference)
    denominator = np.maximum(np.abs(theory), np.finfo(float).eps)
    relative_error = absolute_error / denominator

    root = Path(
        os.environ.get(
            "PYRPL_RESPONSE_RESULTS_DIR",
            ".pyrpl_test_results/frequency_response",
        )
    )
    label = _safe_name(os.environ.get("PYRPL_BITSTREAM_LABEL", "unlabeled"))
    output_dir = root / label
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_name(name)

    summary = {
        "name": str(name),
        "bitstream_label": label,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "points": int(frequencies.size),
        "frequency_min_hz": float(np.min(frequencies)),
        "frequency_max_hz": float(np.max(frequencies)),
        "maximum_absolute_error": float(np.max(absolute_error)),
        "mean_absolute_error": float(np.mean(absolute_error)),
        "rms_absolute_error": float(np.sqrt(np.mean(absolute_error**2))),
        "maximum_relative_error": float(np.max(relative_error)),
        "mean_relative_error": float(np.mean(relative_error)),
        "rms_relative_error": float(np.sqrt(np.mean(relative_error**2))),
        "metadata": metadata or {},
    }

    np.savez_compressed(
        output_dir / f"{stem}.npz",
        frequency_hz=frequencies,
        measured=measured,
        theory=theory,
        difference=difference,
        absolute_error=absolute_error,
        relative_error=relative_error,
    )
    columns = np.column_stack(
        (
            frequencies,
            measured.real,
            measured.imag,
            np.abs(measured),
            np.unwrap(np.angle(measured)) * 180.0 / np.pi,
            theory.real,
            theory.imag,
            np.abs(theory),
            np.unwrap(np.angle(theory)) * 180.0 / np.pi,
            difference.real,
            difference.imag,
            absolute_error,
            relative_error,
        )
    )
    np.savetxt(
        output_dir / f"{stem}.csv",
        columns,
        delimiter=",",
        header=(
            "frequency_hz,measured_real,measured_imag,measured_magnitude,"
            "measured_phase_deg,theory_real,theory_imag,theory_magnitude,"
            "theory_phase_deg,difference_real,difference_imag,"
            "absolute_error,relative_error"
        ),
        comments="",
    )
    with (output_dir / f"{stem}.json").open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True, default=_json_default)

    # Use the object-oriented Agg canvas so saving plots does not select a
    # global matplotlib backend or interfere with Qt-based tests.
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(9, 10), constrained_layout=True)
    FigureCanvasAgg(figure)
    magnitude_axis, phase_axis, error_axis = figure.subplots(3, 1, sharex=True)
    magnitude_axis.plot(frequencies, np.abs(measured), label="measured")
    magnitude_axis.plot(frequencies, np.abs(theory), "--", label="theory")
    magnitude_axis.set_ylabel("Magnitude")
    magnitude_axis.grid(True, which="both")
    magnitude_axis.legend()

    phase_axis.plot(
        frequencies,
        np.unwrap(np.angle(measured)) * 180.0 / np.pi,
        label="measured",
    )
    phase_axis.plot(
        frequencies,
        np.unwrap(np.angle(theory)) * 180.0 / np.pi,
        "--",
        label="theory",
    )
    phase_axis.set_ylabel("Phase (degrees)")
    phase_axis.grid(True, which="both")
    phase_axis.legend()

    error_axis.plot(frequencies, absolute_error, label="absolute error")
    error_axis.plot(frequencies, relative_error, label="relative error")
    error_axis.set_xlabel("Frequency (Hz)")
    error_axis.set_ylabel("Difference")
    error_axis.grid(True, which="both")
    error_axis.legend()
    if frequencies.size > 2 and np.all(frequencies > 0):
        magnitude_axis.set_xscale("log")
        phase_axis.set_xscale("log")
        error_axis.set_xscale("log")
    figure.suptitle(f"{name} ({label})")
    figure.savefig(output_dir / f"{stem}.png", dpi=150)

    return output_dir / stem
