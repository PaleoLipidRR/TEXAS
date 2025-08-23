# main.py - Entry point for TEXAS Streamlit GUI

import streamlit as st
import sys
from config import INV_CACHE_DIR, FWD_CACHE_DIR

# Try authoritative imports per new structure
_predict_fn = None
_get_post_fn = None
_import_errors = []

try:
    from TEXAS.stan.invT import predict_temperature_from_RI as _predict_fn  # type: ignore
except Exception as e:
    _import_errors.append(("TEXAS.stan.invT.predict_temperature_from_RI", repr(e)))

try:
    from TEXAS.stan.sampler import get_posterior as _get_post_fn  # type: ignore
except Exception as e:
    _import_errors.append(("TEXAS.stan.sampler.get_posterior", repr(e)))

# Import pages
from pages.prediction import render_prediction_tab
from pages.exploration import render_exploration_tab
from pages.computation import render_computation_tab

# ──────────────────────────────────────────────────────────────────────────────
# Main App Configuration
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="TEXAS GUI", layout="wide")
st.title("TEXAS GUI")
st.caption("Drop a CSV to get **t_est** or upload a NetCDF to **explore posteriors**.")

tabs = st.tabs(["Predict temperature from RI", "Explore posterior distributions", "Compute posteriors (advanced)"])

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.subheader("Environment")
    st.write("Python:", sys.version.split()[0])
    if _predict_fn is not None:
        st.success("predict_temperature_from_RI: OK (TEXAS.stan.invT)")
    else:
        st.warning("predict_temperature_from_RI not importable")
    if _get_post_fn is not None:
        st.success("get_posterior: OK (TEXAS.stan.sampler)")
    else:
        st.info("get_posterior not importable")
    if _import_errors:
        with st.expander("Import errors"):
            for name, err in _import_errors:
                st.code(f"{name}: {err}")

# ──────────────────────────────────────────────────────────────────────────────
# Tab Contents
# ──────────────────────────────────────────────────────────────────────────────

with tabs[0]:
    render_prediction_tab(_predict_fn)

with tabs[1]:
    render_exploration_tab(INV_CACHE_DIR, FWD_CACHE_DIR)

with tabs[2]:
    render_computation_tab(_get_post_fn)

st.caption("Note: Heavy sampling is best run in batch or notebooks. This GUI provides an ergonomic front end but won't manage long jobs.")