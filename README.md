# TEXAS — Temperature Estimation via a Bayesian Approach with Stan

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)

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

The app accepts a CSV with Ring Index columns and returns downloadable posterior temperature estimates with uncertainty.

---

### Option B — Docker (recommended for reproducibility)

No Stan setup required — CmdStan and all dependencies are pre-installed.

```bash
# Clone the repo
git clone https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS

# Build and start the container
docker compose up
```

Then open JupyterLab at `http://localhost:8888` and run the notebooks in `notebooks/manuscripts/`.

> **Pre-built image on GHCR coming soon.** Until then, the image is built locally from `docker/Dockerfile`.

---

### Option C — conda + pip (for development)

```bash
git clone https://github.com/PaleoLipidRR/TEXAS.git
cd TEXAS

conda env create -f environment.yml
conda activate texas-env

pip install -e .
```

**One-time CmdStan install** (required; sets a flag for the conda C++ compiler on Linux/macOS):

```bash
TBB_CXX_TYPE=gcc python -c "import cmdstanpy; cmdstanpy.install_cmdstan(version='2.36.0')"
```

TEXAS will search for CmdStan in `~/.cmdstan/`, `/opt/cmdstan/`, or the `CMDSTAN` environment variable.

---

## Example usage

```python
from TEXAS.stan.sampler import get_posterior, sampler_invT_posterior
from TEXAS.stan.io import save_posterior
from TEXAS.data.builder import build_invT_inputData

# 1. Forward calibration — fit logistic curve to training data
posterior, diagnostics = get_posterior(
    data,
    model_name="gen_logi_fixed_hier_crtp",
    temptype="SST",
)
save_posterior(posterior)

# 2. Inverse reconstruction — predict temperature from new Ring Index observations
data_inv, kwargs = build_invT_inputData(
    scaledRI, prior_mu_t, prior_sigma_t,
    fwd_posterior_name="gen_logi_fixed_hier_crtp_SST",
)
post_inv, diag = sampler_invT_posterior(data_inv, "invT_gen_logi_fixed", **kwargs)
```

---

## Repository layout

```
src/TEXAS/
  stan/             Sampler, compiler, and NetCDF I/O
  stan_models/      Stan model files (.stan)
  data/             Input data builders, filters, and screening
  ensemble/         Posterior ensemble generation and detection
  models/           Logistic curve functions and classical calibrations
notebooks/
  manuscripts/      Finalized analysis notebooks for the paper
  current/          Active development notebooks
streamlit_app/      Drag-and-drop web interface (Streamlit)
docker/             Dockerfile and compose configuration
docs/               MkDocs documentation source
```

---

## Documentation

Full API reference and method details: [https://paleolipidRR.github.io/TEXAS](https://paleolipidRR.github.io/TEXAS) *(coming soon)*

---

## Citation

If you use TEXAS in your research, please cite:

> Rattanasriampaipong, R. et al. (in prep). *TEXAS: Bayesian GDGT–temperature calibration using Stan.* AGU Paleoceanography and Paleoclimatology.

A `CITATION.cff` and software DOI will be added upon submission.

---

## License

MIT © Ronnakrit Rattanasriampaipong
