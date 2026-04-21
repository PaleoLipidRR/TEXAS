# TEXAS

**TetraEther indeX for Ammonia oxidizerS**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/PaleoLipidRR/TEXAS/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/texas-psm)](https://pypi.org/project/texas-psm/)

TEXAS is a **Bayesian proxy system model (PSM)** for TEX86-based sea surface temperature (SST) reconstruction. It is built around the Ring Index (RI) of isoGDGTs produced by ammonia-oxidizing *Thaumarchaeota*, and treats the full calibration uncertainty — parameter uncertainty, analytical measurement error, and optional non-thermal corrections (GDGT-2/3 ratio, NO₃) — as probability distributions rather than fixed RMSE values.

The result is a **posterior distribution of SST** for each downcore sample, not just a point estimate.

---

## How it works

TEXAS uses a two-stage workflow:

1. **Forward calibration** — a hierarchical Bayesian Stan model fits a generalized logistic curve to modern culture, mesocosm, and core-top Ring Index–temperature data. The output is a posterior distribution of calibration parameters saved as a `.nc` file.

2. **Inverse reconstruction** — your downcore Ring Index (or TEX86) measurements are passed through the forward posterior to produce SST posterior distributions, marginalizing over calibration uncertainty.

Pre-computed forward posteriors are available for download — most users only need Stage 2.

---

## Quickstart

```python
import numpy as np
import TEXAS

# ── Step 1: Download pre-computed forward posteriors (once per machine) ───
TEXAS.download_all()

# ── Step 2: Reconstruct SST from downcore Ring Index measurements ─────────
ri_values = np.array([0.65, 0.67, 0.70, 0.63])   # your Ring Index values

sst_posterior = TEXAS.predict_T_from_proxyObs(ri_values)

# sst_posterior is an xarray.Dataset with full posterior SST draws
print(sst_posterior)
```

For a full worked example — including multivariate corrections, visualization, and running the forward calibration — see the notebooks in `notebooks/manuscripts/` inside the repository.

---

## Installation

See the [Installation page](installation.md) for Docker (recommended), pip, and conda options across Linux, Windows, and macOS.

---

## Citation

If you use TEXAS in published work, please cite the software and the companion manuscript (details on the [repository page](https://github.com/PaleoLipidRR/TEXAS)).
