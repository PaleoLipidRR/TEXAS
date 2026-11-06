# components/file_selector.py - Reusable file selection component

import os
import glob
import tempfile
import streamlit as st
import pandas as pd
import sys

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Optional, Tuple
from utils.file_handling import filter_files_by_pattern


def csv_file_selector(default_dirs: List[str]) -> Tuple[Optional[str], Optional[pd.DataFrame]]:
    """
    Component for selecting CSV files from upload or repository folders
    
    Returns:
        - selected_csv_path: Path to selected CSV file
        - df: Loaded DataFrame or None
    """
    source_mode = st.radio("Select CSV source:", ["Upload CSV", "From repo folders"], horizontal=True)
    
    selected_csv_path = None
    df_in = None

    if source_mode == "Upload CSV":
        up = st.file_uploader("Upload a CSV with RI columns", type=["csv"])
        if up:
            # Save to a temp file so any downstream code that expects a path can use it
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp.write(up.read())
                selected_csv_path = tmp.name
            try:
                df_in = pd.read_csv(selected_csv_path)
            except Exception as e:
                st.error(f"Could not read uploaded CSV: {e}")

    else:
        # Let user pick a repo folder and file (supports simple filename filter)
        existing_dirs = [d for d in default_dirs if os.path.isdir(d)]
        if not existing_dirs:
            st.info("No default CSV folders found. Create one of: spreadsheets/, data/raw/, data/external/ — or use Upload CSV.")
        else:
            colA, colB = st.columns([2, 3])
            with colA:
                pick_dir = st.selectbox("Choose a folder", existing_dirs, index=0)
                pattern = st.text_input("Filename filter (glob)", "*.csv")
            with colB:
                all_csvs = sorted(glob.glob(os.path.join(pick_dir, pattern)))
                nice = [os.path.relpath(p) for p in all_csvs]
                if nice:
                    selected_rel = st.selectbox("Select a CSV", nice)
                    if selected_rel:
                        selected_csv_path = os.path.abspath(selected_rel)
                        try:
                            df_in = pd.read_csv(selected_csv_path)
                        except Exception as e:
                            st.error(f"Could not read {selected_rel}: {e}")
                else:
                    st.info(f"No CSV files found in {pick_dir} matching {pattern}")

    return selected_csv_path, df_in


def netcdf_file_selector(inv_cache_dir: str, fwd_cache_dir: str) -> Tuple[List[str], dict]:
    """
    Component for selecting NetCDF files from cache or upload
    
    Returns:
        - selected_files: List of file paths
        - settings: Dictionary with user settings (bins, kde options)
    """
    source = st.radio("Select source:", ["From cache", "Upload NetCDF"], horizontal=True)
    
    selected_files: List[str] = []
    settings = {}

    if source == "From cache":
        c1, c2, c3 = st.columns([1.2, 2, 1.2])
        with c1:
            cache_choice = st.selectbox("Cache directory", ["Inverse‑T", "Forward"], index=0)
            root = inv_cache_dir if "Inverse" in cache_choice else fwd_cache_dir
        with c2:
            pattern = st.text_input("Filename filter (glob)", "*.nc", key="cache_pattern")
        with c3:
            bins = st.slider("Histogram bins", min_value=20, max_value=200, value=80, step=10)
            if st.checkbox("Show KDE options", value=False):
                kde_bw_method = st.selectbox("KDE bandwidth method", 
                                           ["scott", "silverman", "custom"], 
                                           index=0,
                                           help="scott: good for normal-like distributions, silverman: more conservative")
                if kde_bw_method == "custom":
                    kde_bandwidth = st.slider("Custom bandwidth", 0.01, 2.0, 0.2, 0.01)
                else:
                    kde_bandwidth = kde_bw_method
            else:
                kde_bandwidth = "scott"

        settings.update({"bins": bins, "kde_bandwidth": kde_bandwidth})

        # Check if directory exists
        if not os.path.isdir(root):
            st.warning(f"Cache directory `{root}` does not exist. Create it or use 'Upload NetCDF'.")
        else:
            all_files = sorted(glob.glob(os.path.join(root, "*.nc")))
            if pattern and pattern != "*.nc":
                all_files = filter_files_by_pattern(all_files, pattern)

            if not all_files:
                st.info(f"No .nc files found in `{root}` matching `{pattern}`.")
            else:
                # Show relative paths for cleaner display
                display_names = [os.path.relpath(f, root) for f in all_files]
                selected_display = st.multiselect("Select one or more NetCDF files", 
                                                display_names, 
                                                default=display_names[:1] if display_names else [])
                selected_files = [os.path.join(root, name) for name in selected_display]

    else:
        uploads = st.file_uploader("Upload one or more NetCDF files", 
                                 type=["nc", "netcdf"], 
                                 accept_multiple_files=True)
        bins = st.slider("Histogram bins", min_value=20, max_value=200, value=80, step=10, key="upload_bins")
        
        # KDE options
        if st.checkbox("Show KDE options", value=False):
            kde_bw_method = st.selectbox("KDE bandwidth method", 
                                       ["scott", "silverman", "custom"], 
                                       index=0,
                                       help="scott: good for normal-like distributions, silverman: more conservative")
            if kde_bw_method == "custom":
                kde_bandwidth = st.slider("Custom bandwidth", 0.01, 2.0, 0.2, 0.01)
            else:
                kde_bandwidth = kde_bw_method
        else:
            kde_bandwidth = "scott"
            
        settings.update({"bins": bins, "kde_bandwidth": kde_bandwidth})
        
        if uploads:
            for i, up in enumerate(uploads):
                with tempfile.NamedTemporaryFile(suffix=f"_{i}.nc", delete=False) as tmp:
                    tmp.write(up.read())
                    selected_files.append(tmp.name)

    return selected_files, settings