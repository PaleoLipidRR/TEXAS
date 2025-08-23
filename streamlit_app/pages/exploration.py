# pages/exploration.py - Posterior exploration page

import streamlit as st
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
from components.file_selector import netcdf_file_selector
from components.plot_controls import (
    plot_type_controls, 
    subplot_layout_controls, 
    data_processing_controls,
    variable_selection_controls
)
from components.data_info import (
    display_dataset_information,
    display_individual_file_details,
    display_file_summary,
    create_summary_statistics_table
)
from utils.file_handling import get_file_info, collect_variables_from_files
from utils.data_processing import get_preferred_variables
from utils.plotting import create_histogram_subplots, create_timeseries_plots, create_heatmap_plots
from config import TEMP_RELATED_VARS


def render_exploration_tab(inv_cache_dir: str, fwd_cache_dir: str):
    """
    Render the posterior exploration tab
    
    Args:
        inv_cache_dir: Path to inverse temperature cache directory
        fwd_cache_dir: Path to forward model cache directory
    """
    st.subheader("Explore posterior distributions")

    # File selection
    selected_files, settings = netcdf_file_selector(inv_cache_dir, fwd_cache_dir)
    
    if not selected_files:
        st.info("No files selected yet.")
        return

    # Get file information and variables
    file_info = get_file_info(selected_files)
    if not file_info:
        st.warning("Could not open any selected files.")
        return

    all_vars = collect_variables_from_files(selected_files)
    if not all_vars:
        st.warning("No variables found in the selected files.")
        return

    # Variable selection
    default_var = get_preferred_variables(all_vars, TEMP_RELATED_VARS)
    selected_vars = variable_selection_controls(all_vars, default_var)

    # Plot controls
    plot_settings = plot_type_controls()
    layout_settings = subplot_layout_controls(len(selected_vars))
    processing_settings = data_processing_controls(selected_vars, selected_files)

    # Display file information
    display_file_summary(file_info)

    # Create plots based on type
    if plot_settings["plot_type"] == "Histogram":
        fig, all_rows = create_histogram_subplots(
            variables=selected_vars,
            selected_files=selected_files,
            subplot_cols=layout_settings["subplot_cols"],
            share_axes=layout_settings["share_axes"],
            use_kde=plot_settings["use_kde"],
            bins=settings["bins"],
            kde_bandwidth=settings["kde_bandwidth"],
            reduction_method=processing_settings["reduction_method"],
            axis_param=processing_settings["axis_param"],
            show_mean=plot_settings["show_mean"],
            show_median=plot_settings["show_median"],
            truncate_legend=plot_settings["truncate_legend"]
        )
        
        if all_rows:
            st.pyplot(fig, clear_figure=True)
            create_summary_statistics_table(all_rows)
        else:
            st.info("No variables found in the selected files.")

    elif plot_settings["plot_type"] == "Time series":
        fig = create_timeseries_plots(selected_vars, selected_files)
        st.pyplot(fig, clear_figure=True)

    elif plot_settings["plot_type"] == "2D heatmap":
        figures = create_heatmap_plots(selected_vars, selected_files)
        for fig in figures:
            st.pyplot(fig, clear_figure=True)
    
    display_dataset_information(selected_files)

    # Individual file details
    if plot_settings["show_individual"]:
        display_individual_file_details(selected_vars, selected_files)