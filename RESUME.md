# RESUME — merging completed work back to `main`

**Written:** 2026-08-09 · **Branch when written:** `feat/revision1-validation-groupA` @ `a0b3887`

This file exists so a crash, a closed laptop, or a new session loses nothing.
Every step is copy-pasteable and has a verification command. Work top to
bottom; tick the boxes as you go.

---

## Bootstrap on a different machine (Linux or Windows)

This file is tracked, so it arrives with the clone. Everything below assumes
you have just sat down at a machine that has never seen this work.

```bash
git clone https://github.com/PaleoLipidRR/TEXAS.git && cd TEXAS
git checkout feat/revision1-validation-groupA

# 1. Hydrate Git LFS. THIS IS NOT OPTIONAL — without it, ~97 data files are
#    133-byte pointer stubs and every dataframe silently comes back empty.
git lfs install
git lfs pull

# 2. Verify hydration BEFORE running anything. Must print 0.
git lfs ls-files -n | while IFS= read -r f; do \
  [ -f "$f" ] && [ "$(stat -c%s "$f")" -lt 300 ] && \
  head -c 40 "$f" | grep -q 'git-lfs.github.com/spec' && echo "$f"; done | wc -l

# 3. Environment (conda is canonical; uv/venv also works)
conda env create -f environment.yml && conda activate texas-env
pip install -e .            # editable, or Stan recompiles from scratch every time

# 4. CmdStan must be discoverable, then confirm the whole toolchain
texas-doctor

# 5. Green baseline
pytest -q                   # expect 175 passed
```

**What does NOT travel between machines**, and what to do about it:

| Local-only | Consequence | Fix |
|---|---|---|
| `stash@{0}` (Phase 0 snapshot) | No safety stash elsewhere | Irrelevant once the branch is pushed — the commits are the backup |
| `backup/pre-merge-20260809` | No rollback point elsewhere | Pushed to origin; `git fetch` brings it down |
| Compiled Stan binaries | First sample recompiles (slow, once) | Nothing — expected, and platform-specific anyway |
| `data/cache/**` posteriors | Reconstructions cannot be loaded | `git lfs pull`, `TEXAS.download_posteriors()`, or re-run |
| CmdStan install | Nothing samples | `texas-install-cmdstan` |

> **Never `git stash` in this repo without checking LFS afterwards.** Stashing
> and restoring de-hydrated a 3.6 MB LFS file into a 133-byte stub on
> 2026-08-10. The stub *matches the index*, so the file quietly leaves
> `git status` and looks like it was cleaned up. Re-run the step-2 check after
> any stash/restore, and `git lfs pull` if the count went up.

---

## Where am I?

Run this first, always. The working tree shrinks as you commit, so `git status`
alone tells you which step you are on.

```bash
cd /c/Users/ratta/Documents/GitHub/TEXAS
git status -sb
git log --oneline -8
git stash list          # should be empty; if not, see "Recovery" at the bottom
```

Map the output to a phase:

| `git status` shows | You are at |
|---|---|
| 26 status lines, branch `feat/revision1-validation-groupA` | **Phase 1**, nothing committed |
| fewer status lines, new commits on the branch | **Phase 1**, mid-way — find the first unticked step below |
| only the two 1.8 leftovers, branch unchanged | **Phase 1 done** → go to Phase 2 |
| clean tree, on `main`, `TEXAS-revision/` present | **Phase 2 done** → go to Phase 3 |

Notes on that count:

- `docs/_scripts/` is one status line but three files (28 files total;
  `__pycache__` is gitignored).
- `RESUME.md` never appears — `.gitignore:108` already lists it. It is a local
  working file; delete it when done.
- The two `PhanTEX_*.csv` files dropped out of the count during Phase 0: they
  were stat-dirty only (identical LFS oids `c1658da`/`8fcee58` on both sides)
  and the stash cycle cleaned them. **No content was lost.**

