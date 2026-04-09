# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

**TEXAS** (`texas-psm`) is a Python package for **Bayesian GDGT–temperature calibration** using Stan models. TEXAS stands for "TetraEther indeX for Ammonia oxidizerS" and it is a proxy system model for TEX86 paleothermometer; an organic proxy for past sea surface temperature reconstructions. It implements a two-stage workflow:

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

CmdStan 2.36.0 must be installed and discoverable. `TEXAS/utils/paths.py::find_cmdstan()` searches `~/.cmdstan/`, `/opt/cmdstan/`, and the `CMDSTAN` environment variable.

## Common Commands

```bash
# Run tests
pytest

# Build docs
mkdocs serve  # from docs/

# Run Streamlit app (from streamlit_app/ directory)
streamlit run main.py

# Build Docker image (for isolated Stan compilation)
docker compose up
```

## Architecture

### Package layout (`src/TEXAS/`)

| Module | Purpose |
|---|---|
| `stan/compiler.py` | `StanCompiler`: wraps `CmdStanModel` with in-memory + disk caching; `force=True` clears binary |
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

### Stan models (`src/TEXAS/stan_models/`)

Model names follow a naming convention: `{transform}_{curve}_{params}_{datasources}_{variant}.stan`

- **Transform prefix**: `invT_` = inverse temperature model; no prefix = forward calibration model
- **Curve type**: `gen_logi` = generalized logistic; `logistic` = standard logistic; `linear` = linear
- **Params**: `fixed` = fixed upper asymptote; `free` = free upper asymptote
- **Data sources**: `culmeso` = culture+mesocosm; `culmesocore` = culture+mesocosm+coretop; `crtp` = coretop-only
- **Variants**: `hier_crtp` = hierarchical coretop; `multiv` = multivariate (GDGT23/NO3); `priorApprox` = prior approximation; `marginal_*` = marginalized variants; `reduce_sum` = parallelized with `reduce_sum`

### Parameter suffix convention

Posterior variables carry a suffix indicating which dataset they were estimated from:

- `crtp` — coretop only (highest priority for invT reconstruction)
- `culmesocore` — culture + mesocosm + coretop
- `culmeso` — culture + mesocosm
- `meso` — mesocosm only
- `cul` — culture only

Example: `t0_crtp`, `k_crtp`, `b_crtp`, `v_crtp`, `sigma_proxyObs_crtp`.

> **Q parameter removed (2026-03-24, Python cleanup 2026-03-24)**: The asymmetry parameter Q has been dropped from all Stan models (both forward and invT). The generalized logistic curve now uses Q=1 (inflection point = T₀). All existing `.stan` files were edited in-place — the `gen_logi_fixed_Q1_culmeso.stan` placeholder has been deleted. `ensemble/detection.py` no longer detects Q; `plotting/prior_plot.py` no longer lists Q in `include_groups` or label dicts. Cached `.nc` posteriors generated before this change contain `Q_crtp`/`Q_culmeso` variables that are no longer produced; regenerate them.

> **Stan model bound fixes (2026-03-24)**:
> - `k_crtp upper=0.5 → removed` in all priorApprox models (`gen_logi_fixed_hier_crtp_*_priorApprox*.stan`): the standalone culmeso model has no upper cap on k, and its posterior mean (~0.57) exceeded the old bound, pinning k against the constraint.
> - `b_crtp upper=0.6 → upper=1.0` in all priorApprox models: same class of bug; joint models already used `upper=1`.
> - `v prior T[0, ] → T[0.1, ]` in `gen_logi_fixed_culmesocore.stan`: prior truncation must match the `lower=0.1` parameter declaration (mismatched truncation gives an incorrect normalizing constant).
> - `.gitignore` negation `!src/TEXAS/stan_models/*.stan` added so Stan source files created after the binary-glob rule are not silently untracked.

> **Stan model prior fix (2026-04-08)**:
> - `sigma_proxyObs_crtp ~ normal(0.01, 0.1) → normal(0, 0.1)` in 5 files: `gen_logi_fixed_hier_crtp_multiv.stan`, `gen_logi_fixed_hier_crtp_multiv_priorApprox.stan`, `gen_logi_fixed_hier_crtp_univ_priorApprox.stan`, `gen_logi_fixed_hier_crtp_multiv_priorApprox_werr.stan`, `gen_logi_fixed_culmesocore.stan`. The old prior mean (0.01) was ~5× below the posterior (~0.05); `normal(0, 0.1)` is the conventional half-normal weakly informative prior for scale parameters. Cached `.nc` posteriors from these models must be regenerated.

### Posterior caching

Posteriors are saved as compressed NetCDF (`.nc`) in:
- `data/cache/TEXAS_posterior_cache/` — forward calibration posteriors
- `data/cache/TEXAS_invT_posterior_cache/` — inverse temperature posteriors

Forward posterior filenames follow: `{model}_{temptype}_{proxy_name}{suffix}.nc`
e.g. `gen_logi_fixed_hier_crtp_multiv_SST_scaledRI.nc`
Optional predictor flags (`_gdgt23ratio`, `_no3_1.5`) are appended to `temptype` before `proxy_name`.
`proxy_name` is omitted from the filename only if not set (falls back to old pattern for backward compat).

### Streamlit app (`streamlit_app/`)

Three-tab GUI:
1. **Predict**: upload CSV → run invT reconstruction
2. **Explore**: upload NetCDF posterior → plot distributions
3. **Compute**: run forward calibration in-browser (limited; heavy jobs should use notebooks)

Entry point: `streamlit_app/main.py`. Config (cache dir resolution, plot defaults): `streamlit_app/config.py`.

### Notebooks

- `notebooks/current/` — active analysis notebooks
- `notebooks/manuscripts/` — finalized figure-generation notebooks for papers

## Key Patterns

**Forward data construction**: `build_fwd_data()` in `data/builder.py` is the recommended way to build the Stan data dict — it enforces `proxyObs_*` key naming, validates array shapes, auto-sets `use_gdgt23ratio` / `use_no3` flags, and auto-calculates `no3_cutoff` via Spearman rank correlation if omitted. For two-stage `priorApprox` models, pass `culmeso_posterior=` to extract hyperpriors automatically. Hyperpriors for `t0`, `k`, `b`, `v` are extracted as raw mean/std from the culmeso posterior. Q is no longer a parameter (fixed to 1 in all models).

**Optional predictor auto-detection**: `auto_detect_predictors()` in `stan/sampler.py` inspects the data dict for GDGT23/NO3 arrays and sets `use_gdgt23ratio` / `use_no3` integer flags for Stan. Also translates legacy `scaledRI_*` data keys to `proxyObs_*` with a `DeprecationWarning` for backward compatibility.

**Posterior metadata**: After sampling, `extract_and_update_metadata()` attaches run info (model name, temptype, priors, duration, diagnostic summary) as `xr.Dataset.attrs`. The `proxy_name` attr (e.g. `"scaledRI"`, `"TEX86"`) is required at `get_posterior()` call time and is always written to `.nc` files via `_sanitize_attrs_for_netcdf`. Downstream code reads these attrs for decisions (e.g., `ensemble/detection.py` reads `stan_model_name` and `use_gdgt23ratio`).

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
