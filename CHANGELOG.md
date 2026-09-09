# Changelog

All notable changes to `texas-psm` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Versioning is semantic, with the pre-1.0 convention this project uses: `0.x`
means "manuscript under review", so the public API may change in a minor
release. Every such change is listed below. `1.0.0` is reserved for paper
acceptance.

## [0.4.0] — 2026-09-09

This is the release archived on Zenodo alongside the revised manuscript
submission. It supersedes 0.3.2, which was published to PyPI but never
archived. The version is a minor bump rather than a patch because the public
API changed: see **Removed** below.

### Added

- A bundled thermal-only calibration, selected automatically when
  `predict_T_from_proxyObs` is called with no optional predictors. Four
  calibrations now ship with the wheel; `docs/` describes when each applies.
- `TEXAS.utils.paths.KRIGED_CACHE_DIR` — kriged residual-map grids get their
  own cache folder beside the two posterior caches instead of being written
  loose into the cache root. `set_cache_dir()` repoints all three, and a grid
  still sitting in the old location is read with a printed note.
  `scripts/migrate_kriged_cache.py` moves an existing cache (per machine —
  `data/cache/**` is gitignored).

### Removed

- `TEXAS.generalized_logistic` — the free-upper-asymptote generalized logistic
  (`b + (a - b) / (1 + Q·exp(-k(x - t0)))^(1/v)`). Every shipped Stan model is a
  `_fixed_` upper-asymptote curve and the free-asymptote models live in
  `archive/`, so nothing in the package, the notebooks, the scripts or the docs
  called it. It was also the last Python function to take `Q`, which was dropped
  from all Stan models in 2026-03. Use `generalized_logistic_fixed_upper`.
- `TEXAS.compute_density_based_range` (and `TEXAS.plotting.range_utils.compute_density_based_range`)
  — KDE-based axis range for prior/posterior plots. No caller; the plots use
  `compute_sample_range` and the two suffix/dataset variants.
- `TEXAS.utils.naming.default_version()` — built a `v026`-style token from the
  pip version. The version position was dropped from written case ids on
  2026-08-12 (it still *parses*, so old ids resolve), which left this with no
  caller.
- `TEXAS.utils.naming.describe_compset()` — one-line compset expansion.
  `CaseName.describe()` covers the need and is the one that is used.
- `TEXAS.utils.paths.get_repo_root()`, and its re-exports from `TEXAS.stan` and
  `TEXAS.utils`. Superseded by `get_project_root()`, which has the pip-install
  fallback to `~/.texas/`.
- `TEXAS.utils.system_info.save_system_summary()` — wrote the system summary to
  a timestamped JSON file. `get_system_summary()` and `print_system_summary()`
  are kept; both are used.
- `constraint_type=` and `min_temp=` on `predict_T_from_proxyObs`,
  `predict_temperature_from_proxyObs` and `get_invT_posterior`. The inverse is
  now unconstrained only, which is what the manuscript's reconstructions use.
  The two models they selected —
  `invT_gen_logi_fixed_{univ,multiv}_marginal_truncated_prior.stan` — moved to
  `archive/pre-submission/stan_models/` and remain runnable by passing an
  absolute path as `stan_model_path`. The wheel now ships 7 `.stan` files
  instead of 9. `utils.naming.CONSTRAINT_CODES` is deliberately unchanged: it
  is a name grammar, and case ids already on disk and on Zenodo carry the `t`
  code.
- `TEXAS.predict_temperature_from_proxyObs` / `TEXAS.stan.invT.predict_temperature_from_proxyObs`.
  It was the pre-`predict.py` public entry point and had become a pass-through
  with 27 hand-copied parameters: its only work was reshaping the posterior into
  a percentile dict and optionally writing a `.npz`. Both moved into
  `predict_T_from_proxyObs`, which is the drop-in replacement — pass the
  calibration as `fwd_posterior=` (it takes a name or a Dataset) instead of
  `fwd_posterior_name=`, and `flags=False` if you do not want the quality flags.
- `use_opencl=` on `get_invT_posterior`. OpenCL support was deleted in 2026-05
  and nothing read the `opencl_enabled` attr it set.
- `scaledRI=` on `build_invT_inputData` and `get_invT_posterior`, and the
  `scaledRI_*` → `proxyObs_*` key translation in `auto_detect_predictors`.
  Deprecated since 0.1.x. (The `sigma_scaledRI_*` lookup in `build_invT_inputData`
  stays: it reads variable names inside older posteriors, not a keyword.)
- `model_type=` on `predict_T_from_proxyObs`, `get_invT_posterior` and
  `sampler_invT_posterior`. Only `"direct"` has existed since the ensemble
  models were archived. On `sampler_invT_posterior` it was also a live bug:
  the value was forwarded into `CmdStanModel.sample`, which has no such
  parameter, so any call that passed it raised `TypeError`. (The internal
  `_select_invT_stan_file` still accepts and validates `model_type`; it is
  not part of the public API.)
- `results_path=`, which went with `predict_temperature_from_proxyObs`. The
  `.npz` destination is now `cache_dir` + `filename_tag`, as it already was for
  the `.nc`.

### Changed

- The public API is now guarded. `tests/test_public_api_docs.py` asserts that
  every name in `TEXAS.__all__` resolves, is referenced by at least one test or
  notebook code cell, and (for functions and classes) carries a docstring of at
  least three lines. `ruff`'s `D1` missing-docstring rules are enabled for
  `src/TEXAS`, with `D100`/`D104` (module and package headers) deferred and
  `D105`/`D107` (magic methods, `__init__`) excluded.
- `get_invT_posterior`'s `save=True` is now `save_results=False`, matching
  `predict_T_from_proxyObs`. One name and one default across both layers. The
  function has no caller outside the package, so nothing silently stops saving.
- `proxyObs`, `prior_mu_t` and `prior_sigma_t` are positional-required on
  `get_invT_posterior` and `build_invT_inputData`. They were keyword arguments
  defaulting to `None` that raised `TypeError` at runtime instead.
- `predict_T_from_proxyObs` now returns a percentile key for every quantile the
  posterior carries, derived rather than hard-coded — so `p40` and `p60`, which
  were computed and discarded, are included.
- `predict_T_from_proxyObs` now warns when a calibration uses the NO3
  correction but no `no3=` was supplied, mirroring the existing GDGT-2/3
  warning. NO3 was previously the one predictor/calibration combination of the
  four that stayed silent; omitting a predictor the calibration actually
  applies treats it as 0, which is not the same as switching the correction
  off.

### Fixed

- `shapely` is declared as a dependency. It was imported but undeclared, so a
  clean install could fail at import. The invalid `channel_priority` key was
  also dropped from `environment.yml`.
- The kriged-grid cache no longer writes two copies of one grid: the
  resolution token is formatted with `f"{krige_res:g}"`, so `krige_res=1` and
  `krige_res=1.0` name the same 57 MB file rather than two.
- `streamlit_app/config.py` was missing `DEFAULT_CSV_DIRS`.
- Declared dependencies now match what the code actually imports; five
  packages that were declared but unused were removed, and every notebook's
  top-level imports are checked against the declared set.
