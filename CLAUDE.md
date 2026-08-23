# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

**TEXAS** (`texas-psm`) is a Python package for **Bayesian GDGT–temperature calibration** using Stan models. TEXAS stands for "TetraEther indeX of Ammonia oxidizerS" and it is a proxy system model for TEX86 paleothermometer; an organic proxy for past sea surface temperature reconstructions. It implements a two-stage workflow:

1. **Forward calibration**: Fit a generalized logistic curve (Ring Index → temperature) using hierarchical Bayesian Stan models, producing posterior samples stored as `.nc` files.
2. **Inverse temperature (invT) reconstruction**: Predict paleotemperatures from new Ring Index observations by marginalizing over M parameter sets sampled from the forward posterior.

The proxy system is TEX86/Ring Index (isoGDGT-based paleothermometers), with optional non-thermal predictors (GDGT-2/3 ratio, NO3).

## Environment Setup

```bash
# Create conda environment (primary method)
conda env create -f environment.yml
conda activate texas-env

# Install package in editable mode
pip install -e .

# Or install with all extras
pip install -e ".[all]"
```

CmdStan (≥ 2.23.0; TEXAS is developed against 2.36.0) must be installed and discoverable. `TEXAS/utils/paths.py::find_cmdstan()` searches in priority order: `CMDSTAN` env var → `$CONDA_PREFIX/bin/cmdstan` → `<sys.prefix>/bin/cmdstan` → highest `cmdstan-*` under `/opt/cmdstan/`, `~/.cmdstan/`, `/usr/local/cmdstan/` → cmdstanpy's configured default. A candidate is only accepted if its `bin/stanc` (`stanc.exe` on Windows) both exists and is executable. `set_cmdstan_path()` is always called on the winning path so cmdstanpy's internal state stays consistent. If `CMDSTAN` points to a broken path (dir exists but `stanc` missing/unusable), a `UserWarning` is emitted and the search continues. If nothing is found, a `RuntimeError` is raised with install instructions. `TEXAS.doctor()` / `texas-doctor` diagnoses the whole toolchain (cmdstanpy, CmdStan path/version, C++ compiler, cache dirs) and is encoding-safe (ASCII fallback for Windows cp1252 consoles). `TEXAS.install_cmdstan()` / `texas-install-cmdstan` (`utils/install.py`) is an opt-in one-call installer over `cmdstanpy.install_cmdstan()` — no-ops if already resolvable, steps aside for conda, and auto-`overwrite=True`s a half-built `~/.cmdstan/cmdstan-*` dir. TEXAS never installs CmdStan automatically (no install-on-import, no install-on-first-sample).

> **Development note (editable install)**: always run `pip install -e .` after cloning. A regular `pip install texas-psm` puts the package in site-packages (no compiled Stan binaries, no local source changes). Without `-e`, `STAN_MODELS_DIR` points to site-packages and every Stan model must recompile from scratch on first use.

## Common Commands

```bash
# Run tests
pytest

# Build docs (unified Jupyter Book: guides + autodoc API + tutorial)
jupyter-book build docs/   # output in docs/_build/html/

# Run Streamlit app (from streamlit_app/ directory)
streamlit run main.py

# Build Docker image (for isolated Stan compilation)
docker compose up
```

## Architecture

### Package layout (`src/TEXAS/`)

