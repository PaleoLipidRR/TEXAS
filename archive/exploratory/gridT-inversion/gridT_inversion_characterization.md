# The "gridT" temperature-inversion method — characterization

**Question:** what *is* the fast/cheap grid inversion we use instead of a full
Stan inverse run, and is it a safe substitute for `predict_T_from_proxyObs`?

**Answer up front:** it is **(A) Bayesian quadrature** — it targets the *same*
posterior as the Stan marginal inverse model. It is not (B) a
mixture-of-normalized-posteriors and not (C) a frequentist ensemble root-solve.
No math change is needed to make it correct. The only defect is an **incidental
upper grid bound (45 °C) that truncates the warm/saturated tail**; everything
else agrees with Stan to < 0.01 °C.

---

## Where it lives (there is no `gridT` function)

Searching `src/` and `notebooks/` turns up **no** function literally named
`gridT`, and **no** grid inversion in the installed package
(`grep cumsum/trapz/logsumexp src/**/*.py` → nothing). `src/TEXAS/predict.py::predict_T_from_proxyObs`
is the *Stan* path; `models/logistics.py::inverse_generalized_logistic_fixed_upper`
is the *plug-in* (invert one median curve) — neither is "gridT".

The grid method exists as the **reference implementation embedded in the docs
teaching page** `docs/_static/why-plugin-p50-differs.html`:

- the copy-pasteable **Python** version, `docs/_static/why-plugin-p50-differs.html:217-222`
- the live **JS** version driving the sandbox, `posterior()` + `quantile()` at
  `docs/_static/why-plugin-p50-differs.html:268-280`

Both are the same algorithm. Signature of the Python reference:

```python
def fwd(T, t0, k, b, v):           # generalized logistic, Q=1, upper=1
    return b + (1-b)/np.power(1+np.exp(-k*(T-t0)), 1/v)

T    = np.linspace(-1.8, 45, 4000)
like = np.mean([np.exp(-0.5*((ri-fwd(T,*p[:4]))/p[4])**2)/p[4] for p in draws], axis=0)
post = like * np.exp(-0.5*((T-15)/10)**2)          # × T prior
cdf  = np.cumsum(post); t_p50 = np.interp(0.5*cdf[-1], cdf, T)
```

---

## The central question: A, B, or C — it is **A**

Trace where the m-loop (over ensemble draws) sits relative to normalization, and
whether `sigma` enters.

**Python reference — `why-plugin-p50-differs.html:220-222`:**

```python
like = np.mean([ np.exp(-0.5*((ri - fwd(T,*p[:4]))/p[4])**2) / p[4]  for p in draws], axis=0)
#      └── average over draws m  ────────────────────────────┘ (÷ p[4] = ÷ sigma_m)   ← BEFORE any normalize
post = like * np.exp(-0.5*((T-15)/10)**2)     # multiply the *already-averaged* likelihood by the prior
cdf  = np.cumsum(post)                         # normalize ONCE, at the very end
```

**JS reference — `why-plugin-p50-differs.html:271-274`:**

```js
let like=0; for(const q of ens){ const mu=fwd(t,q.t0,q.k,q.b,q.v);
              like += Math.exp(-0.5*((p.proxy-mu)/q.sig)**2)/q.sig; }   // Σ over m, sigma in exponent AND prefactor
like/=ens.length;                                                       // (1/M) average  ← before normalize
let pr=1; if(usePrior){ pr=Math.exp(-0.5*((t-p.pmean)/p.psd)**2); }
post[i]=like*pr;                                                        // prior applied per grid node
```

The m-loop is **inside** the per-grid-T evaluation and is **averaged before the
single global normalization** (`cumsum`). `sigma_m` enters both in the Gaussian
exponent and as the `1/sigma_m` prefactor. The prior multiplies the averaged
likelihood. That is exactly

> log p(T|y) ∝ log prior(T) + logsumexp_m[ N(y | μ_m(T), σ_m) ] − log M

i.e. **definition (A), Bayesian quadrature.**

This is line-for-line the Stan marginal model. Compare
`src/TEXAS/stan_models/invT_gen_logi_fixed_univ_marginal_truncated_prior.stan:130-141`:

