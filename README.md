# TEXAS — A proxy system model for TetraEther indeX of Ammonia oxidizerS

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/texas-psm.svg)](https://pypi.org/project/texas-psm/)

**TEXAS** (`texas-psm`) is a Python package for **Bayesian calibration** that fits hierarchical generalized-logistic models to isoGDGT proxy data (Scaled RI) for thermal responses and linear models for nonthermal effects (i.e., AOA ecology and nutrient effect) using Stan, then reconstructs paleotemperatures from new sediment records with full posterior uncertainty.

---

## What it does

TEXAS implements a two-stage workflow:

| Stage | Description |
|---|---|
| **Forward calibration** | Fit a generalized logistic curve (Scaled RI → temperature) to culture, mesocosm, and/or coretop data using a hierarchical Bayesian Stan model. Outputs a compressed posterior `.nc` file. |
| **Inverse reconstruction (invT)** | Predict paleotemperatures from Scaled RI observations by marginalizing over posterior parameter draws (i.e., ...). Returns a full posterior temperature distribution per sample. |

Optional non-thermal corrections for GDGT-2/3 ratio (β_{G₂/₃}) and NO₃ concentration (β_{NO₃}) are supported.

The calibration curve is a generalized logistic (Richards curve) with the asymmetry parameter Q fixed to 1 (inflection point = T₀), keeping 4 free thermal parameters: T₀, k, b, ν.

An **Error-in-Variables (EIV)** Stan model (`_eiv`) is available for the multivariate coretop stage. It separates analytical RI measurement error (`sd_proxyObs`) from oceanographic process noise, and treats NO₃ as a latent variable with a lognormal measurement model — providing rigorous uncertainty propagation when secondary predictor uncertainties are known.

Inverse temperature (invT) Stan models use `reduce_sum` for within-chain parallelism — each observed proxy value is processed as an independent chunk, with threads allocated automatically per chain.

---

## Getting started

### Option A — Docker (recommended for reproducibility)

No Stan or conda setup required — CmdStan and all dependencies are pre-installed in the image.

```bash
git clone https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS

# Interactive launcher — prompts for profile and optional cloud drive mounts
./run.sh
```

Select profile `full` to launch JupyterLab at `http://localhost:8888`.
Or launch directly with:

```bash
docker compose --profile full up
```

Then open the notebooks in `notebooks/manuscripts/`.

> **Pre-built image on GHCR coming soon.** Until then, the image is built locally from `docker/Dockerfile` on first run (takes ~10 minutes).

**Forward posteriors in Docker**: the container bind-mounts your local `data/` directory, so posteriors cached at `data/cache/TEXAS_posterior_cache/` are available automatically inside JupyterLab. Download them first — see [Data and posteriors](#data-and-posteriors) below.

**Switching between Docker and a local environment**: Stan binaries compiled inside the container are Linux x86_64 ELF binaries — they will not run on macOS or on a different Linux system. TEXAS detects this automatically: if a cached binary exits with code 127 (not executable), `StanCompiler` emits a `RuntimeWarning`, deletes the stale binary, and recompiles for the current environment. No manual cleanup is needed when switching setups.

**Platform compatibility:**

| Platform | Status | Notes |
|---|---|---|
| Linux (x86\_64) | ✅ Full support | Native — recommended |
| Windows (Docker Desktop + WSL2) | ✅ Full support | Enable WSL2 backend in Docker Desktop settings |
| macOS (Intel) | ✅ Full support | — |
| macOS (Apple Silicon — M1/M2/M3) | ⚠️ Limited | Runs under QEMU emulation; Stan compilation and sampling will be significantly slower. A native `linux/arm64` image is planned. For now, [Option C (pip)](#option-c--pip-install-python-users) with a local conda env is faster on Apple Silicon. |

**Cloud drive mounts**: `run.sh` will prompt you to set up OneDrive or Google Drive mounts. Paths differ by OS — the script handles this automatically. If using the VS Code Dev Container instead, run `.devcontainer/setup-cloud-drives.sh` once after first open.

---

### Option B — pip install (Python users)

> **Do not run `pip install` against the system Python.** Modern Debian/Ubuntu systems mark the system Python as externally managed (PEP 668) and will refuse the install. Always install into a virtual environment first.

**Step 1 — create and activate an isolated environment** (pick one):

```bash
# Option C1: conda (recommended if you already have conda/miniforge)
conda create -n texas-env python=3.10 pip
conda activate texas-env

# Option C2: plain venv
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

**Step 2 — install the package:**

```bash
pip install texas-psm
```

**Step 3 — one-time CmdStan install** (required for Stan sampling — forward calibration and inverse reconstruction):

```bash
TBB_CXX_TYPE=gcc python -c "import cmdstanpy; cmdstanpy.install_cmdstan(version='2.36.0')"
```

This installs CmdStan to `~/.cmdstan/cmdstan-2.36.0`. TEXAS finds it automatically on next import.

TEXAS searches for CmdStan in the following priority order:

| Priority | Location |
|---|---|
| 1 | `CMDSTAN` environment variable (auto-set by conda; also honoured when set manually) |
| 2 | `/opt/cmdstan/cmdstan-2.36.0` |
| 3 | `~/.cmdstan/cmdstan-2.36.0` — default target of `cmdstanpy.install_cmdstan()` |
| 4 | `/usr/local/cmdstan/cmdstan-2.36.0` |
| 5 | Whatever cmdstanpy is already configured to use |

`set_cmdstan_path()` is always called on the winning path. If `CMDSTAN` is set but points to a broken directory, TEXAS emits a warning and continues down the list. If nothing is found, a `RuntimeError` is raised with explicit install instructions.

To use a specific CmdStan installation (e.g. `~/.cmdstan/cmdstan-2.36.0` instead of a conda-managed one):

```bash
export CMDSTAN=~/.cmdstan/cmdstan-2.36.0
```

---

### Option C — conda-lock (exact reproducible environment)

For the most reproducible setup outside of Docker, use the pre-solved conda-lock files published alongside this repository. Every package version and checksum is pinned — the environment will be identical on any machine of the same platform.

**Step 1 — choose your method:**

*With `conda-lock` (multi-platform lock file — recommended):*

```bash
# Install conda-lock once
conda install -c conda-forge conda-lock   # or: pip install conda-lock

# Create the environment
conda-lock install -n texas-env conda-lock.yml
conda activate texas-env
```

*Without `conda-lock` (platform-specific explicit file — works with plain conda):*

```bash
# Pick the file for your platform
conda create -n texas-env --file conda-linux-64.lock    # Linux x86_64
conda create -n texas-env --file conda-osx-arm64.lock   # macOS Apple Silicon
conda create -n texas-env --file conda-osx-64.lock      # macOS Intel
conda create -n texas-env --file conda-win-64.lock      # Windows

conda activate texas-env
```

**Step 2 — install the package:**

```bash
pip install texas-psm
```

CmdStan is bundled in the conda-lock environment — no separate `install_cmdstan()` step needed.

---

### Option D — conda + pip from source (for development)

```bash
git clone https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS
conda env create -f environment.yml
conda activate texas-env
pip install -e .          # editable install — required for development
```

> **Always use `pip install -e .`** (editable mode). A plain `pip install .` or `pip install texas-psm` puts a static copy in site-packages: `STAN_MODELS_DIR` will point there (no pre-compiled binaries), and any local code changes you make will be silently ignored by the running kernel. After cloning, or any time you find the wrong package version is active, re-run `pip install -e .` and restart your Jupyter kernel.

The conda environment sets `CMDSTAN` automatically to the bundled CmdStan. If you installed CmdStan manually via `cmdstanpy.install_cmdstan()` and want to use that version instead, set:

```bash
export CMDSTAN=~/.cmdstan/cmdstan-2.36.0
```

---

## Data and posteriors

TEXAS separates **code** (this repository) from **data** (hosted on Zenodo). Here is what you need depending on your goal:

| Goal | What you need | Where to get it |
|---|---|---|
| Forward prediction (`predict_proxy_from_T`) | Pre-computed forward posterior `.nc` | `TEXAS.download_all()` |
| Inverse reconstruction (`predict_T_from_proxyObs`) | Pre-computed forward posterior `.nc` | `TEXAS.download_all()` |
| Re-run forward calibration from scratch | GDGT training database | `TEXAS.download_all()` |

**Zenodo data record**: https://doi.org/10.5281/zenodo.19666745

**You do not need to download any data just to install the package.** The Stan model files (`.stan`) are bundled inside the pip package and are found automatically.

### Downloading the data

Once the Zenodo data record is published, download everything in one shot (~560 MB ZIP):

```python
import TEXAS
TEXAS.download_all()           # downloads ZIP and extracts posteriors + training CSVs
```

Or selectively:

```python
TEXAS.download_posteriors()    # forward posteriors only → ~/.texas/cache/TEXAS_posterior_cache/
TEXAS.download_training_data() # training CSVs only → data/spreadsheets/
```

All functions are idempotent — running them again skips files already on disk. Use `force=True` to re-download.

> **Zenodo data record coming upon paper submission.** Until then, contact the authors or generate posteriors yourself with `get_posterior()` (see Example usage below).

### Google Colab / no internet access

If you have a posterior `.nc` file on Google Drive (or anywhere on disk), load it directly — no Zenodo download needed:

```python
import xarray as xr
from TEXAS import predict_proxy_from_T, predict_T_from_proxyObs

# Mount Google Drive first (Colab), then:
ds = xr.load_dataset("/content/drive/MyDrive/posteriors/gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc")

# Pass the dataset directly — no cache lookup, no download
result = predict_proxy_from_T(temperatures=np.linspace(5, 35, 100), posterior=ds)
result = predict_T_from_proxyObs(proxyObs=my_ri, prior_mu_t=15.0, prior_sigma_t=10.0,
                                  fwd_posterior=ds, temptype="SST")
```

---

## Example usage

```python
import numpy as np
import xarray as xr
from TEXAS import predict_proxy_from_T, predict_T_from_proxyObs

# ── Option 1: use a posterior by name (auto-downloads from Zenodo if needed) ──
result = predict_proxy_from_T(
    temperatures=np.linspace(5, 35, 100),
    posterior="gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3",
)
result["p50"]   # median calibration curve (Scaled RI)
result["p5"]    # 5th percentile
result["p95"]   # 95th percentile

# ── Option 2: load a posterior from disk and pass directly ────────────────────
ds = xr.load_dataset("/path/to/gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc")

result = predict_proxy_from_T(temperatures=np.linspace(5, 35, 100), posterior=ds)

result = predict_T_from_proxyObs(
    proxyObs=my_ri_array,
    prior_mu_t=15.0,        # prior mean temperature (°C)
    prior_sigma_t=10.0,     # prior uncertainty (°C)
    fwd_posterior=ds,       # pre-loaded dataset — no file I/O
    temptype="SST",
)
result["p50"]   # median temperature reconstruction (°C)
result["p5"]    # 5th percentile
result["p95"]   # 95th percentile

# ── NO₃ predictor options for inverse reconstruction ─────────────────────────
# Option A — disable NO₃ correction (pass a value above the cutoff)
result = predict_T_from_proxyObs(
    proxyObs=my_ri_array, prior_mu_t=15.0, prior_sigma_t=10.0,
    fwd_posterior_name="gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3",
    no3=10.0,   # scalar > no3_cutoff (1.0 µmol/L) → correction disabled for all samples
)

# Option B — provide explicit NO₃ values (scalar or per-observation array)
result = predict_T_from_proxyObs(
    proxyObs=my_ri_array, prior_mu_t=15.0, prior_sigma_t=10.0,
    fwd_posterior_name="gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3",
    no3=my_no3_array,       # array of length N, one value per observation
    gdgt23ratio=my_g23_array,
)

# Option C — automatic lookup from modern WOA23 climatology at drill-site location
ocean_prop_ds = xr.load_dataset("/path/to/ocean_prop_ds.nc")   # from SI_code1

result = predict_T_from_proxyObs(
    proxyObs=my_ri_array, prior_mu_t=15.0, prior_sigma_t=10.0,
    fwd_posterior_name="gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3",
    gdgt23ratio=my_g23_array,
    site_lat=15.3, site_lon=-23.7,   # modern lat/lon of the drill site
    no3_dataset=ocean_prop_ds,       # WOA23-derived xr.Dataset with (lat, lon) grid
)
# Prints: 🌊 WOA23 NO₃ lookup: lat=15.3, lon=-23.7 → 0.42 µmol/L
```

### Running forward calibration from scratch

Only needed if you want to re-fit the model to your own data or reproduce the published calibration.
Requires CmdStan and the GDGT training database (see [Data and posteriors](#data-and-posteriors) above).

```python
from TEXAS import build_fwd_data, get_posterior, save_posterior

# Build the Stan data dict — validates shapes, sets proxyObs_* keys and use_* flags
data = build_fwd_data(
    t_cul=cul_df["SST"].values,       proxy_cul=cul_df["scaledRI"].values,
    t_meso=meso_df["SST"].values,     proxy_meso=meso_df["scaledRI"].values,
    t_crtp=crtp_df["SST"].values,     proxy_crtp=crtp_df["scaledRI"].values,
    gdgt23ratio_crtp=crtp_df["gdgt23ratio"].values,
    no3_crtp=crtp_df["no3"].values,   # no3_cutoff auto-calculated if omitted
)

posterior, diagnostics = get_posterior(
    data,
    stan_file="gen_logi_fixed_hier_crtp_multiv",
    temptype="SST",
    proxy_name="scaledRI",            # required — saved to .nc attrs
)
save_posterior(posterior)
# → gen_logi_fixed_hier_crtp_multiv_SST_scaledRI.nc
```

---

## Repository layout

```
src/TEXAS/
  predict.py        High-level API: predict_proxy_from_T / predict_T_from_proxyObs
  stan/             Sampler, compiler, I/O, and invT orchestration
  stan_models/      Stan model files (.stan) — bundled in the pip package
  data/             Input data builders, filters, screening, and ocean property lookups
  ensemble/         Posterior ensemble generation and model detection
  models/           Logistic curve functions and classical calibrations
  plotting/         Prior/posterior distribution plots and range utilities
  utils/            Path constants, system info, Zenodo download utilities
notebooks/
  manuscripts/      Finalized SI notebooks for the paper
    SI_code1_PreProcessing_finalized.ipynb
    SI_code2_TEXAS_analysis.ipynb
    SI_code3_paleo_showcases.ipynb
  colab_quickstart.ipynb   Google Colab quickstart
streamlit_app/      Drag-and-drop web interface (Streamlit)
docker/             Dockerfile and compose configuration
docs/               MkDocs documentation source
tests/              Unit tests
```

---

## API at a glance

| Function | Description |
|---|---|
| `predict_proxy_from_T(temperatures, posterior, ...)` | Forward prediction: temperature → proxy (Scaled RI, TEX86, or any fitted proxy; pure Python) |
| `predict_T_from_proxyObs(proxyObs, prior_mu_t, prior_sigma_t, ...)` | Inverse reconstruction: proxy → temperature with full uncertainty (runs Stan). Accepts `no3` / `gdgt23ratio` as scalar or array; pass `site_lat` / `site_lon` / `no3_dataset` for automatic WOA23 NO₃ lookup. `predict_T_from_RI` is a deprecated alias |
| `lookup_no3_from_woa(lat, lon, woa_dataset, ...)` | Look up modern NO₃ climatology at one or more lat/lon coordinates from a WOA23-derived xr.Dataset; handles 0–360 and −180–180 longitude conventions automatically |
| `download_posteriors(names, ...)` | Download all standard forward posteriors from Zenodo |
| `download_posterior(name, ...)` | Download a single forward posterior from Zenodo |
| `set_cache_dir(path)` | Override cache location at runtime; persistent alternative is `TEXAS_CACHE_DIR` env var |
| `build_fwd_data(t_cul, proxy_cul, ..., no3_crtp, culmeso_posterior)` | Build validated Stan data dict for forward calibration; auto-detects predictors and `no3_cutoff` |
| `get_posterior(data, stan_file, temptype, proxy_name, ...)` | Run forward calibration Stan sampling; `proxy_name` required, saved to `.nc` attrs |
| `save_posterior(ds)` / `load_posterior(name)` | Persist / load forward posterior as compressed NetCDF; filename pattern: `{model}_{temptype}_{proxy_name}{suffix}.nc` |
| `get_invT_posterior(...)` | Run inverse-T sampling and return full posterior xr.Dataset |
| `generate_ensemble_auto(temperatures, posterior, ...)` | Sample draws from a posterior and compute calibration-curve percentiles |
| `find_optimal_no3_threshold(data, ...)` | Find optimal NO₃ cutoff that maximises GDGT–temperature correlation (Spearman-based); supports `log_method`, `score_method`, `weight_method` |
| `find_optimal_no3_threshold_nointercept(data, ...)` | No-intercept variant; supports `no3_mode`, `log_method`, `weight_method` |
| `summarize_sampler_diagnostics(fit)` | Compute divergences, R-hat, ESS, E-BFMI from a CmdStanMCMC fit |
| `create_summary_table(fit)` | Return a formatted DataFrame of per-parameter diagnostics |
| `detect_model_and_params(posterior)` | Infer suffix, model function, and optional-predictor flags from posterior attributes |
| `plot_prior_distributions(posterior)` | Plot prior distributions from posterior metadata |

Full API reference: [https://paleolipidRR.github.io/TEXAS](https://paleolipidRR.github.io/TEXAS) *(coming soon)*

---

## Citation

If you use TEXAS in your research, please cite:

> Rattanasriampaipong, R. et al. (in prep). *TEXAS: A proxy system model for TEX86 paleothermometry.* AGU Paleoceanography and Paleoclimatology.

See [`CITATION.cff`](CITATION.cff) for machine-readable citation metadata. A Zenodo software DOI will be added upon submission.

---

## License

MIT © Ronnakrit Rattanasriampaipong
