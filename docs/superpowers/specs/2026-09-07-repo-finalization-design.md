# Repo finalization for the public `PaleoLipidRR/TEXAS` — design

**Date:** 2026-09-07 · **Status:** design approved in chat, awaiting spec review
**Scope:** the single public repo that ships `texas-psm` and reproduces the revised manuscript.
**Out of scope:** `AGU_PALO_TEXAS_PSM_draft`, `AGU_PALO_TEXAS_PSM_revised_submission`,
`working-repo/TEXAS-revision`, `data/cache/**`, git history rewriting, the v1.0.0 Zenodo upload.

## 1. Decisions already made (2026-09-07, in chat)

| decision | choice |
|---|---|
| Repo shape | **One repo, tidied.** Package and paper material stay together; matches the 2026-08-14 Phase B decision in RESUME.md. |
| Tracked data | **Untrack what nothing reads, keep what a notebook or test opens.** Files stay on disk. |
| Layout | **Sort in place.** `notebooks/`, `figures/`, `data/`, `scripts/` keep their names; only strays move. No notebook cell path changes. |
| Unmerged branches | **Tag, then delete.** |
| Derived NetCDFs under `data/external` | **Untrack now**, add to the v1.0.0 Zenodo data record later. |

Remote state at design time: local `main` == `origin/main` (`41ba78e8`), 0 ahead / 0 behind.
Tag `v0.2.6` exists locally only. No stashes. Working tree has two dirty SI notebooks and
three untracked CSVs (handled in §8).

## 2. The rule

The top level is the package. Paper material lives in the folders the notebooks already
expect. Anything superseded by the revision goes under `archive/`. Anything third-party or
regenerable leaves git and is pointed to from a README.

## 3. Target layout

```
TEXAS/
  README.md  CITATION.cff  LICENSE  CONTRIBUTING.md
  pyproject.toml  environment.yml  conda-lock.yml  conda-{linux-64,osx-64,osx-arm64,win-64}.lock  uv.lock
  run.sh  .zenodo.json  .gitignore  .gitattributes  .dockerignore  .pre-commit-config.yaml
  CLAUDE.md  RESUME.md              tracked, export-ignored (unchanged)
  .claude/  .github/  .devcontainer/
  src/TEXAS/                        package; stan_models/ holds the 9 shipped models ONLY
  tests/  docs/  docker/  streamlit_app/
  notebooks/
    quickstart_demo.ipynb  quickstart_extended.ipynb
    manuscripts/                    SI_code00, 01, 02, 02a, 03 (+ miscellaneous/)
    reviewer_response/              README, SI_code04
  figures/manuscript/
    README.md  finalized/{main-text,supplementary}/  revision1/  sources/
  data/
    README.md                       gains a "where every file lives" table
    revision1/                      unchanged
    spreadsheets/                   only the files a notebook or test reads (§5)
    raw/  external/                 present on disk, ignored by git
  scripts/
    bump_version.sh  push_docker.sh  zenodo_upload.py  zenodo_fix_draft_metadata.py
    make_bundled_posteriors.py  build_calibration_domain.py  prepare_resubmission_archive.py
    migrate_cache_layout.py  rename_cache_files.py  normalize_posterior_attrs.py  flatten_cache.py
    paper/                          the 10 analysis drivers (§4)
  archive/
    README.md                       index of the three sub-archives
    submission-2026-04/             stan_models/ (existing 8) notebooks/ figures/
    pre-submission/stan_models/     the 20 models from src/.../archive{,_pre_annotated}
    presentations/                  IMOG_presentation.ipynb
    exploratory/gridT-inversion/    TEXAS-revision/ (gridT explainer; NOT in the resubmission)
```

## 4. Moves (all `git mv`, history preserved)

| from | to | note |
|---|---|---|
| `src/TEXAS/stan_models/archive/` (15 .stan + README) | `archive/pre-submission/stan_models/` | closes the open B1 bullet |
| `src/TEXAS/stan_models/archive_pre_annotated/` (4) | `archive/pre-submission/stan_models/pre_annotated/` | keeps the two same-named files apart |
| `notebooks/superseded/{README.md, SI_code2_*.ipynb, SI_code3_*.ipynb}` | `archive/submission-2026-04/notebooks/` | Phase B2 |
| `figures/manuscript/superseded/` (31 files) | `archive/submission-2026-04/figures/` | Phase B3 |
| `figures/manuscript/existing_calibrations_with_DeltaT_Tres_ranges.pdf` | `archive/submission-2026-04/figures/` | stray fig1 parent |
| `TEXAS-revision/` (html, 2 md, 6 png) | `archive/exploratory/gridT-inversion/` | user 2026-09-07: gridT is **not** going into the resubmission, so it is provenance, not reviewer evidence |
| `notebooks/current/IMOG_presentation.ipynb` | `archive/presentations/` | `notebooks/current/` disappears |
| `scripts/{run_manuscript_refits, run_coretop_maps, run_param_sensitivity, fit_t0shift_single_predictors, invt_M_paleo_check, plot_uncertainty_calibration, build_diagnostics_table, build_parameter_table, add_retained_flag, backfill_iter_warmup}.py` | `scripts/paper/` | `scripts/` keeps release + cache tooling |

Not moved: `figures/manuscript/sources/` (editable SVGs of finalized figures),
`data/revision1/`, `notebooks/manuscripts/miscellaneous/` (bib tooling used for the SI).

