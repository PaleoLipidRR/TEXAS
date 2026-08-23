# Archive — the preprint's additive (β) formulation

```{admonition} Archived material
:class: warning
This page preserves the **additive multivariate formulation** used in the
initial submission (preprint) of the TEXAS manuscript and in the posteriors
currently archived on Zenodo. The **revised manuscript supersedes it** with
the [T₀-shift parameterization](index.md) (γ on the curve location T₀), which
keeps predicted Scaled RI inside its physical bounds by construction. This
page exists so readers arriving from the preprint, or working with the
archived `GHEA` posteriors, can map what they see onto the current model.
```

## The additive model

In the preprint, the nonthermal predictors entered **outside** the logistic,
as offsets added to the response:

$$
RI_{\text{scaled}}(T, X) = b + \frac{1 - b}{\left( 1 + e^{-k (T - T_{0})} \right)^{1/v}} + \beta_{\text{G}_{2/3}} \cdot \text{G}_{2/3} + \beta_{\text{NO}_3} \cdot \log_{10}[\text{NO}_3^-]
$$

The β coefficients carry **Scaled-RI units per predictor unit**. Because the
offsets act on the response, sufficiently large predictor values can push
predictions outside the index's physical range (b, 1) — the objection raised
in review, and the reason the revised model moves the predictors inside the
logistic instead.

## Preprint coefficient estimates

From the additive errors-in-variables coretop fit (SST, `scaledRI_cren3`,
NO₃ cutoff 1.0):

| Coefficient | Posterior mean ± SD | P(β < 0) |
|---|---|---:|
| β_{G₂/₃} | −0.0058 ± 0.0004 | ≈ 1.0 |
| β_{NO₃} | −0.0329 ± 0.0025 | ≈ 1.0 |

Both are resolved away from zero with essentially full posterior probability
(reported as the posterior probability of the expected sign, not a frequentist
p-value). The negative signs mean elevated G₂/₃ or nitrate lower the Scaled RI
recorded at a given temperature — the same direction the T₀-shift model
expresses as *positive* γ (a shift toward apparently colder water), since
locally β ≈ −γ·f′(T) where f′ is the calibration slope.

## The archived posteriors are this model

The multivariate posteriors on the current Zenodo record are additive-arm
fits — compset `GHEA` (`A` = additive):

| Case id | Legacy (archived) file name |
|---|---|
| `tx.GHEA.sst.sri03.G23-N1p0` | `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc` |
| `tx.GHEA.thm.sri03.G23-N1p0` | `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3.nc` |

They carry `beta_G23_crtp` / `beta_NO3_crtp` variables. The revised
calibration (`GHEB`, T₀-shift, `gamma_*` variables in °C per predictor unit)
will be archived with the v1.0.0 Zenodo record at paper acceptance; until
then, refit it locally with the
`gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift` Stan model. The
package's ensemble and inverse machinery auto-detects which arm a posterior
belongs to from its variable names, so both remain fully usable.

## What carries over unchanged

The **evidence** that the nonthermal effects exist — residual regressions and
the [variance partitioning](model_validation.md) (thermal ≈ 75 %, G₂/₃ and
NO₃ each a small but robustly non-zero share) — is response-space analysis
that does not depend on which parameterization consumes the effects, and
remains part of the revised manuscript. Only the *placement* of the
correction changed: from β on the response to γ on T₀.
