# Archived Stan models

> **Superseded, 2026-09.** The counts and the "Active models" table below describe
> the package as of 2026-04-16 and are no longer accurate: the `_werr`/`_odr`
> variants named here were consolidated into a single `_eiv` model in v0.1.5, and
> the package now ships 9 Stan models, not 23. The current split is documented in
> [`archive/submission-2026-04/stan_models/README.md`](../../../../archive/submission-2026-04/stan_models/README.md),
> which is also where the models archived in 2026-09 went. This directory holds
> older, pre-submission material and is kept for history. Neither directory ships
> in the wheel (`pyproject.toml` globs `stan_models/*.stan`, non-recursively).


These models are archived because they are not used in the current TEXAS workflow
and are not referenced by any Python code or SI notebooks.

## Why archived

| Group | Models | Reason |
|---|---|---|
| Legacy naming | `hier_crtp_*.stan` (4) | Pre-`gen_logi_fixed` naming convention; superseded by `gen_logi_fixed_hier_crtp_*` equivalents |
| Free upper asymptote | `gen_logi_free_*.stan` (3) | Free upper asymptote variant; not integrated into any current API workflow |
| Joint models | `jnt_cul_meso*.stan` (2) | Experimental joint culture+mesocosm models; not connected to Python API |
| invT without constraint suffix | `invT_gen_logi_fixed_univ.stan`, `invT_gen_logi_fixed_multiv.stan`, `invT_logistic_fixed_univ.stan`, `invT_logistic_fixed_multiv.stan` (4) | `_select_invT_stan_file()` always appends `_unconstrained` or `_hard_constraint`; bare versions are never selected |
| Explicitly legacy invT | `invT_gen_logi_fixed_univ_rev01.stan`, `invT_gen_logi_fixed_univ_reduce_sum.stan` (2) | Ensemble approach (estimates N×M parameters); much slower than the marginal variants now in use |

## Deleted models (not archived)

| Group | Files | Reason |
|---|---|---|
| `invT_logistic_fixed_*` (8) | `*_univ_marginal_unconstrained`, `*_univ_marginal_hard_constraint`, `*_univ_marginal_truncated_prior`, `*_univ_unconstrained`, and multiv equivalents | Only reachable if forward posterior has no `v` or `Q` parameter — impossible with all current `gen_logi_fixed` posteriors. Dead code removed 2026-03-24. |

## Active models (in `../`)

23 active models as of 2026-04-16. See `src/TEXAS/stan/invT.py::_select_invT_stan_file()` for invT selection logic.

| Group | Count | Notes |
|---|---|---|
| Forward (`gen_logi_fixed_*`) | 10 | +1 `_werr_ver2` added 2026-04-16 |
| Inverse (`invT_gen_logi_fixed_*`) | 12 | |
| Linear | 1 | |

### EIV / ODR forward models (experimental, under comparison)

Three models implement Bayesian error-in-variables for secondary predictors (G₂/₃, NO₃). The `_odr` and `_werr` variants use the delta method (heteroscedastic likelihood, no latent vars). `_werr_ver2` uses a latent-variable formulation that also separates RI analytical measurement error (Rs ≈ 0.03) from structural process noise. `_werr.stan` and `_odr.stan` may be archived once `_werr_ver2` comparison is complete.