Phase 1's file lists were checked against the working tree: every dirty file is
assigned to exactly one step, none double-assigned, none missed.

---

## STATUS: Phases 0 and 1 are DONE (2026-08-10)

7 commits on `feat/revision1-validation-groupA`, **unpushed**, 175 tests passing.
Safety net in place: `backup/pre-merge-20260809` + `stash@{0}`.

```
ab10ce0 notebook(SI03): model-switchable paleo showcases (additive EIV vs bounded-T)
a9a8d9f data(revision1): revised training spreadsheet, SI notebook updates, regenerated AppendixA
ac4ce3d docs: generated call map, regenerated on every deploy
fc68ae4 feat(predict): fwd_cache_dir to resolve posteriors outside the default cache
06c2e3a feat(naming): CESM-style case names for posteriors, dual-read
30ccdff fix(windows): compile from an ASCII-sanitized copy of the .stan source
c1a75bb feat(boundedT): bounded-T model support across the package
```

**Resume at Phase 2.** Remaining dirty: only the two Phase 1.8 leftovers.

### Three things that happened, for the record

1. **`git stash` de-hydrated an LFS file.** The Phase 0 stash cycle turned
   `PhanTEX_v001_modified_121025.csv` (3.6 MB) into a 133-byte pointer stub, and
   my Phase 0 note wrongly called that "stat-dirtiness cleaned". 75 of 97 LFS
   files were stubs (most pre-existing). Fixed with `git lfs pull` — 296 MB,
   **0 stubs remain**. *Before stashing in this repo, count stubs; after
   restoring, count again.*
2. **`data/spreadsheets/` is gitignored as a directory** — its files are tracked
   individually, so step 1.7 needs `git add -u <file>`, not `git add <dir>`.
3. **`git commit --amend` hit the wrong commit** and merged SI03 into the data
   commit. Recovered with `git reset --soft ac4ce3d` and re-committing the two
   separately. Every commit message now matches its contents (verified).

---

## Phase 0 — safety net (2 min) — DONE

Nothing here is committed yet, so this is the only irreversible state in the repo.

- [ ] **0.1 Make a backup branch pointing at the current commit**

```bash
git branch backup/pre-merge-20260809
git branch --list 'backup/*'
```

- [ ] **0.2 Snapshot the uncommitted work as a stash that stays on the stack**

```bash
git stash push --include-untracked -m "pre-merge snapshot 20260809"
git stash apply          # put it all back; the stash stays as a copy
git stash list           # must show: stash@{0}: On ...: pre-merge snapshot 20260809
git status -sb           # must show the same ~28 dirty paths as before
```

> Why both: the branch protects committed history, the stash protects the
> uncommitted tree. Drop the stash (`git stash drop`) only after Phase 1 is
> fully committed and verified.

---

## Phase 1 — commit the working tree in themed commits

All on the current branch. **Do not switch branches until this phase is done** —
a dirty tree of this size will not survive a checkout cleanly.

Run the test suite once before starting, so you know the baseline is green:

```bash
.venv/Scripts/python.exe -m pytest -q      # expect: 175 passed
```

---

- [ ] **1.1 Bounded-T support across the package**

Covers gamma-vs-beta detection, bounded-T invT model selection, `gamma_*`
parsing in metadata, and `gamma_*` groups in the prior plots. Also carries the
`fwd_cache_dir` and `fwd_case` changes — those are interleaved with the
bounded-T hunks in the same files and cannot be split without `git add -p`,
which this environment cannot run.

```bash
git add src/TEXAS/data/builder.py src/TEXAS/stan/invT.py \
        src/TEXAS/stan/metadata.py src/TEXAS/plotting/prior_plot.py
git commit -m "feat(boundedT): bounded-T model support across the package

Detect gamma_G23/gamma_NO3 in a forward posterior and route to the bounded-T
inverse model automatically, renaming the Stan data keys beta_* -> gamma_*.
Parse bounded parameter declarations in metadata; add gamma_* groups to the
prior plots. Also attaches fwd_case/fwd_posterior_name provenance to invT
posteriors so a reconstruction can be traced to the calibration it used."
```

