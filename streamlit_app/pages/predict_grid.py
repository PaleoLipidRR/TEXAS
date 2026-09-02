# pages/predict_grid.py - Temperature prediction via gridT (no CmdStan required)
#
# DRAFT -- see the branch-status banner at the top of README.md. This page
# exists specifically to test whether the GUI can offer proxy -> temperature
# prediction WITHOUT requiring users to install CmdStan, by calling
# TEXAS.predict_grid.predict_T_grid() (grid quadrature) instead of
# TEXAS.predict_T_from_proxyObs() (Stan/HMC). See src/TEXAS/predict_grid.py's
# module docstring for validation status and known limitations before
# trusting results from this page for anything beyond a quick sanity check.

import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.file_selector import csv_file_selector
from utils.data_processing import detect_columns
from config import DEFAULT_CSV_DIRS

st.set_page_config(page_title="TEXAS — Predict (gridT)", layout="wide")
st.title("Predict temperature from RI — gridT (no CmdStan)")
st.caption(
    "Grid-quadrature reconstruction: same target posterior as the Stan-based "
    "Predict page, computed by numerical integration instead of HMC sampling. "
    "No CmdStan install needed. DRAFT / unreviewed -- see README.md banner."
)

try:
    from TEXAS.predict_grid import predict_T_grid
    _import_error = None
except Exception as e:  # pragma: no cover - defensive, mirrors config.py's pattern
    predict_T_grid = None
    _import_error = str(e)

if _import_error:
    st.error(f"Could not import TEXAS.predict_grid: {_import_error}")

# ── Input data ────────────────────────────────────────────────────────────
st.subheader("1. Proxy data")
use_example = st.checkbox("Use example data (skip upload)", value=True)

if use_example:
    df_in = pd.DataFrame({
        "scaledRI": [0.45, 0.55, 0.65, 0.75, 0.85, 0.90, 0.94, 0.97],
    })
    st.dataframe(df_in)
    col_scaledRI = "scaledRI"
    opt_gdgt = "<none>"
    opt_no3 = "<none>"
else:
    selected_csv_path, df_in = csv_file_selector(DEFAULT_CSV_DIRS)
    if df_in is None:
        st.info("Upload a CSV or select one from repo folders to continue.")
        st.stop()
    with st.expander("Peek at input (first 10 rows)"):
        st.dataframe(df_in.head(10))

    st.subheader("2. Map columns")
    auto_col = detect_columns(df_in, ["scaledRI", "ri", "RI"]) or df_in.columns[0]
    col_scaledRI = st.selectbox(
        "scaledRI column", options=df_in.columns,
        index=df_in.columns.tolist().index(auto_col),
    )
    opt_gdgt = st.selectbox(
        "gdgt23ratio column (optional)",
        options=["<none>"] + df_in.columns.tolist(), index=0,
    )
    opt_no3 = st.selectbox(
        "no3 column (optional)",
        options=["<none>"] + df_in.columns.tolist(), index=0,
    )

# ── Inference settings ───────────────────────────────────────────────────
st.subheader("3. Inference settings")
prior_mu_t = st.number_input("prior_mu_t", value=15.0)
prior_sigma_t = st.number_input("prior_sigma_t", value=10.0, min_value=0.01)
fwd_posterior_name = st.text_input(
    "Forward posterior name",
    value="tx.GHEB.sst.sri03.G23-N1p0",
    help="Bundled with the package by default -- no download required.",
)

# ── Run ───────────────────────────────────────────────────────────────────
disabled = predict_T_grid is None
if st.button("Run gridT prediction", type="primary", disabled=disabled):
    predictors = {}
    if opt_gdgt != "<none>":
        predictors["gdgt23ratio"] = df_in[opt_gdgt].astype(float).values
    if opt_no3 != "<none>":
        predictors["no3"] = df_in[opt_no3].astype(float).values

    with st.spinner("Running TEXAS.predict_grid.predict_T_grid (grid quadrature)..."):
        try:
            res = predict_T_grid(
                proxyObs=df_in[col_scaledRI].astype(float).values,
                prior_mu_t=float(prior_mu_t),
                prior_sigma_t=float(prior_sigma_t),
                fwd_posterior=fwd_posterior_name,
                predictors=predictors or None,
                percentiles=(5, 16, 50, 84, 95),
            )
        except Exception as e:
            st.error(f"Prediction failed: {e}")
            res = None

    if res is not None:
        out_df = df_in.copy().reset_index(drop=True)
        for p in (5, 16, 50, 84, 95):
            out_df[f"t_est_p{p}"] = res[f"p{p}"]
        out_df["grid_truncated"] = res["flags"]["grid_truncated"]

        st.success("Done!")
        st.dataframe(out_df)

        if out_df["grid_truncated"].any():
            st.warning(
                "Some rows have `grid_truncated = True` -- the upper credible "
                "interval (p84/p95) for those may be understated. See "
                "src/TEXAS/predict_grid.py's module docstring."
            )

        fig, ax = plt.subplots(figsize=(7, 4))
        x = np.arange(len(out_df))
        ax.errorbar(
            x, out_df["t_est_p50"],
            yerr=[out_df["t_est_p50"] - out_df["t_est_p5"], out_df["t_est_p95"] - out_df["t_est_p50"]],
            fmt="o", capsize=4,
        )
        ax.set_xlabel("Observation index")
        ax.set_ylabel("Predicted temperature (degC)")
        ax.set_title("gridT reconstruction (median, 5-95% interval)")
        st.pyplot(fig, clear_figure=True)

        st.download_button(
            "Download results as CSV",
            data=out_df.to_csv(index=False).encode("utf-8"),
            file_name="texas_gridT_results.csv",
            mime="text/csv",
        )
