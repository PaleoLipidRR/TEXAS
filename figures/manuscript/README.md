# Manuscript figures

| Folder | What it is |
|---|---|
| `finalized/main-text/`, `finalized/supplementary/` | the figures of the **current** manuscript and SI, one file per figure number |
| `revision1/` | working outputs of the revision notebooks (`SI_code02a`, and the reviewer-response `SI_code04`) |
| `sources/` | editable vector sources (`.svg`) for hand-composed figures such as the PSM framework diagram |
| `superseded/` | earlier versions — old numbering, pre-`t0shift` fits, unused `figXX_` drafts. Referenced by nothing; kept for provenance |

## Two trees, deliberately different

These are the **notebook-native** figures. The manuscript repo
(`AGU_PALO_TEXAS_PSM_draft/figures/`) holds submission-prepared copies of the
same plots — larger files, because fonts are embedded for the publisher. Do not
try to sync the two byte-for-byte; regenerate here, then re-run the submission
prep on the manuscript side.

## Two figures are hand-finished

`fig1_existing_calibrations…` and `fig2_TEXAS-PSM-framework` are edited by hand
after the notebook draws them: the notebook writes the `_t0shift` PDF here, the
editable file lives in `sources/`, and the exported `_revised.pdf` that the
paper prints lives only in the manuscript repo. Re-running the notebook does
**not** update what the paper shows for these two.

## The numbering trap

Figure numbers moved as the paper evolved (the MCMC-budget pair went S16/S17 →
S17/S18; main-text figures shifted by one when the ODR figure moved to the SI).
Every renumbering left a copy under the old number next to the new one, and the
notebooks kept writing the old names — so re-running refreshed the stale copy
while the file the SI actually includes went untouched. That bug was live until
2026-08-27.

**When you renumber a figure: rename the file, update the notebook that writes
it, and move the old one here to `superseded/` — never leave a copy under the
old number.**
