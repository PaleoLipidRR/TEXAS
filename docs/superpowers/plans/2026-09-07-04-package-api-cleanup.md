# Package API Cleanup (spec §9.6 + §9.7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the six unused public helpers from `src/TEXAS`, bring every public docstring to one Google-style standard behind a test + ruff guard, fold the redundant second wrapper layer out of the inverse path, archive the two truncated-prior Stan models with their `constraint_type`/`min_temp` API, and replace three hard-coded column/key literals with the resolvers the package already has.

**Architecture:** Three independent strands, sequenced so each ends green. (1) Deletions and documentation touch only docstrings, `__all__` lists and one new `CHANGELOG.md`; they land first so the new `tests/test_public_api_docs.py` guard can be switched on against a clean tree. (2) The Stan-model archive move and the `predict_temperature_from_proxyObs` fold are behaviour changes to the inverse path, done in that order so the API only shrinks once. (3) The column-name fixes and the optional DataFrame convenience sit on top and can be dropped without disturbing anything earlier.

**Tech Stack:** Python ≥ 3.10, xarray, numpy, pandas, cmdstanpy/CmdStan 2.36.0, pytest, ruff 0.9.7, Jupyter Book (Sphinx autodoc + napoleon).

**Spec:** `docs/superpowers/specs/2026-09-07-repo-finalization-design.md`

## Global Constraints

- **Pre-1.0 (version `0.3.2`).** Removing a public name is allowed, but **every removal gets a changelog line.** The project has no changelog file today (verified: no `CHANGELOG.md`, no release-notes section in `README.md` or `docs/`, no GitHub release workflow) — Task 1 creates `CHANGELOG.md` at the repo root and every later task appends to its `## [Unreleased]` section.
- **`src/TEXAS/utils/naming.py::CONSTRAINT_CODES` must be left intact**, including the `hard_constraint`, `truncated_prior`, `reparameterized` and `soft` entries. It is a name *grammar*, not a list of selectable options: it must keep decoding case ids of reconstructions already on disk and on Zenodo. Narrowing it would orphan those files. `tests/test_stan_model_archive.py::test_name_grammar_still_decodes_withdrawn_constraints` pins this — do not touch that test.
- **Parameter suffix priority is `crtp` > `culmesocore` > `culmeso` > `meso` > `cul`.** Any docstring that states the order must state exactly this order.
- **The `Q` parameter was dropped in 2026-03 and must not come back.** No new docstring, example or test may name `Q` as a live parameter of the generalized logistic; the shipped curve uses Q = 1.
- **Pytest baseline: 351 passed, 11 skipped**, run as `.venv/bin/python -m pytest -q` (362 collected; verified on this tree). Every task must end with the suite green; the count grows only by tests the task adds, and no test may move from passed to skipped.
- **Run everything through the repo's `.venv`.** `.venv/bin/python -m pytest -q`, `.venv/bin/python -m ruff check .`, `.venv/bin/python -m build`. Every bare `pytest` / `ruff` / `python` in the steps below means that interpreter. The `.venv` is uv-managed and has no `pip`: install into it with `VIRTUAL_ENV=.venv uv pip install <pkg>`. **`ruff` and `build` are not in it yet** — `VIRTUAL_ENV=.venv uv pip install ruff build` before the steps that use them. Do **not** use a conda base interpreter — it pairs numpy 2.5.1 with scipy 1.11.4 and fails collection on 11 modules, which produces a different and wrong baseline.
- **Python ≥ 3.10** (`pyproject.toml` `requires-python`). `X | None` unions and `dict[str, ...]` builtins are fine; nothing may require 3.11+.
- Ruff 0.9.7 is the pinned linter (`.github/workflows/lint.yml`). `ruff check .` must be clean at the end of every task.

## Notes carried from the spec

- **Spec §9.6 also observes that five modules exceed 800 lines** (`data/screening.py` 1241, `plotting/residual_maps.py` 1214, `utils/naming.py` 888, `data/builder.py` 855, `plotting/prior_plot.py` 764) and explicitly does not act on it. **Splitting them is out of scope for this plan.** Do not restructure those files; edit them in place.
- **`load_or_build_halo_cache()` is NOT deleted here.** It is the seventh row of §9.6's deletion table, but plan 02 owns it as part of the kriged-cache work and deletes it there. **This plan deletes six names, not seven.** Leave `plotting/residual_maps.py` and the `load_or_build_halo_cache` entries in `plotting/__init__.py` alone.
- **Archive destination.** Task 6 moves the two truncated-prior models to `archive/pre-submission/stan_models/`, which is what spec §9.8 says. That directory exists by the time this plan runs: **plan 01** (`docs/superpowers/plans/2026-09-07-01-repo-hygiene.md`, Task 2) creates it and fills it with the 15 + 4 development models from `src/TEXAS/stan_models/archive/` and `archive_pre_annotated/`. **This plan therefore depends on plan 01 having landed.**
  `utils/paths.py::STAN_ARCHIVE_DIR` deliberately does **not** cover it — it stays pinned to `archive/submission-2026-04/stan_models`, which is where the eight 2026-04 models live and which `SI_code02a` and the refit scripts still resolve by plain stem. So the two moved models are reachable by **absolute path only**. That is fine and needs no resolver change: after Task 6 removes `constraint_type`, `_select_invT_stan_file` cannot construct their names at all, so nothing can select them by stem in the first place, and `StanCompiler.resolve_stan_path()` passes an absolute path straight through for anyone who wants to run one. **Do not extend `STAN_ARCHIVE_DIR` or the compiler fallback.**
  Every *other* reference in this plan to `archive/submission-2026-04/stan_models/` is about the eight models already there and is correct as written.
- **Spec §9.7 says `get_invT_posterior` is called by "both quickstarts".** It is not. Checked every code cell of `notebooks/quickstart_demo.ipynb` and `notebooks/quickstart_extended.ipynb`: zero code cells call it; the 13 grep hits are echoed source inside stored *output* text. `get_invT_posterior` has no caller outside `src/TEXAS`, which is why Task 7 can safely flip its `save=True` default to `save_results=False`.
- **Out of scope, recorded so nobody "fixes" it mid-task:** `data/builder.py:183` spells the suffix priority list `["crtp", "culmesocore", "culmes", "meso", "cul"]` — `"culmes"`, not `"culmeso"`. That is a real latent bug and it is not this plan's. Leave it.

---

### Task 1: Delete the six unused public names and start the changelog

**Files:**
- Create: `CHANGELOG.md`
- Modify: `src/TEXAS/utils/naming.py` (`__all__` lines 89 and 97; `default_version` lines 224–232; `describe_compset` lines 308–312)
- Modify: `src/TEXAS/models/logistics.py` (`generalized_logistic`, lines 78–102)
- Modify: `src/TEXAS/models/__init__.py` (lines 7, 28)
- Modify: `src/TEXAS/plotting/range_utils.py` (`compute_density_based_range`, lines 14–30; the now-unused `import scipy.stats as stats`, line 4)
- Modify: `src/TEXAS/plotting/__init__.py` (lines 5, 23)
- Modify: `src/TEXAS/utils/paths.py` (`get_repo_root`, lines 111–127)
- Modify: `src/TEXAS/utils/system_info.py` (`save_system_summary`, lines 246–259; the now-unused `import json`, line 18)
- Modify: `src/TEXAS/utils/__init__.py` (lines 1, 2, 6, 9)
- Modify: `src/TEXAS/stan/__init__.py` (lines 7, 20)
- Modify: `src/TEXAS/__init__.py` (lines 40, 81, 113, 150)
- Test: `tests/test_imports.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `CHANGELOG.md` with an `## [Unreleased]` section containing `### Removed` — later tasks append `### Removed` / `### Changed` / `### Added` bullets under that same heading. `TEXAS.__all__` loses `generalized_logistic` and `compute_density_based_range`; `TEXAS.plotting.__all__` loses `compute_density_based_range`; `TEXAS.models.__all__` loses `generalized_logistic`; `TEXAS.utils.__all__` loses `get_repo_root` and `save_system_summary`; `TEXAS.stan.__all__` loses `get_repo_root`; `TEXAS.utils.naming.__all__` loses `default_version` and `describe_compset`.

**Zero-caller verification (run before editing, record the output).** I ran this and the result is reproduced below; re-run it to confirm nothing landed in between.

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
for n in default_version describe_compset generalized_logistic \
         compute_density_based_range get_repo_root save_system_summary; do
  echo "### $n"
  grep -rnw "$n" src tests scripts streamlit_app notebooks docs README.md CLAUDE.md RESUME.md 2>/dev/null \
    | grep -v "docs/_static/callmap.html" | grep -v "docs/_build/" \
    | grep -v "docs/_scripts/" | grep -v "\.ipynb_checkpoints"
  echo
done
```

What it found — **every hit is the definition itself, an `__all__` entry, an import line, or the spec/RESUME row that asked for the removal. No caller anywhere:**

| name | hits |
|---|---|
| `default_version` | `naming.py:97` (`__all__`), `naming.py:224` (def), spec §9.6 row, `RESUME.md:1749` (already lists it for removal) |
| `describe_compset` | `naming.py:89` (`__all__`), `naming.py:308` (def), spec §9.6 row |
| `generalized_logistic` | `logistics.py:78` (def), `TEXAS/__init__.py:40,113`, `models/__init__.py:7,28`, spec §9.6 row |
| `compute_density_based_range` | `range_utils.py:14` (def), `TEXAS/__init__.py:81,150`, `plotting/__init__.py:5,23`, spec §9.6 row |
| `get_repo_root` | `paths.py:111` (def), `stan/__init__.py:7,20`, `utils/__init__.py:1,6`, spec §9.6 row |
| `save_system_summary` | `system_info.py:246` (def), `utils/__init__.py:2,9`, spec §9.6 row |

Two hits are excluded above and both are safe: `docs/_static/callmap.html` and `docs/_scripts/callmap_content.py` — the callmap is **generated** from an AST pass over `src/TEXAS` by `python docs/_scripts/build_callmap.py`, and `callmap_content.py`'s hand-written prose mentions none of the six (checked with `grep -nw` against that file: zero hits). Regenerating the callmap is a step below.

Two dead imports fall out of the deletions and ruff `F401` will catch them if you miss either:
- `range_utils.py:4` `import scipy.stats as stats` — `stats.gaussian_kde` is used **only** inside `compute_density_based_range`.
- `system_info.py:18` `import json` — `json.dump` is used **only** inside `save_system_summary` (verified: lines 253 and 256 are the only `json` references in the file).

`compute_density_based_range` calls `compute_sample_range` as its degenerate-KDE fallback, not the other way round, so deleting it leaves `compute_sample_range` intact.

- [ ] **Step 1: Re-run the zero-caller scan and read the output**

Run the `for` loop above. Expected: the six blocks match the table. If any block shows a hit that is not a definition, an `__all__`/import line, or a `docs/superpowers/specs/`/`RESUME.md` row, **stop and report it** — a caller appeared and the deletion is no longer safe.

- [ ] **Step 2: Write the failing regression test**

Append to `tests/test_imports.py`:

```python
import pytest

# §9.6 deletions (2026-09-07). These six had no caller anywhere in src/, tests/,
# scripts/, streamlit_app/, notebooks/ or docs/ -- only their own re-export
# lines. Re-exporting one again would put an unused name back on the public
# surface, which is what the audit was for.
DELETED_TOP_LEVEL = ["generalized_logistic", "compute_density_based_range"]
DELETED_SUBMODULE = [
    ("TEXAS.utils.naming", "default_version"),
    ("TEXAS.utils.naming", "describe_compset"),
    ("TEXAS.utils.paths", "get_repo_root"),
    ("TEXAS.utils.system_info", "save_system_summary"),
    ("TEXAS.models.logistics", "generalized_logistic"),
    ("TEXAS.plotting.range_utils", "compute_density_based_range"),
    ("TEXAS.stan", "get_repo_root"),
    ("TEXAS.utils", "get_repo_root"),
    ("TEXAS.utils", "save_system_summary"),
]


@pytest.mark.parametrize("name", DELETED_TOP_LEVEL)
def test_deleted_names_are_not_top_level_exports(name):
    """A deleted helper must not come back through TEXAS/__init__.py."""
    import TEXAS
    assert name not in TEXAS.__all__
    assert not hasattr(TEXAS, name)


@pytest.mark.parametrize("module,name", DELETED_SUBMODULE)
def test_deleted_names_are_gone_from_their_module(module, name):
    """Neither the definition nor any re-export of it survives."""
    import importlib
    mod = importlib.import_module(module)
    assert not hasattr(mod, name), f"{module}.{name} is still exported"
    assert name not in getattr(mod, "__all__", []), f"{module}.__all__ lists {name}"


def test_surviving_neighbours_still_export():
    """The deletions were surgical: their file-mates are untouched."""
    import TEXAS
    for kept in ("logistic", "logistic_fixed_upper", "inverse_logistic_fixed_upper",
                 "generalized_logistic_fixed_upper", "compute_sample_range",
                 "compute_suffix_specific_range", "compute_dataset_specific_range"):
        assert kept in TEXAS.__all__ and hasattr(TEXAS, kept)
```

- [ ] **Step 3: Run it to verify it fails**

Run: `pytest tests/test_imports.py -q`
Expected: 11 failures (the two `DELETED_TOP_LEVEL` cases and nine `DELETED_SUBMODULE` cases), with `AssertionError` naming each still-exported symbol. `test_surviving_neighbours_still_export` passes already.

- [ ] **Step 4: Delete `default_version` and `describe_compset` from `utils/naming.py`**

Remove the two `__all__` entries — line 89 `    "describe_compset",` and line 97 `    "default_version",` — and both definitions:

```python
def default_version() -> str:
    """``v`` + the package version with separators dropped: 0.2.6 -> ``v026``."""
    try:
        from .. import __version__ as v
    except Exception:  # pragma: no cover - package metadata unavailable
        return "v000"
    parts = re.findall(r"\d+", str(v))[:3]
    return "v" + "".join(parts) if parts else "v000"
```

```python
def describe_compset(code: str) -> str:
    """One-line human-readable expansion, for logs and figure captions."""
    d = decode_compset(code)
    return (f"{code}: {d['curve']}, {d['training_set']}, "
            f"{d['estimator']}, {d['structure']}")
```

Keep `decode_compset` — `describe_compset` was its only caller here, but `decode_compset` is used by `CaseName.__post_init__` and `CaseName.describe`. Keep `import re`; `_CASE_RE` still uses it.

- [ ] **Step 5: Delete `generalized_logistic` from `models/logistics.py` and its two re-exports**

Remove lines 78–102 in full:

```python
def generalized_logistic(
    x: np.ndarray, 
    t0: float = None, 
    x0: float = None, 
    a: float = None, 
    b: float = None, 
    k: float = None, 
    v: float = None, 
    Q: float = None
):
    """
    Generalized logistic function.

    Parameters
    ----------
    x : array-like
    t0, x0 : float
    a, b : float
        Upper/lower asymptotes.
    k, v, Q : float

    Returns
    -------
    y : np.ndarray
    """
    inflection = t0 if t0 is not None else x0
    if inflection is None or a is None or b is None or k is None or v is None or Q is None:
        raise ValueError("Missing required parameters: t0 (or x0), a, b, k, v, Q")
    x = np.asarray(x).squeeze()
    return b + ((a - b) / np.power(1 + Q * np.exp(-k * (x - inflection)), 1/v))
```

(Note it is the last live reference to `Q` in the Python model layer — dropping it finishes the 2026-03 `Q` removal on this side.)

Then delete `    generalized_logistic,` from the import block at `src/TEXAS/models/__init__.py:7`, `    "generalized_logistic",` from its `__all__` at line 28, `    generalized_logistic,` from `src/TEXAS/__init__.py:40`, and `    "generalized_logistic",` from `src/TEXAS/__init__.py:113`.

- [ ] **Step 6: Delete `compute_density_based_range` and its dead `scipy.stats` import**

In `src/TEXAS/plotting/range_utils.py`, remove lines 14–30:

```python
def compute_density_based_range(
    samples: Sequence[float],
    kde_bw: float = 0.3,
    density_threshold: float = 0.01
) -> Tuple[Optional[float], Optional[float]]:
    if len(samples) == 0:
        return None, None
    p1, p99 = np.percentile(samples, [1, 99])
    xs = np.linspace(p1, p99, 1000)
    kde = stats.gaussian_kde(samples, bw_method=kde_bw)
    dens = kde(xs)
    mask = dens > (density_threshold * dens.max())
    if not mask.any():
        return compute_sample_range(samples)
    lo, hi = xs[mask][[0, -1]]
    pad = 0.1 * (hi - lo)
    return lo - pad, hi + pad
```

and remove line 4, `import scipy.stats as stats`.

Then delete `    compute_density_based_range,` from `src/TEXAS/plotting/__init__.py:5`, `    "compute_density_based_range",` from its `__all__` at line 23, `    compute_density_based_range,` from `src/TEXAS/__init__.py:81`, and `    "compute_density_based_range",` from `src/TEXAS/__init__.py:150`. **Leave the `load_or_build_halo_cache` import and `__all__` entry in `plotting/__init__.py` alone — plan 02 owns them.**

- [ ] **Step 7: Delete `get_repo_root` and both re-exports**

In `src/TEXAS/utils/paths.py`, remove lines 111–127:

```python
def get_repo_root(target_dir_name: str = "TEXAS") -> Path | None:
    cwd = Path.cwd()
    try:
        top = subprocess.check_output(
            ["git","rev-parse","--show-toplevel"], cwd=str(cwd)
        ).decode().strip()
        return Path(top)
    except Exception:
        pass
    for parent in [cwd, *cwd.parents]:
        if parent.name == target_dir_name:
            return parent
        cand = parent/target_dir_name
        if cand.is_dir():
            return cand
    return None
```

Keep `import subprocess` — `get_project_root()`, immediately below, still uses it.

In `src/TEXAS/stan/__init__.py`, delete line 7 (`from ..utils     import get_repo_root`) and line 20 (`    "get_repo_root",`). In `src/TEXAS/utils/__init__.py`, delete line 1 (`from ..utils.paths import get_repo_root`) and line 6 (`    'get_repo_root',`).

- [ ] **Step 8: Delete `save_system_summary` and its dead `json` import**

In `src/TEXAS/utils/system_info.py`, remove lines 246–259:

```python
def save_system_summary(filepath=None):
    """Save system summary to JSON file"""
    from datetime import datetime

    summary = generate_system_summary()

    if filepath is None:
        filepath = f"system_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(filepath, 'w', encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"✅ System configuration saved to: {filepath}")
    return filepath
```

and remove line 18, `import json`. Keep `get_system_summary` and `print_system_summary`, which are used.

In `src/TEXAS/utils/__init__.py`, change line 2 to drop the third name and delete line 9. The file should end as:

```python
from .system_info import get_system_summary, print_system_summary
from .download import download_all, download_posteriors, download_training_data, POSTERIOR_REGISTRY

__all__ = [
    'get_system_summary',
    'print_system_summary',
    'download_all',
    'download_posteriors',
    'download_training_data',
    'POSTERIOR_REGISTRY',
]
```

- [ ] **Step 9: Run the regression test to verify it passes**

Run: `pytest tests/test_imports.py -q`
Expected: PASS, all cases green.

- [ ] **Step 10: Run the full suite and the linter**

Run: `pytest -q` — expected 351 passed + the 12 new cases from Step 2 = **363 passed, 11 skipped**.
Run: `ruff check .` — expected the one pre-existing `F401` in `tests/test_stan_model_archive.py:18` (`pathlib.Path` imported but unused) and **nothing new**. That pre-existing error is fixed in Task 6, which edits that file anyway; do not fix it here.

- [ ] **Step 11: Regenerate the call map**

Run: `python docs/_scripts/build_callmap.py`
Expected: `docs/_static/callmap.html` rewritten; the six deleted nodes no longer appear. Verify with `grep -c "default_version" docs/_static/callmap.html` → `0`.

- [ ] **Step 12: Create `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to `texas-psm` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Versioning is semantic, with the pre-1.0 convention this project uses: `0.x`
means "manuscript under review", so the public API may change in a minor
release. Every such change is listed below. `1.0.0` is reserved for paper
acceptance.

## [Unreleased]

### Removed

- `TEXAS.generalized_logistic` — the free-upper-asymptote generalized logistic
  (`b + (a - b) / (1 + Q·exp(-k(x - t0)))^(1/v)`). Every shipped Stan model is a
  `_fixed_` upper-asymptote curve and the free-asymptote models live in
  `archive/`, so nothing in the package, the notebooks, the scripts or the docs
  called it. It was also the last Python function to take `Q`, which was dropped
  from all Stan models in 2026-03. Use `generalized_logistic_fixed_upper`.
- `TEXAS.compute_density_based_range` (and `TEXAS.plotting.range_utils.compute_density_based_range`)
  — KDE-based axis range for prior/posterior plots. No caller; the plots use
  `compute_sample_range` and the two suffix/dataset variants.
- `TEXAS.utils.naming.default_version()` — built a `v026`-style token from the
  pip version. The version position was dropped from written case ids on
  2026-08-12 (it still *parses*, so old ids resolve), which left this with no
  caller.
- `TEXAS.utils.naming.describe_compset()` — one-line compset expansion.
  `CaseName.describe()` covers the need and is the one that is used.
- `TEXAS.utils.paths.get_repo_root()`, and its re-exports from `TEXAS.stan` and
  `TEXAS.utils`. Superseded by `get_project_root()`, which has the pip-install
  fallback to `~/.texas/`.
- `TEXAS.utils.system_info.save_system_summary()` — wrote the system summary to
  a timestamped JSON file. `get_system_summary()` and `print_system_summary()`
  are kept; both are used.
```

- [ ] **Step 13: Commit**

```bash
git add CHANGELOG.md src/TEXAS tests/test_imports.py docs/_static/callmap.html
git commit -m "refactor: delete six unreferenced public helpers (spec 9.6)

None had a caller in src/, tests/, scripts/, streamlit_app/, notebooks/ or
docs/ -- only their own re-export lines. Adds CHANGELOG.md, which the project
did not have, because pre-1.0 API removal needs a record.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 2: Write the four missing public docstrings

**Files:**
- Modify: `src/TEXAS/plotting/range_utils.py` (`compute_sample_range`, `compute_suffix_specific_range`, `compute_dataset_specific_range`)
- Modify: `src/TEXAS/utils/naming.py` (`CaseName.describe`, plus one-liners on the `temptype_full` and `proxy_full` properties)
- Test: `tests/test_range_utils.py` (create)

**Interfaces:**
- Consumes: Task 1's deletion of `compute_density_based_range` — `range_utils.py` now holds exactly three public functions.
- Produces: nothing new callable. Task 5's ruff `D102`/`D103` selection depends on these six docstrings existing; after this task `ruff check --select D101,D102,D103,D106 src/TEXAS` reports **zero** violations. (Before Task 1 it reported eight: four in `range_utils.py`, three in `naming.py`, one for `paths.get_repo_root`.)

