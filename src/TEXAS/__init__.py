# TEXAS/__init__.py

__version__ = "0.1.2"

# ─── Stan interface ──────────────────────────────────────────────────────
from .stan.compiler import StanCompiler
from .stan.sampler import (
    StanSampler,
    get_posterior,
    sampler_invT_posterior,
)
from .stan.io import (
    load_posterior,
    save_posterior,
    save_invT_posterior,
)
from .stan.invT import get_invT_posterior, predict_temperature_from_RI
from .predict import predict_RI_from_T, predict_T_from_RI

# ─── Data builder for inverse‐T models ──────────────────────────────────
from .data.builder import build_invT_inputData, InvTConfig

# ─── Pure-Python logistic helpers ───────────────────────────────────────
from .models.logistics import (
    logistic,
    logistic_fixed_upper,
    inverse_logistic_fixed_upper,
    generalized_logistic,
    generalized_logistic_fixed_upper,
)
from .models.multivariate import (
    generalized_logistic_fixed_upper_multivariate,
    simple_logistic_fixed_upper_multivariate,
    find_optimal_no3_threshold,
)

# ─── Statistical utilities ────────────────────────────────────────────────────
from .stats import f_test, bootstrap_se

# ─── Ensemble generation ────────────────────────────────────────────────
from .ensemble.generator import generate_ensemble, generate_ensemble_auto
from .ensemble.detection import detect_model_and_params

# ─── Diagnostics utilities ─────────────────────────────────────────────
from .diagnostics import summarize_sampler_diagnostics, create_summary_table

# ─── Posterior download utilities ───────────────────────────────────────
from .utils.download import download_posterior, download_posteriors, POSTERIOR_REGISTRY

# ─── Plotting / dataviz ─────────────────────────────────────────────────
from .plotting import (
    compute_sample_range,
    compute_density_based_range,
    compute_suffix_specific_range,
    compute_dataset_specific_range,
    plot_prior_distributions,
)

__all__ = [
    # version
    "__version__",
    # stan — calibration
    "StanCompiler",
    "StanSampler",
    "get_posterior",
    "load_posterior",
    "save_posterior",
    "save_invT_posterior",
    # stan — inverse temperature
    "get_invT_posterior",
    "predict_temperature_from_RI",
    # high-level prediction API
    "predict_RI_from_T",
    "predict_T_from_RI",
    # data builder
    "build_invT_inputData",
    "InvTConfig",
    # models — logistic curves
    "logistic",
    "logistic_fixed_upper",
    "inverse_logistic_fixed_upper",
    "generalized_logistic",
    "generalized_logistic_fixed_upper",
    "generalized_logistic_fixed_upper_multivariate",
    "simple_logistic_fixed_upper_multivariate",
    "find_optimal_no3_threshold",
    # stats
    "f_test",
    "bootstrap_se",
    # ensemble
    "generate_ensemble",
    "generate_ensemble_auto",
    "detect_model_and_params",
    # diagnostics
    "summarize_sampler_diagnostics",
    "create_summary_table",
    # download utilities
    "download_posterior",
    "download_posteriors",
    "POSTERIOR_REGISTRY",
    # plotting
    "compute_sample_range",
    "compute_density_based_range",
    "compute_suffix_specific_range",
    "compute_dataset_specific_range",
    "plot_prior_distributions",
]
