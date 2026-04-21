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

# ── Download pre-computed forward posteriors (once per machine) ───────────
TEXAS.download_all()

# ── Forward prediction: temperature → Scaled RI calibration curve ─────────
temperatures = np.linspace(5, 35, 100)   # °C

result = TEXAS.predict_proxy_from_T(
    temperatures=temperatures,
    posterior="gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3",
    percentiles=[5, 50, 95],
)
result["p50"]    # median Scaled RI calibration curve
result["p5"]     # 5th percentile envelope
result["p95"]    # 95th percentile envelope

# ── Inverse reconstruction: Scaled RI → SST with full uncertainty ─────────
ri_values = np.array([0.65, 0.67, 0.70, 0.63])   # downcore Scaled RI

result = TEXAS.predict_T_from_proxyObs(
    proxyObs=ri_values,
    prior_mu_t=15.0,      # prior mean SST (°C) — your best geological estimate
    prior_sigma_t=10.0,   # prior uncertainty (°C) — wide if unsure
    fwd_posterior_name="gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3",
)
result["p50"]    # median SST reconstruction (°C), one value per sample
result["p5"]     # 5th percentile
result["p95"]    # 95th percentile
```

For full worked examples — multivariate corrections (GDGT-2/3 ratio, NO₃), paleo showcases, and running the forward calibration — see the notebooks in `notebooks/manuscripts/` inside the repository.

---

## Installation

See the [Installation page](installation.md) for Docker (recommended), pip, and conda options across Linux, Windows, and macOS.

---

## Citation

If you use TEXAS in published work, please cite the software and the companion manuscript (details on the [repository page](https://github.com/PaleoLipidRR/TEXAS)).