Verify: `git show --stat HEAD` lists exactly 4 files.

---

- [ ] **1.2 ASCII-safe Stan build copies**

```bash
git add src/TEXAS/stan/compiler.py tests/test_stan_ascii.py
git commit -m "fix(windows): compile from an ASCII-sanitized copy of the .stan source

cmdstanpy opens .stan with the platform locale codec (cp1252 on Windows), so
any non-ASCII byte in a comment raises UnicodeDecodeError at compile time.
Sanitize the disposable build copy only; model sources keep their Unicode.
Tests assert the invariant for every shipped model."
```

Verify: `.venv/Scripts/python.exe -m pytest tests/test_stan_ascii.py -q`

---

- [ ] **1.3 CESM-style case naming**

```bash
git add src/TEXAS/utils/naming.py src/TEXAS/stan/io.py tests/test_naming.py CLAUDE.md
git commit -m "feat(naming): CESM-style case names for posteriors, dual-read

Replace concatenated-description filenames (95-122 chars, growing with every
new axis) with fixed dot-delimited positions: tx.v025.GHEB.sst.ri3.G23-N10.001
as a case directory holding fwd.nc and its inv.*.nc reconstructions.

Nothing on disk is renamed. load_posterior() accepts either a case id or a
legacy long name and finds the file under either layout, so existing caches,
Zenodo downloads, and old notebooks keep working.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

Verify: `.venv/Scripts/python.exe -m pytest tests/test_naming.py -q` → 53 passed.

---

- [ ] **1.4 Forward-cache directory plumbing**

```bash
git add src/TEXAS/predict.py
git commit -m "feat(predict): fwd_cache_dir to resolve posteriors outside the default cache"
```

---

- [ ] **1.5 Docs call map — MUST be one commit**

`docs.yml` invokes `docs/_scripts/build_callmap.py`. Committing the workflow
without the script breaks the docs deploy on `main`. `__pycache__` is already
gitignored, so `git add docs/_scripts/` is safe.

```bash
git add .github/workflows/docs.yml docs/README.md docs/_config.yml docs/_toc.yml \
        docs/_scripts/ docs/callmap.md docs/_static/callmap.html
git status --porcelain -- docs/ .github/     # must be empty
git commit -m "docs: generated call map, regenerated on every deploy

build_callmap.py runs before the book build so the call graph, the
reachability report, and the API cannot drift apart; it fails loudly if
callmap_content.py names a function that no longer exists."
```

Verify: `git show --stat HEAD | grep -c _scripts` → at least 3 (the three script files).

---

- [ ] **1.6 SI03 model-switch notebook**

```bash
git add notebooks/manuscripts/SI03_paleo_showcases_modelswitch.ipynb
git commit -m "notebook(SI03): model-switchable paleo showcases (additive EIV vs bounded-T)

One MODEL_VARIANT flag drives the whole notebook. The active variant fills the
canonical column names so all four manuscript figure cells are unchanged; only
the saved figure filename gains a _boundedT tag. LOAD_BOTH loads the other
variant into *_alt columns to feed the reviewer-comparison section (per-site
delta-T table, 1:1 + residual figure, provenance CSV).

Run and load iterate one NO3_SCENARIOS registry, so a run's filename and a
load's filename cannot drift apart.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

- [ ] **1.7 Revised data and regenerated figures**

The two `PhanTEX_*.csv` files are **stat-dirty only** — their LFS oids are
unchanged (`c1658da -> c1658da`, `8fcee58 -> 8fcee58`). `git add` cleans them
without recording a content change. Only `ds_gridded_...csv` really changed
(2 lines).

