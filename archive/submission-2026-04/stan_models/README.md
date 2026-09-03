# Archived Stan models — initial submission (2026-04)

These eight models were used during development and in the **initial submission**
of the TEXAS manuscript. They are kept here, in the repository, so that every
result the paper reports remains reproducible — but they are no longer shipped
in the installed package.

`pyproject.toml` declares package data as `stan_models/*.stan`, a non-recursive
glob rooted at `src/TEXAS/stan_models/`. Nothing in this directory reaches the
wheel. `src/TEXAS/stan_models/` now contains only the nine models the revised
manuscript and the public API actually use.

## What moved, and why

| file | why it is archived |
|---|---|
| `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv.stan` | The **initial submission's production calibration** (compset `GHEA`, additive β-on-μ). Superseded by the T₀-shift parameterization (`GHEB`), but it is the comparison arm the revised manuscript reports against, so it must stay reproducible. |
| `gen_logi_fixed_hier_crtp_multiv_priorApprox.stan` | Superseded non-EIV multivariate intermediate. |
| `gen_logi_fixed_hier_crtp_multiv.stan` | Superseded full-hierarchical (non-`priorApprox`) intermediate. |
| `gen_logi_fixed_culmesocore.stan` | Joint culture+mesocosm+coretop fit; not used by any manuscript notebook. |
| `invT_gen_logi_fixed_univ_unconstrained.stan` | Non-marginal (ensemble) inverse; superseded by the `_marginal_` variants, which are far faster. |
| `invT_gen_logi_fixed_multiv_unconstrained.stan` | Non-marginal (ensemble) inverse; same reason. |
| `invT_gen_logi_fixed_univ_marginal_hard_constraint.stan` | Hard lower bound on T. Jacobian-biased near the boundary; the truncated-prior formulation replaced it. Zero references anywhere in the repo. |
| `invT_gen_logi_fixed_multiv_marginal_hard_constraint.stan` | Same. |

## What still ships (`src/TEXAS/stan_models/`, 9 files)

| file | role |
|---|---|
| `gen_logi_fixed_culmeso.stan` | Stage-1 culture+mesocosm fit; supplies the `priorApprox` hyperpriors. |
| `gen_logi_fixed_hier_crtp_univ_priorApprox.stan` | Thermal-only coretop fit; also the source of `R2_thermal`, which the EIV model requires as data. |
| `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift.stan` | **The production calibration** (compset `GHEB`). Both bundled posteriors were fit with it. |
| `invT_gen_logi_fixed_multiv_marginal_unconstrained_t0shift.stan` | Production inverse. |
| `invT_gen_logi_fixed_multiv_marginal_unconstrained.stan` | Multivariate inverse comparator. |
| `invT_gen_logi_fixed_univ_marginal_unconstrained.stan` | Univariate inverse (quickstart, SI_code03). |
| `invT_gen_logi_fixed_{univ,multiv}_marginal_truncated_prior.stan` | Reachable via `constraint_type="truncated_prior"`, and the subject of `docs/why_plugin_p50_differs.md`. |
| `linear_model.stan` | Used by the SI preprocessing and analysis notebooks. |

## How to run an archived model

`get_posterior()` constructs its `StanCompiler` without a `model_dir`, so these
files are not on the default search path. `StanCompiler.resolve_stan_path()`
does pass an **absolute** path straight through, however, so give it one:

```python
from pathlib import Path
from TEXAS import build_fwd_data, get_posterior

ARCHIVE = Path("archive/submission-2026-04/stan_models").resolve()

post, diag = get_posterior(
    data=build_fwd_data(...),
    stan_file=str(ARCHIVE / "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv.stan"),
    temptype="SST",
    proxy_name="scaledRI",
)
```

The compiler copies the source into `STAN_BUILD_DIR` (`~/.texas/stan_cache/`)
before compiling, so running from here writes no build artifacts into the
repository.

Alternatively, construct the compiler directly:

```python
from TEXAS.stan.compiler import StanCompiler
compiler = StanCompiler(model_dir=ARCHIVE)
```

## Which notebooks are affected

No notebook breaks on its **default** settings — every one of them reads a
cached or downloaded posterior rather than recompiling. The archived models are
only reached on a cold cache or an explicit re-run:

- `SI_code02a_model_param_sensitivity_test.ipynb` calls
  `get_posterior(..., stan_file="gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv")`
  inside a `try: load_posterior(...) / except: refit` block. It compiles only
  when the posterior is missing or `FORCE_RERUN = True`.
- `SI_code02_t0shift_TEXAS_analysis.ipynb` names the same model as `EIV_STEM`,
  a posterior-name stem used for loading.
- `SI_code03_paleo_showcases.ipynb` loads both variants from cache
  (`RUN_INVT = False` by default).

To refit the additive arm, point those calls at the absolute path above.

The additive posteriors themselves are also downloadable — see
`TEXAS.download_posteriors()` and the `_eiv` entries in
`src/TEXAS/utils/download.py` — which is the cheaper route if you need the
results rather than the fit.

## Earlier archives

`src/TEXAS/stan_models/archive/` (16 files) and
`src/TEXAS/stan_models/archive_pre_annotated/` (4 files) hold older material
from before the initial submission. Neither ships in the wheel either. They were
left in place in this pass; folding all three into one location is still open.
