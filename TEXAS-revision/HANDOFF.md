# Handoff — gridT characterization branch

**Branch:** `claude/gridt-inversion-characterization-15i183`
**Last updated:** 2026-09-05 (session `session_011zGno2XfuZ8hGbx3iAFrYJ`)
**Status:** deliverables complete; **one correction applied** after an
independent cross-check contradicted an earlier claim (details below).

## What's on this branch (all under `TEXAS-revision/`)

- `gridT_inversion_characterization.md` — the A/B/C characterization + validation.
- `gridT_explainer.html` — single self-contained teaching page (7 figures embedded).
- `gridT_poster_text.md` — GRC poster captions, 30-sec script, Q&A.
- `assets/*.png` — 7 figures (step-by-step, schematic, likelihood ×2, the-grid,
  vs-plugin, validation).

## Verdict on the method (unchanged)

gridT is **(A) Bayesian quadrature** — same posterior target as the Stan marginal
inverse (m-loop averaged before normalization; σ and prior both enter). Confirmed
independently by the real-Stan notebook for RI 0.55–0.97 (diff_p50 ≤ 0.09 °C,
37× faster).

## Correction applied 2026-09-05 — cold-end caveat (NOT a retraction)

The earlier note claimed agreement with Stan "to < 0.01 °C" across the range and
that the cold tail (RI 0.45–0.50) was "pixel-identical." **That was wrong at the
cold end**, and I've corrected it in place (top banner, validation caveat,
tolerance section, and a new "Cold-end failure" section).

- **Trigger:** `notebooks/current/gridT_vs_stan_comparison.ipynb` @ `5d285ba` on
  `claude/gridT-gui-exploratory` (Ronnie + Claude Opus 5). Real Stan vs production
  `TEXAS.predict_grid.predict_T_grid`, `tx.GHEB.sst.sri03.G23-N1p0`, prior N(15,30).
  RI 0.45: diff_p50 = **10.4 °C**, diff_p1 = **58 °C**, `grid_truncated = False`.
- **I verified it firsthand** (didn't take the peer's word): read
  `predict_grid.py` @ `5d285ba` and reproduced the mechanism analytically
  (11.8 °C gap at RI 0.45; my wide-support p50 −6.0 °C matches the notebook's
  Stan −6.0 °C).
- **Root cause** (two real code issues in `src/TEXAS/predict_grid.py`, *not on
  this branch* — it lives on the exploratory branch):
  1. Lower bound hardcoded `min_temp=-1.8`; only the **upper** bound is adaptive.
  2. `grid_truncated` checks only the top node (`post[-1]`), never `post[0]`, so a
     truncated cold tail is never reported.
  3. Constraint mismatch: the auto-selected Stan model is `..._unconstrained_...`
     (no floor), so the grid's −1.8 floor imposes a bound Stan doesn't have. Near
     the lower asymptote (RI ≲ 0.5) with a diffuse prior this diverges ~10 °C.
- **Why my original validation missed it:** I compared gridT against a reference
  that *shared* its −1.8 floor and used a tighter prior (σ=10). Both masked the
  cold tail. My characterization also described the **docs teaching reference**,
  not the production `predict_T_grid`, whose bound/flag handling I never audited.

## Next steps (for whoever owns `predict_grid.py`)

1. Two-sided `grid_truncated`: also flag `post[0] > 1e-3 * post.max()`.
2. Adaptive, constraint-aware lower bound: `T_lo = min(min_temp, mu_prior − 5σ)`
   when the Stan target is unconstrained; keep −1.8 only for `truncated_prior`/
   `hard_constraint` runs with that `min_temp`.
3. Consider flagging rows whose implied T is within ~1–2 σ of the lower asymptote
   (prior-dominated regardless).

These are `predict_grid.py` fixes on the exploratory branch — out of scope for
this doc branch. I did **not** modify any code, only the characterization note.

## Working-tree / git state

Clean and pushed. No stashes. History: `dc1d5c9 → 79dcc6c → 0c87e77 → <this>`.
Note: on 2026-09-01 the remote branch had been force-reset backward to `79dcc6c`,
dropping ~19 unrelated release/CI commits that came with that session's clone; I
replayed only my own commits on top rather than resurrect them. If that backward
reset was unintended, those commits are recoverable from reflogs.
