# TEXAS — Revision-1 analysis workflow (AGU PALO 2026PA005459)

Roadmap for the reviewer-requested **sensitivity-test / statistics reruns** for the
major revision (decision 2026-07-13, revised MS due **2026-09-08**). This doc is the
single source of truth for the workflow: reviewer-comment → exact TEXAS call, data
dependencies, compute notes, and status. A new session should start here.

> **Resume prompt:** *"Continue the TEXAS revision-1 workflow per
> `docs/revision1/analysis_plan.md`. Group A is done; build Group C (spatial CV) next."*

All `file:line` references are to the primary package under `src/TEXAS/` and the
manuscript notebooks under `notebooks/manuscripts/`, verified 2026-07-15.

---

## Design

**Format:** hybrid — reusable, tested logic in `src/TEXAS/validation/`; thin
`notebooks/revision1/` notebooks that call it and render reviewer-facing figures;
long-running batch refits in `scripts/revision1/`; every result persisted to disk.

```
src/TEXAS/validation/
  io.py         save_result/load_result/list_results — .nc + .csv with provenance   [DONE]
  intervals.py  credible_interval() (68/90/95%), "credible" labeling                 [DONE]
  metrics.py    summarize_calibration_metrics/_noise_terms/diagnostics_table         [DONE]
  crossval.py   spatially-blocked k-fold: partition → refit → score held-out         [DONE — core+tests]
  sensitivity.py forward refit under RI / screening / retention variants             [TODO — Group B]
scripts/revision1/  run_crossval.py · run_sensitivity_refits.py                      [TODO]
notebooks/revision1/
  R1_diagnostics_noise_intervals.ipynb   (Group A)                                    [TODO]
  R2_sensitivity_ring_screening.ipynb    (Group B1–B4)                                [TODO]
  R3_prior_nitrate_scenarios.ipynb       (Group B5–B6)                                [TODO]
  R4_spatial_crossval.ipynb              (Group C)                                     [TODO]
tests/test_validation.py                                                              [DONE — 8 tests]
```

**Result persistence:** xarray → `.nc`, DataFrame → `.csv`, each with provenance
attrs (reviewer tag, config JSON, TEXAS version, UTC timestamp). Under
`data/revision1/<group>/` (override `TEXAS_REVISION_RESULTS_DIR`).
**`data/revision1/` is gitignored** — result files match the `*.nc`/`*.csv` LFS
filters and LFS is over budget (see Data section). Results are regenerable; only the
*code* is committed.

---

## Reviewer comment → exact TEXAS call

### Group A — reporting from existing posteriors (no refit) — **DONE**

| Row | Reviewer | Analysis | Call |
|---|---|---|---|
| A1 | R2, R3 | MCMC diagnostics (R-hat/ESS/E-BFMI/divergences) | `diagnostics_table([ds…])` → reads `stan_diag_*` attrs via `create_summary_table` (`diagnostics.py:72`) |
| A2 | R3(Krapp) | Noise terms σ²_culmeso (top), ε (bottom) | `summarize_noise_terms(ds)` → `sigma_proxyObs_crtp` (ε), `sigma_proxyObs_cul/_meso` (top obs), `sigma_{t0,k,b,v}_culmeso` (pooling, full-hier only) |
| A3 | R3(Krapp) | R²/RMSE **credible intervals** | `summarize_calibration_metrics(ds)` → per-draw `R2_full`/`bayesR2_full`/`RMSE_full` (Stan gen. quantities: `gen_logi_fixed_hier_crtp_multiv.stan:173-200`, `_univ_priorApprox.stan:51-68`, `_eiv.stan:161-189`) |
| A4 | R3(Krapp) | 95% (not 68%) intervals; "credible" not "confidence" | `credible_interval(da, level=0.95)` |
| A5 | R1, R2 | Forward (Scaled RI) vs inverse (temp) skill **separately** | **new code** — inverse skill not evaluated anywhere (invT models lack R2/RMSE gen. quantities). Score `predict_T_from_proxyObs` `t_est` vs known coretop WOA T |

Current point-estimate R²/RMSE in `plotting/residual_maps.py:728-730,748` (annotation
`:971`) — a single value off median residuals, **no CI**. Group A supersedes it.

