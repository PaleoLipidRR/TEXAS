# Reviewer comments → what exists in this repo

**Written 2026-08-13.** Source: `working-repo/TEXAS-revision/ReviewerComments.md`.
Deadline: **2026-09-08**.

The point of this file is to separate three things that are easy to confuse when
a review is long: what is **already answered and computed**, what is **a writing
job** on numbers that already exist, and what **needs new analysis**. Only the
third kind costs time.

Status key — `DONE` evidence exists in this repo · `WRITE` numbers exist, prose
does not · `NEW` needs analysis that has not been run · `TEXT` manuscript-only,
nothing to compute.

---

## Reviewer #3

### 3.1 "The bottom-layer model is not bounded" — **DONE**

> The linear factors in Eq. 10 make the model mathematically unbounded… The
> authors should consider a model in which the secondary effects would be
> included in the logistic part.

This is the bounded-T model, and it is fitted, audited and plotted.

    t0_eff = t0 + gamma_G23*G23 + gamma_NO3*log10(NO3)
    mu     = b + (1-b)/(1+exp(-k(T - t0_eff)))^(1/v)

so `mu` stays in `(b, 1)` for any finite predictor value — which is precisely
what the reviewer asks for.

* models: `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT.stan`,
  `invT_gen_logi_fixed_multiv_marginal_unconstrained_boundedT.stan`
* both temperature targets, fitted at one budget against the parent with
  identical training rows and R2_thermal (`comparability_audit.json`, 15/15)
* figures: `fig7/11/12/13/14_*_boundedT.pdf`, `Appendix{A,B,C}_*_boundedT.pdf`
* coefficients: `gamma_G23 = 0.634 [0.592, 0.673]` degC per unit G23,
  `gamma_NO3 = 2.791 [2.550, 3.040]` degC per log10 unit

**Not done, and R3 names them:** secondary effects on **kappa**, and
**temperature x predictor interactions**. Neither is implemented. Worth
addressing explicitly rather than silently — even a sentence saying they were
considered and why gamma-on-T0 was chosen.

### 3.2 Noise terms not reported — **DONE**

> I can't find the estimate for the noise term (or sigma^2_culmeso) of the top
> layer (nor the bottom layer, epsilon), as in Eq 11 and 14.

They were estimated all along; they were filtered out of the figures.
`CORE_GROUPS` in `plotting/prior_plot.py` was `("t0","k","b","v","a")` — sigma
was never in the list, so the Appendix figures could not draw it.

| | median | 68% CrI |
|---|---:|---|
| `sigma_proxyObs_cul` (Eq 11) | 0.0983 | 0.0895–0.1088 |
| `sigma_proxyObs_meso` (Eq 11) | 0.0678 | 0.0513–0.0912 |
| `sigma_proxyObs_crtp`, thermal only (Eq 14) | 0.0577 | 0.0566–0.0588 |
| `sigma_proxyObs_crtp`, additive EIV | 0.0410 | 0.0398–0.0422 |
| `sigma_proxyObs_crtp`, bounded-T | 0.0391 | 0.0380–0.0403 |

**The argument to make, not just the numbers:** the bottom-layer noise falls
**29%** when the predictors enter, and the 95% intervals do not overlap. That is
the reviewer's own point — noise terms are part of the model, not ancillary —
demonstrated with the statistic they asked for. Variance split at the coretop
layer is roughly 35% analytical / 65% process.

Evidence: `parameter_table.csv`, `Appendix{A,B,C}` panels.

### 3.3 R2/RMSE need credible intervals — **DONE**

`parameter_table.csv` carries 68% and 95% credible intervals for every
parameter, noise term and diagnostic.

**Decision still open:** `R2_full` and `bayesR2_full` differ by ~0.06 (0.813 vs
0.874 for bounded-T SST), far more than either interval. They are different
quantities. The manuscript must quote one and name it. Recommend
`bayesR2_full` — it propagates parameter uncertainty, which is what the reviewer
is asking to see; `R2_full`'s +/-0.002 interval will read as implausibly precise.

