---
name: stan-check
description: Audit a TEXAS Stan model file for common issues — bound mismatches, prior scale problems, parameter naming, missing blocks. Use when writing or reviewing a .stan file.
allowed-tools: Read Glob Grep
argument-hint: [path/to/model.stan]
---

Read the Stan model at $ARGUMENTS (or ask the user which file if no argument given).
If no path is given, list all `.stan` files in `src/TEXAS/stan_models/` and ask which one to check.

Audit the file against every rule below. Report each issue as FAIL or PASS. Group by category.

---

## 1. Parameter bounds

- `k_crtp`: must have `lower=0.01` and NO upper bound. FAIL if `upper=0.5` or any upper cap is present (culmeso posterior mean ≈ 0.57).
- `b_crtp`: must have `upper=1.0`. FAIL if `upper=0.6` or lower.
- `v_crtp` / `v_culmeso`: must have `lower=0.1`. FAIL if `lower=0`.
- Any `lower=0` scalar that appears in a half-normal prior context — confirm the prior is `normal(0, ...)`, not `normal(positive_value, ...)`.
- For latent-variable NO3 (`true_no3_crtp`): must have `upper=no3_cutoff` to prevent HMC leapfrog overflow. FAIL if only `lower=0` with no upper bound.

## 2. Prior specifications

- `sigma_proxyObs_*` priors must be `normal(0, ...)`, never `normal(0.01, ...)` or any positive mean. FAIL if mean ≠ 0.
- `v` prior truncation: if the prior is written as `normal(...) T[lower, ]`, the lower truncation bound must match the parameter declaration's `lower=` value. FAIL on mismatch.
- `beta_G23_crtp` / `beta_NO3_crtp`: check that priors exist and are reasonable (e.g. `normal(0, 0.05)` for G23; informative around `-0.064` for NO3). Warn if zero-centered for NO3 (zero-centered + latent vars causes attenuation).

## 3. Parameter naming

- Non-thermal coefficient parameters must be named `beta_G23_*` and `beta_NO3_*`. FAIL if old names `beta0_gdgt23ratio_*` or `beta0_no3_*` are present.
- Q parameter (`Q_crtp`, `Q_culmeso`) must NOT exist in any block. FAIL if found — Q was dropped in all models (2026-03-24); fixed to 1.
- The generalized logistic curve must use Q=1 implicitly: `(1 + exp(-k*(T-t0)))^(1/v)`, not `(1 + Q*exp(...))^(1/v)`.

## 4. Curve formula

Check the generalized logistic formula in both `model` and `generated quantities` blocks:
```stan
b + (1.0 - b) ./ pow(1.0 + exp(-k * (t - t0)), 1.0 / v)
```
FAIL if: asymptote is not `1.0`; Q appears; upper asymptote parameter is free when model name says `fixed`.

## 5. Generated quantities block

- All forward coretop models should have a `generated quantities` block computing at minimum `R2_full`, `RMSE_full`, and `bayesR2_full`.
- FAIL if the block is entirely absent in a `_crtp` or `_priorApprox` model.
- `bayesR2_full` denominator: for ODR/werr models (delta-method), should use `mean(sigma_eff_sq)`; for standard models, `square(sigma_proxyObs_crtp)`.

## 6. EIV / ODR specific (if applicable)

If the model name contains `_werr` or `_odr` (delta-method EIV):
- G23 variance contribution: `square(beta_G23_crtp) * square(sd_gdgt23ratio_crtp[i])`
- NO3 variance contribution (delta method): `square(beta_NO3_crtp) * square(sd_no3_crtp[i] / (no3_crtp[i] * log(10)))`, applied only where `0 < no3_crtp[i] < no3_cutoff`
- CV-gating index arrays (`N_g23`, `N_no3_valid`, `no3_valid_idx`, `N_no3_exact`, `no3_exact_idx`) should be present in the data block.

If the model name contains `_werr_ver2` (latent-variable EIV):
- `sd_proxyObs` must be in data block (per-site RI analytical SE).
- `R2_thermal` must be in data block.
- `true_no3_crtp` must have `<lower=0, upper=no3_cutoff>`.
- Likelihood must combine `sd_proxyObs` and `sigma_proxyObs_crtp` in quadrature: `sqrt(square(sd_proxyObs) + square(sigma_proxyObs_crtp))`.
- NO3 measurement loop must guard `sd_no3_crtp[i] > 0` (sites with unknown SE skip the measurement model).

## 7. Data block completeness (priorApprox models)

If model name contains `_priorApprox`:
- Must have `prior_mean_t0`, `prior_sd_t0`, `prior_mean_k`, `prior_sd_k`, `prior_mean_b`, `prior_sd_b`, `prior_mean_v`, `prior_sd_v`.
- No `prior_mean_Q` / `prior_sd_Q` (Q was dropped).

## 8. Naming convention

Confirm file name matches: `{transform}_{curve}_{params}_{datasources}_{variant}.stan`
- transform: `invT_` or empty
- curve: `gen_logi` / `logistic` / `linear`
- params: `fixed` / `free`
- datasources: `culmeso` / `culmesocore` / `crtp`
- variant: `hier_crtp`, `multiv`, `priorApprox`, `werr`, `werr_ver2`, `odr`, etc.

---

After the audit, provide a concise summary table (PASS/FAIL/WARN per category) and list any required fixes with the exact line change needed.
