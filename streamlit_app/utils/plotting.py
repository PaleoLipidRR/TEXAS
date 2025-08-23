# utils/plotting.py - Matplotlib plotting utilities

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
import os
import sys

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Dict, Any, Tuple
from utils.file_handling import open_nc_any_engine
from utils.data_processing import process_multidim_data
from components.plot_controls import processing_axis_conversion
from config import MAX_LEGEND_FILES, TIME_LIKE_DIMS


def truncate_filename(filename: str, max_length: int = 30) -> str:
    """
    Truncate long filenames for cleaner legends
    
    Args:
        filename: Original filename
        max_length: Maximum length to keep
        
    Returns:
        Truncated filename
    """
    if len(filename) <= max_length:
        return filename
    
    # Try to keep the important parts - remove middle
    if filename.endswith('.nc'):
        name_part = filename[:-3]  # Remove .nc
        if len(name_part) <= max_length - 3:
            return filename
        
        # Keep start and end, replace middle with ...
        keep_start = (max_length - 6) // 2  # -6 for "..." and ".nc"
        keep_end = max_length - 6 - keep_start
        return f"{name_part[:keep_start]}...{name_part[-keep_end:]}.nc"
    else:
        keep_start = (max_length - 3) // 2
        keep_end = max_length - 3 - keep_start
        return f"{filename[:keep_start]}...{filename[-keep_end:]}"


def create_histogram_subplots(
    variables: List[str], 
    selected_files: List[str], 
    subplot_cols: int, 
    share_axes: bool,
    use_kde: bool,
    bins: int,
    kde_bandwidth: str,
    reduction_method: str,
    axis_param: Any,
    show_mean: bool = False,
    show_median: bool = False,
    truncate_legend: bool = True
) -> Tuple[plt.Figure, List[dict]]:
    """
    Create histogram/KDE subplots for multiple variables
    
    Returns:
        - matplotlib figure
        - list of statistics dictionaries
    """
    n_vars = len(variables)
    n_cols = min(subplot_cols, n_vars)
    n_rows = (n_vars + n_cols - 1) // n_cols  # Ceiling division
    
    base_width = 5   # Width per subplot (inches)
    base_height = 4  # Height per subplot (inches)
    fig_width = min(base_width * n_cols, 20)   # Max total width
    fig_height = min(base_height * n_rows, 16)  # Max total height
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(fig_width, fig_height), 
                           squeeze=False, 
                           sharex=share_axes, sharey=share_axes)
    axes = axes.flatten()
    
    all_rows = []
    
    for var_idx, current_var in enumerate(variables):
        ax = axes[var_idx]
        var_rows = []
        file_stats = []  # Store statistics for vertical lines
        
        for f in selected_files:
            try:
                with open_nc_any_engine(f) as ds:
                    if current_var not in ds:
                        continue
                    
                    # Get the raw data and process it
                    raw_data = ds[current_var]
                    
                    # Handle axis parameter conversion
                    axis_for_processing = processing_axis_conversion(axis_param, raw_data.ndim)
                    
                    vals, shape_info = process_multidim_data(
                        raw_data, 
                        method=reduction_method, 
                        axis=axis_for_processing
                    )
                    
                    if vals.size == 0:
                        continue
                        
                    # Create label (truncate if requested)
                    base_label = os.path.basename(f)
                    if truncate_legend:
                        display_label = truncate_filename(base_label)
                    else:
                        display_label = base_label
                    
                    label = display_label + shape_info
                    
                    # Store statistics for vertical lines
                    file_stats.append({
                        'mean': np.mean(vals),
                        'median': np.median(vals),
                        'label': display_label
                    })
                    
                    if use_kde:
                        # Use scipy for KDE
                        try:
                            from scipy.stats import gaussian_kde
                            if vals.size > 1:  # Need at least 2 points for KDE
                                kde = gaussian_kde(vals, bw_method=kde_bandwidth)
                                x_range = np.linspace(vals.min(), vals.max(), 200)
                                density = kde(x_range)
                                ax.plot(x_range, density, label=label, linewidth=2, alpha=0.8)
                            else:
                                st.warning(f"{base_label}: Not enough data points for KDE (n={vals.size})")
                        except ImportError:
                            st.error("scipy not available for KDE. Using histogram instead.")
                            ax.hist(vals, bins=bins, density=True, alpha=0.6, label=label)
                        except Exception as e:
                            st.warning(f"{base_label}: KDE failed ({e}), using histogram")
                            ax.hist(vals, bins=bins, density=True, alpha=0.6, label=label)
                    else:
                        # Standard histogram
                        ax.hist(vals, bins=bins, density=True, alpha=0.6, label=label)
                    
                    var_rows.append({
                        "variable": current_var,
                        "file": base_label,
                        "original_shape": str(raw_data.shape),
                        "dimensions": str(raw_data.dims),
                        "processing": f"{reduction_method}{shape_info}",
                        "n_samples": int(vals.size),
                        "mean": float(np.mean(vals)),
                        "std": float(np.std(vals)),
                        "p5": float(np.percentile(vals, 5)),
                        "p50": float(np.percentile(vals, 50)),
                        "p95": float(np.percentile(vals, 95)),
                    })
            except Exception as e:
                st.warning(f"{os.path.basename(f)} - {current_var}: {e}")
        
        # Add vertical lines for means and medians
        if var_rows:  # Only if we have data
            y_min, y_max = ax.get_ylim()
            
            if show_mean:
                for i, stats in enumerate(file_stats):
                    color = plt.cm.tab10(i % 10)  # Use same colors as plots
                    ax.axvline(stats['mean'], color=color, linestyle='--', alpha=0.7, linewidth=1.5)
                    # Add small text label
                    ax.text(stats['mean'], y_max * 0.95, f"μ", ha='center', va='top', 
                           color=color, fontweight='bold', fontsize=10)
            
            if show_median:
                for i, stats in enumerate(file_stats):
                    color = plt.cm.tab10(i % 10)  # Use same colors as plots  
                    ax.axvline(stats['median'], color=color, linestyle=':', alpha=0.7, linewidth=1.5)
                    # Add small text label
                    ax.text(stats['median'], y_max * 0.85, f"M", ha='center', va='top',
                           color=color, fontweight='bold', fontsize=10)
        
        # Customize each subplot
        if var_rows:
            ax.set_xlabel(current_var)
            ax.set_ylabel("Density")
            ax.set_title(f"{'KDE' if use_kde else 'Histogram'}: {current_var}")
            if len(selected_files) <= MAX_LEGEND_FILES:
                ax.legend(loc="best", fontsize=6)
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, f"No data for\n{current_var}", 
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_title(current_var)
        
        all_rows.extend(var_rows)
    
    # Hide empty subplots
    for i in range(n_vars, len(axes)):
        axes[i].set_visible(False)
    
    plt.tight_layout()
    return fig, all_rows


