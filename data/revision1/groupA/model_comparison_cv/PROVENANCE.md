# Cross-validation / WAIC model comparison — copied evidence

These files are a **copy**. They were produced in a different repository, under a
different locked environment, and that is where they are regenerated:

| | |
|---|---|
| code | `working-repo/TEXAS-revision/scripts/fit_t0shift_comparison.py` |
| export | `working-repo/TEXAS-revision/scripts/export_cv_results.py` |
| environment | that repo's `pyproject.toml` + `uv.lock` (pandas 3.x) — **not** `texas-env` |
| run | 2026-08-21 09:29, `smoke: false`, 5 folds, n = 1513 (**gridded**), ~3 h of Stan |

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

## Which dataset these are fitted to

n = 1513 is the **gridded** coretop set the reported calibration is fitted to
(`datatype == "coretop"` in `ds_gridded_screened_global_compilation_finalized.csv`),
so these metrics sit on the same footing as the headline ones and can be quoted
beside them.

An earlier run used the ungridded n = 2043 subset and its numbers are **not**
comparable with the headline calibration — the two differ in more than n, since
the ungridded fit gives `R2_thermal` = 0.700 against 0.748 here, so the sigma
prior was scaled off a different thermal curve. That run is preserved at
`working-repo/TEXAS-revision/outputs/`; regenerate with `--dataset gridded`
(now the default) and check `cv_waic_meta.json["dataset"]` before quoting
anything from here.