**Group A results (2026-07-15, univ_priorApprox_SST):** R²_full 0.746 [0.744, 0.747];
bayesR²_full 0.746 [0.728, 0.762]; RMSE_full 0.058 [scaled-RI units]; ε
`sigma_proxyObs_crtp` 0.0577 [0.0558, 0.0598]; `sigma_proxyObs_cul` 0.0983;
`sigma_proxyObs_meso` 0.0672. Saved under `data/revision1/groupA/`.

### Group B — sensitivity (each variant = one forward refit) — **TODO**

| Row | Reviewer | Knob | Call / location |
|---|---|---|---|
| B1 | R2, R3 | RI₀₋₃ vs RI₀₋₄/RI₀₋₅ | `compute_scaledRI(…, cren_rings=4\|5)` (`predict.py:388`, kw-only `:395`, formula `:450-451`). **Needs forward refit** — cached are `…_cren3`. |
| B2 | R2 | ≥0.75 high-index retention rule | `detect_outliers_manual(exclude_condition=<mask>)` (`screening.py:318`; 0.75 hardcoded `:368-380`; override arg `:322,362`) → refit |
| B3 | R2, R3 | Mahalanobis threshold (0.90) | `MahalanobisOutlierDetector(confidence=…)` (`screening.py:17,34,37`; χ² `:110-119`). **Sweep already exists** as Fig S6 (`SI_code1…:48105,48901,49074`); extend to downstream calibration |
| B4 | R3(Krapp) | Screening/prior robustness; avoid select-and-evaluate | refit under alt screening + report out-of-sample (ties to Group C) |
| B5 | R1, R2, R3 | PETM/Antarctic temperature-**prior** sensitivity | invT-only rerun — vary `prior_mu_t`/`prior_sigma_t` (see below) |
| B6 | R1, R2, R3 | PETM **nitrate-scenario** sensitivity | invT-only — extend `no3 ∈ {10, modern, 0.1, 0.01}` scenarios (see below) |

Rebuild the calibration dict per variant: `build_fwd_data(t_crtp=…, proxy_crtp=<alt RI
column>, …)` (`builder.py:485`) → `get_posterior(data, stan_file, temptype,
proxy_name)` (`sampler.py:139`) → `save_posterior(…, filename_suffix=<variant tag>)`.
B2/B3/B4 only change which rows enter `build_fwd_data`; B1 changes the proxy column.

**B5 prior locations (SI_code3):** PETM per-site prior means `PhanTEX_PETM_df['prior_mu_T']`
at **L31587–31604** (ODP959 38/33 for 6×/3× CO₂ iPETM; SDB 32/28), `prior_sigma_t=10`
hardcoded in the run loop **~L36826**. iPETM climatology loaded **L30648–30660**
(`Zhu19…iPETM{01,03,06,09}x.nc`); PETM-DA **L31282–31285**. Extreme warm/cold
`site_config` **~L40680–40695** (Co1010 Antarctic `prior_mu_t=10`; ODP1259 warm `=40`),
consumed **~L40794** (TEXAS) / **~L40814** (BAYSPAR). GIG/Tasman flat `prior_mu_t=20`
**~L23244–23313**.

**B6 nitrate locations:** `no3_thershold_dict={'thermoT':'1.0'}` only selects the
forward-posterior file (training-side cutoff, fixed `1.0`). Reconstruction-time `'no3'`
predictor is the scenario knob. PETM scenarios **L31587–31604** (`PETM_no3_01`:10→0.1,
`PETM_no3_001`:10→0.01), invT block **~L36825–36853**. GIG scenarios **~L23262–23317**
(`no3 ∈ {10 (off), modern, 0.1, 0.01}`). invT driver:
`predict_T_from_proxyObs(proxyObs, prior_mu_t, prior_sigma_t, fwd_posterior,
predictors={'gdgt23ratio':…, 'no3':…})` (`predict.py:132`; Stan via `stan/invT.py:403`).

### Group C — spatially-blocked cross-validation — **TODO (highest reviewer weight, all new)**

Backs R2/R3's ask to soften/support "outperforms all existing calibrations" with
out-of-sample, spatially-independent skill.

