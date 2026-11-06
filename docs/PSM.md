# TEXAS Proxy System Model — Bayesian Inference Workflow

## 1. Overview

TEXAS-PSM, the proxy system model built around the TEXAS sensor model, is designed to link **environmental variables** (e.g., sea surface temperature, archaeal community composition, nutrient availability) to **proxy measurements** (e.g., GDGT-based Ring Index, TEX₈₆) using a **Bayesian framework**.

It has two complementary components:

1. **Forward Model** — Predicts proxy values from known environmental conditions.
2. **Inverse Model (Bayesian Inference)** — Infers environmental conditions from observed proxy values.

---

## 2. Why Bayesian?

Bayesian inference provides a natural way to:
- Combine **prior knowledge** (from culture experiments, core-top datasets, or theory) with **new data**.
- Quantify **uncertainty** in both model parameters and reconstructions.
- Explicitly propagate uncertainties from forward models into reconstructions.

The heart of Bayesian statistics is **Bayes' Theorem**:

$$
P(\theta \mid D) = \frac{P(D \mid \theta) \, P(\theta)}{P(D)}
$$

Where:
- \( \theta \) = parameters we want to estimate (e.g., S-curve shape parameters, nutrient effect coefficients).
- \( D \) = observed data (e.g., GDGT fractions, Ring Index values).
- \( P(\theta \mid D) \) = **posterior** — our updated beliefs about parameters given the data.
- \( P(D \mid \theta) \) = **likelihood** — how well a given set of parameters explains the data.
- \( P(\theta) \) = **prior** — what we believed about parameters before seeing the data.
- \( P(D) \) = **evidence** — a normalization constant ensuring probabilities sum to 1.

---

## 3. Forward Model (Environmental Variables → Proxy Values)

The forward model predicts **scaled Ring Index** (\( RI_{\text{scaled}} \)) from environmental predictors.

Example for a **generalized logistic forward model**:

$$
T_{0,\text{eff}} = T_{0} + \sum_{j} \gamma_j X_j,
\qquad
RI_{\text{scaled}}(T, X) = b + \frac{1 - b}{\left( 1 + e^{-k (T - T_{0,\text{eff}})} \right)^{1/v}}
$$

Where:
- \( T \) = temperature.
- \( X_j \) = additional predictors (e.g., GDGT-2/GDGT-3 ratio, nitrate concentration).
- \( b \) = lower asymptote; the upper asymptote is **fixed at 1**; \( T_0 \) = curve location (the steepest response is at \( T_0 - \ln v / k \), not at \( T_0 \)), \( k \) = steepness, \( v \) = shape (curve asymmetry).
- \( \gamma_j \) = coefficients for optional predictors, in °C per predictor unit. They shift the curve's location **inside** the logistic (the *T₀-shift parameterization*), so a sample with elevated predictors records the Scaled RI of apparently colder water, and the predicted \( RI_{\text{scaled}} \) stays confined to \( (b, 1) \) by construction. (An earlier formulation added \( \beta_j X_j \) to the response instead; it is superseded because it can push predictions outside the index's physical bounds.)
- \( RI_{\text{scaled}} \) is normalized between 0 and 1 for comparability.

**Forward Model Role:**  
Given **true environmental conditions**, the model produces a distribution of possible GDGT-based proxy values, including natural variability and measurement noise.

---

## 4. Bayesian Inference (Proxy Values → Environmental Variables)

The inverse problem is: *Given an observed proxy value (e.g., RI), what is the most likely temperature?*

Using Bayes’ theorem:

$$
P(T \mid RI_{\text{obs}}) \propto P(RI_{\text{obs}} \mid T) \, P(T)
$$

- \( P(T) \) — **prior temperature distribution** (e.g., from regional climate models, modern analogs, or culture constraints).
- \( P(RI_{\text{obs}} \mid T) \) — **likelihood** from the forward model.
- The result \( P(T \mid RI_{\text{obs}}) \) is the **posterior** distribution of temperatures consistent with the observation.

---

### 4.1 Likelihood Function

The likelihood assumes a statistical error model:

$$
P(RI_{\text{obs}} \mid T, \theta) = \mathcal{N} \left( RI_{\text{obs}} \,\middle|\, RI_{\text{pred}}(T, X; \theta), \sigma_{RI} \right)
$$

- \( RI_{\text{pred}} \) — forward model prediction.
- \( \sigma_{RI} \) — residual standard deviation (accounts for unmodeled variability).

---

### 4.2 Priors

- **From cultures and mesocosms** — constrain the curve parameters (\( T_0, k, b, v \)); their posterior means and SDs become the hyperpriors for the core-top fit.
- **From core-tops** — refine those curve parameters hierarchically and estimate the environmental effects (\( \gamma_j \)), with the predictors treated as errors-in-variables.

Example prior for the temperature:

$$
T \sim \mathcal{N}(\mu_T, \sigma_T)
$$

Where \(\mu_T\) and \(\sigma_T\) come from prior knowledge (e.g., modern climatology).

---

