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

> ### CHECK THIS FIRST ON EVERY MACHINE: the LFS smudge filter
>
> On 2026-08-10 this repo's `.git/config` was found overriding the global LFS
> filter with `--skip`:
>
> ```
> filter.lfs.smudge  = git-lfs smudge --skip -- %f
> filter.lfs.process = git-lfs filter-process --skip
> ```
>
> `--skip` means LFS content is **never materialized on checkout**, so every
> `git checkout`, branch switch, stash apply, and merge silently writes 133-byte
> pointer stubs instead of data. It is almost certainly a leftover from the July
> LFS-over-budget period. This was the root cause of every LFS symptom in that
> session — the stash de-hydration, files turning back into stubs after a
> `git checkout --`, and the historical 88-of-97.
>
> Diagnose and fix (repo-local, so it must be done on each clone):
>
> ```bash
> git config --show-origin --get filter.lfs.smudge   # want the GLOBAL one, no --skip
> git config --unset filter.lfs.smudge               # only if it shows --skip
> git config --unset filter.lfs.process
> git lfs pull
> ```
>
> Verify with the stub count above (want 0), then confirm a checkout no longer
> stubs: delete an LFS file, `git checkout --` it, and check its size.

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

## HANDOFF — 2026-08-12, refit DONE and READY (read this first)

The refit **finished at 16:20** and the audit passed. The main-text figures were
re-run against it and are committed. Everything below this section predates the
refit; this section is the current state.

```bash
python scripts/run_manuscript_refits.py audit        # re-run the audit any time
cat data/revision1/groupA/manuscript_refit/comparability_audit.json
cat data/revision1/groupA/manuscript_refit/case_ids.json
```

### What ran, and what it produced

`scripts/run_manuscript_refits.py all` — started 14:07, **done in 1:54:52**,
**71 runs = 7 forward + 64 reconstructions**. It refit every manuscript case at
one budget so the parent additive-EIV and bounded-T arms differ in the model and
nothing else.

- Forward **400/1000**: not the cheapest cell for any single model, but the
  cheapest clearing all four gates for all three. A per-model budget would
  sample the two arms differently, which is a confound in exactly the
  comparison being made.
- Inverse **500/1000, M=300**.
- Seed 42, 4 chains, proxy `scaledRI_cren3`, NO3 cutoff 1.0, both SST and
  thermoT.

**The comparability audit reports READY — all 15 checks ok.** The ones that
carry the argument:

| check | result |
|---|---|
| one forward budget / one inverse budget | 400/1000 · 500/1000, M=300 |
| both arms fitted, SST **and** thermoT | `['bnd', 'eiv']` for each |
| identical training rows across arms | n_obs = 1513, both targets |
| identical `R2_thermal` across arms | 0.74558 (SST), 0.75711 (thermoT) |
| every reconstruction paired across arms | 0 unpaired |
| reconstructions used *this* run's calibrations | 0 used a legacy name |
| no date stamps in filenames | 0 stamped |
| strict R-hat gate on forward posteriors | no failures |

The seven case ids it wrote (`case_ids.json`) are **already the short form** —
the version token is gone, so that decision has landed in what is on disk:

```
culmeso|cultureT  tx.GCDU.cul.sri03.p0
univ|SST          tx.GHPU.sst.sri03.p0        univ|thermoT  tx.GHPU.thm.sri03.p0
eiv|SST           tx.GHEA.sst.sri03.G23-N10   eiv|thermoT   tx.GHEA.thm.sri03.G23-N10
bnd|SST           tx.GHEB.sst.sri03.G23-N10   bnd|thermoT   tx.GHEB.thm.sri03.G23-N10
```

Rerunning is resumable and safe to interrupt: every completed run is already in
`manifest.csv` and is skipped. `kill -TERM <pid>` finishes the run in flight,
writes it, and exits; a second signal aborts. The lockfile is
`data/revision1/groupA/manuscript_refit/.run.lock`, and the script refuses to
start while the sensitivity sweep holds its own lock — two Stan jobs on this
box share one binary cache and one set of cores.

### Figures re-run against the refit — committed 2026-08-12

SI03 now runs **both** temperature targets, not SST alone: the GIG run plan goes
28 → 56 Stan runs and all 56 invT posteriors load. Four bounded-T panels were
written from it and committed beside the additive-EIV originals rather than over
them (`figures(boundedT): main-text panels from the post-refit posteriors`):

