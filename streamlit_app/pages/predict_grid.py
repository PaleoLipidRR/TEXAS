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
import plotly.graph_objects as go
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
    from TEXAS import predict_proxy_from_T
    _import_error = None
except Exception as e:  # pragma: no cover - defensive, mirrors config.py's pattern
    predict_T_grid = None
    predict_proxy_from_T = None
    _import_error = str(e)

if _import_error:
    st.error(f"Could not import TEXAS: {_import_error}")

# ── 1. Input data ─────────────────────────────────────────────────────────
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

    st.markdown("**Map columns**")
    auto_col = detect_columns(df_in, ["scaledRI", "ri", "RI"]) or df_in.columns[0]
    col_scaledRI = st.selectbox(
        "scaledRI column", options=df_in.columns,
        index=df_in.columns.tolist().index(auto_col),
    )
    opt_gdgt = st.selectbox(
        "gdgt23ratio column (optional -- overrides the G23 slider below per-row)",
        options=["<none>"] + df_in.columns.tolist(), index=0,
    )
    opt_no3 = st.selectbox(
        "no3 column (optional -- overrides the NO3 input below per-row)",
        options=["<none>"] + df_in.columns.tolist(), index=0,
    )

n_obs = len(df_in)

# ── 2. Non-thermal predictors ────────────────────────────────────────────
st.subheader("2. Non-thermal predictors")
st.caption(
    "These shift the curve's location T0 (see README.md's T0_eff formula). "
    "A CSV column selected above overrides these per-row; otherwise the same "
    "value applies to every sample. NO3 correction only applies when "
    "0 < NO3 < no3_cutoff (posterior-specific, e.g. ~1 µmol/L for the bundled "
    "model) -- set NO3 above the cutoff to switch that correction off."
)
pcol1, pcol2 = st.columns(2)
with pcol1:
    g23_val = st.number_input(
        "GDGT-2/3 ratio (G23)", min_value=0.0, value=0.0, step=0.5,
        help="Unbounded ratio (GDGT-2 / GDGT-3), not a fraction -- typically < 30 in practice.",
    )
with pcol2:
    no3_val = st.number_input(
        "NO3 (µmol/L)", min_value=0.0, value=10.0, step=0.1,
    )

if opt_gdgt != "<none>":
    gdgt23ratio_arr = df_in[opt_gdgt].astype(float).values
else:
    gdgt23ratio_arr = np.full(n_obs, g23_val)

if opt_no3 != "<none>":
    no3_arr = df_in[opt_no3].astype(float).values
else:
    no3_arr = np.full(n_obs, no3_val)

# ── 3. Forward posterior ─────────────────────────────────────────────────
st.subheader("3. Forward posterior")
fwd_posterior_name = st.text_input(
    "Forward posterior name",
    value="tx.GHEB.sst.sri03.G23-N1p0",
    help="Bundled with the package by default -- no download required.",
)

# ── 4. Interactive calibration curve ─────────────────────────────────────
st.subheader("4. Calibration curve")
st.caption(
    "Updates live as you move the G23/NO3 controls above. Dotted lines mark "
    "the proxy values from your data; markers appear here after you run a "
    "prediction below."
)

fig_curve = go.Figure()
curve_error = None
if predict_proxy_from_T is not None:
    try:
        T_grid = np.linspace(-5.0, 45.0, 200)
        curve = predict_proxy_from_T(
            temperatures=T_grid,
            posterior=fwd_posterior_name,
            gdgt23ratio=np.full_like(T_grid, g23_val),
            no3=np.full_like(T_grid, no3_val),
            percentiles=[5, 50, 95],
        )
        fig_curve.add_trace(go.Scatter(
            x=np.concatenate([T_grid, T_grid[::-1]]),
            y=np.concatenate([curve["p95"], curve["p5"][::-1]]),
            fill="toself", fillcolor="rgba(31,119,180,0.15)",
            line=dict(width=0), name="5-95% band", hoverinfo="skip",
        ))
        fig_curve.add_trace(go.Scatter(
            x=T_grid, y=curve["p50"], mode="lines",
            line=dict(color="rgb(31,119,180)", width=2), name="median curve",
        ))
        for y in np.unique(df_in[col_scaledRI].astype(float).values):
            fig_curve.add_hline(y=y, line=dict(color="gray", dash="dot", width=1))
    except Exception as e:
        curve_error = str(e)
else:
    curve_error = _import_error

if curve_error:
    st.warning(f"Could not draw calibration curve: {curve_error}")

# ── 5. Inference settings + run ──────────────────────────────────────────
st.subheader("5. Inference settings")
prior_mu_t = st.number_input("prior_mu_t", value=15.0)
prior_sigma_t = st.number_input("prior_sigma_t", value=10.0, min_value=0.01)

disabled = predict_T_grid is None
if st.button("Run gridT prediction", type="primary", disabled=disabled):
    with st.spinner("Running TEXAS.predict_grid.predict_T_grid (grid quadrature)..."):
        try:
            res = predict_T_grid(
                proxyObs=df_in[col_scaledRI].astype(float).values,
                prior_mu_t=float(prior_mu_t),
                prior_sigma_t=float(prior_sigma_t),
                fwd_posterior=fwd_posterior_name,
                predictors={"gdgt23ratio": gdgt23ratio_arr, "no3": no3_arr},
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
        st.session_state["gridT_out_df"] = out_df
        st.session_state["gridT_col_scaledRI"] = col_scaledRI

# Persist the last result across slider tweaks (Streamlit reruns the whole
# script on every widget change) until "Run" is clicked again, and overlay
# it on the calibration curve above.
out_df = st.session_state.get("gridT_out_df")
if out_df is not None and st.session_state.get("gridT_col_scaledRI") == col_scaledRI:
    colors = ["crimson" if t else "rgb(31,119,180)" for t in out_df["grid_truncated"]]
    fig_curve.add_trace(go.Scatter(
        x=out_df["t_est_p50"], y=out_df[col_scaledRI],
        mode="markers", name="prediction (p50)",
        marker=dict(color=colors, size=10, line=dict(color="white", width=1)),
        error_x=dict(
            type="data", symmetric=False,
            array=out_df["t_est_p95"] - out_df["t_est_p50"],
            arrayminus=out_df["t_est_p50"] - out_df["t_est_p5"],
        ),
        hovertext=[
            f"RI={ri:.3f}<br>p50={p50:.1f} degC<br>p5-p95: {p5:.1f}-{p95:.1f}"
            for ri, p50, p5, p95 in zip(
                out_df[col_scaledRI], out_df["t_est_p50"], out_df["t_est_p5"], out_df["t_est_p95"]
            )
        ],
        hoverinfo="text",
    ))

fig_curve.update_layout(
    xaxis_title="Temperature (degC)", yaxis_title="Scaled RI",
    height=460, margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)
st.plotly_chart(fig_curve, use_container_width=True)

if out_df is not None and st.session_state.get("gridT_col_scaledRI") == col_scaledRI:
    st.success("Done!")
    st.dataframe(out_df)

    if out_df["grid_truncated"].any():
        st.warning(
            "Some rows have `grid_truncated = True` -- the upper credible "
            "interval (p84/p95) for those may be understated. See "
            "src/TEXAS/predict_grid.py's module docstring. (Shown in red above.)"
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