| Module | Purpose |
|---|---|
| `stan/compiler.py` | `StanCompiler`: wraps `CmdStanModel` with in-memory + disk caching; `force=True` clears binary; auto-detects stale/cross-environment binaries (exit code 127 → delete + recompile with `RuntimeWarning`) |
| `stan/sampler.py` | `StanSampler` + functional API `get_posterior()` / `sampler_invT_posterior()`; auto-detects optional predictors |
| `stan/io.py` | `save_posterior()` / `load_posterior()` / `save_invT_posterior()` — persists xarray.Dataset as compressed NetCDF |
| `stan/metadata.py` | Extracts and attaches metadata + prior strings to posterior datasets |
| `data/builder.py` | `build_fwd_data()` — builds validated Stan data dict for forward calibration (proxyObs_* keys, auto use_* flags, no3_cutoff auto-calc); `build_invT_inputData()` + `InvTConfig` — bridges forward → inverse by sampling M parameter sets from a forward posterior |
| `data/filter.py` / `data/screening.py` | Data cleaning and Mahalanobis screening |
| `models/logistics.py` | Pure-Python logistic / generalized-logistic functions |
| `models/multivariate.py` | Multivariate variants (GDGT23ratio, NO3 corrections) |
| `models/calibration.py` | `TEX86Calibration` + `CalibrationRegistry` — classical (non-Bayesian) TEX86 calibrations |
| `ensemble/generator.py` | `generate_ensemble()` / `generate_ensemble_auto()` — samples draws from a posterior and computes calibration curve percentiles |
| `ensemble/detection.py` | `detect_model_and_params()` — infers suffix, model function, and flags from posterior attributes |
| `diagnostics.py` | `summarize_sampler_diagnostics()` — divergences, R-hat, ESS, E-BFMI; attaches as `stan_diag_*` attrs |
| `plotting/` | Range utilities and prior distribution plots |
| `utils/paths.py` | All path constants (`STAN_MODELS_DIR`, `POSTERIOR_CACHE_DIR`, `INVT_CACHE_DIR`, etc.) |
| `constants.py` | `OPTIONAL_PREDICTORS`, `DEFAULT_SUFFIXES` |

> **Deprecated modules removed (2026-05-31)**: `stan/auto.py` (OpenCL auto-detect invT variant), `utils/hw.py` (OpenCL/hardware detection), and `utils/cache_search.py` were deleted — they were marked deprecated and unused by the live package (only `auto.py` imported `hw.py`). Do not reintroduce references to them.

### Stan models (`src/TEXAS/stan_models/`)

Model names follow a naming convention: `{transform}_{curve}_{params}_{datasources}_{variant}.stan`

- **Transform prefix**: `invT_` = inverse temperature model; no prefix = forward calibration model
- **Curve type**: `gen_logi` = generalized logistic; `logistic` = standard logistic; `linear` = linear
- **Params**: `fixed` = fixed upper asymptote; `free` = free upper asymptote
- **Data sources**: `culmeso` = culture+mesocosm; `culmesocore` = culture+mesocosm+coretop; `crtp` = coretop-only
- **Variants**: `hier_crtp` = hierarchical coretop; `multiv` = multivariate (GDGT23/NO3); `priorApprox` = prior approximation; `werr` = delta-method EIV (heteroscedastic likelihood, no latent vars); `werr_ver2` = latent-variable EIV with quadrature RI error + process-noise separation (see below); `odr` = delta-method EIV in the full hierarchical (non-priorApprox) model; `marginal_*` = marginalized variants; `reduce_sum` = parallelized with `reduce_sum`

### Parameter suffix convention

Posterior variables carry a suffix indicating which dataset they were estimated from:

- `crtp` — coretop only (highest priority for invT reconstruction)
- `culmesocore` — culture + mesocosm + coretop
- `culmeso` — culture + mesocosm
- `meso` — mesocosm only
- `cul` — culture only

Example: `t0_crtp`, `k_crtp`, `b_crtp`, `v_crtp`, `sigma_proxyObs_crtp`.

> **Q parameter removed (2026-03-24, Python cleanup 2026-03-24)**: The asymmetry parameter Q has been dropped from all Stan models (both forward and invT). The generalized logistic curve now uses Q=1, so T₀ is the curve's location parameter. **T₀ is not the inflection point** unless ν=1: the steepest response sits at `T₀ − ln(ν)/k`, which for the fitted ν of 2.1–4.0 is 4.2–5.2 °C *below* T₀ (verified 2026-08-13 across the bounded-T, additive-EIV, univariate and culmeso posteriors). Do not quote a single thermal sensitivity for this curve — f′ varies ~6× over the sampled range. All existing `.stan` files were edited in-place — the `gen_logi_fixed_Q1_culmeso.stan` placeholder has been deleted. `ensemble/detection.py` no longer detects Q; `plotting/prior_plot.py` no longer lists Q in `include_groups` or label dicts. Cached `.nc` posteriors generated before this change contain `Q_crtp`/`Q_culmeso` variables that are no longer produced; regenerate them.