**Standard for every docstring in Tasks 2–4:** Google style — a one-line imperative summary, then `Args:`, `Returns:`, and `Raises:` where the function actually raises. One short example only when the call shape is not obvious from the signature. Target 5–25 lines. Pytest does **not** collect doctests here (no `--doctest-modules`, no `[tool.pytest.ini_options]` in `pyproject.toml`, no `conftest.py`), so `>>>` blocks are prose, not executed — but write them so they would run if it ever changes.

- [ ] **Step 1: Write the failing test**

Create `tests/test_range_utils.py`:

```python
"""Axis-range helpers for the prior/posterior plots.

These three are exported from the package top level, so they need docstrings
and they need to behave predictably on the two inputs that actually occur:
an empty sample, and a pooled set assembled by ``plotting.prior_plot``.
"""
import numpy as np
import pytest

from TEXAS.plotting.range_utils import (
    compute_dataset_specific_range,
    compute_sample_range,
    compute_suffix_specific_range,
)

ALL_FUNCS = [compute_sample_range, compute_suffix_specific_range,
             compute_dataset_specific_range]


@pytest.mark.parametrize("fn", ALL_FUNCS, ids=lambda f: f.__name__)
def test_has_a_real_docstring(fn):
    """Public API standard: >= 3 lines, and it says what it returns."""
    doc = (fn.__doc__ or "").strip()
    assert len(doc.splitlines()) >= 3, f"{fn.__name__} has no usable docstring"
    assert "Returns:" in doc, f"{fn.__name__} does not document its return value"


def test_sample_range_pads_outward():
    """The 1-99 span is widened by 20% on each side, so tails are not clipped."""
    samples = np.linspace(0.0, 100.0, 1001)
    lo, hi = compute_sample_range(samples)
    p1, p99 = np.percentile(samples, [1, 99])
    assert lo < p1 and hi > p99
    assert lo == pytest.approx(p1 - 0.2 * (p99 - p1))
    assert hi == pytest.approx(p99 + 0.2 * (p99 - p1))


def test_sample_range_of_empty_is_none():
    assert compute_sample_range([]) == (None, None)


def _entry(samples, ds_idx, label):
    """One row of the (samples, dataset_index, label, model, use_g23, use_no3) tuple."""
    return (np.asarray(samples), ds_idx, label, "gen_logi_fixed", 0, 0)


def test_suffix_range_pools_only_matching_labels():
    """A suffix that appears in one label must not pull in the other dataset."""
    entries = [_entry(np.zeros(100), 0, "t0_crtp"),
               _entry(np.full(100, 50.0), 1, "t0_culmeso")]
    lo, hi = compute_suffix_specific_range(entries, "crtp")
    assert hi < 25.0, "the culmeso samples leaked into the crtp range"


def test_suffix_range_with_no_match_is_none():
    entries = [_entry(np.zeros(10), 0, "t0_crtp")]
    assert compute_suffix_specific_range(entries, "meso") == (None, None)


def test_dataset_range_pools_by_index_not_label():
    """Same labels, different dataset index -- the index is what selects."""
    entries = [_entry(np.zeros(100), 0, "t0_crtp"),
               _entry(np.full(100, 50.0), 1, "t0_crtp")]
    lo, hi = compute_dataset_specific_range(entries, 1)
    assert lo > 25.0, "dataset 0 leaked into dataset 1's range"


def test_dataset_range_with_no_match_is_none():
    entries = [_entry(np.zeros(10), 0, "t0_crtp")]
    assert compute_dataset_specific_range(entries, 7) == (None, None)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_range_utils.py -q`
Expected: the three `test_has_a_real_docstring` cases FAIL with `AssertionError: <name> has no usable docstring` (`fn.__doc__` is `None`). The six behaviour tests already PASS — they document behaviour the functions already have, and they are what makes the docstrings you are about to write checkable.

- [ ] **Step 3: Write the three `range_utils.py` docstrings**

```python
def compute_sample_range(samples: Sequence[float]) -> Tuple[Optional[float], Optional[float]]:
    """Compute a padded plotting range covering the central 98% of a sample.

    Args:
        samples: Posterior draws, or any 1-D numeric sequence.

    Returns:
        ``(lo, hi)``: the 1st and 99th percentiles, each pushed outward by 20%
        of the span between them, so a density curve is not clipped at the axis
        edge. ``(None, None)`` when *samples* is empty.
    """
```

```python
def compute_suffix_specific_range(
    all_samples: List[Tuple[np.ndarray,int,str,str,int,int]],
    target_suffix: str
) -> Tuple[Optional[float], Optional[float]]:
    """Compute one padded range shared by every sample whose label carries a suffix.

    Puts all parameters estimated from one training set (``crtp``,
    ``culmesocore``, ``culmeso``, ``meso``, ``cul``) on a common axis, so the
    panels of a prior/posterior grid stay comparable across parameters.

    Args:
        all_samples: Tuples of ``(samples, dataset_index, label, model_name,
            use_gdgt23ratio, use_no3)``, as assembled by ``plotting.prior_plot``.
        target_suffix: Suffix to match; tested as ``target_suffix in label``,
            so ``"crtp"`` matches ``"t0_crtp"``.

    Returns:
        ``(lo, hi)``: the pooled 5th and 95th percentiles, padded by 5% of their
        span. ``(None, None)`` when nothing matches or the match is empty.
    """
```

```python
def compute_dataset_specific_range(
    all_samples: List[Tuple[np.ndarray,int,str,str,int,int]],
    target_dataset_idx: int
) -> Tuple[Optional[float], Optional[float]]:
    """Compute one padded range shared by every sample from one dataset.

    The dataset counterpart of :func:`compute_suffix_specific_range`: it pools
    by position in the caller's dataset list rather than by parameter suffix,
    which is what puts a whole column of a comparison grid on one axis.

    Args:
        all_samples: Tuples of ``(samples, dataset_index, label, model_name,
            use_gdgt23ratio, use_no3)``, as assembled by ``plotting.prior_plot``.
        target_dataset_idx: Index matched against each tuple's ``dataset_index``.

    Returns:
        ``(lo, hi)``: the pooled 1st and 99th percentiles, padded by 5% of their
        span. ``(None, None)`` when nothing matches or the match is empty.
    """
```

- [ ] **Step 4: Write `CaseName.describe` and the two property docstrings in `naming.py`**

Replace the bare `def describe(self) -> str:` at line 490 with:

```python
    def describe(self) -> str:
        """Expand this case id into a human-readable block.

        Decodes each of the four compset characters and both predictor tokens
        into words, so a case id in a log line, a figure caption or a Zenodo
        file listing can be read without the codebook.

        Returns:
            A multi-line string: the canonical id on the first line, then one
            indented ``key : value`` line per axis (curve, training set,
            estimator, structure, target, proxy, predictors).

        Raises:
            ValueError: if the compset or predictor token cannot be decoded.

        Example:
            ``CaseName("GHEB", "sst", "sri03", "G23-N1p0").describe()`` starts
            ``tx.GHEB.sst.sri03.G23-N1p0`` and then lists ``curve``,
            ``training set``, ``estimator``, ``structure``, ``target``,
            ``proxy`` and ``predictors``.
        """
```

Add one-line docstrings to the two properties above it, which ruff `D102` also flags:

```python
    @property
    def temptype_full(self) -> str:
        """The temperature target spelled out: ``sst`` -> ``SST``, ``thm`` -> ``thermoT``."""
        return TEMPTYPE_DECODE.get(self.temptype, self.temptype)

    @property
    def proxy_full(self) -> str:
        """The proxy spelled out: ``sri03`` -> ``scaledRI_cren3``."""
        return PROXY_DECODE.get(self.proxy, self.proxy)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_range_utils.py tests/test_naming.py -q`
Expected: PASS. `test_naming.py` is included because `CaseName.describe` is edited; its existing cases must stay green.

- [ ] **Step 6: Verify the ruff missing-docstring count is now zero**

Run: `ruff check --select D101,D102,D103,D106 --ignore D105,D107 src/TEXAS`
Expected: `All checks passed!`. If `paths.py:111` still appears, Task 1 Step 7 was not applied.

- [ ] **Step 7: Run the full suite**

Run: `pytest -q`
Expected: **372 passed, 11 skipped** (363 from Task 1 + 9 new in `tests/test_range_utils.py`).

- [ ] **Step 8: Commit**

```bash
git add src/TEXAS/plotting/range_utils.py src/TEXAS/utils/naming.py tests/test_range_utils.py
git commit -m "docs: docstrings for the four undocumented public functions

compute_sample_range, compute_suffix_specific_range,
compute_dataset_specific_range and CaseName.describe had none; the two
CaseName properties beside describe() get one-liners so the ruff D102
selection in the next task starts clean.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 3: Expand the twelve one- and two-line docstrings

**Files:**
- Modify: `src/TEXAS/diagnostics.py` (`summarize_sampler_diagnostics` line 6, `create_summary_table` line 72)
- Modify: `src/TEXAS/ensemble/detection.py` (`detect_model_and_params` line 50)
- Modify: `src/TEXAS/ensemble/generator.py` (`generate_ensemble` line 28)
- Modify: `src/TEXAS/models/calibration.py` (`CalibrationRegistry` line 240)
- Modify: `src/TEXAS/stan/sampler.py` (`StanSampler` line 71, `auto_detect_predictors` line 402)
- Modify: `src/TEXAS/utils/naming.py` (`legacy_invT_name` line 855)
- Modify: `src/TEXAS/utils/system_info.py` (`get_container_info` line 75, `print_summary` line 160, `get_system_info` line 314)
- Modify: `src/TEXAS/data/builder.py` (`InvTConfig` line 39)
- Test: `tests/test_public_api_docs.py` is written in Task 5; this task is verified by the inline check in Step 2 below.

**Interfaces:**
- Consumes: nothing.
- Produces: every name in `TEXAS.__all__` that is a function or class now has a docstring of ≥ 3 lines, which is the precondition for Task 5's guard. No signature changes.

**Why twelve and not ten.** Spec §9.6 lists ten. Two more are required by the guard Task 5 installs, because they are in `TEXAS.__all__` with a one-line docstring: `data.builder.InvTConfig` and `diagnostics.create_summary_table`. I measured this with `inspect.getdoc` over `TEXAS.__all__` — the functions and classes under 3 lines are exactly `StanSampler` (1), `InvTConfig` (1), `generate_ensemble` (2), `detect_model_and_params` (2), `summarize_sampler_diagnostics` (2) and `create_summary_table` (1). The other six on the spec's list (`CalibrationRegistry`, `auto_detect_predictors`, `legacy_invT_name`, `get_container_info`, `print_summary`, `get_system_info`) are not top-level exports, so the guard does not see them; they are here because the spec asks for them.

- [ ] **Step 1: Write the measurement script and run it to see the failures**

Create `/tmp/docs_check.py` (scratch, not committed):

```python
"""Every function/class in TEXAS.__all__ needs a docstring of >= 3 lines."""
import inspect
import TEXAS

thin = []
for name in TEXAS.__all__:
    obj = getattr(TEXAS, name)
    if not (inspect.isfunction(obj) or inspect.isclass(obj)):
        continue
    doc = inspect.getdoc(obj) or ""
    n = len(doc.strip().splitlines())
    if n < 3:
        thin.append((name, n))
print("THIN:", thin)
```

Run: `python /tmp/docs_check.py`
Expected: `THIN: [('StanSampler', 1), ('InvTConfig', 1), ('generate_ensemble', 2), ('detect_model_and_params', 2), ('summarize_sampler_diagnostics', 2), ('create_summary_table', 1)]`

- [ ] **Step 2: Rewrite `diagnostics.py`'s two docstrings**

`summarize_sampler_diagnostics` — replace

```python
    """
    Extract ``divergent__``, ``treedepth__``, E-BFMI, R_hat, and ESS_bulk
    from a CmdStanPy fit and return them as stan_diag_* attrs.
    """
```

with

```python
    """Summarise a CmdStanPy fit's convergence diagnostics as ``stan_diag_*`` attrs.

    Reads divergent transitions, max-treedepth saturation, E-BFMI, R-hat and
    bulk ESS, and grades each against a fixed threshold, so a run can be
    accepted or rejected without re-opening the raw fit. Attached to every
    posterior by ``StanSampler.sample`` and ``get_invT_posterior``.

    Args:
        fit: A ``CmdStanMCMC`` object, as returned by ``CmdStanModel.sample``.

    Returns:
        A flat dict of ``stan_diag_*`` entries: the counts and percentages
        (``n_divergent``, ``pct_divergent``, ``n_max_treedepth``,
        ``pct_max_treedepth``, ``min_ebfmi``, ``max_rhat``, ``n_high_rhat``,
        ``min_ess_bulk``), a ``*_status`` of ``"PASS"``, ``"FAIL"`` or
        ``"UNKNOWN"`` beside each, and ``stan_diag_overall_status``. The
        thresholds are: divergences < 1%, max-treedepth < 5%, R-hat < 1.01,
        bulk ESS > 100. All values are plain Python scalars, so the dict can be
        written straight into NetCDF attrs.
    """
```

`create_summary_table` — replace

```python
    """
    Build a DataFrame summarizing the stan_diag_* attrs from each xarray.Dataset.
    """
```

with

```python
    """Tabulate the ``stan_diag_*`` attrs of several posteriors, one row each.

    Args:
        datasets: Posteriors carrying ``stan_diag_*`` attrs, as written by
            :func:`summarize_sampler_diagnostics`.

    Returns:
        A DataFrame with a ``model`` column (each dataset's ``filename`` attr,
        or ``"unknown"``) plus one column per diagnostic, with the
        ``stan_diag_`` prefix stripped. A dataset missing a diagnostic gets
        ``NaN`` in that column rather than being dropped.
    """
```

- [ ] **Step 3: Rewrite `ensemble/detection.py::detect_model_and_params`**

Replace

```python
    """
    Auto-detect which logistic model and parameters to use.
    Uses a shared suffix priority via choose_suffix().
    """
```

with

```python
    """Infer the curve, parameter names and predictor flags from a forward posterior.

    Structure is read from the posterior's ``data_vars`` and attrs, never from
    ``stan_model_name``, so a posterior that was renamed or downloaded from
    Zenodo still dispatches correctly. The presence of a ``v`` parameter selects
    the generalized curve over the plain logistic; ``gamma_G23*`` /
    ``gamma_NO3*`` select the T0-shift parameterization over the additive one.

    Args:
        posterior_ds: A forward calibration posterior.
        suffix: Force a parameter suffix (e.g. ``"crtp"``). ``None`` selects by
            the priority order crtp > culmesocore > culmeso > meso > cul.

    Returns:
        A dict with ``model_function`` (the callable to evaluate),
        ``param_names`` (unsuffixed names, in the order the callable wants
        them), ``suffix``, ``is_multivariate``, ``use_gdgt23ratio``,
        ``use_no3`` and ``no3_cutoff``.

    Raises:
        ValueError: if gamma coefficients are present without a ``v``
            parameter. No shipped model produces that combination, and fitting
            the additive form to gamma coefficients would be wrong by a whole
            parameterization while still looking plausible.
    """
```

- [ ] **Step 4: Rewrite `ensemble/generator.py::generate_ensemble`**

Replace

```python
    """
    Generate an ensemble of curves from a posterior dataset using any model function.
    (Exact port of your old stan_utils.py version.)
    """
```

with

```python
    """Evaluate a calibration curve at *x_vals* for *n_draws* posterior samples.

    Each draw takes every parameter from one posterior index, so parameter
    correlations are preserved rather than being averaged away. Prefer
    :func:`generate_ensemble_auto`, which infers *model_function*,
    *param_names* and *suffix* from the posterior instead of asking for them.

    Args:
        post_ds: Forward calibration posterior.
        model_function: Curve to evaluate, called as
            ``model_function(x, **params)``.
        x_vals: Temperatures (degC) at which to evaluate the curve.
        param_names: Unsuffixed parameter names, e.g. ``["t0", "b", "k", "v"]``.
        suffix: Parameter suffix, e.g. ``"crtp"``. Required -- nothing is
            inferred here.
        n_draws: Draws to sample; clipped to what the posterior holds.
        seed: Seed for draw selection, for a reproducible ensemble.
        percentiles: Percentiles to return, on a 0-100 scale.
        return_full_ensemble: Also return the draw matrix and run metadata.
        gdgt23ratio: GDGT-2/3 values, applied when the posterior uses them.
        no3: Nitrate values (umol/L), applied when the posterior uses them.
        no3_cutoff: Override the cutoff carried in the posterior attrs.
        is_multivariate: Override the multivariate decision from the detector.
        use_gdgt23ratio_flag: Override the posterior's ``use_gdgt23ratio`` attr.
        use_no3_flag: Override the posterior's ``use_no3`` attr.

    Returns:
        A dict with ``"x_vals"`` and one ``f"p{q:g}"`` key per requested
        percentile (5 -> ``"p5"``, 2.5 -> ``"p2.5"``), plus ``"ensemble"``
        (shape ``(n_draws, len(x_vals))``) and ``"metadata"`` when
        *return_full_ensemble* is True.

    Raises:
        ValueError: if *suffix* is None, if a required parameter is missing from
            the posterior, or if two percentiles collapse onto one key.
        RuntimeError: if *model_function* raises on any draw.
    """
```

- [ ] **Step 5: Rewrite `models/calibration.py::CalibrationRegistry`**

Replace `"""Registry of available TEX86-SST calibrations."""` with

```python
    """Named library of the published classical TEX86-SST calibrations.

    Holds the non-Bayesian regressions -- the linear, inverse, log10 and ln
    forms from Schouten, Kim, Liu, O'Brien and Low -- as
    :class:`TEX86Calibration` objects, so a comparison figure can name a
    calibration instead of repeating its slope and intercept.

    TEXAS's own calibration is not in here: it is a posterior, not a pair of
    coefficients. Use :func:`TEXAS.predict.predict_T_from_proxyObs` for that.

    Class methods:
        ``get(name)`` returns one calibration; ``list_calibrations()`` lists
        the registered names; ``add_calibration(name, slope, intercept, kind)``
        registers another for the current session.
    """
```

- [ ] **Step 6: Rewrite `stan/sampler.py`'s two docstrings**

`StanSampler` — replace `"""A simple wrapper for running the Stan sampler."""` with

```python
    """Run a compiled Stan model and return its draws as an ``xr.Dataset``.

    Wraps ``CmdStanModel.sample`` with the parts every TEXAS run needs: run
    metadata and prior strings attached to the result, convergence diagnostics
    summarised into ``stan_diag_*`` attrs, and one automatic
    recompile-and-retry when a cached binary turns out to be from another
    environment (CmdStan exit code 127, typically a TBB mismatch).

    Args:
        compiler: The :class:`~TEXAS.stan.compiler.StanCompiler` used to
            resolve model names to files and to build them.
    """
```

`auto_detect_predictors` — replace `"""Smart predictor detection with data validation (suffix-prioritized)."""` with

```python
    """Fill in the ``use_*`` flags and predictor arrays a Stan model expects.

    Picks the observation-count key by the suffix priority order crtp >
    culmesocore > meso > cul, then sets ``use_gdgt23ratio`` and ``use_no3``
    from whether a non-empty, not-all-NaN, not-all-zero array is present for
    each. Flags the caller set by hand are respected; the arrays are still
    coerced to the chosen group's length either way, so a model that declares
    a predictor vector always receives one.

    Args:
        data: A Stan data dict, normally from ``build_fwd_data()``.

    Returns:
        A copy of *data* with ``use_gdgt23ratio`` and ``use_no3`` set as
        integers, any missing ``gdgt23ratio_<suffix>`` / ``no3_<suffix>``
        vector filled with zeros of the right length, and ``no3_cutoff``
        defaulted to 1.0 if absent. The input dict is not mutated.
    """
```

> Note for the implementer: this docstring deliberately does **not** mention the legacy `scaledRI_* -> proxyObs_*` key translation. Task 7 removes that block. If you are executing tasks out of order and the block is still present, write the docstring as given anyway — Task 7 will not need to revisit it.

- [ ] **Step 7: Rewrite `utils/naming.py::legacy_invT_name`**

Replace `"""The historical invT name, matching ``io._generate_filename_base``."""` with

```python
    """Rebuild the pre-case-id inverse filename, byte-for-byte.

    Matches what ``io._generate_filename_base`` writes, so ``load_posterior``
    can still find reconstructions saved before the CESM-style case layout
    arrived (2026-08-09). Nothing new is named this way.

    Args:
        site: Site label; slugified into the name.
        stan_model_name: Inverse model name. ``_marginal`` is stripped out of
            the name, and its presence chooses the trailing ``direct`` vs
            ``ensemble`` token.
        temptype: Temperature target, e.g. ``"SST"`` or ``"thermoT"``.
        proxy_name: Proxy label. Omitted from the name when empty or
            ``"unknown"``, which is what the oldest files did.
        use_gdgt23ratio: Whether the calibration carried the G23 correction.
        use_no3: Whether it carried the NO3 correction.
        no3_cutoff: The cutoff in umol/L. Required when *use_no3* is True.
        tags: Extra tag(s), joined with ``+`` and inserted before the kind
            token.

    Returns:
        The legacy stem, without the ``.nc`` extension.

    Raises:
        ValueError: if *use_no3* is True and *no3_cutoff* is None -- writing a
            name with no cutoff would misrecord which run it was.
    """
```

- [ ] **Step 8: Rewrite the three `utils/system_info.py` docstrings**

`get_container_info` — replace `"""Check if running in container"""` with

```python
    """Detect whether this process is running inside a container.

    Reads ``/proc/1/cgroup`` for Docker and LXC markers, then checks the
    ``CODESPACES`` and ``REMOTE_CONTAINERS`` environment variables. Never
    raises: an unreadable or absent cgroup file is reported as "not a
    container", because this only annotates a benchmark, it never gates one.

    Returns:
        ``{"in_container": bool, "container_type": str | None}``, where the
        type is one of ``"Docker"``, ``"LXC"``, ``"GitHub Codespaces"``,
        ``"VS Code Dev Container"`` or ``None``.
    """
```

`print_summary` — replace `"""Print formatted summary"""` with

```python
    """Print a system-configuration summary to stdout.

    The rendering half of :func:`get_system_summary`; call
    :func:`print_system_summary` to collect and print in one step.

    Args:
        summary: A dict as returned by ``generate_system_summary()``. It must
            carry the ``timestamp``, ``system``, ``cpu``, ``memory``, ``disk``,
            ``python``, ``container``, ``stan`` and ``packages`` keys.

    Returns:
        None. The report goes to stdout.
    """
