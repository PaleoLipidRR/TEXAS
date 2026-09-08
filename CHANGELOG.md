# Changelog

All notable changes to `texas-psm` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Versioning is semantic, with the pre-1.0 convention this project uses: `0.x`
means "manuscript under review", so the public API may change in a minor
release. Every such change is listed below. `1.0.0` is reserved for paper
acceptance.

## [Unreleased]

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

### Changed

- The public API is now guarded. `tests/test_public_api_docs.py` asserts that
  every name in `TEXAS.__all__` resolves, is referenced by at least one test or
  notebook code cell, and (for functions and classes) carries a docstring of at
  least three lines. `ruff`'s `D1` missing-docstring rules are enabled for
  `src/TEXAS`, with `D100`/`D104` (module and package headers) deferred and
  `D105`/`D107` (magic methods, `__init__`) excluded.
