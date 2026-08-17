# Cross-validation / WAIC model comparison — copied evidence

These files are a **copy**. They were produced in a different repository, under a
different locked environment, and that is where they are regenerated:

| | |
|---|---|
| code | `working-repo/TEXAS-revision/scripts/fit_boundedT_comparison.py` |
| export | `working-repo/TEXAS-revision/scripts/export_cv_results.py` |
| environment | that repo's `pyproject.toml` + `uv.lock` (pandas 3.x) — **not** `texas-env` |
| run | 2026-08-13 12:03, `smoke: false`, 5 folds, n = 2043, ~1 h of Stan |

Do not re-run the fit from a TEXAS notebook. It needs the uv environment above;
`uv.lock` is the record of what produced these numbers, and running it under
`texas-env` would break that provenance.

`results.pkl` is deliberately **not** copied here. It is a pandas-3 pickle and
fails to load under TEXAS's pandas 2 (`StringDtype` signature change), so it
cannot serve as a record. The CSV/JSON here are the portable form.

## What answers what

- `cv_waic_summary.csv` — the headline table (R2.4 validation, R3.1 comparison).
- `cv_waic_meta.json` — provenance, sampler config, `elpd_diff` ± SE, `mu` ranges.
- `cv_sites.csv` — per-site coords, fold ids, and CV predictions for both models
  under both blocking schemes; the spatial-fold figure is built from this.
- `cv_folds_map.csv` — fold sizes and extents.

## Caveat that must travel with these numbers

n = 2043 is the coretop subset with complete G23 + NO3 + SST + RI. The production
TEXAS chain grids to 1513, so these metrics are **not** directly comparable to the
headline calibration RMSE. State the n wherever they are quoted.
