# TEXAS

**TetraEther indeX of Ammonia oxidizerS — Bayesian proxy system model for TEX86 paleothermometry**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/PaleoLipidRR/TEXAS/blob/main/LICENSE) [![PyPI](https://img.shields.io/pypi/v/texas-psm)](https://pypi.org/project/texas-psm/) [![Zenodo](https://img.shields.io/badge/data-10.5281%2Fzenodo.19666744-blue.svg)](https://doi.org/10.5281/zenodo.19666744)

TEXAS-PSM is a **Bayesian proxy system model (PSM)** for isoGDGT-based (TEX₈₆-family) ocean temperature reconstruction, built around the **TEXAS** sensor model. TEXAS links temperature to the **Scaled Ring Index** (Scaled RI) through a hierarchical generalized-logistic (S-shaped) curve, fitted in Stan to culture, mesocosm, and coretop data. Two optional nonthermal predictors account for archaeal community structure (the GDGT-2/GDGT-3 ratio, G₂/₃) and nutrient availability (nitrate, NO₃⁻). The package reconstructs either sea surface temperature (SST) or surface-to-thermocline temperature (Thermo-T), with full posterior uncertainty.

Of the three PSM submodels (sensor, archive, observation), this package implements the **sensor** and propagates **analytical** measurement uncertainty; sediment-archive effects (bioturbation, diagenesis) and age-model uncertainty are left to dedicated tools.

The result is a **posterior distribution of temperature** for each downcore sample, not just a point estimate with a fixed RMSE.

To see how one measurement becomes that distribution, without installing anything, try [From GDGTs to sea temperature](gdgts_to_temperature.md).

---

## How it works

TEXAS uses a two-stage workflow:

**Stage 1 — Forward calibration** fits a hierarchical Bayesian generalized logistic curve (temperature → Scaled RI) to modern culture, mesocosm, and coretop data. The output is a posterior distribution of calibration parameters saved as a `.nc` file. Pre-computed posteriors ship with the package (the defaults) or download from Zenodo — most users can skip this stage entirely.

**Stage 2 — Inverse reconstruction** passes your downcore Scaled RI measurements through the forward posterior, marginalizing over all calibration parameter uncertainty, and returns a full temperature posterior per sample.

---

## Quickstart

### Install

```bash
pip install texas-psm            # inside a virtual environment
# or, with uv:  uv pip install texas-psm   (or `uv add texas-psm` in a uv project)
```

Or open the interactive notebook in Google Colab — no installation needed:

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/PaleoLipidRR/TEXAS/blob/main/notebooks/quickstart_demo.ipynb)

That is all you need to use TEXAS on your own data. To fork the repository or run the manuscript notebooks (`uv sync` from a clone, Docker, or conda), see [Installation](installation.md).

---

### Step 1 — Compute Scaled Ring Index

Before prediction you need **Scaled Ring Index** (RI₀₋₃) values. Pass raw LC/MS peak areas or fractional abundances — the formula normalizes by the six-GDGT total, so either works:

```python
import pandas as pd
from TEXAS import compute_scaledRI

df = pd.read_csv("my_gdgt_data.csv")

df["scaledRI_cren3"] = compute_scaledRI(
    df["GDGT-0"], df["GDGT-1"], df["GDGT-2"], df["GDGT-3"],
    df["cren"],   df["cren_prime"],   # cren_weight=3 by default → RI₀₋₃
)
```

`````{admonition} Which Ring Index convention?
:class: note

The canonical TEXAS posteriors are calibrated against **RI₀₋₃** (`cren_weight=3`, crenarchaeol and its regioisomer weighted 3). Pass `cren_weight=4` to reproduce the RI₀₋₄ convention of Zhang et al. (2016), but the canonical posteriors were **not** calibrated against that convention — the weight also sets the scale the index is expressed on, so the two are not interchangeable inputs.

`cren_weight` was called `cren_rings` before 2026-08-21. The old keyword still works and warns.
`````

---

### Step 1b — Screen your proxy data (recommended)

Use the Mahalanobis-distance criterion the calibration itself was built with (manuscript Section 5.1) to flag samples that fall outside the modern coretop calibration domain. `from_calibration()` loads the **published** 90 % χ² ellipse in TEX₈₆ × Scaled RI space — fitted on the low-G₂/₃ coretops (`gdgt23ratio ≤ 5`) — so nothing is downloaded and nothing is refit. A flagged sample is an extrapolation, not necessarily a bad sample: past assemblages may genuinely occupy a region with no modern analogue, so the recommendation is to flag and interpret with caution, not to exclude.

```python
import matplotlib.pyplot as plt
from TEXAS.data import MahalanobisOutlierDetector

cols = {"TEX86": "<your_tex86_column>", "scaledRI_cren3": "<your_scaled_RI_column>"}

detector = MahalanobisOutlierDetector.from_calibration(confidence=0.90)
df["mahal_dist"] = detector.transform(df, columns=cols)
df["flagged"] = detector.detect_outliers_manual(df, columns=cols)   # keeps warm end-members (TEX86 > 0.75 and Scaled RI > 0.75)
print(f"Flagged: {int(df['flagged'].sum())} / {len(df)} samples")

# Visualize — 90% confidence ellipse with inliers/outliers color-coded
fig, ax = plt.subplots(figsize=(5, 4))
detector.plot_decision_boundary(df, ax=ax, columns=cols)
ax.set_xlabel("TEX$_{86}$")
ax.set_ylabel(r"Scaled RI$_{0-3}$")
plt.tight_layout()
plt.show()
```

Raising `confidence` (e.g. to 0.99) widens the ellipse so that only strong departures are flagged. The `outside_domain` column of `result["flags"]` applies the same criterion automatically when `tex86=` is passed to `predict_T_from_proxyObs`; the other quality flags (unattainable proxy values, extrapolated predictors, prior-dominated posteriors) are described on the [PSM page](PSM.md#8-reconstructing-temperature-from-proxy-observations) and demonstrated in the quickstart notebook.

---

### Step 2 — Choose a calibration posterior

**You can skip this step.** Four calibrations ship inside the package — the full multivariate T₀-shift fit and its thermal-only counterpart, each for both temperature targets — so a reconstruction needs no download and no network access. TEXAS picks between them from what you pass:

```python
from TEXAS import predict_T_from_proxyObs

result = predict_T_from_proxyObs(          # fwd_posterior omitted →
    proxyObs=df["scaledRI_cren3"].values,  # tx.GHEB.sst.sri03.G23-N1p0
    prior_mu_t=15.0, prior_sigma_t=10.0,
    gdgt23ratio=df["gdgt23ratio"].values,
    no3=df["no3"].values,
)
```

If you supply **no** predictors, TEXAS uses the thermal-only calibration instead and warns that it has done so:

```python
result = predict_T_from_proxyObs(          # no predictors →
    proxyObs=df["scaledRI_cren3"].values,  # tx.GHPU.sst.sri03.p0
    prior_mu_t=15.0, prior_sigma_t=10.0,
)
```

Read that warning rather than dismissing it. The thermal-only fit is a *different* calibration, not the multivariate one with its corrections switched off: the non-thermal effects are in the core-top data either way, and a univariate fit absorbs them into its thermal parameters. Its reconstructions will not match the ones the manuscript reports. Supplying one predictor but not the other raises instead, since that is more likely a mistake than a choice.

Pass `temptype="thermoT"` to get the thermocline-integrated calibration instead; both the multivariate and thermal-only versions of it ship too. Any other posterior is fetched once from [Zenodo](https://doi.org/10.5281/zenodo.19666744) and cached:

```python
import TEXAS

# Culture + mesocosm calibration (<1 MB)
TEXAS.download_posteriors(["tx.GCDU.cul.sri03.p0"])

# Everything in the current Zenodo record (~510 MB: ~475 MB of posteriors,
# of which the six T₀-shift posteriors with predictors are ~78-81 MB each,
# plus ~37 MB of training data)
TEXAS.download_all()

# What you already have — bundled and downloaded alike
TEXAS.list_posteriors()
```

Available forward posteriors:

| Name (no `.nc`) | Model | Predictors | Temperature | In package? | Zenodo size |
|---|---|---|---|---|---|
| `tx.GHEB.sst.sri03.G23-N1p0` | **T₀-shift coretop — the published calibration (default)** | G₂/₃ + NO₃⁻ | SST | **bundled** | ~78 MB |
| `tx.GHEB.thm.sri03.G23-N1p0` | **T₀-shift coretop — the published calibration (default)** | G₂/₃ + NO₃⁻ | Thermo-T | **bundled** | ~78 MB |
| `tx.GHPU.sst.sri03.p0` | Temperature-only coretop | none | SST | **bundled** | 0.3 MB |
| `tx.GHPU.thm.sri03.p0` | Temperature-only coretop | none | Thermo-T | **bundled** | 0.3 MB |
| `tx.GHEB.sst.sri03.G23` | T₀-shift coretop, single predictor | G₂/₃ | SST | download | ~78 MB |
| `tx.GHEB.thm.sri03.G23` | T₀-shift coretop, single predictor | G₂/₃ | Thermo-T | download | ~78 MB |
| `tx.GHEB.sst.sri03.N1p0` | T₀-shift coretop, single predictor | NO₃⁻ | SST | download | ~81 MB |
| `tx.GHEB.thm.sri03.N1p0` | T₀-shift coretop, single predictor | NO₃⁻ | Thermo-T | download | ~81 MB |
| `tx.GCDU.cul.sri03.p0` | Culture + mesocosm (the curve's top layer) | none | Culture T | download | 0.2 MB |
| `tx.GHEA.sst.sri03.G23-N1p0` | Additive (response-offset) coretop — initial submission, superseded | G₂/₃ + NO₃⁻ | SST | download (v0.2.0 record) | ~78 MB |
| `tx.GHEA.thm.sri03.G23-N1p0` | Additive (response-offset) coretop — initial submission, superseded | G₂/₃ + NO₃⁻ | Thermo-T | download (v0.2.0 record) | ~78 MB |

“Bundled” posteriors are installed with `pip install texas-psm` and need no network access. The default needs **both** predictors and refuses to run if one is missing (a missing value is never treated as zero). To switch the nitrate term off, pass a value above the cutoff, e.g. `no3=10`. Use a single-predictor calibration when only one nonthermal predictor applies to your record.

The bundled pair is the same posterior as the archived one with the error-in-variables model's per-site latent variables removed — everything the forward and inverse models read is present and unmodified, which is what takes the file from ~80 MB to 0.37 MB. The complete versions, latents included, are archived on Zenodo with the release record that the paper cites.

From **v0.3.0** the Zenodo record's flat files are named by case id (`tx.GHPU.sst.sri03.p0.fwd.nc`). Version 0.2.0 of the record — the initial submission's additive fits — carries the older names instead (e.g. `gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc`), and `download_posteriors()` still resolves those, pinned to that version, so preprint-era notebooks keep working. `load_posterior()` accepts **either** spelling, and downloads are saved flat in the cache as `<case id>.fwd.nc`.

#### How posterior files are named

Posteriors use CESM-style **case ids**: fixed dot-delimited positions instead of ever-growing concatenated descriptions.

```
tx . GHEB . sst . sri03 . G23-N1p0 . fwd.nc
│    │      │     │       │         └ role: fwd = forward calibration;
│    │      │     │       │           inv.<site>.<tags> = a reconstruction
│    │      │     │       └ predictors: G23, N1p0 (NO₃, cutoff 1.0 — `p`
│    │      │     │         is the decimal point), p0 = none
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

So `tx.GHEB.sst.sri03.G23-N1p0` is the published T₀-shift multivariate SST calibration, and `tx.GHPU.sst.sri03.p0` the univariate SST one. A date/run token may be appended to distinguish refits of the same configuration. Every function that takes a posterior name resolves case ids and legacy long names alike.

```{note}
**Two formulations of the non-thermal terms exist, and they are not
interchangeable.** The current calibration — the bundled `GHEB` pair — applies
G₂/₃ and NO₃ *inside* the logistic, as a shift of the curve location T₀ in °C
(`gamma_G23_crtp` / `gamma_NO3_crtp`), so the predicted Scaled RI stays inside
its bounds for any predictor value. The `GHEA` posteriors on Zenodo are the
preprint's response-offset formulation (`beta_G23_crtp` / `beta_NO3_crtp`, in
Scaled-RI units per predictor unit); they are kept for reproducing the preprint
and are documented on the [preprint archive page](preprint_additive_archive.md).

You do not have to choose between them by hand: TEXAS reads which formulation a
posterior uses from the coefficients it carries and selects the matching inverse
model. The univariate and culture/mesocosm posteriors are unaffected either way —
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

```{note}
`temptype=` is optional here. It does not change the reconstruction, which
follows whichever calibration you supply — the target is read from that
posterior's own attributes, and a `temptype` that contradicts it warns. It
matters in exactly one case: when `fwd_posterior` is omitted, it picks which
bundled calibration is used, `"SST"` (the default) or `"thermoT"`. On the
forward side, `get_posterior(..., temptype=...)` is a real argument — that is
where the target is decided.
```

````````{tab-set}
```````{tab-item} Univariate


```python
from TEXAS import predict_T_from_proxyObs

result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=15.0,        # prior mean temperature (°C) — geological estimate
    prior_sigma_t=10.0,     # prior uncertainty (°C) — use wide prior if unsure
    fwd_posterior="tx.GHPU.sst.sri03.p0",   # temperature-only calibration
)
result["p50"]   # median SST (°C), one value per sample
result["p5"]    # 5th percentile
result["p95"]   # 95th percentile
```
```````
```````{tab-item} Multivariate (GDGT-2/3 + NO₃)


```python
result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=15.0,
    prior_sigma_t=10.0,
    # fwd_posterior omitted → the bundled tx.GHEB.sst.sri03.G23-N1p0
    gdgt23ratio=df["gdgt23ratio"].values,
    no3=df["no3"].values,   # µmol/L; scalar or per-sample array
)
```
```````
```````{tab-item} NO₃ from the CMEMS climatology


```python
import xarray as xr

ocean_ds = xr.load_dataset("ocean_prop_ds.nc")  # CMEMS nitrate on the WOA23 grid, from SI_code00

result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=15.0, prior_sigma_t=10.0,
    gdgt23ratio=df["gdgt23ratio"].values,
    site_lat=15.3, site_lon=-23.7,   # modern drill-site coordinates
    no3_dataset=ocean_ds,
)
# Prints: CMEMS NO₃ lookup: lat=15.3, lon=-23.7 → 0.42 µmol/L
```
```````
```````{tab-item} Load from disk / Google Drive


If you have a posterior `.nc` file locally or on Google Drive, pass it directly — no cache lookup, no download:

```python
import xarray as xr
from TEXAS import predict_T_from_proxyObs

