# components/plot_controls.py - Plot configuration widgets

import streamlit as st
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, List, Tuple
from config import DATA_REDUCTION_METHODS, AXIS_OPTIONS, PLOT_TYPES
from utils.data_processing import create_dimension_info_table
import pandas as pd


def plot_type_controls(n_files: int = 1) -> Dict[str, Any]:
    """
    Component for plot type and basic plot controls.

    When multiple files are selected, defaults to KDE line mode so each file
    appears as a distinct curve on each parameter subplot.
    """
    multi = n_files > 1
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        plot_type = st.selectbox("Plot type", PLOT_TYPES, index=0)
    with col2:
        if plot_type == "Histogram":
            use_kde = st.checkbox(
                "KDE lines" if multi else "Use KDE instead",
                value=multi,
                help="One smooth curve per file — cleaner for multi-file comparison" if multi
                     else "Kernel Density Estimation for smoother curves",
            )
        else:
            use_kde = False
    with col3:
        show_individual = st.checkbox("Show individual file plots", value=False)
    
    # Additional histogram/KDE options
    if plot_type == "Histogram":
        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            show_mean = st.checkbox("Show mean lines", value=False, 
                                  help="Add vertical lines at distribution means")
        with col_b:
            show_median = st.checkbox("Show median lines", value=False,
                                    help="Add vertical lines at distribution medians")
        with col_c:
            truncate_legend = st.checkbox("Truncate long legend names", value=True,
                                        help="Shorten long filenames in legend")
    else:
        show_mean = False
        show_median = False
        truncate_legend = False
    
    return {
        "plot_type": plot_type,
        "use_kde": use_kde,
        "show_individual": show_individual,
        "show_mean": show_mean,
        "show_median": show_median,
        "truncate_legend": truncate_legend
    }


def subplot_layout_controls(n_variables: int) -> Dict[str, Any]:
    """
    Component for subplot layout options
    
    Args:
        n_variables: Number of variables selected
        
    Returns:
        Dictionary with layout settings
    """
    if n_variables > 1:
        col_a, col_b = st.columns([1, 1])
        with col_a:
            subplot_cols = st.selectbox("Subplot columns", [1, 2, 3, 4],
                                      index=1 if n_variables <= 4 else 0,
                                      help="Number of columns in subplot grid")
        with col_b:
            share_axes = st.checkbox("Share axes", value=False,
                                   help="Use same scale for all subplots — off by default since TEXAS parameters have very different ranges")
    else:
        subplot_cols = 1
        share_axes = False
    
    return {
        "subplot_cols": subplot_cols,
        "share_axes": share_axes
    }


def data_processing_controls(variables: List[str], files: List[str]) -> Dict[str, Any]:
    """
    Component for multi-dimensional data processing options
    
    Args:
        variables: Selected variables
        files: Selected files
        
    Returns:
        Dictionary with processing settings
    """
    with st.expander("Multi-dimensional data options", expanded=False):
        # Show dimension info for selected variables
        if variables and files:
            st.write("**Dimension info for selected variables:**")
            dim_info_df = create_dimension_info_table(variables, files)
            if not dim_info_df.empty:
                st.dataframe(dim_info_df, hide_index=True)
        
        col_method, col_axis = st.columns([1, 1])
        with col_method:
            reduction_method = st.selectbox(
                "How to handle multi-dimensional data:",
                DATA_REDUCTION_METHODS,
                index=0,
                help="flatten: use all samples; mean/median: average over specified axis"
            )
        with col_axis:
            if reduction_method != "flatten":
                axis_option = st.selectbox(
                    "Reduce over which axis:",
                    AXIS_OPTIONS,
                    index=0,
                    help="auto: smart choice based on data shape (chains for MCMC)"
                )
                if axis_option == "auto":
                    axis_param = None
                elif axis_option == "0 (first)":
                    axis_param = 0
                elif axis_option == "1 (second)":
                    axis_param = 1
                else:  # all except last
                    axis_param = "all_except_last"
            else:
                axis_param = None
    
    return {
        "reduction_method": reduction_method,
        "axis_param": axis_param
    }


def variable_selection_controls(all_variables: List[str], default_var: str) -> List[str]:
    """
    Component for variable selection
    
    Args:
        all_variables: All available variables
        default_var: Default/preferred variable
        
    Returns:
        List of selected variables
    """
    selected_vars = st.multiselect("Variable(s) to compare", all_variables, 
                                 default=[default_var] if default_var in all_variables else all_variables[:1])
    
    if not selected_vars:
        st.warning("Please select at least one variable to plot.")
        st.stop()
    
    return selected_vars


def processing_axis_conversion(axis_param: Any, raw_data_ndim: int) -> Any:
    """
    Convert axis parameter to the format needed by processing function
    
    Args:
        axis_param: Axis parameter from UI
        raw_data_ndim: Number of dimensions in raw data
        
    Returns:
        Converted axis parameter
    """
    if axis_param == "all_except_last" and raw_data_ndim > 1:
        return tuple(range(raw_data_ndim - 1))
    return axis_param