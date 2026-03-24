# Archived Stan Models

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

All 22 active models are reachable by Python code or executed in SI notebooks.
See `src/TEXAS/stan/invT.py::_select_invT_stan_file()` for selection logic.

| Group | Count |
|---|---|
| Forward (`gen_logi_fixed_*`) | 9 |
| Inverse (`invT_gen_logi_fixed_*`) | 12 |
| Linear | 1 |