### 3.4 68% intervals too narrow; also report 95% — **WRITE + small plot change**

> The use of 68% credible intervals … may give an overly precise visual
> impression (examples are Fig 7, Fig. 8, and Fig. 11-14).

Named figures use `annotation_style='ci68'`. The table already has both.
Plot change is small; the figures are the work.

> It should also be made explicit whether the reported intervals describe
> uncertainty in the fitted mean relationship or the full uncertainty of
> reconstructed temperatures, including the residual noise term.

**This is the same question as the coverage result, from the other direction,
and the honest answer is unflattering:** the predictive intervals are ~14% too
narrow. Half-width / residual SD = 0.863–0.867, which reproduces the observed
coverage of both nominal levels from one number:

| nominal | predicted from the ratio | observed |
|---|---|---|
| 68% | 0.612 | 0.600 |
| 90% | 0.846 | 0.840 |

The +0.93 degC bias contributes essentially nothing (removing it moves coverage
by −0.005). Stable to 0.004 across every budget cell, so it is a property of the
model, not the sampler. Mechanism: the residual spread carries site-level
variability (oceanographic, depth-habitat, bioturbation) the noise model does
not.

Data: `param_sensitivity/invt_budget_sites.csv`. **No figure is drawn from it
yet** — this is the strongest candidate for a new SI panel.

### 3.5 Streamline technical detail; move screening/index selection to SI — **TEXT**

Editorial restructuring. Nothing to compute.

### 3.6 Robustness to alternative screening, index definitions, priors — **PARTLY DONE**

> demonstrate that the main conclusions are robust to reasonable alternative
> screening decisions, index definitions, and prior specifications

* **index definitions — DONE.** `SI_code2a` Part 2 fits SRI03 / SRI04 / SRI05,
  now under *both* parameterisations. Both rank the conventions identically and
  monotonically; the G23 spread is 12.1% (additive) vs 20.5% (bounded-T), NO3
  ~3.5% in both. Worth stating that the G23 sensitivity is ~1.7x larger under
  the production model — a reader who carries the additive robustness across
  would overstate it.
* **screening decisions — NEW.** Not tested. R2 asks the same thing twice
  (Mahalanobis threshold rationale; the `>= 0.75` high-index retention rule).
* **prior specifications — NEW.** Not tested.

### 3.7 "Credible" not "confidence" — **DONE (one file left)**

Notebooks were already clean; `docs/PSM.md` fixed 2026-08-13. The only
remaining occurrence repo-wide is in `docs/tutorial/module5_results.md`,
which deliberately contrasts the two terms and should keep it.

### 3.8 Abbreviations at first use — **TEXT**

L16 TEX86, L16 GDGT, L26 AOA, L27 RMSE, L28 SST, L31 PETM.

---

## Reviewer #2

### 2.1 PSM framing overstated — **TEXT**

Describe TEXAS as a Bayesian sensor/calibration model embeddable in a fuller
PSM; archive model is explicitly not implemented. Affects title, key points,
abstract, Figure 2. (Also: "surfuce" → "surface" in Fig 2.)

### 2.2 Nitrate as prescribed, not corrected — **TEXT**

Frame deep-time nitrate as conditional reconstructions / sensitivity tests.
Soften "corrects for", "resolves", "reconciles".

### 2.3 PETM depends on priors and nitrate scenario — **PARTLY DONE**

SI03 already runs four NO3 scenarios (`no3_modern`, `no3_01`, `no3_001`,
`no3_10`) across both arms — that is the nitrate half. **Alternative temperature
priors are NEW**; R1 asks the same thing independently (see 1.5).

### 2.4 Validation / performance claims — **NEW, and the biggest one**

> claims that TEXAS outperforms existing calibrations should be softened or
> supported with clearer cross-validation, ideally using spatially blocked tests