> **Stan model bound fixes (2026-03-24)**:
> - `k_crtp upper=0.5 → removed` in all priorApprox models (`gen_logi_fixed_hier_crtp_*_priorApprox*.stan`): the standalone culmeso model has no upper cap on k, and its posterior mean (~0.57) exceeded the old bound, pinning k against the constraint.
> - `b_crtp upper=0.6 → upper=1.0` in all priorApprox models: same class of bug; joint models already used `upper=1`.
> - `v prior T[0, ] → T[0.1, ]` in `gen_logi_fixed_culmesocore.stan`: prior truncation must match the `lower=0.1` parameter declaration (mismatched truncation gives an incorrect normalizing constant).
> - `.gitignore` negation `!src/TEXAS/stan_models/*.stan` added so Stan source files created after the binary-glob rule are not silently untracked.

> **Stan model prior fix (2026-04-08)**:
> - `sigma_proxyObs_crtp ~ normal(0.01, 0.1) → normal(0, 0.1)` in 5 files: `gen_logi_fixed_hier_crtp_multiv.stan`, `gen_logi_fixed_hier_crtp_multiv_priorApprox.stan`, `gen_logi_fixed_hier_crtp_univ_priorApprox.stan`, `gen_logi_fixed_culmesocore.stan` (and the former `_werr.stan`, now superseded). The old prior mean (0.01) was ~5× below the posterior (~0.05); `normal(0, 0.1)` is the conventional half-normal weakly informative prior for scale parameters. Cached `.nc` posteriors from these models must be regenerated.

> **EIV Stan model consolidated (2026-04-16, v0.1.5)**:
> The sole EIV model is now `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv.stan`. Earlier development variants (`_werr.stan`, `_werr_ver2.stan`, `_odr.stan`, archived variants) have been removed. Cached posteriors were renamed in-place (`_werr_ver2` → `_eiv`); no resampling needed.
>
> **`_eiv` model design** — latent-variable EIV with analytical RI SE separation:
> - `sd_proxyObs` (per-site RI analytical SE; default Rs = 0.03, Schouten et al. 2013) enters the likelihood in quadrature: `total_sd = √(sd_proxyObs² + sigma_proxyObs_crtp²)`. `sigma_proxyObs_crtp` is therefore *pure process noise* (oceanographic scatter, bioturbation) only.
> - `sigma_proxyObs_crtp` prior scaled to `mean(sd_proxyObs) · √(1 − R²_thermal)`. `R2_thermal` must be passed as data (pre-compute from a thermal-only non-EIV coretop run). `sampler.py` raises `ValueError` if missing.
> - G₂/₃ latent variable: `true_gdgt23ratio_crtp ~ normal(0, 2)` with normal measurement model. Sites with `sd_gdgt23ratio_crtp[i] = 0` receive only the prior.
> - NO₃ latent variable: `true_no3_crtp ~ lognormal(log(0.3), 1.0)` with `<lower=0, upper=no3_cutoff>` — upper bound prevents `exp()` overflow during HMC. Sites with `sd_no3_crtp[i] = 0` receive only the prior. No CV-gating.
> - `build_fwd_data()` always includes `sd_gdgt23ratio_crtp` and `sd_no3_crtp` (defaulting to zeros), and always includes `sd_proxyObs` (defaulting to 0.03). `R2_thermal` must be provided explicitly.

### Posterior caching

Posteriors are saved as compressed NetCDF (`.nc`) in:
- `data/cache/TEXAS_posterior_cache/` — forward calibration posteriors
- `data/cache/TEXAS_invT_posterior_cache/` — inverse temperature posteriors

Forward posterior filenames follow: `{model}_{temptype}_{proxy_name}{suffix}.nc`
e.g. `gen_logi_fixed_hier_crtp_multiv_SST_scaledRI.nc`
Optional predictor flags (`_gdgt23ratio`, `_no3_1.5`) are appended to `temptype` before `proxy_name`.
`proxy_name` is omitted from the filename only if not set (falls back to old pattern for backward compat).

