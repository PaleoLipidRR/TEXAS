# Docs Alignment With the Revised Manuscript — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every page under `docs/` into agreement with the revised manuscript and the shipped Stan models — trim one explainer, move the call map into a Developer part, replace the 574-line ensemble-vs-direct page with a ~100-line catalogue of the seven shipped models, delete the two pages the revision made obsolete, and prove nothing is orphaned.

**Architecture:** The docs are one Jupyter Book. Every change is a file edit plus a matching `_toc.yml` edit plus a sweep for inbound links, and the whole thing is proved by one `jupyter-book build docs/` at the end. Tasks 1–5 each touch a disjoint set of page files (only `_toc.yml` and `docs/README.md` are shared, and then only on distinct lines), so a reviewer can reject one without unpicking its neighbours.

**Tech Stack:** Jupyter Book v1 (Sphinx) with the `jb-book` `_toc.yml` format, MyST Markdown, `sphinx.ext.autodoc` + `napoleon`, GitHub Actions → `gh-pages`.

**Spec:** `docs/superpowers/specs/2026-09-07-repo-finalization-design.md` (§9.8; §10 items 5 and 11)

## Global Constraints

- **Prerequisite: a full project environment.** `jupyter-book<2` is in the `dev` extra and is **not** installed on this machine today. `texas-env` exists but is stale (2026-04-22, pre-ultraplot) and has no `jupyter-book`; the uv-managed `.venv` is a core-only install and has none either. Build a fresh environment first with Task 0 of `2026-09-07-00-INDEX.md` (`conda env create -f environment.yml -n texas-env-2026-09`, under a **new name** — reusing `texas-env` collides with the stale one and the solver reports a misleading matplotlib conflict), or Task 7's build gate cannot run. Do not fall back to the miniforge base interpreter: its numpy 2.5.1 / scipy 1.11.4 pairing is broken.

- The docs are a **single unified Jupyter Book**, migrated from mkdocs-material on 2026-05-30. There is **no `mkdocs.yml`** — do not create one, do not look for one.
- Build with `jupyter-book build docs/`, pinned to **`jupyter-book<2`**: v2/MyST does not read the `jb-book` `_toc.yml` / `_config.yml` format this book uses.
- `docs/_config.yml` sets `only_build_toc_files: true`. A page that is not listed in `_toc.yml` is not built and not linked; a `_toc.yml` entry naming a missing file is a build error.
- The book deploys to `gh-pages` via `.github/workflows/docs.yml` on every push to `main` that touches `docs/**` or `src/TEXAS/**`. That workflow regenerates `_static/callmap.html` and `_static/sampler-budget.html` before building — **never hand-edit either generated file**.
- Optional and heavy dependencies (`cartopy`, `regionmask`, `pykrige`, `proplot`, `pygwalker`, `odrpack`) are mocked via `autodoc_mock_imports` in `docs/_config.yml`, so a core install can build the API page.
- The manuscript's term for the B-compset parameterization is **"T₀-shift parameterization"**; the code token is **`t0shift`**, never `boundedT`.
- `docs/_build/` is gitignored build output. Exclude it from every verification grep (`--exclude-dir=_build`), or delete it before the final build, so a stale local build never reports phantom hits.
- Cross-page links in this book are written as relative Markdown links to the source file, e.g. `[Model validation](model_validation.md)` — keep that form.

## Ordering and ownership

**This plan runs AFTER plan 04 (package API cleanup).** Two pieces of §9.8 are explicitly **out of scope here** and must not be implemented by this plan:

1. **The consequence paragraph at the end of §9.8** — archiving `invT_gen_logi_fixed_univ_marginal_truncated_prior.stan` and `invT_gen_logi_fixed_multiv_marginal_truncated_prior.stan`, and removing `constraint_type` / `min_temp` from the public API — is **owned by plan 04**. The user has **decided on archive**. Consequences for this plan: the rewritten `docs/stan_models.md` describes **SEVEN** shipped models, not nine, and contains **no** section justifying the truncated-prior inverse.
2. **`docs/installation.md` line ~399**, which lists `odrpack` in the dev extra, is **owned by plan 03 (dependency audit)**. Do not touch `docs/installation.md` in this plan.

Two files in this plan have a **second owner**: `docs/model_validation.md` and `docs/troubleshooting.md` are also edited by **plan 02** (kriged-cache folder rename). Task 6 only reads them — but if any later work edits them, **re-read them immediately before editing**, because plan 02 may have landed in between.

---

### Task 1: Trim the 3-D Cartesian tree section from the cKDTree explainer

**Files:**
- Modify: `docs/ckdtree_nearest_ocean_explainer.md:322-346` (353 lines → 328 lines)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: nothing later tasks depend on. `docs/ckdtree_nearest_ocean_explainer.md` keeps its filename and its `_toc.yml` entry.

**Why:** §9.8 rates this page **keep, trim**. Nearest-ocean snapping is part of the SI preprocessing and stays. The "Robust alternative: 3-D Cartesian tree" section describes a technique the code does **not** implement — `get_nearest_valid_value` builds a 2-D lat/lon tree — so it documents a road not taken. Everything else on the page stays, including the whole "Longitude Convention Sensitivity" section and its `to_180` fix, which *is* what the code relies on.

- [ ] **Step 1: Confirm the exact section boundaries before cutting**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
sed -n '320,322p;344,348p' docs/ckdtree_nearest_ocean_explainer.md
wc -l docs/ckdtree_nearest_ocean_explainer.md
```

Expected output:

```
Or convert to 0–360 instead — either is fine, just be consistent.

### Robust alternative: 3-D Cartesian tree
```

(blank)
```
This version is insensitive to longitude convention and works correctly across the date line and poles.

---
```
```
353 docs/ckdtree_nearest_ocean_explainer.md
```

If the line numbers have drifted, locate the same boundaries by content: the cut starts at the line `### Robust alternative: 3-D Cartesian tree` and ends at the blank line immediately after `This version is insensitive to longitude convention and works correctly across the date line and poles.` The `---` rule and the `## See Also` heading that follow are **kept**.