Things that reference moved paths and must be updated in the same commit:
`StanCompiler.resolve_stan_path()` archive-stem fallback (`stan/compiler.py`),
`tests/test_stan_model_archive.py`, `tests/test_streamlit_params.py` (archive glob),
`tests/test_param_sensitivity_config.py:25` (loads `scripts/run_param_sensitivity.py` by
path via `importlib` — must become `scripts/paper/`), `.claude/agents/{figure-sync,pre-commit}.md`,
`.claude/skills/notebook-sync/SKILL.md`, `data/revision1/groupA/{reviewer_response/REVIEWER_MAP.md,
model_comparison_cv/PROVENANCE.md}`, `archive/submission-2026-04/stan_models/README.md`
(banner in the old src README moves with it), `README.md` layout block, `CLAUDE.md`
archive paragraph, `docs/preprint_additive_archive.md`, `.zenodo.json` ("ships 20 Stan
models" → 9). The kriged-cache changes of §5b touch `utils/paths.py`, `plotting/residual_maps.py`,
`plotting/__init__.py`, SI_code02 cell 89, CLAUDE.md and two docs pages.

## 5. Data: what stays tracked, what leaves

Method: every tracked file under `data/spreadsheets`, `data/raw`, `data/external` was
grepped by basename (preceded by `/` or a quote) across `notebooks/`, `src/`, `tests/`,
`scripts/`, `streamlit_app/`, `docs/`, `README.md`. Full lists in Appendix A.

| set | files | MB | action |
|---|---|---|---|
| `data/spreadsheets` referenced | 22 | 55 | stay (LFS) |
| `data/spreadsheets` + `data/raw` unreferenced (+ the duplicate pkl) | 56 | ~112 | `git rm --cached`, listed in `data/README.md` with source |
| `data/external` third-party originals (26 unreferenced + 9 referenced) | 35 | ~266 | `git rm --cached`; README already says download separately |
| `data/external` TEXAS-derived, read by SI_code00/03 | 6 | ~33 | `git rm --cached` now; upload to Zenodo data record at v1.0.0; add to `TRAINING_DATA_REGISTRY` |
| `data/revision1/` | 45 | 1.2 | unchanged |

The 6 derived files: `ds06_calculated_ocean_properties.nc` (already served from the GRL
record via `TRAINING_DATA_REGISTRY["ocean_prop_ds"]`, so it needs no upload),
`Tierney22_PNAS_PETMDA/PETMDA_OCN_annual_regridded.nc`, and the four
`Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/*.nc`. **Five files (16 MB) need the
v1.0.0 upload.** `ds04_gridded_coretop_tex_scaledRI.nc` and
`calculated_ocean_properties_seasonal.nc` are read only by the ignored
`notebooks/exploration/`, so they are dropped without an upload.

Duplicates resolved (keep the path a finalized notebook reads, untrack the other):

| keep | untrack |
|---|---|
| `data/spreadsheets/ols_tex_thermoT_thisStudy.pkl` (SI_code03 cell 18 builds `{repo}/data/spreadsheets/` + basename) | `data/spreadsheets/fitted_models/ols_tex_thermoT_thisStudy.pkl` |
| `data/external/ncfiles/Tierney22_PNAS_PETMDA/PETMDA_OCN_annual.nc` (third-party, untracked either way) | `data/external/ncfiles/PETMDA_OCN_annual.nc` |
| `data/external/ncfiles/ds06_calculated_ocean_properties.nc` | `calculated_ocean_properties.nc`, `calculated_ocean_properties_seasonal.nc` |

`data/README.md` gains one table per set: filename, what reads it, where to get it (Zenodo
data record `10.5281/zenodo.22131367`, GRL record, NOAA WOA23, GISTEMP, PhanSST, PANGAEA,
Scotese & Wright 2018, Müller 2019 plate model, "author-only, not needed by any notebook").

## 5b. Kriged-grid cache gets its own folder (user request 2026-09-07)

**State today.** `plot_residual_maps()` (`src/TEXAS/plotting/residual_maps.py:785-788`)
auto-builds its cache path as `CACHE_DIR / "kriged_grids_{krige_res}deg_{dist}dmax_woa23_{tag}.npz"`,
i.e. the **cache root**, next to the two posterior cache folders. The root now holds 20
`.npz` files of three generations plus two strays:

| files | MB | status |
|---|---|---|
| `kriged_grids_1deg_10dmax_woa23_{SST,t_sf2tc_avg}_scaledRI_cren3_temp_residual.npz` (Jul 28, Aug 15) | 95 | **live** — read by SI_code02 cells 81 and 87 (fig8, figS14) |
| `kriged_grids_1.0deg_…` (Apr 16) | 57 | superseded generation; bytes differ from the `1deg` file. The name differs only because `krige_res` was passed as `1.0` then and `1` now — the f-string has no numeric normalisation |
| `kriged_grids_2.5deg_…` (2 files, Apr) | 90 | superseded; the 2.5° cells in SI_code02 are commented out |
| `kriged_halo_*.npz` (13 files, Mar–Apr) | 38 | orphaned: written by `load_or_build_halo_cache`, which is exported from `plotting/__init__.py` and called by nothing |
| `data_list_extreme_example.pkl` (May 4) | 0.1 | SI_code03 reads a file of this name from `notebooks/manuscripts/` per CLAUDE.md; check the path it uses, then delete this copy if it is not that path |
| `rebuttal_boundedT/run.log` | 0 | stray |

SI_code02 cell 89 (fig9, uncertainty maps) passes `residual_tag='uncertainty'` but no
`temp_param`/`y_param`, so it never gets an auto cache path and re-kriges on every run.

**Design.**

1. `utils/paths.py`: add `KRIGED_CACHE_DIR = CACHE_ROOT / "TEXAS_kriged_grids_cache"`
   beside the two posterior dirs; `set_cache_dir()` sets it too; the module docstring and
   `TEXAS_CACHE_DIR` docs say "three subdirectories".
2. `residual_maps.py`: build the auto path under `KRIGED_CACHE_DIR`, `mkdir(parents=True,
   exist_ok=True)` before saving, and format the resolution with `f"{krige_res:g}"` so
   `1`, `1.0` → `1deg` and `2.5` → `2.5deg` (one name per grid). **Dual-read fallback**:
   when the new path is missing but the same leaf exists in the legacy cache root, load it
   and print one line saying where it was found — the same policy `load_posterior()` uses,
   so the Windows box keeps working before its files are moved.
3. Delete `load_or_build_halo_cache` and `krige_halo_all`'s halo-only cache format from
   the public API (`plotting/__init__.py`): zero callers, superseded file format. Keep
   `krige_halo_all` itself, which `load_or_build_grids_cache` still uses.
4. SI_code02 cell 89: pass `temp_param="SST", y_param="scaledRI_cren3"` so the fig9
   uncertainty grid caches like the other two (`…_SST_scaledRI_cren3_uncertainty.npz`).
5. Tests (`tests/test_kriged_cache.py`, new): `set_cache_dir` repoints `KRIGED_CACHE_DIR`;
   the auto filename is identical for `krige_res=1` and `1.0`; the legacy-root fallback
   loads and the new path is used for writes. No kriging in tests — patch the grid builder.
6. Per-machine migration (local, `data/cache/` is ignored): move the two live `1deg`
   files into `TEXAS_kriged_grids_cache/`; delete the `1.0deg` and `2.5deg` grids, the 13
   halo files and `rebuttal_boundedT/` (regenerable with `recompute='auto'`, ~185 MB
   freed). Add this to the RESUME.md "does not travel" table so it is repeated on Windows.
7. CLAUDE.md "Posterior caching" gains the third folder; `docs/model_validation.md:69`
   and `docs/troubleshooting.md` name it where they describe the cache.

## 6. `.gitignore`, `.gitattributes`, `.dockerignore`

### 6.1 `.gitignore` — rewritten from scratch

Principles: one section per concern with a one-line rule; every negation lists the exact
files it re-includes; no trailing comments on pattern lines (git treats `figures/   # …` as
a literal path, which is why the current line is a silent no-op).

```gitignore
# ── Python / tooling ──────────────────────────────────────────────────────────
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
build/
dist/
.venv/
venv/
env/
.env
.coverage
.pytest_cache/
.mypy_cache/
.ruff_cache/

# ── Editors / OS ──────────────────────────────────────────────────────────────
.vscode/
.idea/
.DS_Store
Thumbs.db
*.tmp
*.log
*.Rhistory
=*
*safeBackup*

# ── Claude Code: machine-local settings only (agents/ and skills/ are tracked) ──
.claude/settings.json
.claude/settings.local.json
.superpowers/
docs/superpowers/

# ── Jupyter ───────────────────────────────────────────────────────────────────
.ipynb_checkpoints/
notebooks/exploration/
notebooks/dask-worker-space/
notebooks/manuscripts/regrid_weights_*.nc
notebooks/manuscripts/*.pkl
notebooks/manuscripts/*.png
notebooks/*.csv

# ── Compiled Stan binaries (CmdStan writes them next to the .stan source) ─────
src/TEXAS/stan_models/*
!src/TEXAS/stan_models/*.stan
!src/TEXAS/stan_models/README.md

# ── Model caches: never tracked, hydrated by download_posteriors() ────────────
data/cache/
**/posterior_cache/
**/invT_posterior_cache/

# ── Data: ignored by default, then re-included file by file ───────────────────
# Rule: a data file is tracked only if a notebook, test, script or the package
# opens it. Everything else is listed with its source in data/README.md.
data/external/
data/raw/
data/spreadsheets/*
!data/spreadsheets/published_data/
data/spreadsheets/published_data/*
!data/spreadsheets/published_data/NICOPP_d15Nsed_database/
data/spreadsheets/published_data/NICOPP_d15Nsed_database/*
!data/spreadsheets/fitted_models/
data/spreadsheets/fitted_models/*
# (one `!data/spreadsheets/<file>` line per kept file — generated from Appendix A)
# Revision-1 reviewer evidence: small, hand-curated, tracked in full
!data/revision1/
data/revision1/**/.run.lock

# ── Figures: finalized + revision1 + sources tracked; scratch renders not ─────
figures/manuscript/**/*.csv
!figures/manuscript/revision1/*.csv
html_figures/
outputs/
logs/
site/

# ── Manuscript text lives in its own repos ────────────────────────────────────
/manuscript/

# ── Release staging (never commit) ────────────────────────────────────────────
review_archive_v*/
texas-psm-zenodo-v*
docs/_build/
tutorial/_build/

# ── Streamlit ─────────────────────────────────────────────────────────────────
.streamlit/
```

Mechanics that make this work: `git rm --cached` first for every file in Appendix A's
"untrack" lists, then rewrite `.gitignore`, then `git ls-files -i -c --exclude-standard`
must print nothing. The `data/spreadsheets/*` + `!file` pattern is used instead of
`data/spreadsheets/` because git cannot re-include a file whose parent directory is
excluded.

The `*.csv`/`*.xlsx` global rules are dropped: they were only ever there to ignore data,
and data is now handled by directory. `.gitattributes` still routes `*.csv`/`*.xlsx` through
LFS, so a newly kept CSV lands in LFS automatically.

### 6.2 `.gitattributes`

Unchanged, except add `/archive/pre-submission/ export-ignore`? **No** — the archive is
part of the reproducibility record and belongs in the Zenodo software tarball. No change.

### 6.3 `.dockerignore`

Delete the "PHYLOGENOMICS EXCLUSIONS" block (pasted from another project; names
`data/phylo/`, GTDB releases, FASTA/MSA files that do not exist here). Keep the rest, add
`archive/`, `docs/_build/`, `review_archive_v*/`, `texas-psm-zenodo-v*`, `.venv/`.

## 7. Branches

Six unmerged remote branches and one local backup. For each: `git tag archived-branch/<name> <tip>`,
push the tag, then delete the branch (remote and, where present, local).

| branch | ahead of main | tag |
|---|---|---|
| `origin/claude/bounded-t-model-revisions-idrogu` | 1 | `archived-branch/claude-bounded-t-model-revisions` |
| `origin/claude/gridT-gui-exploratory` | 12 | `archived-branch/claude-gridT-gui-exploratory` |
| `origin/claude/gridt-inversion-characterization-15i183` | 2 | `archived-branch/claude-gridt-inversion-characterization` |
| `origin/claude/repo-audit-docs-update-od2dsj` | 3 | `archived-branch/claude-repo-audit-docs-update` |
| `origin/claude/version-bump-v0-3-1-pxkvas` | 1 | `archived-branch/claude-version-bump-v0-3-1` |
| `origin/revision/boundedT-si-figures` (+ local) | 4 | `archived-branch/revision-boundedT-si-figures` |
| local `backup/revision1-groupA-prerebase` | — | `archived-branch/backup-revision1-groupA-prerebase` |

`gh-pages` is the docs deploy target and stays. Local-only tag `v0.2.6`: **do not push it** —
`.github/workflows/docker.yml` fires on every `v*` tag and would publish a GHCR image for a
version that was never released. Delete the local tag (`git tag -d v0.2.6`); its commit is on `main`.

## 8. Working tree at start

- `notebooks/manuscripts/SI_code00_PreProcessing.ipynb` and `SI_code02_*.ipynb` are dirty.
  The diff is kernel metadata (`3.13.5` → `3.12.8`) plus, in SI_code00, a recorded
  `ModuleNotFoundError: sklearn` from running in a venv without the dev extra. **Discard
  both with `git checkout --`**; no analysis changed.
- `data/revision1/groupA/manuscript_refit/coretop_maps_boundedT_{manifest,sites}.csv` and
  `superseded_constant_prior/coretop_maps_boundedT_manifest.csv` are byte-identical to
  their `t0shift`/arm-independent twins (verified with `cmp`). Delete.
- Local ignored junk to delete: `texas-psm-zenodo-v0.1.5.zip` (326 MB), `review_archive_v0.2.0/`,
  `dist/`, `outputs/`, `notebooks/exploration/`, `notebooks/manuscripts/.ipynb_checkpoints/`,
  `notebooks/manuscripts/posterior_check.png`, `notebooks/texas_results.csv`,
  `src/TEXAS/stan_models/.Rhistory`, the 11 compiled Stan binaries in `stan_models/`
  (regenerated on next use), `.git/objects/73/tmp_obj_Y0smuy` via `git gc`.

## 9. Dependency audit

Method: AST import extraction over `src/TEXAS/**/*.py`, `streamlit_app/**/*.py`, the five
finalized SI notebooks, SI_code04, both quickstarts and the tutorial notebook; mapped to
distribution names; compared against `pyproject.toml`, `environment.yml`, `uv.lock` (238
packages) and `conda-lock.yml` (1802 entries). Static analysis: a name used only inside a
string, an `eval`, or a `%magic` line is reported as unused.

### 9.1 Coverage — every real import resolves in both lockfiles today

Every third-party module imported anywhere is present in `uv.lock` and `conda-lock.yml`,
so no notebook is unrunnable from the locks. The problems are declaration-side.

### 9.2 `pyproject.toml` findings

| finding | evidence | change |
|---|---|---|
| **`scikit-learn` imported by the package but only in the `dev` extra** | `plotting/residual_maps.py:775` (`r2_score`, inside the maps path) and `data/screening.py:1062` (`PCA` in `plot_pca_projection`), both inside functions, neither guarded | replace `r2_score` with a 3-line numpy R²; wrap the PCA import in `try/except ImportError` with a message naming `scikit-learn`. No new core dep. |
| `joblib` used in `residual_maps.py:73` (guarded) but undeclared | comes transitively with scikit-learn, which `maps` does not declare | add `joblib` to `maps` |
| `cmocean` is a **core** dep but the package never imports it | only SI_code00 uses it (SI_code02/03 import it unused) | move to `plotting` extra |
| `plotly` is a **core** dep but the package never imports it | used by `streamlit_app/` (which has its own `requirements.streamlit.txt` listing plotly) and imported-unused in SI_code02/03 | drop from core |
| `dev` extra lists `anywidget`, `ipylab`, `duckdb`, `sqlalchemy`, `pydantic` | referenced nowhere in the repo | remove |
| `dev` extra lists `statsmodels`, `odrpack` | imported only in SI_code00, and never called there (`sm`, `odr_fit`); user confirmed 2026-09-07 the odrpack import was unintentional | remove the imports and the deps; drop `odrpack` from `docs/_config.yml` `autodoc_mock_imports` too |
| `regrid` extra lists `geopandas`, `geopy`, `gsw`, `rtree`, `pyogrio`, `mapclassify`, `pyproj<3.6`, `shapely`, `cartopy` | `utils/regrid.py` imports only `xesmf` (+ `esmpy` at runtime); `geopandas`/`geopy` are imported-unused in the notebooks; `shapely`/`cartopy` already come via `maps` | `regrid = ["xesmf"]`; drop the `pyproj<3.6` pin **and** `[tool.uv] override-dependencies = ["pyproj>=3.6.1"]`, which exists only to undo that pin (see memory: py3.12 has no pyproj<3.6 wheel) |
| `pyarrow`, `openpyxl` in `dev` | needed implicitly by `pd.read_parquet` (`PhanTEX_GIG_df.parquet`, SI_code02) and `pd.read_excel` | keep, with comments |
| `requests` imported in SI_code00/02/03 | never used in any of them; not declared anywhere | remove the imports; declare nothing |
| `IPython` used in SI_code00/02/03 (`display`) | undeclared but provided by `ipykernel` | no change |
| `psutil` core, `utils/system_info.py:12` unguarded top-level import | correct as core; absent from `environment.yml`'s explicit list (arrives via pip `texas-psm`) | add explicitly to `environment.yml` |

### 9.3 `environment.yml` findings

Remove (imported by nothing, not a runtime lib of anything kept): `dask`, `distributed`,
`zarr`, `cftime`, `gsw`, `geopandas`, `geopy`, `pyogrio`, `mapclassify`, `rtree`, `pyshp`,
`pyproj` (cartopy pulls its own), `statsmodels`, pip `odrpack`, `importlib-metadata<5.0`
(the backport is unnecessary on Python ≥3.8; `__version__` uses the stdlib module).
Keep `esmf`, `hdf5`, `libnetcdf` (native libs behind xesmf/netCDF4), `setuptools<81`
(reason not recorded — leave, note it), `matplotlib-inline` (harmless). Add `psutil`.
`plotly` stays only if the Streamlit app is meant to run from this env; otherwise remove.

### 9.4 Unused imports per finalized notebook — **removed by the plan, not left to the author**

Decision 2026-09-07: the implementation plan edits the import cells of every notebook in
the table below, removing each module and name listed, and replacing `from TEXAS import *`
with an explicit import list of the names the notebook actually uses. Edits are made with
`nbformat` on the source of the import cells only; executed outputs are left untouched
(they are a record of what ran). Verification per notebook: (a) `ruff check --select F401`
on the code cells exported with `jupyter nbconvert --to script`, which must report zero
unused imports; (b) the import cells execute cleanly in the regenerated environment
(`nbconvert --execute` on a copy with every non-import cell removed); (c) every name used
anywhere in the notebook's code cells is defined or imported — checked with `pyflakes`
on the exported script, filtering to undefined-name errors.

| notebook | entire module imported, never used | names imported, never used |
|---|---|---|
| `SI_code00_PreProcessing` | `geopandas as gpd`, `odrpack.odr_fit`, `statsmodels as sm`, `geopy` (Distance, distance, lonlat), `requests`, `tqdm`, `string`, `io`, `time` | numpy: `LinAlgError, inv, pinv`; scipy: `chi2, mahalanobis, pearsonr`; sklearn: `BallTree, HuberRegressor, RANSACRegressor, TheilSenRegressor`; matplotlib: `Patch, colors`; shapely: `Polygon`; TEXAS: `StanCompiler, StanSampler, load_posterior, save_posterior, predict_sst_from_tex86, predict_tex86_from_sst` |
| `SI_code01_t0shift_variance_partitioning` | — | scipy: `spearmanr` |
| `SI_code02_t0shift_TEXAS_analysis` | `pykrige.OrdinaryKriging`, `cmocean as cmo`, `seaborn as sns`, `plotly` (go, px, make_subplots), `ipywidgets` (FloatRangeSlider, VBox), `geopy`, `bayspline as bsl`, `functools.partial`, `requests`, `string`, `io`, `time` | scipy: `curve_fit, gaussian_kde, pearsonr, spearmanr, stats, truncnorm`; sklearn: `HuberRegressor, RANSACRegressor, TheilSenRegressor, resample`; matplotlib: `Circle, Line2D, mpatches, plt`; shapely: `Polygon`; IPython: `display`; cmdstanpy: `CmdStanModel`; TEXAS: `MahalanobisOutlierDetector, StanCompiler, StanSampler, build_invT_inputData, predict_T_from_proxyObs, predict_proxy_from_T` |
| `SI_code02a_model_param_sensitivity_test` | `os`, `math`, `dataclasses.dataclass` | numpy as `_np`; matplotlib: `TwoSlopeNorm`; TEXAS: `StanSampler, auto_detect_predictors, generalized_logistic_fixed_upper_multivariate` |
| `SI_code03_paleo_showcases` | sklearn (`HuberRegressor, LinearRegression, RANSACRegressor, TheilSenRegressor`), `cmocean as cmo`, `ipywidgets`, `geopy`, `requests`, `tqdm`, `string`, `io`, `time`, `importlib`, `functools.partial` | scipy: `curve_fit, pearsonr, spearmanr, truncnorm`; matplotlib: `Circle, Line2D, Rectangle, colors`; plotly: `go, make_subplots`; cmdstanpy: `CmdStanModel`; TEXAS: `CONSTRAINT_CODES, KIND_CODES, StanCompiler, StanSampler, generate_ensemble_auto, get_posterior, predict_proxy_from_T, regrid_curvilinear_to_latlon, save_posterior` |
| `SI_code04_model_comparison_cv` | — | — |
| `quickstart_demo` | — | — |
| `quickstart_extended` | `os`, `xarray as xr`, `ultraplot as plot`, `scipy.interpolate.interp1d` | — |

Also seen: `from TEXAS import *` in SI_code00/02/03 (masks what is really used; replace with
explicit imports), and the SI_code00 outputs record absolute `/home/rrattan/...` paths, which
is output text only, not code.

### 9.5 Lockfile regeneration (after 9.2 + 9.3 land)

```bash
uv lock                                             # → uv.lock
conda-lock -f environment.yml --lockfile conda-lock.yml \
  -p linux-64 -p osx-64 -p osx-arm64 -p win-64      # → conda-lock.yml
conda-lock render -p linux-64 -p osx-64 -p osx-arm64 -p win-64   # → conda-*.lock
docker compose -f docker/docker-compose.yml build   # Dockerfile installs from conda-lock.yml
```

### 9.6 `src/TEXAS` audit — unused helpers and documentation (user request 2026-09-07)

Method: AST scan of all 221 functions, classes and methods defined under `src/TEXAS/`;
word-boundary reference counts across `src/`, `tests/`, `scripts/`, `streamlit_app/`,
every notebook's code cells, and `docs/` + `README.md` + `CLAUDE.md`; each hit below
re-checked with a repo-wide `grep -w`. The package is clean apart from seven names.

**Unused — delete (7).** None has a caller anywhere; the only mentions are their own
`__all__` / `__init__` re-export lines.

| name | where | note |
|---|---|---|
| `default_version()` | `utils/naming.py:224` | RESUME.md line 1749 already lists it for removal |
| `describe_compset()` | `utils/naming.py:308` | 5 lines; `CaseName.describe` covers the need |
| `generalized_logistic()` | `models/logistics.py:78` | free-upper-asymptote curve; every shipped model is `_fixed_`, the free models are in `archive/pre-submission/`. Public top-level export — pre-1.0, so removing is allowed; mention in the changelog |
| `compute_density_based_range()` | `plotting/range_utils.py:14` | also undocumented |
| `load_or_build_halo_cache()` | `plotting/residual_maps.py:294` | see §5b |
| `get_repo_root()` | `utils/paths.py:111` | re-exported from both `stan/__init__` and `utils/__init__`, called by nothing; drop both re-exports |
| `save_system_summary()` | `utils/system_info.py:246` | keep `get_system_summary` / `print_system_summary`, which are used |

No private (`_name`) helper is unreferenced, and no method is.

**Documentation — bring the public API to one standard.** Google-style docstring:
one-line summary, `Args`, `Returns`, `Raises` where relevant, one short example only if
the call shape is not obvious. Target 5–25 lines; anything longer belongs in a `docs/`
explainer that the docstring links to.

| defect | count | items |
|---|---|---|
| no docstring on a public function | 4 (after deletions) | `range_utils.py`: `compute_sample_range`, `compute_suffix_specific_range`, `compute_dataset_specific_range`; `naming.py`: `CaseName.describe` |
| one- or two-line docstring on a >25-line function/class | 10 | `diagnostics.summarize_sampler_diagnostics`, `ensemble.detection.detect_model_and_params`, `ensemble.generator.generate_ensemble`, `models.calibration.CalibrationRegistry`, `stan.sampler.StanSampler`, `stan.sampler.auto_detect_predictors`, `utils.naming.legacy_invT_name`, `utils.system_info.{get_container_info, print_summary, get_system_info}` |
| docstring longer than 60 lines | 5 | `predict.predict_T_from_proxyObs` (177 lines), `models.multivariate.find_optimal_no3_threshold` (74), `..._nointercept` (69), `models.multivariate.inverse_generalized_logistic_fixed_upper_multivariate` (66), `stan.sampler.get_posterior` (67) — trim to ≤ 40 lines; move the narrative into `docs/PSM.md` / `docs/marginalization_explainer.md` and link |

Guard so it stays this way: `tests/test_public_api_docs.py` asserts every name in the
top-level `TEXAS.__all__` resolves, is referenced by at least one test or notebook, and has
a docstring of ≥ 3 lines; plus a `ruff` `D1xx` (missing-docstring) selection scoped to
`src/TEXAS`, with `D105`/`D107` (magic methods, `__init__`) ignored.

Noted, not acted on: five modules exceed 800 lines (`data/screening.py` 1241,
`plotting/residual_maps.py` 1214, `utils/naming.py` 888, `data/builder.py` 855,
`plotting/prior_plot.py` 764). Splitting them is a separate decision.

### 9.7 Wrapper layers in the inverse path (user request 2026-09-07)

The inverse reconstruction is four functions deep:

| layer | function | what it adds | callers outside the chain |
|---|---|---|---|
| 1 | `predict.predict_T_from_proxyObs` | default calibration, NO₃ lookup, predictor shorthands, warnings, quality flags | every notebook, the app, 5 scripts, 3 tests |
| 2 | `stan.invT.predict_temperature_from_proxyObs` | **only** re-shapes layer 3's Dataset into a `p1…p99` dict and optionally writes a `.npz` | `tests/test_invt_save.py`, `scripts/{invt_M_paleo_check,run_param_sensitivity}.py`, `streamlit_app/debug_imports.py` |
| 3 | `stan.invT.get_invT_posterior` | builds Stan data, samples, reduces to quantiles, attaches metadata, saves `.nc` | both quickstarts |
| 4 | `stan.sampler.sampler_invT_posterior` | the raw Stan run | SI_code03 |

Layer 2 is the pre-`predict.py` public entry point (its own docstring still calls it the
"high-level wrapper"); since `predict.py` arrived it has been a pass-through with 27
parameters copied by hand. **Decision: fold it.** Its percentile reduction becomes a
private `_percentiles_from_posterior(ds)` in `invT.py` that derives the keys from the
quantiles present (`p{round(q*100)}`) instead of the hard-coded eleven; its `.npz` save
moves into layer 1 behind `save_results=`. Layer 1 then calls `get_invT_posterior`
directly. The four external callers are repointed to layer 1; `debug_imports.py` is deleted.

Parameters that are dead or duplicated and go with it (pre-1.0, so removal is allowed;
each gets a changelog line):

| parameter | where | why |
|---|---|---|
| `use_opencl` | layers 2–3, sets `attrs["opencl_enabled"]` | OpenCL support was deleted 2026-05-31; nothing reads the attr |
| `scaledRI=` deprecated alias | `build_invT_inputData`, layers 2–3, `auto_detect_predictors` key translation | deprecated since 0.1.x; every notebook uses `proxyObs` |
| `model_type` | layers 1–4, `sampler_invT_posterior` still types `"ensemble"` | only `"direct"` exists since the ensemble models were archived |
| `results_path` | layer 2 | folded into `save_results` + `cache_dir` |
| `save=True` (layer 3) vs `save_results=False` (layers 1–2) | inconsistent name and default across layers | one name, `save_results`, default `False` everywhere |
| `proxyObs=None, prior_mu_t=None, prior_sigma_t=None` with a runtime `TypeError` | layer 3 | make them positional-required |

Kept: `stan_model_path` (the documented route to an archived model), `constraint_type`
and `min_temp` (see §9.8 for the open question), and `predict_proxy_from_T` →
`generate_ensemble_auto`, which is a thin but legitimate wrapper (string-or-Dataset
resolution plus a stable public name).

**Column names.** `predict_T_from_proxyObs` takes arrays, so the *notebook* chooses the
column (`df["scaledRI_cren3"].values`) and the function never guesses one. That is the
right design for a library core: explicit inputs, no sniffing. Three places fall short of it:

1. `predict.py` and `ensemble/generator.py` spell the predictor keys `"gdgt23ratio"` /
   `"no3"` as literals while `builder.py` and `metadata.py` read them from
   `constants.OPTIONAL_PREDICTORS`. Use the constant everywhere, one source of truth.
2. `data/ocean_lookup.py:147` indexes the WOA dataset as `da["lon"]`; `utils/regrid.py`
   already has `lat_name`/`lon_name` arguments with candidate detection and a clear error.
   Reuse that resolver in the lookup.
3. `data/screening.py` defaults to `'TEX86'`/`'SST'` but already accepts `columns=` and
   `col_name=` on `fit_predict`, which is the pattern to copy.

**Recommended addition (optional, small):** a DataFrame convenience in `predict.py`,
`predict_T_from_df(df, *, proxy_col, gdgt23ratio_col=None, no3_col=None, lat_col=None,
lon_col=None, **kwargs)`, that maps named columns onto the array API and returns a copy
of `df` with `p5/p50/p95` (and the flag columns) appended. Column names are explicit
keyword arguments with no defaults, so a user's `"lat"` vs `"Latitude"` is a one-word
choice, never a guess. It is what the quickstart already does by hand in three cells.

### 9.8 Explainers versus the revised manuscript (user request 2026-09-07)

Each page under `docs/` was checked against the revised `main.tex` / SI and the nine
shipped Stan models.

| page | verdict | evidence |
|---|---|---|
| `PSM.md`, `model_validation.md`, `marginalization_explainer.md`, `sampler_budget.md` (+ `_static/sampler-budget.*`) | **keep** | framework, validation, the marginal inverse and the MCMC budget are all in the revised text and SI (Figs. S17–S18) |
| `reduce_sum_for_geologists.md` | **keep** | `main.tex:900` cites `reduce_sum`; all four shipped inverse models use it; zero stale terms |
| `ckdtree_nearest_ocean_explainer.md` | **keep, trim** | nearest-ocean snapping is in the SI preprocessing; 353 lines — cut the "robust alternative: 3-D Cartesian tree" section, which the code does not implement |
| `preprint_additive_archive.md` | **keep** | the index of what the archive reproduces |
| `callmap.md` (+ `_static/callmap.html`, `_scripts/build_callmap.py`) | **keep, move to a "Developer" part of `_toc.yml`** | code tooling, not manuscript content; currently listed under "Getting started" |
| `stan_models_explanation_v2.md` | **rewrite → `stan_models.md`** | 574 lines on "Ensemble vs Direct sampling"; the ensemble side is archived. Replace with ~100 lines: the nine shipped models, what each is for, how the marginal likelihood and threading work, link to the archive README |
| `Prior_Choice_Normal_vs_Cauchy.md` | **delete** | no shipped model uses a Cauchy prior; the manuscript never mentions one; 17 stale-term hits |
| `why_plugin_p50_differs.md` (+ `_static/why-plugin-p50-differs.html`) | **delete** | the plug-in-vs-Bayesian P50 argument and the truncated-prior models appear nowhere in the revised manuscript |

**Consequence of the last row — needs your decision.** RESUME.md kept the two
`invT_*_marginal_truncated_prior.stan` models in the wheel *only because* that page
explains them. With the page gone, the Phase B rule ("ship what the manuscript runs")
says they move to `archive/pre-submission/stan_models/` and `constraint_type` /
`min_temp` leave the public API, which narrows `predict_T_from_proxyObs` to the
unconstrained inverse the paper uses. The alternative is to keep the feature and give it
a 20-line section in the new `stan_models.md`. The spec assumes **archive** unless you say
otherwise.

Links to update: `why_plugin_p50_differs.md` is linked from `stan_models_explanation_v2.md:110`
(rewritten anyway); `Prior_Choice_Normal_vs_Cauchy.md` only from the deleted page.
`docs/installation.md:399` lists `odrpack` in the dev extra and follows §9.2.

## 10. Verification (all must pass before the final commit)

1. `pytest -q` green (baseline 351 passed, 11 skipped).
2. `git ls-files -i -c --exclude-standard` prints nothing.
3. `python -m build && unzip -l dist/*.whl | grep -c '\.stan$'` → 9.
4. `git archive HEAD | tar t | grep -E '^(\.claude/|RESUME\.md|CLAUDE\.md|data/external/)'` → empty.
5. `jupyter-book build docs/` with no warnings about missing files.
6. `papermill` (or `jupyter nbconvert --execute --to notebook`) of `SI_code00` and `SI_code03`
   through their data-loading cells, in the regenerated env, to prove the kept files resolve
   and the removed imports were unused.
7. `git lfs ls-files | wc -l` drops from 127 to 55 (22 spreadsheets + 32 revision1 + 1 figure).
8. Fresh clone into a temp dir: `git lfs pull` succeeds within the LFS budget for the kept set.
9. SI_code02 cells 81 and 87 load their grids from `data/cache/TEXAS_kriged_grids_cache/` (the printed
   "Auto cache path" line names the new folder and no re-kriging occurs).
10. The `src/` reference scan (§9.6) reports zero unreferenced definitions; `tests/test_public_api_docs.py` passes.
11. `jupyter-book build docs/` after §9.8 reports no broken cross-references; `grep -rn cauchy docs/` is empty.

## 11. Explicitly out of scope

History is not rewritten; `.git` stays 7 GB locally and the LFS budget problem for *old*
blobs remains. `data/cache/` untouched. Version stays 0.3.2 (Phase C bumps to 1.0.0). The
Zenodo v1.0.0 upload of the 5 derived NetCDFs is recorded as a Phase C task in RESUME.md.

---

## Appendix A — data file classification (generated 2026-09-07)

### A.1 Keep tracked (referenced; count = number of files referencing it)

| refs | file | MB |
|---|---|---|
| 12 | `data/spreadsheets/combined_coretop_culture_mesocosm_rev20260210.csv` | 1.8 |
| 12 | `data/spreadsheets/ds_gridded_screened_global_compilation_finalized.csv` | 1.0 |
| 3 | `data/spreadsheets/published_data/PhanTEX_GIG_df.csv` | 0.4 |
| 3 | `data/spreadsheets/published_data/PhanTEX_v001_modified_032626.csv` | 4.1 |
| 2 | `data/spreadsheets/culture_mesocosm_combined_rev_030425.csv` | 0.1 |
| 2 | `data/spreadsheets/culture_mesocosm_combined_rev_092325.xlsx` | 0.1 |
| 2 | `data/spreadsheets/ds01_updated_global_coretop_tex_revised_011226.csv` | 0.6 |
| 2 | `data/spreadsheets/ols_tex_thermoT_thisStudy.pkl` | 0.0 |
| 2 | `data/spreadsheets/published_data/Babila_SST_results_finalized_compiled.xlsx` | 0.0 |
| 2 | `data/spreadsheets/published_data/ds07_TasmanSea_paleorecords.xlsx` | 0.1 |
| 2 | `data/spreadsheets/published_data/Gaskell2022_pnas.2111332119.sd01.xlsx` | 5.0 |
| 2 | `data/spreadsheets/published_data/NICOPP_d15Nsed_database/nicopp-coretop-data.txt` | 0.2 |
| 2 | `data/spreadsheets/published_data/ODP1259_d18O_planktic_Bornemann08_OBrien17compl.xlsx` | 0.1 |
| 2 | `data/spreadsheets/published_data/PhanSST_v001_extendedRR_121025.csv` | 40.5 |
| 2 | `data/spreadsheets/published_data/PhanTEX_GIG_df.parquet` | 0.2 |
| 2 | `data/spreadsheets/published_data/tran2025-u1482-bio-sst.txt` | 0.1 |
| 2 | `data/spreadsheets/published_data/U1482_MgCa_SST.xlsx` | 0.0 |
| 2 | `data/spreadsheets/published_data/Varma-etal_Co1010.csv` | 0.0 |
| 2 | `data/spreadsheets/revised_cultures_GDGT_github_March2025_RR.xlsx` | 0.2 |
| 1 | `data/spreadsheets/ds03_processed_coretop_tex.csv` | 1.0 |
| 1 | `data/spreadsheets/global_hydrothermal_vents.csv` | 0.0 |
| 1 | `data/spreadsheets/texmesocosms.csv` | 0.0 |

### A.2 `data/external` referenced (untrack; derived ones go to Zenodo at v1.0.0)

| refs | file | MB |
|---|---|---|
| 10 | `data/external/ncfiles/ds06_calculated_ocean_properties.nc` | 19.8 |
| 2 | `data/external/ncfiles/PETMDA_OCN_annual.nc` | 13.2 |
| 2 | `data/external/ncfiles/Tierney22_PNAS_PETMDA/PETMDA_OCN_annual.nc` | 13.2 |
| 2 | `data/external/ncfiles/Tierney22_PNAS_PETMDA/PETMDA_OCN_annual_regridded.nc` | 1.0 |
| 2 | `data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM01x.nc` | 3.0 |
| 2 | `data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM03x.nc` | 3.0 |
| 2 | `data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM06x.nc` | 3.0 |
| 2 | `data/external/ncfiles/Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/Zhu19_Science_EoceneSim_fullDepth_regridded_iPETM09x.nc` | 3.0 |
| 2 | `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/m06c9h_3id_forPgeog_19o_r1c.rot` | 0.1 |
| 2 | `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/Muller2019-Young2019-Cao2020_COBs.gpmlz` | 0.3 |
| 2 | `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/Muller2019-Young2019-Cao2020_CombinedRotations.rot` | 2.7 |
| 2 | `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/PALEOMAP_PlatePolygons__forPgeog_v19o.gpml` | 5.0 |
| 1 | `data/external/ncfiles/calculated_ocean_properties_seasonal.nc` | 51.4 |
| 1 | `data/external/ncfiles/ds04_gridded_coretop_tex_scaledRI.nc` | 0.5 |
| 1 | `data/external/ncfiles/ds_gridded_coretop_tex_scaledRI_revised_081525.nc` | 0.5 |

### A.3 Untrack (referenced by nothing)

| file | MB |
|---|---|
| `data/external/ncfiles/calculated_ocean_properties.nc` | 19.8 |
| `data/external/ncfiles/ds04_gridded_coretop_tex.nc` | 0.2 |
| `data/external/ncfiles/ds05_gridded_AOM_ds.nc` | 7.2 |
| `data/external/ncfiles/ds_gridded_coretop_tex_scaledRI_revised_101425.nc` | 0.6 |
| `data/external/ncfiles/gistemp1200_GHCNv4_ERSSTv5.nc` | 54.1 |
| `data/external/ncfiles/gridded_coretop_RI.nc` | 0.2 |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM01x.01.cam.h0.TS_TREFHT.2501-2600.climo.nc` | 0.9 |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM01x.01.pop.h.TEMP.2501-2600.climo.nc` | 4.5 |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM03x.02.cam.h0.TS_TREFHT.1901-2000.climo.nc` | 1.9 |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM03x.02.pop.h.TEMP.1901-2000.climo.nc` | 4.9 |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM06x.07.cam.h0.TS_TREFHT.1901-2000.climo.nc` | 1.9 |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM06x.07.pop.h.TEMP.1901-2000.climo.nc` | 4.9 |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM09x.01.cam.h0.TS_TREFHT.1901-2000.climo.nc` | 1.9 |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPETM09x.01.pop.h.TEMP.1901-2000.climo.nc` | 4.9 |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPI.01.cam.h0.TS_TREFHT.0400-0499.climo.nc` | 0.9 |
| `data/external/ncfiles/Zhu19_Science_EoceneSim/b.e12.B1850C5CN.f19_g16.iPI.01.pop.h.TEMP.0400-0499.climo.nc` | 3.9 |
| `data/external/paleoDEMS/PaleoDEMS_elevation_Scotese_Wright_2018.nc` | 54.3 |
| `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/Global_EarthByte_230-0Ma_GK07_AREPS_Coastlines.gpmlz` | 1.5 |
| `data/external/paleoDEMS/pyGplates_files/PaleoDEMS_global_plate_model/Global_EarthByte_230-0Ma_GK07_AREPS.rot` | 0.4 |
| `data/external/shapefiles/Knolls.prj` | 0.0 |
| `data/external/shapefiles/Knolls.shp` | 3.7 |
| `data/external/shapefiles/Knolls.shx` | 1.1 |
| `data/external/shapefiles/Seamounts.dbf` | 3.6 |
| `data/external/shapefiles/Seamounts.prj` | 0.0 |
| `data/external/shapefiles/Seamounts.shp` | 0.9 |
| `data/external/shapefiles/Seamounts.shx` | 0.3 |
| `data/raw/OPTiMAL_culmeso_v2.csv` | 0.0 |
| `data/spreadsheets/bit_mixing_analysis.ods` | 0.0 |
| `data/spreadsheets/bit_mixing_analysis.xlsx` | 0.0 |
| `data/spreadsheets/combined_coretop_culture_mesocosm_rev20241015.csv` | 1.2 |
| `data/spreadsheets/combined_df_culmesocore_griddedRI.csv` | 0.2 |
| `data/spreadsheets/combined_df_culmesocore_rawData.csv` | 0.2 |
| `data/spreadsheets/compiled-regression-dataset.csv` | 1.4 |
| `data/spreadsheets/culmeso_fgdgts.csv` | 0.0 |
| `data/spreadsheets/culture_mesocosm_combined_rev_092325 - Copy.xlsx` | 0.1 |
| `data/spreadsheets/culture_mesocosm_combined_rev_092325.csv` | 0.1 |
| `data/spreadsheets/ds01_updated_global_coretop_tex.csv` | 0.5 |
| `data/spreadsheets/ds02_manual_regionName_assignment.xlsx` | 0.2 |
| `data/spreadsheets/ds_gridded_coretop_tex_scaledRI_revised_120325.csv` | 0.7 |
| `data/spreadsheets/Evans2018_lipid_comp_and_temp.csv` | 0.0 |
| `data/spreadsheets/gridded_coretop_with_logi_predRI_T_2025-08-19.csv` | 1.0 |
| `data/spreadsheets/gridded_coretop_with_logi_predRI_T_2025-08-20.csv` | 2.8 |
| `data/spreadsheets/ODP959_data.csv` | 0.0 |
| `data/spreadsheets/OPTiMAL_culmeso.csv` | 0.0 |
| `data/spreadsheets/OPTiMAL_raw_coretop.csv` | 0.2 |
| `data/spreadsheets/postprocessed_culture_data.csv` | 0.2 |
| `data/spreadsheets/processed_coretop_data.csv` | 0.9 |
| `data/spreadsheets/published_data/Babila2022_MgCa_SDB_PETM.xlsx` | 0.0 |
| `data/spreadsheets/published_data/Babila_SST_results.csv` | 0.0 |
| `data/spreadsheets/published_data/deutnat-vostok-noaa.txt` | 0.1 |
| `data/spreadsheets/published_data/Hingsley_etal_2.23_OG_GDD Global Distribution Dataset.xlsx` | 0.0 |
| `data/spreadsheets/published_data/Huguet2006_ArabianSea_paleorecords/huguet2006-niop-c2_905_pc.csv` | 0.0 |
| `data/spreadsheets/published_data/Huguet2006_ArabianSea_paleorecords/huguet2006-niop-c2_905_pc.xlsx` | 0.0 |
| `data/spreadsheets/published_data/Huguet2006_ArabianSea_paleorecords/huguet2006-so42-74kl.csv` | 0.0 |
| `data/spreadsheets/published_data/Huguet2006_ArabianSea_paleorecords/huguet2006-so42-74kl.xlsx` | 0.0 |
| `data/spreadsheets/published_data/Huguet2006_ArabianSea_paleorecords/NIOP-C2_905_PC_SST.tab` | 0.0 |
| `data/spreadsheets/published_data/Huguet2006_ArabianSea_paleorecords/SO42-74KL_SST.tab` | 0.0 |
| `data/spreadsheets/published_data/Inglis2023_TEX_SDB_PETM.xlsx` | 0.2 |
| `data/spreadsheets/published_data/lisiecki2005-d18o-stack-noaa.txt` | 0.0 |
| `data/spreadsheets/published_data/Naafs-etal_peat-individual-global-gdgt.xlsx` | 0.2 |
| `data/spreadsheets/published_data/NICOPP_d15Nsed_database/NICOPP_coretop_published_130307.mat` | 0.0 |
| `data/spreadsheets/published_data/NICOPP_d15Nsed_database/nicopp-downcore-data.txt` | 1.9 |
| `data/spreadsheets/published_data/NICOPP_d15Nsed_database/NICOPP_downcore_published_130307.mat` | 0.6 |
| `data/spreadsheets/published_data/NICOPP_d15Nsed_database/Seafloor_coretop_samples.xls` | 0.3 |
| `data/spreadsheets/published_data/PhanSST_v001.csv` | 40.3 |
| `data/spreadsheets/published_data/PhanTEX_v001_modified_021126.csv` | 3.5 |
| `data/spreadsheets/published_data/PhanTEX_v001_modified_120325.csv` | 3.4 |
| `data/spreadsheets/published_data/PhanTEX_v001_modified_121025.csv` | 40.4 |
| `data/spreadsheets/published_data/SDB_Mgtemp_Gordon_Apr2022.xlsx` | 0.0 |
| `data/spreadsheets/published_data/Seierstad2014_NGRIP_d18O_dataset.xlsx` | 3.3 |
| `data/spreadsheets/published_data/TEXdatabase_v1.csv` | 0.2 |
| `data/spreadsheets/published_data/tran2025-u1482-bio-sst.csv` | 0.1 |
| `data/spreadsheets/published_data/Weiyi23_EarthSystSciData_nitrification_database.xlsx` | 0.7 |
| `data/spreadsheets/published_data/Zhu19_Science_proxies_aax1874_tables_s1_and_s2.xlsx` | 0.0 |
| `data/spreadsheets/raw_coretop_fGDGTs.csv` | 0.1 |
| `data/spreadsheets/reg_data_revised_122024.csv` | 6.0 |
| `data/spreadsheets/revised_cultures_GDGT_github_RR2024.xlsx` | 0.1 |
| `data/spreadsheets/SonneCoretopTexUk.xlsx` | 0.2 |
| `data/spreadsheets/stan_practices/iris-data.csv` | 0.0 |
| `data/spreadsheets/Summary of methods for GDGT analysis.xlsx` | 0.1 |
| `data/spreadsheets/TT15_coretop_data.csv` | 0.4 |
| `data/spreadsheets/fitted_models/ols_tex_thermoT_thisStudy.pkl` | 0.0 |