`fig7` calibration curves · `fig11` Tasman Sea · `fig12` GIG · `fig13` PETM

The SI sweep panels under `figures/manuscript/revision1/` are committed too.

**SI03 stops at the extreme-RI load cell** (cell 78, `In[63]`):
`data_list_extreme_example.pkl` is not in this machine's posterior cache, so 13
cells below it never ran. It is a missing input, not a broken cell — `fig14`
dates from 07-06 and was made elsewhere.

### What this does NOT disturb

`SI_code3_paleo_showcases.ipynb` is the **original submission's** paleo
analysis. Nothing it reads is overwritten: forward refits take the next free
member (`.002` beside `.001`) and the reconstructions carry new scenario tags,
so the date-stamped files it loads stay exactly where they are.

`SI03_paleo_showcases_modelswitch.ipynb` is the **revision** notebook and is
what the refit feeds. It has been switched to the case ids and re-run; its load
cells now find all 56 reconstructions.

### Naming changed: no more dates in filenames

The run date is now recorded in the **`run_timestamp` attr** instead. It was
not recorded anywhere before — the date lived only in the filename, so this had
to be added first or the date would have been lost outright.

The date was also doing collision-avoidance, which the **run/member token** now
does properly: `save_posterior(run="auto")` takes the next free member, so a
refit lands beside the run it repeats rather than on top of it. Because a
legacy name pins no member, `resolve_posterior_path` now returns the **newest**
member — an ascending scan would have served the first fit of a configuration
forever, silently, since nothing downstream reports which member it loaded.

SI03's NO3 scenarios are named rather than dated (`no3_modern`, `no3_01`,
`no3_001`, `no3_10`). Stripping the date exposed that it was load-bearing: the
modern-NO3 scenario's tag *was* the bare date.

### Post-refit cleanup — FLATTEN the cache, then dedupe (decided 2026-08-12)

Two decisions, both to run once the refit lands. Neither is safe mid-run: the
job writes into this cache, and a restart under changed layout code would give
one refit two layouts.

**0. Drop the version token, in the same change.** Decided 2026-08-12. `v026`
is `TEXAS.__version__` with separators stripped, and the pip version is the
wrong signal for what that position does — wrong in both directions. A
docs-only release bumps it and orphans every existing case directory, because
resolution matches the token as an exact string (verified, not hypothetical).
A `.stan` prior change without a release does not bump it, so two genuinely
incompatible posteriors share one identity — and CLAUDE.md logs several such
changes (Q removal 2026-03-24, the `sigma_proxyObs_crtp` prior 2026-04-08).

The position existed for collision avoidance. **The run/member token now does
that job properly**: two fits of one configuration get `.001` and `.002`
whatever the reason they differ. So the version is removed from the name and
recorded as a `texas_version` attr beside `run_timestamp`.

```
tx.GHEA.sst.sri03.G23-N10.001.fwd.nc          <- 29 chars, from 41
```

Accepted tradeoff: two Zenodo deposits from different paper versions could each
carry `...001.fwd.nc` for one configuration from different model code. Zenodo's
DOI versioning covers it, since a reader downloads one deposit.

- [ ] `CaseName.version` removed from the dotted form; `default_version()`
      retired or kept only to populate the attr
- [ ] `parse_case()` accepts BOTH forms — every case id on disk and in the
      notebooks has `v026` in it, so parsing must stay backward compatible
- [ ] `texas_version` written in `extract_and_update_metadata` alongside
      `run_timestamp`
- [ ] the `case_id` attr and `case_ids.json` regenerate to the short form

**1. Flatten both caches.** Today they hold two layouts at once — forward 17
flat + 18 in case directories, invT 35 flat + 46 in 6 directories — which is
the confusion this fixes. The case directory earns nothing: the leaf already
carries the whole case id, so it is self-identifying either way, and the
directory only repeats it. Flat also matches Zenodo, halves the path (72 -> 41
chars), and still groups a calibration with its reconstructions, because
`...001.fwd.nc` and `...001.inv.<site>.nc` sort adjacent.

Target:

```
data/cache/TEXAS_posterior_cache/tx.v026.GHEA.sst.sri03.G23-N10.001.fwd.nc
data/cache/TEXAS_invT_posterior_cache/tx.v026.GHEA.sst.sri03.G23-N10.001.inv.U1482.ud.nc
```

Order of work:

