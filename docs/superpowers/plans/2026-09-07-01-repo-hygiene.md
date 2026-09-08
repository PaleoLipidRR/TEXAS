# Repo Hygiene and Data Untracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `PaleoLipidRR/TEXAS` to the target layout of the finalization spec by moving superseded material into `archive/`, untracking every data file that no notebook, test, script or the package reads, and rewriting `.gitignore` so the rule is enforced going forward.

**Architecture:** Everything here is git-level and behaviour-preserving. Files move with `git mv` so history follows them; data files leave the index with `git rm --cached` so they stay on disk. The `.gitignore` is rewritten only *after* the untracking, because an already-tracked file is not affected by a new ignore rule and the mismatch is invisible until someone clones. The single check that proves the two halves agree is `git ls-files -i -c --exclude-standard`, which must print nothing.

**Tech Stack:** git, git-lfs, bash. No Python behaviour changes, no Stan compilation, no network.

**Spec:** `docs/superpowers/specs/2026-09-07-repo-finalization-design.md` (sections 4, 5, 6, 7, 8 and Appendix A)

## Global Constraints

- **Sort in place.** `notebooks/`, `figures/`, `data/`, `scripts/` keep their names. Only strays move.
- **No notebook is rewritten to accommodate a move.** This is the reason `figures/manuscript/finalized/` stays where it is: about 60 notebook cells hardcode paths under it, which made moving it not worth doing. The rule constrains *which moves this plan chooses*, not whether a notebook may ever be edited.

  Where an approved move leaves a stale reference **inside** a notebook, fix it. Task 5 moves ten drivers into `scripts/paper/`, and `SI_code02a` builds one of their paths with `local_github_path / "scripts" / "plot_uncertainty_calibration.py"` and feeds it to `subprocess.run`. Leaving that stale ships a notebook that raises at runtime. Comments and printed instructions naming a moved script are fixed for the same reason, one step weaker: a notebook that tells the reader to run a path that no longer exists is wrong.

  Note that a path assembled from `/` operators does **not** match a grep for `scripts/<name>.py`. Search for the bare script stem as well as the slashed path.
- **History is not rewritten.** No `filter-repo`, no rebase, no orphan branch. `.git` stays ~7 GB locally and the LFS budget problem for *old* blobs is out of scope.
- **Data files stay on disk.** `git rm --cached` only. A destructive `rm` of tracked data is never correct in this plan.
- **`data/cache/**` is untouched** and is gitignored, so it does not travel with a clone. Nothing here depends on its contents.
- **Version stays 0.3.2.** Phase C bumps to 1.0.0; not here.
- **Never push tag `v0.2.6`.** It exists locally only, and `.github/workflows/docker.yml` fires on every `v*` tag, so pushing it would publish a GHCR image for a version that was never released.
- **`.zenodo.json` model count:** this plan sets it to **9**, the true count once the pre-submission archives move. Plan 04 lowers it to **7** when it archives the two truncated-prior inverse models. Do not pre-empt that here.
- **pytest baseline: 351 passed, 11 skipped at the start of this plan, and it GROWS as tasks add tests.** Task 2 adds one, taking it to 352 passed / 11 skipped. Compare against the count you measured at the start of your own task plus the tests your task adds, not against a fixed number.

  **Run it as `.venv/bin/python -m pytest -q`.** The interpreter changes the answer and this is the single most common way to get a wrong baseline:

  | interpreter | result | why |
  |---|---|---|
  | `.venv/bin/python` (no esmpy) | 352 passed, 11 skipped | the reference for this plan |
  | `texas-env-2026-09` (esmpy present) | 350 passed, 13 skipped | two `tests/test_regrid.py` cases exercise the *absent-esmpy* fallback and skip when esmpy is installed |
  | `python` (miniforge base) | 11 collection errors | numpy 2.5.1 against scipy 1.11.4, `ValueError: numpy.dtype size changed` |

  Both working environments collect **363** tests; the entire difference is those two regrid cases. `texas-env` (no date suffix) exists but is stale from 2026-04-22, predates the ultraplot migration, and is not a candidate. The `.venv` is uv-managed with no pip: install with `VIRTUAL_ENV=.venv uv pip install <pkg>`.

  **Never measure a baseline while another task is mid-commit.** Doing so during execution made a new test look like a flaky suite.
- Python >= 3.10. The package uses `ultraplot`, never `proplot`.
- **Commit attribution comes from the harness, not from this document.** The trailer lines quoted in each task's commit step were correct when written; if your session has been given different attribution guidance, follow that instead. The trailers are not a spec requirement and a mismatch is not a defect.

---

### Task 1: Clean the working tree and delete local junk

The spec's section 8 recorded the tree state at design time. Confirm it still holds before anything moves, because a `git mv` on a dirty file is how work gets lost.

**Files:**
- Modify (discard changes): `notebooks/manuscripts/SI_code00_PreProcessing.ipynb`, `notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb`
- Delete (untracked): three `coretop_maps_boundedT_*.csv` under `data/revision1/groupA/manuscript_refit/`
- Delete (ignored, local only): the junk list below

**Interfaces:**
- Consumes: nothing.
- Produces: a clean working tree at commit `41ba78e8`, which every later task assumes.

- [ ] **Step 1: Confirm the tree matches the spec's snapshot**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git status --short
git rev-parse --short HEAD          # expect 41ba78e8
git rev-list --count origin/main..HEAD   # expect 0
git rev-list --count HEAD..origin/main   # expect 0
git stash list                      # expect empty
```

Expected: exactly two modified notebooks and three untracked CSVs. **If anything else appears, stop and report it.** The spec's classification of these five files was made against this exact state.

- [ ] **Step 2: Verify the two notebook diffs are metadata only**

```bash
git diff --stat notebooks/manuscripts/SI_code00_PreProcessing.ipynb \
                notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb
git diff notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb | grep -E '^[+-]' | grep -v '^[+-][+-]' | head -40
```

Expected: kernel metadata only (`3.13.5` -> `3.12.8`) plus, in SI_code00, a recorded `ModuleNotFoundError: sklearn` from a run in a venv without the dev extra. No analysis cell source changed.

- [ ] **Step 3: Verify the three stray CSVs are byte-identical twins, then discard both sets**

```bash
cd data/revision1/groupA/manuscript_refit
cmp coretop_maps_boundedT_manifest.csv coretop_maps_t0shift_manifest.csv && echo "IDENTICAL manifest"
cmp coretop_maps_boundedT_sites.csv    coretop_maps_sites.csv            && echo "IDENTICAL sites"
cmp superseded_constant_prior/coretop_maps_boundedT_manifest.csv \
    superseded_constant_prior/coretop_maps_t0shift_manifest.csv          && echo "IDENTICAL superseded"
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
```

Expected: three `IDENTICAL` lines. **If any `cmp` reports a difference, stop** — the file is not a leftover of the `boundedT` -> `t0shift` rename and deleting it would lose data.

```bash
git checkout -- notebooks/manuscripts/SI_code00_PreProcessing.ipynb \
                notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb
rm data/revision1/groupA/manuscript_refit/coretop_maps_boundedT_manifest.csv \
   data/revision1/groupA/manuscript_refit/coretop_maps_boundedT_sites.csv \
   data/revision1/groupA/manuscript_refit/superseded_constant_prior/coretop_maps_boundedT_manifest.csv
git status --short                  # expect empty
```

- [ ] **Step 4: Delete the local ignored junk**

None of this is tracked, so none of it is a commit. It is deleted to make the later `git ls-files` and `git archive` checks readable and to free ~330 MB.

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
rm -f  texas-psm-zenodo-v0.1.5.zip
rm -rf review_archive_v0.2.0/ dist/ outputs/
rm -rf notebooks/exploration/ notebooks/manuscripts/.ipynb_checkpoints/
rm -f  notebooks/manuscripts/posterior_check.png notebooks/texas_results.csv
rm -f  src/TEXAS/stan_models/.Rhistory
```

- [ ] **Step 5: Delete the compiled Stan binaries and repack the object store**

CmdStan writes its binaries next to the `.stan` source. They are platform-specific, regenerate on next use, and their presence makes the `stan_models/` listing unreadable.

```bash
find src/TEXAS/stan_models -maxdepth 1 -type f ! -name '*.stan' ! -name '*.md' -print
```

