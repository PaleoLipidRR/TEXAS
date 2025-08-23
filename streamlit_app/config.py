# config.py - Configuration and constants for TEXAS GUI

import os
from pathlib import Path

# Smart cache directory detection without triggering CmdStan imports
def get_texas_cache_dirs():
    """
    Try to find TEXAS cache directories without importing the full package
    """
    # Method 1: Try direct path calculation (like TEXAS does, but without CmdStan)
    try:
        cwd = Path.cwd()
        # Look for TEXAS project root
        for parent in [cwd, *cwd.parents]:
            if parent.name == "TEXAS" or (parent / "src" / "TEXAS").exists():
                project_root = parent
                cache_dir = project_root / "data" / "cache"
                inv_cache = cache_dir / "TEXAS_invT_posterior_cache"
                fwd_cache = cache_dir / "TEXAS_posterior_cache"
                
                if cache_dir.exists() or project_root.exists():
                    return str(inv_cache), str(fwd_cache)
                break
    except Exception:
        pass
    
    # Method 2: Try importing just the paths (might still fail with CmdStan)
    try:
        # Only import if we're sure it won't break
        import sys
        if 'cmdstanpy' not in str(sys.modules):
            from TEXAS.utils.paths import POSTERIOR_CACHE_DIR, INVT_CACHE_DIR
            return str(INVT_CACHE_DIR), str(POSTERIOR_CACHE_DIR)
    except Exception:
        pass
    
    # Method 3: Environment variables (user can set these)
    inv_env = os.environ.get("TEXAS_INV_CACHE")
    fwd_env = os.environ.get("TEXAS_FWD_CACHE")
    if inv_env and fwd_env:
        return inv_env, fwd_env
    
    # Method 4: Fallback to relative paths
    return "data/cache/TEXAS_invT_posterior_cache", "data/cache/TEXAS_posterior_cache"

# Get cache directories
INV_CACHE_DIR, FWD_CACHE_DIR = get_texas_cache_dirs()

print(f"📁 Cache directories:")
print(f"   Inverse T: {INV_CACHE_DIR}")
print(f"   Forward:   {FWD_CACHE_DIR}")

# Create directories if they don't exist (for convenience)
try:
    Path(INV_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    Path(FWD_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    print(f"✓ Cache directories ready")
except Exception as e:
    print(f"⚠ Could not create cache directories: {e}")

# Default CSV directories
DEFAULT_CSV_DIRS = os.getenv(
    "TEXAS_CSV_DIRS",
    "spreadsheets,data/raw,data/external"
).split(",")

# Plot settings
DEFAULT_BINS = 80
MAX_FIGURE_WIDTH = 16
MAX_FIGURE_HEIGHT = 12
DEFAULT_KDE_BANDWIDTH = "scott"

# Data processing options
DATA_REDUCTION_METHODS = ["flatten", "mean", "median", "std", "min", "max"]
AXIS_OPTIONS = ["auto", "0 (first)", "1 (second)", "all except last"]

# Variable detection preferences (for auto-selection)
TEMP_RELATED_VARS = ["t_est", "t", "temperature", "t_mean", "t_est_mean"]
TIME_LIKE_DIMS = ['time', 'date', 'step', 'iter']

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