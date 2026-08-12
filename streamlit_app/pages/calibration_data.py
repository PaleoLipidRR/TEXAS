# pages/calibration_data.py — Calibration dataset visualization tab

import os
import sys
import streamlit as st
import pandas as pd
import numpy as np
import xarray as xr
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FWD_CACHE_DIR

# ── constants ─────────────────────────────────────────────────────────────────

DATA_CSV_NAME = "ds_gridded_screened_global_compilation_finalized.csv"
DATA_SUBDIR = Path("data") / "spreadsheets"

# Human-readable parameter labels (matches manuscript notation).
#
# Checked against the parameters current posteriors actually contain. An entry
# for a name nothing produces is dead, and a parameter with no entry falls back
# to its raw variable name in the UI -- which is how sigma and both bounded-T
# slopes came to be displayed untranslated: `Q_crtp` was removed from every
# model on 2026-03-24, `sigma_scaledRI_crtp` was renamed `sigma_proxyObs_crtp`,
# and the gamma pair arrived with bounded-T and was never added.
PARAM_LABELS = {
    "t0_crtp":              "T₀ — inflection point (°C)",
    "k_crtp":               "k — slope",
    "b_crtp":               "b — lower asymptote",
    "v_crtp":               "ν — asymmetry",
    "sigma_proxyObs_crtp":  "σ — process noise",
    # additive EIV: predictors enter the response, outside the logistic
    "beta_G23_crtp":        "β_{G₂/₃} — GDGT-2/3 coeff. (Scaled RI)",
    "beta_NO3_crtp":        "β_{NO₃} — nitrate coeff. (Scaled RI)",
    # bounded-T: the same predictors enter T₀, inside the logistic, so these
    # are in °C and are not comparable with the β pair above
    "gamma_G23_crtp":       "γ_{G₂/₃} — GDGT-2/3 coeff. (°C)",
    "gamma_NO3_crtp":       "γ_{NO₃} — nitrate coeff. (°C)",
}

DATATYPE_COLORS = {
    "coretop":  "#2196F3",
    "culture":  "#FF7043",
    "mesocosm": "#43A047",
}

# Temperature axis for calibration curve (°C)
_T_RANGE = np.linspace(-5, 40, 300)


# ── helpers ───────────────────────────────────────────────────────────────────

def _find_project_root() -> Path:
    """Walk up from this file to find the TEXAS project root."""
    for parent in Path(__file__).resolve().parents:
        if parent.name == "TEXAS" or (parent / "src" / "TEXAS").exists():
            return parent
    return Path(__file__).resolve().parents[2]   # fallback


from TEXAS.models.logistics import generalized_logistic_fixed_upper


@st.cache_data(show_spinner="Loading calibration dataset…")
def _load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Replace common sentinel value (-999) with NaN for numeric columns
    for col in ["SST", "t_sf2tc_avg", "OPTiMAL_SST", "no3_sf2tc_avg", "scaledRI", "ringIndex"]:
        if col in df.columns:
            df[col] = df[col].where(df[col] > -900, other=np.nan)
    return df


@st.cache_data(show_spinner="Loading posterior…")
def _load_posterior(nc_path: str) -> dict:
    """Return dict of {var_name: flat_array} plus '_attrs'."""
    ds = xr.open_dataset(nc_path)
    out = {v: ds[v].values.flatten() for v in ds.data_vars}
    out["_attrs"] = dict(ds.attrs)
    return out


