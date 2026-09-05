# Model validation

How well does a TEXAS calibration actually fit, and how do we know the
generalized-logistic Bayesian model improves on existing TEX₈₆ calibrations?
This page summarises the validation strategy used in the manuscript; the full
analysis (with figures) lives in `notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb`.

Validation rests on three complementary checks:

1. **Forward calibration performance** — how accurately the curve reproduces the
   observed proxy (RMSE / R²), benchmarked against existing calibrations.
2. **Residual diagnostics** — whether any *structure* remains in the residuals
   (spatially, or against temperature) after fitting.
3. **Variance partitioning** — how much of the proxy variance is thermal vs
   non-thermal (ecology, nutrients) vs irreducible noise.

---

## 1. Forward calibration performance

The forward model is evaluated on the coretop training set (N ≈ 1513) by
predicting Scaled RI from in-situ SST and comparing to the observed proxy.
RMSE is reported in Scaled RI units (the proxy is normalised to ~[0, 1]), so it
is directly comparable across calibrations.

| Calibration | Non-thermal terms | RMSE (Scaled RI) |
|---|---|---:|
| Linear | — | 0.082 |
| TEX₈₆ᴴ (Kim et al. 2010) | — | 0.085 |
| BAYSPAR (Tierney & Tingley 2014) | — | 0.069 |
| **TEXAS** | thermal only | **0.066** |
| **TEXAS** | + GDGT-2/3 (γ_{G₂/₃}) | **0.060** |
| **TEXAS** | + GDGT-2/3 + NO₃ | **0.059** |

*Values as reported in the initial submission / AGU25 PP33D-1102 (additive-arm
fits). The revised T₀-shift calibration reaches RMSE ≈ 0.05 for the full
multivariate model — reproduce from `SI_code02_t0shift` (and `SI_code2` for the
additive arm).*

The thermal-only TEXAS model already beats the linear and TEX₈₆ᴴ calibrations,
and adding the non-thermal corrections lowers RMSE further — without the
**regression dilution** that affects linear `T ~ TEX₈₆` fits.

You can reproduce a prediction-vs-observation comparison for any cached
posterior with the public API:

```python
import numpy as np
from TEXAS import predict_proxy_from_T

pred = predict_proxy_from_T(
    temperatures=coretop_df["SST"].values,
    posterior="tx.GHPU.sst.sri03.p0",
)
rmse = np.sqrt(np.mean((coretop_df["scaledRI_cren3"] - pred["p50"]) ** 2))
```

---

## 2. Residual diagnostics

Lower RMSE is necessary but not sufficient — a good calibration should also
leave **no systematic structure** in its residuals. The manuscript examines
residuals two ways:

- **Against temperature** — residual-vs-SST plots (Fig. 7–8). Linear and TEX₈₆ᴴ
  show curvature at the temperature extremes (the proxy saturates); the
  generalized-logistic TEXAS curve removes that structure.
- **Spatially** — kriged residual maps (Fig. 9, Fig. S12–S13), rendered with
  `TEXAS.plotting.plot_residual_maps`. Regional residual patterns (e.g. the
  Mediterranean and Red Sea) shrink once the GDGT-2/3 and NO₃ corrections are
  applied, indicating the non-thermal terms capture a real ecological signal
  rather than overfitting noise.

---

## 3. Variance partitioning

To quantify *what the proxy variance is made of*, the coretop proxy variance is
decomposed (Venn-style, after Peres-Neto et al. 2006) into thermal, non-thermal
(GDGT-2/3 and NO₃), and residual components, using the posterior-mean process
noise σ²_proxyObs from nested fits:

| Component | Share of total proxy variance |
|---|---:|
| Thermal (SST) | **74.5 %** |
| GDGT-2/3 (unique) | 2.8 % |
| NO₃ (unique) | 2.2 % |
| GDGT-2/3 ∩ NO₃ (shared) | 0.4 % |
| Residual / irreducible noise | 20.0 % |

*scaledRI_cren3, SST, N ≈ 1513 coretops. See `SI_code2`.*

Temperature dominates (≈ 75 %), confirming Scaled RI is primarily a
thermometer, while the non-thermal predictors each explain a small but
**robustly non-zero** slice. In the published calibration these effects enter
as temperature-equivalent shifts of the curve location — the *T₀-shift
parameterization* (`..._priorApprox_eiv_t0shift`), with
γ_{G₂/₃} = 0.63 ± 0.04 °C per G₂/₃ unit and γ_{NO₃} = 2.79 ± 0.24 °C per
tenfold increase in [NO₃⁻], both resolved away from zero with essentially
full posterior probability.

The preprint expressed the same effects as response-space β offsets; those
estimates, and the archived posteriors that carry them, are preserved on the
[preprint archive page](preprint_additive_archive.md).

> **Note.** Variance partitioning applies to the **forward** calibration only.
> An inverse (invT) reconstruction's posterior width mixes the temperature
> prior, the likelihood, and propagated calibration uncertainty, and cannot be
> cleanly partitioned — use the invT σ uncertainty maps for that instead.

---

## 4. Inverse reconstruction performance

For the inverse direction (proxy → temperature), TEXAS reconstructs coretop SST
with an RMSE of ≈ **3.9 °C** and R² ≈ **0.86**, using a diffuse temperature
prior (`prior_mu_t` = WOA23 SST, `prior_sigma_t` = 10 °C) so the reconstruction
is driven by the data, not the prior (≈ 87 % likelihood weight). This makes the
reported R² a meaningful measure of skill rather than an artefact of an
informative prior.

See `SI_code2` (T-residual plots, Fig. 9) and the paleo applications in
`SI_code03_paleo_showcases.ipynb` for downcore reconstructions with full
posterior uncertainty.

---

## References

- Peres-Neto, P. R., Legendre, P., Dray, S., & Borcard, D. (2006). Variation
  partitioning of species data matrices. *Ecology*, 87(10), 2614–2625.
- Kim, J.-H., et al. (2010). New indices for calibrating the relationship of
  archaeal lipids with sea surface temperature. *GCA*, 74, 4639–4654.
- Tierney, J. E., & Tingley, M. P. (2014). A Bayesian, spatially-varying
  calibration model for the TEX₈₆ proxy. *GCA*, 127, 83–106.
