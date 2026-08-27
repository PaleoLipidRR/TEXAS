# Reviewer comments → what exists in this repo

**Written 2026-08-13 · statuses updated 2026-08-17.** Source:
`working-repo/TEXAS-revision/ReviewerComments.md`. Deadline: **2026-09-08**.

> Entries 1.5, 2.3, 2.4 and 3.4 were stale and are now corrected. 3.4 in
> particular carried a **retracted** result — read its warning box before
> quoting anything about interval width.

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

* models: `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift.stan`,
  `invT_gen_logi_fixed_multiv_marginal_unconstrained_t0shift.stan`
* both temperature targets, fitted at one budget against the parent with
  identical training rows and R2_thermal (`comparability_audit.json`, 15/15)
* figures: `fig7/10/11/12/13_*_t0shift.pdf`, `Appendix{A,B,C}_*_t0shift.pdf`
  (renumbered after the ODR figure moved to the SI; `boundedT` → `t0shift`)
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

> ⚠️ **RETRACTED 2026-08-14 — do not quote the "~14% too narrow" result.**
> An earlier version of this entry reported half-width / residual SD ≈ 0.865
> and a +0.93 °C bias, concluding the predictive intervals were ~14% too
> narrow. That came from `param_sensitivity/invt_budget_sites.csv`, which is
> the **200-site stress set** — tail-weighted by construction, and not held
> out. It is not a population estimate and must not be quoted as one.

Over all **1513** sites the production calibration is essentially calibrated
and **the bias flips sign**: bias **−0.99 °C**, RMSE **4.35**, R² **0.824**,
cov68 **0.664** against 0.68 nominal. Univariate is *better* in the inverse
direction (RMSE 3.87, R² 0.860) — which is the evidence behind 2.5 and R1.2,
and the reason the forward-vs-inverse asymmetry is conceded rather than
explained away.

The plot change (adding 95% alongside 68%) still stands, and so does stating
explicitly which quantity the intervals describe. The answer is the **full
predictive** uncertainty including the residual noise term.

### 3.5 Streamline technical detail; move screening/index selection to SI — **TEXT**

Editorial restructuring. Nothing to compute.

### 3.6 Robustness to alternative screening, index definitions, priors — **PARTLY DONE**

> demonstrate that the main conclusions are robust to reasonable alternative
> screening decisions, index definitions, and prior specifications

* **index definitions — DONE.** `SI_code02a` Part 2 fits SRI03 / SRI04 / SRI05,
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

### 2.3 PETM depends on priors and nitrate scenario — **DONE** (closed 2026-08-14)

SI03 already runs four NO3 scenarios (`no3_modern`, `no3_01`, `no3_001`,
`no3_10`) across both arms — that is the nitrate half.

**The prior half needed no run after all.** Every reconstruction used
`prior_sigma_t = 10` (verified in SI03 cell 61 for the PETM block, cell 77 for
the extreme cases — *not* 15), and because prior and posterior share a scale
the posterior/prior variance ratio bounds the prior's contribution directly:
South Dover Bridge 0.05 (95% of the variance from data), ODP 959 0.14–0.16,
ODP 1259 0.29, Co1010 0.35. A prior 4–20× wider than the posterior it produces
is not setting the answer.

The same table does two more jobs: prior influence rises monotonically toward
both asymptotes, which is the asymptote argument independently confirmed, and
Co1010 is the most prior-influenced record in the study, which confirms R1's
Antarctic criticism (see 1.5). Nitrate-scenario sensitivity at the PETM sites
is second-order too — −1.34 °C (SDB), −0.96 °C (ODP 959), both smaller than a
single run's 68% half-width, against −4.5 to −5.3 °C at the Quaternary sites.

### 2.4 Validation / performance claims — **DONE** (re-run 2026-08-21, gridded)

> claims that TEXAS outperforms existing calibrations should be softened or
> supported with clearer cross-validation, ideally using spatially blocked tests

**This has been run in full** — `working-repo/TEXAS-revision/scripts/fit_t0shift_comparison.py`,
`"smoke": false`, 5 folds, **n = 1513 (gridded)**, ~1 h. It needs working-repo's
own uv environment; `uv.lock` there is the record of what produced these
numbers, so do **not** re-run it under TEXAS's venv.

> The first pass used the **ungridded n = 2043** subset and every number it
> produced is superseded. The load cell in SI_code04 now asserts
> `dataset == "gridded"` and refuses to publish the old export. Numbers below
> are the gridded ones (figures and tables regenerated 2026-08-22).

Exports (CSV/JSON, readable anywhere) live in `../model_comparison_cv/` with a
`PROVENANCE.md`; `results.pkl` is deliberately not the record, because it is a
pandas-3 pickle that will not load under TEXAS's pandas 2. The analysis is
`notebooks/reviewer_response/SI_code04_model_comparison_cv.ipynb`, which reads only
the exports and never samples.