@st.cache_data(show_spinner="Computing calibration envelope…")
def _compute_curves(nc_path: str, n_subsample: int = 800) -> dict:
    """Compute percentile envelopes of the fitted gen-logi curve."""
    post = _load_posterior(nc_path)
    # Q was removed from every Stan model on 2026-03-24 (the curve now fixes
    # Q=1, so the inflection point is T0). Requiring Q_crtp here meant the check
    # failed for every posterior produced since, and the function returned {} --
    # so the envelope silently stopped drawing, with no error to notice.
    required = ["t0_crtp", "b_crtp", "k_crtp", "v_crtp"]
    if not all(k in post for k in required):
        return {}

    n = len(post["t0_crtp"])
    rng = np.random.default_rng(42)
    idx = rng.choice(n, size=min(n_subsample, n), replace=False)

    # The package's own curve, rather than a copy of it. The copy is how this
    # page drifted out of step with the model in the first place.
    curves = np.stack([
        generalized_logistic_fixed_upper(
            _T_RANGE,
            t0=post["t0_crtp"][j],
            b=post["b_crtp"][j],
            k=post["k_crtp"][j],
            v=post["v_crtp"][j],
        )
        for j in idx
    ])  # (n_subsample, len(_T_RANGE))

    return {
        "p05": np.percentile(curves, 5,  axis=0),
        "p25": np.percentile(curves, 25, axis=0),
        "p50": np.percentile(curves, 50, axis=0),
        "p75": np.percentile(curves, 75, axis=0),
        "p95": np.percentile(curves, 95, axis=0),
    }


# ── figure builders ───────────────────────────────────────────────────────────

def _fig_map(df: pd.DataFrame, color_col: str, show_culmeso: bool) -> go.Figure:
    # Map requires valid coordinates; culture/mesocosm entries typically lack them
    map_df = df.dropna(subset=["Latitude", "Longitude"])
    if not show_culmeso:
        map_df = map_df[map_df["datatype"] == "coretop"]
    map_df = map_df.dropna(subset=[color_col]).copy()

    hover_cols = {
        "Latitude": ":.2f",
        "Longitude": ":.2f",
        color_col: ":.3f",
        "scaledRI": ":.3f",
        "reference_name": True,
        "regionName": True,
    }
    # Only include hover columns that exist
    hover_cols = {k: v for k, v in hover_cols.items() if k in map_df.columns}

    n_coretop = (map_df["datatype"] == "coretop").sum()
    title = (
        f"Calibration sites: {len(map_df):,} total  |  "
        f"{n_coretop:,} coretop"
    )

    fig = px.scatter_geo(
        map_df,
        lat="Latitude",
        lon="Longitude",
        color=color_col,
        color_continuous_scale="RdYlBu_r" if color_col == "SST" else "Viridis",
        range_color=[
            map_df[color_col].quantile(0.02),
            map_df[color_col].quantile(0.98),
        ],
        symbol="datatype" if show_culmeso else None,
        hover_data=hover_cols,
        projection="natural earth",
        title=title,
    )
    fig.update_geos(
        showcoastlines=True, coastlinecolor="#aaaaaa",
        showland=True, landcolor="#F5F5F0",
        showocean=True, oceancolor="#EAF4FB",
        showframe=False,
        showcountries=False,
    )
    fig.update_coloraxes(colorbar_title=color_col)
    fig.update_traces(marker=dict(size=5, opacity=0.72))
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=460)
    return fig


def _fig_scatter(
    df: pd.DataFrame,
    temp_col: str,
    show_culmeso: bool,
    curves: dict,
) -> go.Figure:
    fig = go.Figure()

    # ── data points ─────────────────────────────────────────
    datatypes = (
        ["coretop", "culture", "mesocosm"] if show_culmeso else ["coretop"]
    )
    for dtype in datatypes:
        sub = df[(df["datatype"] == dtype) & df[temp_col].notna() & df["scaledRI"].notna()]
        if sub.empty:
            continue
        hover = (
            sub.get("reference_name", pd.Series("", index=sub.index)).astype(str)
            + "<br>T = " + sub[temp_col].round(2).astype(str) + " °C"
            + "<br>Scaled RI = " + sub["scaledRI"].round(4).astype(str)
        )
        fig.add_trace(go.Scatter(
            x=sub[temp_col],
            y=sub["scaledRI"],
            mode="markers",
            name=dtype.capitalize(),
            marker=dict(
                color=DATATYPE_COLORS.get(dtype, "#888"),
                size=5, opacity=0.55,
                line=dict(width=0.4, color="white"),
            ),
            hovertext=hover,
            hoverinfo="text",
        ))

    # ── posterior calibration envelope ──────────────────────
    if curves:
        t_rev = _T_RANGE[::-1]

        # 90% CI band
        fig.add_trace(go.Scatter(
            x=np.concatenate([_T_RANGE, t_rev]),
            y=np.concatenate([curves["p95"], curves["p05"][::-1]]),
            fill="toself",
            fillcolor="rgba(80, 80, 200, 0.10)",
            line=dict(color="rgba(0,0,0,0)"),
            name="90% CI",
            hoverinfo="skip",
        ))
        # 50% CI band
        fig.add_trace(go.Scatter(
            x=np.concatenate([_T_RANGE, t_rev]),
            y=np.concatenate([curves["p75"], curves["p25"][::-1]]),
            fill="toself",
            fillcolor="rgba(80, 80, 200, 0.20)",
            line=dict(color="rgba(0,0,0,0)"),
            name="50% CI",
            hoverinfo="skip",
        ))
        # Median
        fig.add_trace(go.Scatter(
            x=_T_RANGE,
            y=curves["p50"],
            mode="lines",
            line=dict(color="#1a237e", width=2.5),
            name="Median fit",
        ))

    fig.update_layout(
        xaxis_title=f"Temperature (°C)  [{temp_col}]",
        yaxis_title="Scaled Ring Index",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
        ),
        hovermode="closest",
        height=480,
        margin=dict(l=60, r=20, t=50, b=60),
    )
    return fig