```

`get_system_info` — replace `"""Collect system information dict for embedding in posterior metadata."""` with

```python
    """Collect the machine facts stamped onto every posterior's attrs.

    Deliberately cheap and non-raising: a psutil call that fails on a given
    platform yields ``None`` for that field rather than aborting a sampling
    run that may already be hours in.

    Returns:
        A dict of plain scalars -- ``system``, ``platform``, ``architecture``,
        ``processor``, ``hostname``, ``cpu_count_logical``,
        ``cpu_count_physical``, ``cpu_freq_current_mhz``, ``cpu_freq_max_mhz``,
        ``total_memory_gb``, ``available_memory_gb``, ``python_version``,
        ``python_implementation`` and ``run_timestamp`` (ISO 8601). Any field
        that could not be read is ``None``.
    """
```

- [ ] **Step 9: Rewrite `data/builder.py::InvTConfig`**

Replace `"""Configuration for the inverse-T Stan data builder."""` with

```python
    """Knobs for the forward-to-inverse bridge in ``build_invT_inputData``.

    Controls how many parameter sets M are drawn from the forward posterior and
    marginalised over. The marginal-likelihood error falls as 1/sqrt(M) while
    cost rises linearly with it, so M is the main accuracy-versus-runtime dial
    of a reconstruction.

    Attributes:
        mode: Historical artifact; only ``"ensemble"`` is supported.
        n_draws: M, the number of forward draws. ``None`` auto-selects
            ``min(available_draws, 300)``. 100 is quick, 300 the default, 500
            for publication.
        seed: Seed for selecting those M draws, so a reconstruction is
            reproducible.
        no3_cutoff: Fallback NO3 cutoff (umol/L), used only when the forward
            posterior carries no ``no3_cutoff`` attr of its own -- the
            posterior always wins.
        suffix: Force a forward parameter suffix (e.g. ``"crtp"``) instead of
            taking the highest-priority one present.
    """
```

Leave the trailing `#` comments on the fields as they are; they document the same facts at the point of use.

- [ ] **Step 10: Re-run the measurement script**

Run: `python /tmp/docs_check.py`
Expected: `THIN: []`

- [ ] **Step 11: Verify no docstring exceeds the standard and the suite is green**

Run: `pytest -q`
Expected: **372 passed, 11 skipped** — unchanged from Task 2; this task adds no tests and changes no behaviour.
Run: `ruff check .` — expected only the pre-existing `tests/test_stan_model_archive.py:18` `F401`.

- [ ] **Step 12: Commit**

```bash
git add src/TEXAS
git commit -m "docs: expand twelve thin docstrings to the Google-style standard

The ten from spec 9.6, plus InvTConfig and create_summary_table, which are in
TEXAS.__all__ with a one-line docstring and so would fail the guard added in
the next task but one.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 4: Trim the five over-long docstrings, moving narrative into `docs/`

**Files:**
- Modify: `src/TEXAS/predict.py` (`predict_T_from_proxyObs` docstring, lines 174–352 — 177 lines)
- Modify: `src/TEXAS/models/multivariate.py` (`inverse_generalized_logistic_fixed_upper_multivariate` lines 211–276 — 66; `find_optimal_no3_threshold` lines 337–411 — 74; `find_optimal_no3_threshold_nointercept` lines 507–575 — 69)
- Modify: `src/TEXAS/stan/sampler.py` (`get_posterior` docstring, lines 212–279 — 67)
- Modify: `docs/PSM.md` (append two sections)
- Modify: `docs/marginalization_explainer.md` (append one section)
- Test: `tests/test_public_api_docs.py` is Task 5; verified here by the inline length check in Step 1.

**Interfaces:**
- Consumes: nothing.
- Produces: every public docstring is ≤ 40 lines. Task 5's guard checks the lower bound (≥ 3 lines) only; the upper bound is checked once, here, by the Step 1 script. `docs/PSM.md` gains `## 8. Reconstructing temperature from proxy observations` and `## 9. Choosing the NO₃ cutoff`; `docs/marginalization_explainer.md` gains `## 7. The deterministic point inverse, and when not to use it`. Later prose must link to those anchors, not restate them.

**Ordering note.** The trimmed `predict_T_from_proxyObs` docstring below still documents `constraint_type` and `min_temp`, in two short entries. **Task 6 deletes those two entries** when it removes the parameters. Written this way so Task 4 and Task 6 can be reviewed independently and neither has to guess at the other's text.

- [ ] **Step 1: Write the length check and run it to see the failures**

Create `/tmp/doclen_check.py` (scratch, not committed):

```python
"""No public docstring in TEXAS may exceed 40 lines."""
import inspect

from TEXAS.models.multivariate import (
    find_optimal_no3_threshold,
    find_optimal_no3_threshold_nointercept,
    inverse_generalized_logistic_fixed_upper_multivariate,
)
from TEXAS.predict import predict_T_from_proxyObs
from TEXAS.stan.sampler import get_posterior

for fn in (predict_T_from_proxyObs, get_posterior,
           find_optimal_no3_threshold, find_optimal_no3_threshold_nointercept,
           inverse_generalized_logistic_fixed_upper_multivariate):
    n = len((inspect.getdoc(fn) or "").strip().splitlines())
    print(f"{n:4d}  {'OK ' if n <= 40 else 'LONG'}  {fn.__name__}")
```

Run: `python /tmp/doclen_check.py`
Expected, before the edits (getdoc strips the leading blank line, so these run a little under the raw source counts):

```
 177  LONG  predict_T_from_proxyObs
  67  LONG  get_posterior
  74  LONG  find_optimal_no3_threshold
  69  LONG  find_optimal_no3_threshold_nointercept
  66  LONG  inverse_generalized_logistic_fixed_upper_multivariate
```

- [ ] **Step 2: Append the two new sections to `docs/PSM.md`**

The file currently ends with `## 7. Key Equations Summary`. Append:

```markdown
## 8. Reconstructing temperature from proxy observations

`TEXAS.predict_T_from_proxyObs` is the inverse half of the API. Three things
about how it is called are worth stating once here rather than in its
docstring.

**The default calibration.** Omitting `fwd_posterior` selects the full
multivariate T₀-shift calibration for the requested target — `tx.GHEB.sst.sri03.G23-N1p0`
for SST, `tx.GHEB.thm.sri03.G23-N1p0` for thermoT — both of which ship inside
the wheel, so a reconstruction needs no download. That is the default because
the non-thermal effects are present in the core-top data whether or not a user
models them: a temperature-only calibration does not remove them, it absorbs
them into the thermal parameters.

**Which NO₃ value reaches Stan.** The resolution order is
`site_lat`/`site_lon` lookup → an explicit `no3=` → `predictors["no3"]` →
zeros. Passing `site_lat` and `site_lon` interpolates the WOA23-derived
`ocean_prop_ds` field at those coordinates (downloaded and cached from Zenodo
on first use if `no3_dataset` is not supplied). A scalar `no3` broadcasts to
every observation; a value above `no3_cutoff` — e.g. `no3=10.0` when the
cutoff is 1.0 — puts every observation outside the correction window, which is
how the correction is switched off.

Supplying *nothing* is not the same as switching it off. An absent predictor
is treated as zero, which asserts a ratio or concentration of zero and biases
the reconstruction; the function warns when it detects this. Use a
temperature-only calibration (`tx.GHPU.sst.sri03.p0`) if that is what you want.

**`temptype` is a label, not a modelling choice.** The reconstruction follows
whatever calibration it was given: the target is read from the posterior's own
attrs, and `temptype` only names the metadata and the output files. It matters
in exactly one case — when `fwd_posterior` is omitted, it chooses which default
calibration is used. A `temptype` that contradicts the calibration raises a
warning and is otherwise ignored.

**Per-observation flags.** `result["flags"]` is a DataFrame with one row per
observation, marking rows the reconstruction cannot support — above all, proxy
values outside the calibration curve's attainable range, which return a
converged, plausible-looking temperature that is really a readout of the prior.
The published calibration-domain ellipse is two-dimensional (TEX₈₆ × Scaled RI),
so the `outside_domain` check needs `tex86=` as well; without it that column is
`pd.NA` rather than passing. Computing the flags costs no extra sampling. Filter
with:

```python
result = predict_T_from_proxyObs(ri, prior_mu_t=25, prior_sigma_t=10)
keep = ~result["flags"]["any_flag"].to_numpy(dtype=bool)
sst = result["p50"][keep]
```

## 9. Choosing the NO₃ cutoff

The NO₃ correction applies only below a cutoff concentration: above it, sites
are nutrient-replete and the term is switched off. `find_optimal_no3_threshold`
and `find_optimal_no3_threshold_nointercept` search that cutoff against the
residuals of a temperature-only fit. They differ in the criterion, and the
choice is a modelling decision, not a tuning detail.

**`find_optimal_no3_threshold`** takes the cutoff that maximises the *negative*
correlation between log(NO₃) and the residuals.

- `score_method="spearmanr"` (default) uses the most negative Spearman ρ. It is
  rank-based, robust to outliers, and is what the prior publication used.
- `score_method="R_squared"` uses the highest no-intercept R² of
  `RI_res = β·log(NO₃)` with β < 0. It penalises poor fit rather than rank order
  alone, and corresponds to a model whose correction is zero at NO₃ = 1.

**`find_optimal_no3_threshold_nointercept`** instead maximises the no-intercept
R² of `RI_res = β·x`, matching the `_no3ratio` Stan formulation where the
correction is exactly zero *at the threshold*.

- `no3_mode="log10ratio"` (default) sets `x = log10(NO₃ / threshold)` — zero at
  the boundary.
- `no3_mode="log10"` sets `x = log10(NO₃)` — zero at NO₃ = 1 regardless of the
  threshold, which is the original Stan form. Use it to compare the
  no-intercept criterion against the Spearman one while holding the predictor
  fixed.

**Asymmetric weighting** (`weight_method`, R²-based criteria only; Spearman
takes no sample weights) exists because the two corrections have opposite
expected signs.

- `"uniform"` — ordinary least squares.
- `"positive_residuals"` — `wᵢ = max(resᵢ, ε)`. For the **NO₃** correction:
  nutrient-limited sites are expected to have positive RI residuals (observed
  RI above what temperature alone predicts).
- `"negative_residuals"` — `wᵢ = max(−resᵢ, ε)`. For the **G₂/₃** correction:
  deep-water, high-G₂/₃ sites are expected to have negative RI residuals.

In both weighted cases `ε = 0.001 · std(residuals)`, so off-direction points are
suppressed but never fully excluded — which keeps the fit stable when nearly all
residuals fall on one side.

`log_method` (`"log10"` or `"ln"`) sets the log base. `"log10"` matches the Stan
models; `"ln"` is there to test sensitivity to that choice.
```

- [ ] **Step 3: Append the new section to `docs/marginalization_explainer.md`**

The file currently ends with `## 6. Key Takeaway`. Append:

```markdown
## 7. The deterministic point inverse, and when not to use it

`TEXAS.inverse_generalized_logistic_fixed_upper_multivariate` inverts the
forward curve for a **single** parameter set. It is not a reconstruction.

The two non-thermal corrections are additive and independent of temperature, so
the inversion subtracts them off and then inverts the thermal curve
analytically:

```
y_thermal = y − β_G23·gdgt23ratio − β_NO3·log10(no3)   [only where 0 < no3 < no3_cutoff]
x         = t0 − ln(((1 − b) / (y_thermal − b))**v − 1) / k
```

`gdgt23ratio` and `no3` may each be a scalar (applied to every sample) or an
array broadcastable to `y`. They are additive predictors that must be supplied,
not quantities solved for: pass the same covariate values that applied to those
observations.

The thermal inverse is defined only for `b < y_thermal < 1`. Values outside that
range are physically unreachable for the given parameters and come back as
`np.nan`, with a single `RuntimeWarning` if any occur. That NaN is the honest
answer, and it is the first reason this function is not a reconstruction: the
Bayesian path returns a posterior in exactly that region, driven by the prior,
which is informative in a way a NaN is not.

The second reason is uncertainty. Feeding this function the posterior means of
`t0`, `k`, `b` and `v` gives one number per sample and no interval — and the
plug-in estimate is not the median of the marginal posterior, because the
inverse is non-linear. For an uncertainty-aware reconstruction that marginalises
over the full forward posterior, use `TEXAS.predict_T_from_proxyObs`, which is
the Stan path this page describes.

Use the point inverse for what it is good at: drawing a single calibration curve
on a figure, checking an algebraic identity against the forward function, or
sanity-checking one parameter set by hand.
```

- [ ] **Step 4: Trim `predict.py::predict_T_from_proxyObs` to 40 lines**

Replace the entire docstring (source lines 174–352) with:

```python
    """Reconstruct temperature from proxy observations, with full uncertainty.

    Runs the TEXAS inverse Stan model, marginalising over M draws from the
    forward calibration posterior so calibration uncertainty propagates into
    the reconstruction (manuscript Section 8). See
    :doc:`PSM` §8 for the default calibration, how the NO3 predictor is
    resolved, and what the quality flags mean.

    Args:
        proxyObs: Observed proxy values, shape (N,) -- scaledRI, TEX86, ...
        prior_mu_t: Prior mean temperature (degC). Scalar, or shape (N,) for a
            per-sample prior.
        prior_sigma_t: Prior temperature standard deviation (degC). Use a
            diffuse value (~10) when little is known.
        fwd_posterior: The forward calibration: a case id or legacy name (str,
            loaded from the cache) or a pre-loaded ``xr.Dataset`` (no file I/O,
            no download). Omit it to use the bundled default for *temptype*.
        proxy_name: Proxy label. Inherited from the calibration when omitted,
            and validated against it when given.
        temptype: ``"SST"`` or ``"thermoT"``. A label only, except that it
            picks the default calibration when *fwd_posterior* is omitted.
        site_name: Label for the metadata and the output filenames.
        predictors: Non-thermal predictor arrays, e.g.
            ``{"gdgt23ratio": ..., "no3": ...}``.
        no3: Nitrate (umol/L), scalar or shape (N,). Overrides *predictors*.
        gdgt23ratio: GDGT-2/3 ratio, scalar or shape (N,). Overrides *predictors*.
        site_lat: Latitude(s) for a WOA23 NO3 lookup. Needs *site_lon*.
        site_lon: Longitude(s) for the same lookup.
        no3_dataset: The WOA23-derived ``(lat, lon)`` field. Downloaded from
            Zenodo and cached if omitted.
        no3_dataset_var: Variable to read from it. Default ``"no3_sf2tc_avg"``.
        flags: Attach ``result["flags"]``, one row per observation. Default True.
        tex86: TEX86 for the same samples; only the ``outside_domain`` flag
            uses it.
        config: :class:`InvTConfig` controlling M, the seed and the suffix.
        chains: MCMC chains. Default 4.
        iter_warmup: Warmup iterations per chain. Default 500.
        iter_sampling: Sampling iterations per chain. Default 1000.
        seed: Random seed. Default 42.
        constraint_type: Temperature constraint. ``"unconstrained"`` (default)
            or ``"truncated_prior"``, which bounds P5 at *min_temp* without
            biasing P50.
        min_temp: Lower temperature bound (degC), e.g. -1.8. Required for
            ``"truncated_prior"``, and selects it when passed alone.
        threads_per_chain: Within-chain parallelism for ``reduce_sum`` models.
        save_results: Write the quantile ``.nc`` and the results ``.npz``.
        save_draws: Also write the raw draws as ``{base}_draws.nc``.
        filename_tag: Extra tag(s) for the output filenames.
        cache_dir: Where outputs are written. Defaults to the invT cache.
        fwd_cache_dir: Where a named *fwd_posterior* is read from. A different
            directory from *cache_dir*.

    Returns:
        A dict with ``"proxyObs"``, ``"proxy_name"``, ``"metadata"``, one
        ``"pN"`` array per posterior quantile (``"p5"``, ``"p50"``, ``"p95"``,
        ...), and ``"flags"`` when *flags* is True.
    """
```

That Args block is long because the signature is; the narrative is what moved.
Verify with the Step 1 script that `getdoc` reports ≤ 40 lines — if it does not,
shorten the per-argument lines further; do **not** drop an argument.

- [ ] **Step 5: Trim `stan/sampler.py::get_posterior` to 40 lines**

Replace lines 212–279 with:

```python
    """Run a forward calibration in Stan and return the posterior.

    Wraps :class:`StanSampler` with automatic predictor detection, CPU
    configuration and metadata attachment. The returned dataset can be passed
    straight to ``predict_proxy_from_T`` or saved with ``save_posterior``.

    Args:
        data: Stan data dict from ``build_fwd_data()``. The ``use_*`` predictor
            flags are auto-detected from the arrays present.
        stan_file: Model name without ``.stan``, e.g.
            ``"gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv"``.
        temptype: Temperature target, e.g. ``"SST"`` or ``"thermoT"``.
        proxy_name: Proxy label, e.g. ``"scaledRI_cren3"``. Required: it is
            written to the attrs and validated when the posterior is later used
            for a reconstruction.
        iter_warmup: Warmup iterations per chain. Default 1000 (CmdStan's).
        iter_sampling: Sampling iterations per chain. Default 1000.
        threads_per_chain: Threads per chain for ``reduce_sum`` models;
            auto-enabled for models whose filename contains ``reduce_sum``.
        chains: Independent chains. Default 4.
        parallel_chains: Chains run at once. Auto-detected from the CPU count.
        adapt_delta: Target acceptance rate. Default 0.8; raise toward 0.99 to
            trade leapfrog steps for fewer divergences.
        max_treedepth: HMC maximum tree depth. Default 10.
        **kwargs: Forwarded to ``CmdStanModel.sample``.

    Returns:
        ``(posterior, diagnostics)``: an ``xr.Dataset`` of draws with metadata
        attrs (model name, temptype, proxy_name, priors, ``stan_diag_*``), and
        the human-readable sampler diagnostic summary.

    Raises:
        ValueError: if active predictors are present but a univariate model was
            requested, or if an EIV model is requested without ``R2_thermal``.

    Example:
        >>> posterior, diag = get_posterior(
        ...     data, stan_file="gen_logi_fixed_hier_crtp_univ_priorApprox",
        ...     temptype="SST", proxy_name="scaledRI_cren3")
        >>> save_posterior(posterior)
    """
```

- [ ] **Step 6: Trim the three `models/multivariate.py` docstrings**

`inverse_generalized_logistic_fixed_upper_multivariate` — replace the whole
docstring with:

```python
    """Invert :func:`generalized_logistic_fixed_upper_multivariate` for one parameter set.

    Subtracts the two additive non-thermal corrections, then inverts the thermal
    curve analytically. This is a deterministic **point** inverse, not a
    reconstruction: see :doc:`marginalization_explainer` §7 for the algebra, the
    NaN convention and why :func:`TEXAS.predict.predict_T_from_proxyObs` is what
    you want for paleotemperature.

    Args:
        y: Proxy observations to invert. Scalar or array.
        t0: Curve location parameter. ``x0`` is accepted as a legacy alias.
        x0: Legacy alias for *t0*.
        b: Lower asymptote.
        k: Slope.
        v: Generalized-logistic shape parameter. Defaults to 1.0, matching the
            forward function.
        beta_G23: GDGT-2/3 coefficient. The correction applies only when both
            this and *gdgt23ratio* are given.
        gdgt23ratio: GDGT-2/3 ratio: scalar, or one value per sample.
        beta_NO3: Nitrate coefficient. The correction applies only when both
            this and *no3* are given, and only where ``0 < no3 < no3_cutoff``.
        no3: Nitrate concentration (umol/L): scalar, or one value per sample.
        no3_cutoff: Upper NO3 bound for the correction. Must match the value
            used in the forward call.

    Returns:
        Reconstructed temperature, ``np.nan`` wherever *y* is unreachable for
        these parameters. A 0-d array for scalar input, matching the forward
        function's convention.

    Raises:
        ValueError: if ``t0``/``x0``, ``b`` or ``k`` is missing, or a predictor
            array cannot be broadcast to the shape of *y*.
    """
```

`find_optimal_no3_threshold` — replace the whole docstring with:

```python
    """Find the NO3 cutoff that maximises the negative log(NO3)-residual correlation.

    Selects the ``no3_cutoff`` used by the multivariate models: points below it
    carry the NO3 correction, points above are nutrient-replete and excluded.
    The two scoring criteria and the three weighting schemes are different
    modelling choices, not tuning knobs -- see :doc:`PSM` §9.

    Args:
        no3_values: Nitrate concentrations (umol/L).
        residuals: Residuals of a temperature-only fit on the same observations.
        threshold_range: Cutoffs to test. Defaults to ``np.arange(0.5, 5, 0.01)``.
        min_points: Minimum valid points required to score a cutoff.
        log_method: ``"log10"`` (default, matches the Stan models) or ``"ln"``.
        score_method: ``"spearmanr"`` (default; most negative Spearman rho,
            rank-based) or ``"R_squared"`` (highest no-intercept R2 with
            beta < 0).
        weight_method: ``"uniform"`` (default), ``"positive_residuals"`` (for
            the NO3 correction) or ``"negative_residuals"`` (for the G23
            correction). Applies to ``"R_squared"`` only.

    Returns:
        ``(optimal_threshold, results)``: the best cutoff in umol/L, and a
        DataFrame with one row per tested cutoff. Its columns are ``threshold``,
        ``spearman_rho``, ``spearman_pval``, ``n_points`` for ``"spearmanr"``,
        or ``threshold``, ``beta``, ``r2_nointercept``, ``n_points`` for
        ``"R_squared"``.

    Raises:
        ImportError: if pandas or scipy is unavailable.
        ValueError: if *log_method* or *score_method* is unrecognised, or no
            valid threshold is found.
    """
```

`find_optimal_no3_threshold_nointercept` — replace the whole docstring with:

```python
    """Find the NO3 cutoff that maximises the no-intercept R2 of ``RI_res = beta * x``.

    Matches the ``_no3ratio`` Stan formulation, where the correction is exactly
    zero at the threshold boundary -- unlike :func:`find_optimal_no3_threshold`,
    which is Spearman-based and was used in the prior publication. The predictor
    forms and the weighting schemes are explained in :doc:`PSM` §9.

    Args:
        no3_values: Nitrate concentrations (umol/L).
        residuals: Residuals of a temperature-only fit on the same observations.
        threshold_range: Cutoffs to test. Defaults to ``np.arange(0.5, 5, 0.01)``.
        min_points: Minimum valid points required to fit the regression.
        no3_mode: ``"log10ratio"`` (default; ``x = log10(no3 / threshold)``,
            zero at the boundary) or ``"log10"`` (``x = log10(no3)``, zero at
            no3 = 1, the original Stan form).
        log_method: ``"log10"`` (default) or ``"ln"``.
        weight_method: ``"uniform"`` (default), ``"positive_residuals"`` or
            ``"negative_residuals"``.

    Returns:
        ``(optimal_threshold, results)``: the cutoff in umol/L giving the
        highest no-intercept R2 with beta < 0, and a DataFrame with one row per
        tested cutoff and columns ``threshold``, ``beta``, ``r2_nointercept``,
        ``n_points``.

    Raises:
        ImportError: if pandas or scipy is unavailable.
        ValueError: if a parameter is unrecognised or no valid threshold is
            found.
    """
```

