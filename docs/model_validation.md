# Model validation

How well does a TEXAS calibration fit, and how do we know the generalized-logistic
Bayesian model improves on existing TEX₈₆ calibrations? This page summarizes the
validation reported in the manuscript (Rattanasriampaipong et al., 2026,
*Paleoceanography and Paleoclimatology*); the analysis itself, with every
figure, is `notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb`.
Every number below is quoted from the revised manuscript (under review) and can be recomputed
from the archived posteriors without refitting.

Validation rests on four complementary checks:

1. **Forward calibration performance** — how accurately the curve reproduces the
   observed proxy (R², RMSE in Scaled RI units).
2. **Residual diagnostics** — whether any *structure* remains in the residuals,
   against temperature and on a map.
3. **Inverse reconstruction skill** — how well the calibration recovers modern
   SST from the coretop proxy, globally and by ocean basin, against BAYSPAR and
   the linear and exponential TEX₈₆ calibrations.
4. **Sensitivity** — to the proxy definition and to the sampler budget.

All of the coretop metrics are **in-sample**: they are computed on the gridded
compilation the calibration was estimated from (1,518 cells), and the manuscript
says so. The culture and mesocosm data constrain the warm end that the coretops
never reach.

---

## 1. Forward calibration performance

Scaled RI is predicted from temperature (and, in the bottom layer, from the two
nonthermal predictors), and the posterior-median prediction is compared with the
observation.

| Fit | Data | R²_fwd | RMSE_fwd (Scaled RI) |
|---|---|---:|---:|
| Linear | global calibration dataset | 0.70 | — |
| Exponential (log₁₀) | global calibration dataset | 0.72 | — |
| Top layer (`tx.GCDU.cul.sri03.p0`) | culture + mesocosm | 0.72 | 0.092 |
| Bottom layer, temperature only (`tx.GHPU.sst.sri03.p0`) | 1,518 coretop cells | 0.75 | 0.058 |
| Bottom layer, T + G₂/₃ (`tx.GHEB.sst.sri03.G23`) | 1,518 coretop cells | 0.77 | 0.054 |
| **Bottom layer, T + G₂/₃ + NO₃** (`tx.GHEB.sst.sri03.G23-N1p0`, the published calibration) | 1,518 coretop cells | **0.80** | **0.051** |

*Manuscript Fig. 5d–f (functional forms), Fig. 6 (top layer), Fig. 7 (bottom
layer) and Fig. S13 (all configurations).*

The sigmoid's R² is only slightly above the linear and exponential fits; what
sets it apart is the residual structure (next section). Adding the nonthermal
predictors raises R²_fwd from 0.75 to 0.80 and lowers RMSE from 0.058 to 0.051.

The published SST calibration's parameters (posterior median ± SD):

| T₀ (°C) | b | k | ν | γ_{G₂/₃} (°C per unit) | γ_{NO₃} (°C per log₁₀ unit) | σ_crtp |
|---:|---:|---:|---:|---:|---:|---:|
| 34.8 ± 0.7 | 0.412 ± 0.008 | 0.28 ± 0.04 | 4.0 ± 0.7 | 0.63 ± 0.04 | 2.79 ± 0.24 | 0.0391 ± 0.0011 |

Both γ coefficients are resolved away from zero with essentially full posterior
probability. σ_crtp is pure process noise: the per-site analytical error
(σ_meas = 0.03, the TEX₈₆ interlaboratory reproducibility) is carried separately
and combined in quadrature, so the implied total spread √(0.03² + 0.039²) ≈ 0.049
matches the realized RMSE of 0.051. The prior scale for σ_crtp is set by the
thermal-only fit's R² (≈ 0.75) — this is the only place that quantity enters
the model.

You can reproduce a prediction-versus-observation comparison for any cached
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

A lower RMSE is necessary but not sufficient: a good calibration should leave
**no systematic structure** in its residuals.

- **Against temperature** (Fig. 5d–f). The linear and exponential fits show
  pronounced structure at the warm end, where the proxy saturates; the sigmoid's
  residuals show none across the full range.
- **Spatially** (Fig. 8, Figs. S13, S14, S16). Residuals are kriged onto a map
  with `TEXAS.plotting.plot_residual_maps`. The linear and TEX₈₆ᴴ calibrations
  underpredict in polar waters and the Red Sea; BAYSPAR removes most of that but
  keeps an Arctic residual, because coretops above 70°N were excluded from its
  training set. The TEXAS univariate model already homogenizes the high
  latitudes; the nonthermal predictors then remove the Mediterranean and Red Sea
  warm biases (Red Sea inverse RMSE 6.9 → 2.2 °C). Fig. S16 shows which predictor
  acts where: G₂/₃ in the tropical Atlantic and subtropical Pacific gyres, NO₃
  in the Red Sea and Mediterranean. Kriging six panels takes minutes, so the
  grids are cached under `data/cache/TEXAS_kriged_grids_cache/`; pass
  `recompute='auto'` to build a missing grid or `recompute=True` to re-krige.