def _fig_posteriors(post: dict) -> go.Figure | None:
    param_keys = [k for k in PARAM_LABELS if k in post]
    if not param_keys:
        return None

    ncols = min(4, len(param_keys))
    nrows = (len(param_keys) + ncols - 1) // ncols
    subplot_titles = [PARAM_LABELS[k] for k in param_keys]

    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=subplot_titles)

    for idx, key in enumerate(param_keys):
        row = idx // ncols + 1
        col = idx % ncols + 1
        vals = post[key]

        fig.add_trace(
            go.Histogram(
                x=vals,
                nbinsx=60,
                marker_color="#5c7cfa",
                opacity=0.80,
                name=PARAM_LABELS[key],
                showlegend=False,
                hovertemplate=f"{key}<br>value=%{{x:.4f}}<extra></extra>",
            ),
            row=row, col=col,
        )
        # Median dashed line
        med = float(np.median(vals))
        fig.add_vline(
            x=med,
            line_dash="dash",
            line_color="#e53935",
            line_width=1.5,
            row=row, col=col,
        )

    fig.update_layout(
        height=260 * nrows,
        margin=dict(l=40, r=20, t=60, b=40),
        bargap=0.05,
    )
    return fig


# ── main render function ──────────────────────────────────────────────────────

def render_calibration_tab(fwd_cache_dir: str):
    """Render the Calibration Dataset tab (map + scatter + posteriors)."""

    # ── locate data file ──────────────────────────────────────
    root = _find_project_root()
    csv_path = root / DATA_SUBDIR / DATA_CSV_NAME

    if not csv_path.exists():
        st.error(
            f"Calibration CSV not found at `{csv_path}`.\n\n"
            "Expected: `data/spreadsheets/ds_gridded_screened_global_compilation_finalized.csv`"
        )
        return

    df = _load_data(str(csv_path))
    n_coretop = int((df["datatype"] == "coretop").sum())

    # ── locate posterior cache ────────────────────────────────
    cache_path = Path(fwd_cache_dir)
    nc_files = sorted(cache_path.glob("*.nc")) if cache_path.exists() else []
    nc_names = [f.name for f in nc_files]

    # ── summary metrics ───────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Coretop sites", f"{n_coretop:,}")
    col2.metric("Culture samples", f"{(df['datatype']=='culture').sum():,}")
    col3.metric("Mesocosm samples", f"{(df['datatype']=='mesocosm').sum():,}")
    col4.metric("Posterior files", len(nc_names))

    st.divider()

    # ══════════════════════════════════════════════════════════
    # SECTION 1 — Global coretop map
    # ══════════════════════════════════════════════════════════
    st.markdown("### 1 — Global site distribution")

    with st.expander("Map options", expanded=False):
        mc1, mc2 = st.columns(2)
        color_col_map = mc1.selectbox(
            "Color by",
            [c for c in ["SST", "scaledRI", "modernWaterDepth", "gdgt23ratio"]
             if c in df.columns],
            index=0,
            key="map_color",
        )
        show_culmeso_map = mc2.checkbox(
            "Show culture / mesocosm", value=False, key="map_culmeso"
        )

    fig_map = _fig_map(df, color_col_map, show_culmeso_map)
    st.plotly_chart(fig_map, use_container_width=True)

    st.divider()

    # ══════════════════════════════════════════════════════════
    # SECTION 2 — Calibration scatter + fitted curve
    # ══════════════════════════════════════════════════════════
    st.markdown("### 2 — Scaled RI vs Temperature")

    s_left, s_right = st.columns([3, 1])

    with s_right:
        temp_options = [
            c for c in ["SST", "t_sf2tc_avg", "OPTiMAL_SST"] if c in df.columns
        ]
        temp_col = st.selectbox("Temperature column", temp_options, index=0)
        show_culmeso_scatter = st.checkbox(
            "Show culture / mesocosm", value=True, key="scatter_culmeso"
        )

        st.markdown("**Overlay posterior curve**")
        if nc_names:
            sel_nc_scatter = st.selectbox(
                "Posterior", ["(none)"] + nc_names, index=0, key="scatter_nc"
            )
        else:
            st.info("No `.nc` files in cache.")
            sel_nc_scatter = "(none)"

    curves = {}
    if sel_nc_scatter != "(none)":
        curves = _compute_curves(str(cache_path / sel_nc_scatter))

    fig_scatter = _fig_scatter(df, temp_col, show_culmeso_scatter, curves)
    s_left.plotly_chart(fig_scatter, use_container_width=True)

    st.divider()

    # ══════════════════════════════════════════════════════════
    # SECTION 3 — Forward model parameter posteriors
    # ══════════════════════════════════════════════════════════
    st.markdown("### 3 — Forward model posteriors")

    if not nc_names:
        st.info(
            "No forward posterior `.nc` files found in "
            f"`{fwd_cache_dir}`. Run a forward calibration first."
        )
        return

    p_left, p_right = st.columns([3, 1])

    with p_right:
        sel_nc_post = st.selectbox(
            "Posterior file", nc_names, index=0, key="post_nc"
        )
        post = _load_posterior(str(cache_path / sel_nc_post))
        attrs = post.get("_attrs", {})

        st.markdown("**Run info**")
        st.caption(f"Model: `{attrs.get('stan_model_name', '—')}`")
        st.caption(f"Temp type: `{attrs.get('temptype', '—')}`")
        st.caption(f"N coretop: `{attrs.get('N_crtp', '—')}`")
        st.caption(f"Draws: {len(post.get('t0_crtp', [])):,}")

        st.markdown("**Diagnostics**")
        rhat = attrs.get("stan_diag_max_rhat", None)
        ess  = attrs.get("stan_diag_min_ess_bulk", None)
        div  = attrs.get("stan_diag_n_divergent", None)
        if rhat is not None:
            st.caption(f"R-hat max: `{rhat}`")
        if ess is not None:
            st.caption(f"ESS min: `{ess}`")
        if div is not None:
            label = "✓" if div == 0 else "⚠"
            st.caption(f"Divergences: {label} `{div}`")

        overall = attrs.get("stan_diag_overall_status", "")
        if overall == "OK":
            st.success("Overall: OK")
        elif overall:
            st.warning(f"Overall: {overall}")

        # Per-parameter summary table
        param_keys = [k for k in PARAM_LABELS if k in post]
        if param_keys:
            rows = []
            for k in param_keys:
                v = post[k]
                rows.append({
                    "param": k.replace("_crtp", ""),
                    "median": round(float(np.median(v)), 4),
                    "std":    round(float(np.std(v)), 4),
                })
            st.dataframe(
                pd.DataFrame(rows).set_index("param"),
                use_container_width=True,
            )

    with p_left:
        fig_post = _fig_posteriors(post)
        if fig_post:
            st.plotly_chart(fig_post, use_container_width=True)
        else:
            st.warning("No recognizable CRTP parameters found in this posterior file.")
