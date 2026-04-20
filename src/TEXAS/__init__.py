# TEXAS/__init__.py

__version__ = "0.1.6"

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
from .stan.invT import (
    get_invT_posterior,
    predict_temperature_from_proxyObs,
    predict_temperature_from_RI,  # deprecated alias
)
from .predict import predict_proxy_from_T, predict_T_from_proxyObs, predict_RI_from_T, predict_T_from_RI  # predict_RI_from_T and predict_T_from_RI are deprecated aliases

# ─── Data builder for inverse‐T models ──────────────────────────────────
from .data.builder import build_invT_inputData, build_fwd_data, InvTConfig

# ─── Ocean property lookups ──────────────────────────────────────────────
from .data.ocean_lookup import lookup_no3_from_woa

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
    find_optimal_no3_threshold_nointercept,
)

# ─── Statistical utilities ────────────────────────────────────────────────────
from .stats import f_test, bootstrap_se

# ─── Ensemble generation ────────────────────────────────────────────────
from .ensemble.generator import generate_ensemble, generate_ensemble_auto
from .ensemble.detection import detect_model_and_params

# ─── Diagnostics utilities ─────────────────────────────────────────────
from .diagnostics import summarize_sampler_diagnostics, create_summary_table

# ─── Posterior download utilities ───────────────────────────────────────
from .utils.download import (
    download_posterior, download_posteriors, POSTERIOR_REGISTRY,
    download_training_data, TRAINING_DATA_REGISTRY,
)

# ─── Cache configuration ─────────────────────────────────────────────────
from .utils.paths import set_cache_dir

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
    "predict_temperature_from_proxyObs",
    "predict_temperature_from_RI",   # deprecated alias
    # high-level prediction API
    "predict_proxy_from_T",
    "predict_T_from_proxyObs",
    "predict_RI_from_T",             # deprecated alias
    "predict_T_from_RI",             # deprecated alias
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
    "find_optimal_no3_threshold_nointercept",
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
    "download_training_data",
    "TRAINING_DATA_REGISTRY",
    "POSTERIOR_REGISTRY",
    # cache configuration
    "set_cache_dir",
    # plotting
    "compute_sample_range",
    "compute_density_based_range",
    "compute_suffix_specific_range",
    "compute_dataset_specific_range",
    "plot_prior_distributions",
]
