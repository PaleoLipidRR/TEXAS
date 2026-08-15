# TEXAS

**TetraEther indeX of Ammonia oxidizerS — Bayesian proxy system model for TEX86 paleothermometry**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/PaleoLipidRR/TEXAS/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/texas-psm)](https://pypi.org/project/texas-psm/)
[![Zenodo](https://img.shields.io/badge/data-10.5281%2Fzenodo.20032542-blue.svg)](https://doi.org/10.5281/zenodo.20032542)

TEXAS-PSM is a **Bayesian proxy system model (PSM)** for TEX86-based sea surface temperature (SST) reconstruction, built around the **TEXAS** sensor model. It fits hierarchical generalized-logistic Stan models to isoGDGT Ring Index data — with optional non-thermal corrections for GDGT-2/3 ratio (AOA ecology) and NO₃ (nutrient effect) — and reconstructs paleotemperatures with full posterior uncertainty.

The result is a **posterior distribution of temperature** for each downcore sample, not just a point estimate with a fixed RMSE.

---

## How it works

TEXAS uses a two-stage workflow:

**Stage 1 — Forward calibration** fits a hierarchical Bayesian generalized logistic curve to modern culture, mesocosm, and coretop Ring Index–temperature data. The output is a posterior distribution of calibration parameters saved as a `.nc` file. Pre-computed posteriors are available on Zenodo — most users can skip this stage entirely.

**Stage 2 — Inverse reconstruction** passes your downcore Scaled RI measurements through the forward posterior, marginalizing over all calibration parameter uncertainty, and returns a full temperature posterior per sample.

---

## Quickstart

### Install

```bash
pip install texas-psm
# or, with uv:  uv add texas-psm
```

Or open the interactive notebook in Google Colab — no installation needed:

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/PaleoLipidRR/TEXAS/blob/main/notebooks/quickstart_demo.ipynb)

For Docker, conda-lock, uv, and development installs see [Installation](installation.md).

---

### Step 1 — Compute Scaled Ring Index

Before prediction you need **Scaled Ring Index** (RI₀₋₃) values. Pass raw LC/MS peak areas or fractional abundances — the formula normalises by the six-GDGT total, so either works:

```python
import pandas as pd
from TEXAS import compute_scaledRI

df = pd.read_csv("my_gdgt_data.csv")

df["scaledRI_cren3"] = compute_scaledRI(
    df["GDGT-0"], df["GDGT-1"], df["GDGT-2"], df["GDGT-3"],
    df["cren"],   df["cren_prime"],   # cren_rings=3 by default → RI₀₋₃
)
```

!!! note "Which Ring Index convention?"
    The canonical TEXAS posteriors are calibrated against **RI₀₋₃** (`cren_rings=3`, crenarchaeol counted as 3 rings). Pass `cren_rings=4` to reproduce the RI₀₋₄ convention of Zhang et al. (2016), but the canonical posteriors were **not** calibrated against that convention.

---

### Step 1b — Screen your proxy data (recommended)

Use Mahalanobis distance to flag samples that fall outside the modern coretop calibration domain before running the inverse reconstruction. The detector is fit on the **screened coretop training data** (low-G23 subset: `gdgt23ratio ≤ 5`) using `TEX86` and `scaledRI_cren3` as features. Samples in the paleo record whose distance exceeds the chi-squared threshold are flagged; `detect_outliers_manual()` additionally preserves warm end-member samples (high RI + high TEX86) that lie outside the ellipse.

```python
import pandas as pd
import matplotlib.pyplot as plt
import TEXAS
from TEXAS.utils.paths import SPREADSHEETS_DIR
from TEXAS.data import MahalanobisOutlierDetector

# Download training data from Zenodo (~1.8 MB, skipped if already cached)
TEXAS.download_training_data()

# Load combined dataset; keep coretop rows only
combined_df = pd.read_csv(SPREADSHEETS_DIR / 'combined_coretop_culture_mesocosm_rev20260210.csv')
coretop_df = combined_df[combined_df['datatype'] == 'coretop']

# Fit on low-G23 coretops (gdgt23ratio ≤ 5 excludes ecology-dominated samples)
detector = MahalanobisOutlierDetector(['TEX86', 'scaledRI_cren3'], confidence=0.9)
detector.fit(coretop_df[coretop_df['gdgt23ratio'] <= 5])
print(f"Fitted on {int((coretop_df['gdgt23ratio'] <= 5).sum())} coretop samples (gdgt23ratio ≤ 5)")
print(f"Mahalanobis threshold (90% CI): {detector.threshold:.3f}")

# Apply to your downcore data — requires TEX86 and scaledRI_cren3 columns
df['TEXRI_cren3_mahalDist_low23ratio_outliers_manual'] = detector.detect_outliers_manual(df)
n_out = int(df['TEXRI_cren3_mahalDist_low23ratio_outliers_manual'].sum())
print(f"Screened out: {n_out} / {len(df)} samples")

# Visualise — 90% confidence ellipse with inliers/outliers colour-coded
fig, ax = plt.subplots(figsize=(5, 4))
detector.plot_decision_boundary(df, ax=ax)
ax.set_xlabel("TEX$_{86}$")
ax.set_ylabel(r"Scaled RI$_{0-3}$")
ax.set_title("Mahalanobis screening (90% CI)")
plt.tight_layout()
plt.show()

# Keep only inliers
df_screened = df[df['TEXRI_cren3_mahalDist_low23ratio_outliers_manual'] == False].reset_index(drop=True)
```

---

### Step 2 — Download a forward posterior

Pre-computed posteriors are hosted on [Zenodo](https://doi.org/10.5281/zenodo.20032542). Download only what you need:

```python
import TEXAS

# Univariate SST — recommended starting point (~0.3 MB)
TEXAS.download_posteriors(["tx.GHPU.sst.sri03.p0"])

# Multivariate EIV (GDGT-2/3 + NO₃ corrections) — ~78 MB each
TEXAS.download_posteriors([
    "tx.GHEA.sst.sri03.G23-N10",
])

# Or download everything at once (~158 MB total)
TEXAS.download_all()

# Check what is already cached
TEXAS.list_posteriors()
```

Available forward posteriors:

| Name (no `.nc`) | Model | Temperature | Size |
|---|---|---|---|
| `tx.GCDU.cul.sri03.p0` | Culture + mesocosm | Culture T | <1 MB |
| `tx.GHPU.sst.sri03.p0` | Univariate coretop | SST | <1 MB |
| `tx.GHPU.thm.sri03.p0` | Univariate coretop | Thermo T | <1 MB |
| `tx.GHEA.sst.sri03.G23-N10` | EIV multivariate coretop | SST | ~78 MB |
| `tx.GHEA.thm.sri03.G23-N10` | EIV multivariate coretop | Thermo T | ~78 MB |

The Zenodo record's flat files still carry the pre-revision legacy names
(e.g. `gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc`).
`download_posteriors()` and `load_posterior()` accept **either** spelling —
downloads are unpacked into the case-directory layout shown below.

#### How posterior files are named

Posteriors use CESM-style **case ids**: fixed dot-delimited positions instead
of ever-growing concatenated descriptions.

```
tx . GHEB . sst . sri03 . G23-N10 . fwd.nc
│    │      │     │       │         └ role: fwd = forward calibration;
│    │      │     │       │           inv.<site>.<tags> = a reconstruction
│    │      │     │       └ predictors: G23, N10 (NO₃ with cutoff 1.0), p0 = none
│    │      │     └ proxy: sri03 = scaledRI_cren3, sri = scaledRI, tex = TEX86
│    │      └ target temperature: sst, thm (Thermo-T), cul (culture T)
│    └ compset — the model recipe, one letter per axis (see table)
└ project prefix
```

The four **compset** letters encode, in order:

| Axis | Letters |
|---|---|
| Curve | `G` generalized logistic · `L` logistic · `N` linear |
| Training set | `H` hierarchical coretop · `C` culture+mesocosm · `J` culture+mesocosm+coretop · `T` coretop-only |
| Estimator | `P` priorApprox · `E` priorApprox + errors-in-variables · `D` full hierarchical |
| Predictor structure | `U` univariate · `A` additive (β on the response, unbounded) · `B` bounded-by-construction (the **T₀-shift** structure: γ on T₀) |

So `tx.GHEB.sst.sri03.G23-N10` is the published T₀-shift multivariate SST
calibration, and `tx.GHPU.sst.sri03.p0` the univariate SST one. A date/run
token may be appended to distinguish refits of the same configuration. Every
function that takes a posterior name resolves case ids and legacy long names
alike.

```{warning}
**The two multivariate posteriors above are the response-offset formulation, not
the T₀-shift one** — they are the preprint's calibration (see the
[preprint archive page](preprint_additive_archive.md)). They carry
`beta_G23_crtp` / `beta_NO3_crtp`, in Scaled-RI
units per predictor unit. The current calibration applies the predictors inside
the logistic instead, as a shift of T₀ in °C
(`gamma_G23_crtp` / `gamma_NO3_crtp` — see
[Running forward calibration from scratch](#running-forward-calibration-from-scratch)
below). The T₀-shift
posteriors are published with the v1.0.0 Zenodo record; until then, refit locally
with `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift` if you need them.
The univariate and culture/mesocosm posteriors listed above are unaffected —
they have no non-thermal predictors.
```

---

### Step 3 — Forward prediction (temperature → proxy)

Useful for plotting the calibration curve and its uncertainty envelope:

```python
import numpy as np
from TEXAS import predict_proxy_from_T

result = predict_proxy_from_T(
    temperatures=np.linspace(5, 35, 100),
    posterior="tx.GHPU.sst.sri03.p0",
)
result["p50"]   # median Scaled RI (numpy array, length 100)
result["p5"]    # 5th percentile
result["p95"]   # 95th percentile
```

---

### Step 4 — Inverse reconstruction (proxy → temperature)

=== "Univariate"

    ```python
    from TEXAS import predict_T_from_proxyObs

    result = predict_T_from_proxyObs(
        proxyObs=df["scaledRI_cren3"].values,
        prior_mu_t=15.0,        # prior mean temperature (°C) — geological estimate
        prior_sigma_t=10.0,     # prior uncertainty (°C) — use wide prior if unsure
        fwd_posterior="tx.GHPU.sst.sri03.p0",
        temptype="SST",
    )
    result["p50"]   # median SST (°C), one value per sample
    result["p5"]    # 5th percentile
    result["p95"]   # 95th percentile
    ```

=== "Multivariate (GDGT-2/3 + NO₃)"

    ```python
    result = predict_T_from_proxyObs(
        proxyObs=df["scaledRI_cren3"].values,
        prior_mu_t=15.0,
        prior_sigma_t=10.0,
        fwd_posterior="tx.GHEA.sst.sri03.G23-N10",
        temptype="SST",
        gdgt23ratio=df["gdgt23ratio"].values,
        no3=df["no3"].values,   # µmol/L; scalar or per-sample array
    )
    ```

=== "NO₃ from WOA23 climatology"

    ```python
    import xarray as xr

    ocean_ds = xr.load_dataset("ocean_prop_ds.nc")  # WOA23-derived, from SI_code1

    result = predict_T_from_proxyObs(
        proxyObs=df["scaledRI_cren3"].values,
        prior_mu_t=15.0, prior_sigma_t=10.0,
        fwd_posterior="tx.GHEA.sst.sri03.G23-N10",
        temptype="SST",
        gdgt23ratio=df["gdgt23ratio"].values,
        site_lat=15.3, site_lon=-23.7,   # modern drill-site coordinates
        no3_dataset=ocean_ds,
    )
    # Prints: WOA23 NO₃ lookup: lat=15.3, lon=-23.7 → 0.42 µmol/L
    ```

=== "Load from disk / Google Drive"

    If you have a posterior `.nc` file locally or on Google Drive, pass it directly — no cache lookup, no download:

    ```python
    import xarray as xr
    from TEXAS import predict_T_from_proxyObs

    # Colab: mount Google Drive first, then load
    # (files downloaded straight from Zenodo keep the archived legacy name)
    ds = xr.load_dataset("/content/drive/MyDrive/posteriors/gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc")

    result = predict_T_from_proxyObs(
        proxyObs=df["scaledRI_cren3"].values,
        prior_mu_t=15.0, prior_sigma_t=10.0,
        fwd_posterior=ds,    # xr.Dataset — skips all file I/O
        temptype="SST",
    )
    ```

---

### Saving results

By default `predict_T_from_proxyObs` returns a dict in memory and writes nothing to disk. Pass `save_results=True` to persist:

```python
result = predict_T_from_proxyObs(
    ...,
    save_results=True,            # writes quantile .nc + .npz
    save_draws=True,              # also saves raw MCMC draws as _draws.nc
    cache_dir="/your/output/",    # default: ~/.texas/cache/TEXAS_invT_posterior_cache/
)
```

---

## Running forward calibration from scratch

Only needed if you want to re-fit the model to your own data or reproduce the published calibration. Requires CmdStan and the GDGT training database (`TEXAS.download_training_data()`).

```python
from TEXAS import build_fwd_data, get_posterior, save_posterior

data = build_fwd_data(
    t_cul=cul_df["SST"].values,       proxy_cul=cul_df["scaledRI"].values,
    t_meso=meso_df["SST"].values,     proxy_meso=meso_df["scaledRI"].values,
    t_crtp=crtp_df["SST"].values,     proxy_crtp=crtp_df["scaledRI"].values,
    gdgt23ratio_crtp=crtp_df["gdgt23ratio"].values,
    no3_crtp=crtp_df["no3"].values,   # no3_cutoff auto-calculated via Spearman if omitted
)

posterior, diagnostics = get_posterior(
    data,
    stan_file="gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift",
    temptype="SST",
    proxy_name="scaledRI_cren3",
)
save_posterior(posterior)
```

`..._eiv_t0shift` is the published calibration. The non-thermal predictors enter
inside the logistic, shifting the curve's location parameter T₀ rather than adding
an offset to the response:

```
T₀_eff = T₀ + γ_{G₂/₃}·G₂/₃ + γ_{NO₃}·log₁₀(NO₃)
Scaled RI = b + (1 − b) / (1 + exp(−k·(T − T₀_eff)))^(1/ν)
```

so the fitted coefficients are `gamma_G23_crtp` and `gamma_NO3_crtp`, in °C per
predictor unit, and the predicted Scaled RI is confined to (b, 1) by construction.
`R2_thermal` must be supplied to this model — compute it from a thermal-only
coretop fit with `gen_logi_fixed_hier_crtp_univ_priorApprox`.

---

## Citation

If you use TEXAS in published work, please cite:

> Rattanasriampaipong, R. et al. (in prep). *TEXAS: A proxy system model for TEX86 paleothermometry.* AGU Paleoceanography and Paleoclimatology.

See [`CITATION.cff`](https://github.com/PaleoLipidRR/TEXAS/blob/main/CITATION.cff) for machine-readable metadata.
