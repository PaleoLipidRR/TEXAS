# TEXAS/__init__.py

__version__ = "0.1.0"

# ─── Stan interface ──────────────────────────────────────────────────────
from .stan.compiler import StanCompiler
from .stan.sampler import (
    StanSampler,
    get_posterior,
    get_invT_posterior,
)
from .stan.io import (
    load_posterior,
    save_posterior,
    save_invT_posterior,
)

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
)

# ─── Ensemble generation ────────────────────────────────────────────────
from .ensemble.generator import generate_ensemble, generate_ensemble_auto
from .ensemble.detection import detect_model_and_params

# ─── Diagnostics utilities ─────────────────────────────────────────────
from .diagnostics import summarize_sampler_diagnostics, create_summary_table

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
    # stan
    "StanCompiler",
    "StanSampler",
    "get_posterior",
    "get_invT_posterior",
    "load_posterior",
    "save_posterior",
    "save_invT_posterior",
    # data builder
    "build_invT_inputData",
    "InvTConfig",
    # models
    "logistic",
    "logistic_fixed_upper",
    "inverse_logistic_fixed_upper",
    "generalized_logistic_model",
    "generalized_logistic_fixed_upper",
    "generalized_logistic_multivariate",
    "simple_logistic_model_fixed_upper_multivariate",
    # ensemble
    "generate_ensemble",
    "generate_ensemble_auto",
    "detect_model_and_params",
    # diagnostics
    "summarize_sampler_diagnostics",
    "create_summary_table",
    # plotting
    "compute_sample_range",
    "compute_density_based_range",
    "compute_suffix_specific_range",
    "compute_dataset_specific_range",
    "plot_prior_distributions",
]
