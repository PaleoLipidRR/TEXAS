# components/data_info.py - Dataset information display components

import streamlit as st
import pandas as pd
import numpy as np
import os
import sys

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
from utils.file_handling import open_nc_any_engine


def display_dataset_information(selected_files: List[str]):
    """
    Component to display detailed dataset information with collapsible sections
    
    Args:
        selected_files: List of NetCDF file paths
    """
    if st.checkbox("Show detailed dataset information"):
        for i, f in enumerate(selected_files):
            try:
                with open_nc_any_engine(f) as ds:
                    filename = os.path.basename(f)
                    
                    # Main file expander
                    with st.expander(f"📄 {filename}", expanded=(i == 0)):  # First file expanded by default
                        
                        # Posterior Run Information (Global Attributes)
                        if ds.attrs:
                            with st.expander("📊 Posterior Run Information", expanded=True):
                                # Create a more readable display of attributes
                                attrs_info = []
                                for key, value in ds.attrs.items():
                                    # Handle different types of values
                                    if isinstance(value, (list, tuple, np.ndarray)):
                                        if len(str(value)) > 100:
                                            display_value = f"{str(value)[:100]}... ({len(value)} items)"
                                        else:
                                            display_value = str(value)
                                    elif isinstance(value, dict):
                                        display_value = f"Dict with {len(value)} keys: {list(value.keys())[:5]}..."
                                    elif isinstance(value, str) and len(value) > 150:
                                        display_value = f"{value[:150]}..."
                                    else:
                                        display_value = str(value)
                                    
                                    attrs_info.append({
                                        "Attribute": key,
                                        "Value": display_value
                                    })
                                
                                attrs_df = pd.DataFrame(attrs_info)
                                st.dataframe(attrs_df, hide_index=True, use_container_width=True)
                                
                                # Show raw attrs in sub-expandable section
                                with st.expander("🔍 Raw attributes (JSON format)"):
                                    st.json(dict(ds.attrs))
                        
                        # Structure Information
                        with st.expander("🏗️ Dataset Structure"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write("**📏 Dimensions:**")
                                dims_df = pd.DataFrame([
                                    {"Dimension": name, "Size": size} 
                                    for name, size in ds.dims.items()
                                ])
                                st.dataframe(dims_df, hide_index=True)
                            
                            with col2:
                                # File size and basic info
                                st.write("**ℹ️ File Info:**")
                                total_vars = len(ds.data_vars)
                                total_coords = len(ds.coords)
                                total_attrs = len(ds.attrs)
                                
                                info_df = pd.DataFrame([
                                    {"Property": "Data Variables", "Count": total_vars},
                                    {"Property": "Coordinates", "Count": total_coords}, 
                                    {"Property": "Global Attributes", "Count": total_attrs}
                                ])
                                st.dataframe(info_df, hide_index=True)
                        
                        # Coordinates
                        if ds.coords:
                            with st.expander("📍 Coordinates"):
                                coords_info = []
                                for name, coord in ds.coords.items():
                                    coord_info = {
                                        "Coordinate": name,
                                        "Dimensions": str(coord.dims),
                                        "Shape": str(coord.shape),
                                        "Dtype": str(coord.dtype)
                                    }
                                    # Add range info if numeric
                                    if np.issubdtype(coord.dtype, np.number) and coord.size > 0:
                                        vals = coord.values
                                        if vals.size > 0:
                                            coord_info["Min"] = f"{np.nanmin(vals):.3f}"
                                            coord_info["Max"] = f"{np.nanmax(vals):.3f}"
                                    
                                    # Add coordinate attributes if they exist
                                    if coord.attrs:
                                        attr_summary = ", ".join([f"{k}={v}" for k, v in list(coord.attrs.items())[:3]])
                                        if len(coord.attrs) > 3:
                                            attr_summary += "..."
                                        coord_info["Attributes"] = attr_summary
                                    
                                    coords_info.append(coord_info)
                                
                                st.dataframe(pd.DataFrame(coords_info), hide_index=True)
                        
                        # Data Variables
                        with st.expander("📈 Data Variables (Parameters)"):
                            vars_info = []
                            for name, var_item in ds.data_vars.items():
                                var_info = {
                                    "Variable": name,
                                    "Dimensions": str(var_item.dims),
                                    "Shape": str(var_item.shape),
                                    "Dtype": str(var_item.dtype)
                                }
                                
                                # Add basic stats if numeric and not too large
                                if np.issubdtype(var_item.dtype, np.number) and var_item.size < 1000000:
                                    try:
                                        vals = var_item.values
                                        finite_vals = vals[np.isfinite(vals)]
                                        if finite_vals.size > 0:
                                            var_info["Min"] = f"{np.nanmin(finite_vals):.3f}"
                                            var_info["Max"] = f"{np.nanmax(finite_vals):.3f}"
                                            var_info["Mean"] = f"{np.nanmean(finite_vals):.3f}"
                                            var_info["Std"] = f"{np.nanstd(finite_vals):.3f}"
                                    except:
                                        pass
                                
                                # Add variable attributes summary
                                if var_item.attrs:
                                    attr_keys = list(var_item.attrs.keys())[:3]
                                    attr_summary = ", ".join(attr_keys)
                                    if len(var_item.attrs) > 3:
                                        attr_summary += f"... (+{len(var_item.attrs)-3} more)"
                                    var_info["Attributes"] = attr_summary
                                
                                vars_info.append(var_info)
                            
                            st.dataframe(pd.DataFrame(vars_info), hide_index=True)
                            
                            # Variable-specific attributes inspector
                            vars_with_attrs = [name for name, var in ds.data_vars.items() if var.attrs]
                            if vars_with_attrs:
                                with st.expander("🔬 Variable Attributes Inspector"):
                                    selected_var = st.selectbox(
                                        "Select variable to inspect:", 
                                        vars_with_attrs, 
                                        key=f"var_attrs_{filename}_{i}"
                                    )
                                    if selected_var:
                                        var_attrs = dict(ds[selected_var].attrs)
                                        st.json(var_attrs)
                        
                        # Quick summary at the bottom
                        st.caption(f"📊 Summary: {len(ds.data_vars)} variables, {len(ds.coords)} coordinates, {len(ds.attrs)} global attributes")
                        
            except Exception as e:
                st.error(f"❌ Error reading {os.path.basename(f)}: {e}")


def display_individual_file_details(variables: List[str], selected_files: List[str]):
    """
    Component to show individual file details
    
    Args:
        variables: Selected variables to show details for
        selected_files: List of NetCDF file paths
    """
    if st.checkbox("Show individual file details"):
        st.subheader("Individual File Details")
        for f in selected_files:
            with st.expander(f"Details: {os.path.basename(f)}"):
                try:
                    with open_nc_any_engine(f) as ds:
                        for current_var in variables:
                            if current_var in ds:
                                var_data = ds[current_var]
                                st.write(f"**Variable: {current_var}**")
                                st.write(f"- Dimensions: {var_data.dims}")
                                st.write(f"- Shape: {var_data.shape}")
                                st.write(f"- Dtype: {var_data.dtype}")
                                
                                # Show some values
                                vals = var_data.values
                                if vals.size < 20:
                                    st.write(f"- Values: {vals}")
                                else:
                                    flat_vals = vals.flatten()
                                    st.write(f"- Sample values: {flat_vals[:10]}...")
                                
                                # Variable-specific attributes
                                if var_data.attrs:
                                    st.write("**Attributes:**")
                                    for attr_key, attr_val in var_data.attrs.items():
                                        st.write(f"- {attr_key}: {attr_val}")
                            else:
                                st.write(f"Variable '{current_var}' not found in this file")
                            st.write("---")
                except Exception as e:
                    st.error(f"Error: {e}")


def display_file_summary(file_info: List[dict]):
    """
    Display a summary of file information
    
    Args:
        file_info: List of dictionaries with file information
    """
    with st.expander("File information"):
        for info in file_info:
            filename = os.path.basename(info['file'])
            st.write(f"**{filename}**: {len(info['vars'])} variables, dims: {info['dims']}")


def create_summary_statistics_table(all_rows: List[dict]) -> pd.DataFrame:
    """
    Create and display summary statistics table
    
    Args:
        all_rows: List of dictionaries with statistics
        
    Returns:
        DataFrame with statistics
    """
    if all_rows and st.checkbox("Show summary statistics"):
        df = pd.DataFrame(all_rows)
        st.dataframe(df)
        return df
    return pd.DataFrame()