What it gives each comment:

* **R2's validation demand.** Spatial blocking degrades both arms
  (R² 0.802 → 0.750, cov95 0.939 → 0.899), so the in-sample figures are
  labelled as such and the blocked counterparts quoted beside them.
* **R3.1's formal comparison** (see 3.1). T₀-shift beats additive on every
  metric; Δelpd = **+24.3 ± 11.6** (2.1 SE). The additive fitted mean reaches
  **0.343** where the T₀-shift floor is **0.420** — both below/above the fitted
  lower asymptote *b* ≈ 0.41, which is the physical line being crossed.
  **Soften this relative to the earlier draft:** under spatial blocking the two
  arms are within ΔRMSE = 0.0002 of each other (0.0574 vs 0.0572), so the case
  for T₀-shift is boundedness and elpd, *not* predictive accuracy.
* **The outperformance claim itself.** Multivariate TEXAS and BAYSPAR are
  statistically indistinguishable on RMSE (Δ = +0.041 °C, p = 0.786) — claim
  neither outperformance nor concede underperformance. Univariate TEXAS
  significantly beats BAYSPAR (−0.456 °C, p = 0.001), which is safe to claim.
  The residual-structure ordering (Moran's I 0.423 multivariate < 0.579
  univariate < 0.650 BAYSPAR < 0.769 Schouten02 < 0.810 Kim2010) is monotonic
  in how much mechanism each model represents — the *reverse* of the RMSE
  ranking, i.e. the multivariate model converts systematic regional error into
  random error.

> Two n are in play — always state which: **1513** (the CV, and the production
> calibration — same gridded set, so they are on the same footing) and **1298**
> (the comparison against other calibrations, after 215 sites drop for unmatched
> or ambiguous TEX₈₆ joins). TEXAS is **in-sample** in that comparison and the
> others are not; say so.

Still optional, and not needed for the argument: a spatially blocked **refit**
of TEXAS (~3.5 h) so its side is genuinely held out. The **12.9%** in-sample →
spatial penalty measured above currently stands in as a bound.

### 2.5 Forward vs inverse performance — **WRITE**

> inverse temperature prediction performance appears to decrease slightly as
> predictors are added … most users will apply TEXAS in the inverse direction

`param_sensitivity/invt_budget_grid.csv` has bias / MAE / RMSE / coverage68 /
coverage90 per configuration. The numbers exist; the framing does not.

### 2.6 Report MCMC diagnostics explicitly — **DONE**

`diagnostics_table.csv`. All seven manuscript calibrations pass every gate:
max R-hat 1.00372–1.00909, min ESS(bulk) 796–1633, zero divergences, zero
treedepth saturations, 4 chains x 1000 draws.

Fuller convergence characterisation, if wanted: `SI_code02a` Part 1 sweeps 27
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

### 1.5 PETM priors not tested — **DONE** (same as 2.3, closed 2026-08-14)

Were iCESM-derived priors tested against data-driven alternatives? Also the
Antarctic 10 degC prior against reconstructions near 0 degC, and Fig 14b showing
temperatures below seawater freezing.

Answered by the variance-ratio argument in **2.3** — no refit required. Note
that the ratio table **confirms this reviewer's Antarctic criticism** rather
than rebutting it: Co1010 is the most prior-influenced record in the study
(0.35, i.e. 35% of its posterior variance traceable to the prior). Say so.

### 1.6 Cite Bijl et al. (2025) — **TEXT**

---

## What actually needs new compute

**Updated 2026-08-17.** Two of the original four are closed; what is left is
the screening pair.

1. **Screening sensitivity** (3.6 / 2.8) — the only genuinely unrun items.
   Two separate runs: the **Mahalanobis threshold sweep**, and a **refit
   without the `>= 0.75` retention rule**. The latter also closes 3.3's
   screening-robustness request. Worth knowing before you start: that rule
   keeps 39 samples (1.9%) the 90% ellipse would drop, at mean SST 27.7 °C
   against 16.3 °C for the rest — so the warm-end leverage the reviewer
   suspected is real, and the refit is answering a live question, not a
   formality. (Reproduced on the processed coretop table, n = 2024; the
   production chain grids to 1513, so treat the 39 as indicative.)
2. **Optional, not needed for the argument** — a spatially blocked *refit* of
   TEXAS (~3.5 h) so its side of the calibration comparison is genuinely held
   out. The 8.7% in-sample → spatial penalty from the CV stands in as a bound.

Closed since this file was written:

* ~~Spatially blocked CV + WAIC~~ — **run in full 2026-08-13**, see 2.4.
* ~~PETM prior sensitivity~~ — **no run needed**, closed by the variance-ratio
  argument, see 2.3.
* ~~An uncertainty-calibration figure~~ — the result it was meant to show was
  an artifact of the stress set and has been retracted; see the warning in 3.4.

Everything else is writing against numbers that already exist.
