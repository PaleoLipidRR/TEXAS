"""TEXAS revision-1 analysis workflow.

Reusable, tested building blocks for the reviewer-requested reruns, grouped by
the review triage:

- ``metrics`` / ``intervals`` (Group A): report diagnostics, noise terms, and
  R2/RMSE **credible intervals** from existing forward posteriors (no refit).
- ``io``: persist every result to disk as NetCDF/CSV with provenance.
- ``crossval`` (Group C): spatially-blocked cross-validation — out-of-sample
  R2/RMSE credible intervals from leave-one-block-out refits.

Sensitivity refits (Group B) build on these and are added as ``sensitivity``.
"""
from __future__ import annotations

from .crossval import (
    CrossvalArrays,
    SpatialFold,
    assign_block_folds,
    assign_ocean_basin_folds,
    crossval_fold,
    fold_score_table,
    heldout_scores,
    make_folds,
    run_spatial_crossval,
)
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
    # Group C — spatially-blocked cross-validation
    "SpatialFold",
    "CrossvalArrays",
    "assign_block_folds",
    "assign_ocean_basin_folds",
    "make_folds",
    "heldout_scores",
    "fold_score_table",
    "run_spatial_crossval",
    "crossval_fold",
]
