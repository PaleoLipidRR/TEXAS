# TEXAS/plotting/__init__.py

from .range_utils import (
    compute_sample_range,
    compute_density_based_range,
    compute_suffix_specific_range,
    compute_dataset_specific_range,
)
from .prior_plot import plot_prior_distributions
from .residual_maps import (
    plot_residual_maps,
    krige_halo_all,
    make_true_grid,
    load_or_build_halo_cache,
    load_or_build_grids_cache,
)

# Deprecated alias — use plot_residual_maps instead
plot_proxy_residual_maps = plot_residual_maps

__all__ = [
    "compute_sample_range",
    "compute_density_based_range",
    "compute_suffix_specific_range",
    "compute_dataset_specific_range",
    "plot_prior_distributions",
    "plot_residual_maps",
    "plot_proxy_residual_maps",
    "krige_halo_all",
    "make_true_grid",
    "load_or_build_halo_cache",
    "load_or_build_grids_cache",
]