## 5. Putting It Together

1. **Forward Step**  
   - Start with priors for all parameters.
   - Use the forward logistic model to simulate RI given environmental conditions.
   - Compare to observed RI values via the likelihood.

2. **Bayesian Updating**  
   - The posterior combines **likelihood** and **priors**.
   - We sample from the posterior (e.g., via MCMC in Stan/CmdStanPy).

3. **Inference Output**  
   - Posterior temperature distribution for each site/sample.
   - Full uncertainty range, not just a single “best estimate.”

---

## 6. Advantages for Paleoceanography

- **Mechanistic**: Based on GDGT biosynthesis behavior, not just empirical regression.
- **Flexible**: Can include ecological and nutrient effects.
- **Transparent Uncertainty**: Directly quantifies credible intervals on temperature estimates.
- **Culture Integration**: Uses lab data as informative priors, bridging modern process understanding with ancient climate reconstructions.

---

## 7. Key Equations Summary

1. **Bayes' Theorem**
$$
P(\theta \mid D) = \frac{P(D \mid \theta) \, P(\theta)}{P(D)}
$$

2. **Forward Logistic Model**
$$
T_{0,\text{eff}} = T_{0} + \sum_{j} \gamma_j X_j,
\qquad
RI_{\text{scaled}}(T, X) = b + \frac{1 - b}{\left( 1 + e^{-k (T - T_{0,\text{eff}})} \right)^{1/v}}
$$

3. **Likelihood**
$$
P(RI_{\text{obs}} \mid T, \theta) = \mathcal{N} \left( RI_{\text{obs}} \,\middle|\, RI_{\text{pred}}, \sigma_{RI} \right)
$$

---

*This workflow ensures that your TEXAS-PSM reconstructions combine the best available culture, modern, and paleo data in a statistically rigorous way, providing more reliable temperature estimates for past climates.*

## 8. Reconstructing temperature from proxy observations

`TEXAS.predict_T_from_proxyObs` is the inverse half of the API. Three things about how it is called are worth stating once here rather than in its docstring.

**The default calibration.** Omitting `fwd_posterior` selects the full multivariate T₀-shift calibration for the requested target — `tx.GHEB.sst.sri03.G23-N1p0` for SST, `tx.GHEB.thm.sri03.G23-N1p0` for thermoT — both of which ship inside the wheel, so a reconstruction needs no download. That is the default because the non-thermal effects are present in the core-top data whether or not a user models them: a temperature-only calibration does not remove them, it absorbs them into the thermal parameters.

**Which NO₃ value reaches Stan.** The resolution order is `site_lat`/`site_lon` lookup → an explicit `no3=` → `predictors["no3"]` → zeros. Passing `site_lat` and `site_lon` interpolates the `ocean_prop_ds` field (the CMEMS nitrate climatology on the WOA23 grid) at those coordinates (downloaded and cached from Zenodo on first use if `no3_dataset` is not supplied). A scalar `no3` broadcasts to every observation; a value above `no3_cutoff` — e.g. `no3=10.0` when the cutoff is 1.0 — puts every observation outside the correction window, which is how the correction is switched off.

Supplying *nothing* is not the same as switching it off. If the calibration you named declares a correction and you supply no values for it, `predict_T_from_proxyObs` raises a `ValueError` naming the ways out rather than passing zeros to Stan — for the GDGT-2/3 ratio and for NO₃ alike — because a zero would assert a ratio or concentration of zero and bias the reconstruction. The `predictor_missing` quality flag (below) marks the same condition on a reconstruction loaded back from disk. And if you name *no* calibration and supply *no* predictors, TEXAS selects the thermal-only calibration (`tx.GHPU.sst.sri03.p0`, or `tx.GHPU.thm.sri03.p0` for thermoT; both also ship in the wheel) and warns that it has done so. That fallback is a convenience, not an equivalence: as above, a thermal-only fit absorbs the non-thermal signal into its thermal parameters, so its reconstructions differ from the multivariate ones the manuscript reports.

**`temptype` is a label, not a modeling choice.** The reconstruction follows whatever calibration it was given: the target is read from the posterior's own attrs, and `temptype` only names the metadata and the output files. It matters in exactly one case — when `fwd_posterior` is omitted, it chooses which default calibration is used. A `temptype` that contradicts the calibration raises a warning and is otherwise ignored.

**Per-observation quality flags.** The screening above and several further checks run with every reconstruction and come back as `result["flags"]`, a DataFrame with one row per sample (manuscript Appendix C2.8). Each column is a check that is passed, failed, or — when it could not be evaluated — `pd.NA`, never a pass. Computing them costs no extra sampling.