```bash
git add data/spreadsheets/ notebooks/manuscripts/SI_code1_PreProcessing_finalized.ipynb \
        notebooks/manuscripts/SI_code2_TEXAS_analysis.ipynb \
        notebooks/manuscripts/SI_code3_paleo_showcases.ipynb \
        figures/manuscript/finalized/main-text/AppendixA_culmesoT_prior_distributions.pdf
git commit -m "data(revision1): revised training spreadsheet, SI notebook updates, regenerated AppendixA"
```

---

- [ ] **1.8 Decide the two leftovers**

```bash
git status --porcelain      # should show only these two
```

1. `.claude/settings.json` — Claude Code project settings, currently untracked
   and **not** gitignored. Either commit it (shares hooks/permissions with
   collaborators) or add `.claude/` to `.gitignore`. Your call.
2. `src/TEXAS/stan_models/invT_gen_logi_fixed_multiv_marginal_unconstrained_boundedT.stan`
   — **do not commit.** It is already on `revision/boundedT-si-figures`,
   byte-identical apart from CRLF vs LF (177-line file, 177-byte size delta).
   Phase 3 brings it in from that branch. Leave it untracked for now.

- [ ] **1.9 Phase 1 gate**

```bash
.venv/Scripts/python.exe -m pytest -q     # expect: 175 passed
git log --oneline -7                      # your 7 new commits
git status -sb                            # only the two leftovers from 1.8
git push origin feat/revision1-validation-groupA
```

Once this is green and pushed, drop the safety stash: `git stash drop`.

---

## Phase 2 — land the free win: the gridT branch

`origin/claude/gridt-inversion-characterization-15i183` is 5 commits, **all new
files** under `TEXAS-revision/`, with **zero overlap** against any other branch
or against your working tree. It is the newest work in the repo (2026-08-01),
unreviewed, and easy to lose track of. Nothing else depends on it.

- [ ] **2.1 Merge it**

```bash
git checkout main && git pull
git merge --no-ff origin/claude/gridt-inversion-characterization-15i183 \
    -m "Merge gridT inversion characterization + explainer"
ls TEXAS-revision/          # 9 files: 6 assets + 3 docs
git push origin main
```

Expected: clean merge, no conflicts. If git reports any conflict, **stop** —
something changed since 2026-08-09 and this plan's assumptions need rechecking.

---

## Phase 3 — reconcile `revision/boundedT-si-figures`

4 commits: the two bounded-T `.stan` files, ~15 regenerated figures, and
`SI_code2`. After Phase 1 it collides on **three** files. Handle each
deliberately — do not let git auto-resolve binaries or notebooks.

- [ ] **3.1 Start the merge and see the damage**

```bash
git checkout main && git pull
git merge --no-ff revision/boundedT-si-figures
git status --short --diff-filter=U       # the conflicted set
```

- [ ] **3.2 Resolve, file by file**

| File | How to resolve |
|---|---|
| `src/TEXAS/stan_models/invT_..._boundedT.stan` | Same content, CRLF only. Take the branch's: `git checkout --theirs <path>` |
| `figures/.../AppendixA_culmesoT_prior_distributions.pdf` | **Binary — you must decide.** Your Phase-1 commit and the branch each regenerated it. Open both and pick the one from the newer `prior_plot.py`. Likely yours (`--ours`), since Phase 1 carries the rewritten plotting code. |
| `notebooks/manuscripts/SI_code2_TEXAS_analysis.ipynb` | Modified on both sides. Do **not** take either blindly — diff the cell sources first (see command below) and merge by hand. |

```bash
# inspect the notebook conflict without drowning in output/base64
git show :2:notebooks/manuscripts/SI_code2_TEXAS_analysis.ipynb > /tmp/ours.ipynb
git show :3:notebooks/manuscripts/SI_code2_TEXAS_analysis.ipynb > /tmp/theirs.ipynb
.venv/Scripts/python.exe - <<'EOF'
import json
for tag, p in (("OURS", "/tmp/ours.ipynb"), ("THEIRS", "/tmp/theirs.ipynb")):
    nb = json.load(open(p, encoding="utf-8"))
    print(tag, len(nb["cells"]), "cells")
EOF
```