Expected: **10** extensionless executables and nothing else. (The spec's section 8 says 11; it is wrong, verified 2026-09-07 by counting. If you find a different number, confirm every entry is a Stan executable and no unexpected file type is present, then proceed — the count is informational, the file-type check is the guard.)

```bash
find src/TEXAS/stan_models -maxdepth 1 -type f ! -name '*.stan' ! -name '*.md' -delete
ls src/TEXAS/stan_models/          # expect: archive/ archive_pre_annotated/ and 9 .stan files
git gc --prune=now
git status --short                 # expect empty
```

- [ ] **Step 6: Commit**

Nothing tracked changed, so there is nothing to commit. Record the state instead:

```bash
git status --short && echo "TREE CLEAN — proceed to Task 2"
```

---

### Task 2: Move the pre-submission Stan archives out of the package

`src/TEXAS/stan_models/archive/` and `archive_pre_annotated/` sit inside the installed package directory but are not shipped (`pyproject.toml` globs `stan_models/*.stan` non-recursively). Moving them to the repo-root archive closes the open Phase B1 bullet and makes the package directory mean exactly "what ships".

**Files:**
- Move: `src/TEXAS/stan_models/archive/` (15 `.stan` + `README.md`) -> `archive/pre-submission/stan_models/`
- Move: `src/TEXAS/stan_models/archive_pre_annotated/` (4 `.stan`) -> `archive/pre-submission/stan_models/pre_annotated/`
- Modify: `src/TEXAS/utils/paths.py` (the `STAN_ARCHIVE_DIR` constant)
- Modify: `src/TEXAS/stan/compiler.py:216-230` (the archive-stem fallback and its docstring)
- Modify: `tests/test_stan_model_archive.py`, `tests/test_streamlit_params.py`

**Interfaces:**
- Consumes: a clean tree from Task 1.
- Produces: `STAN_ARCHIVE_DIR` pointing at `<repo root>/archive/pre-submission/stan_models`. Task 3 and Task 6 both write into `archive/`, and Task 6's README indexes what this task creates.

- [ ] **Step 1: Read the current archive resolution before touching it**

```bash
sed -n '200,240p' src/TEXAS/stan/compiler.py
grep -rn "STAN_ARCHIVE_DIR" src/ tests/
sed -n '1,60p' tests/test_stan_model_archive.py
```

The fallback exists so an archived model still resolves by plain stem, which the SI notebooks rely on. Whatever the constant is named and wherever it is defined, it must end up pointing at the new location and nothing else may change about the lookup order.

- [ ] **Step 2: Run the archive tests to establish they pass before the move**

```bash
.venv/bin/python -m pytest tests/test_stan_model_archive.py tests/test_streamlit_params.py -q
```

Expected: PASS. This is the baseline the move must preserve.

- [ ] **Step 3: Create the destination and move both trees**

The two directories contain same-named files (`gen_logi_fixed_hier_crtp_multiv_priorApprox.stan` and `gen_logi_fixed_hier_crtp_multiv.stan` exist in both), so `archive_pre_annotated/` must keep its own subdirectory. Flattening them would silently drop one version of each.

```bash
mkdir -p archive/pre-submission/stan_models
git mv src/TEXAS/stan_models/archive/* archive/pre-submission/stan_models/
git mv src/TEXAS/stan_models/archive_pre_annotated archive/pre-submission/stan_models/pre_annotated
rmdir src/TEXAS/stan_models/archive
ls archive/pre-submission/stan_models/            # 15 .stan + README.md + pre_annotated/
ls archive/pre-submission/stan_models/pre_annotated/   # 4 .stan
```

- [ ] **Step 4: Leave `STAN_ARCHIVE_DIR` exactly as it is**

**Do not edit `src/TEXAS/utils/paths.py` in this task.** An earlier draft of this plan said to repoint the constant at the new directory. That would have been a bug, and the check below is what caught it.

```bash
sed -n '155,165p' src/TEXAS/utils/paths.py
.venv/bin/python -c "from TEXAS.utils.paths import STAN_ARCHIVE_DIR; print(STAN_ARCHIVE_DIR)"
```

Expected output:

```python
_archive = (PROJECT_ROOT / "archive" / "submission-2026-04" / "stan_models")
STAN_ARCHIVE_DIR = _archive.resolve() if _archive.is_dir() else None
```

The constant points at **`archive/submission-2026-04/stan_models`** and always has. It has never pointed at `src/TEXAS/stan_models/archive/`, which is the directory this task moves. So the move does not affect it, and repointing it would break plain-stem resolution for the eight 2026-04 models that `tests/test_stan_model_archive.py` asserts on and that `SI_code02a` loads.

The 15 pre-submission models were **not** resolvable by plain stem before this move and are not afterwards. That is unchanged behaviour, not a regression. They are reachable by absolute path, which `archive/README.md` documents in Task 6.

- [ ] **Step 5: Leave the compiler fallback alone too**

`src/TEXAS/stan/compiler.py:216-230` resolves against `STAN_ARCHIVE_DIR`, which did not move. Read it and confirm no path literal names `src/TEXAS/stan_models/archive`:

```bash
grep -n "stan_models/archive\|archive_pre_annotated" src/TEXAS/stan/compiler.py
```

Expected: no output. If a literal does appear, fix that literal only, and leave the constant alone.

- [ ] **Step 6: Update the two tests**

`tests/test_streamlit_params.py:32` already builds `REPO / "archive" / "submission-2026-04" / "stan_models"` and its comment at lines 28-30 says `stan_models/archive/` and `archive_pre_annotated/` are deliberately excluded because they declare `Q_crtp` and `sigma_scaledRI_crtp`. Those two directories now live at `archive/pre-submission/stan_models/`, so the comment must name the new path and the exclusion must still hold. Update the comment text and add an assertion that the excluded tree is where the comment says it is:

```python
PRE_SUBMISSION_DIR = REPO / "archive" / "pre-submission" / "stan_models"

def test_pre_submission_archive_is_excluded_from_the_param_scan():
    """The pre-2026-04 models declare Q_crtp and sigma_scaledRI_crtp.

    Those are exactly the stale parameter names this module exists to catch, so
    the scan must never walk them. Pinning the path here means a future move
    breaks this test instead of silently widening the scan.
    """
    assert PRE_SUBMISSION_DIR.is_dir()
    assert PRE_SUBMISSION_DIR not in ARCHIVE_DIR.parents
```

In `tests/test_stan_model_archive.py`, update the module docstring and any path literal that names `src/TEXAS/stan_models/archive`. Read lines 1-60 first; the `needs_archive` skipif at line 48 keys on a directory existing and must key on the new one.

- [ ] **Step 7: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_stan_model_archive.py tests/test_streamlit_params.py -q
.venv/bin/python -m pytest -q
```

Expected: the two files PASS, and the full suite is 351 passed / 11 skipped.

- [ ] **Step 8: Verify the 2026-04 archive still resolves by plain stem**

The behaviour that must survive this move is the fallback into
`archive/submission-2026-04/stan_models`, which `SI_code02a` depends on.

```bash
.venv/bin/python -c "
from TEXAS.stan.compiler import StanCompiler
p = StanCompiler().resolve_stan_path('gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv')
print(p)
assert p.exists(), p
assert 'submission-2026-04' in str(p), p
print('OK: 2026-04 archive still resolves')
"
```

Expected: the resolver prints its own `superseded model; resolving from ...` notice, then the path, then `OK`.

**Do not** assert anything about the pre-submission models resolving. They never did. `resolve_stan_path('hier_crtp_multiv')` returns `src/TEXAS/stan_models/hier_crtp_multiv.stan` both before and after this task, a path that does not exist in either case, because the resolver only checks existence on its archive fallback. That is pre-existing behaviour this plan deliberately does not change.

- [ ] **Step 9: Commit**

```bash
git add -A src/TEXAS archive tests
git commit -m "Move the pre-submission Stan archives out of the package directory

src/TEXAS/stan_models/ now holds only what ships. The 15 pre-submission models
and the 4 pre-annotated variants move to archive/pre-submission/stan_models/,
with archive_pre_annotated/ kept in its own subdirectory because two of its
files share names with the other tree.

STAN_ARCHIVE_DIR follows them, so resolve_stan_path()'s plain-stem fallback is
unchanged from a caller's point of view.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 3: Move the superseded notebooks and figures into the 2026-04 archive

**Files:**
- Move: `notebooks/superseded/{README.md, SI_code2_TEXAS_analysis.ipynb, SI_code3_paleo_showcases.ipynb}` -> `archive/submission-2026-04/notebooks/`
- Move: `figures/manuscript/superseded/` (31 files) -> `archive/submission-2026-04/figures/`
- Move: `figures/manuscript/existing_calibrations_with_DeltaT_Tres_ranges.pdf` -> `archive/submission-2026-04/figures/`
- Modify: `README.md:198` (the layout block naming `superseded/`)

**Interfaces:**
- Consumes: `archive/submission-2026-04/` from Task 2's sibling (it already exists, holding `stan_models/`).
- Produces: `archive/submission-2026-04/{notebooks,figures,stan_models}/`, indexed by Task 6.

- [ ] **Step 1: Confirm the contents before moving**

```bash
ls notebooks/superseded/
ls figures/manuscript/superseded/ | wc -l        # expect 31
ls figures/manuscript/*.pdf
```

- [ ] **Step 2: Move**

```bash
mkdir -p archive/submission-2026-04/notebooks archive/submission-2026-04/figures
git mv notebooks/superseded/* archive/submission-2026-04/notebooks/
rmdir notebooks/superseded
git mv figures/manuscript/superseded/* archive/submission-2026-04/figures/
rmdir figures/manuscript/superseded
git mv figures/manuscript/existing_calibrations_with_DeltaT_Tres_ranges.pdf \
       archive/submission-2026-04/figures/
```

The stray PDF is the parent of the initial submission's Fig. 1 and belongs with the rest of that submission's figures rather than loose in `figures/manuscript/`.

- [ ] **Step 3: Find and fix every reference to the two moved paths**

```bash
grep -rn "notebooks/superseded\|figures/manuscript/superseded" \
  --include='*.py' --include='*.md' --include='*.ipynb' --include='*.yml' \
  --include='*.json' --include='*.toml' --include='*.cfg' . \
  | grep -v '^\./\.git/' | grep -v 'docs/superpowers/' | grep -v '^\./\.venv/'
```

Fix each hit. `README.md:198` currently reads:

```
  superseded/       Pre-revision (additive-formulation) versions, kept for provenance
```

Replace that line, and the tree it sits in, so the layout block matches section 3 of the spec. Do not invent a layout: copy the target tree from the spec verbatim and trim it to what `README.md` already shows.

Hits inside `RESUME.md` are a historical record of past sessions. **Leave RESUME.md alone** except where it states a *current* path a future session would follow.

- [ ] **Step 4: Verify nothing dangles**

```bash
grep -rn "notebooks/superseded\|figures/manuscript/superseded" \
  --include='*.py' --include='*.md' --include='*.ipynb' . \
  | grep -v '^\./\.git/' | grep -v 'docs/superpowers/' | grep -v 'RESUME.md'
```

Expected: no output.

- [ ] **Step 5: Run the tests and commit**

```bash
.venv/bin/python -m pytest -q
git add -A
git commit -m "Archive the initial submission's notebooks and figures

notebooks/superseded/ and figures/manuscript/superseded/ join the Stan models
already under archive/submission-2026-04/, so the three parts of that
submission sit together. The stray existing_calibrations PDF, parent of the
initial Fig. 1, goes with them.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 4: Archive the gridT exploratory material and the IMOG presentation

The gridded-inversion work is **not** going into the resubmission (user decision, 2026-09-07). That makes it provenance rather than reviewer evidence, so it moves to `archive/exploratory/` rather than staying at the top level where a reader would take it for part of the paper.

**Files:**
- Move: `TEXAS-revision/` (`gridT_explainer.html`, 2 `.md`, `assets/` with 6 `.png`) -> `archive/exploratory/gridT-inversion/`
- Move: `notebooks/current/IMOG_presentation.ipynb` -> `archive/presentations/`
- Delete (empty afterwards): `notebooks/current/`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `archive/exploratory/gridT-inversion/` and `archive/presentations/`, both indexed by Task 6.

- [ ] **Step 1: Confirm contents**

```bash
find TEXAS-revision -type f | sort
ls notebooks/current/
```

Expected: exactly `gridT_explainer.html`, `gridT_inversion_characterization.md`, `gridT_poster_text.md`, and six PNGs under `assets/`; and one notebook in `notebooks/current/`.

- [ ] **Step 2: Move**

```bash
mkdir -p archive/exploratory archive/presentations
git mv TEXAS-revision archive/exploratory/gridT-inversion
git mv notebooks/current/IMOG_presentation.ipynb archive/presentations/
rmdir notebooks/current
```

`notebooks/current/` disappears entirely. Everything active lives in `notebooks/manuscripts/` and `notebooks/reviewer_response/`.

- [ ] **Step 3: Fix references**

```bash
grep -rn "TEXAS-revision\|notebooks/current" \
  --include='*.py' --include='*.md' --include='*.ipynb' --include='*.yml' --include='*.json' . \
  | grep -v '^\./\.git/' | grep -v 'docs/superpowers/' | grep -v '^\./\.venv/' | grep -v 'RESUME.md'
```

Fix each hit. Note that `working-repo/TEXAS-revision` mentioned in `CLAUDE.md` is a **different, separate repository** and must not be rewritten. Read the surrounding sentence before editing: only bare `TEXAS-revision/` at this repo's root is the thing that moved.

- [ ] **Step 4: Verify and commit**

```bash
grep -rn "^TEXAS-revision\|(TEXAS-revision/\|notebooks/current" --include='*.md' --include='*.py' . \
  | grep -v '^\./\.git/' | grep -v 'docs/superpowers/' | grep -v RESUME.md
.venv/bin/python -m pytest -q
git add -A
git commit -m "Archive the gridT exploratory material and the IMOG presentation

gridT is not in the resubmission, so TEXAS-revision/ is provenance and moves to
archive/exploratory/gridT-inversion/ rather than reading as reviewer evidence at
the repo root. notebooks/current/ held one presentation notebook and disappears.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 5: Split the paper drivers out of `scripts/`

`scripts/` currently mixes two unrelated things: release and cache tooling that a *user* might run, and the ten long-running analysis drivers that produced the manuscript's numbers. Separating them means a reader opening `scripts/` sees tools, not a pile of one-off refit jobs.

**Files:**
- Move into `scripts/paper/`: `run_manuscript_refits.py`, `run_coretop_maps.py`, `run_param_sensitivity.py`, `fit_t0shift_single_predictors.py`, `invt_M_paleo_check.py`, `plot_uncertainty_calibration.py`, `build_diagnostics_table.py`, `build_parameter_table.py`, `add_retained_flag.py`, `backfill_iter_warmup.py`
- Stay in `scripts/`: `bump_version.sh`, `push_docker.sh`, `zenodo_upload.py`, `zenodo_fix_draft_metadata.py`, `make_bundled_posteriors.py`, `build_calibration_domain.py`, `prepare_resubmission_archive.py`, `migrate_cache_layout.py`, `rename_cache_files.py`, `normalize_posterior_attrs.py`, `flatten_cache.py`
- Modify: `tests/test_param_sensitivity_config.py:25`, `tests/test_manuscript_refit_config.py`, `.claude/agents/pre-commit.md`, `.claude/agents/figure-sync.md`, `.claude/skills/notebook-sync/SKILL.md`, `data/revision1/groupA/reviewer_response/REVIEWER_MAP.md`, `data/revision1/groupA/model_comparison_cv/PROVENANCE.md`, `docs/sampler_budget.md`, `docs/_scripts/build_sampler_budget.py`, `notebooks/reviewer_response/README.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `scripts/paper/`. `tests/test_param_sensitivity_config.py` loads a driver **by path via importlib**, so it is the one that breaks loudest if a path is missed.

- [ ] **Step 1: Establish the baseline**

```bash
.venv/bin/python -m pytest tests/test_param_sensitivity_config.py tests/test_manuscript_refit_config.py -q
sed -n '15,35p' tests/test_param_sensitivity_config.py
```

Read the importlib load so you know the exact string to change.

- [ ] **Step 2: Move**

```bash
mkdir -p scripts/paper
git mv scripts/run_manuscript_refits.py scripts/run_coretop_maps.py \
       scripts/run_param_sensitivity.py scripts/fit_t0shift_single_predictors.py \
       scripts/invt_M_paleo_check.py scripts/plot_uncertainty_calibration.py \
       scripts/build_diagnostics_table.py scripts/build_parameter_table.py \
       scripts/add_retained_flag.py scripts/backfill_iter_warmup.py \
       scripts/paper/
rm -rf scripts/__pycache__
ls scripts/ scripts/paper/
```

- [ ] **Step 3: Find every reference**

```bash
grep -rn "scripts/run_manuscript_refits\|scripts/run_coretop_maps\|scripts/run_param_sensitivity\|scripts/fit_t0shift_single_predictors\|scripts/invt_M_paleo_check\|scripts/plot_uncertainty_calibration\|scripts/build_diagnostics_table\|scripts/build_parameter_table\|scripts/add_retained_flag\|scripts/backfill_iter_warmup" \
  . 2>/dev/null | grep -v '^\./\.git/' | grep -v 'docs/superpowers/' | grep -v '^\./\.venv/'
```

Rewrite each to `scripts/paper/...`. The drivers reference **each other** as well (`run_coretop_maps.py`, `run_manuscript_refits.py`, `run_param_sensitivity.py` and `backfill_iter_warmup.py` all appeared in the reference scan), so check the moved files themselves, not only their callers.

Historical narration in `RESUME.md` stays as written. Only lines that tell a future session which file to run get updated.

- [ ] **Step 4: Fix the importlib path in the test**

`tests/test_param_sensitivity_config.py` line 25 loads the driver by path. Change the literal to `scripts/paper/run_param_sensitivity.py`, keeping whatever `Path(__file__).parent...` construction is already there.

- [ ] **Step 5: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_param_sensitivity_config.py tests/test_manuscript_refit_config.py -q
.venv/bin/python -m pytest -q
```

Expected: 351 passed, 11 skipped.

- [ ] **Step 6: Sanity-check each moved driver still imports**

A driver that hardcoded its own location relative to the repo root will now be one directory deeper. Catch that here rather than in a six-hour Stan run.

```bash
for f in scripts/paper/*.py; do
  .venv/bin/python -c "
import ast, sys, pathlib
src = pathlib.Path('$f').read_text()
ast.parse(src)
" || echo "PARSE FAIL $f"
  grep -n "parent\.parent\|parents\[" "$f" && echo "  ^^ check depth in $f"
done
```

Any `Path(__file__).resolve().parent.parent` that meant "repo root" now means `scripts/`. Add one `.parent` wherever that pattern appears in a moved file, and note in the commit which files needed it.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Split the ten paper drivers into scripts/paper/

scripts/ was mixing release and cache tooling a user might run with one-off
analysis drivers that produced the manuscript's numbers. The drivers move; the
tooling stays. tests/test_param_sensitivity_config.py loads one of them by path
via importlib and follows.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 6: Write the archive index

Four sub-archives now exist with no explanation of what distinguishes them. A reader landing in `archive/` needs to know which one holds the initial submission and which holds material that was never submitted at all.

**Files:**
- Create: `archive/README.md`
- Modify: `CLAUDE.md` (the archive paragraph under "Stan models"), `docs/preprint_additive_archive.md`, `.zenodo.json`

**Interfaces:**
- Consumes: the four directories created by Tasks 2, 3 and 4.
- Produces: the index every later plan links to when it says "see the archive README".

- [ ] **Step 1: Write `archive/README.md`**

```markdown
# Archive

Nothing here is deleted and nothing here ships in the wheel. Each sub-archive
answers a different question about the project's history.

| directory | what it holds | why it is not in the live tree |
|---|---|---|
| `submission-2026-04/` | The initial submission: 8 Stan models, 2 SI notebooks, 32 figures | Superseded by the revision. The additive (beta-on-mu) model here is still the revision's comparison arm, and its posteriors remain downloadable, so the code that reads them is live even though the model is not. |
| `pre-submission/stan_models/` | 15 development models, plus 4 pre-annotated variants under `pre_annotated/` | Never submitted. They declare parameters the project has since dropped (`Q_crtp`, `sigma_scaledRI_crtp`), which is why `tests/test_streamlit_params.py` deliberately does not scan this tree. |
| `exploratory/gridT-inversion/` | The gridded-inversion explainer, its two write-ups and six figures | Explored during the revision and left out of the resubmission. Provenance, not reviewer evidence. |
| `presentations/` | `IMOG_presentation.ipynb` | A conference talk, not part of the analysis. |

## Running an archived Stan model

`pyproject.toml` globs `stan_models/*.stan` non-recursively, so nothing under
`archive/` reaches the wheel. To run an archived model from a source checkout,
pass an absolute path — `StanCompiler.resolve_stan_path()` passes absolute paths
straight through:

```python
from pathlib import Path
from TEXAS import get_posterior

stan_file = Path("archive/submission-2026-04/stan_models/"
                 "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv.stan").resolve()
post, diag = get_posterior(data, "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv",
                           temptype="SST", proxy_name="scaledRI",
                           stan_file=str(stan_file))
```

There is no `model_dir=` route through `get_posterior()`; it builds a
`StanCompiler()` with no arguments.

Archived models also still resolve by plain stem through
`resolve_stan_path()`'s archive fallback, which is inert in a wheel install
because `archive/` is not packaged.
```

- [ ] **Step 2: Update the CLAUDE.md archive paragraph**

`CLAUDE.md` contains a block quote under "Stan models" beginning "**Stan models pruned to the shipped set (2026-09-03, RESUME.md Phase B1)**". It says the other 8 models "moved to `archive/submission-2026-04/stan_models/` at the repo root". That is still true. Add one sentence naming the two new sub-archives and pointing at `archive/README.md`. Do not rewrite the surrounding paragraph; it documents decisions that have not changed.

- [ ] **Step 3: Fix the Stan model count in `.zenodo.json`**

Line 3 of `.zenodo.json` currently claims:

```
The package ships 20 Stan models covering univariate and multivariate variants, direct (marginal) and ensemble sampling, and hard/unconstrained temperature constraints.
```

Every clause is wrong: it ships 9 (after this plan), the ensemble models were archived in April, and the hard-constraint models went with them. Replace with:

```
The package ships the nine Stan models the manuscript runs: three forward calibrations, five marginal inverse models, and a linear reference. Superseded and exploratory models are kept in the repository's <code>archive/</code> directory rather than shipped.
```

**Plan 04 lowers "nine" to "seven"** when it archives the two truncated-prior inverse models, and adjusts the breakdown. Leave a comment in the commit message so that edit is expected.

- [ ] **Step 4: Check `docs/preprint_additive_archive.md`**

```bash
grep -n "archive\|stan_models" docs/preprint_additive_archive.md
```

It indexes what the 2026-04 archive reproduces. Update any path that moved and add a link to `archive/README.md`. Its content is otherwise correct and stays.

- [ ] **Step 5: Verify the counts the README asserts**

```bash
ls archive/submission-2026-04/stan_models/*.stan | wc -l      # expect 8
ls archive/submission-2026-04/notebooks/*.ipynb | wc -l       # expect 2
ls archive/submission-2026-04/figures/ | wc -l                # expect 32
ls archive/pre-submission/stan_models/*.stan | wc -l          # expect 15
ls archive/pre-submission/stan_models/pre_annotated/*.stan | wc -l  # expect 4
ls src/TEXAS/stan_models/*.stan | wc -l                       # expect 9
```

**If any count differs, fix the README to match reality, not reality to match the README.**

- [ ] **Step 6: Commit**

```bash
git add archive/README.md CLAUDE.md .zenodo.json docs/preprint_additive_archive.md
git commit -m "Index the archive and correct the Stan model count in .zenodo.json

archive/ now has four sub-archives with different reasons for existing, so it
gets a README saying which is which and how to run a model out of one.

.zenodo.json claimed 20 shipped models with ensemble sampling and hard
constraints. It ships 9, and both of those families were archived in April.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 7: Untrack every data file nothing reads

This is the task that changes the repository's size and its LFS bill. 97 files leave the index and stay on disk.

**Files:**
- Untrack: 55 files under `data/spreadsheets/`, 1 under `data/raw/`, 41 under `data/external/`
- Keep tracked: 22 under `data/spreadsheets/`, 45 under `data/revision1/`, `data/README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: an index in which `git ls-files data/` returns 68 files. Task 8's `.gitignore` encodes exactly this set, and Task 12's `git ls-files -i -c` check is what proves the two agree.

- [ ] **Step 1: Record the baseline**

```bash
git ls-files data/ | wc -l          # expect 165
git lfs ls-files | wc -l            # expect 127
du -sh .git
```

- [ ] **Step 2: Write the keep-list to a file**

The 22 files that stay tracked, from Appendix A.1 of the spec:

```bash
cat > /tmp/texas_keep.txt <<'EOF'
data/spreadsheets/combined_coretop_culture_mesocosm_rev20260210.csv
data/spreadsheets/ds_gridded_screened_global_compilation_finalized.csv
data/spreadsheets/culture_mesocosm_combined_rev_030425.csv
data/spreadsheets/culture_mesocosm_combined_rev_092325.xlsx
data/spreadsheets/ds01_updated_global_coretop_tex_revised_011226.csv
data/spreadsheets/ds03_processed_coretop_tex.csv
data/spreadsheets/global_hydrothermal_vents.csv
data/spreadsheets/ols_tex_thermoT_thisStudy.pkl
data/spreadsheets/revised_cultures_GDGT_github_March2025_RR.xlsx
data/spreadsheets/texmesocosms.csv
data/spreadsheets/published_data/Babila_SST_results_finalized_compiled.xlsx
data/spreadsheets/published_data/ds07_TasmanSea_paleorecords.xlsx
data/spreadsheets/published_data/Gaskell2022_pnas.2111332119.sd01.xlsx
data/spreadsheets/published_data/ODP1259_d18O_planktic_Bornemann08_OBrien17compl.xlsx
data/spreadsheets/published_data/PhanSST_v001_extendedRR_121025.csv
data/spreadsheets/published_data/PhanTEX_GIG_df.csv
data/spreadsheets/published_data/PhanTEX_GIG_df.parquet
data/spreadsheets/published_data/PhanTEX_v001_modified_032626.csv
data/spreadsheets/published_data/tran2025-u1482-bio-sst.txt
data/spreadsheets/published_data/U1482_MgCa_SST.xlsx
data/spreadsheets/published_data/Varma-etal_Co1010.csv
data/spreadsheets/published_data/NICOPP_d15Nsed_database/nicopp-coretop-data.txt
EOF
wc -l /tmp/texas_keep.txt          # expect 22
```

- [ ] **Step 3: Verify every keep-list file is tracked and exists**

A typo here untracks a file a notebook needs, and the failure surfaces only when someone clones.

```bash
while read -r f; do
  [ -e "$f" ] || echo "MISSING ON DISK: $f"
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || echo "NOT TRACKED: $f"
done < /tmp/texas_keep.txt
echo "keep-list check done"
```

Expected: no `MISSING` or `NOT TRACKED` lines.

- [ ] **Step 4: Re-verify the untrack list against the working tree**

The spec's classification was made by grepping each basename across `notebooks/`, `src/`, `tests/`, `scripts/`, `streamlit_app/`, `docs/` and `README.md`. Repeat that check now, because Tasks 3, 4 and 5 moved files that do the referencing.

```bash
git ls-files data/spreadsheets data/raw data/external > /tmp/texas_all.txt
grep -vxF -f /tmp/texas_keep.txt /tmp/texas_all.txt > /tmp/texas_untrack.txt
wc -l /tmp/texas_untrack.txt       # expect 97

while read -r f; do
  b=$(basename "$f")
  hits=$(grep -rlF "$b" --include='*.py' --include='*.ipynb' --include='*.md' \
          notebooks/ src/ tests/ scripts/ streamlit_app/ docs/ README.md 2>/dev/null \
        | grep -v 'docs/superpowers/' | wc -l)
  [ "$hits" -gt 0 ] && echo "STILL REFERENCED ($hits): $f"
done < /tmp/texas_untrack.txt
echo "untrack-list check done"
```

**Expect roughly 14 `STILL REFERENCED` lines, not zero.** An earlier draft of this step said zero and was miscalibrated: Appendix A.2 lists 15 `data/external` files that ARE referenced by notebooks and are untracked anyway, on purpose. The check is not "no hits" — it is "every hit falls into a category the spec already accounts for". Measured 2026-09-07, the 14 break down as:

| count | category | disposition |
|---|---|---|
| 6 | TEXAS-derived NetCDFs read by SI_code00 / SI_code03 | untracked now, 5 of them uploaded to Zenodo at v1.0.0 (Appendix A.2) |
| 5 | third-party originals documented for separate download | untracked, sources listed in `data/README.md` by Task 9 |
| 2 | duplicate basenames | the plan keeps the path a notebook opens and untracks the other: `fitted_models/ols_tex_thermoT_thisStudy.pkl` versus the copy directly under `data/spreadsheets/`, and `ncfiles/PETMDA_OCN_annual.nc` versus the copy under `Tierney22_PNAS_PETMDA/` |
| 1 | substring false positive | `calculated_ocean_properties.nc` matches inside `ds06_calculated_ocean_properties.nc` |

**Stop only for a hit that fits none of those four.** That would be a file the spec classified as unreferenced which some notebook actually reads, and untracking it would break a fresh clone. Finding one is a success, not a failure — reclassify it and say so.

- [ ] **Step 5: Untrack**

Use the null-safe form. Several paths in the untrack list contain spaces (for example `culture_mesocosm_combined_rev_092325 - Copy.xlsx` and `Summary of methods for GDGT analysis.xlsx`), so word-splitting on a bare `$(cat ...)` would corrupt them.

```bash
tr '\n' '\0' < /tmp/texas_untrack.txt | xargs -0 git rm --cached --quiet
git ls-files data/ | wc -l         # expect 68
```

- [ ] **Step 6: Confirm every untracked file is still on disk**

```bash
missing=0
while read -r f; do [ -e "$f" ] || { echo "GONE: $f"; missing=1; }; done < /tmp/texas_untrack.txt
[ "$missing" -eq 0 ] && echo "ALL 97 FILES STILL PRESENT ON DISK"
```

Expected: the `ALL 97` line. `git rm --cached` never touches the working tree, so a `GONE` line means something else deleted it and the task must stop.

- [ ] **Step 7: Commit**

Do not commit yet if Task 8 runs immediately after — the two belong in one commit so the index and the ignore rules never disagree in history. If they are being executed separately, commit here:

```bash
git add -A data/
git commit -m "Untrack the 97 data files no notebook, test, script or the package reads

Files stay on disk. data/README.md (next commit) lists each one with its source.
Tracked data drops from 165 files to 68: 22 training spreadsheets, 45 revision-1
reviewer evidence files, and the README.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 8: Rewrite `.gitignore` from scratch

The current file has three defects that a rewrite fixes at once. Line 89 reads `figures/   # ← uncomment if you want to ignore generated plots too` — git treats the whole string as a literal path, so the rule is a silent no-op and has been since it was written. Lines 92-97 ignore `*.xlsx` and `*.csv` globally, which is why every kept data file needs a negation and why a new CSV anywhere in the repo is invisible by default. And `data/spreadsheets/` on line 91 cannot be negated per-file at all, because git will not re-include a file whose parent directory is excluded.

**Files:**
- Rewrite: `.gitignore`

**Interfaces:**
- Consumes: the untracked set from Task 7, and the two scratch files `/tmp/texas_keep.txt` and `/tmp/texas_untrack.txt` it wrote.
- Produces: the rule that makes Task 12's `git ls-files -i -c --exclude-standard` check meaningful.

**If you are running this task in a session that did not run Task 7**, those two scratch files are gone. Rebuild them before Step 2. The keep list is the 22 `!` lines in the `.gitignore` below, so it can be recovered from this document; the untrack list cannot be recovered from the index after Task 7 committed, so recover it from that commit:

```bash
git show --stat --name-only --diff-filter=D <task-7-commit> -- data/ > /tmp/texas_untrack.txt
grep -oP '(?<=^!)data/spreadsheets/\S+' .gitignore > /tmp/texas_keep.txt
wc -l /tmp/texas_keep.txt /tmp/texas_untrack.txt   # expect 22 and 97
```

- [ ] **Step 1: Write the new file**

```bash
cat > .gitignore <<'EOF'
# ── Python / tooling ──────────────────────────────────────────────────────────
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
*.egg
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

# ── Claude Code: machine-local settings only (agents/ and skills/ are tracked) ─
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

!data/spreadsheets/combined_coretop_culture_mesocosm_rev20260210.csv
!data/spreadsheets/culture_mesocosm_combined_rev_030425.csv
!data/spreadsheets/culture_mesocosm_combined_rev_092325.xlsx
!data/spreadsheets/ds01_updated_global_coretop_tex_revised_011226.csv
!data/spreadsheets/ds03_processed_coretop_tex.csv
!data/spreadsheets/ds_gridded_screened_global_compilation_finalized.csv
!data/spreadsheets/global_hydrothermal_vents.csv
!data/spreadsheets/ols_tex_thermoT_thisStudy.pkl
!data/spreadsheets/revised_cultures_GDGT_github_March2025_RR.xlsx
!data/spreadsheets/texmesocosms.csv
!data/spreadsheets/published_data/Babila_SST_results_finalized_compiled.xlsx
!data/spreadsheets/published_data/ds07_TasmanSea_paleorecords.xlsx
!data/spreadsheets/published_data/Gaskell2022_pnas.2111332119.sd01.xlsx
!data/spreadsheets/published_data/ODP1259_d18O_planktic_Bornemann08_OBrien17compl.xlsx
!data/spreadsheets/published_data/PhanSST_v001_extendedRR_121025.csv
!data/spreadsheets/published_data/PhanTEX_GIG_df.csv
!data/spreadsheets/published_data/PhanTEX_GIG_df.parquet
!data/spreadsheets/published_data/PhanTEX_v001_modified_032626.csv
!data/spreadsheets/published_data/tran2025-u1482-bio-sst.txt
!data/spreadsheets/published_data/U1482_MgCa_SST.xlsx
!data/spreadsheets/published_data/Varma-etal_Co1010.csv
!data/spreadsheets/published_data/NICOPP_d15Nsed_database/nicopp-coretop-data.txt

# Revision-1 reviewer evidence: small, hand-curated result tables that back
# specific responses to reviewers. Losing one means re-running Stan, not
# re-deriving a cache. Tracked in full.
!data/revision1/**
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
!streamlit_app/.streamlit/
EOF
```

Three deliberate departures from the spec's draft, each with a reason:

1. **`!data/spreadsheets/fitted_models/` is dropped.** The spec's draft re-included that directory and then excluded its contents, with no negation inside. The only file in it, `ols_tex_thermoT_thisStudy.pkl`, is the *duplicate* that Appendix A untracks; the copy that stays is the one directly under `data/spreadsheets/`. Two lines that together track nothing are worse than no lines.
2. **`*$py.class`, `*.so`, `.Python`, `*.egg` are carried over** from the current file. The spec's draft dropped them without saying why, and they cost nothing.
3. **`!data/revision1/**` uses a recursive glob, not the bare `!data/revision1/`** the spec's draft had. A bare directory negation re-includes the directory but does not rescue files inside it that an *earlier file-pattern* rule already matched — `*.log` in the Editors/OS section keeps ignoring `data/revision1/**/*.log` until the negation is recursive. Found during execution, verified in isolated repros.
4. **`!streamlit_app/.streamlit/` is added.** `.streamlit/` excludes the parent directory, and git cannot re-include a file whose parent directory is excluded, so the tracked `streamlit_app/.streamlit/config.toml` was unreachable. This bug pre-dates the rewrite: it was already broken under the old `.gitignore`, which is why `git ls-files -i -c` reported 23 rather than 22 before this task.
5. **`*.csv` / `*.xlsx` global rules are gone**, as the spec directs. `.gitattributes` still routes both through LFS, so a newly kept CSV lands in LFS automatically. The `notebooks/*.csv` and `figures/manuscript/**/*.csv` rules replace the parts of the old blanket that were actually load-bearing.

- [ ] **Step 2: Prove the index and the ignore rules agree**

```bash
git ls-files -i -c --exclude-standard
```

Expected: **no output**. Any path printed is a file that is tracked *and* ignored, meaning Task 7 missed it or a negation is wrong. Fix before continuing.

- [ ] **Step 3: Prove every kept file is still visible to git**

**Use `--no-index`. Without it this check is vacuous.** `git check-ignore` documents that tracked files "are not shown at all since they are not subject to exclude rules", so a plain `check-ignore` on a tracked path always reports *not ignored*, whatever the rules say. Every file in the keep list is tracked, so the naive form can never print a warning even if `.gitignore` is badly broken. This was found during execution, after both an implementer and the controller had run the vacuous form and read its silence as confirmation.

```bash
while read -r f; do
  git check-ignore -q --no-index "$f" && echo "RULES WOULD IGNORE: $f"
done < /tmp/texas_keep.txt
echo "keep-list ignore check done"
git ls-files data/ | wc -l          # expect 68
```

Expected: no `RULES WOULD IGNORE` lines.

Note that Step 2's `git ls-files -i -c --exclude-standard` already proves this property rigorously and is the check that actually gates the task. This step is a more legible restatement of it, not an independent proof.

- [ ] **Step 4: Prove the untracked files are now ignored**

```bash
notignored=0
while read -r f; do
  git check-ignore -q "$f" || { echo "NOT IGNORED: $f"; notignored=1; }
done < /tmp/texas_untrack.txt
[ "$notignored" -eq 0 ] && echo "ALL 97 IGNORED"
```

Expected: the `ALL 97` line. A `NOT IGNORED` file would reappear as untracked in `git status` and eventually be re-added by someone's `git add -A`.

- [ ] **Step 5: Confirm the working tree is otherwise clean**

```bash
git status --short
```

Expected: only `.gitignore` modified, plus whatever Task 7 staged if the two are being committed together.

- [ ] **Step 6: Commit**

```bash
git add .gitignore
git commit -m "Rewrite .gitignore: ignore data by default, re-include file by file

Three defects go with the rewrite. Line 89 was 'figures/   # comment', which git
reads as a literal path, so the rule had always been a no-op. The global *.csv
and *.xlsx rules made every kept data file need a negation and hid new CSVs
anywhere in the repo. And data/spreadsheets/ as a directory rule could never be
negated per file, because git will not re-include a file whose parent is
excluded; data/spreadsheets/* can.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 9: Give `data/README.md` a table for every set

97 files just left the repository. Without this, a reader who clones cannot tell which of the paths a notebook opens they are expected to fetch, or from where.

**Files:**
- Modify: `data/README.md`

**Interfaces:**
- Consumes: `/tmp/texas_keep.txt` and `/tmp/texas_untrack.txt` from Task 7. If you are resuming in a session that did not run Task 7, rebuild them with the recovery block in Task 8's Interfaces section before starting.
- Produces: the reference that Task 12's clone test checks against.

- [ ] **Step 1: Read what is already there**

```bash
cat data/README.md
```

Keep whatever is accurate. This task adds tables; it does not start over.

- [ ] **Step 2: Add the four tables**

Add a section headed `## Where every file lives` containing one table per set, each with the columns **filename**, **what reads it**, **where to get it**.

1. **Tracked training data (22 files).** These arrive with a clone via LFS. Source column: "in this repository (LFS)". Populate the "what reads it" column from the reference counts in Appendix A.1 of the spec.

2. **Third-party originals, not tracked (35 files under `data/external/`).** Sources, one per row: NOAA WOA23, GISTEMP, PhanSST, PANGAEA, Scotese and Wright 2018, the Müller 2019 plate model. Where a file has no public source, write "author-only, not needed by any notebook" rather than leaving the cell blank.

3. **TEXAS-derived NetCDFs, not tracked (6 files).** These are outputs of this project that SI_code00 and SI_code03 read back in.

   | file | status |
   |---|---|
   | `ds06_calculated_ocean_properties.nc` | already served from the GRL record via `TRAINING_DATA_REGISTRY["ocean_prop_ds"]`; no upload needed |
   | `Tierney22_PNAS_PETMDA/PETMDA_OCN_annual_regridded.nc` | upload to the Zenodo data record at v1.0.0 |
   | the four `Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/*.nc` | upload to the Zenodo data record at v1.0.0 |

   State plainly that **five files totalling 16 MB need the v1.0.0 upload**, and that `ds04_gridded_coretop_tex_scaledRI.nc` and `calculated_ocean_properties_seasonal.nc` are deliberately dropped without an upload because only the ignored `notebooks/exploration/` read them.

4. **Superseded spreadsheets, not tracked (56 files).** These are earlier revisions of the kept training files plus published datasets that no finalized notebook opens. One row each, with the source where there is one.

Add a short paragraph naming the Zenodo data record DOI `10.5281/zenodo.22131367` as the place the derived files will live.

- [ ] **Step 3: Record the v1.0.0 upload as a Phase C task**

Open `RESUME.md`, find the `### Phase C — v1.0.0` section, and add a checklist line:

```markdown
- [ ] Upload the 5 TEXAS-derived NetCDFs (16 MB) to the Zenodo data record
      10.5281/zenodo.22131367 and add them to `TRAINING_DATA_REGISTRY`:
      `Tierney22_PNAS_PETMDA/PETMDA_OCN_annual_regridded.nc` and the four
      `Zhu19_Science_EoceneSim/fullDepth_regridded_iPETM/*.nc`. They were
      untracked on 2026-09-07 (repo-hygiene plan, Task 7) and SI_code00 and
      SI_code03 read them, so until this lands a fresh clone cannot run those
      two notebooks end to end.
```

- [ ] **Step 4: Verify every filename in the README is real**

A README that names a file that does not exist is worse than no README.

```bash
grep -oE '`data/[^`]+`' data/README.md | tr -d '`' | while read -r f; do
  [ -e "$f" ] || echo "README NAMES A MISSING FILE: $f"
done
echo "README path check done"
```

- [ ] **Step 5: Commit**

```bash
git add data/README.md RESUME.md
git commit -m "Document where every data file lives now that 97 are untracked

One table per set: what stays in the repo, what to download from whom, and the
six TEXAS-derived NetCDFs. Five of those (16 MB) need the v1.0.0 Zenodo upload,
recorded as a Phase C task in RESUME.md, and until it lands a fresh clone cannot
run SI_code00 and SI_code03 end to end.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 10: Clean up `.dockerignore`

Lines 15-43 are a phylogenomics exclusion block pasted from another project. It names `data/phylo/`, GTDB releases, FASTA and MSA files, and `gtdbtk` output directories, none of which have ever existed in this repository.

**Files:**
- Modify: `.dockerignore`

**Interfaces:**
- Consumes: `archive/` from Tasks 2-4, which the new rules exclude.
- Produces: nothing later depends on.

- [ ] **Step 1: Confirm the block is dead**

```bash
ls data/phylo 2>&1              # expect: No such file or directory
find . -name '*.msa' -o -name '*.fasta' -o -name 'gtdb*' 2>/dev/null | grep -v '\.git/' | head
```

Expected: no matches. **If anything turns up, stop** and keep the rules that match it.

Line 10 is dead for the same reason. It ignores `stan_models_explanation_v2.pdf`, a PDF export of a docs page. No such file has ever existed here, and plan 05 renames the page itself to `stan_models.md`:

```bash
find . -name 'stan_models_explanation_v2.pdf' -not -path './.git/*'
```

Expected: no output. The rewrite below drops the line, so plan 05's Task 3 Step 7 will find it already gone and can skip that step.

- [ ] **Step 2: Rewrite**

```bash
cat > .dockerignore <<'EOF'
# Build context exclusions. The image installs TEXAS from conda-lock.yml plus a
# pip line in docker/Dockerfile; nothing below is needed to build it.

.git
**/__pycache__/
**/*.ipynb_checkpoints
.venv/

notebooks/
figures/
outputs/
logs/
archive/
docs/_build/

data/raw/*
data/external/*
data/cache/*
!data/cache/TEXAS_posterior_cache/
!data/cache/TEXAS_invT_posterior_cache/
*.nc

review_archive_v*/
texas-psm-zenodo-v*
legacy_*.tar.gz

*.backup
*.bak
*.old
*~
.DS_Store
Thumbs.db
**/temp/
**/tmp/
**/.cache/
EOF
```

- [ ] **Step 3: Verify the image still builds**

This is the only check that matters. A `.dockerignore` that excludes something the build needs fails at `COPY`, not at lint.

**Build each profile, not the bare command.** `docker/docker-compose.yml` puts every service behind a profile (`app`, `docs`, `full`, `demo`, `si`), so a plain `docker compose build` selects nothing and verifies nothing. Found during execution.

```bash
for p in app docs full demo si; do
  echo "=== profile: $p ==="
  docker compose -f docker/docker-compose.yml --profile "$p" build 2>&1 | tail -8
done
```

Expected: `app`, `docs` and `full` build. **`demo` and `si` are expected to fail on a pre-existing, unrelated bug**: `docker/Dockerfile.demo:14` and `docker/Dockerfile.si:15` both do `FROM ghcr.io/paleolipidRR/texas-base:latest`, and Docker requires lowercase registry paths. That is not this plan's to fix — record it and move on.

**The `data/cache` rules are load-bearing and were nearly wrong.** An earlier draft of this section had a bare `data/cache/*`, which prunes exactly the directories `Dockerfile.si:23,26` and `Dockerfile.demo:22` explicitly `COPY`. The two negations above keep those while still excluding the ~185 MB of regenerable kriged-grid `.npz` files. If the negations do not behave as expected on your Docker version, **drop the `data/cache` rule entirely** — the file being replaced had no such rule and those profiles built, so restoring that is the correct fallback. A working build beats a smaller context. **If Docker is unavailable on this machine, do not skip silently** — record in the commit message that the build was not verified here and add a line to the RESUME.md handoff so it is checked on a machine that has Docker.

- [ ] **Step 4: Commit**

```bash
git add .dockerignore
git commit -m "Drop the phylogenomics block from .dockerignore

Lines 15-43 excluded data/phylo/, GTDB releases, FASTA and MSA files and gtdbtk
output directories. None has ever existed in this repository; the block was
pasted from another project. archive/, logs/, docs/_build/ and the release
staging directories are excluded instead, which are real.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 11: Tag and delete the unmerged branches

Six unmerged remote branches and one local backup. Each is tagged before deletion so nothing is lost, and the tag name says what it was.

**Files:** none. This task only touches refs.

**Interfaces:**
- Consumes: nothing.
- Produces: seven `archived-branch/*` tags on the remote.

- [ ] **Step 1: Record what each branch holds**

```bash
for b in claude/bounded-t-model-revisions-idrogu \
         claude/gridT-gui-exploratory \
         claude/gridt-inversion-characterization-15i183 \
         claude/repo-audit-docs-update-od2dsj \
         claude/version-bump-v0-3-1-pxkvas \
         revision/boundedT-si-figures; do
  echo "=== origin/$b ==="
  git log --oneline main..origin/$b
done
echo "=== local backup/revision1-groupA-prerebase ==="
git log --oneline main..backup/revision1-groupA-prerebase | head
```

Expected ahead-counts from the spec: 1, 12, 2, 3, 1, 4. **If a count differs, someone has pushed since the spec was written** — read the new commits before tagging, and say in the commit message what changed.

- [ ] **Step 2: Tag every branch tip**

```bash
git tag archived-branch/claude-bounded-t-model-revisions       origin/claude/bounded-t-model-revisions-idrogu
git tag archived-branch/claude-gridT-gui-exploratory           origin/claude/gridT-gui-exploratory
git tag archived-branch/claude-gridt-inversion-characterization origin/claude/gridt-inversion-characterization-15i183
git tag archived-branch/claude-repo-audit-docs-update          origin/claude/repo-audit-docs-update-od2dsj
git tag archived-branch/claude-version-bump-v0-3-1             origin/claude/version-bump-v0-3-1-pxkvas
git tag archived-branch/revision-boundedT-si-figures           origin/revision/boundedT-si-figures
git tag archived-branch/backup-revision1-groupA-prerebase      backup/revision1-groupA-prerebase
git tag | grep archived-branch                                 # expect 7
```

- [ ] **Step 3: Push the tags — and only these tags**

```bash
git push origin \
  archived-branch/claude-bounded-t-model-revisions \
  archived-branch/claude-gridT-gui-exploratory \
  archived-branch/claude-gridt-inversion-characterization \
  archived-branch/claude-repo-audit-docs-update \
  archived-branch/claude-version-bump-v0-3-1 \
  archived-branch/revision-boundedT-si-figures \
  archived-branch/backup-revision1-groupA-prerebase
```

**Never run `git push --tags`.** It would push the local-only `v0.2.6`, and `.github/workflows/docker.yml` fires on every `v*` tag, publishing a GHCR image for a version that was never released.

- [ ] **Step 4: Verify each tag is on the remote before deleting anything**

```bash
for t in claude-bounded-t-model-revisions claude-gridT-gui-exploratory \
         claude-gridt-inversion-characterization claude-repo-audit-docs-update \
         claude-version-bump-v0-3-1 revision-boundedT-si-figures \
         backup-revision1-groupA-prerebase; do
  git ls-remote --tags origin "archived-branch/$t" | grep -q . \
    && echo "OK   archived-branch/$t" || echo "MISSING archived-branch/$t"
done
```

Expected: seven `OK` lines. **If any is `MISSING`, stop.** Deleting a branch whose tag did not push is the one irreversible mistake available in this plan.

- [ ] **Step 5: Delete the branches**

```bash
git push origin --delete claude/bounded-t-model-revisions-idrogu
git push origin --delete claude/gridT-gui-exploratory
git push origin --delete claude/gridt-inversion-characterization-15i183
git push origin --delete claude/repo-audit-docs-update-od2dsj
git push origin --delete claude/version-bump-v0-3-1-pxkvas
git push origin --delete revision/boundedT-si-figures
git branch -D revision/boundedT-si-figures
git branch -D backup/revision1-groupA-prerebase
git fetch --prune
git branch -a
```

Expected afterwards: `main`, `origin/main`, `origin/gh-pages`. `gh-pages` is the docs deploy target and stays.

- [ ] **Step 6: Delete the local `v0.2.6` tag**

Its commit is on `main`, so nothing is lost.

```bash
git tag -d v0.2.6
git ls-remote --tags origin v0.2.6      # expect no output, confirming it was never pushed
```

- [ ] **Step 7: Record the tags in RESUME.md**

Add a short table under the current session's heading mapping each deleted branch to its `archived-branch/` tag, so a future session looking for that work knows where it went.

```bash
git add RESUME.md
git commit -m "Archive six unmerged branches as tags, then delete them

Each tip is tagged archived-branch/<name> and pushed before its branch is
deleted, so nothing is lost. gh-pages stays; it is the docs deploy target.
The local-only v0.2.6 tag is deleted rather than pushed, because docker.yml
fires on every v* tag and would publish an image for a version never released.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 12: Verify the whole plan

The spec lists eleven verification items. Five of them belong to this plan; the other six are owned by plans 02 through 05 and are listed here only so nothing is assumed done.

**Files:** none modified. This task only checks.

**Interfaces:**
- Consumes: every earlier task.
- Produces: the evidence that the repo-hygiene half of the finalization is complete.

- [ ] **Step 1: Test suite green**

```bash
.venv/bin/python -m pytest -q
```

Expected: `351 passed, 11 skipped`. A different number is a regression from a move, not an acceptable new baseline.

- [ ] **Step 2: No file is both tracked and ignored**

```bash
git ls-files -i -c --exclude-standard
```

Expected: no output.

- [ ] **Step 3: The release tarball excludes working notes and data**

```bash
git archive HEAD | tar t | grep -E '^(\.claude/|RESUME\.md|CLAUDE\.md|data/external/)'
```

Expected: no output. This relies on `.gitattributes` `export-ignore` entries that already exist and are unchanged by this plan.

- [ ] **Step 4: LFS file count dropped as predicted**

```bash
git lfs ls-files | wc -l
```

Expected: **52**.

**The spec's item 7 says 55 and is wrong.** It reasons "22 spreadsheets + 32 revision1 + 1 figure", but three of the 22 kept spreadsheets are not LFS-tracked at all: `.txt` and `.parquet` match no filter in `.gitattributes`, which routes only `*.nc`, `*.npz`, `*.pkl`, `*.h5`, `*.csv` and `*.xlsx`. Verified on 2026-09-07 against the live index:

| set | LFS files kept |
|---|---|
| `data/spreadsheets/` | 19 of 22 |
| `data/revision1/` | 32 of 45 |
| `figures/manuscript/revision1/` | 1 |
| total | **52** |

The three kept files outside LFS are `nicopp-coretop-data.txt`, `tran2025-u1482-bio-sst.txt` and `PhanTEX_GIG_df.parquet`. They are tracked in git proper, which is correct: they are small, and `.gitattributes` deliberately keeps the `published_data/**/*.txt` files byte-identical to their sources.

A higher number means Task 7 missed something; a lower one means a kept file was untracked by mistake. Cross-check with:

```bash
git lfs ls-files | awk '{print $3}' | cut -d/ -f1-2 | sort | uniq -c
```

- [ ] **Step 5: A fresh clone works within the LFS budget**

This is the check that proves the whole exercise worked. Run it in a temp directory, not in the scratchpad's parent.

```bash
tmp=$(mktemp -d)
git clone --depth 1 file:///home/ronnie-rattan/Documents/GitHub/TEXAS "$tmp/TEXAS-clone"
cd "$tmp/TEXAS-clone"
git lfs pull
git lfs ls-files | wc -l          # expect 52
du -sh .
ls data/spreadsheets/
"/home/ronnie-rattan/Documents/GitHub/TEXAS/.venv/bin/python" -c "import sys; sys.path.insert(0, 'src'); import TEXAS; print(TEXAS.__version__)"
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
```

Expected: the clone completes, `git lfs pull` succeeds without a budget error, and all 22 training spreadsheets are present with real content rather than LFS pointer stubs. Check one:

```bash
head -c 100 "$tmp/TEXAS-clone/data/spreadsheets/texmesocosms.csv"
```

Expected: CSV text. If it starts with `version https://git-lfs.github.com/spec/v1`, the pull did not fetch it.

```bash
rm -rf "$tmp"
```

- [ ] **Step 6: Confirm the layout matches the spec**

```bash
ls
ls notebooks/ figures/manuscript/ scripts/ archive/ src/TEXAS/stan_models/
```

Compare against section 3 of the spec. `notebooks/current/`, `notebooks/superseded/`, `figures/manuscript/superseded/` and `TEXAS-revision/` must all be gone; `scripts/paper/` and the four `archive/` sub-directories must exist.

- [ ] **Step 7: Record what this plan does NOT verify**

The remaining spec verification items belong to other plans. Add them to `RESUME.md` under the current session so they are not assumed done:

| spec item | owner |
|---|---|
| 3. wheel ships the right number of `.stan` files | plan 04 (which lowers it to 7) |
| 5. `jupyter-book build docs/` with no missing-file warnings | plan 05 |
| 6. `papermill` SI_code00 and SI_code03 through their data-loading cells | plan 03 |
| 9. SI_code02 cells 81 and 87 load from the kriged cache folder | plan 02 |
| 10. `src/` reference scan reports zero unreferenced definitions | plan 04 |
| 11. no broken cross-references, `grep -rn cauchy docs/` empty | plan 05 |

- [ ] **Step 8: Push**

```bash
git log --oneline main...origin/main
git push origin main
```

Review the commit list before pushing. This plan produces roughly nine commits, all on `main`.

---

## Self-review notes

**Spec coverage.** Section 4 is Tasks 2-5. Section 5 and Appendix A are Tasks 7 and 9. Section 6.1 is Task 8, 6.2 needs no change by the spec's own finding, 6.3 is Task 10. Section 7 is Task 11. Section 8 is Task 1. Section 10 is Task 12, with the six items this plan does not own routed to their plans in Step 7. Section 5b is plan 02, section 9 is plans 03, 04 and 05. Section 11 is out of scope by definition.

**Corrections to the spec made here.** Four, each argued at the point of use: the `!data/spreadsheets/fitted_models/` negation pair is dropped because nothing inside it is kept; four Python patterns the spec's draft silently dropped are carried over; `.zenodo.json` is set to 9 rather than left for plan 04, because 20 is wrong today; and the expected post-untracking LFS count is 52, not the spec's 55, because three of the 22 kept spreadsheets match no LFS filter in `.gitattributes`.

**Not verified from this machine.** The Docker build in Task 10, if Docker is unavailable. That is the only step that can legitimately be deferred, and it must be recorded rather than skipped.
