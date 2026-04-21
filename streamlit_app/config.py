import os
import warnings
from pathlib import Path

# Resolve cache dirs: env vars take priority (set by docker-compose.yml),
# then fall back to TEXAS package paths (suppressing the CmdStan-not-found
# warning since CmdStan is not installed in the Streamlit container).
def _resolve_cache_dirs():
    inv_env = os.environ.get("TEXAS_INV_CACHE")
    fwd_env = os.environ.get("TEXAS_FWD_CACHE")
    if inv_env and fwd_env:
        return inv_env, fwd_env

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from TEXAS.utils.paths import POSTERIOR_CACHE_DIR, INVT_CACHE_DIR
        return str(INVT_CACHE_DIR), str(POSTERIOR_CACHE_DIR)
    except Exception:
        pass

    # Local fallback (running outside Docker without env vars)
    return (
        "data/cache/TEXAS_invT_posterior_cache",
        "data/cache/TEXAS_posterior_cache",
    )

INV_CACHE_DIR, FWD_CACHE_DIR = _resolve_cache_dirs()

# Ensure directories exist
for _d in (INV_CACHE_DIR, FWD_CACHE_DIR):
    Path(_d).mkdir(parents=True, exist_ok=True)

# Plot settings
DEFAULT_BINS = 80
MAX_FIGURE_WIDTH = 16
MAX_FIGURE_HEIGHT = 12
DEFAULT_KDE_BANDWIDTH = "scott"

# Data processing options
DATA_REDUCTION_METHODS = ["flatten", "mean", "median", "std", "min", "max"]
AXIS_OPTIONS = ["auto", "0 (first)", "1 (second)", "all except last"]

# Variable detection preferences (forward posteriors: t0, k, b, v; invT: t_est)
TEMP_RELATED_VARS = ["t_est", "t0_crtp", "t0_culmesocore", "t0_culmeso", "t", "temperature"]
TIME_LIKE_DIMS = ["time", "date", "step", "iter"]

# UI defaults
MAX_CHAINS_ASSUMPTION = 20
MAX_LEGEND_FILES = 8
MAX_DIMENSION_INFO_VARS = 3
MAX_DIMENSION_INFO_FILES = 2

# File extensions
NETCDF_EXTENSIONS = ["nc", "netcdf"]
CSV_EXTENSIONS = ["csv"]

# Plot types
PLOT_TYPES = ["Histogram", "Time series", "2D heatmap"]
KDE_BANDWIDTH_METHODS = ["scott", "silverman", "custom"]