- [ ] `naming.fwd_relpath()` / `inv_relpath()` return a bare leaf, not
      `<case>/<leaf>`
- [ ] `resolve_posterior_path()` gains the flat-leaf candidate and KEEPS the
      two directory forms, so nothing on disk has to move for reads to work
- [ ] `next_free_run()` scans flat files as well as directories — it currently
      only looks at directories, so after flattening it would restart at .001
      and collide
- [ ] `io._generate_filename_base()` drops its `<case>/` prefix
- [ ] `download.py::_local_dest()` becomes the identity function
- [ ] `migrate_cache_layout.py --flatten` to move what exists, dry-run first
- [ ] tests: a flat leaf resolves, a directory leaf still resolves, members
      still increment

**2. Dedupe.** At least three known duplicate pairs, all from the old
date-stamping:

- `..._eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc` and its `_041626_eiv`
  twin — identical statistics, so almost certainly identical draws
- `tx.v026.GCDU.cul.ri3.none.001/fwd.nc` vs `...cul.sri03.p0.001/` — verified
  byte-identical draws
- `tx.v026.GHPU.sst.ri3.none.001/fwd.nc` vs `...sst.sri03.p0.001/` — draws
  DIFFER; the new one is today's 400/1000 refit, so keep that and retire the
  old, but decide deliberately rather than by script

Compare draws, not file size, before deleting anything: two of the three pairs
differ in bytes while agreeing in content.

### Done since the refit landed (2026-08-12)

- [x] Ran `audit` — **READY**, 15/15. `case_ids.json` written.
- [x] **Pointed SI03 at the case ids** (decided 2026-08-12: case ids are the
      canonical identity from the resubmission on). Its `fwd_name()` built
      legacy names, and a legacy name cannot reach the refit posteriors at all:
      the cache holds 17 flat files with exactly those names, and an exact flat
      hit is the first thing `resolve_posterior_path` tries — so SI03 was
      silently loading the pre-refit fits.
      **Do not delete the flat files** — `SI_code3_paleo_showcases.ipynb`, the
      original submission, reads them. They are the compatibility layer; new
      work names case ids explicitly.
- [x] Re-ran SI03's figure cells against the new posteriors; four bounded-T
      panels committed.
- [x] **Filled the bounded-T grid.** `run_manuscript_refits.py` fits each arm
      with the full predictor set only, so bounded-T had 2 of the 6 cells the
      additive arm has, and SI_code02's five-layer prior figures were two
      layers short. `scripts/fit_boundedT_single_predictors.py` fitted
      `tx.GHEB.{sst,thm}.sri03.{G23,N10}` at the refit's budget, loading
      culmeso and the univariate baseline **from the refit manifest** rather
      than resampling. All 0 divergences, max R-hat 1.0096. It writes its own
      manifest, so `audit` still reports READY 15/15.
- [x] **Put SI_code02 on case ids.** 21 name sites across 10 cells. This was
      not tidiness: legacy names hit the surviving flat files first, so those
      figures were mixing a pre-refit culmeso and univariate baseline with a
      post-refit bounded-T layer, silently (culmeso t0 35.80 vs 35.64).
- [x] **SI03 runs clean end to end (cells 0-88, 0 failures).** fig11-14 all
      regenerated in one pass from the audited cache. The fig14 cell held two
      more dead names: one raised, and one -- the `draws_tag` -- failed
      SILENTLY into a Gaussian fallback, so the KDE branch had been dead. Both
      sites now plot real posterior KDEs (4000 draws).
- [x] **Rebuilt the extreme-RI section of SI03.** Its generator was pinned to a
      date-stamped posterior that no longer exists. Now case ids, both arms,
      per-variant pickles that do **not** collide with SI_code3's. bounded-T
      moves ODP1259 by 3.33 degC and Co1010 by 0.38 degC.

### Still open when you get back

- [ ] **`AppendixA_culmesoT_prior_distributions_boundedT.pdf` is stale** —
      written 17:29 on 2026-08-12, before the four single-predictor fits landed
      and from the pre-rename cell sources. Regenerate from SI_code02.
- [ ] **Under-coverage in the inverse model.** Part 3 found 68% intervals
      containing measured SST only 59-61% of the time and 90% intervals 84%,
      stable across all nine cells so it is not noise. Partly by construction
      (constant prior, in-sample, stress-weighted subset) but it deserves an
      explanation before it reaches an SI.