- [ ] **Step 7: Re-run the length check**

Run: `python /tmp/doclen_check.py`
Expected: all five lines read `OK`, none above 40.

- [ ] **Step 8: Build the docs and check the new cross-references resolve**

Run: `jupyter-book build docs/`
Expected: build succeeds. Grep the log for `WARNING` mentioning `PSM` or
`marginalization_explainer` — there must be none. The three `:doc:` roles resolve
because both targets are already listed in `docs/_toc.yml`; no toc edit is needed.

- [ ] **Step 9: Run the full suite**

Run: `pytest -q`
Expected: **372 passed, 11 skipped** — unchanged. This task changes no behaviour.

- [ ] **Step 10: Commit**

```bash
git add src/TEXAS docs/PSM.md docs/marginalization_explainer.md
git commit -m "docs: trim five over-long docstrings, move the narrative into docs/

predict_T_from_proxyObs was 177 lines. The default-calibration rationale, the
NO3 resolution order and the quality-flag explanation move to PSM.md 8; the
NO3-cutoff criteria to PSM.md 9; the point-inverse-vs-Bayesian argument to
marginalization_explainer.md 7. Each docstring now links to its section.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 5: Install the guard — a public-API docs test and a ruff `D1` selection

**Files:**
- Create: `tests/test_public_api_smoke.py`
- Create: `tests/test_public_api_docs.py`
- Modify: `pyproject.toml` (`[tool.ruff.lint]`, lines 129–135)
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: Task 1's deletions (so `__all__` no longer lists `generalized_logistic` or `compute_density_based_range`), Task 2's and Task 3's docstrings (so every function/class in `__all__` clears the 3-line bar), Task 2's `tests/test_range_utils.py` (which is what makes the three range helpers *referenced*).
- Produces: `tests/test_public_api_docs.py` with three checks over `TEXAS.__all__` — resolves, referenced, documented. Every later task that adds to or removes from `__all__` must keep it green. `pyproject.toml` gains `D1` in `select`, so `ruff check .` from here on also fails on a new undocumented public function, class or method under `src/TEXAS`.

**Why the smoke file exists.** The "referenced by at least one test or notebook" check does not pass on today's tree. I measured it: after Task 1's deletions and Task 2's new `tests/test_range_utils.py`, **six** exported names have no reference in `tests/` or `notebooks/` — `simple_logistic_fixed_upper_multivariate`, `find_optimal_no3_threshold_nointercept`, `bootstrap_se`, `create_summary_table`, `POSTERIOR_REGISTRY` and `set_cache_dir`. The guard is only worth having if the reference check is real, so Step 1 gives those six an actual test rather than an allowlist. The guard then excludes *itself* from the scan, so a name cannot satisfy the check merely by being listed in the guard.

- [ ] **Step 1: Write the smoke tests for the six unreferenced exports**

Create `tests/test_public_api_smoke.py`:

```python
"""The exported names that nothing else exercised.

`tests/test_public_api_docs.py` asserts that every name in `TEXAS.__all__` is
referenced by at least one test or notebook. Six were not, which is a fair
description of "exported but never used". These are real smoke tests -- each
one calls the thing and checks something that would break if it regressed --
not placeholders to satisfy the scan.
"""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

import TEXAS


def test_simple_logistic_multivariate_applies_the_g23_offset():
    """The G23 term is additive on mu, so the offset is exactly beta * ratio."""
    x = np.linspace(0.0, 30.0, 11)
    base = TEXAS.simple_logistic_fixed_upper_multivariate(x, t0=15.0, b=0.2, k=0.3)
    with_g23 = TEXAS.simple_logistic_fixed_upper_multivariate(
        x, t0=15.0, b=0.2, k=0.3,
        beta_G23=0.05, gdgt23ratio=np.full_like(x, 2.0),
    )
    np.testing.assert_allclose(with_g23 - base, 0.05 * 2.0)


def test_simple_logistic_multivariate_rejects_mismatched_predictor():
    x = np.linspace(0.0, 30.0, 11)
    with pytest.raises(ValueError):
        TEXAS.simple_logistic_fixed_upper_multivariate(
            x, t0=15.0, b=0.2, k=0.3, beta_G23=0.05, gdgt23ratio=np.zeros(3),
        )


def test_find_optimal_no3_threshold_nointercept_recovers_a_planted_cutoff():
    """Below 2.0 the residuals follow -0.1*log10(no3/2); above, they are noise."""
    rng = np.random.default_rng(0)
    no3 = np.concatenate([rng.uniform(0.1, 2.0, 120), rng.uniform(2.0, 8.0, 120)])
    res = np.where(no3 < 2.0, -0.1 * np.log10(no3 / 2.0), 0.0)
    res = res + rng.normal(0.0, 0.002, res.size)

    threshold, table = TEXAS.find_optimal_no3_threshold_nointercept(no3, res)

    assert 1.0 < threshold < 4.0, f"planted cutoff 2.0 not recovered, got {threshold}"
    assert set(["threshold", "beta", "r2_nointercept", "n_points"]).issubset(table.columns)
    assert (table["threshold"] == pytest.approx(threshold)).any()


def test_bootstrap_se_is_reproducible_and_shaped_per_parameter():
    def line(x, a, b):
        return a * x + b

    rng = np.random.default_rng(1)
    X = np.linspace(0.0, 10.0, 60)
    y = 2.0 * X + 1.0 + rng.normal(0.0, 0.5, X.size)
    bounds = ([-10.0, -10.0], [10.0, 10.0])

    se_a, boots_a = TEXAS.bootstrap_se(line, X, y, p0=[1.0, 0.0],
                                       bounds=bounds, n_boot=40, seed=7)
    se_b, _ = TEXAS.bootstrap_se(line, X, y, p0=[1.0, 0.0],
                                 bounds=bounds, n_boot=40, seed=7)

    assert se_a.shape == (2,)
    assert boots_a.shape[1] == 2
    np.testing.assert_allclose(se_a, se_b), "same seed must give the same SEs"
    assert np.all(np.isfinite(se_a))


def test_create_summary_table_strips_the_prefix_and_names_the_model():
    a = xr.Dataset(attrs={"filename": "run_a.nc", "stan_diag_max_rhat": 1.001,
                          "stan_diag_overall_status": "PASS"})
    b = xr.Dataset(attrs={"stan_diag_max_rhat": 1.20,
                          "stan_diag_overall_status": "FAIL"})

    table = TEXAS.create_summary_table([a, b])

    assert list(table["model"]) == ["run_a.nc", "unknown"]
    assert "max_rhat" in table.columns and "stan_diag_max_rhat" not in table.columns
    assert list(table["overall_status"]) == ["PASS", "FAIL"]
    assert isinstance(table, pd.DataFrame)


def test_posterior_registry_entries_are_well_formed():
    """Every entry must carry the two fields download_posteriors() reads."""
    assert TEXAS.POSTERIOR_REGISTRY, "the registry is empty"
    for name, entry in TEXAS.POSTERIOR_REGISTRY.items():
        assert "filename" in entry, f"{name} has no filename"
        assert entry["filename"].endswith(".nc"), f"{name}: {entry['filename']}"
        assert isinstance(entry.get("size_mb"), (int, float)), f"{name} has no size_mb"


def test_set_cache_dir_redirects_both_caches_and_io_defaults(tmp_path):
    """It mutates module globals, so the test restores them itself."""
    import TEXAS.stan.io as io
    import TEXAS.utils.paths as paths

    saved = (paths.CACHE_ROOT, paths.CACHE_DIR, paths.POSTERIOR_CACHE_DIR,
             paths.INVT_CACHE_DIR, io.DEFAULT_FORWARD_DIR, io.DEFAULT_INVT_DIR)
    try:
        TEXAS.set_cache_dir(tmp_path)
        assert paths.POSTERIOR_CACHE_DIR == tmp_path / "TEXAS_posterior_cache"
        assert paths.INVT_CACHE_DIR == tmp_path / "TEXAS_invT_posterior_cache"
        # The point of the function: io.py bound its defaults at import time.
        assert io.DEFAULT_FORWARD_DIR == paths.POSTERIOR_CACHE_DIR
        assert io.DEFAULT_INVT_DIR == paths.INVT_CACHE_DIR
    finally:
        (paths.CACHE_ROOT, paths.CACHE_DIR, paths.POSTERIOR_CACHE_DIR,
         paths.INVT_CACHE_DIR, io.DEFAULT_FORWARD_DIR, io.DEFAULT_INVT_DIR) = saved
```

- [ ] **Step 2: Run the smoke tests**

Run: `pytest tests/test_public_api_smoke.py -q`
Expected: PASS, 7 tests. If `test_find_optimal_no3_threshold_nointercept_recovers_a_planted_cutoff` fails, widen the assertion window rather than weakening it to a tautology — the point is that the search finds the planted structure.

- [ ] **Step 3: Write the guard test**

Create `tests/test_public_api_docs.py`:

```python
"""The published surface of TEXAS: it resolves, it is used, it is documented.

Three properties, each of which has failed silently in this package before:

1. A name in ``__all__`` that does not resolve is an ImportError for anyone
   doing ``from TEXAS import *``.
2. A name nothing calls is dead weight on the public API. The 2026-09-07 audit
   found six such helpers and deleted them; this stops the next six accruing.
3. A one-line docstring on a fifteen-argument function is not documentation.
   Three lines is a low bar deliberately -- ruff's D1 rules enforce *presence*,
   this enforces that presence means something.

Reference scanning looks at code cells only, so a name that appears in a
notebook's stored *output* does not count, and this file excludes itself, so a
name cannot be kept alive by being listed here.
"""
import inspect
import json
import re
from pathlib import Path

import pytest

import TEXAS

REPO = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
MIN_DOC_LINES = 3


def _python_sources() -> list[str]:
    """Every test module except this one, plus every notebook code cell."""
    chunks = []
    for path in sorted((REPO / "tests").rglob("*.py")):
        if path.resolve() == SELF:
            continue
        chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    for path in sorted((REPO / "notebooks").rglob("*.ipynb")):
        if ".ipynb_checkpoints" in path.parts:
            continue
        try:
            nb = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            continue
        for cell in nb.get("cells", []):
            if cell.get("cell_type") == "code":
                chunks.append("".join(cell.get("source", [])))
    return chunks


SOURCES = _python_sources()


@pytest.mark.parametrize("name", TEXAS.__all__)
def test_export_resolves(name):
    """`from TEXAS import *` must not raise."""
    assert hasattr(TEXAS, name), f"TEXAS.__all__ lists '{name}' but it does not resolve"


@pytest.mark.parametrize("name", TEXAS.__all__)
def test_export_is_referenced(name):
    """Something must use it, or it should not be exported.

    If this fails on a name you just added, write a test that calls it. If you
    cannot think of one, that is the finding.
    """
    if name == "__version__":
        pytest.skip("module dunder, exercised by test_imports.py")
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    assert any(pattern.search(chunk) for chunk in SOURCES), (
        f"'{name}' is exported from TEXAS but no test module or notebook code "
        f"cell references it. Add a test that calls it, or drop it from "
        f"__all__ and add a CHANGELOG line."
    )


@pytest.mark.parametrize("name", TEXAS.__all__)
def test_export_is_documented(name):
    """Functions and classes need a docstring with something in it."""
    obj = getattr(TEXAS, name)
    if not (inspect.isfunction(obj) or inspect.isclass(obj)):
        pytest.skip(f"'{name}' is a constant or registry, not a callable")
    doc = (inspect.getdoc(obj) or "").strip()
    n_lines = len(doc.splitlines())
    assert n_lines >= MIN_DOC_LINES, (
        f"'{name}' has a {n_lines}-line docstring. The standard is a one-line "
        f"summary, then Args/Returns (and Raises where it raises); see the "
        f"other exports for the shape."
    )


def test_the_scan_can_actually_fail():
    """A canary: if _python_sources() ever returns nothing, every check above
    would pass vacuously except test_export_is_referenced, which would fail
    everywhere. Assert the corpus is real."""
    assert len(SOURCES) > 20, "the reference corpus looks empty; the scan is broken"
    assert any("predict_T_from_proxyObs" in chunk for chunk in SOURCES)
```

- [ ] **Step 4: Run the guard and confirm it passes**

Run: `pytest tests/test_public_api_docs.py -q`
Expected: PASS. With 46 names in `__all__` after Task 1 that is 138 parametrized cases plus the canary, of which one `test_export_is_referenced` case skips (`__version__`) and the non-callable exports skip in `test_export_is_documented`.

If `test_export_is_referenced` fails for a name, Task 1/2/5 did not land in order — re-check that `tests/test_range_utils.py` and `tests/test_public_api_smoke.py` both exist. Do **not** add the name to an allowlist.

- [ ] **Step 5: Edit the ruff configuration**

In `pyproject.toml`, replace lines 129–135:

```toml
[tool.ruff.lint]
# Start conservative: pyflakes (F) catches the real issues — undefined names,
# unused imports/variables — without a noisy whole-repo style reformat.
select = ["F"]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]   # re-exports (TEXAS.build_fwd_data etc.) are intentional
```

with:

```toml
[tool.ruff.lint]
# pyflakes (F) catches the real issues — undefined names, unused
# imports/variables — without a noisy whole-repo style reformat.
#
# D1 (pydocstyle: missing docstring) is scoped to src/TEXAS by the per-file
# ignores below. The package is the published API and is held to one
# documentation standard; tests and scripts are not, and turning D1 on there
# would add 216 violations that say nothing about the API.
select = ["F", "D1"]

# D100/D104 (module and package headers) would be a separate 23-file sweep and
# are deliberately deferred — see spec §9.6, which scopes the pass to public
# functions, classes and methods. D105/D107 (magic methods, __init__) are
# excluded by that spec directly: an __init__ is documented in its class
# docstring's Args block.
ignore = ["D100", "D104", "D105", "D107"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]   # re-exports (TEXAS.build_fwd_data etc.) are intentional
"tests/**" = ["D1"]        # D1 is for the published API, not the test suite
"scripts/**" = ["D1"]      # nor for the one-off analysis runners
```

`extend-exclude` at line 127 already keeps `notebooks`, `streamlit_app`, `docs`, `docker`, `build` and `dist` out of the lint entirely, so no ignore entry is needed for those.

- [ ] **Step 6: Verify the lint is clean and that the rule bites**

Run: `ruff check .`
Expected: `All checks passed!` — **except** for the one pre-existing `F401` at `tests/test_stan_model_archive.py:18`. If any `D1` violation appears under `src/TEXAS`, Tasks 1–3 did not fully land.

Prove the rule actually fires (do not commit this):

```bash
printf '\n\ndef temporarily_undocumented():\n    return 1\n' >> src/TEXAS/diagnostics.py
ruff check src/TEXAS/diagnostics.py    # expect: D103 Missing docstring in public function
git checkout -- src/TEXAS/diagnostics.py
ruff check src/TEXAS/diagnostics.py    # expect: All checks passed!
```

- [ ] **Step 7: Run the full suite**

Run: `pytest -q`
Expected: **372 + 7 + 139 = 518 passed**, plus the skips from the guard's own `pytest.skip` calls added to the 11 baseline skips. Record the exact figure the run prints; from here on that is the number later tasks must hold or grow.

- [ ] **Step 8: Add the changelog line**

Under `## [Unreleased]` in `CHANGELOG.md`, add a new subsection after `### Removed`:

```markdown
### Changed

- The public API is now guarded. `tests/test_public_api_docs.py` asserts that
  every name in `TEXAS.__all__` resolves, is referenced by at least one test or
  notebook code cell, and (for functions and classes) carries a docstring of at
  least three lines. `ruff`'s `D1` missing-docstring rules are enabled for
  `src/TEXAS`, with `D100`/`D104` (module and package headers) deferred and
  `D105`/`D107` (magic methods, `__init__`) excluded.
```

- [ ] **Step 9: Commit**

```bash
git add tests/test_public_api_docs.py tests/test_public_api_smoke.py pyproject.toml CHANGELOG.md
git commit -m "test: guard the public API surface (docs, references, ruff D1)

The reference check does not pass vacuously: six exported names had no test or
notebook using them, and test_public_api_smoke.py now exercises each. The guard
excludes itself from the scan so a name cannot be kept alive by being listed
in it.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 6: Archive the two truncated-prior models and remove `constraint_type` / `min_temp`

**This is one atomic task on purpose.** Moving the `.stan` files without removing the API leaves `_select_invT_stan_file` able to name a file that no longer ships; removing the API without moving the files leaves two dead models in the wheel. Neither half is committed alone.

**Files:**
- Move: `src/TEXAS/stan_models/invT_gen_logi_fixed_multiv_marginal_truncated_prior.stan` → `archive/pre-submission/stan_models/`
- Move: `src/TEXAS/stan_models/invT_gen_logi_fixed_univ_marginal_truncated_prior.stan` → `archive/pre-submission/stan_models/`
- Modify: `src/TEXAS/stan/invT.py` (`_SHIPPED_CONSTRAINTS` line 29; `get_invT_posterior` signature lines 89–90 and body lines 194–209, 224; `_select_invT_stan_file` lines 366, 378–381, 397–405, 413; `predict_temperature_from_proxyObs` signature lines 478–479 and body lines 524–525)
- Modify: `src/TEXAS/predict.py` (signature lines 165–166, docstring entries added in Task 4, forwarding lines 482–483, and the now-unused `Literal` import on line 39)
- Modify: `src/TEXAS/quality.py` (line 20)
- Modify: `scripts/paper/run_param_sensitivity.py` (line 153 `INVT_CONSTRAINT`, line 804 `constraint_type=`)
- Modify: `scripts/paper/invt_M_paleo_check.py` (line 77 `constraint_type=`)
- Modify: `tests/test_param_sensitivity_config.py` (line 59)
- Modify: `tests/test_stan_model_archive.py` (module docstring, line 18 unused `Path` import, `ARCHIVED`, `NEVER_EXISTED`, `test_shipped_set_is_exactly_nine`, `test_withdrawn_constraints_raise_with_a_useful_message`)
- Modify: `archive/README.md` (the index of the four sub-archives, created by plan 01 Task 6)
- Modify: `archive/submission-2026-04/stan_models/README.md` (its "What still ships" table only)
- Modify: `docs/_scripts/callmap_content.py` (the `stan.invT._select_invT_stan_file` explainer, lines 317–322)
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: nothing from Tasks 1–5 except that Task 4 wrote the `constraint_type` / `min_temp` docstring entries this task deletes.
- Produces: `predict_T_from_proxyObs`, `predict_temperature_from_proxyObs` and `get_invT_posterior` no longer accept `constraint_type` or `min_temp` — passing either is a `TypeError`. `_select_invT_stan_file(data, predictor_usage, *, threads_per_chain=None, model_type="direct", constraint_type="unconstrained", no3ratio=False, bounded=False) -> str` keeps its `constraint_type` parameter as a private, validating one: `_SHIPPED_CONSTRAINTS == frozenset({"unconstrained"})`, and anything else raises `ValueError` naming the archive. **`src/TEXAS/stan_models/` holds 7 `.stan` files.**

**Destination:** `archive/pre-submission/stan_models/`, as spec §9.8 says. Plan 01 Task 2 creates that directory and puts the 15 + 4 development models in it, so **plan 01 must have landed before this task runs.**

**These two will resolve by absolute path only, and that is deliberate.** `STAN_ARCHIVE_DIR` stays pinned to `archive/submission-2026-04/stan_models` — that is the fallback the eight 2026-04 models depend on, and widening it is not part of this work. Nothing regresses: once Step 5 removes `constraint_type`, `_select_invT_stan_file` can no longer construct these two filenames under any argument, so nothing selects them by stem. Anyone wanting to run one passes the explicit path, which `StanCompiler.resolve_stan_path()` passes through untouched:

```python
from pathlib import Path
p = Path("archive/pre-submission/stan_models/invT_gen_logi_fixed_multiv_marginal_truncated_prior.stan").resolve()
get_invT_posterior(..., stan_model_path=str(p))
```

**Do not extend `STAN_ARCHIVE_DIR` or the compiler's archive fallback to cover the new directory.**

**Do not touch `utils/naming.py::CONSTRAINT_CODES`.** `"truncated_prior": "t"` stays. Case ids already written to disk and to Zenodo carry that code.

- [ ] **Step 1: Update the tests first, and watch them fail**

In `tests/test_stan_model_archive.py`:

Delete the now-unused import on line 18, `from pathlib import Path` (this also clears the repo's one pre-existing `ruff` `F401`).

Extend `ARCHIVED` with the two new entries:

```python
ARCHIVED = [
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv",
    "gen_logi_fixed_hier_crtp_multiv_priorApprox",
    "gen_logi_fixed_hier_crtp_multiv",
    "gen_logi_fixed_culmesocore",
    "invT_gen_logi_fixed_univ_unconstrained",
    "invT_gen_logi_fixed_multiv_unconstrained",
    "invT_gen_logi_fixed_univ_marginal_hard_constraint",
    "invT_gen_logi_fixed_multiv_marginal_hard_constraint",
    # Archived 2026-09-07: docs/why_plugin_p50_differs.md, the only page that
    # explained them, is removed in the same pass, and the manuscript's
    # reconstructions are all unconstrained.
    "invT_gen_logi_fixed_univ_marginal_truncated_prior",
    "invT_gen_logi_fixed_multiv_marginal_truncated_prior",
]
```

Shrink `NEVER_EXISTED` to the one name the selector can still build:

```python
# The T0-shift arm only ever had the multiv/unconstrained inverse model. This
# was never written, so it is not a regression from an archive move -- it is
# caught at runtime by the FileNotFoundError in `stan/invT.py`, which says so.
# The two truncated_prior t0shift names that used to sit here are unreachable
# now that `truncated_prior` is not a shipped constraint.
NEVER_EXISTED = {
    "invT_gen_logi_fixed_univ_marginal_unconstrained_t0shift.stan",
}
```

Change the shipped-count test:

```python
def test_shipped_set_is_exactly_seven():
    """A model added to the shipped dir should be a deliberate act."""
    shipped = sorted(p.name for p in STAN_MODELS_DIR.glob("*.stan"))
    assert len(shipped) == 7, f"expected 7 shipped models, found {len(shipped)}: {shipped}"
```

Extend and re-point the withdrawn-constraint test:

```python
@pytest.mark.parametrize("constraint",
                         ["truncated_prior", "hard_constraint", "reparameterized", "soft"])
def test_withdrawn_constraints_raise_with_a_useful_message(constraint):
    """Fail at the argument, not later at a missing file."""
    with pytest.raises(ValueError) as exc:
        _select_invT_stan_file({"M": 100}, {}, constraint_type=constraint)
    assert "unconstrained" in str(exc.value), "the error should name the valid value"
    assert "archive/pre-submission" in str(exc.value), \
        "the error should say where the truncated-prior models went"