The attenuation-bias check behind the errors-in-variables treatment (OLS versus
ODR slopes of the residuals against each predictor; Text S2, Fig. S11) is in
`SI_code01_t0shift_variance_partitioning.ipynb`.

---

## 3. Inverse reconstruction skill

Each coretop's SST is reconstructed from its proxy values with a diffuse prior
(`prior_mu_t` = the modern WOA23 SST at the site, `prior_sigma_t` = 10 °C) and
compared with the observed SST. Global metrics, from Fig. 8:

| Calibration | R²_invT | RMSE_invT (°C) | median σ (°C) |
|---|---:|---:|---:|
| Linear (Schouten et al., 2002) | 0.74 | 5.3 | — |
| TEX₈₆ᴴ (Kim et al., 2010) | 0.68 | 5.9 | — |
| BAYSPAR (Tierney & Tingley, 2014) | 0.83 | 4.3 | 3.3 |
| TEXAS, temperature only | **0.86** | **3.9** | 5.1 |
| TEXAS, T + G₂/₃ | 0.84 | 4.2 | 3.9 |
| TEXAS, T + G₂/₃ + NO₃ | 0.82 | 4.3 | 3.8 |

Two things to read from that table:

- **Adding predictors lowers forward error but not inverse error.** Variance the
  temperature-only model assigns to T is redistributed among T, G₂/₃ and NO₃,
  and the predictors' own measurement uncertainty propagates into the inverse.
  The full model's global RMSE equals BAYSPAR's and stays below the linear and
  exponential calibrations.
- **The posterior width tells the opposite story.** The median 1σ half-width
  falls from 5.1 °C (temperature only) to 3.8 °C (full model); excluding sites
  poleward of 60° brings TEXAS and BAYSPAR to the same 3.1 °C (Fig. 9). The
  remaining high-latitude width is the sigmoid's lower asymptote: with
  σ_meas = 0.03, inverse uncertainty exceeds ±5 °C below 7.1 °C and above
  40.9 °C (Fig. 7d).

**By ocean basin** (Fig. S17; the 21 Natural Earth regions with ≥ 20 cells,
1,286 of 1,518 sites): a TEXAS configuration has the lowest regional RMSE in 12
of 21 regions, BAYSPAR in 7, the exponential calibration in 2. The full TEXAS
model's regional RMSE spans 2.1–5.7 °C against 1.4–9.1 °C for BAYSPAR,
2.1–9.7 °C linear and 1.3–12.7 °C exponential, and the standard deviation of regional RMSE across the 21
regions (1.1–1.2 °C for the three TEXAS configurations) is about half BAYSPAR's (2.2 °C). That comparison is conservative
for TEXAS, which uses one global calibration where BAYSPAR's coefficients vary
by region.

Downcore applications with full posterior uncertainty are in
`SI_code03_paleo_showcases.ipynb` (manuscript Section 8).

---

## 4. Sensitivity

- **Proxy definition** (Fig. S12). Refitting with crenarchaeol counted as 4 or 5
  rings instead of 3 moves none of the four response parameters outside its 68 %
  interval (T₀ = 34.8, 35.4, 35.7 °C) and leaves σ_crtp at 0.0391; R²_fwd falls
  monotonically from 0.803 to 0.785 and 0.772, which is why Scaled RI₀₋₃ is
  adopted. γ_{G₂/₃} is the sensitive coefficient (+20.5 % across conventions),
  so users of another ring convention should refit rather than transfer it.
- **Sampler budget** (Text S3, Figs. S18–S19; the [sampler budget](sampler_budget.md)
  page). Every forward budget that clears the convergence gates agrees with a
  long reference run to within 0.07 SD for every parameter.

---

## References

- Kim, J.-H., et al. (2010). New indices and calibrations derived from the
  distribution of crenarchaeal isoprenoid tetraether lipids. *GCA*, 74,
  4639–4654.
- Tierney, J. E., & Tingley, M. P. (2014). A Bayesian, spatially-varying
  calibration model for the TEX₈₆ proxy. *GCA*, 127, 83–106.
- Schouten, S., Hopmans, E. C., Schefuß, E., & Sinninghe Damsté, J. S. (2002).
  Distributional variations in marine crenarchaeotal membrane lipids. *EPSL*,
  204, 265–274.
