 > **Pre-release:** This software is under active development. APIs may change before v1.0.0 (first stable release at paper acceptance).

# TEXAS — A proxy system model for TetraEther indeX of Ammonia oxidizerS

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/texas-psm.svg)](https://pypi.org/project/texas-psm/)
[![Zenodo](https://img.shields.io/badge/data-10.5281%2Fzenodo.20032542-blue.svg)](https://doi.org/10.5281/zenodo.20032542)

**TEXAS** (`texas-psm`) is a Python package for **Bayesian calibration** of the TEX86 paleothermometer. It fits hierarchical generalized-logistic Stan models to isoGDGT proxy data (Scaled RI) for thermal responses — with optional non-thermal corrections for AOA ecology (GDGT-2/3 ratio) and nutrient effects (NO₃) — and reconstructs paleotemperatures from new sediment records with full posterior uncertainty.

<p align="center">
  <kbd><a href="docs/installation.md">📦 Installation</a></kbd> &nbsp;
  <kbd><a href="https://paleolipidRR.github.io/TEXAS">📖 Documentation</a></kbd> &nbsp;
  <kbd><a href="CONTRIBUTING.md">🤝 Contributing</a></kbd> &nbsp;
  <kbd><a href="LICENSE">📄 License</a></kbd>
</p>

---

## What it does

TEXAS implements a two-stage workflow:

| Stage | Description |
|---|---|
| **Forward calibration** | Fit a generalized logistic curve (Scaled RI → temperature) to culture, mesocosm, and/or coretop data using a hierarchical Bayesian Stan model. Outputs a compressed posterior `.nc` file. |
| **Inverse reconstruction (invT)** | Predict paleotemperatures from Scaled RI observations by marginalizing over posterior parameter draws. Returns a full posterior temperature distribution per sample. |

Optional non-thermal corrections for GDGT-2/3 ratio (β_{G₂/₃}) and NO₃ (β_{NO₃}) are supported via an Error-in-Variables (EIV) Stan model that separates analytical measurement error from oceanographic process noise. Inverse models use `reduce_sum` for within-chain parallelism.

---

## Quick start

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/PaleoLipidRR/TEXAS/blob/main/notebooks/quickstart_demo.ipynb)

```bash
pip install texas-psm
# or, with uv:  uv add texas-psm
```

> **Inverse reconstruction runs Stan**, so pip/uv users need CmdStan installed once (`python -c "import cmdstanpy; cmdstanpy.install_cmdstan(version='2.36.0')"`). Docker and conda-lock bundle it. The forward `predict_proxy_from_T` is pure Python and needs no CmdStan. See [Installation](docs/installation.md#cmdstan-discovery).

```python
import TEXAS

# Download pre-computed posteriors from Zenodo (~0.3 MB for univariate)
TEXAS.download_posteriors(["gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3"])

# Forward: temperature → Scaled RI
result = TEXAS.predict_proxy_from_T(
    temperatures=[15, 20, 25, 30],
    posterior="gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3",
)

# Inverse: Scaled RI → temperature
result = TEXAS.predict_T_from_proxyObs(
    proxyObs=my_ri_array,
    prior_mu_t=15.0, prior_sigma_t=10.0,
    fwd_posterior="gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3",
    temptype="SST",
)
result["p50"]   # median temperature (°C)
result["p5"]    # 5th percentile
result["p95"]   # 95th percentile
```

For Docker, conda-lock, uv, and development installs, see [Installation](docs/installation.md).

---

## Data and posteriors

Pre-computed posteriors and training data are hosted on Zenodo:
**[https://doi.org/10.5281/zenodo.20032542](https://doi.org/10.5281/zenodo.20032542)**

```python
import TEXAS

TEXAS.download_all()               # posteriors + training CSVs
TEXAS.download_posteriors()        # forward posteriors only (~158 MB total;
                                   # EIV multiv posteriors are ~78 MB each)
TEXAS.download_training_data()     # training CSVs + CMEMS NO₃ field
```

Pass `names=` to download only what you need:

```python
# Univariate SST posterior — ~0.3 MB
TEXAS.download_posteriors(["gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3"])
```

Load a posterior directly from disk (no cache lookup):

```python
import xarray as xr
ds = xr.load_dataset("/path/to/posterior.nc")
result = TEXAS.predict_T_from_proxyObs(..., fwd_posterior=ds)
```

Check what is cached:

```python
TEXAS.list_posteriors()
```

| Install method | Posteriors | Training data |
|---|---|---|
| `pip install texas-psm` | `~/.texas/cache/TEXAS_posterior_cache/` | `~/.texas/data/spreadsheets/` |
| From source (`pip install -e .`) | `data/cache/TEXAS_posterior_cache/` | `data/spreadsheets/` |

---

## Example usage

```python
import numpy as np
import xarray as xr
from TEXAS import compute_scaledRI, predict_proxy_from_T, predict_T_from_proxyObs

# ── Compute Scaled Ring Index from raw GDGT abundances ────────────────────────
df["scaledRI_cren3"] = compute_scaledRI(
    df["GDGT-0"], df["GDGT-1"], df["GDGT-2"], df["GDGT-3"],
    df["cren"],   df["cren_prime"],          # cren_rings=3 by default (RI₀₋₃)
)

# ── Forward prediction (temperature → proxy) ──────────────────────────────────
result = predict_proxy_from_T(
    temperatures=np.linspace(5, 35, 100),
    posterior="gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3",
)
# result["p50"], result["p5"], result["p95"] — numpy arrays

# ── Inverse reconstruction (proxy → temperature) ──────────────────────────────
result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=15.0, prior_sigma_t=10.0,
    fwd_posterior="gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3",
    temptype="SST",
    save_results=True,   # write quantile .nc + .npz to the invT cache dir
)

# ── Multivariate model with NO₃ and GDGT-2/3 correction ──────────────────────
result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=15.0, prior_sigma_t=10.0,
    fwd_posterior="gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3",
    temptype="SST",
    gdgt23ratio=df["gdgt23ratio"].values,
    no3=df["no3"].values,           # or: site_lat=, site_lon=, no3_dataset= for WOA23 lookup
)

# ── Pass a pre-loaded dataset (Colab / Google Drive) ──────────────────────────
ds = xr.load_dataset("/content/drive/MyDrive/posteriors/gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc")
result = predict_T_from_proxyObs(..., fwd_posterior=ds)
```

---

## Repository layout

```
src/TEXAS/
  predict.py        High-level API: predict_proxy_from_T / predict_T_from_proxyObs
  stan/             Sampler, compiler, I/O, and invT orchestration
  stan_models/      Stan model files (.stan) — bundled in the pip package
  data/             Input data builders, filters, screening, ocean property lookups
  ensemble/         Posterior ensemble generation and model detection
  models/           Logistic curve functions and classical calibrations
  utils/            Path constants, system info, Zenodo download utilities
notebooks/
  manuscripts/      Finalized SI notebooks (SI_code1, SI_code2, SI_code3)
  quickstart_demo.ipynb
streamlit_app/      Drag-and-drop web interface (Streamlit)
docker/             Dockerfile and compose configuration
docs/               Jupyter Book documentation source (guides, API, tutorial)
tests/              Unit tests
```

---

## API at a glance

| Function | Description |
|---|---|
| `compute_scaledRI(gdgt0, …, cren_prime)` | Compute Scaled RI (RI₀₋₃ by default) from six isoGDGT abundances |
| `predict_proxy_from_T(temperatures, posterior, …)` | Forward: temperature → proxy percentiles (pure Python) |
| `predict_T_from_proxyObs(proxyObs, prior_mu_t, prior_sigma_t, fwd_posterior, …)` | Inverse: proxy → temperature with full uncertainty (runs Stan); accepts name string or `xr.Dataset` |
| `download_posteriors(names, …)` | Download forward posteriors from Zenodo (with per-file size notice) |
| `download_training_data(…)` | Download training CSVs + CMEMS NO₃ field from Zenodo |
| `list_posteriors()` | Print and return `.nc` stems in the local cache |
| `lookup_no3_from_woa(lat, lon, woa_dataset)` | WOA23 NO₃ climatology lookup at drill-site coordinates |
| `build_fwd_data(t_cul, proxy_cul, …)` | Build validated Stan data dict for forward calibration |
| `get_posterior(data, stan_file, temptype, proxy_name, …)` | Run forward calibration Stan sampling |
| `save_posterior(ds)` / `load_posterior(name)` | Persist / load forward posterior as compressed NetCDF |
| `set_cache_dir(path)` | Override cache root at runtime |
| `summarize_sampler_diagnostics(fit)` | Divergences, R-hat, ESS, E-BFMI |

Full API reference: [https://paleolipidRR.github.io/TEXAS](https://paleolipidRR.github.io/TEXAS)

---

## Citation

If you use TEXAS in your research, please cite:

> Rattanasriampaipong, R. et al. (in prep). *TEXAS: A proxy system model for TEX86 paleothermometry.* AGU Paleoceanography and Paleoclimatology.

See [`CITATION.cff`](CITATION.cff) for machine-readable citation metadata.

---

## License

MIT © Ronnakrit Rattanasriampaipong — see [`LICENSE`](LICENSE) for the full text.