**A script for exactly this already exists and has never been run properly:**
`working-repo/TEXAS-revision/scripts/fit_boundedT_comparison.py` implements
`spatial_folds()`, WAIC and paired elpd differences, fitting parent and
bounded-T on identical subsets. Its `outputs/manifest.json` says
`"smoke": true, "folds": 2`. Full mode is 5 folds at 500/1000, roughly an hour
of Stan.

Running it answers R2's validation demand **and** gives R3 a formal
parent-vs-bounded model comparison. Highest value-per-hour item in this file.

Note it needs working-repo's own uv environment — `uv.lock` there is the record
of what produced reviewer-facing numbers, so do not run it under TEXAS's venv.

### 2.5 Forward vs inverse performance — **WRITE**

> inverse temperature prediction performance appears to decrease slightly as
> predictors are added … most users will apply TEXAS in the inverse direction

`param_sensitivity/invt_budget_grid.csv` has bias / MAE / RMSE / coverage68 /
coverage90 per configuration. The numbers exist; the framing does not.

### 2.6 Report MCMC diagnostics explicitly — **DONE**

`diagnostics_table.csv`. All seven manuscript calibrations pass every gate:
max R-hat 1.00372–1.00909, min ESS(bulk) 796–1633, zero divergences, zero
treedepth saturations, 4 chains x 1000 draws.

Fuller convergence characterisation, if wanted: `SI_code2a` Part 1 sweeps 27
budget cells x 3 models with per-parameter R-hat.

### 2.7 Practical guidance section — **TEXT** (overlaps R1.1)

SST vs Thermo-T; unconstrained paleo-nitrate; samples outside the Mahalanobis
ellipse; RI0-3 vs RI0-4 (the last is answered by 3.6).

### 2.8 Specific comments — **TEXT**

Title, key points, abstract, Fig 2, Cren weighting as empirical choice,
Mahalanobis guidance and threshold rationale, high-index retention rule,
upper asymptote constrained by culture/mesocosm, nitrate sign intuition,
BAYSPAR framing, PETM priors, conclusions softening.

Two of these are **NEW** analysis, not text: the Mahalanobis-threshold
justification and a sensitivity test without the `>= 0.75` retention rule.

---

## Reviewer #1

### 1.1 "A clear statement of what is required to use this model" — **TEXT / docs**

Data layout, units (%, concentrations, peak areas?), what auxiliary data is
needed, what to prepare before running. R1 is explicitly not a Python user and
could not find this on Zenodo. Overlaps R2.7.

### 1.2 RMSE increase in the inverse direction — **WRITE** (same data as 2.5)

Is >4 degC problematic? Is the trend still usable? Does extra proxy data reduce
it?

### 1.3 Time-varying nitrate — **TEXT, possibly NEW**

Can TEXAS take a nitrate time series rather than one scenario? Worth checking
whether `predict_T_from_proxyObs` already accepts a per-sample nitrate vector —
if it does (it takes arrays for predictors), this is a documentation answer, not
a code change.

### 1.4 Polar fronts / Ishii et al. (2026) — **TEXT**

Cite at the cold-water discussion; step-changes in community across the Polar
Front complicate a single low-temperature relationship. Relevant to the polar
behaviour in fig9/fig10.

### 1.5 PETM priors not tested — **NEW** (same as 2.3)

Were iCESM-derived priors tested against data-driven alternatives? Also the
Antarctic 10 degC prior against reconstructions near 0 degC, and Fig 14b showing
temperatures below seawater freezing.

### 1.6 Cite Bijl et al. (2025) — **TEXT**

---

## What actually needs new compute

Ordered by value per hour.

1. **Spatially blocked CV + WAIC** (2.4, and gives 3.1 a formal comparison).
   ~1 h. Script exists, never run in full.
2. **An uncertainty-calibration figure** (3.4). Data exists, no figure. Answers
   the "fitted mean or full predictive?" question directly.
3. **PETM prior sensitivity** (1.5 / 2.3). Alternative temperature priors;
   nitrate scenarios already done.
4. **Screening sensitivity** (3.6 / 2.8): Mahalanobis threshold, and the
   `>= 0.75` retention rule.

Everything else is writing against numbers that already exist.
