"""TEXAS revision-1 analysis workflow.

Reusable, tested building blocks for the reviewer-requested reruns, grouped by
the review triage:

- ``metrics`` / ``intervals`` (Group A): report diagnostics, noise terms, and
  R2/RMSE **credible intervals** from existing forward posteriors (no refit).
- ``io``: persist every result to disk as NetCDF/CSV with provenance.

Cross-validation (Group C) and sensitivity refits (Group B) build on these and
are added as ``crossval`` / ``sensitivity``.
"""
from __future__ import annotations

from .intervals import LEVELS, credible_interval, format_ci
from .io import list_results, load_result, results_root, save_result
from .metrics import (
    CALIBRATION_METRICS,
    OBSERVATION_NOISE,
    POOLING_NOISE,
    diagnostics_table,
    summarize_calibration_metrics,
    summarize_noise_terms,
)

__all__ = [
    "credible_interval",
    "format_ci",
    "LEVELS",
    "save_result",
    "load_result",
    "list_results",
    "results_root",
    "summarize_calibration_metrics",
    "summarize_noise_terms",
    "diagnostics_table",
    "CALIBRATION_METRICS",
    "OBSERVATION_NOISE",
    "POOLING_NOISE",
]
