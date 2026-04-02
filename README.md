# TEXAS — A proxy system model for TetraEther indeX of Ammonia oxidizerS

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/texas-psm.svg)](https://pypi.org/project/texas-psm/)

**TEXAS** (`texas-psm`) is a Python package for **Bayesian GDGT–temperature calibration**. It fits hierarchical generalized-logistic models to isoGDGT proxy data (TEX86 / Ring Index) using Stan, then reconstructs paleotemperatures from new sediment records with full posterior uncertainty.

---

## What it does

TEXAS implements a two-stage workflow:

| Stage | Description |
|---|---|
| **Forward calibration** | Fit a generalized logistic curve (Ring Index → temperature) to culture, mesocosm, and/or coretop data using a hierarchical Bayesian Stan model. Outputs a compressed posterior `.nc` file. |
| **Inverse reconstruction (invT)** | Predict paleotemperatures from new Ring Index observations by marginalizing over posterior parameter draws. Returns a full posterior temperature distribution per sample. |

Optional non-thermal corrections for GDGT-2/3 ratio (β_{G₂/₃}) and NO₃ concentration (β_{NO₃}) are supported. The NO₃ correction uses log₁₀(NO₃ / cutoff) — a ratio form that is continuous at the cutoff boundary and avoids a step discontinuity in the calibration curve.

The calibration curve is a generalized logistic (Richards curve) with the asymmetry parameter Q fixed to 1 (inflection point = T₀), keeping 4 free thermal parameters: T₀, k, b, ν.

Inverse temperature (invT) Stan models use `reduce_sum` for within-chain parallelism — each observed proxy value is processed as an independent chunk, with threads allocated automatically per chain.

---

## Getting started

### Option A — No-code: Streamlit web app

Upload a CSV and get paleotemperature reconstructions in your browser — no Python or Stan installation required.

> **Streamlit deployment coming soon.**

---

### Option B — Docker (recommended for reproducibility)

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

**Platform compatibility:**

| Platform | Status | Notes |
|---|---|---|
| Linux (x86\_64) | ✅ Full support | Native — recommended |
| Windows (Docker Desktop + WSL2) | ✅ Full support | Enable WSL2 backend in Docker Desktop settings |
| macOS (Intel) | ✅ Full support | — |
| macOS (Apple Silicon — M1/M2/M3) | ⚠️ Limited | Runs under QEMU emulation; Stan compilation and sampling will be significantly slower. A native `linux/arm64` image is planned. For now, [Option C (pip)](#option-c--pip-install-python-users) with a local conda env is faster on Apple Silicon. |

**Cloud drive mounts**: `run.sh` will prompt you to set up OneDrive or Google Drive mounts. Paths differ by OS — the script handles this automatically. If using the VS Code Dev Container instead, run `.devcontainer/setup-cloud-drives.sh` once after first open.

---

### Option C — pip install (Python users)

```bash
pip install texas-psm
```

**One-time CmdStan install** (required for any Stan sampling — forward calibration or inverse reconstruction):

```bash
TBB_CXX_TYPE=gcc python -c "import cmdstanpy; cmdstanpy.install_cmdstan(version='2.36.0')"
```

TEXAS will search for CmdStan in `~/.cmdstan/`, `/opt/cmdstan/`, or the `CMDSTAN` environment variable.

---

### Option D — conda + pip from source (for development)

```bash
git clone https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS
conda env create -f environment.yml
conda activate texas-env
pip install -e .
```

Then install CmdStan as shown in Option C above.

---

## Data and posteriors

TEXAS separates **code** (this repository) from **data** (hosted on Zenodo). Here is what you need depending on your goal:

| Goal | What you need | Where to get it |
|---|---|---|
| Forward prediction (`predict_RI_from_T`) | Pre-computed forward posterior `.nc` | Zenodo data record *(link upon publication)* |
| Inverse reconstruction (`predict_T_from_proxyObs`) | Pre-computed forward posterior `.nc` | Zenodo data record *(link upon publication)* |
| Re-run forward calibration from scratch | GDGT training database | Zenodo data record *(link upon publication)* |

**You do not need to download any data just to install the package.** The Stan model files (`.stan`) are bundled inside the pip package and are found automatically.

### Downloading the forward posteriors

The forward calibration posteriors are the pre-computed Bayesian parameter distributions required for both forward and inverse predictions. Once the Zenodo data record is published, you can fetch them in one line:

```python
import TEXAS
TEXAS.download_posteriors()   # downloads all standard posteriors to ~/.texas/
```

Or download a single posterior:

```python
TEXAS.download_posterior("gen_logi_fixed_hier_crtp_multiv_SST")
```

Posteriors are cached at `~/.texas/data/cache/TEXAS_posterior_cache/` and are found automatically on subsequent calls — no repeated downloads.

> **Zenodo data record coming upon paper submission.** Until then, contact the authors or generate posteriors yourself with `get_posterior()` (see Example usage below).

### Google Colab / no internet access

If you have a posterior `.nc` file on Google Drive (or anywhere on disk), load it directly — no Zenodo download needed:

```python
import xarray as xr

# Mount Google Drive first (Colab), then:
ds = xr.load_dataset("/content/drive/MyDrive/posteriors/gen_logi_fixed_hier_crtp_multiv_SST.nc")

# Pass the dataset directly — no cache lookup, no download
result = predict_RI_from_T(temperatures=np.linspace(5, 35, 100), posterior=ds)
result = predict_T_from_proxyObs(proxyObs=my_ri, prior_mu_t=15.0, prior_sigma_t=10.0,
                                  fwd_posterior=ds, temptype="SST")
```

---

## Example usage

```python
import numpy as np
import xarray as xr
from TEXAS import predict_RI_from_T, predict_T_from_proxyObs

# ── Option 1: use a posterior by name (auto-downloads from Zenodo if needed) ──
result = predict_RI_from_T(
    temperatures=np.linspace(5, 35, 100),
    posterior="gen_logi_fixed_hier_crtp_multiv_SST",
)
result["p50"]   # median calibration curve (scaled RI)
result["p5"]    # 5th percentile
result["p95"]   # 95th percentile

# ── Option 2: load a posterior from disk and pass directly ────────────────────
ds = xr.load_dataset("/path/to/gen_logi_fixed_hier_crtp_multiv_SST.nc")

result = predict_RI_from_T(temperatures=np.linspace(5, 35, 100), posterior=ds)

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
  predict.py        High-level API: predict_RI_from_T / predict_T_from_proxyObs
  stan/             Sampler, compiler, I/O, and invT orchestration
  stan_models/      Stan model files (.stan) — bundled in the pip package
  data/             Input data builders, filters, and screening
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
| `predict_RI_from_T(temperatures, posterior, ...)` | Forward prediction: temperature → Ring Index (pure Python) |
| `predict_T_from_proxyObs(proxyObs, prior_mu_t, prior_sigma_t, ...)` | Inverse reconstruction: proxy → temperature with full uncertainty (runs Stan); `predict_T_from_RI` is a deprecated alias |
| `download_posteriors(names, ...)` | Download all standard forward posteriors from Zenodo |
| `download_posterior(name, ...)` | Download a single forward posterior from Zenodo |
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

> Rattanasriampaipong, R. et al. (in prep). *TEXAS: Bayesian GDGT–temperature calibration using Stan.* AGU Paleoceanography and Paleoclimatology.

See [`CITATION.cff`](CITATION.cff) for machine-readable citation metadata. A Zenodo software DOI will be added upon submission.

---

## License

MIT © Ronnakrit Rattanasriampaipong
