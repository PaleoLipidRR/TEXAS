# main.py - Entry point for TEXAS Streamlit GUI

import streamlit as st
from config import INV_CACHE_DIR, FWD_CACHE_DIR

from pages.exploration import render_exploration_tab

st.set_page_config(page_title="TEXAS — Explore Posteriors", layout="wide")
st.title("TEXAS — Explore Posterior Distributions")
st.caption("Upload a NetCDF posterior file to explore parameter distributions.")

render_exploration_tab(INV_CACHE_DIR, FWD_CACHE_DIR)