```

Add a test that the API is gone:

```python
def test_constraint_type_and_min_temp_are_not_public_parameters():
    """They left the API with the models they selected (2026-09-07)."""
    import inspect

    from TEXAS.predict import predict_T_from_proxyObs
    from TEXAS.stan.invT import get_invT_posterior

    for fn in (predict_T_from_proxyObs, get_invT_posterior):
        params = inspect.signature(fn).parameters
        assert "constraint_type" not in params, f"{fn.__name__} still takes constraint_type"
        assert "min_temp" not in params, f"{fn.__name__} still takes min_temp"
```

Finally, update the module docstring's opening line from "was pruned from 17 models to 9 on 2026-09-03; the other 8 moved" to:

```python
"""The shipped Stan model set, and the archive that keeps the rest runnable.

`src/TEXAS/stan_models/` was pruned from 17 models to 9 on 2026-09-03 and to 7
on 2026-09-07. Eight went to `archive/submission-2026-04/stan_models/`, which
`STAN_ARCHIVE_DIR` covers; the two truncated-prior inverses went to
`archive/pre-submission/stan_models/`, which it deliberately does not -- nothing
can select them by stem now that `constraint_type` is gone, so an absolute path
is the only route and the only one needed. Three things have to hold after a
move like that, and none of them fails loudly on its own:
```

(leave points 1–3 of that docstring unchanged.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_stan_model_archive.py -q`
Expected failures: `test_shipped_set_is_exactly_seven` (finds 9), the two new
`ARCHIVED` entries fail `test_archived_models_are_in_the_archive_not_the_package`
and `test_archived_models_still_resolve_by_plain_stem`, the `truncated_prior`
case of `test_withdrawn_constraints_raise_with_a_useful_message` fails (no raise),
and `test_constraint_type_and_min_temp_are_not_public_parameters` fails on both
functions.

- [ ] **Step 3: Move the two Stan files**

```bash
test -d archive/pre-submission/stan_models || { echo "plan 01 has not landed"; exit 1; }
git mv src/TEXAS/stan_models/invT_gen_logi_fixed_multiv_marginal_truncated_prior.stan \
       archive/pre-submission/stan_models/
git mv src/TEXAS/stan_models/invT_gen_logi_fixed_univ_marginal_truncated_prior.stan \
       archive/pre-submission/stan_models/
ls src/TEXAS/stan_models/*.stan | wc -l   # expect 7
```

The seven that remain: `gen_logi_fixed_culmeso`, `gen_logi_fixed_hier_crtp_univ_priorApprox`, `gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift`, `invT_gen_logi_fixed_multiv_marginal_unconstrained`, `invT_gen_logi_fixed_multiv_marginal_unconstrained_t0shift`, `invT_gen_logi_fixed_univ_marginal_unconstrained`, `linear_model`.

Also delete any compiled artifacts of the two moved models so a stale binary cannot shadow the move:

```bash
rm -f src/TEXAS/stan_models/invT_gen_logi_fixed_*_marginal_truncated_prior \
      src/TEXAS/stan_models/invT_gen_logi_fixed_*_marginal_truncated_prior.hpp \
      src/TEXAS/stan_models/invT_gen_logi_fixed_*_marginal_truncated_prior.exe
```

- [ ] **Step 4: Narrow `_select_invT_stan_file` and `_SHIPPED_CONSTRAINTS`**

In `src/TEXAS/stan/invT.py`, replace lines 25–29:

```python
#: Constraint formulations that have a Stan model in ``src/TEXAS/stan_models/``.
#: ``hard_constraint`` was archived (2026-09) to
#: ``archive/submission-2026-04/stan_models/``; ``reparameterized`` and ``soft``
#: appeared in the old type hints but were never implemented as Stan models.
_SHIPPED_CONSTRAINTS = frozenset({"unconstrained", "truncated_prior"})
```

with:

```python
#: Constraint formulations that have a Stan model in ``src/TEXAS/stan_models/``.
#: Only the unconstrained inverse ships. ``truncated_prior`` was archived on
#: 2026-09-07 to ``archive/pre-submission/stan_models/``, with the explainer
#: page that was its only documentation; ``hard_constraint`` was archived in
#: 2026-09 to ``archive/submission-2026-04/stan_models/``.
#: ``reparameterized`` and ``soft`` appeared in old type hints but were never
#: implemented as Stan models.
_SHIPPED_CONSTRAINTS = frozenset({"unconstrained"})
```

In `_select_invT_stan_file`, change the annotation on line 366 to
`constraint_type: Literal["unconstrained"] = "unconstrained",`, replace the
`constraint_type` bullet in its docstring with

```python
        constraint_type: Only ``"unconstrained"`` ships. Retained as a
            parameter so a caller passing a withdrawn value gets an error that
            names the archive, rather than a missing-file error at compile time.
```

and replace the validation block at lines 397–405 with:

```python
    if constraint_type not in _SHIPPED_CONSTRAINTS:
        raise ValueError(
            f"constraint_type={constraint_type!r} is not supported. "
            f"The only shipped inverse formulation is 'unconstrained'. "
            f"'truncated_prior' was archived to archive/pre-submission/stan_models/ "
            f"and 'hard_constraint' to archive/submission-2026-04/stan_models/; "
            f"either can be run by passing its absolute path as stan_model_path. "
            f"'reparameterized' and 'soft' were never implemented as Stan models."
        )
```

Note the removal of the `docs/why_plugin_p50_differs.md` pointer: that page is deleted by the §9.8 work, so the message must not send anyone to it.

Leave line 413 (`model_name += f"_{constraint_type}"`) as it is — with the set narrowed it can only ever append `_unconstrained`, which is the correct filename, and keeping it means the selector still reads as a name builder rather than a special case.

- [ ] **Step 5: Remove `constraint_type` and `min_temp` from `get_invT_posterior`**

Delete lines 89–90 from its signature:

```python
    constraint_type: Literal["unconstrained", "truncated_prior"] = "unconstrained",
    min_temp: Optional[float] = None,
```

Delete the auto-select and validation block, lines 194–209:

```python
    # Auto-select truncated_prior when min_temp is given and the user hasn't
    # explicitly chosen a different constraint type.
    if min_temp is not None and constraint_type == "unconstrained":
        constraint_type = "truncated_prior"
        print(f"🔧 Auto-selected constraint_type='truncated_prior' (min_temp={min_temp})")

    if constraint_type == "truncated_prior":
        if min_temp is None:
            raise ValueError(
                f"min_temp must be provided when constraint_type='{constraint_type}'. "
                "Example: min_temp=-1.8 for seawater freezing point."
            )
        data["min_temp"] = float(min_temp)
    elif min_temp is not None:
        print(f"⚠️  min_temp={min_temp} provided but constraint_type='{constraint_type}' — "
              f"min_temp will be ignored.")
```

Delete `            constraint_type=constraint_type,` from the `_select_invT_stan_file` call (line 224). The selector's own default supplies `"unconstrained"`.

- [ ] **Step 6: Remove them from layer 2 and layer 1**

In `src/TEXAS/stan/invT.py::predict_temperature_from_proxyObs`, delete lines 478–479 from the signature and lines 524–525 from the forwarded call:

```python
    constraint_type: Literal["unconstrained", "truncated_prior"] = "unconstrained",
    min_temp: Optional[float] = None,
```

```python
        constraint_type=constraint_type,
        min_temp=min_temp,
```

In `src/TEXAS/predict.py::predict_T_from_proxyObs`, delete lines 165–166 from the signature and lines 482–483 from the forwarded call (the same two pairs of lines), and delete the `constraint_type:` and `min_temp:` entries from the Args block Task 4 wrote.

`Literal` is then unused in `predict.py` — change line 39 from

```python
from typing import Dict, List, Literal, Optional, Sequence, Union, Any
```

to

```python
from typing import Dict, List, Optional, Sequence, Union, Any
```

`ruff` `F401` will flag it if you forget. In `invT.py`, `Literal` is still used by `model_type` — leave that import alone (Task 7 removes it).

- [ ] **Step 7: Update `quality.py`'s prose**

Line 20 currently reads:

```python
``prior_mu_t`` and ``prior_sigma_t`` rather than a measurement. Under the
default ``constraint_type="unconstrained"`` there is no lower bound on ``t_est``
at all, so the value returned can be physically impossible. The same happens in
```

Replace the middle line so it does not name a parameter that no longer exists:

```python
``prior_mu_t`` and ``prior_sigma_t`` rather than a measurement. The shipped
inverse models put no lower bound on ``t_est`` at all, so the value returned
can be physically impossible. The same happens in
```

- [ ] **Step 8: Update the two scripts and their config test**

In `scripts/paper/run_param_sensitivity.py`, delete line 153:

```python
INVT_CONSTRAINT = "unconstrained"
```

and delete line 804 from the `predict_temperature_from_proxyObs` call:

```python
        constraint_type    = INVT_CONSTRAINT,
```

In `scripts/paper/invt_M_paleo_check.py`, delete line 77:

```python
                constraint_type=R.INVT_CONSTRAINT,
```

In `tests/test_param_sensitivity_config.py`, delete line 59 from the `SHARED` dict:

```python
    "INVT_CONSTRAINT": True,
```

(That dict compares literals shared between the runner script and `SI_code02a`. `INVT_CONSTRAINT` is defined in neither once the script's line is gone; checked — no code cell of any notebook mentions it, so this removal takes nothing else with it.)

- [ ] **Step 9: Run the tests to verify they pass**

Run: `pytest tests/test_stan_model_archive.py tests/test_param_sensitivity_config.py -q`
Expected: PASS.

Run: `python -c "import TEXAS; TEXAS.predict_T_from_proxyObs(min_temp=-1.8)"`
Expected: `TypeError: predict_T_from_proxyObs() got an unexpected keyword argument 'min_temp'` — the argument error, before any Stan work starts.

- [ ] **Step 10: Update the archive index and the 2026-04 README's shipped list**

Two files, and the split matters: the two models land in `pre-submission/`, so
that is where the *index* records them; but the 2026-04 README's "What still
ships" table also lists them, and that list is now wrong wherever it lives.

**`archive/README.md`** (created by plan 01 Task 6 as the index of the four
sub-archives). Append a sentence to its `pre-submission/` row:

```markdown
Also holds `invT_gen_logi_fixed_{univ,multiv}_marginal_truncated_prior.stan`,
archived 2026-09-07 when `constraint_type` and `min_temp` left the public API.
`STAN_ARCHIVE_DIR` does not cover this directory, so these resolve by absolute
path only — which is all that is needed, since nothing can select them by stem
any more.
```

**`archive/submission-2026-04/stan_models/README.md`** — this directory did not
gain the two models, so its opening counts ("These eight models", "the other
8 moved") stay as they are. Only its shipped-set table is stale:

- Change the "What still ships" heading to
  `## What still ships (`src/TEXAS/stan_models/`, 7 files)`.
- Delete its `invT_gen_logi_fixed_{univ,multiv}_marginal_truncated_prior.stan`
  row, and add one line under the table:

```markdown
Two further models — `invT_gen_logi_fixed_{univ,multiv}_marginal_truncated_prior.stan`
— were archived on 2026-09-07 to `archive/pre-submission/stan_models/`, not
here, when `constraint_type` left the public API.
```

- [ ] **Step 11: Update the call-map explainer and regenerate**

In `docs/_scripts/callmap_content.py`, replace the `stan.invT._select_invT_stan_file` entry (lines 317–322):

```python
    "stan.invT._select_invT_stan_file":
        "Picks the .stan file from the shape of the problem: which optional predictors are "
        "active, and the temperature constraint scheme (unconstrained, "
        "truncated_prior). truncated_prior is the one that keeps P50 unbiased near a lower "
        "bound; hard_constraint was Jacobian-biased there and was archived in 2026-09, "
        "along with reparameterized and soft, which never had Stan models.",
```

with:

```python
    "stan.invT._select_invT_stan_file":
        "Picks the .stan file from the shape of the problem: which optional predictors are "
        "active, and whether the calibration is the T0-shift arm. Only the unconstrained "
        "inverse ships. truncated_prior was archived to archive/pre-submission/stan_models/ "
        "on 2026-09-07 and hard_constraint to archive/submission-2026-04/stan_models/ in "
        "2026-09; reparameterized and soft never had Stan models at all. Passing any of "
        "them raises here, at the "
        "argument, rather than failing later on a missing file.",
```

Run: `python docs/_scripts/build_callmap.py`
Expected: `docs/_static/callmap.html` rewritten with no error.

- [ ] **Step 12: Verify the wheel — it now ships 7 `.stan` files, not 9**

**State this explicitly.** Spec §10 item 3 reads

```
3. `python -m build && unzip -l dist/*.whl | grep -c '\.stan$'` → 9.
```

**After this task the correct expected value is 7**, because
`invT_gen_logi_fixed_univ_marginal_truncated_prior.stan` and
`invT_gen_logi_fixed_multiv_marginal_truncated_prior.stan` are no longer under
`src/TEXAS/stan_models/`, which is the non-recursive glob `pyproject.toml`
packages.

**Do not edit the spec.** It is the record of what was decided on 2026-09-07 and
stays as written; the change is recorded here and in this plan's Final
verification section, which is what an executor reads.

Then verify it for real:

```bash
python -m build
unzip -l dist/*.whl | grep -c '\.stan$'    # expect: 7
unzip -l dist/*.whl | grep truncated_prior # expect: no output
rm -rf dist build
```

- [ ] **Step 13: Run the full suite and the linter**

Run: `pytest -q`
Expected: the Task 5 total, plus 1 (the new `test_constraint_type_and_min_temp_are_not_public_parameters`), plus 1 (the fourth `constraint` parametrization), and the same skip count. No failures.
Run: `ruff check .`
Expected: **`All checks passed!`** — the pre-existing `F401` in `tests/test_stan_model_archive.py` was cleared in Step 1.

- [ ] **Step 14: Add the changelog lines**

Under `### Removed` in `CHANGELOG.md`:

```markdown
- `constraint_type=` and `min_temp=` on `predict_T_from_proxyObs`,
  `predict_temperature_from_proxyObs` and `get_invT_posterior`. The inverse is
  now unconstrained only, which is what the manuscript's reconstructions use.
  The two models they selected —
  `invT_gen_logi_fixed_{univ,multiv}_marginal_truncated_prior.stan` — moved to
  `archive/pre-submission/stan_models/` and remain runnable by passing an
  absolute path as `stan_model_path`. The wheel now ships 7 `.stan` files
  instead of 9. `utils.naming.CONSTRAINT_CODES` is deliberately unchanged: it
  is a name grammar, and case ids already on disk and on Zenodo carry the `t`
  code.
```

- [ ] **Step 15: Commit**

```bash
git add src/TEXAS archive scripts tests \
        docs/_scripts/callmap_content.py docs/_static/callmap.html CHANGELOG.md
git commit -m "refactor!: archive the truncated-prior inverse models, drop constraint_type/min_temp

The wheel ships 7 .stan files, not 9. Both models move to
archive/pre-submission/stan_models/, reachable by absolute path; nothing can
select them by stem any more because constraint_type is gone, so
STAN_ARCHIVE_DIR is deliberately left pinned to the 2026-04 archive.
CONSTRAINT_CODES is untouched: it decodes case ids already on Zenodo.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 7: Fold layer 2 into layer 1 and drop the dead parameters

**Files:**
- Modify: `src/TEXAS/stan/invT.py` (add `_percentiles_from_posterior`; delete `predict_temperature_from_proxyObs` lines 456–564; `get_invT_posterior` signature and body; `_attach_invT_metadata` lines 36–62)
- Modify: `src/TEXAS/predict.py` (imports lines 45–50, call block lines 461–511)
- Modify: `src/TEXAS/stan/sampler.py` (`auto_detect_predictors` legacy-key block lines 406–427; `sampler_invT_posterior` lines 507–536)
- Modify: `src/TEXAS/data/builder.py` (`build_invT_inputData` `scaledRI` alias, lines 66 and 105–114)
- Modify: `src/TEXAS/__init__.py` (lines 22–25, line 100)
- Modify: `src/TEXAS/stan/__init__.py` (line 8, line 21)
- Delete: `streamlit_app/debug_imports.py`
- Modify: `scripts/paper/invt_M_paleo_check.py` (lines 49, 70–80)
- Modify: `scripts/paper/run_param_sensitivity.py` (lines 763, 790–806)
- Modify: `tests/test_invt_save.py` (module docstring, lines 1–12)
- Create: `tests/test_invt_percentiles.py`
- Modify: `docs/_scripts/callmap_content.py` (lines 169–175, 250, 327–329)
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: Task 6's removal of `constraint_type` / `min_temp` from all three layers. Executing this task before Task 6 means carrying two parameters you then delete.
- Produces:
  - `TEXAS.stan.invT._percentiles_from_posterior(posterior: xr.Dataset) -> Dict[str, np.ndarray]` — private; keys are `f"p{round(q * 100)}"` for the quantiles present on `posterior["t_est"]`. Callers pass it positionally.
  - `get_invT_posterior(proxyObs, prior_mu_t, prior_sigma_t, *, proxy_name=None, fwd_posterior_name=None, site_name=None, temptype=None, predictors=None, config=None, save_results=False, save_draws=False, filename_tag=None, cache_dir=None, chains=None, iter_warmup=None, iter_sampling=None, seed=None, threads_per_chain=None, stan_model_path=None, fwd_posterior=None, fwd_cache_dir=None) -> xr.Dataset` — the first three are positional-required; `save` is gone, `save_results` defaults to `False`.
  - `sampler_invT_posterior(data, stan_file, site_name=None, temptype=None, **kwargs) -> Tuple[xr.Dataset, str]` — no `model_type`.
  - `build_invT_inputData(...)` — no `scaledRI=`.
  - `TEXAS.predict_T_from_proxyObs` returns the same dict shape as before plus `p40` and `p60`.
  - `TEXAS.predict_temperature_from_proxyObs` **no longer exists**, and leaves `TEXAS.__all__` and `TEXAS.stan.__all__`.

**Two latent bugs this fixes, both worth knowing before you start.**

1. `sampler_invT_posterior(..., model_type=...)` forwards `model_type` into `StanSampler.sample`'s `**kwargs`, which forwards it to `CmdStanModel.sample`, which has no such parameter. Any call that passed it raised `TypeError` inside cmdstanpy. `StanSampler.sample` pops `temptype`, `proxy_name`, `site_name`, `version` and `recompile` but never `model_type`. Removing the parameter removes the bug.
2. Layer 2's percentile dict hard-codes eleven keys while `get_invT_post_quantiles` computes thirteen quantiles — `p40` and `p60` were computed and then discarded, and a caller who passed a custom quantile set got a `KeyError` on `0.01`. Deriving the keys fixes both directions.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_invt_percentiles.py`:

```python
"""The percentile reduction that used to live in predict_temperature_from_proxyObs.