- [ ] **3.3 Finish**

```bash
.venv/Scripts/python.exe -m pytest -q      # expect 175 passed
git add -A && git commit
git push origin main
```

`pyproject.toml` is **not** a real conflict: this branch and groupA both bump
0.2.5 → 0.2.6 identically.

---

## Phase 4 — PR #15

- [ ] **4.1 Read the recommendation, then decide**

PR #15 ("Revision-1 analysis workflow: Group A + hand-off plan") has been open
since 2026-07-15. The branch has moved 6 commits past where it opened, and
Phase 1 adds 7 more → **22 commits**, against a 2026-09-08 deadline.

**Recommendation: split.** Themes 1.3 (naming), 1.5 (docs call map) and 1.6
(SI03 notebook) are independent of the Group-A validation work and touch
disjoint files. Cherry-pick each onto its own branch off the updated `main`,
open three small PRs, and leave #15 as what it claims to be.

```bash
# after Phases 2 and 3, main is current
git checkout main && git pull

git checkout -b feat/case-naming main
git cherry-pick <sha of 1.3>
git push -u origin feat/case-naming

git checkout -b docs/callmap main
git cherry-pick <sha of 1.5>
git push -u origin docs/callmap

git checkout -b notebook/si03-modelswitch main
git cherry-pick <sha of 1.6>
git push -u origin notebook/si03-modelswitch
```

Get the SHAs with `git log --oneline -7 feat/revision1-validation-groupA`.
These three commits touch files nothing else touches, so the cherry-picks
should be clean.

- [ ] **4.2 Rebase what's left of #15 onto the updated main and re-request review**

---

## Known gaps — not blockers, but do not forget

- [ ] **Bounded-T forward grid is incomplete.** `boundedT_thermoT_gdgt23ratio_no3_1.0`
      does not exist; the additive model has it. The thermoT variant comparison
      is incomplete until you fit it. The preflight cell in SI03 prints this.
- [ ] **No paleo-site invT posteriors are cached.** All 72 files in
      `TEXAS_invT_posterior_cache/` are `global_coretop_b*` CV blocks — nothing
      for U1482, MD98-2152, ODP959, etc. SI03's load cells will report
      everything missing until you run `download_posteriors()` or set
      `RUN_INVT = True`.

---

## Facts already established (do not re-derive)

- All three branches are **0 commits behind `main`** — no rebasing needed to merge.
- `backup/pre-pull-20260731` is 2 behind main and fully superseded; safe to delete.
- Branch file-overlap: gridT ∩ groupA = **∅**; boundedT-si-figures ∩ groupA =
  `pyproject.toml` only (identical version bump).
- Working tree ∩ boundedT-si-figures = the 3 files listed in Phase 3.
- Naming scheme verified against all 17 cached forward posteriors: 0 case-id
  collisions, 0 round-trip failures, dual-read resolves by either name under
  either layout.
- Baseline test count: **175 passed** (122 before this work + 53 new).

## Recovery

| Symptom | Fix |
|---|---|
| Wrong files in a commit | `git reset --soft HEAD~1`, re-stage, re-commit |
| Working tree lost | `git stash list` → `git stash apply stash@{0}` (Phase 0.2) |
| Commits lost | `git reflog`, or `git reset --hard backup/pre-merge-20260809` |
| Merge going badly | `git merge --abort` — always safe before you commit the merge |
| Cherry-pick conflict | `git cherry-pick --abort` and merge the branch instead |
| Tests fail after a merge | `git log --oneline main..HEAD` to see what came in; suspect `builder.py`/`invT.py` first — they carry the most interleaved changes |