- [ ] **Step 2: Delete the section**

Delete lines 322–346 inclusive — that is, from the heading

```markdown
### Robust alternative: 3-D Cartesian tree
```

down to and including the blank line after

```markdown
This version is insensitive to longitude convention and works correctly across the date line and poles.
```

The surrounding text must end up reading exactly:

```markdown
Or convert to 0–360 instead — either is fine, just be consistent.

---

## See Also
```

Do **not** touch the `### Fix: normalise to the same convention` section above it, the `latlon_to_xyz` name anywhere else in the repo, or the `## See Also` list.

- [ ] **Step 3: Verify the cut**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
wc -l docs/ckdtree_nearest_ocean_explainer.md
grep -n "Cartesian\|latlon_to_xyz\|chord length" docs/ckdtree_nearest_ocean_explainer.md
sed -n '318,326p' docs/ckdtree_nearest_ocean_explainer.md
```

Expected: `328 docs/ckdtree_nearest_ocean_explainer.md`; the `grep` prints **nothing**; the `sed` shows the "Or convert to 0–360" line, a blank, `---`, a blank, `## See Also`.

- [ ] **Step 4: Confirm no other page referenced the removed section**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -rn "Cartesian\|latlon_to_xyz" docs/ --exclude-dir=_build
```

Expected: no output. (If a hit appears in a page other than the one just edited, remove that link — it now points at a deleted anchor.)

- [ ] **Step 5: Commit**

```bash
git add docs/ckdtree_nearest_ocean_explainer.md
git commit -m "docs: drop the 3-D Cartesian tree section the cKDTree code does not implement"
```

---

### Task 2: Move the call map into a "Developer" part of `_toc.yml`

**Files:**
- Modify: `docs/_toc.yml:4-9` and `docs/_toc.yml:30-32`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: a `- caption: Developer` part sitting between `Explainers` and `Archive`, containing `- file: callmap`. Tasks 3–5 edit the `Explainers` part of the same file and must not disturb this new part.

**Why:** §9.8 rates `callmap.md` (+ `_static/callmap.html`, `_scripts/build_callmap.py`) **keep, move to a "Developer" part**. It is code tooling — an AST-derived call graph of `src/TEXAS` — not manuscript content, and it currently sits under "Getting started" between `api` and `troubleshooting`, where a new user meets it before they have installed anything.

**Nothing but `_toc.yml` changes.** `docs/callmap.md`, `docs/_static/callmap.html` and `docs/_scripts/build_callmap.py` are untouched; the page's own relative link `[API reference](api.md)` still resolves, because MyST resolves it against the source tree, not the TOC.

- [ ] **Step 1: Read the current file and confirm it matches**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
cat docs/_toc.yml
```

Expected — this is the **before** state:

```yaml
format: jb-book
root: index
parts:
  - caption: Getting started
    chapters:
      - file: installation
      - file: api
      - file: callmap
      - file: troubleshooting
  - caption: Tutorial
    chapters:
      - file: tutorial/intro
        sections:
          - file: tutorial/module1_prior
          - file: tutorial/module2_bayesian_updating
          - file: tutorial/module3_curve_explorer
          - file: tutorial/module4_mcmc
          - file: tutorial/module5_results
  - caption: Explainers
    chapters:
      - file: PSM
      - file: model_validation
      - file: sampler_budget
      - file: stan_models_explanation_v2
      - file: marginalization_explainer
      - file: why_plugin_p50_differs
      - file: reduce_sum_for_geologists
      - file: Prior_Choice_Normal_vs_Cauchy
      - file: ckdtree_nearest_ocean_explainer
  - caption: Archive
    chapters:
      - file: preprint_additive_archive
```

- [ ] **Step 2: Remove `callmap` from "Getting started"**

Replace

```yaml
  - caption: Getting started
    chapters:
      - file: installation
      - file: api
      - file: callmap
      - file: troubleshooting
```

with

```yaml
  - caption: Getting started
    chapters:
      - file: installation
      - file: api
      - file: troubleshooting
```

- [ ] **Step 3: Add the Developer part between Explainers and Archive**

Replace

```yaml
      - file: ckdtree_nearest_ocean_explainer
  - caption: Archive
    chapters:
      - file: preprint_additive_archive
```

with

```yaml
      - file: ckdtree_nearest_ocean_explainer
  - caption: Developer
    chapters:
      - file: callmap
  - caption: Archive
    chapters:
      - file: preprint_additive_archive
```