- [ ] **The invT drift floor rests on one seed replicate** (0.271 degC). Two or
      three more would make the "budget does not matter" claim rigorous.
- [ ] Phase 5A: `inv_relpath()` is still dead code with a competing leaf format.
- [ ] The branch is **6 commits behind `main`** (and 75 ahead) — merge before
      opening any PR.
- [x] **DOI reconciled 2026-08-12.** `data/README.md` cited `19666745` while
      `README.md`, `CITATION.cff` and `download.py` used `20032542`. Aligned on
      `20032542`, which `download.py` documents as the currently published
      record and actually fetches from. **Check this if 19666745 was the
      *concept* DOI** (all-versions) rather than a superseded version DOI — in
      that case the right move is the opposite one, and citing the concept DOI
      is better practice. Could not verify from here without network access.
- [ ] `streamlit_app/pages/calibration_data.py` reads `post["Q_crtp"]`, and Q
      was removed from every Stan model on 2026-03-24. That page is broken
      against any current posterior.

### Uncommitted, deliberately

`SI_code2_TEXAS_analysis.ipynb` and the regenerated
`AppendixA_culmesoT_prior_distributions.pdf` are live edits — the run cells were
uncommented and one switched to a case id. Left alone; commit when you are happy
with them.

---

## STATUS: Phases 0, 1 and 2 are DONE — resume at Phase 3 (2026-08-10)

> ### Handoff — Linux box → Windows, 2026-08-11
>
> Written at the end of a Linux session so the Windows machine can pick up cold.
>
> **Do this first on Windows**, before trusting any dataframe:
>
> ```bash
> git checkout feat/revision1-validation-groupA && git pull
> git config --show-origin --get filter.lfs.smudge   # must be the GLOBAL one, NO --skip
> ```
>
> The Linux clone's `.git/config` had the `--skip` smudge override described
> below; it was **unset there on 2026-08-11** and LFS is fully hydrated (0/99
> stubs). That fix is **per-clone and does not travel** — assume Windows still
> has it until you have checked. The GitHub **LFS budget is restored**, so
> `git lfs pull` works again; the Zenodo fallback is no longer required.
>
> **What changed in this session** — documentation only, no code touched:
> - **Phase 5 was rescoped.** It used to say "rename the `.stan` model files".
>   That was a mistake: the target is the **posterior `.nc` filenames** (up to
>   118 chars). Phase 5 is rewritten around that, with four verified defects
>   (5A–5D) found by auditing the code and the live cache rather than by reading
>   docs. The `.stan` rename is *out of scope*.
> - **A "fact" in the do-not-re-derive list was wrong** and is struck through:
>   the forward cache has **2 case-id collisions**, not 0. Anything that migrates
>   the cache must be blocked until Phase 5C lands.
> - The invT-cache "known gap" is **machine-dependent** and was stated as
>   universal; both machines' contents are now recorded side by side.
>
> **Verified on Linux, 2026-08-11:** `texas-doctor` → Stan sampling READY;
> `pytest -q` → 173 passed, 2 skipped (the "175" below counts the 2 Windows-only
> skips as passes — expect the same total, split differently, on Windows).
> Note the editable install's metadata had gone stale at 0.2.1, which is why
> `texas-doctor` was missing as a command; `pip install -e . --no-deps` fixed it.
> **If a console script is missing on Windows, that is the first thing to try.**
>
> Stale local branches were deleted on the Linux box only (`working-branch`,
> `archive/laptop-before-merge`, `restructure-repo`, `tutorial`, local
> `gh-pages`) — all verified superseded. Windows may still list them.

Everything below is **pushed to origin**. Nothing important lives only on one
machine any more; you can pick this up from any clone.

- `feat/revision1-validation-groupA` @ `3e72cd8` — 9 commits, 175 tests passing
- `main` @ `d70405a` — gridT merged (Phase 2), 85 tests passing
  (85 not 175 is correct: `test_naming.py` + `test_stan_ascii.py` are 90 tests
  that live on the feature branch, not yet on main)
- `backup/pre-merge-20260809` @ `a0b3887` — rollback point, on origin
- The Phase 0 stash was verified redundant against the pushed commits, then dropped

**The feature branch is now 6 commits behind `main`.** Merge or rebase before
opening PRs in Phase 4.

Two commits beyond the original 7, both for cross-machine portability:

- `chore: normalize line endings deterministically across platforms` — adds
  `* text=auto` so a Windows clone (`autocrlf=true`) and a Linux clone
  (`autocrlf=false`) cannot commit the same file with different endings.
  Third-party `published_data/**/*.txt` excluded to stay byte-identical.
  Verified zero churn via `git add --renormalize .`.
- `docs: track RESUME.md as the cross-machine handoff note` — this file used to
  be gitignored as scratch, so the plan could not follow the work to the Linux
  boxes. Now tracked, with the bootstrap section above.

```
ab10ce0 notebook(SI03): model-switchable paleo showcases (additive EIV vs bounded-T)
a9a8d9f data(revision1): revised training spreadsheet, SI notebook updates, regenerated AppendixA
ac4ce3d docs: generated call map, regenerated on every deploy
fc68ae4 feat(predict): fwd_cache_dir to resolve posteriors outside the default cache
06c2e3a feat(naming): CESM-style case names for posteriors, dual-read
30ccdff fix(windows): compile from an ASCII-sanitized copy of the .stan source
c1a75bb feat(boundedT): bounded-T model support across the package
```

**Resume at Phase 3.** Working tree is clean. Phase 1.8's two leftovers are
resolved: the bounded-T inverse `.stan` is now committed (the branch was not
self-contained without it — a fresh clone could not run
`MODEL_VARIANT="boundedT"` at all), and `.claude/settings.json` is gitignored
as a machine-specific allowlist.

### SI03 is ready to run

Verified by executing cells 0–31 headlessly on 2026-08-10:

- LFS hydrated (0 stubs / 97), all deps present, `texas-doctor` → **READY**
- Paths resolve on any machine (repo root by `pyproject.toml`; OneDrive by
  searching `~/OneDrive*` for `Postdoc/WOA23`)
- With `TEMP_PARAMS = ["SST"]`: the run plan reports **28 Stan runs** and the
  load cell looks for **exactly 28 files** — run and load agree
- With `thermoT` added: **44 runs, 12 skipped**, reported up front, because the
  bounded-T thermoT (g23+no3) forward posterior does not exist

Nothing is cached for the paleo sites, so every column is NaN until you set
`RUN_INVT = True`. `data/cache/` is gitignored — those posteriors were never in
git and cannot come from LFS or Zenodo. They must be generated, on whichever
machine you choose.

Sample counts: MD98-2152 200, U1482 259, DSDP591 46, U1510 43, ODP959 371,
South Dover Bridge 53.

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

## Phase 2 — land the free win: the gridT branch — DONE

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
| `src/TEXAS/stan_models/invT_..._boundedT.stan` | Now committed on the feature branch too, so this is a **same-content** conflict (CRLF only). Take either: `git checkout --theirs <path>` |
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

## Phase 5 — shorten and systematize the posterior `.nc` filenames

> **Scope correction (2026-08-11).** An earlier draft of this phase described
> renaming the 17 `.stan` model sources. That was a mistake — **the `.stan`
> files are not the problem and are not in scope.** The artifacts that need
> shortening are the **posterior `.nc` output files**, whose names run to 118
> characters and grow with every new axis. The `.stan` rename is a separate,
> optional idea; if it is ever revisited it must be its own phase, because it
> carries a full-recompile cost and six silent string-parsing hazards that the
> `.nc` work does not.

### The problem, measured

Today's cache on this Linux box: **17 forward + 35 inverse `.nc`, and zero case
directories.** Worst offender at 118 characters:

```
MD98-2152_invT_gen_logi_fixed_multiv_unconstrained_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_no3_001_direct.nc
```

The CESM-style scheme already exists in `src/TEXAS/utils/naming.py` (605 lines)
and compresses hard — forward names measured across all 17 files:

| | legacy | case id |
|---|---|---|
| shortest | 49 | 27 |
| longest | 104 | 32 |

```
tx.v026.GHEA.sst.ri3.G23-N10.001/       <- the case = one calibration identity
    fwd.nc                              <- the forward posterior
    inv.U1482.ud-050126.nc              <- a reconstruction derived from it
```

**So the scheme is not what is missing. The wiring is.** The forward half works;
the inverse half is written but not connected, and nothing on disk has moved.

### Decided and implemented 2026-08-11 (commit follows this file)

Four naming decisions, all landed with tests, none of them touching the
published Zenodo record:

| axis | was | now | why |
|---|---|---|---|
| leaf name | `fwd.nc` | `<case>.fwd.nc` | a bare leaf loses its identity the moment it is copied out, and Zenodo's namespace is flat |
| proxy code | `ri3` | `sri03` | `ri3` read as "ring index variant 3"; it means *scaled* RI with crenarchaeol counted as **3 rings** |
| no predictors | `none` | `p0` | reads as a value next to `.001`; position kept, CESM-style, because fixed positions are what make the id parseable |
| `TEXRI_cren3` | `ri3` | `tri03` | it shared a code with `scaledRI_cren3`, collapsing two distinct proxies onto one case id |

Old spellings still **parse**, so the case directories already on disk resolve;
they are simply no longer written. `download_posteriors()` now unpacks a flat
Zenodo file into its case directory, so the local cache is one uniform layout
whether a posterior was sampled here or downloaded.

**Honest accounting on the leaf change:** it is *not* free. Full path goes
39 → 72 chars against a bare `fwd.nc`. The leaf — the part you publish and
read — goes ~100 → ~41. The genuinely free option was dropping the case
directory entirely and going flat; the directory was kept because it groups a
calibration with its reconstructions and gives one local layout.

`scripts/migrate_cache_layout.py` does the eventual move. **Dry-run by
default**, refuses on any collision, copies-and-verifies before pruning, and
skips inverse posteriors entirely (see 5D).

### What is actually broken — verified 2026-08-11, not from reading docs

- [ ] **5A `inv_relpath()` is dead code in production.** It is the documented
      canonical inverse-name builder, exported in `naming.__all__`, and
      **nothing outside `tests/test_naming.py` calls it.** The real save path is
      `io._generate_filename_base()` (`stan/io.py:316`), which reimplements a
      *different* leaf format inline:

      | | produced |
      |---|---|
      | `inv_relpath()` | `inv.<site>.<cc><k>[-<scenario>]-<NNN>.nc` |
      | `_generate_filename_base()` | `<case>/inv.<site>.<cc><k>[-<tag>]` |

      The production path has **no run number** and folds scenario and run into
      one undifferentiated tag list. Two spellings of one format is how a naming
      scheme rots. Fix: delete the inline branch and call `inv_relpath()`.
      Verify: `tests/test_naming.py:301-323` currently asserts the *inline*
      behaviour, so those two tests must be updated in the same commit.

- [ ] **5B `save_invT_posterior()` is entirely case-unaware.** The public,
      `__all__`-exported entry point (`stan/io.py:269`) builds
      `f"{site}_{name}_{ttype}.nc"` by hand. It never consults `fwd_case`, never
      calls `_generate_filename_base`, and **silently drops `proxy_name`** — so
      a `scaledRI` and a `TEX86` reconstruction of the same site overwrite each
      other. Two invT save paths disagreeing is worse than either alone. Route
      both through one function.

- [ ] **5C Forward case ids collide — 2 of 17 today.** `case_from_attrs()`
      defaults the run/member token to `.001`, and `filename_suffix` is **not
      recoverable from the attrs**, so a refit and its original land on the same
      id:

      ```
      ..._SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc              -> tx.v026.GHEA.sst.ri3.G23-N10.001
      ..._SST_gdgt23ratio_no3_1.0_scaledRI_cren3_041626_eiv.nc   -> tx.v026.GHEA.sst.ri3.G23-N10.001
      ```

      (Same collision on the `thermoT` pair.) Migrating in this state would
      **destroy one posterior of each pair.** Fix: persist the run token as an
      attr (`case_run`) at save time so it survives a round-trip, and have the
      migration script derive it from the legacy date stamp for existing files.
      A migration must refuse to run while any collision remains.

- [ ] **5D The 35 cached invT posteriors have no recoverable parent.** Checked
      every one: **0 of 35 carry a `fwd_case` attr.** Worse, it cannot be
      reconstructed from the filename — an invT model name records curve,
      structure and constraint (`gen_logi_fixed_multiv_unconstrained`) but
      **not the training set or estimator**, which is exactly what the compset
      encodes. `build_invT_inputData` attaches `fwd_case` now (`stan/invT.py:311`),
      so anything run from today forward is fine; these 35 predate it.

      **Recommendation: do not migrate them.** Leave them under legacy
      dual-read, which already works, and let them age out as sites are re-run.
      Guessing a parent case by matching temptype + predictors would be a guess
      recorded as provenance — the one thing a naming scheme must never do.

