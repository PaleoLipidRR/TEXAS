# RESUME — merging completed work back to `main`

**Written:** 2026-08-09 · **Branch when written:** `feat/revision1-validation-groupA` @ `a0b3887`

This file exists so a crash, a closed laptop, or a new session loses nothing.
Every step is copy-pasteable and has a verification command. Work top to
bottom; tick the boxes as you go.

---

## Latest session — 2026-08-14 (evening): the R2R is fully drafted

**All 31 R2R responses are now written.** The 15 `[RESPONSES]` placeholders are
filled and `main.tex` compiles clean under xelatex (0 errors, 36 pages, was 28).
Committed as `27a7ab5` in the R2R repo.

Three responses rest on evidence extracted for the first time this session:

- **R2C14** — the reviewer is right that coretops do not constrain the warm end,
  and more strongly than they put it. All **28 observations above the warmest
  coretop (29.80 °C) are culture (24) or mesocosm (4)**; not one coretop exceeds
  it. T₀ = 34.8 °C lies above the entire coretop range and the max-slope
  temperature (29.85 °C) sits at its very top edge. Also clarified: the upper
  asymptote is **fixed at 1 by construction**, not estimated — what culture and
  mesocosm constrain is the *approach* to it.
- **R2C13** — the `>= 0.75` retention rule keeps **39 samples (1.9%)** the 90%
  ellipse would drop, mean SST **27.7 °C** against 16.3 °C for the rest. The
  warm-end leverage R2 suspected is real. (Reproduced on the processed coretop
  table, n=2024; the production chain grids to 1513, so treat as indicative.)
- **R1C5 / R2C3 / R2C18** — **the PETM is demonstrably not prior-driven**, so the
  planned prior-sensitivity refit is no longer needed. See below.

### The PETM prior question is CLOSED — no run required

Every reconstruction used `prior_sigma_t = 10` (verified in SI03 cell 61 for the
PETM block and cell 77 for the extreme cases — **not 15**). Because prior and
posterior share a scale, the posterior/prior variance ratio bounds the prior's
contribution directly:

| record | 68% half-width | post/prior var | variance from data |
|---|---|---|---|
| South Dover Bridge (PETM) | 2.2 °C | 0.05 | **95%** |
| ODP 959 (PETM) | 3.8–4.1 °C | 0.14–0.16 | 84–86% |
| ODP 1259 (upper asymptote) | 5.4 °C | 0.29 | 71% |
| Co1010 (Antarctic, lower asymptote) | 5.9 °C | 0.35 | 65% |

A prior 4–20× wider than the posterior it produces is not setting the answer.
The same table **independently confirms the asymptote argument** (prior influence
rises monotonically toward both asymptotes) and **confirms R1C5's Antarctic
criticism** — Co1010 is the most prior-influenced record in the study.

Nitrate-scenario sensitivity at the PETM sites is also second-order: **−1.34 °C
(SDB), −0.96 °C (ODP 959)**, both smaller than a single run's 68% half-width —
against **−4.5 to −5.3 °C** at the Quaternary sites.

### CORRECTION: the "intervals are 14% too narrow" result was wrong

It came from `invt_budget_sites.csv`, the 200-site **stress set** (tail-weighted
by construction, and *not* held out). Over all 1513 sites the production
calibration is calibrated and the bias flips sign — see the corrected entry
further down this file. Population: bias **−0.99 °C**, RMSE **4.35**, R² **0.824**,
cov68 **0.664** vs 0.68 nominal. Univariate is *better* in the inverse direction
(RMSE 3.87, R² 0.860), which is the evidence behind R2C4 and R1C2.

### Section 6.2 / Section 7 drafting (2026-08-14)

- **§6.2's new closing paragraph** (replacing the dissolved §6.3): refined draft in
  `scratchpad/sec62_para3.tex`. The fix was that it estimated **β** coefficients and
  then pointed at §7 for "posterior coefficients" — but §7 reports **γ**, a
  different quantity in different units. It now says the two parameterizations are
  not numerically comparable and that only the *qualitative* result carries forward.
  Verified: thermal R² 0.75, both G₂/₃ slopes, both NO₃ slopes, n=1513, and
  **n=562** for `no3_sf2tc_avg` ≤ 1.0 all check out; divergence factor 2.48.