- [ ] **Step 4: Verify the YAML parses and the part exists**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
python -c "
import yaml, pathlib
toc = yaml.safe_load(pathlib.Path('docs/_toc.yml').read_text())
caps = [p['caption'] for p in toc['parts']]
print(caps)
dev = [p for p in toc['parts'] if p['caption'] == 'Developer'][0]
print(dev)
gs = [p for p in toc['parts'] if p['caption'] == 'Getting started'][0]
assert all(c['file'] != 'callmap' for c in gs['chapters']), 'callmap still under Getting started'
assert dev['chapters'] == [{'file': 'callmap'}]
print('OK')
"
```

Expected:

```
['Getting started', 'Tutorial', 'Explainers', 'Developer', 'Archive']
{'caption': 'Developer', 'chapters': [{'file': 'callmap'}]}
OK
```

- [ ] **Step 5: Commit**

```bash
git add docs/_toc.yml
git commit -m "docs: move the call map out of Getting started into a Developer part"
```

---

### Task 3: Replace `stan_models_explanation_v2.md` with a seven-model `stan_models.md`

**Files:**
- Create: `docs/stan_models.md`
- Delete: `docs/stan_models_explanation_v2.md` (574 lines)
- Modify: `docs/_toc.yml` (the `Explainers` part)
- Modify: `docs/reduce_sum_for_geologists.md:279`
- Modify: `docs/README.md:36`
- Modify: `.dockerignore:10`

**Interfaces:**
- Consumes: the `Developer` part added in Task 2 — do not remove it while editing `_toc.yml`.
- Produces: the page `docs/stan_models.md`, linkable as `[Stan models](stan_models.md)`. Task 5 relies on the fact that this task has already deleted `stan_models_explanation_v2.md:110`, which was the only inbound link to `why_plugin_p50_differs.md`.

**Why:** §9.8 rates this page **rewrite → `stan_models.md`**. Its 574 lines are organised around "Ensemble vs Direct sampling", and the ensemble models were archived to `archive/submission-2026-04/stan_models/` in 2026-09 — so more than half the page compares the shipped models against something that no longer ships, complete with a `model_type="ensemble"` usage example for a value that now raises `ValueError`. The replacement is a catalogue: what each shipped model is for, how the marginal likelihood works, how threading works, and where the archive is. The marginalization mathematics and the `reduce_sum` mechanics already have their own pages (`marginalization_explainer.md`, `reduce_sum_for_geologists.md`) — link out rather than re-derive.

**Inbound links, found by grep before writing anything (Step 1 below re-runs this):**

| location | disposition |
|---|---|
| `docs/_toc.yml:24` — `- file: stan_models_explanation_v2` | retarget to `stan_models` (Step 4) |
| `docs/reduce_sum_for_geologists.md:279` — `[Stan models overview](stan_models_explanation_v2.md)` | retarget (Step 5) |
| `docs/README.md:36` — table row naming it *and* a `stan_explanation.md` that does not exist | rewrite the row (Step 6) |
| `docs/why_plugin_p50_differs.md:60` — `[Stan models explained](stan_models_explanation_v2.md)` | **no action** — Task 5 deletes that whole file |
| `.dockerignore:10` — `stan_models_explanation_v2.pdf` | drop the line (Step 7); it ignores a PDF export of a page that will no longer exist |
| `RESUME.md:2556` | **no action** — RESUME.md is a dated working log describing what was true in a past pass; it is excluded from the release archives and must not be back-edited |

- [ ] **Step 1: Re-run the inbound-link sweep and confirm the list**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -rn "stan_models_explanation" . --exclude-dir=.git --exclude-dir=_build
ls -1 src/TEXAS/stan_models/*.stan
```

Expected: the six locations in the table above, and **seven** `.stan` files (plan 04 has already archived the two `*_marginal_truncated_prior.stan` models). If nine files are listed, **stop** — plan 04 has not run yet, and this plan must run after it.

- [ ] **Step 2: Write the replacement page**

Create `docs/stan_models.md` with exactly this content:

````markdown
# Stan models shipped with TEXAS

`src/TEXAS/stan_models/` holds **seven** `.stan` files: the three forward
calibrations the revised manuscript fits, the three inverse (proxy → temperature)
models it runs, and one straight-line reference model used in the SI figures.
Everything else ever written for this project lives in
`archive/submission-2026-04/stan_models/`, whose README names each retired file,
says why it was retired, and shows how to run one by absolute path.

`pyproject.toml` declares package data as `stan_models/*.stan` — a non-recursive
glob — so only these seven reach the wheel.

## Naming convention

```
{transform}_{curve}_{params}_{datasources}_{variant}.stan
```

| position | values used in the shipped set |
|---|---|
| transform | *(none)* = forward calibration; `invT_` = inverse |
| curve | `gen_logi` = generalized logistic (Richards); `linear` |
| params | `fixed` = upper asymptote pinned at 1 |
| data sources | `culmeso` = culture + mesocosm; `hier_crtp` = hierarchical coretop |
| variant | `univ` / `multiv` = without / with non-thermal predictors; `priorApprox` = stage-2 fit using stage-1 hyperpriors; `eiv` = errors-in-variables; `t0shift` = predictors shift T₀; `marginal` = ensemble marginalized analytically; `unconstrained` = no bound on T |

## Forward calibration

| file | role |
|---|---|
| `gen_logi_fixed_culmeso.stan` | **Stage 1.** One generalized logistic fitted jointly to the culture and mesocosm data — the controlled experiments, which constrain the *shape* of the response. Its posterior mean and SD for `{t0, k, b, v}` are the hyperpriors every `priorApprox` model consumes, so this fit runs first. |
| `gen_logi_fixed_hier_crtp_univ_priorApprox.stan` | **Stage 2, thermal only.** Coretop fit of the Scaled Ring Index against temperature with no non-thermal predictors. It is also the source of `R2_thermal`, which the EIV model requires **as data**. |
| `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift.stan` | **The production calibration** (compset `GHEB`). Coretop fit with the G₂/₃ ratio and NO₃ entering as a shift of the curve's location parameter — the manuscript's **T₀-shift parameterization** — plus Bayesian errors-in-variables on those predictors and on the RI. Both bundled posteriors were fitted with it. |

All three share the curve

```
RI = b + (1 - b) / (1 + exp(-k * (T - T0)))^(1/v)
```

with the upper asymptote fixed at 1 and Q fixed at 1. **T₀ is the curve's
location parameter, not its inflection point.** The steepest response sits at
`T0 - ln(v)/k`, several °C below T₀ for the fitted ν, and the slope varies
severalfold across the sampled range — so there is no single thermal sensitivity
to quote for this curve.

In the T₀-shift model the predictors move T₀ rather than the mean:

```
T0_eff[i] = T0 + gamma_G23 * g23_true[i] + gamma_NO3 * log10(no3_true[i])
mu[i]     = b + (1 - b) / (1 + exp(-k * (T[i] - T0_eff[i])))^(1/v)
```

Because they act *inside* the logistic, `mu` stays within `(b, 1)` for any finite
predictor value and any finite coefficient. That bounded-by-construction property
is why the parameterization was adopted.

## Inverse reconstruction

| file | role |
|---|---|
| `invT_gen_logi_fixed_univ_marginal_unconstrained.stan` | Univariate inverse — proxy only, no predictors. Used by the quickstart and by `SI_code03`. |
| `invT_gen_logi_fixed_multiv_marginal_unconstrained.stan` | Multivariate inverse for the additive (β-on-μ) forward arm, which the revision reports as the comparison arm. |
| `invT_gen_logi_fixed_multiv_marginal_unconstrained_t0shift.stan` | Multivariate inverse for the T₀-shift forward arm. **The production inverse.** |