- [ ] **5E Zenodo is the freeze point.** Unchanged and still the schedule
      driver. `utils/download.py:79` hardcodes five posterior filenames exactly
      as published on `10.5281/zenodo.20032542`:

      ```
      "filename": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc"
      ```

      Those are what every reader of the paper downloads. A published DOI's
      files cannot be renamed in place; changing them means a new deposit
      version, and the accepted paper's data-availability statement points at
      whichever version it cites. **The `.nc` naming must be final before the
      deposit the paper cites, and is frozen forever after.**

- [ ] **5F Migration script + doc sweep.** Only after 5A–5C. A
      `scripts/migrate_cache_layout.py` that is **dry-run by default**, refuses
      to proceed on any collision, copies rather than moves until verified, and
      reports every source → destination. Then update the hardcoded long names
      in `docs/index.md`, `docs/stan_models_explanation_v2.md` (4 names),
      `CLAUDE.md`, and `SI_code2` / `SI_code3` (7 names between them).

> **Also unresolved:** `data/README.md` cites DOI `10.5281/zenodo.19666745`
> while `README.md`, `CITATION.cff` and `download.py` use `20032542`. Reconcile
> before submission regardless of the naming decision.

### Recommended schedule against the 2026-09-08 deadline

- **Now → submission: 5A + 5B + 5C only, and rename nothing.** All three are
  bug fixes wearing a refactor's clothes — a dead canonical function, a public
  API that silently overwrites on `proxy_name`, and an id collision that would
  eat data the moment anyone migrates. They are invisible to reviewers, touch
  no file on disk, cost no recompile, and have zero Zenodo impact. They also
  make the revision reruns *safer*, because every new posterior written from
  here on gets a correct, collision-free identity.
- **After submission, before the final archive: 5F + the Zenodo re-deposit** in
  one dedicated session. Migrating mid-revision buys nothing a reviewer sees
  and risks the final figures.
- **5D stays "do nothing" permanently** unless those 35 sites get re-run anyway.

> **Cached posteriors keep their old `stan_model_name` and their old flat
> filenames.** That is intended — dual-read already handles both layouts, and
> the attr records what was actually run.

---

## Known gaps — not blockers, but do not forget

- [ ] **Bounded-T forward grid is incomplete.** `boundedT_thermoT_gdgt23ratio_no3_1.0`
      does not exist; the additive model has it. The thermoT variant comparison
      is incomplete until you fit it. The preflight cell in SI03 prints this.
- [ ] **invT cache contents differ per machine — `data/cache/` is gitignored, so
      it does not travel.** Check before trusting either statement below.
      - *Windows box, when this was written:* 72 files, all `global_coretop_b*`
        CV blocks, no paleo sites. SI03's load cells report everything missing
        until you run `download_posteriors()` or set `RUN_INVT = True`.
      - *Linux box, 2026-08-11:* the opposite — **35 files, all paleo sites**
        (Co1010, DSDP591, MD98-2152, ODP1172, ODP1259, ODP959, SDB, U1482,
        U1510, WL), and **no** `global_coretop_b*` CV blocks at all. So the CV
        outputs are the ones missing here.

      Neither machine has both sets. Run `ls data/cache/TEXAS_invT_posterior_cache/`
      first and believe that, not this file.

---

## Facts already established (do not re-derive)

- All three branches are **0 commits behind `main`** — no rebasing needed to merge.
- `backup/pre-pull-20260731` is 2 behind main and fully superseded; safe to delete.
- Branch file-overlap: gridT ∩ groupA = **∅**; boundedT-si-figures ∩ groupA =
  `pyproject.toml` only (identical version bump).
- Working tree ∩ boundedT-si-figures = the 3 files listed in Phase 3.
- ~~Naming scheme verified against all 17 cached forward posteriors: 0 case-id
  collisions, 0 round-trip failures.~~ **Wrong — corrected 2026-08-11.**
  Re-measured with `case_from_attrs()` over all 17: **15 unique ids, 2
  collisions** (`tx.v026.GHEA.sst.ri3.G23-N10.001` and
  `tx.v026.GHEA.thm.ri3.G23-N10.001` each claimed by two files). The earlier
  check must have tested round-tripping a *supplied* `filename_suffix` rather
  than recovering it from attrs — which is precisely the gap. Dual-read itself
  is fine. See Phase 5C; **do not migrate the cache until this is fixed.**
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