def create_timeseries_plots(variables: List[str], selected_files: List[str]) -> plt.Figure:
    """
    Create time series plots for multiple variables and files
    
    Returns:
        matplotlib figure
    """
    n_vars = len(variables)
    n_files = len(selected_files)
    
    # Create subplot grid: variables as rows, files as columns (or vice versa)
    if n_vars <= 3 and n_files <= 4:
        # Small grid: vars as rows, files as columns  
        fig, axes = plt.subplots(n_vars, n_files, figsize=(3*n_files, 2.5*n_vars), squeeze=False)
        
        for var_idx, current_var in enumerate(variables):
            for file_idx, f in enumerate(selected_files):
                ax = axes[var_idx, file_idx] if n_files > 1 else axes[var_idx, 0]
                
                try:
                    with open_nc_any_engine(f) as ds:
                        if current_var not in ds:
                            ax.text(0.5, 0.5, f"'{current_var}'\nnot found", 
                                   ha='center', va='center', transform=ax.transAxes, fontsize=8)
                            continue
                            
                        var_data = ds[current_var]
                        
                        # Try to find a time-like dimension
                        time_dim = None
                        for dim in var_data.dims:
                            if any(time_word in dim.lower() for time_word in TIME_LIKE_DIMS):
                                time_dim = dim
                                break
                        
                        if time_dim is None and len(var_data.dims) > 0:
                            time_dim = var_data.dims[0]
                        
                        if time_dim:
                            if len(var_data.dims) == 1:
                                ax.plot(ds[time_dim], var_data, '-o', markersize=2)
                            else:
                                other_dims = [d for d in var_data.dims if d != time_dim]
                                mean_data = var_data.mean(dim=other_dims) if other_dims else var_data
                                ax.plot(ds[time_dim], mean_data, '-o', markersize=2)
                        else:
                            vals = var_data.values.flatten()
                            ax.plot(vals, '-o', markersize=2)
                        
                        ax.set_title(f"{os.path.basename(f)}\n{current_var}", fontsize=8)
                        ax.grid(True, alpha=0.3)
                        
                except Exception as e:
                    ax.text(0.5, 0.5, f"Error:\n{str(e)[:30]}", 
                           ha='center', va='center', transform=ax.transAxes, fontsize=8)
    else:
        # Large grid: flatten to single column, group by variable
        total_plots = n_vars * n_files
        fig, axes = plt.subplots(total_plots, 1, figsize=(10, 2*total_plots), squeeze=False)
        axes = axes.flatten()
        
        plot_idx = 0
        for current_var in variables:
            for f in selected_files:
                ax = axes[plot_idx]
                plot_idx += 1
                
                try:
                    with open_nc_any_engine(f) as ds:
                        if current_var not in ds:
                            ax.text(0.5, 0.5, f"'{current_var}' not found", 
                                   ha='center', va='center', transform=ax.transAxes)
                            ax.set_title(f"{os.path.basename(f)} - {current_var}")
                            continue
                            
                        var_data = ds[current_var]
                        
                        # Find time dimension and plot
                        time_dim = None
                        for dim in var_data.dims:
                            if any(time_word in dim.lower() for time_word in TIME_LIKE_DIMS):
                                time_dim = dim
                                break
                        
                        if time_dim is None and len(var_data.dims) > 0:
                            time_dim = var_data.dims[0]
                        
                        if time_dim:
                            if len(var_data.dims) == 1:
                                ax.plot(ds[time_dim], var_data, '-', linewidth=1)
                            else:
                                other_dims = [d for d in var_data.dims if d != time_dim]
                                mean_data = var_data.mean(dim=other_dims) if other_dims else var_data
                                ax.plot(ds[time_dim], mean_data, '-', linewidth=1)
                        else:
                            vals = var_data.values.flatten()
                            ax.plot(vals, '-', linewidth=1)
                        
                        ax.set_title(f"{os.path.basename(f)} - {current_var}")
                        ax.set_ylabel(current_var)
                        ax.grid(True, alpha=0.3)
                        
                except Exception as e:
                    ax.text(0.5, 0.5, f"Error: {str(e)[:50]}", 
                           ha='center', va='center', transform=ax.transAxes)
                    ax.set_title(f"{os.path.basename(f)} - {current_var}")
    
    plt.tight_layout()
    return fig