- **§7's sampler paragraph**: corrected draft in `scratchpad/sec7_sampler_para.tex`.
  Four numbers were wrong — the budget sweep is **Text S2 not S3**; forward runs
  take **9.8–212.0 s** not 11–186; agreement is within **0.06** posterior SD at the
  production 400/1000 cell (0.0677 belongs to a *different* budget, bounded-T's
  recommended 300/900); and median ESS across the seven fits is **1247.6**, not
  1341 (1340.9 is one fit's value). Also narrowed "All model fits" → "All
  calibrations reported here", because the SRI05 univariate comparator has
  R̂ = 1.01407.

> **Where M=300 came from — do not claim the sweep recommended it.** It did not:
> `recommended_invt_budget.json` recommends **1000/1000 with M=500**. Production
> runs 500/1000 with M=300, i.e. *cheaper* than the recommendation. The reason the
> recommender returned the reference cell is that its drift gate is the
> **seed-to-seed floor (0.271 °C)**, measured by rerunning the reference at a new
> seed — but any cheaper cell carries a budget effect *plus* seed noise, so it
> essentially cannot come in under a pure-noise threshold. **The gate is close to
> unpassable by construction**, so "no cheaper cell passed" is not evidence that
> M=300 is inadequate. What the grid actually shows: across all eight cells bias
> 0.921–0.934, RMSE 4.511–4.529, cov68 0.590–0.610. The production cell drifts
> 0.339 °C against the 0.271 °C floor — ~13× smaller than the 4.5 °C RMSE.
> Defensible claim: the budget moves medians by ~0.3 °C, comparable to seed noise
> and an order of magnitude below the reconstruction uncertainty. **Avoid "more
> than sufficient" for the inverse.**

### Moving this work to another machine (the zip question)

**Do not zip the whole repo.** The working tree is 4.9 GB before `.git` (7.8 GB)
and `.venv` (1.9 GB), and it contains **6 compiled Linux Stan binaries** in
`src/TEXAS/stan_models/` that are actively harmful elsewhere (TEXAS detects the
exit-127 cross-environment failure and recompiles, but only after confusion).

Clone + `git lfs pull` already carries everything tracked. What git does **not**
carry is 459 files under `data/`, 3.9 GB:

| what | size | needed? |
|---|---|---|
| `data/cache/TEXAS_posterior_cache/` | 3.5 G | yes — the expensive thing |
| `data/cache/TEXAS_invT_posterior_cache/` | 18 M | yes — 173 `.nc` + 175 `.npz` |
| `data/revision1/**` untracked (18 files) | <1 M | yes — SI evidence tables |
| `data/spreadsheets/` untracked (9 files) | small | **yes** — incl. `predT_bayspar_p16_p50_p84.csv`, which SI_code02 loads |
| `data/cache/kriged_grids_*.npz` | 332 M | optional, regenerable (slow) |
| `data/cache/superseded_halo_cache/` | 111 M | no |

Build the sidecar (~3.5 GB; `.nc`/`.npz` are already compressed, so `-z` buys
little and costs a lot of time):

```bash
cd /home/rrattan/Documents/GitHub/TEXAS
tar -cf ../texas-sidecar-$(date +%Y%m%d).tar \
    --exclude='data/cache/superseded_halo_cache' \
    --exclude='data/cache/kriged_grids_*' \
    data/cache data/revision1 data/spreadsheets
```

On the other machine: `git clone`, `git checkout feat/revision1-validation-groupA`,
`git lfs pull`, **check the `--skip` smudge filter** (see below), then untar over
the clone. Tracked files are overwritten with identical content, so the order does
not matter. Do **not** copy `src/TEXAS/stan_models/` binaries — let them recompile.

### Still open

- **`.gitignore` boundary is backwards in one place, NOT yet fixed.** A blanket
  `*.csv` ignores SI evidence (`mcmc_budget_grid.csv`, the Text S2 sweep;
  `proxy_definition_summary.csv`) while off-scope material is tracked:
  `TEXAS-revision/` (9 files — gridT poster/explainer, **zero references** from
  main text, SI, docs or package) and `notebooks/current/IMOG_presentation.ipynb`.
  Also note `proxy_parameter_comparison_by_arm.csv` is tracked but its sibling
  `proxy_parameter_comparison.csv` is not — almost certainly accidental.
  > ⚠️ **`.gitignore:89` reads `figures/   # ← uncomment if you want...`** — it is
  > inert **only** because the trailing text makes the pattern match nothing.
  > "Tidying" that comment would ignore all 92 tracked manuscript figures.
- **Two R2R red boxes remain, both genuinely unrun**: the Mahalanobis threshold
  sweep (R2C12) and the refit without the `>= 0.75` retention rule (R2C13). The
  latter also closes R3C3's screening-robustness request. The PETM prior box is
  **gone** — answered above.
- The `[TO BE CONFIRMED BY THE AUTHORS]` box in R3C3 is still for you.

---

## Latest session — 2026-08-14

Everything below is pushed. Branch `feat/revision1-validation-groupA` is level
with origin; the manuscript and R2R repos are level with their `main`.

**The manuscript restructured Sections 6 and 7.** Eq. 10 (the multivariate
forward model) no longer exists in §6.2. The bounded-T model is introduced once,
in §7.1.2, as **Eq. 13** — and the two duplicate statements of it that used to
sit there (`eq:bottomlayer-general`, `eq:bottomlayer-full`) were folded into it.
§6 is now confined to the S-curve, the temperature-only fit, and the evidence
that the nonthermal effects exist. **Equation numbers downstream of §6.2 all
shifted**; the R2R's noise-term table was updated to match (Eq. 11 → 10,
Eq. 14 → 13). If you cite an equation number from memory, re-check it.

**New Appendix C, "Running TEXAS on your own data"** — answers R1C1's request for
a practical "list of ingredients". Two facts in it were verified against the
package, not assumed: `compute_scaledRI` is scale-invariant, so peak areas and
fractional abundances give identical results and no normalization is needed; and
**nothing in the package consumes an age model**, so chronological uncertainty is
not propagated. The Open Research Section was trimmed to availability only.

