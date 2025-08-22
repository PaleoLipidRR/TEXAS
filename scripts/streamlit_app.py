# streamlit_app.py
import streamlit as st
import xarray as xr
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import truncnorm, beta, gaussian_kde
import proplot as plot

from TEXAS.stan_utils import (
    load_posterior,
    make_ensemble,
    make_forward_ensemble,
)

# ─── SETTINGS ─────────────────────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent / "posterior_cache"

# ─── SIDEBAR ──────────────────────────────────────────────────────────────
st.sidebar.title("Model Selection")

nc_files = sorted(CACHE_DIR.glob("*.nc"))
if not nc_files:
    st.error("No posterior files found in posterior_cache/")
    st.stop()

model_options = [f.stem for f in nc_files]
selected_model = st.sidebar.selectbox("Select posterior model:", model_options)
posterior = load_posterior(selected_model)

# Detect predictors used
used_predictors = [v for v in posterior.data_vars if v.startswith("beta0_")]
predictor_names = [p.replace("beta0_", "") for p in used_predictors]
st.sidebar.markdown("---")
st.sidebar.write("**Optional predictors in model:**")
for name in predictor_names:
    st.sidebar.markdown(f"- {name}")

# ─── MAIN PANEL ────────────────────────────────────────────────────────────
st.title("culRI-Bayesian Model Explorer")
st.markdown(f"### Loaded Model: `{selected_model}`")

# Posterior summaries
st.subheader("Posterior Distributions")
param_cols = ["x0_coretop", "k_coretop", "b_coretop", "sigma_scaledRI_coretop"] + used_predictors
fig, axs = plt.subplots(len(param_cols), 1, figsize=(6, 3 * len(param_cols)))

set_priors_dict = {
    'x0_coretop': {
        'kde': gaussian_kde(truncnorm.rvs(a=-1.8, b=np.inf, loc=30, scale=10, size=4000)),
        'xlim': (0, 100)
    },
    'k_coretop': {
        'kde': gaussian_kde(beta.rvs(2, 5, size=4000)),
        'xlim': (0, 1)
    },
    'b_coretop': {
        'kde': gaussian_kde(beta.rvs(2, 5, size=4000)),
        'xlim': (0, 1)
    },
}

for i, param in enumerate(param_cols):
    if param in set_priors_dict:
        # Plot prior as KDE
        x = np.linspace(*set_priors_dict[param]['xlim'], 500)
        y = set_priors_dict[param]['kde'](x)
        axs[i].plot(x, y, color="orange", label="Prior")
        axs[i].legend()

    # Plot posterior distributions
    if param in posterior.data_vars:
        axs[i].hist(
            posterior[param].values.flatten(),
            bins=30,
            density=True,
            alpha=0.5,
            color="blue",
            label="Posterior"
        )
    else:
        st.error(f"Parameter {param} not found in posterior data.")
        continue

    axs[i].set_title(param)
plt.tight_layout()
st.pyplot(fig)

# ─── FORWARD MODEL: FIT PLOT ───────────────────────────────────────────────
st.subheader("Forward Model Fit")
st.markdown("Showing logistic model predictions on observed data")

uploaded_data = st.file_uploader("Upload coretop dataset (.csv with thermoT and scaledRI columns)", type="csv")
if uploaded_data is not None:
    df = pd.read_csv(uploaded_data)
    if "thermoT" not in df or "scaledRI" not in df:
        st.error("CSV must contain 'thermoT' and 'scaledRI' columns")
    else:
        pred_y = make_forward_ensemble(
            x=df["thermoT"].values,
            posterior=posterior,
            **{name: df[name].values for name in predictor_names if name in df.columns}
        )
        p5 = np.percentile(pred_y, 5, axis=0)
        p50 = np.percentile(pred_y, 50, axis=0)
        p95 = np.percentile(pred_y, 95, axis=0)

        fig2, ax = plt.subplots(figsize=(6, 4))
        ax.fill_between(df["thermoT"], p5, p95, color="teal", alpha=0.2, label="90% CI")
        ax.plot(df["thermoT"], p50, color="teal", label="Median Prediction")
        ax.scatter(df["thermoT"], df["scaledRI"], color="black", s=10, label="Observed")
        ax.set_xlabel("ThermoT")
        ax.set_ylabel("Scaled RI")
        ax.legend()
        st.pyplot(fig2)

# ─── INVERSE PREDICTION ────────────────────────────────────────────────────
st.subheader("Inverse Prediction")

scaledRI_input = st.text_area("Paste scaledRI values (comma-separated)", "0.4, 0.5, 0.6")
try:
    scaledRI_vals = np.array([float(v.strip()) for v in scaledRI_input.split(",")])
    prior_mu = np.full_like(scaledRI_vals, 10.0)
    prior_sigma = 10.0
    # Dummy predictors if needed
    dummy_predictors = {
        name: np.zeros(len(scaledRI_vals)) for name in predictor_names
    }
    pred_T = make_ensemble(
        y=scaledRI_vals,
        posterior=posterior,
        prior_mu_t=prior_mu,
        prior_sig_t=prior_sigma,
        **dummy_predictors
    )
    T_p5 = np.percentile(pred_T, 5, axis=0)
    T_p50 = np.percentile(pred_T, 50, axis=0)
    T_p95 = np.percentile(pred_T, 95, axis=0)

    fig3, ax3 = plt.subplots(figsize=(6, 4))
    ax3.errorbar(scaledRI_vals, T_p50, yerr=[T_p50 - T_p5, T_p95 - T_p50], fmt="o", color="darkorange")
    ax3.set_xlabel("Scaled RI")
    ax3.set_ylabel("Predicted ThermoT")
    st.pyplot(fig3)
except Exception as e:
    st.error(f"Error parsing input or predicting: {e}")
