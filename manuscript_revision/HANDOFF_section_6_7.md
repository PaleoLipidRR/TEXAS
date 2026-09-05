# Handoff — Section 6–7 revision (bounded-T non-thermal formulation)

- **Date:** 2026-09-05
- **Branch:** `claude/bounded-t-model-revisions-idrogu` (see "Branch discrepancy" below)
- **Resubmission deadline:** 2026-09-08

## Where this stands

**Done (text drafted, in this commit — `sections_6_7_boundedT_draft.md`):**
- Full replacement draft for Sections 6–7, written entirely in the bounded-T
  (inflection-shift) framing. Readers see only the bounded-T model; the additive
  form is never mentioned. The GLM *principle* (covariates enter a linear predictor
  mapped to the response's support by a link) is used as positive motivation, and the
  model is classified honestly as a generalized *nonlinear* model (estimated asymptote
  `b` and shape `ν`, so not a GLM in the strict sense).
- Section 7 opening paragraph added: HMC configuration (forward 1,000 warmup /
  1,000 sampling; inverse 500 / 1,000; 4 chains; adapt_delta 0.8; max_treedepth 10),
  a pointer to Supplementary Text S[X], and a note that the noise/scale and diagnostic
  parameters are archived in every `.nc`. These numbers are the code defaults
  (`predict.py`, `stan/invT.py`, `stan/sampler.py`).

**Not done / untouched:**
- **No figures** were produced or modified in this session.
- **No model was fitted.** Every posterior number in §7.1–7.2 is a bracketed
  placeholder (`[mu_min]`, `[mu_max]`, `[gamma_G23]`, `[gamma_NO3]`, `[R2_full]`,
  `[RMSE_full]`). There is **no fitted bounded-T posterior in the repo** (no
  `data/cache/TEXAS_posterior_cache/`, no `*_boundedT_*.nc`). To fill them, fit
  `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT.stan` (needs the coretop
  data dict + an `R2_thermal` from a thermal-only run; `sampler.py` raises if missing).
- **Supplementary Text S[X]** on sampling-parameter tuning is *referenced but not
  written*. The claim "selected as the point beyond which additional warmup/sampling
  produced no material change" needs an ESS / R-hat-vs-iterations sweep to back it,
  or should be softened to a plain convergence statement.
- **No code changes.**

## Next action
1. Fit the bounded-T model; replace the §7.1–7.2 placeholders with real posterior values.
2. Write (or descope) Supplementary Text S[X] on sampling-parameter choice.
3. Assign the real S[X] cross-reference number.

## Branch discrepancy — needs a human decision
This session's task config bound it to `claude/bounded-t-model-revisions-idrogu` and
forbade pushing elsewhere without explicit permission. A peer session (github-12
end-of-day sweep) twice asked to push this work to `revision/boundedT-si-figures`
instead. That push was **not** performed — this session has no authorization for it.
The draft and this note are committed to `claude/bounded-t-model-revisions-idrogu`.
If `revision/boundedT-si-figures` is the intended home, cherry-pick this commit across.

## Repo-state flags (reported by the peer sweep; not independently verified here)
- **Branch is behind main.** TEXAS `main` has moved to `41ba78e` (recent origin
  history mentions "update conda-lock.yml for v0.3.2 (#24)"). Both this branch and
  `revision/boundedT-si-figures` (reported 5 weeks old at `088ca46`) are well behind
  and should be rebased before resubmission rather than assuming a stale base.
- **gridT cold-end validity is unvalidated.** On `claude/gridT-gui-exploratory`
  commit `5d285ba`, an executed Stan-vs-quadrature comparison shows gridT agreeing with
  Stan to ≤0.05 °C across RI 0.55–0.97 but diverging by 10.4 °C at the median
  (58 °C at p1) at RI 0.45 — the cold end — while `grid_truncated` still reports
  `False`. Note RI 0.45 sits just above the bounded-T lower asymptote `b≈0.41`, where
  `dRI/dT → 0` and the inverse is ill-conditioned. If any part of Section 6–7 rests on
  gridT at the cold end, record it as **unvalidated**, not resolved.