| column | fires when |
|---|---|
| `outside_domain` | the sample lies outside the published 90 % χ² ellipse in TEX₈₆ × Scaled RI, with the same warm-end exception as the calibration screening (Section 5.1). Needs `tex86=`; `pd.NA` without it, or when the reconstruction's proxy is not `scaledRI_cren3`. |
| `proxy_below_floor`, `proxy_above_ceiling` | the Scaled RI is below the curve's lower asymptote *b* or above 1 in more than half of the calibration draws. The curve cannot produce the observation, so the converged, plausible-looking temperature is a readout of the prior, not a measurement (Section 8.4). The graded companions `frac_draws_below_floor` / `frac_draws_above_ceiling` give the fraction of draws that rule the value out. |
| `proxy_extrapolated` | the Scaled RI is outside the range of the calibration data. |
| `predictor_extrapolated` | GDGT-2/3 or NO₃ is outside the range of the calibration data. |
| `predictor_missing` | a predictor the calibration uses was not supplied. Reachable only when `compute_quality_flags` is called directly on a saved result: `predict_T_from_proxyObs` refuses that case before sampling (above). |
| `prior_dominated` | the posterior 68 % half-width, (p84 − p16)/2, is ≥ 85 % of `prior_sigma_t` (the threshold is the `prior_dominated_ratio` keyword). |
| `no3_correction_inactive` | advisory only: NO₃ is above the cutoff, so the nitrate term is off — usually deliberate (`no3=10`). Reported, but it does not count toward `any_flag`. |
| `any_flag` | any evaluated defect column is True. `pd.NA` entries contribute nothing. |

`posterior_prior_width_ratio` is the graded companion of `prior_dominated`: `1 − ratio²` is the per-sample share of the prior variance the proxy removed, the prior-referenced diagnostic the manuscript recommends (Appendix C2.8). The SI's prior-comparison table reports the record-level version of the same quantity, with the half-width averaged over the record first.

```python
result = predict_T_from_proxyObs(
    proxyObs=df["scaledRI_cren3"].values,
    prior_mu_t=20.0, prior_sigma_t=10.0,
    gdgt23ratio=df["gdgt23ratio"].values,
    no3=10.0,                        # correction off
    tex86=df["TEX86"].values,        # enables outside_domain
)
flags = result["flags"]
resolved = 1 - flags["posterior_prior_width_ratio"] ** 2

keep = ~flags["any_flag"].to_numpy(dtype=bool)   # NA never counts as a pass
sst = result["p50"][keep]
```

The quickstart notebook (`notebooks/quickstart_demo.ipynb`, Step 6b) runs this on a short record that includes one deliberately unreachable sample, so each flag can be seen firing before it is applied to real data.

## 9. Choosing the NO₃ cutoff

The NO₃ correction applies only below a cutoff concentration: above it, sites are nutrient-replete and the term is switched off. The manuscript (Section 6.2) finds the strongest negative Spearman correlation between the thermal residuals and log₁₀[NO₃⁻] at 1.8 µmol/L and adopts **1.0 µmol/L** as the practical cutoff, because the correction is log-linear and passes through zero at NO₃ = 1; that is the value recorded in the published posteriors. `find_optimal_no3_threshold` and `find_optimal_no3_threshold_nointercept` search that cutoff against the residuals of a temperature-only fit. They differ in the criterion, and the choice is a modeling decision, not a tuning detail.

**`find_optimal_no3_threshold`** takes the cutoff that maximises the *negative* correlation between log(NO₃) and the residuals.

- `score_method="spearmanr"` (default) uses the most negative Spearman ρ. It is rank-based, robust to outliers, and is what the prior publication used.
- `score_method="R_squared"` uses the highest no-intercept R² of `RI_res = β·log(NO₃)` with β < 0. It penalizes poor fit rather than rank order alone, and corresponds to a model whose correction is zero at NO₃ = 1.

**`find_optimal_no3_threshold_nointercept`** instead maximises the no-intercept R² of `RI_res = β·x`, for a correction that is exactly zero *at the threshold* (a formulation explored during development; the shipped Stan models use the `log10` form, zero at NO₃ = 1).

- `no3_mode="log10ratio"` (default) sets `x = log10(NO₃ / threshold)` — zero at the boundary.
- `no3_mode="log10"` sets `x = log10(NO₃)` — zero at NO₃ = 1 regardless of the threshold, which is the original Stan form. Use it to compare the no-intercept criterion against the Spearman one while holding the predictor fixed.

**Asymmetric weighting** (`weight_method`, R²-based criteria only; Spearman takes no sample weights) exists because the two corrections have opposite expected signs.

- `"uniform"` — ordinary least squares.
- `"positive_residuals"` — `wᵢ = max(resᵢ, ε)`. For the **NO₃** correction: nutrient-limited sites are expected to have positive RI residuals (observed RI above what temperature alone predicts).
- `"negative_residuals"` — `wᵢ = max(−resᵢ, ε)`. For the **G₂/₃** correction: deep-water, high-G₂/₃ sites are expected to have negative RI residuals.

In both weighted cases `ε = 0.001 · std(residuals)`, so off-direction points are suppressed but never fully excluded — which keeps the fit stable when nearly all residuals fall on one side.

`log_method` (`"log10"` or `"ln"`) sets the log base. `"log10"` matches the Stan models; `"ln"` is there to test sensitivity to that choice.