# Colab: mount Google Drive first, then load
ds = xr.load_dataset("/content/drive/MyDrive/posteriors/tx.GHPU.sst.sri03.p0.fwd.nc")

result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=15.0, prior_sigma_t=10.0,
    fwd_posterior=ds,    # xr.Dataset — skips all file I/O
)
```
```````
````````

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

`..._eiv_t0shift` is the published calibration. The non-thermal predictors enter inside the logistic, shifting the curve's location parameter T₀ rather than adding an offset to the response:

```
T₀_eff = T₀ + γ_{G₂/₃}·G₂/₃ + γ_{NO₃}·log₁₀(NO₃)
Scaled RI = b + (1 − b) / (1 + exp(−k·(T − T₀_eff)))^(1/ν)
```

so the fitted coefficients are `gamma_G23_crtp` and `gamma_NO3_crtp`, in °C per predictor unit, and the predicted Scaled RI is confined to (b, 1) by construction. `R2_thermal` must be supplied to this model — compute it from a thermal-only coretop fit with `gen_logi_fixed_hier_crtp_univ_priorApprox`.

---

## Citation

If you use TEXAS in published work, please cite:

> Rattanasriampaipong, R., Tierney, J. E., Elling, F. J., & Inglis, G. N. (2026). *TEXAS: A proxy system model for TEX86 paleothermometry.* ESS Open Archive (preprint). https://doi.org/10.22541/essoar.15002926/v3 — under review at *Paleoceanography and Paleoclimatology*.

See [`CITATION.cff`](https://github.com/PaleoLipidRR/TEXAS/blob/main/CITATION.cff) for machine-readable metadata.