`predict_T_from_proxyObs()` selects among these for you: the univariate file when
no predictor arrays are supplied, a multivariate file when they are, and the
`t0shift` file when the forward posterior being marginalized over was fitted with
the T₀-shift parameterization.

## Reference model

`linear_model.stan` fits `proxy = slope · T + intercept` with both coefficients
constrained non-negative. It is the straight-line form the sigmoid calibrations
are compared against in the SI figures, and is used by the preprocessing and
analysis notebooks. It is deliberately *not* a general-purpose linear regression.

## How the marginal likelihood works

The inverse question is: given an observed proxy value, what temperature produced
it — allowing for the fact that the calibration curve is itself uncertain? TEXAS
answers it by drawing `M` parameter sets from the forward posterior and
integrating over them.

The direct way would be to sample an `N × M` matrix of temperatures, one per
observation per forward draw. The shipped models instead sample `N` temperatures
and do that integral analytically inside the log-density:

```stan
for (n in 1:N) {
  vector[M] llk;
  for (m in 1:M)
    llk[m] = normal_lpdf(proxyObs[n] | fwd(t_est[n], params[m]), sigma[m]);
  lp += log_sum_exp(llk) - log(M);   // log[(1/M) * sum_m exp(llk_m)]
}
```

`log_sum_exp(llk) - log(M)` **is** the marginalization — the log of the mean
likelihood across the ensemble. It targets the same posterior as the matrix
formulation from a parameter space two orders of magnitude smaller, with far
better sampling geometry. Why the geometry matters, and what it does to the
effective sample size, is worked through in
[Why marginalization improves inverse TEXAS sampling](marginalization_explainer.md).

## How threading works

All three inverse models wrap that observation loop in Stan's `reduce_sum`, which
splits the `N` observations into chunks evaluated on separate CPU threads. The
chunk size is the `grainsize` data variable:

- `grainsize = 1` → maximum parallelism (best on many cores)
- `grainsize = N` → no parallelism, bit-for-bit the same result

Threading is active only when the model is compiled with `STAN_THREADS=True` and
run with `threads_per_chain > 1`; otherwise `reduce_sum` evaluates the same code
sequentially. It pays off when `N` is large — hundreds of observations — and the
`M` loop is expensive; below roughly `N = 20` the overhead can outweigh the gain.
[Understanding `reduce_sum` and `ll_chunk`](reduce_sum_for_geologists.md) explains
the mechanism without assuming any Stan.

The forward calibrations are **not** threaded. Their cost is in the hierarchical
structure and the latent EIV variables, not in one long independent loop, so
there is nothing for `reduce_sum` to split.

## See also

