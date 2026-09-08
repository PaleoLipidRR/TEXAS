# Stan models shipped with TEXAS

`src/TEXAS/stan_models/` holds **seven** `.stan` files: the three forward
calibrations the revised manuscript fits, the three inverse (proxy → temperature)
models it runs, and one straight-line reference model used in the SI figures.
Everything else ever written for this project lives in
`archive/submission-2026-04/stan_models/`, whose README names each retired file,
says why it was retired, and shows how to run one by absolute path.

`pyproject.toml` declares package data as `stan_models/*.stan` — a non-recursive
glob — so only these seven reach the wheel.

## Naming convention

```
{transform}_{curve}_{params}_{datasources}_{variant}.stan
```

| position | values used in the shipped set |
|---|---|
| transform | *(none)* = forward calibration; `invT_` = inverse |
| curve | `gen_logi` = generalized logistic (Richards); `linear` |
| params | `fixed` = upper asymptote pinned at 1 |
| data sources | `culmeso` = culture + mesocosm; `hier_crtp` = hierarchical coretop |
| variant | `univ` / `multiv` = without / with non-thermal predictors; `priorApprox` = stage-2 fit using stage-1 hyperpriors; `eiv` = errors-in-variables; `t0shift` = predictors shift T₀; `marginal` = ensemble marginalized analytically; `unconstrained` = no bound on T |

## Forward calibration

| file | role |
|---|---|
| `gen_logi_fixed_culmeso.stan` | **Stage 1.** One generalized logistic fitted jointly to the culture and mesocosm data — the controlled experiments, which constrain the *shape* of the response. Its posterior mean and SD for `{t0, k, b, v}` are the hyperpriors every `priorApprox` model consumes, so this fit runs first. |
| `gen_logi_fixed_hier_crtp_univ_priorApprox.stan` | **Stage 2, thermal only.** Coretop fit of the Scaled Ring Index against temperature with no non-thermal predictors. It is also the source of `R2_thermal`, which the EIV model requires **as data**. |
| `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift.stan` | **The production calibration** (compset `GHEB`). Coretop fit with the G₂/₃ ratio and NO₃ entering as a shift of the curve's location parameter — the manuscript's **T₀-shift parameterization** — plus Bayesian errors-in-variables on those predictors and on the RI. Both bundled posteriors were fitted with it. |

All three share the curve

```
RI = b + (1 - b) / (1 + exp(-k * (T - T0)))^(1/v)
```

with the upper asymptote fixed at 1 and Q fixed at 1. **T₀ is the curve's
location parameter, not its inflection point.** The steepest response sits at
`T0 - ln(v)/k`, several °C below T₀ for the fitted ν, and the slope varies
severalfold across the sampled range — so there is no single thermal sensitivity
to quote for this curve.

In the T₀-shift model the predictors move T₀ rather than the mean:

```
T0_eff[i] = T0 + gamma_G23 * g23_true[i] + gamma_NO3 * log10(no3_true[i])
mu[i]     = b + (1 - b) / (1 + exp(-k * (T[i] - T0_eff[i])))^(1/v)
```

Because they act *inside* the logistic, `mu` stays within `(b, 1)` for any finite
predictor value and any finite coefficient. That bounded-by-construction property
is why the parameterization was adopted.

## Inverse reconstruction

| file | role |
|---|---|
| `invT_gen_logi_fixed_univ_marginal_unconstrained.stan` | Univariate inverse — proxy only, no predictors. Used by the quickstart and by `SI_code03`. |
| `invT_gen_logi_fixed_multiv_marginal_unconstrained.stan` | Multivariate inverse for the additive (β-on-μ) forward arm, which the revision reports as the comparison arm. |
| `invT_gen_logi_fixed_multiv_marginal_unconstrained_t0shift.stan` | Multivariate inverse for the T₀-shift forward arm. **The production inverse.** |

`predict_T_from_proxyObs()` selects among these for you: the univariate file when
no predictor arrays are supplied, a multivariate file when they are, and the
`t0shift` file when the forward posterior being marginalized over was fitted with
the T₀-shift parameterization.

## Reference model

`linear_model.stan` fits `proxy = slope · T + intercept` with both coefficients
constrained non-negative. It is the straight-line form the sigmoid calibrations
are compared against in the SI figures, and is used by the preprocessing and
analysis notebooks. It is deliberately *not* a general-purpose linear regression.

## How the marginal likelihood works

The inverse question is: given an observed proxy value, what temperature produced
it — allowing for the fact that the calibration curve is itself uncertain? TEXAS
answers it by drawing `M` parameter sets from the forward posterior and
integrating over them.

The direct way would be to sample an `N × M` matrix of temperatures, one per
observation per forward draw. The shipped models instead sample `N` temperatures
and do that integral analytically inside the log-density:

```stan
for (n in 1:N) {
  vector[M] llk;
  for (m in 1:M)
    llk[m] = normal_lpdf(proxyObs[n] | fwd(t_est[n], params[m]), sigma[m]);
  lp += log_sum_exp(llk) - log(M);   // log[(1/M) * sum_m exp(llk_m)]
}
```

`log_sum_exp(llk) - log(M)` **is** the marginalization — the log of the mean
likelihood across the ensemble. It targets the same posterior as the matrix
formulation from a parameter space two orders of magnitude smaller, with far
better sampling geometry. Why the geometry matters, and what it does to the
effective sample size, is worked through in
[Why marginalization improves inverse TEXAS sampling](marginalization_explainer.md).

## How threading works

All three inverse models wrap that observation loop in Stan's `reduce_sum`, which
splits the `N` observations into chunks evaluated on separate CPU threads. The
chunk size is the `grainsize` data variable:

- `grainsize = 1` → maximum parallelism (best on many cores)
- `grainsize = N` → no parallelism, bit-for-bit the same result

Threading is active only when the model is compiled with `STAN_THREADS=True` and
run with `threads_per_chain > 1`; otherwise `reduce_sum` evaluates the same code
sequentially. It pays off when `N` is large — hundreds of observations — and the
`M` loop is expensive; below roughly `N = 20` the overhead can outweigh the gain.
[Understanding `reduce_sum` and `ll_chunk`](reduce_sum_for_geologists.md) explains
the mechanism without assuming any Stan.

The forward calibrations are **not** threaded. Their cost is in the hierarchical
structure and the latent EIV variables, not in one long independent loop, so
there is nothing for `reduce_sum` to split.

## See also

- [Why marginalization improves inverse TEXAS sampling](marginalization_explainer.md)
- [Understanding `reduce_sum` and `ll_chunk`](reduce_sum_for_geologists.md)
- [Sampler budget](sampler_budget.md) — measured runtimes for these models
- [Archive — the preprint's additive (β) formulation](preprint_additive_archive.md)
- `archive/submission-2026-04/stan_models/README.md` — the retired models and how to run one