Layer 2 hard-coded eleven keys against a thirteen-quantile posterior, so p40 and
p60 were computed and thrown away, and any non-default quantile set raised
KeyError on 0.01. The keys now follow the quantiles the dataset actually has.
"""
import inspect

import numpy as np
import pytest
import xarray as xr

from TEXAS.stan.invT import _percentiles_from_posterior


def _quantile_ds(quantiles, n_obs=4):
    """A reduced invT posterior: t_est over (quantile, obs)."""
    values = np.tile(np.asarray(quantiles, dtype=float)[:, None] * 100.0, (1, n_obs))
    return xr.Dataset(
        {"t_est": (("quantile", "obs_idx"), values)},
        coords={"quantile": list(quantiles), "obs_idx": np.arange(n_obs)},
    )


def test_default_quantiles_give_thirteen_keys_including_p40_and_p60():
    """The eleven hard-coded keys silently dropped these two."""
    defaults = (0.01, 0.05, 0.1, 0.16, 0.25, 0.4, 0.5,
                0.6, 0.75, 0.84, 0.9, 0.95, 0.99)
    out = _percentiles_from_posterior(_quantile_ds(defaults))
    assert set(out) == {"p1", "p5", "p10", "p16", "p25", "p40", "p50",
                        "p60", "p75", "p84", "p90", "p95", "p99"}


def test_values_match_the_quantile_they_are_named_for():
    out = _percentiles_from_posterior(_quantile_ds((0.05, 0.5, 0.95)))
    np.testing.assert_allclose(out["p5"], 5.0)
    np.testing.assert_allclose(out["p50"], 50.0)
    np.testing.assert_allclose(out["p95"], 95.0)


def test_arrays_are_one_per_observation():
    out = _percentiles_from_posterior(_quantile_ds((0.05, 0.5, 0.95), n_obs=7))
    assert out["p50"].shape == (7,)


def test_a_custom_quantile_set_is_honoured_not_rejected():
    """The old code raised KeyError on 0.01 for any set that omitted it."""
    out = _percentiles_from_posterior(_quantile_ds((0.025, 0.5, 0.975)))
    assert set(out) == {"p2", "p50", "p98"}, out.keys()


def test_colliding_keys_raise_rather_than_overwrite():
    """0.005 and 0.0049 both round to p0; silently keeping one is the bug."""
    with pytest.raises(ValueError, match="distinct keys"):
        _percentiles_from_posterior(_quantile_ds((0.005, 0.0049, 0.5)))


def test_missing_t_est_is_a_clear_error():
    ds = xr.Dataset({"sigma": (("quantile",), [1.0])}, coords={"quantile": [0.5]})
    with pytest.raises(KeyError, match="t_est"):
        _percentiles_from_posterior(ds)


def test_layer_two_is_gone():
    """predict_temperature_from_proxyObs folded into predict_T_from_proxyObs."""
    import TEXAS
    import TEXAS.stan
    import TEXAS.stan.invT as invT

    assert not hasattr(invT, "predict_temperature_from_proxyObs")
    assert not hasattr(TEXAS, "predict_temperature_from_proxyObs")
    assert "predict_temperature_from_proxyObs" not in TEXAS.__all__
    assert "predict_temperature_from_proxyObs" not in TEXAS.stan.__all__


@pytest.mark.parametrize("param", ["use_opencl", "scaledRI", "model_type", "save"])
def test_dead_parameters_are_gone_from_get_invT_posterior(param):
    from TEXAS.stan.invT import get_invT_posterior
    assert param not in inspect.signature(get_invT_posterior).parameters


def test_the_three_inputs_are_positional_required():
    """They were keyword-with-None and raised a runtime TypeError instead."""
    from TEXAS.stan.invT import get_invT_posterior
    params = inspect.signature(get_invT_posterior).parameters
    for name in ("proxyObs", "prior_mu_t", "prior_sigma_t"):
        assert params[name].default is inspect.Parameter.empty, f"{name} still defaults"
        assert params[name].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD


def test_save_results_defaults_to_false_everywhere():
    from TEXAS.predict import predict_T_from_proxyObs
    from TEXAS.stan.invT import get_invT_posterior
    for fn in (predict_T_from_proxyObs, get_invT_posterior):
        assert inspect.signature(fn).parameters["save_results"].default is False


def test_scaledRI_alias_is_gone_from_the_builder():
    from TEXAS.data.builder import build_invT_inputData
    assert "scaledRI" not in inspect.signature(build_invT_inputData).parameters


def test_sampler_invT_posterior_does_not_forward_model_type(monkeypatch):
    """It used to reach CmdStanModel.sample, which has no such parameter."""
    from TEXAS.stan import sampler as sampler_mod

    seen = {}

    def fake_sample(self, data, stan_file, cpp_options=None, **kwargs):
        seen.update(kwargs)
        return "posterior", "diagnostics"

    monkeypatch.setattr(sampler_mod.StanSampler, "sample", fake_sample)
    sampler_mod.sampler_invT_posterior({"N": 1}, "invT_gen_logi_fixed_univ_marginal_unconstrained")

    assert "model_type" not in seen
    assert "model_type" not in inspect.signature(sampler_mod.sampler_invT_posterior).parameters
```

Add to `tests/test_invt_save.py` a test that layer 1 writes the `.npz` itself, without running Stan:

```python
def test_predict_T_from_proxyObs_writes_the_npz_itself(tmp_path, monkeypatch):
    """The .npz save moved out of the deleted wrapper and into predict.py."""
    import numpy as np
    import TEXAS.predict as predict_mod

    reduced = xr.Dataset(
        {"t_est": (("quantile", "obs_idx"),
                   np.tile(np.array([[5.0], [20.0], [35.0]]), (1, 3)))},
        coords={"quantile": [0.05, 0.5, 0.95], "obs_idx": np.arange(3)},
    )
    reduced.attrs.update({
        "SiteName": "TestSite", "temptype": "SST", "proxy_name": "scaledRI_cren3",
        "stan_model_name": "invT_gen_logi_fixed_univ_marginal_unconstrained",
        "use_gdgt23ratio": 0, "use_no3": 0, "no3_cutoff": 0.0,
        "model_type": "direct",
    })
    monkeypatch.setattr(predict_mod, "_get_invT_posterior",
                        lambda *a, **k: reduced)

    fwd = xr.Dataset(attrs={"use_gdgt23ratio": 0, "use_no3": 0,
                            "proxy_name": "scaledRI_cren3", "temptype": "SST"})
    result = predict_mod.predict_T_from_proxyObs(
        np.array([0.3, 0.4, 0.5]), prior_mu_t=20.0, prior_sigma_t=10.0,
        fwd_posterior=fwd, flags=False, save_results=True, cache_dir=tmp_path,
    )

    assert set(["p5", "p50", "p95"]).issubset(result)
    np.testing.assert_allclose(result["p50"], 20.0)
    written = list(tmp_path.glob("*.npz"))
    assert len(written) == 1, f"expected one .npz, got {written}"
    assert "TestSite" in written[0].name
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_invt_percentiles.py tests/test_invt_save.py -q`
Expected: `tests/test_invt_percentiles.py` fails at **collection** with `ImportError: cannot import name '_percentiles_from_posterior'`, and the new `test_invt_save.py` case fails with `AttributeError: ... has no attribute '_get_invT_posterior'`.

- [ ] **Step 3: Add `_percentiles_from_posterior` to `stan/invT.py`**

Insert immediately after `get_invT_post_quantiles` (i.e. after line 453):

```python
# -------------------------------------------------------------------------
def _percentiles_from_posterior(posterior: xr.Dataset) -> Dict[str, np.ndarray]:
    """Reduce a quantile-summarised invT posterior to a ``{"pN": array}`` dict.

    The keys follow the quantiles the dataset actually carries. The eleven that
    used to be hard-coded here silently dropped ``p40`` and ``p60`` -- both of
    which :func:`get_invT_post_quantiles` computes by default -- and raised
    ``KeyError`` on any run that asked for a different quantile set.

    Args:
        posterior: Output of :func:`get_invT_post_quantiles`. Must carry
            ``t_est`` with a ``quantile`` coordinate on the [0, 1] scale.

    Returns:
        One entry per quantile, keyed ``f"p{round(q * 100)}"`` (0.05 ->
        ``"p5"``), each a float array of length N.

    Raises:
        KeyError: if *posterior* has no ``t_est`` variable.
        ValueError: if two quantiles round to the same key, which would make
            one silently overwrite the other.
    """
    if "t_est" not in posterior:
        raise KeyError(
            "invT posterior has no 't_est' variable; found "
            f"{sorted(posterior.data_vars)}"
        )
    t_est = posterior["t_est"]
    quantiles = [float(q) for q in np.atleast_1d(t_est["quantile"].values)]
    keys = [f"p{round(q * 100)}" for q in quantiles]
    if len(set(keys)) != len(quantiles):
        raise ValueError(
            f"quantiles {quantiles} do not map to distinct keys {keys}; "
            "two entries would overwrite each other"
        )
    return {
        key: t_est.sel(quantile=q, drop=True).values
        for key, q in zip(keys, quantiles)
    }
```

- [ ] **Step 4: Delete `predict_temperature_from_proxyObs` and its re-exports**

Delete `src/TEXAS/stan/invT.py` lines 455–564 in full — the separator comment, the function, its `scaledRI` back-compat block, the `get_invT_posterior` call, the eleven-key `results` dict, and the `results_path` / `_save_invT_results` tail. `_save_invT_results` and `_generate_filename_base` become unused in `invT.py`; trim the import at lines 16–21 to:

```python
from TEXAS.stan.io import (
    load_posterior,
    _save_invT_posterior,
    _save_invT_draws,
)
```

In `src/TEXAS/stan/__init__.py`, change line 8 to
`from .invT import get_invT_posterior, get_invT_post_quantiles` and delete
`    "predict_temperature_from_proxyObs",` from `__all__`.

In `src/TEXAS/__init__.py`, change lines 22–25 to

```python
from .stan.invT import get_invT_posterior
```

and delete `    "predict_temperature_from_proxyObs",` at line 100.

- [ ] **Step 5: Clean up `get_invT_posterior`'s signature and body**

Replace the signature (lines 65–93) with:

```python
def get_invT_posterior(
    proxyObs: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    *,
    proxy_name: Optional[str] = None,
    fwd_posterior_name: Optional[str] = None,
    site_name: Optional[str] = None,
    temptype: Optional[str] = None,
    predictors: Optional[Dict[str, np.ndarray]] = None,
    config: Optional[InvTConfig] = None,
    save_results: bool = False,
    save_draws: bool = False,
    filename_tag: Optional[Union[str, Sequence[str]]] = None,
    cache_dir: Optional[Union[str, Path]] = None,
    chains: Optional[int] = None,
    iter_warmup: Optional[int] = None,
    iter_sampling: Optional[int] = None,
    seed: Optional[int] = None,
    threads_per_chain: Optional[int] = None,
    stan_model_path: Optional[Union[str, Path]] = None,
    fwd_posterior: Optional[xr.Dataset] = None,
    fwd_cache_dir: Optional[Union[str, Path]] = None,
) -> xr.Dataset:
    """Run the inverse-T model and return the quantile-reduced posterior.

    Builds the Stan data from a forward calibration posterior, samples,
    reduces the draws to quantiles, attaches run and provenance metadata, and
    optionally writes the result. Most callers want
    :func:`TEXAS.predict.predict_T_from_proxyObs`, which wraps this with the
    default calibration, the NO3 lookup and the quality flags.

    Args:
        proxyObs: Observed proxy values, shape (N,).
        prior_mu_t: Prior mean temperature (degC), scalar or shape (N,).
        prior_sigma_t: Prior temperature standard deviation (degC).
        proxy_name: Proxy label. Inherited from the forward posterior when
            omitted, and validated against it when given.
        fwd_posterior_name: Case id or legacy name of the forward calibration,
            read from *fwd_cache_dir*. Not needed when *fwd_posterior* is given.
        site_name: Label for the metadata and the output filenames.
        temptype: Temperature target label. Taken from the calibration when
            omitted.
        predictors: Non-thermal predictor arrays, e.g. ``{"no3": ...}``.
        config: :class:`InvTConfig`, or a dict of its fields. Sampler-level
            keys in that dict (``show_console``, ``show_progress``, ``refresh``,
            ``sig_figs``, ``timeout``) are routed to cmdstanpy instead.
        save_results: Write the quantile posterior as ``.nc``. Default False.
        save_draws: Also write the raw pre-quantile draws as
            ``{base}_draws.nc``.
        filename_tag: Extra tag(s) for the output filenames.
        cache_dir: Where results are **written**. Defaults to the invT cache.
        chains: MCMC chains. Default 4.
        iter_warmup: Warmup iterations per chain. Default 500.
        iter_sampling: Sampling iterations per chain. Default 1000.
        seed: Random seed.
        threads_per_chain: Within-chain parallelism. Only applied to models
            containing ``reduce_sum``; auto-sized from the CPU count if None.
        stan_model_path: Run a specific ``.stan`` file, including an absolute
            path into ``archive/submission-2026-04/stan_models/`` or
            ``archive/pre-submission/stan_models/``.
        fwd_posterior: A pre-loaded forward posterior. Skips all file I/O and
            any Zenodo download.
        fwd_cache_dir: Where *fwd_posterior_name* is **read** from. A different
            directory from *cache_dir*: passing *cache_dir* does not change
            where the calibration is looked up.

    Returns:
        The quantile-reduced posterior, with ``t_est`` over
        ``(quantile, obs_idx)`` and the run metadata in ``.attrs``.

    Raises:
        ValueError: if the calibration uses a NO3 correction but no NO3 values
            were supplied, or if *proxy_name* contradicts the calibration.
        FileNotFoundError: if the selected inverse model does not ship.
    """
```

Then delete these from the body:

- lines 107–116, the `scaledRI` back-compat block and the `proxyObs is None` `TypeError` — the signature enforces it now:

```python
    # Backward-compat: accept deprecated scaledRI kwarg
    if scaledRI is not None and proxyObs is None:
        import warnings
        warnings.warn(
            "The 'scaledRI' parameter is deprecated; use 'proxyObs' instead.",
            DeprecationWarning, stacklevel=2,
        )
        proxyObs = scaledRI
    if proxyObs is None:
        raise TypeError("get_invT_posterior() missing required argument: 'proxyObs'")
```

- lines 259–264, the OpenCL branch, replaced by a bare `cpp_options = {}`:

```python
    cpp_options = {}
    if use_opencl and threads_per_chain:
        raise ValueError("Cannot use both OpenCL and threading simultaneously.")
    if use_opencl:
        cpp_options["STAN_OPENCL"] = True
        sampler_kwargs["opencl_ids"] = [0, 0]
```
→
```python
    cpp_options = {}
```

- line 294, `ds.attrs["opencl_enabled"] = use_opencl`, and line 295,
  `ds.attrs["model_type"] = model_type`. `_attach_invT_metadata` already derives
  `model_type` from the Stan filename, which is the honest source now that the
  parameter is gone.

Replace the two `model_type == "direct"` guards with the unconditional form. Lines 269–274:

```python
    if model_type == "direct":
        N = data["N"]
        if threads_per_chain and _uses_reduce_sum:
            data["grainsize"] = 1
        else:
            data["grainsize"] = max(1, min(10, N // 4))
```
→
```python
    N = data["N"]
    if threads_per_chain and _uses_reduce_sum:
        data["grainsize"] = 1
    else:
        data["grainsize"] = max(1, min(10, N // 4))
```

Lines 313–314:

```python
    if model_type == "direct" and threads_per_chain:
        ds.attrs["grainsize"] = data.get("grainsize", 0)
```
→
```python
    if threads_per_chain:
        ds.attrs["grainsize"] = data.get("grainsize", 0)
```

Delete `            model_type=model_type,` from the `_select_invT_stan_file` call (line 223), and rename the save flag at line 351:

```python
    if save:
```
→
```python
    if save_results:
```

Finally simplify `_attach_invT_metadata` (lines 36–62): drop its unused
`model_type` parameter, so its signature becomes

```python
def _attach_invT_metadata(
    ds: xr.Dataset,
    data: dict,
    stan_file: str,
    site_name: Optional[str] = None,
) -> xr.Dataset:
    """Attach the metadata every saved reconstruction is identified by."""
```

and its model-type block becomes

```python
    ds.attrs["model_type"] = "direct" if "marginal" in stan_file else "ensemble"
    ds.attrs["use_marginal"] = 1 if ds.attrs["model_type"] == "direct" else 0
```

`Literal` is now unused in `invT.py`; change line 3 to
`from typing import Union, Optional, Dict, Sequence, List, Any` — except that
`Any` is also unused once layer 2 is gone, so make it
`from typing import Union, Optional, Dict, Sequence, List`. Ruff `F401` will tell
you if either judgement is wrong.

- [ ] **Step 6: Rewrite layer 1's call block in `predict.py`**

Change the imports at lines 45–50 to:

```python
from .stan.io import load_posterior, _generate_filename_base, _save_invT_results
from .ensemble.generator import generate_ensemble_auto
from .stan.invT import get_invT_posterior as _get_invT_posterior
from .stan.invT import _percentiles_from_posterior
from .data.builder import InvTConfig
from .constants import DEFAULT_FWD_POSTERIOR
from .data.ocean_lookup import lookup_no3_from_woa, get_ocean_prop_ds
```

Replace lines 461–485 (the `_predict_temperature_from_proxyObs(...)` call) with:

```python
    post_ds = _get_invT_posterior(
        proxyObs,
        prior_mu_t,
        prior_sigma_t,
        proxy_name=proxy_name,
        fwd_posterior_name=_fwd_name,
        fwd_posterior=_fwd_ds,
        site_name=site_name,
        temptype=temptype,
        predictors=predictors,
        config=config,
        save_results=save_results,
        save_draws=save_draws,
        filename_tag=filename_tag,
        cache_dir=cache_dir,
        chains=chains,
        iter_warmup=iter_warmup,
        iter_sampling=iter_sampling,
        seed=seed,
        threads_per_chain=threads_per_chain,
        fwd_cache_dir=fwd_cache_dir,
    )

    # The metadata dict layer 2 used to build. The explicit keys come first so
    # the posterior's own attrs win where they overlap -- the calibration is a
    # better witness to its own name than the argument that requested it.
    _metadata = {
        "fwd_posterior_name": _fwd_name,
        "filename_tag": filename_tag,
        **post_ds.attrs,
    }
    _result: Dict[str, Any] = {
        "proxyObs": np.asarray(proxyObs),
        "proxy_name": post_ds.attrs.get("proxy_name"),
        "metadata": _metadata,
        **_percentiles_from_posterior(post_ds),
    }

    # The .npz is written before the flags are attached, exactly as it was when
    # this lived in stan/invT.py: _save_invT_results np.asarray()s every value,
    # and a DataFrame is not that.
    if save_results:
        _results_path = None
        if cache_dir is not None:
            _out = Path(cache_dir)
            _out.mkdir(parents=True, exist_ok=True)
            _results_path = _out / f"{_generate_filename_base(_metadata, filename_tag)}.npz"
        _save_invT_results(_result, _results_path)
```

Everything from `    # Per-observation quality flags.` (line 487) onward is unchanged.

- [ ] **Step 7: Remove `model_type` from `sampler_invT_posterior`**

Replace lines 507–536 of `src/TEXAS/stan/sampler.py`:

```python
def sampler_invT_posterior(
    data: dict,
    stan_file: str,
    site_name: Optional[str] = None,
    temptype: Optional[str] = None,
    **kwargs
) -> Tuple[xr.Dataset, str]:
    """Compile and run an inverse-T Stan model on a prepared data dict.

    The raw sampling layer: it does no data assembly and no model selection.
    Use :func:`TEXAS.stan.invT.get_invT_posterior` for those, or
    :func:`TEXAS.predict.predict_T_from_proxyObs` for the full inverse.

    Args:
        data: Stan data dict, e.g. from ``build_invT_inputData()``.
        stan_file: Inverse model name, with or without ``.stan``.
        site_name: Label written into the posterior metadata.
        temptype: Temperature target label, e.g. ``"SST"``.
        **kwargs: Forwarded to ``CmdStanModel.sample``. ``seed`` defaults to 42
            and also seeds numpy, so a run is reproducible end to end.

    Returns:
        ``(posterior, diagnostics)``: the draws as an ``xr.Dataset`` with
        metadata attrs, and the human-readable diagnostic summary.
    """
    rng_seed = kwargs.setdefault("seed", 42)
    np.random.seed(rng_seed)

    compiler = StanCompiler()
    sampler = StanSampler(compiler)

    return sampler.sample(
        data=data,
        stan_file=stan_file,
        site_name=site_name,
        temptype=temptype,
        **kwargs
    )
```

Check whether `Literal` is still used elsewhere in `sampler.py` before touching its import; if it is not, remove it.

- [ ] **Step 8: Remove the two `scaledRI` back-compat blocks**

In `src/TEXAS/data/builder.py`, delete line 66 from `build_invT_inputData`'s signature (`    scaledRI: Union[np.ndarray, List[float]] = None,  # deprecated alias`) and lines 105–114:

```python
    # Backward-compat: accept deprecated scaledRI kwarg
    if scaledRI is not None and proxyObs is None:
        import warnings
        warnings.warn(
            "The 'scaledRI' parameter is deprecated; use 'proxyObs' instead.",
            DeprecationWarning, stacklevel=2,
        )
        proxyObs = scaledRI
    if proxyObs is None:
        raise TypeError("build_invT_inputData() missing required argument: 'proxyObs'")
```

Make the three inputs positional-required there too, matching `get_invT_posterior`:

```python
def build_invT_inputData(
    proxyObs: Union[np.ndarray, List[float]],
    prior_mu_t: Union[np.ndarray, float],
    prior_sigma_t: float,
    *,
    fwd_posterior_name: Optional[str] = None,
```

**Leave line 285 alone** — `sigma_key = f"sigma_scaledRI_{used_suffix}"` reads a *variable name inside old posteriors*, not the deprecated keyword, and dropping it would break every posterior written before the `proxyObs` rename.

In `src/TEXAS/stan/sampler.py::auto_detect_predictors`, delete the legacy key translation, lines 406–427:

```python
    # 0) Translate legacy scaledRI_* keys → proxyObs_* for backward compatibility
    _key_map = {
        "scaledRI_":    "proxyObs_",
        "mu_scaledRI_": "mu_proxyObs_",
        "sigma_scaledRI_": "sigma_proxyObs_",
    }
    _renames = {}
    for key in list(enhanced.keys()):
        for old_prefix, new_prefix in _key_map.items():
            if key.startswith(old_prefix):
                _renames[key] = new_prefix + key[len(old_prefix):]
                break
    if _renames:
        import warnings
        warnings.warn(
            f"Data dict contains legacy key(s) {list(_renames)}. "
            "Rename scaledRI_* → proxyObs_* (e.g. scaledRI_cul → proxyObs_cul). "
            "Auto-translating for now.",
            DeprecationWarning, stacklevel=3,
        )
        for old, new in _renames.items():
            enhanced[new] = enhanced.pop(old)

```

and renumber the comments that follow (`# 1)` … `# 7)`) down by one if you want them contiguous; leaving them is also fine. Task 3's docstring for this function already omits the translation.

- [ ] **Step 9: Repoint the external callers**

**`streamlit_app/debug_imports.py`** — delete it: `git rm streamlit_app/debug_imports.py`. Nothing imports or runs it (verified with a repo-wide `grep -rn debug_imports` across `*.py`, `*.md`, `*.toml`, `*.yml`: zero hits outside the file itself). It was a hand-run import tracer.

**`scripts/paper/invt_M_paleo_check.py`** — change line 49 from

```python
    from TEXAS.stan.invT import predict_temperature_from_proxyObs
```
to
```python
    from TEXAS.predict import predict_T_from_proxyObs
```

and the call at lines 70–80 to:

```python
            res = predict_T_from_proxyObs(
                sub[col].to_numpy(float),
                np.full(len(sub), mu), PRIOR_SIGMA_T,
                fwd_posterior=fwd, site_name=f"Mcheck_{rec.replace(' ','')}_M{M}",
                temptype=R.TEMPTYPE, proxy_name=col, predictors=preds or None,
                config=InvTConfig(n_draws=M), chains=CHAINS,
                iter_warmup=ITER_WARMUP, iter_sampling=ITER_SAMPLING, seed=SEED,
                save_results=False,          # a tuning run is not a reconstruction
                flags=False,                 # and it does not read them
            )
```

`fwd` is already the posterior *name* string from `R._invt_fwd_name()`, and layer 1's `fwd_posterior=` accepts a name string as well as a Dataset — that is the one rename this repoint needs. `flags=False` keeps the script's behaviour identical: layer 2 never computed flags. The script reads `res["p16"]`, `res["p50"]`, `res["p84"]`, which all survive the fold.

**`scripts/paper/run_param_sensitivity.py`** — change line 763 from

```python
    from TEXAS.stan.invT import predict_temperature_from_proxyObs
```
to
```python
    from TEXAS.predict import predict_T_from_proxyObs
```

and the call at lines 790–806 to:

```python
    res = predict_T_from_proxyObs(
        subset[proxy_col].to_numpy(dtype=float),
        np.full(len(subset), prior_mu),
        INVT_PRIOR_SIGMA_T,
        fwd_posterior      = fwd_name,
        site_name          = f"budgettest_n{len(subset)}",
        temptype           = TEMPTYPE,
        proxy_name         = proxy_col,
        predictors         = predictors or None,
        config             = InvTConfig(n_draws=M),
        chains             = chains,
        iter_warmup        = iter_warmup,
        iter_sampling      = iter_sampling,
        seed               = seed,
        save_results       = False,   # a tuning run is not a reconstruction
        flags              = False,   # and it does not read them
    )
```

It reads `res["metadata"]`, `res["p50"]`, `res["p16"]`, `res["p84"]`, `res["p5"]`, `res["p95"]` — all unchanged.

**`tests/test_invt_save.py`** — the reference is in the module docstring only (there is no import). Change lines 1–12's second sentence from

```
``_save_invT_posterior`` is what the production path
(``predict_temperature_from_proxyObs``) calls.
```
to
```
``_save_invT_posterior`` is what the production path
(``predict_T_from_proxyObs`` -> ``get_invT_posterior``) calls.
```

- [ ] **Step 10: Run the tests to verify they pass**

Run: `pytest tests/test_invt_percentiles.py tests/test_invt_save.py tests/test_predictors.py tests/test_pipeline.py -q`
Expected: PASS. `test_predictors.py` and `test_pipeline.py` are included because they exercise `auto_detect_predictors` and the builder, both edited here.

- [ ] **Step 11: Update the call-map content and regenerate**

In `docs/_scripts/callmap_content.py`:

Delete the whole `"Wrapper"` stage (lines 169–175):

```python
        {
            "name": "Wrapper",
            "note": "Thin layer that runs the model and turns draws into percentile summaries.",
            "nodes": [
                "stan.invT.predict_temperature_from_proxyObs",
            ],
        },
```

Change the `predict.predict_T_from_proxyObs` explainer's last clause (line 250) from
`"...and delegates to predict_temperature_from_proxyObs. prior_sigma_t should be..."` to
`"...and delegates to get_invT_posterior, reducing its quantiles to a p5/p50/p95 dict. prior_sigma_t should be..."`.

Delete the `"stan.invT.predict_temperature_from_proxyObs"` explainer entry (lines 327–329).

Run: `python docs/_scripts/build_callmap.py`
Expected: no error, and `grep -c predict_temperature_from_proxyObs docs/_static/callmap.html` → `0`.

- [ ] **Step 12: Run the full suite and the linter**

Run: `pytest -q`
Expected: the Task 6 total, plus 12 new cases in `tests/test_invt_percentiles.py` and 1 in `tests/test_invt_save.py`, minus 3 — Task 5's guard loses the `predict_temperature_from_proxyObs` parametrization from each of its three checks, since it leaves `__all__`. No failures.
Run: `ruff check .`
Expected: `All checks passed!`. If `F401` fires on `Literal` or `Any` in `invT.py`, `predict.py` or `sampler.py`, remove the flagged name from that import line.

- [ ] **Step 13: Add the changelog lines**

Under `### Removed` in `CHANGELOG.md`:

```markdown
- `TEXAS.predict_temperature_from_proxyObs` / `TEXAS.stan.invT.predict_temperature_from_proxyObs`.
  It was the pre-`predict.py` public entry point and had become a pass-through
  with 27 hand-copied parameters: its only work was reshaping the posterior into
  a percentile dict and optionally writing a `.npz`. Both moved into
  `predict_T_from_proxyObs`, which is the drop-in replacement — pass the
  calibration as `fwd_posterior=` (it takes a name or a Dataset) instead of
  `fwd_posterior_name=`, and `flags=False` if you do not want the quality flags.
- `use_opencl=` on `get_invT_posterior`. OpenCL support was deleted in 2026-05
  and nothing read the `opencl_enabled` attr it set.
- `scaledRI=` on `build_invT_inputData` and `get_invT_posterior`, and the
  `scaledRI_*` → `proxyObs_*` key translation in `auto_detect_predictors`.
  Deprecated since 0.1.x. (The `sigma_scaledRI_*` lookup in `build_invT_inputData`
  stays: it reads variable names inside older posteriors, not a keyword.)
- `model_type=` on `predict_T_from_proxyObs`, `get_invT_posterior`,
  `_select_invT_stan_file` and `sampler_invT_posterior`. Only `"direct"` has
  existed since the ensemble models were archived. On `sampler_invT_posterior`
  it was also a live bug: the value was forwarded into `CmdStanModel.sample`,
  which has no such parameter, so any call that passed it raised `TypeError`.
- `results_path=`, which went with `predict_temperature_from_proxyObs`. The
  `.npz` destination is now `cache_dir` + `filename_tag`, as it already was for
  the `.nc`.

### Changed

- `get_invT_posterior`'s `save=True` is now `save_results=False`, matching
  `predict_T_from_proxyObs`. One name and one default across both layers. The
  function has no caller outside the package, so nothing silently stops saving.
- `proxyObs`, `prior_mu_t` and `prior_sigma_t` are positional-required on
  `get_invT_posterior` and `build_invT_inputData`. They were keyword arguments
  defaulting to `None` that raised `TypeError` at runtime instead.
- `predict_T_from_proxyObs` now returns a percentile key for every quantile the
  posterior carries, derived rather than hard-coded — so `p40` and `p60`, which
  were computed and discarded, are included.
```

- [ ] **Step 14: Commit**

```bash
git add src/TEXAS scripts tests docs/_scripts/callmap_content.py \
        docs/_static/callmap.html CHANGELOG.md
git rm streamlit_app/debug_imports.py
git commit -m "refactor!: fold predict_temperature_from_proxyObs into predict_T_from_proxyObs

Layer 2 only reshaped quantiles and wrote a .npz. Both move up; the percentile
keys are now derived from the quantiles present, which recovers p40 and p60.
Removes use_opencl, the scaledRI alias, model_type, results_path, and the
save=/save_results= split. Dropping model_type from sampler_invT_posterior also
fixes a TypeError: it was forwarded to CmdStanModel.sample, which has no such
parameter.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 8: One source of truth for predictor keys, lat/lon names, and screening columns

**Files:**
- Modify: `src/TEXAS/constants.py` (lines 19–20)
- Modify: `src/TEXAS/predict.py` (the predictor-dict writes and the `use_*` attr reads inside `predict_T_from_proxyObs`)
- Modify: `src/TEXAS/ensemble/generator.py` (lines 96–100, 60–70)
- Modify: `src/TEXAS/utils/regrid.py` (extract `resolve_latlon_names` from `_prepare_grids`, lines 20–29)
- Modify: `src/TEXAS/data/ocean_lookup.py` (`lookup_no3_from_woa`, lines 63–68 signature and 130–175 body)
- Modify: `src/TEXAS/data/screening.py` (`plot_decision_boundary`, `plot_multiple_ellipses`, `plot_pairwise_ellipses`, `plot_pca_projection`, `plot_corner`)
- Modify: `tests/test_screening.py`
- Modify: `tests/test_regrid.py`
- Create: `tests/test_ocean_lookup.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: Task 7's rewritten `predict.py` call block (this task edits the predictor lines above it).
- Produces:
  - `TEXAS.constants.GDGT23RATIO_KEY = "gdgt23ratio"` and `TEXAS.constants.NO3_KEY = "no3"`, with `OPTIONAL_PREDICTORS = [GDGT23RATIO_KEY, NO3_KEY]` built from them. Neither new name is added to `TEXAS.__all__`, so Task 5's guard is unaffected.
  - `TEXAS.utils.regrid.resolve_latlon_names(ds, lat_name=None, lon_name=None) -> tuple[str, str]` — module-level, used by `_prepare_grids` and by `ocean_lookup`.
  - `lookup_no3_from_woa(lat, lon, woa_dataset, variable="no3_sf2tc_avg", method="linear", *, lat_name=None, lon_name=None)`.
  - Five `MahalanobisOutlierDetector.plot_*` methods gain `columns: Optional[dict] = None`, the same logical→physical map `fit`, `transform`, `detect_outliers` and `fit_predict` already take.

**Why the constant, not the list.** `OPTIONAL_PREDICTORS` is a list, so a *lookup* site cannot read from it without indexing by position — which is worse than the literal it replaces. Naming the two keys and building the list from them keeps one source of truth and stays readable at both kinds of site. `builder.py:309` and `metadata.py:108` iterate the list and are unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_regrid.py`:

```python
def test_resolve_latlon_names_prefers_pop_names():
    """POP output carries TLAT/TLONG; the WOA fields carry lat/lon."""
    import xarray as xr

    from TEXAS.utils.regrid import resolve_latlon_names

    pop = xr.Dataset({"TLAT": (("y", "x"), np.zeros((2, 2))),
                      "TLONG": (("y", "x"), np.zeros((2, 2)))})
    assert resolve_latlon_names(pop) == ("TLAT", "TLONG")

    woa = xr.Dataset(coords={"lat": [0.0, 1.0], "lon": [0.0, 1.0]})
    assert resolve_latlon_names(woa) == ("lat", "lon")


def test_resolve_latlon_names_honours_explicit_names():
    import xarray as xr

    from TEXAS.utils.regrid import resolve_latlon_names

    ds = xr.Dataset(coords={"lat": [0.0], "lon": [0.0], "y_deg": [0.0], "x_deg": [0.0]})
    assert resolve_latlon_names(ds, lat_name="y_deg", lon_name="x_deg") == ("y_deg", "x_deg")


def test_resolve_latlon_names_says_what_it_looked_at():
    import pytest
    import xarray as xr

    from TEXAS.utils.regrid import resolve_latlon_names

    ds = xr.Dataset(coords={"row": [0.0], "col": [0.0]})
    with pytest.raises(ValueError, match="auto-detect"):
        resolve_latlon_names(ds)
```

Create `tests/test_ocean_lookup.py`:

```python
"""The NO3 lookup must not assume the WOA grid spells its axes 'lat'/'lon'.

