# utils/file_handling.py - File I/O operations

import os
import glob
import fnmatch
import xarray as xr
import streamlit as st
from typing import List


@st.cache_data(show_spinner=False)
def list_nc_files(root_dir: str) -> List[str]:
    """List NetCDF files in a directory"""
    if not os.path.isdir(root_dir):
        return []
    # one level deep; adjust if needed
    return sorted(glob.glob(os.path.join(root_dir, "*.nc")))


def open_nc_any_engine(path: str):
    """Open NetCDF file with fallback engines"""
    last_err = None
    for eng in ("h5netcdf", "netcdf4", "scipy", None):
        try:
            return xr.open_dataset(path, engine=eng) if eng else xr.open_dataset(path)
        except Exception as e:
            last_err = (eng, e)
    raise RuntimeError(
        f"Could not open {os.path.basename(path)}; "
        f"last error with {last_err[0] if last_err else 'unknown'}: "
        f"{last_err[1] if last_err else 'unknown'}"
    )


def find_csv_files(directories: List[str], pattern: str = "*.csv") -> List[str]:
    """Find CSV files in given directories matching pattern"""
    all_csvs = []
    for directory in directories:
        if os.path.isdir(directory):
            files = sorted(glob.glob(os.path.join(directory, pattern)))
            all_csvs.extend(files)
    return all_csvs


def filter_files_by_pattern(files: List[str], pattern: str) -> List[str]:
    """Filter files by glob pattern"""
    if not pattern or pattern == "*":
        return files
    return [f for f in files if fnmatch.fnmatch(os.path.basename(f), pattern)]


def get_file_info(selected_files: List[str]) -> List[dict]:
    """Get basic info about NetCDF files"""
    file_info = []
    for f in selected_files:
        try:
            with open_nc_any_engine(f) as ds:
                file_info.append({
                    'file': f,
                    'vars': list(ds.data_vars.keys()),
                    'dims': dict(ds.dims)
                })
        except Exception as e:
            st.warning(f"Skipping {os.path.basename(f)}: {e}")
    return file_info


def collect_variables_from_files(selected_files: List[str]) -> List[str]:
    """Collect all unique variables from selected files"""
    var_sets = []
    for f in selected_files:
        try:
            with open_nc_any_engine(f) as ds:
                var_sets.append(set(ds.data_vars.keys()))
        except Exception as e:
            st.warning(f"Skipping {os.path.basename(f)}: {e}")
    
    if not var_sets:
        return []
    
    return sorted(set().union(*var_sets))