```stan
for (m in 1:M) {
    real mu = b[m] + (1 - b[m]) / pow(1 + exp(-k[m]*(t_est[n]-t0[m])), 1.0/v[m]);
    lp[m]  = normal_lpdf(proxy_param[n] | mu, sigma_proxy_param[m]);
}
target += log_sum_exp(lp) - log_M;      // ← average likelihood over draws, sigma_m inside
```

with the prior `T ~ TruncNormal(prior_mu_t, prior_sigma_t, lower=min_temp)`
induced by the inverse-CDF `q → t_est` map (lines 113-121). Same integrand, same
prior; Stan draws HMC samples from the density that gridT integrates on a grid.

**Empirical confirmation** (real embedded posterior, 80 draws, prior N(15,10)):

| RI   | **A = gridT** | B = normalized-mixture | C = root-pool (median) |
|------|--------------:|-----------------------:|-----------------------:|
| 0.55 |    **14.69**  |   14.69                |   16.38                |
| 0.75 |    **28.28**  |   28.28                |   29.80                |
| 0.90 |    **36.09**  |   36.12                |   38.74                |
| 0.97 |    **39.20**  |   39.28                |   46.88                |
| 0.45 |    **8.03**   |    8.03                |   −1.99 (drops no-root draws) |

gridT's output *is* column A. C is off by +1.5 … +7.7 °C and undefined for
draws whose asymptote sits above `y`. B happens to be close for this posterior
(the draws have similar marginal-likelihood integrals, so equal-weight ≈
integral-weight) but drifts at the tails — it is a genuinely different estimator,
just not the one implemented.

---

## Also-checked items

**1 · SST prior.** Applied. `post = like * exp(-0.5*((T-pmu)/psd)²)`
(`:221`; JS `:273`, toggle `usePrior`). Matches the Stan `Normal`/`TruncNormal`
prior. The grid's **lower** bound −1.8 °C coincides with the Stan `min_temp`
(seawater freezing) — a *deliberate* physical floor, not an accidental one, so
cold-site mass legitimately piles against it (the Stan `truncated_prior` model
does the same). If the prior toggle is off, the grid bounds `[-1.8, 45]` act as
an implicit **uniform** prior on that interval.

**2 · Grid resolution & range, truncation.**
Python `linspace(-1.8, 45, 4000)` → dt ≈ 0.0117 °C; JS `GRID=520` over
`[minT, 42]` → dt ≈ 0.08 °C. Resolution is a non-issue. **Range is not.** Mass at
the *upper* node under the true posterior:

| RI (obs)        | 0.75  | 0.80  | 0.85  | 0.90  | 0.94  | 0.97  |
|-----------------|------:|------:|------:|------:|------:|------:|
| P(T > 45 °C)    | 1e-5  | 3e-4  | 0.3 % | 2.2 % | 6.5 % | **12 %** |

Any observation with implied T ≳ 35 °C (RI ≳ 0.85) leaves non-negligible density
at the last node → the warm tail is **truncated**. The lower node never truncates
in the error sense (−1.8 is the intended `min_temp`; the reference and Stan floor
there identically).

**3 · Secondary linear terms (GDGT-2/3, NO₃).** **Not handled.** The reference
`fwd(T,t0,k,b,v)` is the *univariate* mean function only; it corresponds to the
`invT_..._univ_...` Stan model. The multivariate Stan mean
(`invT_gen_logi_fixed_multiv_marginal_truncated_prior.stan:44-58`) is

```stan
real lin = b[m];
if (use_gd  == 1) lin += beta_gd[m] * gd_seg[i];
if (use_no3 == 1) { real logno3 = (n3>0 && n3<no3_cutoff) ? log10(n3+1e-9) : 0.0;
                    lin += beta_no3[m] * logno3; }
real mu  = lin + (1 - b[m]) / pow(1+exp(-k[m]*(T-t0[m])), 1.0/v[m]);
```

So to match a *multiv* posterior the grid `fwd` would need
`mu = b + beta_gd·gd + beta_no3·logno3_gated + (1−b)/pow(...)`, with the NO₃
cutoff gate and — importantly — the numerator kept as `(1−b_m)`, **not**
`(1−lin)`. As written, gridT silently reconstructs only the thermal term; using
it against a multivariate posterior drops the corrections.