**`arydshln` removed from the manuscript preamble.** It was loaded ahead of
`array`/`colortbl`, which broke `\hline`, `\midrule` and `\toprule` alike —
LaTeX did not fail cleanly, it ground for >10 min in an error cascade. Nothing in
the document uses dashed rules. **If a table ever stops compiling, check this
first.**

**New notebook**: `SI_code01_boundedT_variance_partitioning.ipynb` — the
frequentist additive-vs-bounded-T comparison, one fitter with
`parameterization=` and `beta_fit=` switches. Reproduces the submitted additive
numbers and settles the fig6 NO₃ ODR question (see below).

**Explainer**: `working-repo/TEXAS-revision/boundedT-explainer.html` — plain-language
derivation of the bounded-T model from the production posterior, written for the
§6–7 rewrite.

**The sampler budget is now recorded and reported.** `sampler.py` stamps
`iter_warmup`, `iter_sampling`, `chains` and `thin` on every new posterior, read
from the CmdStan fit so defaults are captured too. `scripts/backfill_iter_warmup.py`
retrofits existing files **only where a refit manifest names the specific file** —
a blanket stamp would be wrong, because the cache mixes 400 (refit script), 300
(`SI_code02_boundedT`) and CmdStan's default 1000, all indistinguishable in the
file. 11 forward posteriors stamped and verified; **the 173 inverse posteriors are
deliberately left unstamped**, since the manifest records no path for inverse runs.
§7 now states the budget, and **Text S2** in the SI carries the sweep.

**Two more manuscript edits landed**: the Conclusions now says explicitly that
R² 0.75 → 0.80 is *in-sample*, and gives the cross-validated counterparts (0.74
random, 0.70 spatially blocked). R3C3's robustness half is drafted from the CV
run and SI_code2a.

**Section 6.3's methodology moved to Text S3**; §6.3 now carries the argument and
ends on a prediction §7.1.2 tests. **Bounded-T is presented as the formulation, not as
the winner of a comparison** — the additive model appears nowhere in the manuscript or
SI, only in the R2R. §7.2's results were still in β from the additive fit and are now
γ from the production posterior, with 68% and 95% intervals.

**R² convention decided 2026-08-14**: report `R2_full` (1 − RSS/TSS), because published
TEX₈₆ calibrations are mostly not Bayesian and report that quantity. Univariate 0.746,
multivariate 0.813 — an internally consistent pair. Bayesian R² (0.874) is named once,
cited to Gelman et al. 2019, and never quoted interchangeably. The Conclusions moved
0.80 → 0.81 to match.

**The length argument is now on the record.** The Introduction closes with a roadmap
naming each section; the R2R has a full response to the Associate Editor (there was
none before) arguing that the length is intrinsic to a methods paper making two
structural departures, and that the answer is navigability rather than brevity.

**Claim audit done 2026-08-14 — six moderated, two numbers reconciled.** Anchored to
what the reviewers actually objected to (R2C4 and R2's closing paragraph on in-sample
metrics and forward-vs-inverse; R3 on "outperforming all existing"; the AE endorsing
both), not to general adjective-hunting. Method: render the text as a *reader* sees it
— resolve `\change{old}{new}` to the new half, strip `\note{}` — then scan for
evaluative language and check each hit against the evidence actually in hand.

Two were factual inconsistencies, now fixed:

- The **abstract still said R² = 0.80 (RMSE 0.052)** for the multivariate fit while §7.2
  and the Conclusions had moved to the production posterior. The temperature-only pair
  (0.75, 0.058) already matched; only the multivariate one did not. Now **0.81 (0.050)**.
- The **inverse figures (R² = 0.82, RMSE 4.4 °C) were unlabelled** as in-sample, which
  R2C4 and R3 both asked for explicitly. Now labelled, with the spatially blocked
  counterpart given.

Six were overstatements against the paper's own evidence or its own hedged wording
elsewhere. All use `\change{}` except the heading:

| where | was | now |
|---|---|---|
| Conclusions (Tasman) | "**removes** the persistent warm bias" | "reduces", **plus** an explicit statement that these are sensitivity tests conditional on assumed nutrient depletion |
| §7.2 heading | "**resolves** first-order spatial biases" | "reduces" — §8.1's heading had already been softened the same way |
| §7.2 | "captures the **universal**, nonlinear physiological response" | "captures the nonlinear response" |
| §8.3 PETM | nonthermal controls are "**essential** for reliable reconstruction" | "illustrates how much reconstructed temperature can depend on the assumed nonthermal state" |
| Plain Language Summary | "**more geologically reasonable** … **more reliable** window" | "agree more closely with independent proxy and model evidence", uncertainty reported |
| §6.1 / §7.2 | "**superior** ability"; maps "**unambiguously**" | "better represents"; maps onto |

The Tasman one was the important one: §8.1 says TEXAS "can recover realistic SST
amplitudes *once the extent of past nutrient depletion is constrained*" and labels those
runs sensitivity reconstructions, so the Conclusions was arguing against the body. It was
also the sentence most exposed to R2C2.

**The R2R's AE response now enumerates all six** rather than asserting that claims "have
been moderated", so an editor can spot-check each against the revised text.

