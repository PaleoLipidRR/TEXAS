# Why the plug-in P50 ≠ the Bayesian P50

A common surprise when moving from a frequentist to a Bayesian TEXAS reconstruction:
inverting the calibration **at the posterior-median parameters** — the "plug-in"
estimate — does not reproduce the **P50 of the full Bayesian** inverse posterior
returned by [`predict_T_from_proxyObs`](api.md#predict-t-from-proxy-observations).

This is expected, not a bug. Three distinct effects separate the two, and which one
dominates depends on where the sample sits on the S-curve:

1. **Asymptote breakdown** (dominant at the extremes) — the generalized-logistic
   inverse explodes as the proxy approaches the lower asymptote `b` or the upper
   asymptote `1`. For a proxy below the median `b`, the plug-in is *literally
   undefined*, while the marginalized posterior stays finite because most ensemble
   draws have a lower `b`.
2. **Mixture / nonlinearity** (dominant on the steep flanks) — TEXAS marginalizes the
   likelihood over the forward ensemble. Because the inverse is steeply nonlinear,
   `median_m[inv(y; θ_m)] ≠ inv(y; θ̂)`. This shifts the **median**, not just the mean.
3. **Temperature prior** (the systematic mid-curve offset) — the truncated-Normal prior
   on `T` shrinks the posterior toward its mean. The plug-in uses none of it.

The interactive explainer below lets you vary the proxy value, the prior mean and σ,
and the calibration spread, and watch the gap decompose in real time. It grid-integrates
the *same* marginalized likelihood × truncated-Normal prior that
`invT_gen_logi_fixed_univ_marginal_truncated_prior.stan` samples, using an embedded
ensemble drawn from the real forward posterior
`tx.GHPU.sst.sri03.p0`.

```{note}
The sandbox is for building intuition. Production numbers should still come from
[`predict_T_from_proxyObs`](api.md#predict-t-from-proxy-observations), which runs the
Stan model rather than a grid approximation.
```

```{raw} html
<p style="margin:1rem 0 0;">
  <a href="_static/why-plugin-p50-differs.html" target="_blank" rel="noopener"><strong>Open the explainer full-page →</strong></a>
</p>
<iframe src="_static/why-plugin-p50-differs.html"
        title="Why plug-in P50 differs from Bayesian P50 — interactive explainer"
        loading="lazy"
        style="width:100%; height:85vh; min-height:640px; border:1px solid rgba(128,128,128,0.35); border-radius:10px; margin:1rem 0;">
</iframe>
```

## Takeaway

The mismatch you see down-core is **worst at the temperature extremes, for two
compounding reasons at once**: the S-curve flattens, so the inverse becomes
ill-conditioned, *and* the prior pulls hardest exactly where the data are least
informative. Near the middle of the calibration range the two estimates agree to
within a couple of degrees.

## See also

- [Why marginalization improves inverse TEXAS sampling](marginalization_explainer.md) —
  the mechanics of the ensemble marginalization that drives effect (2).
- [Prior choice: Normal vs Cauchy](Prior_Choice_Normal_vs_Cauchy.md) — how the
  temperature prior in effect (3) is specified.
- [Stan models explained](stan_models_explanation_v2.md) — where the inverse models fit
  in the wider model family.