def create_heatmap_plots(variables: List[str], selected_files: List[str]) -> List[plt.Figure]:
    """
    Create 2D heatmap plots for multiple variables
    
    Returns:
        List of matplotlib figures (one per variable)
    """
    figures = []
    
    for current_var in variables:
        st.subheader(f"Heatmaps for: {current_var}")
        
        # Calculate subplot layout for files
        n_files = len(selected_files)
        n_cols = min(3, n_files)  # Max 3 columns
        n_rows = (n_files + n_cols - 1) // n_cols
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(4*n_cols, 4*n_rows), squeeze=False)
        axes = axes.flatten()
        
        file_idx = 0
        for f in selected_files:
            ax = axes[file_idx]
            file_idx += 1
            
            try:
                with open_nc_any_engine(f) as ds:
                    if current_var not in ds:
                        ax.text(0.5, 0.5, f"'{current_var}'\nnot found", 
                               ha='center', va='center', transform=ax.transAxes)
                        ax.set_title(os.path.basename(f))
                        continue
                        
                    var_data = ds[current_var]
                    
                    if len(var_data.dims) < 2:
                        ax.text(0.5, 0.5, f"Not 2D+\n(dims: {var_data.dims})", 
                               ha='center', va='center', transform=ax.transAxes)
                        ax.set_title(os.path.basename(f))
                        continue
                    
                    # For MCMC data with (chains, draws), show as 2D
                    if len(var_data.dims) == 2:
                        plot_data = var_data
                    else:
                        # Take first slice of extra dimensions
                        slice_dict = {dim: 0 for dim in var_data.dims[2:]}
                        plot_data = var_data.isel(**slice_dict)
                    
                    im = ax.imshow(plot_data.values, aspect='auto', origin='lower')
                    ax.set_title(f"{os.path.basename(f)}")
                    ax.set_xlabel(plot_data.dims[1] if len(plot_data.dims) > 1 else "dim_1")
                    ax.set_ylabel(plot_data.dims[0])
                    plt.colorbar(im, ax=ax)
                    
            except Exception as e:
                ax.text(0.5, 0.5, f"Error:\n{str(e)[:30]}", 
                       ha='center', va='center', transform=ax.transAxes)
                ax.set_title(os.path.basename(f))
        
        # Hide empty subplots
        for i in range(n_files, len(axes)):
            axes[i].set_visible(False)
        
        plt.tight_layout()
        figures.append(fig)
    
    return figures