**4 · Quantiles.** From the **CDF of the grid density**: `cumsum` → `interp` at
`0.5·cdf[-1]` (`:222`); JS `quantile()` linearly interpolates within the target
bin (`:278-280`). `cumsum` is a left-Riemann CDF, giving a constant ≈ −dt/2 ≈
−0.006 °C half-bin bias vs a trapezoid CDF — negligible, and the dominant piece
of the sub-0.01 °C agreement below. (Replacing `cumsum` with
`scipy.integrate.cumulative_trapezoid` removes even that.)

---

## Numerical validation

CmdStan / cmdstanpy are not installed here and both posterior caches are empty,
so a live `predict_T_from_proxyObs` run was not possible. Instead I validate
against the **exact density the Stan model samples** — the identical
`prior × (1/M)Σ_m N(y|μ_m(T),σ_m)` integrated on a 40 000-pt grid over a wide
support (a fine-quadrature reference has *no* MC noise, so it is a stricter test
than one Stan chain). Inputs: the real 80-draw posterior
`gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3` embedded in the
docs page; prior N(15, 10); a sweep of RI observations spanning the calibrated
range.

**Discretization only** (gridT `[-1.8,45]` vs fine reference on the *same*
support — isolates the grid method itself):

```
MAX |Δ| = 0.010 °C     RMS = 0.006 °C     (across p5/p16/p50/p84/p95)
```

**Including the 45 °C cap** (gridT `[-1.8,45]` vs true posterior on `[-1.8,80]`):

| quantile | max \|Δ\| °C | RMS °C |
|----------|-----------:|-------:|
| p5       | 0.19       | 0.06   |
| p16      | 0.27       | 0.09   |
| p50      | 0.58       | 0.18   |
| p84      | 1.67       | 0.54   |
| p95      | **3.55**   | 1.19   |

The entire error budget is upper-tail truncation, concentrated at RI ≥ 0.85
(implied T ≳ 35 °C). For RI ≤ 0.80 the deviation is ≤ 0.015 °C at every
quantile. See `notes/assets/gridT_validation.png`: the three warm-saturated
panels (RI 0.90/0.94/0.97) show gridT (orange) tracking the true posterior
(blue) until the 45 °C cap, then renormalizing upward and pulling p95 low; the
three cold-tail panels (RI 0.45/0.47/0.50) are pixel-identical (Δ = 0.0 °C).

**Safe-substitute tolerance.** With the grid as written (`[-1.8, 45]`):

- **Median (p50):** safe to **≈ 0.2 °C** everywhere; **≈ 0.01 °C** for RI ≤ 0.80.
- **Upper quantiles (p84/p95):** safe to **≈ 0.1 °C only for RI ≲ 0.80
  (implied T ≲ 32 °C)**. For RI ≥ 0.85 the p95 error grows to 3.5 °C — do **not**
  trust gridT's warm-tail credible interval on saturated observations.
- Rule of thumb: **trust gridT wherever P(T > T_max_grid) < ~1e-3**; flag the
  observation otherwise.

---

## If you want the warm tail correct (do not apply without sign-off)

gridT is **already method A** — no estimator change is required. The single
minimal fix is to stop the upper bound from truncating real mass; extend it, or
make it adaptive, e.g.

```python
# was: T = np.linspace(-1.8, 45, 4000)
T = np.linspace(-1.8, max(60.0, prior_mu_t + 5*prior_sigma_t), 6000)
# and (optional) drop the ~0.006 °C half-bin bias:
from scipy.integrate import cumulative_trapezoid
cdf = cumulative_trapezoid(post, T, initial=0)
t_p50 = np.interp(0.5*cdf[-1], cdf, T)
```

To reconstruct against a **multivariate** posterior, `fwd` must additionally
carry the `beta_gd·gd + beta_no3·logno3(gated by no3_cutoff)` terms exactly as in
`invT_gen_logi_fixed_multiv_marginal_truncated_prior.stan:44-58` (numerator stays
`1−b`, not `1−lin`).

These are bound/scope fixes, not a redefinition of the method.