**Two gotchas worth remembering.** A section heading cannot take `\change{}` — soul
markup in a sectioning command propagates into the ToC and the `.aux`; edit the heading
directly and record it in a `\note{}`. And a naive `\change` regex fails on nested
braces like `[NO$_{\text{3}}^-$]`, so a verification script needs a real brace matcher
or it will report the struck-through half as if it were live text.

**Scope limit, so nobody assumes more than was done:** the scan used a fixed term list
(outperform, superior, resolves, demonstrates, universal, essential, unambiguous,
guarantee, and similar). It is not a full read-through, and it did not audit numerical
claims other than the two above.

**Full read-through audit done 2026-08-14** (the earlier one was a term-list scan;
this one read the whole manuscript as a reader sees it). Twenty findings, all fixed.
Three were serious:

1. **Eleven figures were still the additive fit** — fig7–fig14 and all three appendix
   prior plots pointed at the superseded versions. Copied from the TEXAS repo and
   repointed. **`fig6` deliberately stays the parent**: its `_boundedT` counterpart
   contains the additive-vs-bounded comparison, which must never appear in the paper.
2. **§7.2's curve parameters were the additive fit's.** T₀ = 36.2±1.6, b = 0.437,
   k = 0.20, ν = 2.8 matches `tx.GHEA` (additive) to three decimals; the production
   `tx.GHEB` gives 34.8±0.7, 0.412, 0.28, 4.0. Replaced for SST and Thermo-T, and the
   *interpretation* with them — T₀ is no longer "virtually unchanged" but 1.7/3.5 °C
   cooler, and b no longer shifts "marginally higher". Fig. 8's caption had the same
   stale R²/RMSE.
