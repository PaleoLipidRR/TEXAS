 > **Pre-release:** This software is under active development. APIs may change before v1.0.0 (first stable release at paper acceptance).

# TEXAS — A proxy system model for TetraEther indeX of Ammonia oxidizerS

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/texas-psm.svg)](https://pypi.org/project/texas-psm/)
[![Zenodo](https://img.shields.io/badge/data-10.5281%2Fzenodo.19666744-blue.svg)](https://doi.org/10.5281/zenodo.19666744)

**TEXAS-PSM** (`texas-psm`) is a Python package implementing a **Bayesian proxy
system model** for the TEX86 paleothermometer. **TEXAS** is its sensor model —
the calibration linking temperature to the index — while TEXAS-PSM is the whole
chain around it: sensor, archive, observation, and the inversion back to
temperature. The distribution name and the import already carry that split
(`pip install texas-psm`, `import TEXAS`). It fits hierarchical generalized-logistic Stan models to isoGDGT proxy data (Scaled RI) for thermal responses — with optional non-thermal corrections for AOA ecology (GDGT-2/3 ratio) and nutrient effects (NO₃) — and reconstructs paleotemperatures from new sediment records with full posterior uncertainty.

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

Optional non-thermal predictors — the GDGT-2/GDGT-3 (G23) and NO₃ — enter **inside** the logistic, as a shift of the curve's location parameter T₀:

```
T₀_eff = T₀ + γ_{G23}·G23 + γ_{NO₃}·log₁₀(NO₃)
Scaled RI = b + (1 − b) / (1 + exp(−k·(T − T₀_eff)))^(1/ν)
```

The γ coefficients are in **°C per predictor unit**, so a sample with a given G23 behaves like water that is γ·G23 °C colder. Because the predictors translate the curve rather than adding an offset to the response, the predicted Scaled RI stays inside (b, 1) for any finite predictor value — the bound a ratio has by definition is reproduced by construction, with no truncation or clipping. They are fitted through an Error-in-Variables (EIV) Stan model that separates analytical measurement error from oceanographic process noise. Inverse models use `reduce_sum` for within-chain parallelism.

> **T₀ is the curve's location, not its inflection point.** The steepest response sits at `T₀ − ln(ν)/k`, roughly 4–5 °C below T₀ for the fitted ν. Because `dRI/dT` varies about sixfold across the calibrated range, there is no single thermal sensitivity to quote for this proxy.

---

## Quick start

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/PaleoLipidRR/TEXAS/blob/main/notebooks/quickstart_demo.ipynb)

```bash
pip install texas-psm
# or, with uv:  uv add texas-psm
```

> **Inverse reconstruction runs Stan**, so pip/uv users need CmdStan installed once — run `TEXAS.install_cmdstan()` (or the `texas-install-cmdstan` command), which installs the tested version and verifies the toolchain. Docker and conda-lock bundle it. The forward `predict_proxy_from_T` is pure Python and needs no CmdStan. See [Installation](docs/installation.md#cmdstan-install-discovery-and-verification).

```python
import TEXAS

# Download pre-computed posteriors from Zenodo (~0.3 MB for univariate)
TEXAS.download_posteriors(["tx.GHPU.sst.sri03.p0"])   # univariate SST calibration
# Posterior names are CESM-style case ids (tx.<compset>.<temp>.<proxy>.<predictors>);
# legacy long names (gen_logi_fixed_...) are also accepted everywhere. See
# "How posterior files are named" in the docs quickstart.

# Forward: temperature → Scaled RI
result = TEXAS.predict_proxy_from_T(
    temperatures=[15, 20, 25, 30],
    posterior="tx.GHPU.sst.sri03.p0",
)

# Inverse: Scaled RI → temperature
result = TEXAS.predict_T_from_proxyObs(
    proxyObs=my_ri_array,
    prior_mu_t=15.0, prior_sigma_t=10.0,
    fwd_posterior="tx.GHPU.sst.sri03.p0",
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
**[https://doi.org/10.5281/zenodo.19666744](https://doi.org/10.5281/zenodo.19666744)**

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
TEXAS.download_posteriors(["tx.GHPU.sst.sri03.p0"])
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
    df["cren"],   df["cren_prime"],          # cren_weight=3 by default (RI₀₋₃)
)

# ── Forward prediction (temperature → proxy) ──────────────────────────────────
result = predict_proxy_from_T(
    temperatures=np.linspace(5, 35, 100),
    posterior="tx.GHPU.sst.sri03.p0",
)
# result["p50"], result["p5"], result["p95"] — numpy arrays

# ── Inverse reconstruction (proxy → temperature) ──────────────────────────────
result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=15.0, prior_sigma_t=10.0,
    fwd_posterior="tx.GHPU.sst.sri03.p0",
    temptype="SST",
    save_results=True,   # write quantile .nc + .npz to the invT cache dir
)

# ── Multivariate model with NO₃ and GDGT-2/3 correction ──────────────────────
# This is the default: omitting fwd_posterior selects the full multivariate
# T₀-shift calibration, which ships inside the package — no download needed.
# Pass temptype="thermoT" for the thermocline-integrated calibration.
result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=15.0, prior_sigma_t=10.0,
    fwd_posterior="tx.GHEB.sst.sri03.G23-N1p0",   # the default; may be omitted
    temptype="SST",
    gdgt23ratio=df["gdgt23ratio"].values,
    no3=df["no3"].values,           # or: site_lat=, site_lon=, no3_dataset= for WOA23 lookup
)

# ── Pass a pre-loaded dataset (Colab / Google Drive) ──────────────────────────
# (downloads are named by case id; v0.2.0-era files keep their legacy name)
ds = xr.load_dataset("/content/drive/MyDrive/posteriors/tx.GHPU.sst.sri03.p0.fwd.nc")
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
  quickstart_demo.ipynb     Minimal end-to-end path: GDGTs -> Scaled RI -> temperature
  quickstart_extended.ipynb Longer walkthrough: a published record, model comparison
  manuscripts/      Finalized SI notebooks behind the paper (SI_code00 .. SI_code03)
  reviewer_response/ Analyses answering review comments, not cited in the paper
  superseded/       Pre-revision (additive-formulation) versions, kept for provenance
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