**Built (`validation/crossval.py`, 15 tests total in `test_validation.py`):**
1. **Partition** — `assign_block_folds(lons, lats, block_deg=20, n_folds=5, seed=)`
   deals whole equal-area lon/lat blocks into k folds (pure NumPy, no deps; keeps
   spatial blocks intact so held-out ⟂ training). `assign_ocean_basin_folds` =
   leave-one-basin-out via the same regionmask basins as `residual_maps.py:55`.
   `make_folds(fold_ids, min_test=2)` → leave-one-fold-out `SpatialFold` splits.
2. **Refit + predict** — `crossval_fold(fold, CrossvalArrays, stan_file, temptype,
   proxy_name, culmeso_posterior, R2_thermal, …)` slices train rows →
   `build_fwd_data` → `get_posterior` → `predict_proxy_from_T(return_full=True)`
   on held-out true T. Array-based inputs (no hardcoded column names → aligns w/
   Group D).
3. **Score** — `heldout_scores(observed, predicted_draws, level=0.95)` = per-draw
   R²/RMSE **credible intervals** (out-of-sample analogue of Group A);
   `fold_score_table(...)` → tidy per-fold + POOLED table.
4. **Driver** — `run_spatial_crossval(...)` loops folds with per-fold
   checkpointing (resumable) + persists via `validation.io`.

**Forward held-out skill only** so far (T→proxy — clean per-draw metric). Inverse
(proxy→T) held-out skill is the invT-heavy path (R1/R2 want both, A5): run
`predict_T_from_proxyObs` per held-out site vs each fold's refit posterior → feed
its temperature draws to `heldout_scores`. Left to the batch driver.

**Batch driver DONE** (`scripts/revision1/run_crossval.py`): argparse CLI over
`run_spatial_crossval`, coretop-subset + fold-assign + `CrossvalArrays` build, all
column names overridable (`--*-col`, Group-D-aligned), ASCII-safe output. Defaults
to the light univ_priorApprox model; `--stan-file …_eiv --predictors both
--r2-thermal` opts into the headline multivariate EIV model. **Verified end-to-end**
on synthetic coretop + the real Zenodo culmeso posterior: one fold refit
(compile→sample→predict→score) runs green.

