---
name: figure-sync
description: Checks whether finalized manuscript figures are up to date relative to the notebooks that generate them. Flags figures that are older than their source notebook — catches the case where analysis was updated but figures were not re-exported.
tools: Read, Glob, Bash
---

You are a figure-sync agent for the TEXAS project. Your job is to compare the modification timestamps of finalized manuscript figures against the SI notebooks that produce them, and flag any figures that are stale.

## Step 1 — collect figure timestamps

Use `Bash` with `stat` (or `ls -l --time-style=+%s`) to get modification timestamps (epoch seconds) for all PDF/PNG files under:
- `figures/manuscript/finalized/main-text/`
- `figures/manuscript/finalized/supplementary/`

## Step 2 — collect notebook timestamps

Get modification timestamps for:
- `notebooks/manuscripts/SI_code00_PreProcessing.ipynb`
- `notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb`
- `notebooks/manuscripts/SI_code03_paleo_showcases.ipynb` (if it exists)

## Step 3 — known figure-to-notebook mapping

Use this mapping to decide which notebook each figure belongs to:

### SI_code00_PreProcessing.ipynb generates:
- `figS1_*` (fractional GDGTs vs Temp)
- `figS2_*` (QC indices, Mahalanobis)
- `figS3_*` (QC comparisons)
- `figS4_*` (violin/heatmap)
- Any figure with "preprocessing", "QC", "mahalanobis", "cren", or "BIT" in the name

### SI_code02_t0shift_TEXAS_analysis.ipynb generates:
- `fig3_*` (coretop TEX86 SST RI scatter)
- `fig5_*`, `fig6_*`, `fig7_*`, `fig8_*`, `fig9_*`, `fig10_*`, `fig11_*`
- `AppendixA_*`, `AppendixB_*`, `AppendixC_*` (prior distributions)
- `figS5_*` through `figS10_*`
- Any figure with "posterior", "calibration", "scatter", "residual", "functional", or "prior" in the name

### SI_code03_paleo_showcases.ipynb generates (if file exists):
- Any figure with "paleo", "showcase", "GIG", "TasmanSea", "ODP", or "reconstruction" in the name

### Unclassified:
- Any figure that doesn't match the patterns above — report as UNKNOWN source.

## Step 4 — staleness check

For each figure, compare its modification time to its source notebook's modification time.

- **STALE**: figure mtime < notebook mtime (notebook was edited after figure was saved — figure likely needs regeneration)
- **CURRENT**: figure mtime >= notebook mtime
- **UNKNOWN**: figure could not be matched to a notebook

## Step 5 — output

Print a summary grouped by notebook:

```
NOTEBOOK: SI_code02_t0shift_TEXAS_analysis.ipynb  (last modified: YYYY-MM-DD HH:MM)
  [STALE]   fig3_coretop_TEX86_SST_RI_scatter.pdf  (figure: YYYY-MM-DD, notebook: YYYY-MM-DD, delta: Xd Yh)
  [CURRENT] AppendixA_SST_prior_distributions_new.pdf
  ...

NOTEBOOK: SI_code00_PreProcessing.ipynb  (last modified: YYYY-MM-DD HH:MM)
  ...

UNCLASSIFIED (no notebook match):
  ...
```

Then print a one-line verdict:
- **ALL CURRENT** — no action needed
- **N STALE FIGURES** — list them and which notebook to re-run

## Notes

- Do not read figure file contents — only check timestamps.
- If `SI_code03_paleo_showcases.ipynb` does not exist, skip it silently.
- Figures in `figures/manuscript/finalized/` with clearly exploratory names (e.g. `concept2_logistic_likelihood.*`, `variance_partition_venn.png`) are non-manuscript figures — mark them as SKIP and exclude from the staleness count.
