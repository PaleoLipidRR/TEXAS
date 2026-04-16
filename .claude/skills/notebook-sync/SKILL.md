---
name: notebook-sync
description: Check SI notebooks in notebooks/manuscripts/ for deprecated API usage, hardcoded paths, stale parameter names, and compatibility with the current TEXAS package. Use after refactors or before paper submission.
allowed-tools: Read Glob Grep
---

Audit all finalized SI notebooks in `notebooks/manuscripts/`. Check each one against every rule below and report PASS / FAIL / WARN per notebook per category.

Target notebooks (read each):
- `SI_code1_PreProcessing_finalized.ipynb`
- `SI_code2_TEXAS_analysis.ipynb`
- `SI_code3_paleo_showcases.ipynb` (if present)

---

## 1. Deprecated API usage

FAIL if any cell contains:
- `predict_T_from_RI(` — deprecated alias; use `predict_T_from_proxyObs()`
- `predict_temperature_from_RI(` — internal function, should not appear in SI notebooks
- `scaledRI_crtp`, `scaledRI_cul`, `scaledRI_meso` as Stan data dict keys — old naming; current keys are `proxyObs_crtp`, `proxyObs_cul`, `proxyObs_meso`
- `from TEXAS.stan.runner import` — `runner.py` was deleted
- `from TEXAS.utils.cache_search import` — removed from `__all__`
- `from TEXAS.stan.auto import` — deprecated module
- `from TEXAS.utils.hw import` — deprecated module

WARN if any cell contains:
- `import TEXAS.stan.invT` directly (power-user internal; consider using `predict_T_from_proxyObs` instead)

## 2. Hardcoded paths

FAIL if any cell contains hardcoded absolute paths for CmdStan, e.g.:
- `/opt/cmdstan/cmdstan-2.36.0`
- `~/.cmdstan/cmdstan-2.36.0`
- `C:\Users\...`
- Any string matching `cmdstan` that is NOT `from TEXAS.utils.paths import CMDSTAN_DIR`

Correct pattern:
```python
from TEXAS.utils.paths import CMDSTAN_DIR
```

WARN if any other absolute path appears that is not a relative data path or a Zenodo URL.

## 3. Parameter naming

FAIL if any cell references old coefficient names:
- `beta0_gdgt23ratio_crtp` or `beta0_gdgt23ratio_culmeso` — renamed to `beta_G23_crtp` / `beta_G23_culmeso`
- `beta0_no3_crtp` — renamed to `beta_NO3_crtp`

FAIL if any cell references Q parameter:
- `Q_crtp`, `Q_culmeso` — Q was removed from all models (2026-03-24); regenerate posteriors if these appear in posterior access code

## 4. Stan model names

WARN if any cell references a Stan model name that no longer exists as an active `.stan` file in `src/TEXAS/stan_models/`. Check against the list of files in that directory.

Active forward models (verify these exist):
`gen_logi_fixed_culmeso`, `gen_logi_fixed_culmesocore`, `gen_logi_fixed_hier_crtp_multiv`,
`gen_logi_fixed_hier_crtp_multiv_priorApprox`, `gen_logi_fixed_hier_crtp_multiv_priorApprox_werr`,
`gen_logi_fixed_hier_crtp_multiv_priorApprox_werr_ver2`, `gen_logi_fixed_hier_crtp_multiv_odr`,
`gen_logi_fixed_hier_crtp_univ_priorApprox`.

## 5. Posterior file references

WARN if any cell hardcodes a posterior filename that includes old parameter names (`Q`, `beta0_`) in the filename string.

## 6. Imports and package structure

Check that all imports resolve against the current package layout:
- `from TEXAS import build_fwd_data, get_posterior, save_posterior, load_posterior` — valid
- `from TEXAS import predict_RI_from_T, predict_T_from_proxyObs` — valid (added 2026-02-22)
- `from TEXAS.stan.invT import predict_temperature_from_RI` — valid (internal, still present)
- `from TEXAS.ensemble.generator import generate_ensemble_auto` — valid
- `from TEXAS.utils.paths import CMDSTAN_DIR, POSTERIOR_CACHE_DIR` — valid

## 7. Proplot guard (SI_code2 only)

In `SI_code2_TEXAS_analysis.ipynb`, confirm that `proplot` import is wrapped in a try/except:
```python
try:
    import proplot as pplt
except ImportError:
    pplt = None
```
FAIL if `import proplot` appears without a guard.

---

## Output format

For each notebook, print a table:

| Category | Status | Details |
|---|---|---|
| Deprecated API | PASS / FAIL | list of cells with issues |
| Hardcoded paths | PASS / WARN | list of occurrences |
| Parameter naming | PASS / FAIL | list of old names found |
| Stan model names | PASS / WARN | list of unresolved names |
| Imports | PASS / FAIL | list of broken imports |
| Proplot guard | PASS / FAIL / N/A | |

Finish with a one-line verdict per notebook: **Ready** / **Needs fixes** / **Not found**.
