# gridT for the GRC poster — text, captions, and Q&A

Companion to the three figures:
`notes/assets/gridT_stepbystep.png`, `gridT_schematic.png`, `gridT_vs_plugin.png`.

---

## 1 · The method in plain words (for the intro/methods column)

We don't invert a single calibration curve. The forward calibration gives an
**ensemble of ~100 Ring Index–temperature curves** that captures how uncertain
the calibration itself is. For each candidate temperature on a grid we ask *how
well every curve in the ensemble reproduces the observed Ring Index*, average
that across the ensemble (this propagates calibration uncertainty), and multiply
by an independent SST prior. The result is a **full probability distribution of
temperature** for every sample; we report its median and credible interval. The
grid version reproduces the full Bayesian MCMC inversion to within 0.01 °C but
runs in milliseconds, so we can score thousands of samples live.

---

## 2 · The equation (poster box)

$$
p(T \mid \mathrm{RI}) \;\propto\; \underbrace{p(T)}_{\text{SST prior}}\times
\underbrace{\frac{1}{M}\sum_{m=1}^{M}\mathcal{N}\!\big(\mathrm{RI}\mid \mu_m(T),\sigma_m\big)}_{\text{average over } M \text{ calibration draws}}
,\qquad
\mu_m(T)=b_m+\frac{1-b_m}{\big(1+e^{-k_m(T-T_{0,m})}\big)^{1/v_m}}
$$

- **Estimate** \(\hat T = \text{median}\) of \(p(T\mid\mathrm{RI})\).
- **Uncertainty** = its quantiles: 68 % CI = [p16, p84], 90 % CI = [p5, p95].
- The average **before** normalizing is the whole idea — it folds the
  calibration's own uncertainty into the reconstruction.

---

## 3 · Figure captions (drop-in)

**Fig — How gridT computes T (`gridT_stepbystep.png`).**
The marginalization loop, unrolled for one sample (RI = 0.72). ① The inputs: one
Ring Index and the full calibration ensemble. ② At a candidate temperature every
curve predicts an RI; a good temperature is one whose predicted-RI cloud brackets
the observation. ③ The Gaussian likelihood of the observed RI is averaged over all
ensemble members, giving one score per temperature. ④ Sweeping temperature traces
the marginalized likelihood L(T). ⑤ Multiplying by the SST prior gives the
posterior. ⑥ Its median is the estimate (26.6 °C), its quantiles the uncertainty
(68 % CI [23.1, 29.8]).

**Fig — gridT reconstruction (`gridT_schematic.png`).**
Left: the forward calibration is a ~100-curve posterior ensemble, not a single
line; an observed RI reads across all of them. Right: marginalizing the ensemble
and applying the SST prior yields a full temperature posterior — median 26.6 °C,
68 % CI [23.1, 29.8], 90 % CI [20.4, 31.8].

**Fig — Why marginalize (`gridT_vs_plugin.png`).**
gridT (blue) vs the naive plug-in that inverts only the median curve (orange).
Left: across the RI range the plug-in diverges at both S-curve ends — undefined
below the median lower asymptote and exploding toward saturation — while gridT
stays finite and carries a credible interval. Right: for a warm, near-saturated
sample the plug-in is biased warm and gives no uncertainty; the gridT posterior
is well-behaved and quantifies the widening tail.

---

## 4 · The 30-second script (say this standing at the poster)

1. "We measure Ring Index from the GDGTs."
2. "Our calibration isn't one curve — it's an ensemble, so we carry its uncertainty."
3. "For every temperature on a grid we score how well *all* the curves reproduce
   the observed RI, and average — that's the marginalization."
4. "Times an independent SST prior gives a full temperature posterior. Median is
   the estimate, the spread is honest uncertainty."
5. "It matches the full MCMC inversion to a hundredth of a degree, but fast."

---

## 5 · Q&A cheat-sheet (hold behind the poster)

**Q. Isn't a grid just an approximation of the real Bayesian model?**
It's numerical integration of the *exact same* posterior the MCMC samples — same
likelihood, same prior. Validated against a fine-grid reference to max |Δ| ≈
0.01 °C, RMS 0.006 °C for RI ≲ 0.80. No estimator difference, no MC noise.

**Q. Where does the temperature prior come from — doesn't it drive the answer?**
Where RI is informative (the steep middle of the S-curve) the data dominate and
the prior barely moves the median. The prior only matters at the saturated ends
where the proxy carries little temperature information — which is exactly where
you *want* an honest prior doing the work. We use a diffuse σ = 10 °C.

**Q. What happens for warm, saturated samples?**
The proxy saturates near the top of the S-curve, so the posterior grows a long
warm tail and the estimate becomes prior-dependent. We keep the grid wide enough
that the upper tail closes (a too-short grid truncates p95 by up to ~3 °C at
RI ≈ 0.97). We flag any sample with non-negligible mass at the grid edge.

**Q. Why not just report the plug-in point estimate (invert the median curve)?**
It ignores calibration uncertainty *and* the prior, has no credible interval, and
is undefined or explosive at the S-curve asymptotes (see the contrast figure).

**Q. How is the uncertainty defined — is it just calibration scatter?**
It's the full posterior width: calibration-curve uncertainty (ensemble spread) +
residual proxy scatter σ_m + prior, all propagated together. 68 % and 90 %
credible intervals from the posterior CDF.

**Q. Does it use the GDGT-2/3 and NO₃ corrections?**
The thermal (univariate) version shown here uses RI only. The multivariate model
adds βG23·(GDGT-2/3) and βNO₃·log(NO₃) (below a cutoff) to the curve's lower
term; same marginalization, just a richer mean function.

**Q. How many calibration draws M, and does it matter?**
~100 draws; the average is a Monte-Carlo estimate of the marginal likelihood, and
100 is enough for the posterior median/CI to stabilize at our reporting precision.

**Q. Could two different temperatures give the same RI (non-identifiability)?**
The curve is monotonic in T, so no — but sensitivity collapses at the flat ends,
which is why those samples get wide intervals rather than a false-precise point.
