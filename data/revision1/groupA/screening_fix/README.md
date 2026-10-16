# Screening fix: Mahalanobis screen on Scaled RI (`scaledRI_cren3`)

**Status (2026-10-16): held on branch `fix/dm-screen-cren3`, not merged.** Merge after the
revised manuscript comes back, together with the figure and number updates listed below.

## The problem

The finalized calibration set (`ds_gridded_screened_global_compilation_finalized.csv`, 1513
core-top cells, 55 culture, 8 mesocosm) was built by SI_code00 cell 97 with the `TEXRI`
Mahalanobis flags, whose features are TEX86 and `scaledRI` (RI with crenarchaeol counted as 4
rings, / 4). The manuscript, the fits and `MahalanobisOutlierDetector.from_calibration()` all use
Scaled RI, `scaledRI_cren3` (crenarchaeol as 3 rings, / 3). Verified three ways: the committed
file matches a `scaledRI` screen exactly (all 1513 cells and medians, all 55 cultures);
`scaledRI` recomputed from the GDGT fractions is RI(cren = 4)/4; and the notebook used the
`TEXRI` filter at a9a8d9f9, the commit that last regenerated the file.

## The fix (on this branch)

- `notebooks/manuscripts/SI_code00_PreProcessing.ipynb` cell 97 filters on
  `TEXRI_cren3_mahalDist_low23ratio_outliers_manual`.
- `scripts/paper/rebuild_finalized_compilation.py` rebuilds the file without running the notebook
  (cells 90, 97, 99, 110 and the NO3 = 10 fill on culture/mesocosm rows). `--check` rebuilds with
  the old features and reproduces the committed file row for row.
- The rebuilt file: 1518 core-top cells (8 added, 3 dropped by value), 59 culture (7 added,
  3 dropped), 8 mesocosm. `add_retained_flag.py` rerun: all 29 rows outside the ellipse are now
  warm-end exceptions (before: 28 outside, 27 exceptions).

## What it changes (both arms refitted on one machine, same code, seed 42, same budgets)

| | change, corrected minus old screen |
|---|---|
| forward posteriors, all 11 fits (`forward_comparison.txt`) | every parameter < 0.3 posterior SD; T0 -0.1 to -0.4 degC; R2 / RMSE in the 3rd-4th decimal |
| T0-shift SST (GHEB): T0, k, nu, gamma_G23, gamma_NO3, R2 | 34.80 -> 34.69, 0.273 -> 0.269, 3.97 -> 3.86, 0.631 -> 0.638, 2.789 -> 2.785, 0.813 -> 0.812 |
| 64 paleo reconstructions (`paleo_reconstruction_*`) | per-sample median ~0.1 degC RMS (the Monte Carlo floor: thermal-only, nearly unaffected by the screen, shows the same); no run's mean > 0.11 degC; 68% widths +-0.1 |
| T0-shift core-top maps (`coretop_maps_comparison.txt`) | inverse RMSE 4.355 -> 4.339 (SST, G23 + NO3); coverage within 0.01; shared cells' residuals 0.13 degC RMS |

No figure should look different and no number quoted to one decimal changes. What does change:
the sample counts (1513 -> 1518 core-top cells, 55 -> 59 culture) and statistics quoted to three
decimals.

## Prior check (inverse skill with priors that ignore the answer)

The inverse-skill comparison (SI_code04) gives TEXAS and BAYSPAR the same prior, N(measured SST,
10), centred on the value being scored. `run_coretop_maps.py --prior`,
`bayspar_prior_variants.py` and `score_prior_variants.py` rescore both under a latitude-only prior
(30 cos^2(lat) - 1) and a constant 15 degC (`prior_variant_skill.csv`, 1518 cells):

| prior | TEXAS T0-shift R2 / RMSE | TEXAS thermal-only R2 / RMSE | BAYSPAR R2 / RMSE |
|---|---|---|---|
| measured SST (published) | 0.824 / 4.34 | 0.860 / 3.87 | 0.831 / 4.26 |
| latitude only | 0.828 / 4.30 | 0.859 / 3.89 | 0.827 / 4.30 |
| 15 degC everywhere | 0.767 / 5.00 | 0.710 / 5.58 | 0.788 / 4.77 |

The truth-centred prior does not inflate TEXAS's reported R2: under a realistic prior it is
unchanged. Without geographic information TEXAS degrades more than BAYSPAR, almost all at polar
sites (flat cold end of the S-curve); there the truth-centred prior also flatters the thermal-only
model (polar RMSE 3.20 -> 3.98, coverage 0.987). The measured-prior thermal-only row reproduces
the published 3.88 / 0.860. Forward R2 is unaffected by the inverse prior by construction.

## On merge, after the reviews

1. Posteriors: the refits are in the `TEXAS-cren3` worktree's cache
   (`data/cache/`, gitignored, this machine only), run with `TEXAS_CACHE_DIR` pointed there.
   Elsewhere, rerun `run_manuscript_refits.py all`, `fit_t0shift_single_predictors.py` and
   `run_coretop_maps.py --arm bnd|eiv|univ` (~20 h). Their manifests in
   `manuscript_refit/` must be regenerated with the outputs; the committed ones list the old
   runs as done, so move them aside first or every run is skipped.
2. Regenerate `data/spreadsheets/predT_bayspar_p16_p50_p84.csv` for the 1518 cells (SI_code04
   asserts every site has a BAYSPAR prediction); `bayspar_prior_variants.csv` here has the SST
   columns under the measured prior already.
3. Rerun SI_code01, SI_code02, SI_code02a, SI_code03 and SI_code04 against the new posteriors;
   update counts (1513 -> 1518, 55 -> 59) and three-decimal statistics in text, tables, SI.
4. Zenodo: the calibration set and the posteriors change, so a new data-record version (and the
   `download.py` record id / registry together, in a release).

`scripts/` here are the comparison scripts used for the tables above; they read the
`TEXAS-baseline` and `TEXAS-cren3` worktrees by absolute path on the machine that ran them.
