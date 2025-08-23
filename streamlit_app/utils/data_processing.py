# utils/data_processing.py - Data processing utilities

import numpy as np
import pandas as pd
import xarray as xr
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Tuple, Union, Optional, Any, Sequence


def process_multidim_data(data_array, method: str = "flatten", axis: Optional[Union[int, str, tuple]] = None) -> Tuple[np.ndarray, str]:
    """
    Process multi-dimensional data with flexible options
    
    Parameters:
    - data_array: xarray DataArray or numpy array
    - method: "flatten", "mean", "median", "std", "min", "max"
    - axis: int, str, or None - which axis to reduce (for mean/median/etc)
    
    Returns:
    - processed numpy array (1D)
    - info string describing what was done
    """
    arr = np.asarray(data_array)
    original_shape = arr.shape
    
    if arr.ndim <= 1:
        # Already 1D or scalar
        processed = arr.ravel()
        info = ""
    elif method == "flatten":
        # Flatten to 1D
        processed = arr.flatten()
        info = f" (flattened from {original_shape})"
    else:
        # Reduction operations
        if axis is None:
            # Reduce over all axes except the last one (common for MCMC: keep draws, reduce chains)
            if arr.ndim == 2:
                axis = 0  # For (chains, draws), reduce over chains
            else:
                axis = tuple(range(arr.ndim - 1))  # Keep last dimension
        
        if method == "mean":
            processed = np.mean(arr, axis=axis)
        elif method == "median":
            processed = np.median(arr, axis=axis)
        elif method == "std":
            processed = np.std(arr, axis=axis)
        elif method == "min":
            processed = np.min(arr, axis=axis)
        elif method == "max":
            processed = np.max(arr, axis=axis)
        else:
            # Fallback to flatten
            processed = arr.flatten()
            method = "flatten"
        
        processed = processed.ravel()  # Ensure 1D
        
        if isinstance(axis, int):
            axis_name = f"axis {axis}"
        elif isinstance(axis, tuple):
            axis_name = f"axes {axis}"
        else:
            axis_name = str(axis)
            
        info = f" ({method} over {axis_name}, from {original_shape})"
    
    # Return only finite values
    finite_data = processed[np.isfinite(processed)]
    return finite_data, info


def ndarray1d(values) -> np.ndarray:
    """Legacy function - kept for backward compatibility"""
    arr = np.asarray(values)
    
    # Handle common MCMC structures: (chains, draws) -> flatten to (chains*draws,)
    if arr.ndim == 2:
        # Check if this looks like (chains, draws) - typically chains << draws
        if arr.shape[0] < arr.shape[1] and arr.shape[0] <= 20:  # Assume max 20 chains
            arr = arr.flatten()
        elif arr.shape[1] < arr.shape[0] and arr.shape[1] <= 20:  # draws, chains order
            arr = arr.flatten()
        else:
            # For other 2D arrays, just flatten
            arr = arr.flatten()
    elif arr.ndim > 2:
        # For higher dimensional arrays, flatten completely
        arr = arr.flatten()
    else:
        # Already 1D or 0D
        arr = arr.ravel()
    
    # Return only finite values
    return arr[np.isfinite(arr)]


def detect_columns(df: pd.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    """Detect column names from a list of candidates (case-insensitive)"""
    lc = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in df.columns:
            return cand
        if cand.lower() in lc:
            return lc[cand.lower()]
    return None


def summarize_t_est(t_draws: np.ndarray) -> pd.DataFrame:
    """Summarize temperature estimates with percentiles"""
    arr = np.asarray(t_draws)
    if arr.ndim == 1:
        mean = arr
        p05 = arr
        p50 = arr
        p95 = arr
    else:
        # try to put draws on axis=1
        if arr.shape[0] < arr.shape[1]:
            x = arr
        else:
            x = arr.T
        mean = np.nanmean(x, axis=1)
        p05 = np.nanpercentile(x, 5, axis=1)
        p50 = np.nanpercentile(x, 50, axis=1)
        p95 = np.nanpercentile(x, 95, axis=1)
    return pd.DataFrame({"t_est_mean": mean, "t_est_p05": p05, "t_est_p50": p50, "t_est_p95": p95})


def extract_t_est_from_result(res) -> Optional[np.ndarray]:
    """Extract temperature estimates from various result formats"""
    try:
        if isinstance(res, xr.Dataset):
            if "t_est" in res.data_vars:
                return np.asarray(res["t_est"].values)
            for k in res.data_vars:
                if "t_est" in k:
                    return np.asarray(res[k].values)
    except Exception:
        pass
    
    try:
        if isinstance(res, dict):
            if "t_est" in res:
                return np.asarray(res["t_est"])
            for k in list(res.keys()):
                if "t_est" in k:
                    return np.asarray(res[k])
    except Exception:
        pass
    
    try:
        if isinstance(res, pd.DataFrame):
            cols = [c for c in res.columns if c.startswith("t_est")]
            if len(cols) == 1:
                return np.asarray(res[cols[0]].values)
            elif len(cols) > 1:
                return np.asarray(res[cols].values)
    except Exception:
        pass
    
    return None


def get_preferred_variables(all_vars: list, preferences: list) -> Optional[str]:
    """Get the preferred variable from a list based on preferences"""
    preferred = [v for v in all_vars if any(term in v.lower() for term in preferences)]
    return preferred[0] if preferred else (all_vars[0] if all_vars else None)


def create_dimension_info_table(variables: list, files: list, max_vars: int = 3, max_files: int = 2) -> pd.DataFrame:
    """Create a table showing dimension information for variables"""
    from .file_handling import open_nc_any_engine
    import os
    
    dim_info = []
    for current_var in variables[:max_vars]:  # Show first few variables
        for f in files[:max_files]:  # Show first few files
            try:
                with open_nc_any_engine(f) as ds:
                    if current_var in ds:
                        var_data = ds[current_var]
                        dim_info.append({
                            "Variable": current_var,
                            "File": os.path.basename(f),
                            "Shape": str(var_data.shape),
                            "Dimensions": str(var_data.dims)
                        })
                        break  # Just need one example per variable
            except:
                pass
    return pd.DataFrame(dim_info)