3. **The manuscript addressed a reviewer by name** in §7 ("which Reviewer 3 rightly
   noted") — my wording, the same fault already fixed in Appendix C.

Plus: §7.1.1 and §7.2 both said 1000 warm-up against §7's 400 (budget now stated once);
three places called T₀ the inflection point when §6.1 says it is not; two cross-references
pointed at figure labels while typeset "Eq." and "Table"; the acronym read "indeX **for**";
a doubled period; a lowercase sentence start; four grammar slips. One regression of my own
— the claim pass had dropped "the nonlinear temperature response" from §6.1 — restored.

**CI was red and is now green.** Nine ruff F401/F841 failures on this branch, each
verified dead individually rather than bulk-autofixed. `ruff check` passes, 277 tests pass.

### Still open after this session

- **Two figure choices need your eye.** fig11 and fig12 previously pointed at
  hand-edited `_revised.pdf` files (they have paired `.svg`); they now point at the
  freshly generated `_boundedT.pdf`, which is the right *data* but carries **none of
  the manual annotation**. Also `fig1_..._boundedT.pdf` exists and is unused — the
  manuscript still shows `fig1_..._revised.pdf`.
- **One sentence of R3C3 is for the authors** — whether the screening criteria and
  the index choice were fixed independently of the final calibration results. It is
  a red box in the R2R titled `[TO BE CONFIRMED BY THE AUTHORS]`. Everything else
  in R3C3 is drafted.
- **Two manuscript edits the R2R promises but that are NOT made** — flagged in a
  second red box in the R2R. (1) Move §6.3's per-site uncertainty assignments,
  OLS/ODR implementation and delta-method propagation to the SI; **that becomes
  Text S3**, since Text S2 is now taken. (2) The Conclusions half of this is done.
- **ρ for NO₃ — RESOLVED 2026-08-14, was never wrong.** The draft's −0.38 is quoted
  at threshold **1.8** and reproduces exactly (−0.382, n=701). The −0.328 that
  looked like a discrepancy was computed at threshold 1.0, a number the manuscript
  never claims. G2/3 reproduces at −0.360 too. **No manuscript change needed.**
- **The Open Research Section cites Zenodo v0.2.1**, but tags run to v0.2.5 and the
  installed package reports 0.2.6. Three releases stale.
- **The frequentist notebook is committed but not yet in the Zenodo record** — it is
  on this branch only, and releases are tagged from `main`. Zenodo archives the whole
  repo tarball (no `export-ignore`), so it travels automatically once the branch
  merges and a tag is cut; no manual step. Its input CSV is tracked in LFS, so it is
  reproducible from the archive.

---

## PLAN — resubmission, then the archive split, then v1.0.0 (written 2026-08-14)

Three phases, strictly ordered. **Phase A blocks resubmission. Do not start
Phase B until the revised manuscript is out** — moving files while the SI
notebooks are still being edited is how a figure quietly loses its source.

### The line the split is drawn on

The initial submission (tag **`v0.1.10`**, 2026-04-24) fitted the **additive-EIV**
model: the nonthermal predictors added an offset to the response, outside the
logistic. Compset **`GHEA`**, Stan file `..._priorApprox_eiv.stan`, coefficients
`beta_G23_crtp` / `beta_NO3_crtp`.

The revision fits the **bounded-T** model: the predictors shift T₀, inside the
logistic. Compset **`GHEB`**, Stan file `..._priorApprox_eiv_boundedT.stan`,
coefficients `gamma_G23_crtp` / `gamma_NO3_crtp`.

Everything that exists *only* to reproduce the `GHEA` arm is archive. Everything
the bounded-T arm runs on is the package. That is the whole rule.

---

### Phase A — finish the revision (blocking)

- [ ] **15 of 31 R2R responses are still `[RESPONSES]` placeholders.** This is the
      largest single piece of remaining work, and nothing else on this list is
      close. Unwritten: **R1C2, R1C3, R1C4, R1C5, R1C6, R2C3, R2C5, R2C9, R2C11,
      R2C12, R2C13, R2C14, R2C17, R2C18, R2C19**. Note that R1C1, R2C1, R2C2,
      R2C4, R3C1–R3C4 — the structural ones — *are* written.
- [ ] **The `[TO BE CONFIRMED BY THE AUTHORS]` red box** in R3C3 (`main.tex:640`):
      one sentence on whether the screening criteria and the index choice were
      fixed independently of the final calibration results. Not draftable from
      the repository.
- [ ] **Two stale thermoT uncertainty maps** — both were rendered before their
      inputs finished and silently show a subset of the 1513 sites. Regenerate
      `figXX_..._thermoT_...` from `SI_code2` and `figXX_..._thermoT_..._boundedT`
      from `SI_code02`, then confirm the site count.
- [ ] **`AppendixA_culmesoT_prior_distributions_boundedT.pdf` is stale** — predates
      the four single-predictor fits.
- [ ] **fig11 / fig12 lost their manual annotation.** They now point at the freshly
      generated `_boundedT.pdf`, which is the right data with none of the hand
      editing that `_revised.pdf` carried. Re-annotate, or accept the plain version.
- [ ] **Commit the four dirty SI notebooks.** `SI_code2` is the dangerous one — its
      run cells are uncommented and executing it overwrites the audited 400/1000
      posteriors.
- [ ] **The Open Research Section cites Zenodo v0.2.1**; tags run to v0.2.5 and the
      package reports 0.2.6. Cut a tag and update the citation as part of resubmission.

**Done this session** (all uncommitted):

- The R2R now opens with a **Summary of revisions** table (ten rows, each keyed to
  the comments it answers). Builds under xelatex, 28 pages.
- **Every Stan header rewritten to read standalone.** No file describes itself as a
  diff against a superseded design any more — the two bounded-T headers were the
  worst offenders (the forward one opened with "THE PROBLEM THIS ADDRESSES
  (reviewer comment)" and a measured indictment of the additive model). Six files
  that had no header, or a header naming the wrong file, now have one. All 17
  parse under `stanc` 2.36.0; 279 tests pass.
- **Tutorial Module 3 rebuilt** on the bounded-T design: slider defaults are the
  published posterior medians rather than illustrative values (t₀ 34.8, k 0.275,
  b 0.412, ν 4.0), and there are new G₂/₃ and NO₃ sliders that slide the curve
  sideways while the thermal-only curve stays put, so the boundedness is visible
  rather than asserted.
- **README and `docs/index.md` describe the γ-on-T₀ formulation**, and the
  forward-calibration example now names `..._eiv_boundedT`.

⚠️ **`docs/index.md` carries a new warning that the two multivariate posteriors on
Zenodo are the additive-EIV formulation.** That warning is a stopgap for the
`download.py` problem in Phase C, not a fix — remove it when the bounded-T
posteriors are published.

### Two defects found in passing

- **The `inflection_point` generated quantity had the wrong sign** in
  `gen_logi_fixed_hier_crtp_univ_priorApprox.stan` and
  `gen_logi_fixed_culmesocore.stan`: both computed `t0 + ln(v)/k`. Setting
  d²f/dT² = 0 gives `exp(-k(T-T0)) = v`, hence **`t0 − ln(v)/k`**. Verified
  numerically against the production posterior — the true max-slope temperature
  is 29.85 °C against t₀ = 34.8 °C, i.e. 4.95 °C *below* t₀ and matching the
  4.2–5.2 °C range CLAUDE.md already records. The old formula returned 39.75 °C,
  wrong by 9.9 °C and on the wrong side. Both are fixed and the variable renamed
  to **`max_slope_temp`**, which is what it actually is. Nothing in Python or the
  notebooks read the old variable, so this renames cleanly; cached `.nc` files
  carry the old name and value, so **regenerate before quoting it**.
- **`SI_code1` repeats the same sign error in Python** —
  `generalized_logistic_inflection_point()` returns `x0 + np.log(v)/k`, and it is
  plotted as a marker on the parameter-sweep panels. The marker therefore sits on
  the wrong side of x₀. **Not fixed here**: that notebook is deliberately
  uncommitted, and correcting it moves a published figure. Decide before
  resubmission.

### The archive already half-exists inside the package

`src/TEXAS/stan_models/` contains **`archive/` (16 tracked files) and
`archive_pre_annotated/` (4)** — the earlier `gen_logi_free_*`, `logistic_*` and
ensemble invT models, with their own README. The non-recursive `ls *.stan` used
when Phase B was drafted missed them. They are **already excluded from the wheel**
(package-data is `stan_models/*.stan`, not `**`), so no packaging change is needed
— but they should fold into `archive/submission-2026-04/` in Phase B rather than
leaving three archives in two places.

---

### Phase B — the archive split

Decided 2026-08-14: **repo-root `archive/`, not installed.** The final package
ships production models only; the archive is a readable folder rather than a git
tag, and reproduction goes through an explicit `model_dir=`.

```
archive/
  submission-2026-04/
    README.md              <- what this reproduces (v0.1.10), and the exact commands
    stan_models/           <- 9 files
    notebooks/             <- SI_code2, SI_code3
    figures/               <- the additive-fit parents
```

#### B1 — Stan models: 17 → 8 shipped, 9 archived

**Stays in `src/TEXAS/stan_models/` (8):**

| file | why it stays |
|---|---|
| `gen_logi_fixed_culmeso.stan` | stage-1 culture+mesocosm hyperpriors |
| `gen_logi_fixed_hier_crtp_univ_priorApprox.stan` | thermal-only fit; also produces `R2_thermal` |
| `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT.stan` | **the production calibration** |
| `invT_gen_logi_fixed_multiv_marginal_unconstrained_boundedT.stan` | production inverse |
| `invT_gen_logi_fixed_univ_marginal_unconstrained.stan` | univariate inverse (quickstart, SI03) |
| `invT_gen_logi_fixed_multiv_marginal_unconstrained.stan` | multivariate inverse comparator in SI03 |
| `invT_gen_logi_fixed_*_marginal_truncated_prior.stan` (2) | **live docs** — `docs/why_plugin_p50_differs.md` is in `_toc.yml` and explains the plug-in/marginal gap through them |
| `linear_model.stan` | used by `SI_code1` and every SI notebook |

**Moves to `archive/submission-2026-04/stan_models/` (9):**

| file | why it moves |
|---|---|
| `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv.stan` | **the initial submission's production model** (`GHEA`) |
| `gen_logi_fixed_hier_crtp_multiv_priorApprox.stan` | superseded non-EIV intermediate |
| `gen_logi_fixed_hier_crtp_multiv.stan` | superseded full-hierarchical intermediate |
| `gen_logi_fixed_culmesocore.stan` | not used by any manuscript notebook (Streamlit only) |
| `invT_gen_logi_fixed_univ_unconstrained.stan` | non-marginal inverse; `SI_code3` only |
| `invT_gen_logi_fixed_multiv_unconstrained.stan` | non-marginal inverse; `SI_code3` only |
| `invT_gen_logi_fixed_*_marginal_hard_constraint.stan` (2) | **zero references anywhere** |

> **Verified, not assumed:** `SI_code02`'s only mention of the additive `_eiv`
> model is in its header markdown table (documenting the difference) and in
> commented-out code. The bounded-T arm never compiles it.

**Before moving, these break and must be handled:**

- `src/TEXAS/utils/naming.py` — the compset decoder maps `A` (additive) and the
  `culmesocore` training set. **Keep the decoder intact**; it must still parse
  `tx.GHEA.*` case ids or every archived posterior becomes unreadable.
- `streamlit_app/pages/{prediction,computation}.py` reference `culmesocore`.
- `tests/test_naming.py`, `tests/test_run_tokens.py` assert on archived names —
  they are testing the *name grammar*, not the models, so they stay.
- `scripts/prepare_review_archive.sh` is written entirely against the legacy flat
  names of the initial submission. It belongs in `archive/`, not `scripts/`.
- `src/TEXAS/stan_models/archive/` (16 files) and `archive_pre_annotated/` (4)
  already exist and are tracked. Fold both into `archive/submission-2026-04/`
  rather than leaving three archive locations. Neither ships in the wheel today.

#### B2 — Notebooks

Move `SI_code2_TEXAS_analysis.ipynb` and `SI_code3_paleo_showcases.ipynb` to
`archive/submission-2026-04/notebooks/`. Superseded by `SI_code02_*_boundedT`
and `SI03_*_modelswitch` respectively.

**`SI_code3` is the one with a trap.** It requests date-stamped legacy posterior
names (`..._scaledRI_cren3_050126_eiv`). Those resolve only because the files on
disk still carry the old name in their `filename` attr — a re-run would break
them. Archive the notebook *and* the posteriors it needs, together, or it stops
being reproducible.

#### B3 — Figures and posteriors

- Additive-fit parents (`fig7`–`fig14`, the three Appendix prior plots) → archive.
  **`fig6`'s parent stays where it is** — its `_boundedT` counterpart contains the
  additive-vs-bounded comparison, which must never appear in the paper.
- `data/cache/.../superseded/` and the flat legacy `.nc` names → the Zenodo
  archive record, not the repo (the cache is gitignored either way).
- `review_archive_v0.1.8/` at the repo root is untracked staging from April.
  Delete it, or fold it into `archive/`.

#### B4 — Root cleanup

`site/`, `dist/`, `html_figures/`, `outputs/`, `logs/` are all untracked and
gitignored, but Zenodo archives the working tree as a tarball. Clear them before
tagging.

---

### Phase C — v1.0.0

- [ ] **`download.py` still ships the additive posteriors as the public default.**
      `_ZENODO_FILES` has five entries — two of them the additive multivariate
      (`GHEA`), the rest univariate/culmeso — and **no bounded-T entry at all**.
      A user who follows the README today downloads the superseded calibration.
      **This is the single most important v1.0.0 fix** — it is a correctness
      problem, not tidiness.
- [ ] Same repointing in `README.md:153`, `docs/index.md:119,136,137,186,203,265`.
- [ ] Upload the bounded-T posteriors to Zenodo; keep the `GHEA` ones in the record
      as the submission archive, clearly labelled.
- [ ] `pyproject.toml` package-data stays `stan_models/*.stan` — correct, since the
      archive lives outside `src/`. Confirm the wheel drops from 17 to 8 models.
- [ ] `CITATION.cff` / `.zenodo.json` → 1.0.0; drop the "in prep" / "prepared to
      submit" language once accepted.

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

### Decided, do not relitigate

- **`tx.GHPU.sst.sri05.p0` fails the strict R-hat gate (1.01407) and that is
  accepted.** Checked 2026-08-13. The failing fit is the SRI05 *univariate*
  stage, which enters the analysis only through `R2_thermal`, i.e. as a prior
  scale. The fits that actually produce the coefficients both pass — SRI05 eiv
  1.00887, SRI05 bnd 1.00827 — and MCSE on `gamma_G23` is 0.00123 on a median
  of 0.7641 (0.16%), so the 20.5% G23 spread statistic is precise to a fraction
  of a point. SRI05 is a comparator, not a production calibration; no refit.
  Note it *does* set the upper end of that spread, so "unused" is the wrong
  reason to dismiss it — "its coefficient fit converged" is the right one.
- **The univariate model is the SLOWEST of the three to converge**, not the
  fastest, despite having no predictors: only 9 of 27 budget cells clear
  R-hat <= 1.01, and the worst parameter rotates among k/v/t0 trading off
  against each other. The production 400/1000 budget clears it comfortably
  (1.00465, ESS 760); the cheapest clearing cell is 400/600.

### Both thermoT uncertainty maps are STALE — regenerate first (2026-08-13)

Each was written **before the reconstructions it draws finished**. The maps glob
the `global_coretop_*` invT posteriors, so an early run silently renders a
subset of the 1513 sites rather than failing.

| figure | inputs written | figure written | verdict |
|---|---|---|---|
| `figXX_..._thermoT_..._boundedT` | 13:53 → **16:12** | **13:23** | built before *any* input existed |
| `figXX_..._thermoT_...` (additive-EIV) | 12:34 → **13:47** | **13:13** | missing the last batches |
| `fig10_..._SST_..._boundedT` | 09:53 → 11:02 | 13:23 | OK |
| `fig9`, `figS13` | (SST) | — | OK, SST only |

Both are committed — the bounded-T one in `16bfb3e`, the additive-EIV one in
`04a5b24` (committed 2026-08-13 believing it was a clean recache; it was not).
**SST maps are fine**; only thermoT is affected, in both arms.

Now safe to regenerate: the bounded-T arm reached 28/28 at 16:12 and the
additive-EIV arm is 28/28, so both sets are complete for the first time. Re-run
the map cells in `SI_code2` (untagged) and `SI_code02` (`_boundedT`).

- [ ] regenerate `figXX_..._thermoT_...` from SI_code2
- [ ] regenerate `figXX_..._thermoT_..._boundedT` from SI_code02
- [ ] confirm each covers all 1513 sites, not a subset

### Still open when you get back

- [ ] **`AppendixA_culmesoT_prior_distributions_boundedT.pdf` is stale** —
      written 17:29 on 2026-08-12, before the four single-predictor fits landed
      and from the pre-rename cell sources. Regenerate from SI_code02.
- [x] **Under-coverage explained 2026-08-12 — it is interval WIDTH, not bias.**
      One number accounts for both figures: the mean 68% half-width is
      **0.863-0.867x the residual SD** (3.83 degC against 4.43 degC). Feed that
      ratio through a Gaussian and it predicts cov68 = 0.612 against 0.60
      observed, and cov90 = 0.846 against 0.84 observed. Both, to within a
      couple of points, from one quantity.

      The +0.93 degC bias is **not** the cause: removing it changes coverage by
      -0.005, i.e. it slightly *lowers* it. And the ratio is stable to 0.004
      across every budget cell, which is why this was never sampler noise --
      more draws cannot widen an interval the model does not think is wide.

      So the honest statement for the SI is that the predictive intervals
      understate the true error by about 14%: the residual spread contains
      site-level variability (oceanographic, depth-habitat, bioturbation) that
      the calibration's noise model does not carry. Reproduce with
      `data/revision1/groupA/param_sensitivity/invt_budget_sites.csv`.

      > ### CORRECTED 2026-08-14 — this is a STRESS-SET result, not a population one
      >
      > **Do not quote the 14% figure as the model's interval calibration.**
      > `invt_budget_sites.csv` is the 200-site sampler-tuning subset built by
      > `invt_subset()` in `scripts/run_param_sensitivity.py`, which fills
      > equal-width bins over the proxy *range* with an equal quota each. Its own
      > docstring is explicit: *"a stress set, not a validation set: error
      > statistics over it are not population statistics for the compilation."*
      > It deliberately over-weights the asymptote regions, where intervals are
      > worst. The 200 sites are also **not held out** — they are drawn from the
      > same coretops the calibration was fitted on.
      >
      > Recomputed over **all 1513 sites** from the `global_coretop_b01..b07`
      > invT posteriors (`tx.GHEB.sst.sri03.G23-N10`, alignment checked per site
      > against `scaledRI_cren3`), the production calibration is close to
      > calibrated, and the bias even **flips sign**:
      >
      > | | stress set (n=200) | population (n=1513) |
      > |---|---|---|
      > | bias | **+0.93** degC | **-0.99** degC |
      > | RMSE | 4.52 | 4.35 |
      > | R2 | — | 0.824 |
      > | half-width / residual SD | 0.865 | **1.05** |
      > | cov68 (nominal 0.68) | 0.60 | **0.664** |
      > | cov90 (nominal 0.90) | 0.84 | 0.853 |
      >
      > The population RMSE/R2 reproduce the manuscript's reported inverse
      > in-sample figures (4.4 degC, 0.82), which is the check that the
      > alignment is right. Univariate for comparison: RMSE 3.87, R2 0.860,
      > cov68 0.770 — **inverse skill is better without the predictors**, which
      > is the evidence behind R2C4 and R1C2.
      >
      > The stress-set numbers remain valid *as a statement about the asymptote
      > regime* — coverage really does degrade there — and R1C2 in the R2R now
      > says exactly that, sourced to the population figures.
- [ ] **The invT drift floor rests on one seed replicate** (0.271 degC). Two or
      three more would make the "budget does not matter" claim rigorous.
- [x] **Phase 5A done 2026-08-13** (`58ddb86`). `_generate_filename_base` now
      calls `inv_relpath` instead of respelling the leaf; `scenario` widened to
      take a sequence, which was the only real difference between them. Names
      unchanged byte for byte, checked over 216 combinations before committing.
      The drift this closes had already happened and was invisible: only the
      *unreachable* copy was wrong (it still documented `<case>/<leaf>` and a
      run number), so nothing broke and nothing could have caught it. The test
      now asserts the two builders agree rather than asserting a literal.
      **The other two Phase 5A items were already fixed** — `save_invT_posterior`
      no longer drops `proxy_name` (it delegates to the shared builder), and the
      cache flattening has landed (`fwd_relpath`/`inv_relpath` both return a
      bare leaf).
- [x] The branch is **0 behind `main`** as of 2026-08-13 (110 ahead). The
      "6 behind" note was stale.
- [x] **DOI reconciled 2026-08-12.** `data/README.md` cited `19666745` while
      `README.md`, `CITATION.cff` and `download.py` used `20032542`. Aligned on
      `20032542`, which `download.py` documents as the currently published
      record and actually fetches from. **Check this if 19666745 was the
      *concept* DOI** (all-versions) rather than a superseded version DOI — in
      that case the right move is the opposite one, and citing the concept DOI
      is better practice. Could not verify from here without network access.
- [x] ~~`streamlit_app/pages/calibration_data.py` reads `post["Q_crtp"]`~~ —
      **already fixed** (checked 2026-08-13). `Q_crtp` survives only in two
      comments explaining the repair; there is no live read of it anywhere in
      `streamlit_app/` or `src/`. The page also lost its private copy of the
      curve in the same pass, which is what let it drift out of step.
- [x] **fig6's four slopes RESOLVED 2026-08-14.** All four reproduce, including
      the one that did not on 08-13. Thermal R² 0.747, G2/3 OLS −0.0058, G2/3
      ODR −0.0059, NO₃ OLS −0.0296, and **NO₃ ODR −0.072 — the draft value is
      correct.** The 08-13 figure of −0.052 was the degenerate standalone re-fit,
      exactly as suspected; running the hierarchical culmeso→coretop path
      reproduces −0.072. §6.3's bracket claim stands on 1.7–4.3.
      Settled by `notebooks/manuscripts/SI_code01_boundedT_variance_partitioning.ipynb`
      (`35a256d`), which reimplements the two-step protocol with a switch for the
      parameterization. **ρ for NO₃ is still unconfirmed** (−0.328 computed
      against the draft's −0.38) — that is a Spearman on the plotted subset, not
      an output of the fitter, so it needs checking in SI_code1 cell 123 itself.
- [x] **`fig6_ODR_regression_dilution.pdf` — superseded, not regenerated
      (2026-08-14).** The manuscript moved to the bounded-T formulation, so the
      relevant figure is now `fig6_ODR_regression_dilution_boundedT.pdf`
      (`35a256d`), built from the current spreadsheets by SI_code01. The parent
      PDF stays as the record of the original submission and is deliberately
      **not** rebuilt. The prior-elicitation worry is closed by the slopes above:
      they did not move, so the β priors on disk were not elicited from
      superseded data.

### Uncommitted, deliberately

**Four SI notebooks only** (2026-08-14): `SI_code1_PreProcessing_finalized`,
`SI_code2_TEXAS_analysis`, `SI_code02_boundedT_TEXAS_analysis`,
`SI_code2a_model_param_sensitivity_test`. `SI_code2` is the dangerous one — its
run cells are uncommented, so executing it overwrites the audited 400/1000
posteriors. Left alone; commit when you are happy with them.

The figures and the two LFS training spreadsheets that used to sit here **are now
committed** (`cca55ca`), so a fresh clone gets the same inputs and figures rather
than silently different ones.

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
