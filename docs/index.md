# TEXAS

**TetraEther indeX for Ammonia oxidizerS**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/PaleoLipidRR/TEXAS/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/texas-psm)](https://pypi.org/project/texas-psm/)

TEXAS is a **Bayesian proxy system model (PSM)** for TEX86-based sea surface temperature (SST) reconstruction. It replaces classical TEX86 calibration equations with a full probabilistic framework: uncertainty in the calibration parameters, the proxy measurement, and optional non-thermal corrections (GDGT-2/3 ratio, NO₃) are all propagated into the final temperature estimate.

---

## What does TEXAS do?

TEX86 is an organic paleothermometer based on the ring distribution of isoGDGTs produced by *Thaumarchaeota* (ammonia-oxidizing archaea). The ratio of these lipids — summarized as the Ring Index (RI) or TEX86 — varies with temperature, making it a widely used proxy for past SSTs in marine sediment records.

Classical TEX86 calibrations (e.g., Kim et al. 2010; O'Brien et al. 2017) fit a single regression line through modern core-top data and report a fixed RMSE. TEXAS instead:

1. **Forward calibration** — fits a generalized logistic curve to modern culture, mesocosm, and core-top data using a hierarchical Bayesian Stan model. The result is a *posterior distribution* over calibration parameters (not a single best-fit line), capturing calibration uncertainty explicitly.

2. **Inverse temperature reconstruction** — takes your downcore Ring Index (or TEX86) measurements and reconstructs SST by marginalizing over thousands of parameter draws from the forward posterior. The output is a full posterior distribution of temperature for each sample — not just a point estimate and RMSE.

Optional predictors correct for non-thermal influences:

- **GDGT-2/3 ratio** — corrects for terrestrial or deep-water GDGT input
- **NO₃ concentration** — accounts for subsurface production of GDGTs in nutrient-rich waters

---

## Quickstart

```python
import TEXAS

# ── 1. Download forward calibration posteriors (once) ──────────────────────
TEXAS.download_all()   # saves to data/cache/TEXAS_posterior_cache/

# ── 2. Inverse temperature reconstruction ─────────────────────────────────
import numpy as np
from TEXAS import predict_T_from_proxyObs, load_posterior

# Your downcore Ring Index measurements
ri_values   = np.array([0.65, 0.67, 0.70, 0.63])
ri_sd       = np.array([0.01, 0.01, 0.01, 0.01])   # analytical SE

# Load the pre-computed forward posterior
posterior = load_posterior("gen_logi_fixed_hier_crtp_multiv_SST_scaledRI")

# Reconstruct SST — returns posterior samples for each sample
sst_posterior = predict_T_from_proxyObs(ri_values, posterior)

# Summarize
print(sst_posterior.mean(dim="draw"))   # posterior mean SST per sample
```

See the [full README](https://github.com/PaleoLipidRR/TEXAS) for complete examples including forward calibration, multivariate corrections, and ensemble visualization.

---

## Documentation

| Page | What it covers |
|---|---|
| [Installation](installation.md) | Docker (recommended), pip, conda-lock, and source install — per OS |
| [API Reference](api.md) | Full Python API with parameter descriptions |
| [PSM description](PSM.md) | Statistical framework, model equations, and prior choices |
| [Stan model guide](stan_models_explanation_v2.md) | Annotated walkthrough of the Stan models |

---

## Why Bayesian?

A standard calibration gives you one number: "TEX86 = 0.70 → SST = 28°C ± 2°C (1σ RMSE)". That ±2°C is a *population-level* residual, not a statement about *your specific sample*. It does not account for:

- Uncertainty in the calibration parameters themselves
- Analytical uncertainty in your Ring Index measurement
- Non-thermal influences on GDGT distributions

TEXAS propagates all of these through a formal probabilistic model. The result is a sample-specific posterior distribution — wider where the calibration is uncertain (e.g., at the warm end of the calibration range), narrower where it is well-constrained.

---

## Citation

If you use TEXAS in published work, please cite:

> Rattanasriampaipong et al. (in prep). TEXAS: a Bayesian proxy system model for TEX86 paleothermometry.

A Zenodo DOI for the software is available at the [repository](https://github.com/PaleoLipidRR/TEXAS).