It did: `da["lon"]` at ocean_lookup.py:147. utils/regrid.py already had a
candidate-detecting resolver with a clear error, so the lookup now uses it.
"""
import numpy as np
import pytest
import xarray as xr

from TEXAS.data.ocean_lookup import lookup_no3_from_woa


def _grid(lat_name="lat", lon_name="lon", lons=None):
    lats = np.arange(-10.0, 10.1, 5.0)
    lons = np.arange(0.0, 360.0, 30.0) if lons is None else np.asarray(lons, float)
    # A field that is a simple function of longitude, so a mis-resolved axis
    # produces a visibly wrong number rather than a plausible one.
    values = np.tile(lons[None, :], (lats.size, 1))
    return xr.Dataset(
        {"no3_sf2tc_avg": ((lat_name, lon_name), values)},
        coords={lat_name: lats, lon_name: lons},
    )


def test_lookup_on_a_latitude_longitude_grid():
    ds = _grid("latitude", "longitude")
    got = lookup_no3_from_woa(0.0, 30.0, ds)
    np.testing.assert_allclose(float(got), 30.0)


def test_lookup_still_works_on_the_plain_lat_lon_grid():
    got = lookup_no3_from_woa(0.0, 60.0, _grid())
    np.testing.assert_allclose(float(got), 60.0)


def test_explicit_names_win_over_detection():
    ds = _grid("latitude", "longitude")
    got = lookup_no3_from_woa(0.0, 90.0, ds, lat_name="latitude", lon_name="longitude")
    np.testing.assert_allclose(float(got), 90.0)


def test_negative_longitude_is_normalised_to_the_datasets_convention():
    """The dataset is 0-360; -90 must land on 270, not off the grid."""
    got = lookup_no3_from_woa(0.0, -90.0, _grid("latitude", "longitude"))
    np.testing.assert_allclose(float(got), 270.0)


def test_array_input_returns_one_value_per_point():
    got = lookup_no3_from_woa(np.zeros(3), np.array([0.0, 30.0, 60.0]),
                              _grid("latitude", "longitude"))
    assert got.shape == (3,)
    np.testing.assert_allclose(got, [0.0, 30.0, 60.0])


def test_unresolvable_axes_raise_before_interpolating():
    ds = _grid().rename({"lat": "row", "lon": "col"})
    with pytest.raises(ValueError, match="auto-detect"):
        lookup_no3_from_woa(0.0, 0.0, ds)
```

Append to `tests/test_screening.py`:

```python
class TestPlotColumnMapping:
    """The plot methods indexed df[self.features[...]] directly, so a caller
    using columns= everywhere else still had to rename its frame to plot."""

    @staticmethod
    def _physical_frame():
        train = _training_df()
        return train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})

    MAPPING = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}

    def test_decision_boundary_accepts_a_columns_map(self):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9)
        det.fit(_training_df())
        fig, ax = plt.subplots()
        try:
            returned_ax, ellipse = det.plot_decision_boundary(
                self._physical_frame(), ax=ax, columns=self.MAPPING)
            assert returned_ax is ax
            assert ellipse is not None
            assert len(ax.collections) > 0, "no points were drawn"
        finally:
            plt.close(fig)

    def test_decision_boundary_without_a_map_still_needs_logical_names(self):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9)
        det.fit(_training_df())
        fig, ax = plt.subplots()
        try:
            with pytest.raises(KeyError):
                det.plot_decision_boundary(self._physical_frame(), ax=ax)
        finally:
            plt.close(fig)

    @pytest.mark.parametrize("method_name", [
        "plot_decision_boundary", "plot_multiple_ellipses",
        "plot_pairwise_ellipses", "plot_pca_projection", "plot_corner",
    ])
    def test_every_plot_method_takes_columns(self, method_name):
        import inspect
        method = getattr(MahalanobisOutlierDetector, method_name)
        assert "columns" in inspect.signature(method).parameters, (
            f"{method_name} cannot be given the logical->physical map that "
            "fit_predict already accepts")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_regrid.py tests/test_ocean_lookup.py tests/test_screening.py -q`
Expected: the three `resolve_latlon_names` cases fail at import (`ImportError`); `test_ocean_lookup.py`'s `latitude`/`longitude` cases fail with `ValueError: woa_dataset must have 'lat' and 'lon' dimensions`; and the `TestPlotColumnMapping` cases fail with `TypeError: ... got an unexpected keyword argument 'columns'`.

- [ ] **Step 3: Name the predictor keys in `constants.py`**

Replace lines 19–20:

```python
# Optional predictors
OPTIONAL_PREDICTORS = ["gdgt23ratio", "no3"]
```

with:

```python
# Optional (non-thermal) predictors. The two named constants are the single
# source of truth for the key spelling; OPTIONAL_PREDICTORS is the canonical
# order in which they are iterated (data/builder.py, stan/metadata.py). Code
# that looks *up* one predictor uses the name; code that loops over both uses
# the list. Neither spells the string again.
GDGT23RATIO_KEY = "gdgt23ratio"
NO3_KEY = "no3"
OPTIONAL_PREDICTORS = [GDGT23RATIO_KEY, NO3_KEY]
```

- [ ] **Step 4: Use them in `predict.py`**

Extend the constants import:

```python
from .constants import DEFAULT_FWD_POSTERIOR, GDGT23RATIO_KEY, NO3_KEY
```

Then, inside `predict_T_from_proxyObs`, replace the five literal sites:

```python
    if no3 is not None:
        predictors["no3"] = no3
    if gdgt23ratio is not None:
        predictors["gdgt23ratio"] = gdgt23ratio
```
→
```python
    if no3 is not None:
        predictors[NO3_KEY] = no3
    if gdgt23ratio is not None:
        predictors[GDGT23RATIO_KEY] = gdgt23ratio
```

and in the warning block:

```python
        if predictors.get("gdgt23ratio") is not None and not _attrs.get("use_gdgt23ratio", False):
```
→
```python
        if (predictors.get(GDGT23RATIO_KEY) is not None
                and not _attrs.get(f"use_{GDGT23RATIO_KEY}", False)):
```

```python
        if predictors.get("gdgt23ratio") is None and _attrs.get("use_gdgt23ratio", False):
```
→
```python
        if (predictors.get(GDGT23RATIO_KEY) is None
                and _attrs.get(f"use_{GDGT23RATIO_KEY}", False)):
```

```python
        if predictors.get("no3") is not None and not _attrs.get("use_no3", False):
```
→
```python
        if (predictors.get(NO3_KEY) is not None
                and not _attrs.get(f"use_{NO3_KEY}", False)):
```

Leave the warning *messages* spelling `gdgt23ratio` and `no3` in prose — they are addressed to a human reading a traceback, and an f-string there would only make them harder to read.

- [ ] **Step 5: Use them in `ensemble/generator.py`**

Add at the top, after the `detection` import:

```python
from ..constants import GDGT23RATIO_KEY, NO3_KEY
```

Replace the attr reads at lines 60–70:

```python
    if use_gdgt23ratio_flag is None:
        # apply only if the attr exists and is truthy
        use_gdgt = bool(post_ds.attrs.get("use_gdgt23ratio", False))
```
→
```python
    if use_gdgt23ratio_flag is None:
        # apply only if the attr exists and is truthy
        use_gdgt = bool(post_ds.attrs.get(f"use_{GDGT23RATIO_KEY}", False))
```

```python
    if use_no3_flag is None:
        # apply only if the attr exists and is truthy
        use_no3 = bool(post_ds.attrs.get("use_no3", False))
```
→
```python
    if use_no3_flag is None:
        # apply only if the attr exists and is truthy
        use_no3 = bool(post_ds.attrs.get(f"use_{NO3_KEY}", False))
```

and the kwargs built for the model function at lines 96–100:

```python
            if use_gdgt and gdgt23ratio is not None:
                params["gdgt23ratio"] = gdgt23ratio
            if use_no3 and no3 is not None:
                params["no3"] = no3
                params["no3_cutoff"] = eff_no3_cutoff
```
→
```python
            if use_gdgt and gdgt23ratio is not None:
                params[GDGT23RATIO_KEY] = gdgt23ratio
            if use_no3 and no3 is not None:
                params[NO3_KEY] = no3
                params["no3_cutoff"] = eff_no3_cutoff
```

**Leave the `metadata` dict's keys at lines 135–138 as literals** (`"use_gdgt23ratio"`, `"use_no3"`, `"gdgt23ratio_provided"`, `"no3_provided"`). Those are the *output* contract of `generate_ensemble` — callers read them by name — not predictor lookups, and an f-string there would obscure a public key for no gain.

- [ ] **Step 6: Extract `resolve_latlon_names` in `utils/regrid.py`**

Add above `_prepare_grids`:

```python
def resolve_latlon_names(ds, lat_name=None, lon_name=None):
    """Resolve a dataset's latitude and longitude coordinate names.

    Grids in this project arrive under several spellings -- POP curvilinear
    output as ``TLAT``/``TLONG``, the WOA23-derived fields as ``lat``/``lon``,
    CMIP-style files as ``latitude``/``longitude`` -- so the names are detected
    rather than assumed. An explicit name always wins over detection.

    Args:
        ds: An ``xr.Dataset`` or ``xr.DataArray`` to inspect.
        lat_name: Latitude coordinate name. ``None`` auto-detects, trying
            ``TLAT``, ``lat``, ``latitude``, ``LAT``, ``Lat`` in that order.
        lon_name: Longitude coordinate name. ``None`` auto-detects, trying
            ``TLONG``, ``lon``, ``longitude``, ``LON``, ``Lon``, ``LONG``.

    Returns:
        ``(lat_name, lon_name)`` as they appear in *ds*.

    Raises:
        ValueError: if either name is absent and no candidate matches. The
            message lists what *ds* does contain, so the caller can pass the
            right names rather than guess again.
    """
    if lat_name is None:
        lat_name = next((c for c in _LAT_CANDIDATES if c in ds), None)
    if lon_name is None:
        lon_name = next((c for c in _LON_CANDIDATES if c in ds), None)
    if lat_name is None or lon_name is None:
        available = list(ds.variables) if hasattr(ds, "variables") else list(ds.coords)
        raise ValueError(
            f"Could not auto-detect lat/lon coordinates. Available: {available}. "
            "Pass lat_name and lon_name explicitly."
        )
    return lat_name, lon_name
```

Then replace the first nine lines of `_prepare_grids` (lines 21–29) with a call:

```python
def _prepare_grids(ds, lat_name, lon_name, target_res, lat_range, lon_range):
    lat_name, lon_name = resolve_latlon_names(ds, lat_name, lon_name)
    lat_dims, lon_dims = ds[lat_name].dims, ds[lon_name].dims
```

The rest of `_prepare_grids` is unchanged.

- [ ] **Step 7: Use the resolver in `data/ocean_lookup.py`**

Add the import at the top of the file:

```python
from ..utils.regrid import resolve_latlon_names
```

Change the signature (lines 63–68) to:

```python
def lookup_no3_from_woa(
    lat: Union[float, np.ndarray],
    lon: Union[float, np.ndarray],
    woa_dataset: xr.Dataset,
    variable: str = "no3_sf2tc_avg",
    method: Literal["linear", "nearest"] = "linear",
    *,
    lat_name: Optional[str] = None,
    lon_name: Optional[str] = None,
) -> np.ndarray:
```

In its docstring, change the `woa_dataset` entry from

```
        WOA23-derived dataset with a ``(lat, lon)`` grid containing *variable*.
        Dimensions must be named ``"lat"`` and ``"lon"``.
```
to
```
        WOA23-derived dataset on a regular latitude/longitude grid containing
        *variable*. The axis names are detected (``lat``/``lon``,
        ``latitude``/``longitude``, ``LAT``/``LON``, ...); pass *lat_name* /
        *lon_name* to override.
```

and add two Parameters entries before `Returns`:

```
    lat_name : str, optional
        Latitude coordinate name.  Auto-detected when omitted.
    lon_name : str, optional
        Longitude coordinate name.  Auto-detected when omitted.
```

Change the `Raises` entry from `If *woa_dataset* does not have "lat" and "lon" dimensions.` to
`If the latitude/longitude axes cannot be resolved, or the resolved names are coordinates but not dimensions.`

Replace the validation block (lines 130–135):

```python
    # ── Validate dataset ──────────────────────────────────────────────────────
    if "lat" not in woa_dataset.dims or "lon" not in woa_dataset.dims:
        raise ValueError(
            "woa_dataset must have 'lat' and 'lon' dimensions. "
            f"Found: {list(woa_dataset.dims)}"
        )
```
with
```python
    # ── Resolve the grid axes ─────────────────────────────────────────────────
    # utils/regrid.py already knows the spellings these grids arrive under; the
    # lookup used to hard-code "lat"/"lon" and fail on anything else.
    lat_name, lon_name = resolve_latlon_names(woa_dataset, lat_name, lon_name)
    if lat_name not in woa_dataset.dims or lon_name not in woa_dataset.dims:
        raise ValueError(
            f"woa_dataset must be on a regular grid: {lat_name!r} and "
            f"{lon_name!r} are coordinates but not dimensions. "
            f"Found dims: {list(woa_dataset.dims)}"
        )
```

Replace line 147:

```python
    ds_lon = da["lon"].values
```
with
```python
    ds_lon = da[lon_name].values
```

and both `interp` calls (lines 162–175):

```python
    if scalar_input:
        result = da.interp(
            lat=float(lat_arr),
            lon=float(lon_arr),
            method=method,
        )
        out = np.asarray(result.values, dtype=float)
    else:
        # Vectorised interpolation: build coordinate DataArrays so xarray
        # performs point-wise (not grid) interpolation.
        lat_da = xr.DataArray(lat_arr, dims="obs")
        lon_da = xr.DataArray(lon_arr, dims="obs")
        result = da.interp(lat=lat_da, lon=lon_da, method=method)
        out = np.asarray(result.values, dtype=float)
```
with
```python
    if scalar_input:
        result = da.interp(
            {lat_name: float(lat_arr), lon_name: float(lon_arr)},
            method=method,
        )
        out = np.asarray(result.values, dtype=float)
    else:
        # Vectorised interpolation: build coordinate DataArrays so xarray
        # performs point-wise (not grid) interpolation.
        lat_da = xr.DataArray(lat_arr, dims="obs")
        lon_da = xr.DataArray(lon_arr, dims="obs")
        result = da.interp({lat_name: lat_da, lon_name: lon_da}, method=method)
        out = np.asarray(result.values, dtype=float)
```

- [ ] **Step 8: Give the five screening plot methods a `columns=` map**

The pattern is the same in all five, and it is the pattern `fit_predict` already
uses: resolve once at the top through `self._resolve_features`, which returns a
copy of the frame relabelled to the logical names, then work on that copy. Every
nested call (`detect_outliers`, `detect_outliers_manual`, `pair_detector.fit`)
then needs no `columns=` of its own, because the frame it receives is already
logical.

Add to each of the five signatures, as a keyword-only argument after the
existing ones:

```python
        *,
        columns: Optional[dict] = None,
```

(`plot_decision_boundary`, `plot_multiple_ellipses`, `plot_pairwise_ellipses`
and `plot_corner` have no `*` today; `plot_pca_projection` does not either. Add
one. `plot_corner` already takes `**kwargs`, so put `columns` before it.)

Add to each docstring's Parameters block:

```
        columns : dict, optional
            Mapping ``{logical_name: physical_column}`` for callers whose
            DataFrame uses different column names than ``self.features`` --
            the same map ``fit``, ``transform`` and ``fit_predict`` accept.
```

Then insert, as the first statement after each method's existing validation
(`if len(self.features) != 2: raise ...`, `if not self.is_fitted: raise ...`):

```python
        # Work on a copy relabelled to the logical names, so every df[...] below
        # and every nested detector call sees self.features regardless of what
        # the caller's columns are called.
        df = self._resolve_features(df, columns=columns, on_unscorable='ignore')
```

Rebinding `df` is deliberate: it means the rest of each method — `df[self.features[0]]`,
`self.detect_outliers_manual(df)`, `pair_detector.fit(df)`, `df.loc[inliers, feat_i]`,
`df[self.features]` — needs no further edit. `_resolve_features` preserves the
index, so the boolean masks these methods build still align.

`on_unscorable='ignore'` avoids a duplicate NaN warning: `detect_outliers` /
`detect_outliers_manual` still warn once, from inside.

- [ ] **Step 9: Run the tests to verify they pass**

Run: `pytest tests/test_regrid.py tests/test_ocean_lookup.py tests/test_screening.py tests/test_ensemble_percentiles.py tests/test_predictors.py -q`
Expected: PASS.

- [ ] **Step 10: Confirm the literals are gone**

```bash
grep -n '"gdgt23ratio"\|"no3"' src/TEXAS/predict.py src/TEXAS/ensemble/generator.py
```
Expected: only the two `metadata` output keys in `generator.py` and any occurrence inside a warning *message string* in `predict.py`. No dict-lookup or attr-name use.

```bash
grep -n 'da\["lon"\]\|da\["lat"\]' src/TEXAS/data/ocean_lookup.py
```
Expected: no output.

- [ ] **Step 11: Run the full suite and the linter**

Run: `pytest -q`
Expected: the Task 7 total plus 3 (regrid) + 6 (ocean lookup) + 7 (screening) new cases, no failures.
Run: `ruff check .` — expected `All checks passed!`.

- [ ] **Step 12: Add the changelog lines**

Under `### Changed` in `CHANGELOG.md`:

```markdown
- `lookup_no3_from_woa` now detects the grid's latitude/longitude axis names
  instead of hard-coding `"lat"`/`"lon"`, reusing `utils.regrid`'s resolver
  (now public as `resolve_latlon_names`). New keyword arguments `lat_name=` and
  `lon_name=` override the detection.
- The five `MahalanobisOutlierDetector.plot_*` methods accept `columns=`, the
  same logical-to-physical column map `fit`, `transform` and `fit_predict`
  already take. Plotting a frame whose columns are named differently no longer
  requires renaming it first.

### Added

- `TEXAS.constants.GDGT23RATIO_KEY` and `TEXAS.constants.NO3_KEY`.
  `OPTIONAL_PREDICTORS` is built from them, and `predict.py` and
  `ensemble/generator.py` now read the predictor keys from these instead of
  spelling the strings again.
- `TEXAS.utils.regrid.resolve_latlon_names`.
```

- [ ] **Step 13: Commit**

```bash
git add src/TEXAS tests CHANGELOG.md
git commit -m "refactor: one source of truth for predictor keys, grid axes and screening columns

predict.py and ensemble/generator.py read the predictor keys from constants;
ocean_lookup reuses regrid's lat/lon resolver instead of indexing da['lon'];
the five screening plot methods take the columns= map fit_predict already did.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 9 (OPTIONAL): `predict_T_from_df` — the DataFrame convenience

> **This task is optional.** Spec §9.7 marks it "Recommended addition (optional,
> small)". It is last because nothing before it depends on it: drop it and Tasks
> 1–8 are complete and coherent. Do not let it hold up the rest.

**Files:**
- Modify: `src/TEXAS/predict.py` (add `predict_T_from_df`; add the `pandas` import)
- Modify: `src/TEXAS/__init__.py` (import and `__all__`)
- Modify: `docs/api.md` (quick-reference row + autofunction block)
- Create: `tests/test_predict_from_df.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: Task 7's `predict_T_from_proxyObs` (no `constraint_type`, no `model_type`, percentile keys derived) and Task 5's guard, which this new export must satisfy — hence the tests below and the ≥ 3-line docstring.
- Produces: `TEXAS.predict_T_from_df(df, *, proxy_col, gdgt23ratio_col=None, no3_col=None, lat_col=None, lon_col=None, **kwargs) -> pd.DataFrame`.

**Design rule, from the spec:** column names are explicit keyword arguments with
**no defaults**. A user's `"lat"` versus `"Latitude"` is a one-word choice, never
a guess. Nothing is sniffed, and a missing column is an error naming both the
argument and the column it named.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_predict_from_df.py`:

```python
"""The DataFrame front door to the inverse API.

