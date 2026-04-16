---
name: regenerate-posteriors
description: List stale forward posterior .nc files in the TEXAS cache and show the correct get_posterior() call to regenerate each one. Use when Stan models or priors have changed and cached posteriors may be outdated.
allowed-tools: Read Glob Grep Bash
---

Inspect `data/cache/TEXAS_posterior_cache/` and report which `.nc` posterior files are likely stale, why, and how to regenerate them.

## Step 1 — List cached posteriors

Run:
```bash
ls -lh data/cache/TEXAS_posterior_cache/*.nc 2>/dev/null | sort
```

If the directory is empty or missing, report that no posteriors are cached and skip to Step 3.

## Step 2 — Check for staleness signals

For each `.nc` file, try to read its metadata attributes with Python if possible:
```bash
python -c "
import xarray as xr, sys
ds = xr.open_dataset('$FILE', engine='scipy')
attrs = dict(ds.attrs)
vars_ = list(ds.data_vars)
print('vars:', vars_[:10])
print('model:', attrs.get('stan_model_name','?'))
print('date:', attrs.get('run_date','?'))
"
```

Flag a posterior as **stale** if any of the following apply:

| Signal | Stale reason |
|---|---|
| Data variables contain `Q_crtp` or `Q_culmeso` | Q parameter removed 2026-03-24; model now uses Q=1 fixed |
| Data variables contain `beta0_gdgt23ratio_crtp` or `beta0_no3_crtp` | Old coefficient names; renamed to `beta_G23_crtp` / `beta_NO3_crtp` (2026-02-22) |
| `stan_model_name` attr references a model file that no longer exists in `src/TEXAS/stan_models/` | Model was renamed or deleted |
| `run_date` is before 2026-04-08 AND model is one of: `gen_logi_fixed_hier_crtp_multiv`, `gen_logi_fixed_hier_crtp_multiv_priorApprox`, `gen_logi_fixed_hier_crtp_univ_priorApprox`, `gen_logi_fixed_hier_crtp_multiv_priorApprox_werr`, `gen_logi_fixed_culmesocore` | sigma prior was `normal(0.01, 0.1)` before 2026-04-08; now `normal(0, 0.1)` |

## Step 3 — Show regeneration calls

For each stale posterior, show the appropriate regeneration call based on the filename pattern
`{model}_{temptype}_{proxy_name}{suffix}.nc`.

Reference pattern:
```python
from TEXAS import build_fwd_data, get_posterior, save_posterior

# Two-stage (priorApprox) models — need culmeso posterior first
data = build_fwd_data(
    t_crtp=crtp_df["SST"].values,
    proxy_crtp=crtp_df["scaledRI"].values,
    gdgt23ratio_crtp=crtp_df["gdgt23ratio"].values,
    no3_crtp=crtp_df["no3"].values,
    sd_proxyObs=crtp_df["scaledRI_se"].values,  # required for _werr_ver2
    culmeso_posterior=culmeso_post,              # required for priorApprox
    R2_thermal=0.74,                             # required for _werr_ver2 only
)
post, diag = get_posterior(data, "gen_logi_fixed_hier_crtp_multiv_priorApprox", temptype="SST", proxy_name="scaledRI")
save_posterior(post)

# Full hierarchical models (not priorApprox)
data = build_fwd_data(
    t_cul=cul_df["SST"].values,   proxy_cul=cul_df["scaledRI"].values,
    t_meso=meso_df["SST"].values, proxy_meso=meso_df["scaledRI"].values,
    t_crtp=crtp_df["SST"].values, proxy_crtp=crtp_df["scaledRI"].values,
    gdgt23ratio_crtp=crtp_df["gdgt23ratio"].values,
    no3_crtp=crtp_df["no3"].values,
)
post, diag = get_posterior(data, "gen_logi_fixed_hier_crtp_multiv", temptype="SST", proxy_name="scaledRI")
save_posterior(post)
```

Tailor each call to the specific model and predictor flags inferred from the filename (e.g. `_no3_1.0_` in the filename means `no3_cutoff=1.0` was used).

## Step 4 — Summary

Print a table:
| File | Stale? | Reason | Action |
|---|---|---|---|

Finish with the total count of stale vs current posteriors.