> **CESM-style case naming (2026-08-09)**: `utils/naming.py` replaces the
> concatenated-description filenames (95–122 chars, growing with every new axis)
> with fixed dot-delimited positions, so tokens stay short:
>
> ```
> tx.v026.GHEB.sst.sri03.G23-N1p0.001/                          <- the case
>     tx.v026.GHEB.sst.sri03.G23-N1p0.001.fwd.nc                <- forward posterior
>     tx.v026.GHEB.sst.sri03.G23-N1p0.001.inv.U1482.ud-050126.nc <- a reconstruction
> ```
>
> Positions: project, version, **compset**, target temperature, proxy,
> predictors, run/member. The 4-char compset encodes curve (`G` gen_logi_fixed,
> `L` logistic, `N` linear), training set (`H` hier_crtp, `C` culmeso,
> `J` culmesocore, `T` crtp), estimator (`P` priorApprox, `E` priorApprox+EIV,
> `D` full hierarchical), and predictor structure (`U` univariate, `A` additive
> β-on-μ, `B` bounded-by-construction — the manuscript's "T₀-shift parameterization",
> γ-on-T₀; the letter names the property, the paper names the mechanism).
> So `..._hier_crtp_multiv_priorApprox_eiv_t0shift` → `GHEB`. Predictors are
> `G23` and `N` + the cutoff with `p` for the decimal point (`N1p0` = cutoff
> 1.0), or `p0` when there are none.
>
> > **`N10` → `N1p0` rename (2026-08-23).** The nitrate token was `N` + cutoff×10,
> > so a cutoff of 1.0 µmol/L was written `N10` — misreadable in the one way that
> > matters, since **10 is also the documented value for switching the NO₃
> > correction off**. A token could therefore be read as the opposite of what it
> > means. `encode_predictors` now writes `N1p0` (`_fmt_cutoff`, `p` for the
> > decimal point since `.` delimits the fields); `N10` still *parses*, so every
> > case id in the cache, in notebooks and in `case_ids.json` keeps resolving.
> > Nothing on disk was renamed except the two bundled posteriors.
> >
> > Files on disk were renamed on 2026-08-23 by
> > `scripts/rename_cache_files.py` (dry-run by default, refuses on any
> > destination clash, `--revert` to undo): 191 files across both caches,
> > `.npz` siblings moved with their `.nc`. This is per-machine — `data/cache/**`
> > is gitignored, so run it on the Windows box too.
> >
> > `resolve_posterior_path` now normalises the predictor token on **both**
> > sides before comparing, and tries both spellings on the exact-path lookups,
> > because an id and the file it names can sit on opposite sides of the rename
> > in either direction — a notebook holding `N10` must find a posterior written
> > today, and `N1p0` must find one in an old cache. Pinned by
> > `tests/test_naming.py`.
>
> > **Posterior attrs normalised (2026-08-23).** `scripts/normalize_posterior_attrs.py`
> > edits cached posteriors' attrs in place through netCDF4 (append mode, so the
> > draws are never rewritten — verified byte-identical, +87 bytes of header):
> > `stan_model_name` `..._eiv_boundedT` → `..._eiv_t0shift` on the 8 `GHEB`
> > files, `case_id` refreshed to the current predictor token, and the duplicate
> > **`model` and `version` attrs dropped**, and `generated_by` corrected from
> > `culRI-Bayesian` (the project's name years before it was TEXAS) to
> > `texas-psm`. `model` was arviz echoing CmdStan's own config key —
> > `stan_model_name` + `"_model"`, identical in all 33 cached files — and it is
> > the reason a rename could leave one name stale while the other was current.
> > `version` was `extract_and_update_metadata()`'s own default argument,
> > literally `"1.0.0"` everywhere, set by no caller and read by nothing.
> > `sampler.py` and `metadata.py` no longer write either: **`stan_model_name`
> > is the single model name and `texas_version` the single version**, and
> > `texas_version` is *not* backfilled onto older files, because which package
> > produced them is not recoverable and absent is the honest answer. The
> > bundled pair additionally carries `bundled_with`, which is a different fact
> > — the version that built the bundle, not the one that sampled the draws. `filename` is deliberately left as written (it is history, not
> > identity, and legacy stamped lookups match on it), and `superseded/` is not
> > touched at all. Dry-run by default.
> >
> > **`boundedT` → `t0shift` rename (2026-08-15).** The variant token in Stan
> > file names, figure names, notebook names, and scripts is now `t0shift`,
> > matching the revised manuscript's "T₀-shift parameterization". The legacy
> > `boundedT` spelling still *parses* (`encode_compset` maps both to `B`), so
> > cached posteriors with old `stan_model_name` attrs and legacy `.nc`/`.pkl`
> > cache files resolve unchanged — nothing in `data/cache/` was renamed.
> > Renamed Stan models recompile on next use.
> >
> > **Notebook switch keys followed on 2026-08-21.** They were left alone
> > initially on the grounds that they name runtime branches, not artifacts —
> > which was wrong: `SI03_paleo_showcases_modelswitch` interpolates
> > `MODEL_VARIANT` straight into two output names
> > (`figSI_variant_comparison_{variant}_vs_{other}.pdf`,
> > `data_list_extreme_example_{variant}.pkl`), so the branch key *is* an
> > artifact name. `MODEL_VARIANT`, the `VARIANTS`/`COMPSET`/`MU` dict keys,
> > and `parameterization=` in `SI_code01` now all read `t0shift`, and those
> > two outputs were renamed on disk to match. Executed cell *outputs* still
> > show the old spelling until each notebook is re-run; that is a record of
> > what ran, not stale code.
> >
> > The same pass renamed `coretop_maps_boundedT_manifest.csv` →
> > `coretop_maps_t0shift_manifest.csv` (`run_coretop_maps.py` already looked
> > for the new name, so a resumed `--arm bnd` run had been finding no manifest
> > at all) and deleted `coretop_maps_boundedT_sites.csv`, a byte-identical
> > leftover of the arm-independent `coretop_maps_sites.csv` that `SI_code04`
> > now reads. In `working-repo/TEXAS-revision`: `fit_boundedT_comparison.py` →
> > `fit_t0shift_comparison.py`, `inspect_boundedT.ipynb` →
> > `inspect_t0shift.ipynb`, and the local `..._eiv_boundedT.stan` →
> > `..._eiv_t0shift.stan`. Only `boundedT-explainer.html` keeps the old token,
> > because its prose does too.
>
> **Proxy codes** read as *s*caled + *ri* + crenarchaeol ring count:
> `sri03` = `scaledRI_cren3` (crenarchaeol counted as 3 rings), `sri04` =
> `scaledRI_cren4` (the RI₀₋₄ convention of Zhang et al.), `sri` = `scaledRI`,
> `tex` = `TEX86`, `tri03` = `TEXRI_cren3`.
>
> > **Token spellings changed 2026-08-11** (`ri3`→`sri03`, `none`→`p0`, and the
> > leaf gained its case prefix). The old spellings still *parse*, so case
> > directories already on disk keep resolving, but they are no longer written.
> > `TEXRI_cren3` previously shared the code `ri3` with `scaledRI_cren3`, which
> > silently collapsed two distinct proxies onto one case id; it is now `tri03`.
>
> **Why each leaf repeats its case.** CESM names data output for its case
> (`b.e12.B1850C5CN.f19_g16.iPETM09x.01.pop.h.1901-2000.climo.nc`) and reserves
> bare names for case *control* files that never leave the directory. A
> posterior does leave — decisively, it is published to a Zenodo record whose
> namespace is **flat**, where fifteen files named `fwd.nc` cannot coexist.
> This is not free: the full path grows from 39 to 72 characters versus a bare
> `fwd.nc`. What it buys is a leaf that is still self-identifying once detached,
> and the leaf itself still drops ~100 → ~41 characters against the legacy name.
> `download_posteriors()` unpacks a flat Zenodo file into its case directory
> (`utils/download.py::_local_dest`) so the local cache has one uniform layout
> whether a posterior was sampled here or downloaded.
>
> - **The case is the forward calibration.** An invT model name records the curve
>   and constraint but not the training set or estimator, so a reconstruction is
>   named as a member *of* its parent case, not as a case of its own. This relies
>   on the `fwd_case` / `fwd_posterior_name` attrs that `build_invT_inputData`
>   now attaches — invT posteriors written before this carry no provenance and
>   fall back to the legacy flat name automatically.
> - **The run position** (`.001`) is CESM's ensemble-member field; `save_posterior`
>   maps `filename_suffix` (e.g. a `050126` date stamp) onto it, which is what
>   stops two refits of one configuration from colliding.
> - **Dual-read, write-new.** Nothing on disk was renamed. `load_posterior()`
>   accepts *either* a case id or a legacy long name and finds the file under
>   *either* layout (exact-path lookups first, attr-matching scan only as a
>   fallback), so existing caches, Zenodo downloads, and old notebooks keep
>   working. `save_posterior(..., layout=)` takes `"auto"` (default, prefers case),
>   `"case"`, or `"legacy"`.
>
> **Status of the inverse half (audited 2026-08-11) — the forward side is wired,
> the inverse side is only half-wired. Do not assume otherwise:**
> - `naming.inv_relpath()` is the documented canonical inverse-name builder and
>   **nothing outside `tests/` calls it.** The production path is
>   `io._generate_filename_base()`, which reimplements a *different* leaf format
>   inline (no run number).
> - `save_invT_posterior()` (`stan/io.py:269`, exported in `__all__`) is entirely
>   case-unaware and **silently drops `proxy_name`**, so a `scaledRI` and a
>   `TEX86` run of one site overwrite each other.
> - ~~`case_from_attrs()` cannot recover `filename_suffix`.~~ **Fixed
>   2026-08-11.** `run_from_attrs()` recovers the run token from the `filename`
>   attr, which `save_posterior` stamps onto every dataset and which keeps its
>   date suffix even after a file is renamed without one. Refits now get
>   distinct runs instead of all collapsing onto `.001`. `save_posterior` still
>   passes a run explicitly, so a genuinely new fit never inherits a stale
>   stamp.
>
> Tracked as Phase 5 in `RESUME.md` on `feat/revision1-validation-groupA`.

#### Renaming an existing cache onto the case layout

`scripts/migrate_cache_layout.py` converts forward posteriors — legacy flat
files *and* case directories written before 2026-08-11 — onto
`<case>/<case>.fwd.nc`.

```bash
python scripts/migrate_cache_layout.py                  # dry run: print the plan
python scripts/migrate_cache_layout.py --apply          # copy into place, verify each
python scripts/migrate_cache_layout.py --apply --prune  # then delete the sources
python scripts/migrate_cache_layout.py --cache /some/other/dir
```

It is **dry-run by default**, copies before it deletes, re-opens every copy and
checks the case id matches the directory, and **exits 1 without touching
anything if two files claim one case id** — that guard is what makes it safe to
run unattended.

**This is per-machine, and the plan will differ on each one.** `data/cache/**`
is gitignored, so it does not travel with a clone: the Linux box and the
Windows box hold different posteriors. Never assume a migration done on one
machine has happened on another — run the dry run first and read it. The only
prerequisites are an editable install (`pip install -e .`, so `TEXAS` imports)
and `xarray`; no CmdStan, no compilation, no network.

**Inverse posteriors are deliberately skipped.** An invT model name records the
curve and constraint but not the training set or estimator, so for any file
without a `fwd_case` attr the parent case is unrecoverable, and inventing one
would record a guess as provenance. Leave them on the legacy dual-read path.

**Nothing is lost if the leaf names are wrong** — `load_posterior()` reads
legacy flat names, `<case>/fwd.nc`, and `<case>/<case>.fwd.nc` alike, and old
`ri3` / `none` tokens still parse. Migration is a tidiness step, not a
correctness one.

##### Renaming and re-running are NOT equivalent for old names

| you ask `load_posterior()` for | after **migrating** | after **re-running Stan** |
|---|---|---|
| the new case id | ✅ | ✅ |
| the unstamped legacy name (`..._scaledRI_cren3`) | ✅ | ✅ |
| a **date-stamped** legacy name (`..._cren3_050126_eiv`) | ✅ | ❌ |

The difference is where the old name lives. Migration **copies the `filename`
attr through untouched**, so the file still remembers what it was called and
`resolve_posterior_path` matches on it. A re-run writes a *new* file and
`save_posterior` stamps the *new* leaf name onto `filename` — nothing on disk
remembers the old one. The unstamped form keeps working either way because it
is reconstructed from attrs by `legacy_fwd_name()` rather than remembered.

This matters because `SI_code3_paleo_showcases.ipynb` and
`SI03_paleo_showcases_modelswitch.ipynb` both request a stamped name
(`..._scaledRI_cren3_050126_eiv`). **If you re-run those calibrations rather
than migrating, update the notebooks to the case id.** Both behaviours are
pinned by tests in `tests/test_naming.py`.

### Streamlit app (`streamlit_app/`)

Three-tab GUI:
1. **Predict**: upload CSV → run invT reconstruction
2. **Explore**: upload NetCDF posterior → plot distributions
3. **Compute**: run forward calibration in-browser (limited; heavy jobs should use notebooks)

Entry point: `streamlit_app/main.py`. Config (cache dir resolution, plot defaults): `streamlit_app/config.py`.

### Notebooks

- `notebooks/current/` — active analysis notebooks
- `notebooks/manuscripts/` — finalized figure-generation notebooks for papers

### Documentation (`docs/`)

The docs are a **single unified Jupyter Book** (Sphinx), migrated from
mkdocs-material on 2026-05-30. `docs/_config.yml` + `docs/_toc.yml` define one
book covering the guides, the autodoc API reference, the explainers, and the
interactive tutorial (`docs/tutorial/`).

- **Build**: `jupyter-book build docs/` (pin `jupyter-book<2` — v2/MyST does not
  read the `jb-book` `_toc.yml`/`_config.yml` format). Output in `docs/_build/html/`.
- **API reference** (`docs/api.md`): Sphinx `autodoc` + `napoleon` (both Google
  and NumPy docstrings). Optional/heavy deps are mocked via `autodoc_mock_imports`
  in `_config.yml`, so a core install builds the API page.
- **Branding**: `docs/_static/texas_logo.svg` (colorblock TEXAS wordmark) +
  `docs/_static/custom.css` (steel-blue accent), derived from the AGU25 poster.
- **Deploy**: `.github/workflows/docs.yml` builds the book and publishes
  `docs/_build/html` to `gh-pages` on push to `main`. Live at
  <https://paleolipidrr.github.io/TEXAS/>. There is no longer an `mkdocs.yml`.

## Key Patterns

**Forward data construction**: `build_fwd_data()` in `data/builder.py` is the recommended way to build the Stan data dict — it enforces `proxyObs_*` key naming, validates array shapes, auto-sets `use_gdgt23ratio` / `use_no3` flags, and auto-calculates `no3_cutoff` via Spearman rank correlation if omitted. For two-stage `priorApprox` models, pass `culmeso_posterior=` to extract hyperpriors automatically. Hyperpriors for `t0`, `k`, `b`, `v` are extracted as raw mean/std from the culmeso posterior. Q is no longer a parameter (fixed to 1 in all models).

**Optional predictor auto-detection**: `auto_detect_predictors()` in `stan/sampler.py` inspects the data dict for GDGT23/NO3 arrays and sets `use_gdgt23ratio` / `use_no3` integer flags for Stan. Also translates legacy `scaledRI_*` data keys to `proxyObs_*` with a `DeprecationWarning` for backward compatibility.

**Posterior metadata**: After sampling, `extract_and_update_metadata()` attaches run info (model name, temptype, priors, duration, diagnostic summary) as `xr.Dataset.attrs`. The `proxy_name` attr (e.g. `"scaledRI"`, `"TEX86"`) is required at `get_posterior()` call time and is always written to `.nc` files via `_sanitize_attrs_for_netcdf`. Downstream code reads these attrs for decisions (e.g., `ensemble/detection.py` reads `use_gdgt23ratio`, `use_no3`, `no3_cutoff` from attrs and infers model function from data_vars — it does not read `stan_model_name`).

**Forward → inverse pipeline**:
```python
# 1. Forward calibration
data = build_fwd_data(
    t_cul=cul_df["SST"].values,   proxy_cul=cul_df["scaledRI"].values,
    t_meso=meso_df["SST"].values, proxy_meso=meso_df["scaledRI"].values,
    t_crtp=crtp_df["SST"].values, proxy_crtp=crtp_df["scaledRI"].values,
    gdgt23ratio_crtp=crtp_df["gdgt23ratio"].values,
    no3_crtp=crtp_df["no3"].values,  # no3_cutoff auto-calculated via Spearman if omitted
)
post, diag = get_posterior(data, "gen_logi_fixed_hier_crtp_multiv", temptype="SST", proxy_name="scaledRI")
save_posterior(post)  # → gen_logi_fixed_hier_crtp_multiv_SST_scaledRI.nc

# 2. Inverse reconstruction
data_inv, kwargs = build_invT_inputData(proxyObs, prior_mu_t, prior_sigma_t, fwd_posterior_name="...")
post_inv, diag = sampler_invT_posterior(data_inv, "invT_gen_logi_fixed_multiv", **kwargs)
```