It maps named columns onto the array call and appends the result. It guesses
nothing: every column is named by an explicit keyword argument, and a name that
is not in the frame is an error, not a fallback.

The Stan run is monkeypatched out -- what is under test is the column mapping,
not the sampler.
"""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

import TEXAS
import TEXAS.predict as predict_mod


@pytest.fixture
def frame():
    return pd.DataFrame({
        "RI03": [0.30, 0.40, 0.50],
        "G23": [1.0, 2.0, 3.0],
        "nitrate": [0.2, 0.4, 0.6],
        "Latitude": [10.0, 11.0, 12.0],
        "Longitude": [-20.0, -21.0, -22.0],
        "depth_m": [100, 200, 300],
    })


@pytest.fixture
def captured(monkeypatch):
    """Replace the array API with a recorder that returns a fixed result."""
    seen = {}

    def fake(proxyObs, prior_mu_t=None, prior_sigma_t=None, **kwargs):
        seen["proxyObs"] = np.asarray(proxyObs)
        seen["prior_mu_t"] = prior_mu_t
        seen["prior_sigma_t"] = prior_sigma_t
        seen.update(kwargs)
        n = len(seen["proxyObs"])
        return {
            "proxyObs": seen["proxyObs"],
            "proxy_name": "scaledRI_cren3",
            "metadata": {},
            "p5": np.full(n, 15.0),
            "p50": np.full(n, 20.0),
            "p95": np.full(n, 25.0),
            "flags": pd.DataFrame({"any_flag": [False] * n,
                                   "outside_range": [False] * n}),
        }

    monkeypatch.setattr(predict_mod, "predict_T_from_proxyObs", fake)
    return seen


def test_appends_percentiles_and_flags_without_touching_the_input(frame, captured):
    out = TEXAS.predict_T_from_df(frame, proxy_col="RI03",
                                  prior_mu_t=20.0, prior_sigma_t=10.0)

    assert list(out.columns[:len(frame.columns)]) == list(frame.columns)
    for col in ("p5", "p50", "p95", "any_flag", "outside_range"):
        assert col in out.columns
    np.testing.assert_allclose(out["p50"], 20.0)
    assert "p50" not in frame.columns, "the caller's frame was mutated"
    pd.testing.assert_index_equal(out.index, frame.index)


def test_named_columns_reach_the_array_api(frame, captured):
    TEXAS.predict_T_from_df(frame, proxy_col="RI03", gdgt23ratio_col="G23",
                            no3_col="nitrate", prior_mu_t=20.0, prior_sigma_t=10.0)

    np.testing.assert_allclose(captured["proxyObs"], [0.30, 0.40, 0.50])
    np.testing.assert_allclose(captured["gdgt23ratio"], [1.0, 2.0, 3.0])
    np.testing.assert_allclose(captured["no3"], [0.2, 0.4, 0.6])


def test_lat_lon_columns_become_site_lat_site_lon(frame, captured):
    TEXAS.predict_T_from_df(frame, proxy_col="RI03", lat_col="Latitude",
                            lon_col="Longitude", prior_mu_t=20.0, prior_sigma_t=10.0)

    np.testing.assert_allclose(captured["site_lat"], [10.0, 11.0, 12.0])
    np.testing.assert_allclose(captured["site_lon"], [-20.0, -21.0, -22.0])


def test_kwargs_pass_straight_through(frame, captured):
    TEXAS.predict_T_from_df(frame, proxy_col="RI03", prior_mu_t=25.0,
                            prior_sigma_t=8.0, temptype="thermoT", seed=7)

    assert captured["prior_mu_t"] == 25.0
    assert captured["prior_sigma_t"] == 8.0
    assert captured["temptype"] == "thermoT"
    assert captured["seed"] == 7


def test_a_missing_column_names_the_argument_that_named_it(frame, captured):
    with pytest.raises(KeyError, match="gdgt23ratio_col"):
        TEXAS.predict_T_from_df(frame, proxy_col="RI03", gdgt23ratio_col="GDGT23",
                                prior_mu_t=20.0, prior_sigma_t=10.0)


def test_lat_without_lon_is_rejected(frame, captured):
    with pytest.raises(ValueError, match="lat_col and lon_col"):
        TEXAS.predict_T_from_df(frame, proxy_col="RI03", lat_col="Latitude",
                                prior_mu_t=20.0, prior_sigma_t=10.0)


def test_a_column_clash_is_refused_not_overwritten(captured):
    """Silently overwriting a user's p50 column would destroy their data."""
    df = pd.DataFrame({"RI03": [0.3, 0.4], "p50": [1.0, 2.0]})
    with pytest.raises(ValueError, match="p50"):
        TEXAS.predict_T_from_df(df, proxy_col="RI03",
                                prior_mu_t=20.0, prior_sigma_t=10.0)


def test_it_is_exported():
    assert "predict_T_from_df" in TEXAS.__all__
    assert callable(TEXAS.predict_T_from_df)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_predict_from_df.py -q`
Expected: every test fails with `AttributeError: module 'TEXAS' has no attribute 'predict_T_from_df'`.

- [ ] **Step 3: Implement it in `predict.py`**

Add `import pandas as pd` beside the numpy and xarray imports (pandas is already
a hard dependency — `data/screening.py` imports it at module scope and
`TEXAS/__init__.py` imports that). Then append, after `predict_T_from_proxyObs`:

```python
#: Percentile columns appended by :func:`predict_T_from_df`.
_DF_PERCENTILES = ("p5", "p50", "p95")


def predict_T_from_df(
    df: pd.DataFrame,
    *,
    proxy_col: str,
    gdgt23ratio_col: Optional[str] = None,
    no3_col: Optional[str] = None,
    lat_col: Optional[str] = None,
    lon_col: Optional[str] = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Reconstruct temperature for a whole DataFrame and append the result.

    A thin mapping from named columns onto :func:`predict_T_from_proxyObs`,
    which takes arrays. Every column is named by an explicit keyword argument
    with no default: whether your latitude column is ``"lat"`` or
    ``"Latitude"`` is a one-word choice here, never something this function
    guesses at.

    Args:
        df: The observations, one row each. Not modified.
        proxy_col: Column holding the proxy values, e.g. ``"scaledRI_cren3"``.
        gdgt23ratio_col: Column holding the GDGT-2/3 ratio, if the calibration
            uses it.
        no3_col: Column holding nitrate (umol/L), if the calibration uses it.
        lat_col: Column holding latitude, for the modern WOA23 NO3 lookup.
            Must be given together with *lon_col*.
        lon_col: Column holding longitude, for the same lookup.
        **kwargs: Forwarded to :func:`predict_T_from_proxyObs` -- above all
            ``prior_mu_t`` and ``prior_sigma_t``, which it requires.

    Returns:
        A copy of *df* with ``p5``, ``p50`` and ``p95`` appended, plus one
        column per quality flag when ``flags`` is left on.

    Raises:
        KeyError: if a named column is not in *df*. The message names both the
            argument and the column it named.
        ValueError: if only one of *lat_col* / *lon_col* is given, or if a
            column the result would append already exists in *df* -- appending
            over it would destroy data.

    Example:
        >>> out = predict_T_from_df(
        ...     core_df, proxy_col="scaledRI_cren3", gdgt23ratio_col="gdgt23ratio",
        ...     lat_col="Latitude", lon_col="Longitude",
        ...     prior_mu_t=25.0, prior_sigma_t=10.0)
        >>> out.loc[~out["any_flag"], ["depth_m", "p50"]]
    """
    named = [("proxy_col", proxy_col), ("gdgt23ratio_col", gdgt23ratio_col),
             ("no3_col", no3_col), ("lat_col", lat_col), ("lon_col", lon_col)]
    for argument, column in named:
        if column is not None and column not in df.columns:
            raise KeyError(
                f"{argument}={column!r} is not a column of the DataFrame. "
                f"Available columns: {list(df.columns)}"
            )

    if (lat_col is None) != (lon_col is None):
        raise ValueError(
            "lat_col and lon_col must be given together -- a WOA23 nitrate "
            "lookup needs both coordinates."
        )

    clashes = [c for c in _DF_PERCENTILES if c in df.columns]
    if clashes:
        raise ValueError(
            f"The DataFrame already has column(s) {clashes}, which this "
            "function would append over. Rename or drop them first; appending "
            "over them would destroy data."
        )

    call: Dict[str, Any] = dict(kwargs)
    if gdgt23ratio_col is not None:
        call["gdgt23ratio"] = df[gdgt23ratio_col].to_numpy(dtype=float)
    if no3_col is not None:
        call["no3"] = df[no3_col].to_numpy(dtype=float)
    if lat_col is not None:
        call["site_lat"] = df[lat_col].to_numpy(dtype=float)
        call["site_lon"] = df[lon_col].to_numpy(dtype=float)

    result = predict_T_from_proxyObs(df[proxy_col].to_numpy(dtype=float), **call)

    out = df.copy()
    for key in _DF_PERCENTILES:
        if key in result:
            out[key] = np.asarray(result[key])

    flags = result.get("flags")
    if flags is not None:
        overwritten = [c for c in flags.columns if c in out.columns]
        if overwritten:
            raise ValueError(
                f"The DataFrame already has flag column(s) {overwritten}. "
                "Rename or drop them, or call with flags=False."
            )
        for column in flags.columns:
            out[column] = flags[column].to_numpy()

    return out
```

- [ ] **Step 4: Export it**

In `src/TEXAS/__init__.py`, change line 26 to

```python
from .predict import (
    predict_proxy_from_T,
    predict_T_from_proxyObs,
    predict_T_from_df,
    compute_scaledRI,
)
```

and add `    "predict_T_from_df",` to `__all__` immediately after
`    "predict_T_from_proxyObs",`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_predict_from_df.py -q`
Expected: PASS, 8 tests.

Run: `pytest tests/test_public_api_docs.py -q`
Expected: PASS — the guard's three checks now cover `predict_T_from_df`, which
resolves, is referenced by `tests/test_predict_from_df.py`, and has a docstring
well over three lines.

- [ ] **Step 6: Add it to the API reference**

In `docs/api.md`, add a row to the quick-reference table immediately after the
`predict_T_from_proxyObs` row:

```markdown
| [`predict_T_from_df`](#predict-t-from-a-dataframe) | Inverse for a whole DataFrame: named columns in, `p5`/`p50`/`p95` and flags appended |
```

and, in the `## Prediction` section immediately after the
"Predict T from proxy observations" block:

```markdown
### Predict T from a DataFrame

```{eval-rst}
.. autofunction:: TEXAS.predict.predict_T_from_df
```
```

- [ ] **Step 7: Run the full suite, the linter and the docs build**

Run: `pytest -q` — expected the Task 8 total plus 8, no failures.
Run: `ruff check .` — expected `All checks passed!`.
Run: `jupyter-book build docs/` — expected no warning about the new anchor.

- [ ] **Step 8: Add the changelog line**

Under `### Added` in `CHANGELOG.md`:

```markdown
- `TEXAS.predict_T_from_df(df, *, proxy_col, gdgt23ratio_col=None, no3_col=None,
  lat_col=None, lon_col=None, **kwargs)` — the inverse reconstruction over a
  DataFrame, returning a copy with `p5`/`p50`/`p95` and the quality-flag columns
  appended. Column names are explicit keyword arguments with no defaults, so
  nothing is guessed; a name that is not in the frame raises, and a column the
  result would append over is refused rather than overwritten.
```

- [ ] **Step 9: Commit**

```bash
git add src/TEXAS/predict.py src/TEXAS/__init__.py tests/test_predict_from_df.py \
        docs/api.md CHANGELOG.md
git commit -m "feat: add predict_T_from_df, the DataFrame front door to the inverse

Column names are explicit keyword arguments with no defaults -- 'lat' vs
'Latitude' is the caller's one-word choice, never a guess. Refuses to append
over an existing p5/p50/p95 or flag column.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

## Final verification (run after the last task you executed)

1. `.venv/bin/python -m pytest -q` — green. Baseline was **351 passed, 11 skipped**; after all nine
   tasks it is that plus the tests each task added, minus the three guard
   parametrizations that left with `predict_temperature_from_proxyObs`.
2. `.venv/bin/python -m ruff check .` — `All checks passed!`, now including the `D1`
   missing-docstring rules over `src/TEXAS`.
3. **`.venv/bin/python -m build && unzip -l dist/*.whl | grep -c '\.stan$'` → 7.**
   The spec's §10 item 3 says **9**; the ARCHIVE decision on §9.8's last row
   moved `invT_gen_logi_fixed_univ_marginal_truncated_prior.stan` and
   `invT_gen_logi_fixed_multiv_marginal_truncated_prior.stan` out of
   `src/TEXAS/stan_models/` and into `archive/pre-submission/stan_models/`, so
   **7 is the correct value from here on**. The spec is deliberately left
   unedited — it records what was decided on 2026-09-07; this line is the
   correction. Also check `unzip -l dist/*.whl | grep truncated_prior` prints
   nothing.
4. `python docs/_scripts/build_callmap.py && jupyter-book build docs/` — both
   succeed, no warning about a missing file or unresolved cross-reference.
5. `python -c "import TEXAS; print(len(TEXAS.__all__))"` — 45 after Task 8
   (46 after Task 1's two removals, minus `predict_temperature_from_proxyObs`
   in Task 7), 46 if the optional Task 9 landed.
6. `grep -rn "predict_temperature_from_proxyObs" src tests scripts streamlit_app docs --include=*.py --include=*.md`
   → no output.
7. `git status --short` — clean; `streamlit_app/debug_imports.py` is deleted and
   the two `.stan` files show as renames, not as a delete plus an add.

## Self-review

Run against the spec with fresh eyes. Three checks; findings and their fixes
follow each.

**1. Spec coverage.**

| spec requirement | task |
|---|---|
| §9.6 delete 7 unused names | Task 1 deletes 6. `load_or_build_halo_cache` is plan 02's, and that is stated in "Notes carried from the spec" and again in Task 1's file list. |
| §9.6 four functions with no docstring | Task 2 (the three range helpers + `CaseName.describe`) |
| §9.6 ten thin docstrings | Task 3 (the ten, plus `InvTConfig` and `create_summary_table`, which the guard forces) |
| §9.6 five docstrings over 60 lines → ≤ 40 with narrative in `docs/` | Task 4 |
| §9.6 `tests/test_public_api_docs.py` guard | Task 5 |
| §9.6 ruff `D1xx` scoped to `src/TEXAS`, `D105`/`D107` ignored | Task 5 Step 5 |
| §9.6 five modules over 800 lines: noted, not acted on | Stated as out of scope in "Notes carried from the spec" |
| §9.7 fold layer 2 | Task 7 |
| §9.7 `_percentiles_from_posterior` deriving keys | Task 7 Step 3 |
| §9.7 `.npz` save moves into layer 1 behind `save_results=` | Task 7 Step 6 |
| §9.7 repoint four external callers, delete `debug_imports.py` | Task 7 Step 9 |
| §9.7 remove `use_opencl`, `scaledRI=`, `model_type`, `results_path`, `save`/`save_results`, the `None` trio | Task 7 Steps 5–8 |
| §9.7 column names 1/2/3 | Task 8 |
| §9.7 optional `predict_T_from_df` | Task 9, marked optional |
| §9.8 last row: ARCHIVE decision | Task 6 |

No gap found.

**2. Placeholder scan.** No "TBD", no "similar to Task N", no "add appropriate
error handling". Every code step carries the literal before-and-after text. Two
steps say "if ruff flags it, remove the name" (Task 6 Step 6, Task 7 Step 5)
about unused `typing` imports — that is a stated verification, not a deferred
decision, and both name the specific symbol at issue (`Literal`, `Any`).

**3. Type consistency.** Four discrepancies found on this pass and fixed inline
above:

- Task 7's guard test named the layer-1 seam `predict_mod._get_invT_posterior`,
  while Step 6's import line originally read
  `from .stan.invT import get_invT_posterior`. Fixed: the import is now
  `from .stan.invT import get_invT_posterior as _get_invT_posterior`, which is
  what `tests/test_invt_save.py::test_predict_T_from_proxyObs_writes_the_npz_itself`
  monkeypatches, and what the call block calls.
- `_percentiles_from_posterior`'s parameter is named `posterior` in the
  implementation (Task 7 Step 3) and the tests call it positionally, so the
  Interfaces block's `_percentiles_from_posterior(ds: ...)` shorthand was
  misleading. The signature everywhere that matters is positional; no test binds
  the name as a keyword.
- Task 6's `test_shipped_set_is_exactly_seven` renames the function
  `test_shipped_set_is_exactly_nine`, so the count claim and the test name agree.
  Any later reference to a "nine models" test would be stale — the final
  verification section and Task 6 Step 12 both say 7. Neither edits the spec:
  §10 item 3 still reads 9 and stays that way, because the spec records what was
  decided on 2026-09-07 rather than tracking the work.
- `_attach_invT_metadata` loses its `model_type` parameter in Task 7 Step 5, and
  `get_invT_posterior` stops overriding `ds.attrs["model_type"]`. Both edits are
  in the same step so the attr is written exactly once, by the helper, from the
  Stan filename. Recorded as a deliberate behaviour change: an archived
  non-marginal model run through `stan_model_path` will now be recorded as
  `model_type="ensemble"` rather than inheriting a caller's `"direct"` — which
  is the honest value, and it feeds `_generate_filename_base`'s trailing token.

One more consistency point worth stating rather than fixing: Task 4 writes
`constraint_type` and `min_temp` entries into the trimmed
`predict_T_from_proxyObs` docstring and Task 6 deletes them. That is intentional
— the two tasks are reviewed independently and neither should have to guess the
other's text — and it is called out in Task 4's "Ordering note" and Task 6's file
list.