- [Why marginalization improves inverse TEXAS sampling](marginalization_explainer.md)
- [Understanding `reduce_sum` and `ll_chunk`](reduce_sum_for_geologists.md)
- [Sampler budget](sampler_budget.md) — measured runtimes for these models
- [Archive — the preprint's additive (β) formulation](preprint_additive_archive.md)
- `archive/submission-2026-04/stan_models/README.md` — the retired models and how to run one
````

- [ ] **Step 3: Delete the old page**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git rm docs/stan_models_explanation_v2.md
```

- [ ] **Step 4: Retarget the `_toc.yml` entry**

In `docs/_toc.yml`, replace

```yaml
      - file: stan_models_explanation_v2
```

with

```yaml
      - file: stan_models
```

(It stays in the same position in the `Explainers` part, between `sampler_budget` and `marginalization_explainer`.)

- [ ] **Step 5: Fix the inbound link in `reduce_sum_for_geologists.md`**

At `docs/reduce_sum_for_geologists.md:279`, replace

```markdown
*See also: [Why marginalization improves inverse sampling](marginalization_explainer.md)
and the [Stan models overview](stan_models_explanation_v2.md).*
```

with

```markdown
*See also: [Why marginalization improves inverse sampling](marginalization_explainer.md)
and the [Stan models overview](stan_models.md).*
```

- [ ] **Step 6: Fix the `docs/README.md` structure table**

At `docs/README.md:36`, replace

```markdown
| `PSM.md`, `stan_explanation.md`, `stan_models_explanation_v2.md` | Explainers |
```

with

```markdown
| `PSM.md`, `model_validation.md`, `stan_models.md`, `sampler_budget.md` | Explainers |
```

(The row also named `stan_explanation.md`, which has not existed for some time — dropping it is part of the same fix.)

- [ ] **Step 7: Drop the stale `.dockerignore` pattern**

At `.dockerignore:10`, delete the line

```
stan_models_explanation_v2.pdf
```

It ignored a PDF export of the page being deleted; no such file is ever produced now.

- [ ] **Step 8: Verify no reference to the old page survives, and the new one is reachable**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -rn "stan_models_explanation" . --exclude-dir=.git --exclude-dir=_build
```

Expected: exactly one line — `RESUME.md:2556` — and nothing else. (`docs/why_plugin_p50_differs.md:60` will still hit at this point if Task 5 has not run; that is expected and Task 5 removes the file. If Task 5 has already run, this grep returns only the RESUME.md line.)

Then:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
test -f docs/stan_models.md && echo "page exists"
grep -c "truncated_prior\|constraint_type\|min_temp\|model_type\|ensemble" docs/stan_models.md
grep -n "boundedT" docs/stan_models.md
wc -l docs/stan_models.md
```

Expected: `page exists`; the count is `0` — the new page must not mention the archived truncated-prior models, the removed `constraint_type` / `min_temp` arguments, `model_type`, or the archived ensemble models; the `boundedT` grep prints nothing; the line count is roughly 130.

Then check every model the page names actually ships:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
for f in $(grep -o '[A-Za-z0-9_]*\.stan' docs/stan_models.md | sort -u); do
  test -f "src/TEXAS/stan_models/$f" && echo "OK   $f" || echo "MISSING $f"
done
```

Expected: seven `OK` lines, no `MISSING`.

- [ ] **Step 9: Commit**

```bash
git add docs/stan_models.md docs/_toc.yml docs/reduce_sum_for_geologists.md docs/README.md .dockerignore
git add -u docs/stan_models_explanation_v2.md
git commit -m "docs: replace the ensemble-vs-direct page with a catalogue of the seven shipped Stan models"
```

---

### Task 4: Delete `Prior_Choice_Normal_vs_Cauchy.md`

**Files:**
- Delete: `docs/Prior_Choice_Normal_vs_Cauchy.md` (142 lines)
- Modify: `docs/_toc.yml` (the `Explainers` part)
- Modify: `docs/README.md:38`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the invariant `grep -rn -i cauchy docs/ --exclude-dir=_build` is empty, which Task 7 re-checks.

**Why:** §9.8 rates this page **delete**. No shipped Stan model uses a Cauchy prior — the scale priors are half-normal (`normal(0, 0.1)`), fixed in 2026-04 — and the manuscript never mentions one. The page argues against a formulation the codebase abandoned, using example code (`sigma_scaledRI ~ cauchy(0, 0.1)`, `sigma_t0_culmeso ~ cauchy(0, 1)`) that no longer appears in any `.stan` file. §9.8 counts 17 stale-term hits.

`src/TEXAS/plotting/prior_plot.py` mentions `"cauchy"` at lines 244–245 and 454–455, but that is a **renderer branch** — it formats a prior string if a posterior it is handed happens to declare one. It is not a claim about the shipped models, it is not documentation, and it is **out of scope**: do not touch it.

- [ ] **Step 1: Find every reference before deleting**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -rni "cauchy\|Prior_Choice" . --exclude-dir=.git --exclude-dir=_build
```

Expected hits: the page itself; `docs/_toc.yml:28`; `docs/README.md:38`; `docs/why_plugin_p50_differs.md:58` (Task 5 deletes that whole file — no action here); and the four `src/TEXAS/plotting/prior_plot.py` lines, which stay.

- [ ] **Step 2: Delete the page**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git rm docs/Prior_Choice_Normal_vs_Cauchy.md
```

- [ ] **Step 3: Remove the `_toc.yml` entry**

In `docs/_toc.yml`, delete the line

```yaml
      - file: Prior_Choice_Normal_vs_Cauchy
```

Leave the surrounding entries (`reduce_sum_for_geologists` above it, `ckdtree_nearest_ocean_explainer` below it) in place.

- [ ] **Step 4: Fix the `docs/README.md` structure table**

At `docs/README.md:38`, replace

```markdown
| `Prior_Choice_Normal_vs_Cauchy.md`, `ckdtree_nearest_ocean_explainer.md` | Method notes |
```

with

```markdown
| `ckdtree_nearest_ocean_explainer.md` | Method notes |
```

- [ ] **Step 5: Verify**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -rni "cauchy" docs/ --exclude-dir=_build
grep -rn "Prior_Choice" docs/ --exclude-dir=_build
```

Expected at this point: the only remaining hits are inside `docs/why_plugin_p50_differs.md` (lines 58 and 60), which Task 5 deletes. Both greps must be **completely empty** once Task 5 is done — Task 7 re-checks.

- [ ] **Step 6: Commit**

```bash
git add docs/_toc.yml docs/README.md
git add -u docs/Prior_Choice_Normal_vs_Cauchy.md
git commit -m "docs: delete the Normal-vs-Cauchy prior page; no shipped model uses a Cauchy prior"
```

---

### Task 5: Delete `why_plugin_p50_differs.md` and its interactive explainer

**Files:**
- Delete: `docs/why_plugin_p50_differs.md` (61 lines)
- Delete: `docs/_static/why-plugin-p50-differs.html`
- Modify: `docs/_toc.yml` (the `Explainers` part)
- Modify: `TEXAS-revision/gridT_inversion_characterization.md` (5 references; the directory may already have been moved to `archive/exploratory/gridT-inversion/` by an earlier plan — locate it, do not assume the path)
- Verify only: `archive/submission-2026-04/stan_models/README.md`, `src/TEXAS/stan/invT.py`

**Interfaces:**
- Consumes: Task 3, which rewrote `stan_models_explanation_v2.md:110` — the page's **only inbound documentation link** — out of existence.
- Produces: no page in the book references the plug-in-vs-Bayesian P50 argument or the truncated-prior inverse models.

**Why:** §9.8 rates this page **delete**. The plug-in-vs-Bayesian P50 argument does not appear in the revised manuscript, and the page's interactive sandbox is built around
`invT_gen_logi_fixed_univ_marginal_truncated_prior.stan` — one of the two models plan 04 archives. §9.8's consequence paragraph records that RESUME.md kept those two models in the wheel *only because this page explained them*; with the page gone the "ship what the manuscript runs" rule archives them, and the user has decided on archive.

**On the sole inbound link.** §9.8 states the page is linked from `stan_models_explanation_v2.md:110`. Step 1 confirms that by grep. That line read:

```markdown
bias `truncated_prior` was written to remove (see
[why the plug-in P50 differs](why_plugin_p50_differs.md)). `reparameterized` and
```

Task 3 deleted the entire file containing it, so **no documentation link needs repairing here.** The remaining references are outside `docs/` and are handled below.

- [ ] **Step 1: Confirm the inbound-link picture**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -rni "why_plugin\|why-plugin" . --exclude-dir=.git --exclude-dir=_build
test -f docs/stan_models_explanation_v2.md && echo "TASK 3 NOT DONE — stop" || echo "task 3 done"
```

Expected: `task 3 done`, and the surviving hits are **only**:

| location | disposition |
|---|---|
| `docs/why_plugin_p50_differs.md` (lines 37, 39) | self-references inside the file being deleted |
| `docs/_toc.yml:26` | remove (Step 3) |
| `TEXAS-revision/gridT_inversion_characterization.md` (lines ~24, 26, 28, 49, 58) | repair (Step 4) |
| `archive/submission-2026-04/stan_models/README.md:36` | plan 04 owns this row; verify (Step 5) |
| `src/TEXAS/stan/invT.py:403` | plan 04 owns this string; verify (Step 5) |
| `RESUME.md:1431` | **no action** — dated working log, not back-edited |

- [ ] **Step 2: Delete the page and its embedded explainer**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git rm docs/why_plugin_p50_differs.md docs/_static/why-plugin-p50-differs.html
```

- [ ] **Step 3: Remove the `_toc.yml` entry**

In `docs/_toc.yml`, delete the line

```yaml
      - file: why_plugin_p50_differs
```

Leave `marginalization_explainer` above it and `reduce_sum_for_geologists` below it in place.

- [ ] **Step 4: Repair the gridT working note's dead pointers**

Locate the file first — an earlier plan moves `TEXAS-revision/` to `archive/exploratory/gridT-inversion/`, so do not hardcode the path:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git ls-files | grep gridT_inversion_characterization.md
```

That note quotes the grid-inversion reference implementation **inline**, so the algorithm is not lost — only the line-number pointers into the deleted HTML go dead. Insert one provenance note and leave the quoted code exactly as it is. Replace

```markdown
The grid method exists as the **reference implementation embedded in the docs
teaching page** `docs/_static/why-plugin-p50-differs.html`:

- the copy-pasteable **Python** version, `docs/_static/why-plugin-p50-differs.html:217-222`
- the live **JS** version driving the sandbox, `posterior()` + `quantile()` at
  `docs/_static/why-plugin-p50-differs.html:268-280`
```

with

```markdown
The grid method existed as the **reference implementation embedded in the docs
teaching page** `docs/_static/why-plugin-p50-differs.html`:

- the copy-pasteable **Python** version, `why-plugin-p50-differs.html:217-222`
- the live **JS** version driving the sandbox, `posterior()` + `quantile()` at
  `why-plugin-p50-differs.html:268-280`

> **That page was removed at the 2026-09 repository finalization** — the
> plug-in-vs-Bayesian P50 argument is not part of the revised manuscript, and the
> truncated-prior inverse it demonstrated was archived to
> `archive/submission-2026-04/stan_models/`. The line references below are to the
> deleted file and are kept for provenance; both excerpts are quoted in full
> here, so nothing needed to follow the argument is missing. Recover the original
> page with `git log --diff-filter=D -- docs/_static/why-plugin-p50-differs.html`.
```

The two later references, `**Python reference — `why-plugin-p50-differs.html:220-222`:**` and `**JS reference — `why-plugin-p50-differs.html:271-274`:**`, are already written without the `docs/_static/` path and are covered by that note — leave them unchanged.

- [ ] **Step 5: Verify plan 04 already cleared the two non-docs references**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -rn "why_plugin_p50_differs" src/ archive/ 2>/dev/null
```

Expected: **no output.** Plan 04 removes `constraint_type` (taking the `invT.py:403` error string with it) and rewrites the archive README's shipped-models table when it moves the two truncated-prior files.

If either hit survives, plan 04 left a dangling documentation link. Repair it here — this is a link fix, not an API change:

- In `src/TEXAS/stan/invT.py`, delete the clause `` -- see docs/why_plugin_p50_differs.md `` (and its surrounding parentheses) from the error message, leaving the rest of the sentence intact.
- In `archive/submission-2026-04/stan_models/README.md`, change the phrase `and the subject of `docs/why_plugin_p50_differs.md`` to `and the subject of a docs page removed at the 2026-09 finalization`.

Then re-run the grep and confirm it is empty.

- [ ] **Step 6: Verify the book has no dangling reference left**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -rni "why_plugin\|why-plugin\|plug-in P50" docs/ --exclude-dir=_build
grep -rni "cauchy" docs/ --exclude-dir=_build
ls docs/_static/
```

Expected: both greps print **nothing**; `docs/_static/` lists `callmap.html`, `custom.css`, `sampler-budget.data.json`, `sampler-budget.html`, `texas_logo.svg` — and no `why-plugin-p50-differs.html`.

- [ ] **Step 7: Commit**

```bash
git add docs/_toc.yml
git add -u docs/why_plugin_p50_differs.md docs/_static/why-plugin-p50-differs.html
git add -A -- '*gridT_inversion_characterization.md'
git commit -m "docs: delete the plug-in-vs-Bayesian P50 page and its sandbox"
```

---

### Task 6: Verify the KEEP pages need no edit

**Files:**
- Read only: `docs/PSM.md`, `docs/model_validation.md`, `docs/marginalization_explainer.md`, `docs/sampler_budget.md`, `docs/_static/sampler-budget.html`, `docs/_static/sampler-budget.data.json`, `docs/reduce_sum_for_geologists.md`, `docs/preprint_additive_archive.md`
- Modify: only if a grep below reports a genuine hit

**Interfaces:**
- Consumes: Tasks 3–5 (the pages those tasks retargeted must already be in their final state, or this task's link greps will report stale hits).
- Produces: a written verdict per page, and — if any grep fires — the minimal edit that clears it.

**Why:** §9.8 rates six pages **keep**, but "keep" is a claim, and this task is where it is tested rather than assumed. The specific risk is that a page still uses a term the revised manuscript dropped, or still names one of the two Stan models plan 04 archived.

**Second-owner warning:** `docs/model_validation.md` and `docs/troubleshooting.md` are **also edited by plan 02** (the kriged-cache folder rename). If any step below turns into an edit to either file, **re-read the file immediately beforehand** — plan 02 may have landed since this plan was written.

- [ ] **Step 1: Grep every KEEP page for terms the revision dropped**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
for f in PSM.md model_validation.md marginalization_explainer.md sampler_budget.md \
         reduce_sum_for_geologists.md preprint_additive_archive.md callmap.md \
         ckdtree_nearest_ocean_explainer.md index.md troubleshooting.md; do
  echo "=== $f ==="
  grep -nEi "boundedT|hard_constraint|Q_crtp|Q_culmeso|beta0_|ensemble model|model_type|Cauchy" "docs/$f"
done
```

Expected: every section header, no hits underneath. `boundedT` in particular must not appear — the code token is `t0shift` and the manuscript term is "T₀-shift parameterization".

Any hit is a real finding: fix it in place (rename `boundedT` → `t0shift`, drop the sentence naming an archived model) and note it in the task report.

- [ ] **Step 2: Grep every KEEP page for the two archived truncated-prior models**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -rn "truncated_prior\|constraint_type\|min_temp" docs/ --exclude-dir=_build
```

Expected: **no output.** These names left the public API in plan 04; a docs page that still mentions them documents an argument a user cannot pass.

- [ ] **Step 3: Check every Stan model named anywhere in the docs still ships**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -rho '[A-Za-z0-9_]*\.stan' docs/ --exclude-dir=_build | sort -u | while read -r f; do
  if [ -f "src/TEXAS/stan_models/$f" ]; then echo "SHIPPED  $f"
  elif [ -f "archive/submission-2026-04/stan_models/$f" ]; then echo "ARCHIVED $f"
  else echo "UNKNOWN  $f"; fi
done
```

Expected: `SHIPPED` for the seven live models. An `ARCHIVED` line is acceptable **only** on `docs/preprint_additive_archive.md`, whose entire subject is the archived additive arm — check with `grep -rn "<name>" docs/` which page names it, and if it is any other page, rewrite that sentence to name the shipped equivalent. `UNKNOWN` is always a defect: the docs name a file that exists nowhere.

- [ ] **Step 4: Confirm the sampler-budget assets are intact and still generated**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
ls -l docs/_static/sampler-budget.html docs/_static/sampler-budget.data.json
grep -n "sampler-budget" docs/sampler_budget.md
grep -n "build_sampler_budget" .github/workflows/docs.yml
```

Expected: both assets present; `docs/sampler_budget.md` embeds `_static/sampler-budget.html`; the workflow still runs `python docs/_scripts/build_sampler_budget.py` before the build. Neither `_static` file is hand-edited — they are regenerated by that script from the committed `.data.json` snapshot.

- [ ] **Step 5: Confirm every internal Markdown link in the KEEP pages resolves**

Run:

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
python - <<'PY'
import pathlib, re
docs = pathlib.Path("docs")
bad = []
for md in docs.rglob("*.md"):
    if "_build" in md.parts or "superpowers" in md.parts:
        continue
    for m in re.finditer(r"\]\(([^)#\s]+\.md)(#[^)]*)?\)", md.read_text(encoding="utf-8")):
        target = (md.parent / m.group(1)).resolve()
        if not target.exists():
            bad.append(f"{md}: {m.group(1)}")
print("\n".join(bad) or "all internal .md links resolve")
PY
```

Expected: `all internal .md links resolve`.

- [ ] **Step 6: Write the verdict and commit any fixes**

Record, per page, `clean` or the edit that was made:

- `PSM.md` — framework description, in the revised text
- `model_validation.md` — validation section; **plan 02 also owns this file**
- `marginalization_explainer.md` — the marginal inverse, in the revised SI
- `sampler_budget.md` (+ `_static/sampler-budget.*`) — MCMC budget, SI Figs. S17–S18
- `reduce_sum_for_geologists.md` — `reduce_sum` is cited at `main.tex:900` and used by all three shipped inverse models
- `preprint_additive_archive.md` — the index of what the archive reproduces

If nothing changed, this task commits nothing and reports "all six KEEP pages verified clean, no edits". If something changed:

```bash
git add docs/
git commit -m "docs: clear stale terms found while verifying the kept explainer pages"
```

---

### Task 7: Build the book and prove nothing is broken

**Files:**
- Read only: all of `docs/`
- Modify: only whatever the build reports as broken

**Interfaces:**
- Consumes: Tasks 1–6 complete.
- Produces: the spec's §10 items 5 and 11 satisfied.

**Why:** §10.5 requires `jupyter-book build docs/` with no warnings about missing files; §10.11 requires no broken cross-references after §9.8 and `grep -rn cauchy docs/` empty. This is the gate.

- [ ] **Step 1: Start from a clean build directory**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
rm -rf docs/_build
```

(`docs/_build/` is gitignored; a stale build otherwise poisons the greps below with hits from deleted pages.)

- [ ] **Step 2: Confirm the environment**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
conda activate texas-env
python -c "import TEXAS; print(TEXAS.__version__)"
python -c "import jupyter_book; print(jupyter_book.__version__)"
```

Expected: a version prints for TEXAS (autodoc imports it), and the Jupyter Book version is **1.x**. If it is 2.x, run `pip install "jupyter-book<2"` — v2/MyST cannot read this book's `jb-book` `_toc.yml`.

- [ ] **Step 3: Confirm every `_toc.yml` entry resolves to a file that exists**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
python - <<'PY'
import yaml, pathlib
docs = pathlib.Path("docs")
toc = yaml.safe_load((docs / "_toc.yml").read_text())

def files(node):
    if isinstance(node, dict):
        if "file" in node:
            yield node["file"]
        for key in ("parts", "chapters", "sections"):
            for child in node.get(key, []):
                yield from files(child)
    elif isinstance(node, list):
        for child in node:
            yield from files(child)

missing = []
for f in [toc["root"], *files(toc)]:
    if not any((docs / f).with_suffix(ext).exists() for ext in (".md", ".ipynb", ".rst")):
        missing.append(f)
print("MISSING:", missing or "none")
PY
```

Expected: `MISSING: none`.

The `_toc.yml` at this point must read exactly:

```yaml
format: jb-book
root: index
parts:
  - caption: Getting started
    chapters:
      - file: installation
      - file: api
      - file: troubleshooting
  - caption: Tutorial
    chapters:
      - file: tutorial/intro
        sections:
          - file: tutorial/module1_prior
          - file: tutorial/module2_bayesian_updating
          - file: tutorial/module3_curve_explorer
          - file: tutorial/module4_mcmc
          - file: tutorial/module5_results
  - caption: Explainers
    chapters:
      - file: PSM
      - file: model_validation
      - file: sampler_budget
      - file: stan_models
      - file: marginalization_explainer
      - file: reduce_sum_for_geologists
      - file: ckdtree_nearest_ocean_explainer
  - caption: Developer
    chapters:
      - file: callmap
  - caption: Archive
    chapters:
      - file: preprint_additive_archive
```

- [ ] **Step 4: Regenerate the two generated pages, exactly as CI does**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
python docs/_scripts/build_callmap.py
python docs/_scripts/build_sampler_budget.py
```

Expected: both exit 0. `build_callmap.py` fails loudly if `_scripts/callmap_content.py` names a function that no longer exists — after plan 04 removed public API arguments, that is a real possibility, and a failure here is a finding to report, not to paper over.

- [ ] **Step 5: Build the book and capture the log**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
jupyter-book build docs/ 2>&1 | tee /tmp/claude-1000/-home-ronnie-rattan-Documents-GitHub-TEXAS/68ae6f0f-4a75-4e97-a12d-d6e12fc1b02c/scratchpad/jb-build.log
```

Expected: ends with `Finished generating HTML for book.`

- [ ] **Step 6: Check the log for missing files and broken references**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -nEi "WARNING|ERROR" /tmp/claude-1000/-home-ronnie-rattan-Documents-GitHub-TEXAS/68ae6f0f-4a75-4e97-a12d-d6e12fc1b02c/scratchpad/jb-build.log \
  | grep -Ei "not found|toctree|nonexisting|undefined label|broken|missing file|document isn't included"
```

Expected: **no output.** Any hit naming `stan_models_explanation_v2`, `why_plugin_p50_differs`, `Prior_Choice_Normal_vs_Cauchy`, or `callmap` is a link this plan failed to repair — fix it and rebuild.

- [ ] **Step 7: Run the spec's §10.11 greps**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -rn -i cauchy docs/ --exclude-dir=_build
grep -rni "why_plugin\|why-plugin\|Prior_Choice\|stan_models_explanation" docs/ --exclude-dir=_build
grep -rn "truncated_prior\|constraint_type\|min_temp\|boundedT" docs/ --exclude-dir=_build
```

Expected: all three print **nothing**.

- [ ] **Step 8: Confirm no page references a Stan model that no longer ships**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
grep -rho '[A-Za-z0-9_]*\.stan' docs/ --exclude-dir=_build | sort -u | while read -r f; do
  [ -f "src/TEXAS/stan_models/$f" ] || echo "NOT SHIPPED: $f  ->  $(grep -rl "$f" docs/ --exclude-dir=_build | tr '\n' ' ')"
done
ls -1 src/TEXAS/stan_models/*.stan | wc -l
```

Expected: the only `NOT SHIPPED` lines point at `docs/preprint_additive_archive.md`, which documents the archived additive arm on purpose; the model count is **7**.

- [ ] **Step 9: Confirm the built site has the pages and not the deleted ones**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
ls docs/_build/html/*.html | xargs -n1 basename
```

Expected: `stan_models.html` and `callmap.html` present; `stan_models_explanation_v2.html`, `why_plugin_p50_differs.html` and `Prior_Choice_Normal_vs_Cauchy.html` **absent**.

- [ ] **Step 10: Commit**

The build directory is gitignored, so this commit carries only whatever Step 6 or 8 forced. If nothing changed, skip the commit and report the verification result.

```bash
git status --short docs/
git add docs/
git commit -m "docs: fix cross-references surfaced by the book build"
```

---

## Self-review

**1. Spec coverage.** §9.8's table has eight rows. `PSM.md` / `model_validation.md` / `marginalization_explainer.md` / `sampler_budget.md` → Task 6. `reduce_sum_for_geologists.md` → Task 6 (and Task 3 Step 5 retargets its final link). `ckdtree_nearest_ocean_explainer.md` → Task 1. `preprint_additive_archive.md` → Task 6. `callmap.md` → Task 2. `stan_models_explanation_v2.md` → Task 3. `Prior_Choice_Normal_vs_Cauchy.md` → Task 4. `why_plugin_p50_differs.md` → Task 5. §9.8's link list: `stan_models_explanation_v2.md:110` → Task 5 Step 1 confirms Task 3 removed it; `Prior_Choice` linked only from the deleted page → Task 4 Step 1 confirms. §9.8's consequence paragraph and `docs/installation.md:399` are declared out of scope under **Ordering and ownership**, with their owning plans named. §10.5 and §10.11 → Task 7 Steps 5–8.

**2. Placeholder scan.** No "TBD", no "similar to Task N", no "summarize the section". The replacement page is written out in full in Task 3 Step 2; every `_toc.yml` before/after is quoted literally; every verification step gives the command and its expected output. Task 5 Step 5 and Task 6 Steps 1–3 are conditional ("if the grep fires"), but each spells out the exact edit to make, so they are not placeholders.

**3. Type consistency.** The new page is `docs/stan_models.md` everywhere — the `_toc.yml` entry is `stan_models`, the link in `reduce_sum_for_geologists.md` is `stan_models.md`, the `docs/README.md` row says `stan_models.md`, and Task 7's build check expects `stan_models.html`. "Seven shipped models" is used consistently in the header, Task 3 Step 1's guard, the new page's opening line, and Task 7 Step 8's count. The token is `t0shift` throughout; `boundedT` appears only as something the greps must *not* find.

**Fixed during review:** the first draft verified `grep -rn -i cauchy docs/` without excluding `docs/_build`, which a stale local build would fail; Task 7 Step 1 now deletes `docs/_build` first and every grep passes `--exclude-dir=_build`. The first draft also assumed `TEXAS-revision/` was still at its original path when Task 5 repairs it; Step 4 now locates the file with `git ls-files` because an earlier plan moves that directory to `archive/exploratory/gridT-inversion/`.
