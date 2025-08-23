# pages/computation.py - Advanced posterior computation page

import streamlit as st
import json
import inspect
import io
import xarray as xr


def render_computation_tab(get_posterior_fn):
    """
    Render the advanced posterior computation tab
    
    Args:
        get_posterior_fn: TEXAS get_posterior function (or None if not available)
    """
    st.subheader("Call TEXAS.stan.sampler.get_posterior (advanced)")
    
    if get_posterior_fn is None:
        st.info("get_posterior not importable. Ensure TEXAS is installed and the module path is correct.")
        return
    
    # Show function signature
    sig = inspect.signature(get_posterior_fn)
    st.write("**Detected signature:**")
    st.code(str(sig))

    # Show docstring if available
    doc = inspect.getdoc(get_posterior_fn) or ""
    if doc:
        with st.expander("Docstring", expanded=False):
            st.markdown(doc)

    # JSON input interface
    st.markdown("Provide keyword arguments as JSON. Example:")
    example_json = (
        '{\n'
        '  "model": "gen_logi_fixed_culmesocore_thermoT",\n'
        '  "data": { "N": 123 },\n'
        '  "chains": 4,\n'
        '  "iter_sampling": 1000,\n'
        '  "iter_warmup": 500,\n'
        '  "seed": 42,\n'
        '  "save_results": true\n'
        '}'
    )
    st.code(example_json, language="json")

    kwargs_text = st.text_area("kwargs (JSON)", value="{}", height=250)
    run_btn = st.button("Run get_posterior", type="primary")

    if run_btn:
        try:
            kwargs = json.loads(kwargs_text or "{}")
            with st.spinner("Running get_posterior(...) — this can be compute-heavy."):
                result = get_posterior_fn(**kwargs)
            st.success("get_posterior completed.")
            
            if isinstance(result, xr.Dataset):
                st.write("Result dims:", dict(result.dims))
                st.write("Result variables:", list(result.data_vars)[:20])
                bytes_io = io.BytesIO()
                result.to_netcdf(bytes_io)
                st.download_button("Download result NetCDF", 
                                 data=bytes_io.getvalue(),
                                 file_name="posterior_result.nc", 
                                 mime="application/netcdf")
            else:
                st.write("Result (repr):")
                st.code(repr(result)[:5000])
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")
        except Exception as e:
            st.error(f"Error: {e}")