> **⚠ Windows PATH caveat (verified 2026-07-15):** a real Stan compile from the
> `.venv` picks up Strawberry Perl's g++ 13.2.0 and fails at link (`collect2: ld
> returned 1`) **even though `texas-doctor` says READY**. Prepend RTools40 first:
> `export PATH="~/.cmdstan/RTools40/mingw64/bin:~/.cmdstan/RTools40/usr/bin:$PATH"`.
> Applies to the eventual full CV run and any Group B/C refit from this venv.

**Still TODO:** run the real CV once the coretop CSV is un-LFS'd/on Zenodo
(`ds_gridded_screened_global_compilation_finalized.csv` is still a pointer);
inverse (proxy→T) held-out skill; `notebooks/revision1/R4_spatial_crossval.ipynb`
(reviewer-facing figure).

### Group D — API usability: variable-name-agnostic functions — **TODO**

Author requirement, and it answers **R1's** major usability comment ("what data / what
layout is required to use this model"). Public functions must not assume DataFrame
column names — users hit `KeyError` for `scaledRI_cren3` (and `TEX86`, `gdgt23ratio`,
`no3`) when applying TEXAS to differently-named data.

**Approach:** accept explicit column-name params (`proxy_col=`, `tex86_col=`, …) or
arrays/Series directly, instead of indexing hardcoded literals. `compute_scaledRI` and
the top-level `predict_*` already take arrays — gaps are mostly in screening, builders,
and posterior-name/suffix plumbing.

Hardcoded-name sites (2026-07-15 grep for `scaledRI_cren3`/`TEX86`/`no3`/`gdgt23ratio`):
`data/screening.py`, `data/builder.py`, `predict.py`, `stan/sampler.py`, `stan/io.py`,
`stan/invT.py`, `plotting/residual_maps.py`. Add regression tests with a
deliberately-renamed input DataFrame.

### Text-only (no rerun — do NOT scope into the analysis workflow)
PSM framing (R2), "correction"→"conditional" wording (R2), Ishii/Bijl citations (R1),
streamline Sections 4–6 to SI (R3), abbreviation definitions (R3), title wording (R2).

---

## Data dependencies (⚠ Git LFS is over budget)

**GitHub LFS for this repo is over quota** — `git lfs pull` fails
("exceeded its LFS budget"). LFS files are present only as 133-byte pointers. Get data
from **Zenodo** instead (record via `utils/download.py`).

| Need | Source | Command |
|---|---|---|
| Forward posteriors (Group A, B refit priors, B5/B6 fwd) | Zenodo ✅ | `TEXAS.download_posteriors()` |
| Training CSVs + CMEMS NO₃ (Group B/C refits) | Zenodo ✅ | `TEXAS.download_training_data()` |
| iPETM/PETM-DA climatology, paleo spreadsheets (`data/spreadsheets/published_data/`: PhanSST/PhanTEX/GIG), invT cache | **LFS-only, NOT on Zenodo** ❌ | needs LFS budget restored **or** files provided → **blocks B5/B6 + PETM/Antarctic figures** |
| SI_code1 coretop CSV (`ds01_updated_global_coretop_tex_revised_011226.csv`, `SI1:8055`), WOA23 | OneDrive / NOAA (manual) | not needed unless re-running preprocessing |

Zenodo posteriors confirmed downloaded 2026-07-15: `…_culmeso_cultureT`,
`…_hier_crtp_univ_priorApprox_{SST,thermoT}`, `…_hier_crtp_multiv_priorApprox_eiv_{SST,thermoT}`
(EIV ~78 MB each, 1513 coretop sites w/ per-site latent vars).

---

## Compute notes

- CmdStan **works on this Windows machine** (fixed 2026-07-15): CmdStan 2.36.0 at
  `~/.cmdstan/cmdstan-2.36.0`; RTools40 toolchain at `~/.cmdstan/RTools40` (g++ 8.3.0;
  `mingw32-make` supplied via pacman + a manual copy of `usr/bin/make.exe`). `texas-doctor`
  → `Stan sampling: READY`. cmdstanpy auto-adds RTools to PATH at compile time.
- **culmeso** forward fit: fast (N=55 culture + 8 mesocosm), 4 chains × (1000 warmup +
  1000 sampling).
- **coretop EIV multivariate**: heavy (~1513 sites, per-site latent NO₃/G₂₃ vars) — was
  pre-cached, not run in-notebook. Group B (RI×3, retention×2, threshold-grid) and Group C
  (k folds) refit this model → **hours-scale**. Run via `scripts/revision1/` batch jobs
  with per-variant checkpointing, not in a notebook.

---

## Status (2026-07-15)

- ✅ **Group A** built, tested (8 passing, synthetic data), ruff-clean, run against real
  Zenodo posteriors; results in `data/revision1/groupA/`.
- ✅ **Group C core** (`validation/crossval.py`) built + tested — 15 tests total pass in
  `test_validation.py` (7 new: block folds, LOO splits, held-out CI scoring, table).
  Pure fold-assignment + scoring covered; Stan orchestrator (`crossval_fold` /
  `run_spatial_crossval`) is thin, lazily-imported, checkpointed. Forward held-out skill
  only; inverse held-out is the invT-heavy TODO.
- ✅ Fixed `utils/download.py` Windows cp1252 crash (non-ASCII in `print`).
- ⏭ **Next for Group C:** `scripts/revision1/run_crossval.py` batch driver + `R4` notebook
  (needs Zenodo coretop CSV + culmeso posterior; hours-scale refits).
- ⏭ Then Group B refits, then B5/B6 (blocked on LFS/Zenodo data gap above).
- ⏭ **Group D** (variable-name-agnostic API) is independent of Stan/data — can be done
  anytime, in parallel, and unblocks the user's use of TEXAS on other datasets.

**Open question for the author:** Krapp's "σ²_culmeso" — *observation* noise
(`sigma_proxyObs_cul/_meso`) or *hierarchical pooling* variance (`sigma_{t0,k,b,v}_culmeso`)?
The priorApprox posteriors contain only the former; the module reports whatever is present
and labels it (`kind` coord). Confirm intent before wording the manuscript.
