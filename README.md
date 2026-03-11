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

Optional non-thermal corrections for GDGT-2/3 ratio and NO₃ concentration are supported.

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
| Inverse reconstruction (`predict_T_from_RI`) | Pre-computed forward posterior `.nc` | Zenodo data record *(link upon publication)* |
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
result = predict_T_from_RI(scaledRI=my_ri, prior_mu_t=15.0, prior_sigma_t=10.0,
                            fwd_posterior=ds, temptype="SST")
```

---

## Example usage

```python
import numpy as np
import xarray as xr
from TEXAS import predict_RI_from_T, predict_T_from_RI

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

result = predict_T_from_RI(
    scaledRI=my_ri_array,
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
from TEXAS import get_posterior, save_posterior

posterior, diagnostics = get_posterior(
    data,                                       # your GDGT data dict
    model_name="gen_logi_fixed_hier_crtp_multiv",
    temptype="SST",
)
save_posterior(posterior)   # saves to ~/.texas/ (or repo cache/ if running from source)
```

---

## Repository layout

```
src/TEXAS/
  predict.py        High-level API: predict_RI_from_T / predict_T_from_RI
  stan/             Sampler, compiler, I/O, and invT orchestration
  stan_models/      Stan model files (.stan) — bundled in the pip package
  data/             Input data builders, filters, and screening
  ensemble/         Posterior ensemble generation and model detection
  models/           Logistic curve functions and classical calibrations
  plotting/         Prior/posterior distribution plots and range utilities
  utils/            Path constants, system info, Zenodo download utilities
notebooks/
  manuscripts/      Finalized SI notebooks for the paper
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
| `predict_T_from_RI(scaledRI, prior_mu_t, prior_sigma_t, ...)` | Inverse reconstruction: Ring Index → temperature with full uncertainty (runs Stan) |
| `download_posteriors(names, ...)` | Download all standard forward posteriors from Zenodo |
| `download_posterior(name, ...)` | Download a single forward posterior from Zenodo |
| `get_posterior(data, model_name, temptype, ...)` | Run forward calibration Stan sampling |
| `save_posterior(ds)` / `load_posterior(name)` | Persist / load forward posterior as compressed NetCDF |
| `get_invT_posterior(...)` | Run inverse-T sampling and return full posterior xr.Dataset |
| `generate_ensemble_auto(temperatures, posterior, ...)` | Sample draws from a posterior and compute calibration-curve percentiles |
| `summarize_sampler_diagnostics(fit)` | Compute divergences, R-hat, ESS, E-BFMI from a CmdStanMCMC fit |
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
