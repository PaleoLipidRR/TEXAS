# Reviewer-response analyses

Analyses run to answer reviewer comments that are **not cited in the
manuscript or the SI**. They are kept — and shipped with the software
release — because they are the evidence behind editorial decisions the
response letter states, and because a reviewer may ask for them at the next
round. They are held apart from `notebooks/manuscripts/` so that the Open
Research claim, *"the notebooks that generate every figure in this
manuscript"*, describes that folder exactly.

## `SI_code04_model_comparison_cv.ipynb`

WAIC and 5-fold cross-validation (random and spatially blocked) comparing
the additive β-on-μ arm against the T₀-shift parameterization, plus an
inverse-direction skill comparison against the existing calibrations,
a paired bootstrap on RMSE, and Moran's I on the residuals.

Written for **R2C4** ("*claims that TEXAS outperforms existing calibrations
should be softened or supported with clearer cross-validation, ideally using
spatially blocked tests*") and **R3C1** (boundedness).

**Why it is not in the manuscript.** The response to R2C4 answers the comment
a different way: every calibration-set metric is now labelled *in-sample*,
and the pooled global comparison is complemented by the region-resolved
breakdown across 21 basins (Fig. S16, from `SI_code02_t0shift_TEXAS_analysis`).
The letter states plainly that this is "*a regional breakdown of calibration
residuals, not an out-of-sample validation*", and that no out-of-sample claim
is made anywhere in the revised manuscript. Publishing the CV table would
contradict that framing by making an out-of-sample claim after all — so the
analysis stayed out of the paper. It supports the *decision*, not a printed
result.

The boundedness numbers here (additive fitted mean falls to 0.343, below the
curve's own lower asymptote *b* ≈ 0.41; T₀-shift stays at 0.420) are the
fitted means at the observed sites. They are **not** the numbers quoted at
R3C1 in the response letter, which evaluates the curve over T = −2 to 40 °C
at posterior-median coefficients and is computed separately.

It does not fit anything: the fits live in
`working-repo/TEXAS-revision/scripts/fit_t0shift_comparison.py` under a
separate locked environment, and this notebook reads their exported results
from `data/revision1/groupA/model_comparison_cv/`.

> Its figures were named `figS17_spatial_cv_folds` and
> `figS18_inverse_skill_by_block`, which collided with the SI's real S17 and
> S18 (the MCMC-budget pair). Since they appear in no SI, treat the numbers
> as meaningless here; do not renumber them back into the SI sequence.
