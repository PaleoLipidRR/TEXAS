# Kriged-Grid Cache Folder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the kriged residual-map grids their own cache subdirectory (`TEXAS_kriged_grids_cache/`) with one filename per grid, a dual-read fallback to the old location, and no dead halo-only cache API.

**Architecture:** `utils/paths.py` gains a third cache directory beside the two posterior directories, repointed by `set_cache_dir()` like the others. `plotting/residual_maps.py` builds its auto cache path through a new private `_auto_cache_path()` that reads `KRIGED_CACHE_DIR` at call time (so `set_cache_dir` works without a reimport) and formats the resolution with `:g`, so `krige_res=1` and `krige_res=1.0` name one file instead of two. `load_or_build_grids_cache()` reads the new location first and silently falls back to the same leaf in the legacy cache root, printing one line — the same never-fatal dual-read policy `load_posterior()` uses — and always *writes* to the new location. The dead `load_or_build_halo_cache()` goes; `krige_halo_all()` stays because `load_or_build_grids_cache()` calls it.

**Tech Stack:** Python ≥ 3.10, numpy, pytest, nbformat (notebook edit), matplotlib/cartopy/pykrige (optional map deps — not exercised by the tests).

**Spec:** `docs/superpowers/specs/2026-09-07-repo-finalization-design.md` (section **5b** only; verification item **9** of section 10)

## Global Constraints

- Python **>= 3.10** (`pyproject.toml` floor; the repo's conda env is 3.10).
- The repo uses **ultraplot**, not proplot (`import ultraplot as plot`). Never add a proplot import.
- **`data/cache/**` is gitignored and per-machine** — nothing under it travels with a clone. Never assume a cache migration done on one box has happened on another, and never commit a cache file.
- **pytest baseline is 351 passed / 11 skipped and must stay green.** Run it as `.venv/bin/python -m pytest -q` from the repo root. **The interpreter matters and is the usual cause of a wrong baseline.** Measured 2026-09-07:

  | interpreter | result |
  |---|---|
  | `.venv/bin/python` (uv-managed, editable TEXAS 0.3.2, numpy 2.4.6 / scipy 1.18.0) | **351 passed, 11 skipped** |
  | `python` (miniforge base, numpy 2.5.1 / scipy 1.11.4) | 11 collection errors, `ValueError: numpy.dtype size changed` |

  An earlier draft of this plan recorded `349 passed, 13 skipped` and treated the spec as wrong. It was not: that number came from a different interpreter. If you observe anything other than 351/11, check which Python you are running before concluding the suite has drifted.

  The `.venv` is uv-managed and has **no pip**. Install into it with `VIRTUAL_ENV=.venv uv pip install <pkg>`. `pytest` itself was installed this way on 2026-09-07; it is in the `dev` extra but was absent from the venv.
- **Run everything inside a full project environment.** `texas-env` exists but is stale (2026-04-22, pre-ultraplot: matplotlib 3.4.3, no `ultraplot`, no `arviz`) and cannot run the current notebooks. Task 0 of `2026-09-07-00-INDEX.md` builds a fresh one with `conda env create -f environment.yml -n texas-env-2026-09` — under a **new name**, because reusing `texas-env` collides with the stale one and the solver reports a misleading matplotlib conflict. That is a prerequisite for this plan's notebook steps. Until it exists, `.venv/bin/python` runs the test suite but **cannot** import `ultraplot`, `cartopy`, `pykrige`, `scikit-learn` or `arviz`, and has no `nbformat` or `nbconvert`, so Tasks 5 and 8 cannot run there. Do not substitute the miniforge base interpreter: it pairs numpy 2.5.1 with scipy 1.11.4 and fails collection on 11 test modules.
- The package must keep importing with only the core install: cartopy, pykrige, regionmask and joblib are all optional and already guarded in `residual_maps.py`. Do not add a hard import of any of them.
- This plan touches **section 5b only**. Do not touch the `sklearn.metrics.r2_score` import in `residual_maps.py` (that is spec §9.2), and do not move any file listed in §4.
- **Notebook edits are made with `nbformat`, on cell `source` only.** Executed outputs are a record of what ran and are left untouched.
- **Plan 03 edits the IMPORT cells of the same notebook** (`notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb`, spec §9.4). This plan edits cell 89's `plot_residual_maps(...)` call. The two plans must **not** be in flight at the same time — a concurrent `nbformat` write loses one side's edit wholesale. Finish and commit Task 5 here before starting plan 03's SI_code02 work (or vice versa).

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/TEXAS/utils/paths.py` | declares `KRIGED_CACHE_DIR`; `set_cache_dir()` repoints it | 1 |
| `tests/test_kriged_cache.py` (new) | pins the folder, the one-name-per-grid rule, the fallback, the write location, and the removed halo API | 1, 2, 3, 4 |
| `src/TEXAS/plotting/__init__.py` | drops the `load_or_build_halo_cache` import and `__all__` entry | 2 |
| `src/TEXAS/plotting/residual_maps.py` | deletes `load_or_build_halo_cache`; adds `_auto_cache_path` / `_legacy_grids_cache`; dual-read + mkdir in `load_or_build_grids_cache`; auto path in `plot_residual_maps` | 2, 3, 4 |
| `notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb` | cell 89 gains `temp_param` / `y_param` so fig9 caches | 5 |
| `scripts/migrate_kriged_cache.py` (new) | per-machine, dry-run-first cache migration | 6 |
| `RESUME.md` | one row in the "does not travel" table so Windows repeats the migration | 6 |
| `CLAUDE.md`, `docs/model_validation.md`, `docs/troubleshooting.md` | name the third cache folder | 7 |

---

### Task 1: `KRIGED_CACHE_DIR` in `utils/paths.py`

**Files:**
- Modify: `src/TEXAS/utils/paths.py` (module head; lines 197–241; `set_cache_dir` at 270–291)
- Create: `tests/test_kriged_cache.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `TEXAS.utils.paths.KRIGED_CACHE_DIR: Path` — module-level, `CACHE_ROOT / "TEXAS_kriged_grids_cache"`. Read it as `paths.KRIGED_CACHE_DIR` (module attribute), never `from ... import KRIGED_CACHE_DIR`, because `set_cache_dir()` rebinds the module attribute and a from-import would keep the stale value.
  - `set_cache_dir(path: str | Path) -> None` — unchanged signature; now also rebinds `KRIGED_CACHE_DIR`.
  - `tests/test_kriged_cache.py::cache_root` — a pytest fixture yielding a `tmp_path` that all three cache dirs point at, restoring the original root on teardown. Later tasks add tests to this file and reuse the fixture.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_kriged_cache.py`:

```python
"""Tests for the kriged-grid cache — its own folder under the cache root.

Kriged residual-map grids used to be written straight into the cache root, next
to the two posterior directories, under a filename whose resolution token came
from an unformatted f-string: ``krige_res=1`` and ``krige_res=1.0`` wrote two
57 MB copies of one grid. These tests pin the folder, the one-name-per-grid
rule, the dual-read fallback that keeps a not-yet-migrated machine working, and
the removal of the halo-only cache API.

No kriging happens here — the two grid builders are patched, because the real
thing takes minutes and needs pykrige.
"""
import numpy as np
import pytest

import TEXAS.plotting.residual_maps as rm
from TEXAS.utils import paths
from TEXAS.utils.paths import set_cache_dir


@pytest.fixture
def cache_root(tmp_path):
    """Point every TEXAS cache at a temp dir; put the real root back afterwards.

    Teardown goes back through ``set_cache_dir`` rather than restoring the
    attributes by hand, because that function also rebinds the module-level
    defaults inside ``TEXAS.stan.io``.
    """
    original = paths.CACHE_ROOT
    set_cache_dir(tmp_path)
    yield tmp_path
    set_cache_dir(original)


def test_kriged_dir_sits_beside_the_posterior_dirs():
    assert paths.KRIGED_CACHE_DIR.parent == paths.CACHE_ROOT
    assert paths.KRIGED_CACHE_DIR.name == "TEXAS_kriged_grids_cache"


def test_set_cache_dir_repoints_the_kriged_dir(cache_root):
    assert paths.KRIGED_CACHE_DIR == cache_root / "TEXAS_kriged_grids_cache"
    # The two it already handled must still move with it.
    assert paths.POSTERIOR_CACHE_DIR == cache_root / "TEXAS_posterior_cache"
    assert paths.INVT_CACHE_DIR == cache_root / "TEXAS_invT_posterior_cache"


def test_set_cache_dir_is_reversible(cache_root):
    """The fixture's teardown depends on this; assert it rather than assume it."""
    inner = cache_root / "nested"
    set_cache_dir(inner)
    assert paths.KRIGED_CACHE_DIR == inner / "TEXAS_kriged_grids_cache"
    set_cache_dir(cache_root)
    assert paths.KRIGED_CACHE_DIR == cache_root / "TEXAS_kriged_grids_cache"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_kriged_cache.py -v`
Expected: FAIL — `AttributeError: module 'TEXAS.utils.paths' has no attribute 'KRIGED_CACHE_DIR'`.

- [ ] **Step 3: Add the module docstring**

`src/TEXAS/utils/paths.py` currently begins with a bare comment and no docstring. Insert a docstring between the comment and `from __future__`:

```python
# TEXAS/utils/paths.py
"""Filesystem locations TEXAS reads and writes.

The cache root — ``TEXAS_CACHE_DIR`` if set, else ``<repo>/data/cache`` in a git
checkout, else ``~/.texas/cache`` — holds three subdirectories:

* ``TEXAS_posterior_cache/``      forward calibration posteriors (``.nc``)
* ``TEXAS_invT_posterior_cache/`` inverse temperature reconstructions (``.nc``)
* ``TEXAS_kriged_grids_cache/``   kriged residual-map grids (``.npz``)

``set_cache_dir()`` repoints all three at once.
"""

from __future__ import annotations
```

- [ ] **Step 4: Declare the directory and extend the priority comment**

Replace the cache-root comment block and the three assignments (lines ~197–241):

```python
# ── Cache root resolution ────────────────────────────────────────────────────
# Priority:
#   1. TEXAS_CACHE_DIR environment variable
#   2. data/cache/ inside the repo (when running from a git checkout)
#   3. ~/.texas/cache/ (pip-installed / Colab / no repo)
#
# Three subdirectories live under the root: TEXAS_posterior_cache/,
# TEXAS_invT_posterior_cache/ and TEXAS_kriged_grids_cache/.
```

and, further down:

```python
CACHE_ROOT = _resolve_cache_root()
CACHE_DIR = CACHE_ROOT          # backward-compat alias
POSTERIOR_CACHE_DIR = CACHE_ROOT / "TEXAS_posterior_cache"
INVT_CACHE_DIR      = CACHE_ROOT / "TEXAS_invT_posterior_cache"
# Kriged residual-map grids (.npz). Until 2026-09-07 these were written loose
# into CACHE_ROOT, alongside the two posterior directories; residual_maps.py
# still reads them from there as a fallback.
KRIGED_CACHE_DIR    = CACHE_ROOT / "TEXAS_kriged_grids_cache"
```

- [ ] **Step 5: Repoint it in `set_cache_dir`**

In `set_cache_dir`, update the docstring `Args` block and add the assignment:

```python
    Args:
        path: Root directory for all TEXAS caches.  Three subdirectories will
              be used inside it: ``TEXAS_posterior_cache/``,
              ``TEXAS_invT_posterior_cache/`` and
              ``TEXAS_kriged_grids_cache/``.
    """
    import TEXAS.utils.paths as _paths
    root = Path(path)
    _paths.CACHE_ROOT           = root
    _paths.CACHE_DIR            = root
    _paths.POSTERIOR_CACHE_DIR  = root / "TEXAS_posterior_cache"
    _paths.INVT_CACHE_DIR       = root / "TEXAS_invT_posterior_cache"
    _paths.KRIGED_CACHE_DIR     = root / "TEXAS_kriged_grids_cache"
```

(The `import TEXAS.stan.io` propagation block below it is unchanged — nothing in `stan/io.py` binds the kriged directory.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/test_kriged_cache.py -v`
Expected: 3 passed.

- [ ] **Step 7: Run the full suite**

Run: `pytest -q`
Expected: the baseline pass count plus 3, no new failures or skips.

- [ ] **Step 8: Commit**

```bash
git add src/TEXAS/utils/paths.py tests/test_kriged_cache.py
git commit -m "feat(paths): add KRIGED_CACHE_DIR as the third cache subdirectory

Kriged residual-map grids had no home of their own and landed loose in the
cache root. Declare TEXAS_kriged_grids_cache/ beside the two posterior dirs and
repoint it from set_cache_dir().

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 2: Delete the halo-only cache API

**Files:**
- Modify: `src/TEXAS/plotting/residual_maps.py:294-356` (delete `load_or_build_halo_cache`)
- Modify: `src/TEXAS/plotting/__init__.py:14,31`
- Test: `tests/test_kriged_cache.py`

**Interfaces:**
- Consumes: `tests/test_kriged_cache.py` from Task 1.
- Produces: `TEXAS.plotting.residual_maps.krige_halo_all(...)` **stays** and stays exported. `load_or_build_halo_cache` no longer exists anywhere.

**Zero-callers check — verified before writing this task.** Two greps over `src/ tests/ scripts/ streamlit_app/ notebooks/ archive/ README.md CLAUDE.md RESUME.md docs/*.md docs/tutorial/` (excluding the generated `docs/_static/callmap.html` and `docs/_build/`, which are build artefacts):

- `load_or_build_halo_cache` → **3 hits, all self-referential**: its own `def` at `residual_maps.py:294`, the import at `plotting/__init__.py:14`, the `__all__` entry at `plotting/__init__.py:31`. No notebook, test, script or doc page calls it. It is **not** re-exported from the top-level `TEXAS/__init__.py` (which imports only the four range helpers and `plot_prior_distributions` from `.plotting`), so this is not a top-level public-API removal.
- `krige_halo_all` → **6 hits**: its `def` at `residual_maps.py:189`, the two `plotting/__init__.py` lines, and three call sites — `residual_maps.py:346` (inside `load_or_build_halo_cache`, which is going away), `:409` (inside `load_or_build_grids_cache`, which stays) and `:801` (inside `plot_residual_maps`, which stays). **Keep it.**

The 15 `kriged_halo_*.npz` files this function wrote are the orphaned format Task 6 deletes.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_kriged_cache.py`:

```python
def test_the_halo_only_cache_api_is_gone():
    """Superseded by load_or_build_grids_cache, which caches halo AND true grids.

    ``load_or_build_halo_cache`` had zero callers and wrote a file format
    (``data_{i}``/``mask_{i}``, no true grids) that nothing reads any more.
    ``krige_halo_all`` is a different thing and must survive: the grids cache
    calls it.
    """
    import TEXAS.plotting as plotting

    assert not hasattr(rm, "load_or_build_halo_cache")
    assert not hasattr(plotting, "load_or_build_halo_cache")
    assert "load_or_build_halo_cache" not in plotting.__all__

    assert callable(rm.krige_halo_all)
    assert "krige_halo_all" in plotting.__all__
    assert callable(rm.load_or_build_grids_cache)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_kriged_cache.py::test_the_halo_only_cache_api_is_gone -v`
Expected: FAIL — `assert not hasattr(rm, "load_or_build_halo_cache")`.

- [ ] **Step 3: Delete the function**

In `src/TEXAS/plotting/residual_maps.py`, delete the whole block from `def load_or_build_halo_cache(` (line 294) through its final `return halo_grids` (line 356) — i.e. everything between `make_true_grid`'s closing `return np.ma.array(z, mask=~has_data)` and `def load_or_build_grids_cache(`. Leave exactly two blank lines between the two remaining functions.

Do **not** touch `krige_halo_all` (line 189) or `load_or_build_grids_cache` (line 359).

- [ ] **Step 4: Drop the two export lines**

`src/TEXAS/plotting/__init__.py` becomes:

```python
# TEXAS/plotting/__init__.py

from .range_utils import (
    compute_sample_range,
    compute_density_based_range,
    compute_suffix_specific_range,
    compute_dataset_specific_range,
)
from .prior_plot import plot_prior_distributions
from .residual_maps import (
    plot_residual_maps,
    krige_halo_all,
    make_true_grid,
    load_or_build_grids_cache,
)

# Deprecated alias — use plot_residual_maps instead
plot_proxy_residual_maps = plot_residual_maps

__all__ = [
    "compute_sample_range",
    "compute_density_based_range",
    "compute_suffix_specific_range",
    "compute_dataset_specific_range",
    "plot_prior_distributions",
    "plot_residual_maps",
    "plot_proxy_residual_maps",
    "krige_halo_all",
    "make_true_grid",
    "load_or_build_grids_cache",
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_kriged_cache.py -v`
Expected: 4 passed.

- [ ] **Step 6: Confirm no reference survives**

Run:
```bash
grep -rn "load_or_build_halo_cache" src/ tests/ scripts/ streamlit_app/ notebooks/ archive/ README.md CLAUDE.md RESUME.md docs/*.md docs/tutorial/
```
Expected: no output (exit 1).

- [ ] **Step 7: Run the full suite**

Run: `pytest -q`
Expected: baseline + 4, no new failures.

- [ ] **Step 8: Commit**

```bash
git add src/TEXAS/plotting/residual_maps.py src/TEXAS/plotting/__init__.py tests/test_kriged_cache.py
git commit -m "refactor(plotting): drop the dead halo-only grid cache

load_or_build_halo_cache had zero callers and wrote a superseded .npz format
(halo grids only, no true grids). krige_halo_all stays — load_or_build_grids_cache
and plot_residual_maps both call it.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 3: Auto cache path moves into `KRIGED_CACHE_DIR`, with `:g` resolution

**Files:**
- Modify: `src/TEXAS/plotting/residual_maps.py` (imports at the top; new helper after `make_true_grid`; `load_or_build_grids_cache` save block; `plot_residual_maps` docstring + auto-path block, currently lines 783–790)
- Test: `tests/test_kriged_cache.py`

**Interfaces:**
- Consumes: `TEXAS.utils.paths.KRIGED_CACHE_DIR` (Task 1); the `cache_root` fixture (Task 1).
- Produces:
  - `residual_maps._auto_cache_path(temp_param: str, y_param: str, residual_tag: str, krige_res: float = 1.0, max_dist_deg: float = 10.0) -> pathlib.Path` — the default cache location for one figure. Resolves `KRIGED_CACHE_DIR` at call time.
  - `residual_maps.load_or_build_grids_cache(...)` — unchanged signature; now creates the parent directory before saving.
  - `residual_maps._fake_grid` / `no_kriging` fixture in the test file, reused by Task 4.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_kriged_cache.py`:

```python
# ── Fixtures for the cache read/write tests ─────────────────────────────────
# Shapes are 3x4 rather than the real 180x360: nothing under test cares, and a
# small array keeps the .npz round-trip instant.

def _fake_grid(value):
    return np.ma.array(np.full((3, 4), float(value)), mask=np.zeros((3, 4), bool))


@pytest.fixture
def no_kriging(monkeypatch):
    """Replace the two grid builders — real kriging takes minutes and needs pykrige."""
    monkeypatch.setattr(
        rm, "krige_halo_all",
        lambda data, lons, lats, *a, **kw: [_fake_grid(10 + i) for i in range(len(data))],
    )
    monkeypatch.setattr(
        rm, "make_true_grid",
        lambda lons, lats, residuals, *a, **kw: _fake_grid(20),
    )


# One panel is enough: the cache format is per-index, not per-figure.
DATA = [(None, None, None, np.array([1.0, 2.0]), "blue9", "panel")]
LONS = np.array([0.0, 1.0])
LATS = np.array([0.0, 1.0])


# ── The auto path ───────────────────────────────────────────────────────────

def test_auto_path_lands_in_the_kriged_folder(cache_root):
    p = rm._auto_cache_path("SST", "scaledRI_cren3", "temp_residual", krige_res=1)
    assert p.parent == cache_root / "TEXAS_kriged_grids_cache"


@pytest.mark.parametrize("res", [1, 1.0])
def test_one_name_per_grid_whatever_the_resolution_literal(cache_root, res):
    """``1`` and ``1.0`` used to write two 57 MB copies of the same grid."""
    p = rm._auto_cache_path("SST", "scaledRI_cren3", "temp_residual", krige_res=res)
    assert p.name == (
        "kriged_grids_1deg_10dmax_woa23_SST_scaledRI_cren3_temp_residual.npz"
    )


def test_a_fractional_resolution_keeps_its_decimal(cache_root):
    p = rm._auto_cache_path("SST", "scaledRI_cren3", "temp_residual", krige_res=2.5)
    assert p.name.startswith("kriged_grids_2.5deg_")


def test_a_missing_cache_is_written_to_the_new_folder(cache_root, no_kriging):
    path = rm._auto_cache_path("SST", "scaledRI_cren3", "temp_residual", krige_res=1)
    assert not path.parent.exists()          # the folder does not exist yet

    halo, true = rm.load_or_build_grids_cache(
        str(path), DATA, LONS, LATS, recompute="auto",
    )

    assert path.exists()                     # written, and the folder was created
    assert len(halo) == 1 and len(true) == 1
    assert not (cache_root / path.name).exists()   # never the legacy root
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_kriged_cache.py -v`
Expected: the five new tests FAIL with `AttributeError: module 'TEXAS.plotting.residual_maps' has no attribute '_auto_cache_path'`.

- [ ] **Step 3: Add the `Path` import**

In `src/TEXAS/plotting/residual_maps.py`, after `import os`:

```python
import os
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union
```

- [ ] **Step 4: Add the auto-path helper**

Insert immediately after `make_true_grid` (i.e. where `load_or_build_halo_cache` used to be, before `def load_or_build_grids_cache`):

```python
def _auto_cache_path(
    temp_param: str,
    y_param: str,
    residual_tag: str,
    krige_res: float = 1.0,
    max_dist_deg: float = 10.0,
) -> Path:
    """Default location of the kriged-grids cache for one figure.

    The resolution is formatted with ``:g``, so ``krige_res=1`` and
    ``krige_res=1.0`` produce the same ``1deg`` token and ``2.5`` keeps its
    decimal. The unformatted f-string this replaces wrote ``1deg`` and
    ``1.0deg`` as two names for one 57 MB grid.

    ``KRIGED_CACHE_DIR`` is read from the module rather than from-imported so
    that :func:`TEXAS.set_cache_dir` takes effect without a reimport.

    Args:
        temp_param: Temperature column name, e.g. ``"SST"``.
        y_param: Proxy column name, e.g. ``"scaledRI_cren3"``.
        residual_tag: What kind of field is gridded, e.g. ``"temp_residual"``.
        krige_res: Halo grid resolution in degrees.
        max_dist_deg: Kriging search radius in degrees.

    Returns:
        Path to the ``.npz`` under ``TEXAS_kriged_grids_cache/``. The file need
        not exist.
    """
    from TEXAS.utils import paths as _paths

    leaf = (
        f"kriged_grids_{krige_res:g}deg_{int(max_dist_deg)}dmax_woa23_"
        f"{temp_param}_{y_param}_{residual_tag}.npz"
    )
    return _paths.KRIGED_CACHE_DIR / leaf
```

- [ ] **Step 5: Create the directory before saving**

In `load_or_build_grids_cache`, change the save block:

```python
    # Save both to cache
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        cache_path,
        **{f"halo_data_{i}": halo_grids[i].data for i in range(len(data))},
        **{f"halo_mask_{i}": halo_grids[i].mask for i in range(len(data))},
        **{f"true_data_{i}": true_grids[i].data for i in range(len(data))},
        **{f"true_mask_{i}": true_grids[i].mask for i in range(len(data))},
    )
    print(f"Saved grids cache → {cache_path}")
    return halo_grids, true_grids
```

- [ ] **Step 6: Route `plot_residual_maps` through the helper**

Replace the auto-path block (currently lines 783–790):

```python
    # ── Halo + True grids (cached) ──────────────────────────────────────────
    if cache_path is None and temp_param is not None and y_param is not None:
        cache_path = str(_auto_cache_path(
            temp_param, y_param, residual_tag,
            krige_res=krige_res, max_dist_deg=max_dist_deg,
        ))
        print(f"Auto cache path: {cache_path}")
```

(The `from TEXAS.utils.paths import CACHE_DIR` line and the local `_tag` variable go away with it.)

- [ ] **Step 7: Correct the `cache_path` docstring**

In `plot_residual_maps`'s docstring, replace the `cache_path` paragraph:

```
    cache_path : str, optional
        Explicit path to the .npz grids cache.  When omitted and both
        ``temp_param`` and ``y_param`` are set, auto-generated under
        ``data/cache/TEXAS_kriged_grids_cache/`` as
        ``kriged_grids_{res}deg_{dist}dmax_woa23_{temp_param}_{y_param}_{residual_tag}.npz``.
        The resolution token is formatted with ``:g``, so ``krige_res=1`` and
        ``krige_res=1.0`` name one file.  A cache left in the old location (the
        cache root, pre-2026-09-07) is still read, with a printed note.
        Caches both halo and true grids.
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `pytest tests/test_kriged_cache.py -v`
Expected: 9 passed.

- [ ] **Step 9: Run the full suite**

Run: `pytest -q`
Expected: baseline + 9, no new failures.

- [ ] **Step 10: Commit**

```bash
git add src/TEXAS/plotting/residual_maps.py tests/test_kriged_cache.py
git commit -m "feat(plotting): cache kriged grids in TEXAS_kriged_grids_cache/

The auto path moves out of the cache root into its own folder, the parent dir
is created before saving, and the resolution is formatted with :g so 1 and 1.0
no longer write two names for one grid.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 4: Dual-read fallback to the legacy cache root

**Files:**
- Modify: `src/TEXAS/plotting/residual_maps.py` (new `_legacy_grids_cache` helper; the load block of `load_or_build_grids_cache`)
- Test: `tests/test_kriged_cache.py`

**Interfaces:**
- Consumes: `_auto_cache_path` (Task 3); the `cache_root` and `no_kriging` fixtures and `DATA`/`LONS`/`LATS` (Tasks 1, 3).
- Produces: `residual_maps._legacy_grids_cache(cache_path: str | Path) -> pathlib.Path | None` — the same leaf in `CACHE_ROOT` if it exists there and `cache_path` is an auto path, else `None`.

**Policy this mirrors.** `stan/io.py::load_posterior` (lines 192–235) resolves a name against several layouts in order — exact paths first, attr-matching scan only as a fallback, bundled copy last — and each fallback is wrapped so that a failure to resolve is never fatal, it just moves on to the next candidate. The fallback here is the same shape: try the new path, fall back to the legacy leaf, and if neither is there behave exactly as before. Two differences are deliberate:

1. **It prints.** `load_posterior` is silent because both layouts are supported indefinitely; this one is a migration aid with a script behind it (Task 6), so the user is told where the file was found. The wording follows the module's own house style — `residual_maps.py` already prints `Loaded grids cache ← {path}` and `Saved grids cache → {path}`, so the new line uses the same `←` form.
2. **It never writes back.** Writes always go to `cache_path`, the new location. A fallback read leaves the legacy file where it is; Task 6's script is what moves it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_kriged_cache.py`:

```python
# ── The legacy-root fallback ────────────────────────────────────────────────

def _write_grids_npz(path, halo_value, true_value):
    """Write one panel's worth of the grids-cache format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        halo_data_0=np.full((3, 4), float(halo_value)),
        halo_mask_0=np.zeros((3, 4), bool),
        true_data_0=np.full((3, 4), float(true_value)),
        true_mask_0=np.zeros((3, 4), bool),
    )


def test_a_grid_left_in_the_legacy_cache_root_is_still_read(
    cache_root, no_kriging, capsys
):
    """Pre-2026-09-07 caches sit loose in the root; a Windows box may not be migrated."""
    path = rm._auto_cache_path("SST", "scaledRI_cren3", "temp_residual", krige_res=1)
    _write_grids_npz(cache_root / path.name, halo_value=7, true_value=8)

    # recompute=False raises if nothing is found, so a returned grid proves the
    # fallback fired rather than the compute branch.
    halo, true = rm.load_or_build_grids_cache(
        str(path), DATA, LONS, LATS, recompute=False,
    )

    assert halo[0].data[0, 0] == 7.0
    assert true[0].data[0, 0] == 8.0
    assert "legacy cache root" in capsys.readouterr().out
    assert not path.exists()          # a fallback read never copies or writes


def test_the_new_location_wins_over_the_legacy_one(cache_root, no_kriging):
    path = rm._auto_cache_path("SST", "scaledRI_cren3", "temp_residual", krige_res=1)
    _write_grids_npz(cache_root / path.name, halo_value=7, true_value=8)
    _write_grids_npz(path, halo_value=70, true_value=80)

    halo, true = rm.load_or_build_grids_cache(
        str(path), DATA, LONS, LATS, recompute=False,
    )

    assert halo[0].data[0, 0] == 70.0
    assert true[0].data[0, 0] == 80.0


def test_an_explicit_cache_path_gets_no_fallback(cache_root, no_kriging):
    """An explicit path is explicit — never silently redirected to the root."""
    explicit = cache_root / "elsewhere" / "my_grids.npz"
    _write_grids_npz(cache_root / "my_grids.npz", halo_value=7, true_value=8)

    with pytest.raises(FileNotFoundError):
        rm.load_or_build_grids_cache(
            str(explicit), DATA, LONS, LATS, recompute=False,
        )


def test_a_genuinely_missing_cache_still_raises(cache_root, no_kriging):
    path = rm._auto_cache_path("SST", "scaledRI_cren3", "temp_residual", krige_res=1)
    with pytest.raises(FileNotFoundError, match="TEXAS_kriged_grids_cache"):
        rm.load_or_build_grids_cache(str(path), DATA, LONS, LATS, recompute=False)


def test_recompute_true_ignores_the_legacy_file(cache_root, no_kriging):
    """recompute=True means re-krige and overwrite — at the NEW path."""
    path = rm._auto_cache_path("SST", "scaledRI_cren3", "temp_residual", krige_res=1)
    _write_grids_npz(cache_root / path.name, halo_value=7, true_value=8)

    halo, _ = rm.load_or_build_grids_cache(
        str(path), DATA, LONS, LATS, recompute=True,
    )

    assert halo[0].data[0, 0] == 10.0   # the patched builder, not the cached 7
    assert path.exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_kriged_cache.py -v`
Expected: `test_a_grid_left_in_the_legacy_cache_root_is_still_read` FAILS with `FileNotFoundError`; the rest of the new block may pass incidentally.

- [ ] **Step 3: Add the fallback resolver**

Insert directly after `_auto_cache_path` in `src/TEXAS/plotting/residual_maps.py`:

```python
def _legacy_grids_cache(cache_path: Union[str, Path]) -> Optional[Path]:
    """The same cache leaf in the legacy cache root, if it is sitting there.

    Kriged grids were written straight into ``CACHE_ROOT`` until 2026-09-07,
    next to the two posterior directories. Reading them from there keeps a
    machine whose files have not been moved yet working — the same never-fatal
    dual-read policy ``load_posterior`` uses for legacy posterior filenames.
    ``data/cache/**`` is gitignored, so this is genuinely per-machine:
    ``scripts/migrate_kriged_cache.py`` is what moves them.

    Only auto-generated paths get the fallback. An explicitly passed
    ``cache_path`` is taken at its word.

    Args:
        cache_path: The path that was asked for.

    Returns:
        The legacy path if it exists and ``cache_path`` is an auto path under
        ``KRIGED_CACHE_DIR``, otherwise ``None``. Nothing is ever written back
        to the old location.
    """
    from TEXAS.utils import paths as _paths

    p = Path(cache_path)
    if p.parent != _paths.KRIGED_CACHE_DIR:
        return None
    legacy = _paths.CACHE_ROOT / p.name
    return legacy if legacy.exists() else None
```

- [ ] **Step 4: Read through the fallback in `load_or_build_grids_cache`**

Replace the load block (the `if recompute != True:` stanza) with:

```python
    # Dual-read: prefer the new location, accept a grid still sitting loose in
    # the legacy cache root. Writes below always go to `cache_path`.
    read_path = Path(cache_path)
    if not read_path.exists():
        legacy = _legacy_grids_cache(cache_path)
        if legacy is not None:
            print(f"Loaded grids cache ← {legacy}  (legacy cache root; run "
                  f"scripts/migrate_kriged_cache.py to move it)")
            read_path = legacy

    if recompute != True:  # False or 'auto'
        if read_path.exists():
            cache = np.load(read_path)
            halo_grids = [
                np.ma.array(cache[f"halo_data_{i}"], mask=cache[f"halo_mask_{i}"])
                for i in range(len(data))
            ]
            true_grids = [
                np.ma.array(cache[f"true_data_{i}"], mask=cache[f"true_mask_{i}"])
                for i in range(len(data))
            ]
            print(f"Loaded grids cache ← {read_path}")
            return halo_grids, true_grids
        if recompute == False:
            raise FileNotFoundError(
                f"Cache not found at:\n  {cache_path}\n"
                "Pass recompute=True to generate it, or recompute='auto' to "
                "compute-and-cache automatically."
            )
        # recompute='auto' and cache missing — fall through to compute
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_kriged_cache.py -v`
Expected: 14 passed.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: baseline + 14, no new failures.

- [ ] **Step 7: Commit**

```bash
git add src/TEXAS/plotting/residual_maps.py tests/test_kriged_cache.py
git commit -m "feat(plotting): dual-read kriged grids from the legacy cache root

A grid still sitting loose in data/cache/ is loaded with a printed note instead
of being re-kriged, so a machine whose files have not been migrated keeps
working. Writes always go to the new folder; the fallback never copies.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 5: SI_code02 cell 89 gets its cache tags

**Files:**
- Modify: `notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb` (cell index **89**, the fig9 ±1σ uncertainty maps cell)

**Interfaces:**
- Consumes: `_auto_cache_path` behaviour from Task 3 — with `temp_param` and `y_param` set, `plot_residual_maps` builds `TEXAS_kriged_grids_cache/kriged_grids_1deg_10dmax_woa23_SST_scaledRI_cren3_uncertainty.npz`.
- Produces: nothing other tasks consume.

**Why.** Cell 89 passes `residual_tag='uncertainty'` but neither `temp_param` nor `y_param`, so `cache_path` stays `None`, the auto-path branch never fires, and the figure re-kriges four panels on every run. Cells 81 and 87 both pass all three and cache correctly. The cell already defines `temp_param = 'SST'` and `y_param = 'scaledRI_cren3'` as locals; the call uses **literals** so the cache name cannot drift if those variables are later reused.

**Scope note:** cell 90 is the `thermoT` twin of cell 89 and has the same gap. It is **not** in this spec section — leave it alone.

**Coordination:** see the Global Constraints — plan 03 rewrites this notebook's import cells. Do not run both at once.

- [ ] **Step 1: Confirm the target cell before touching it**

Run:
```bash
conda activate texas-env
python - <<'PY'
import nbformat
nb = nbformat.read("notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb", as_version=4)
src = nb.cells[89].source
assert nb.cells[89].cell_type == "code"
assert "FIGURE: ±1σ Uncertainty Maps" in src
assert "fig9_TEXAS_1sigma_uncertainty_maps" in src
assert src.count("plot_residual_maps(") == 2   # the import line + the call
i = src.index("fig, axs = plot_residual_maps(")
print(src[i:i+200])
PY
```
Expected output starts:
```
fig, axs = plot_residual_maps(
    data, lons, lats,
    residual_tag = 'uncertainty',
    recompute='auto',
```

- [ ] **Step 2: Apply the edit with nbformat**

Run:
```bash
python - <<'PY'
import nbformat

PATH = "notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb"
OLD = "    data, lons, lats,\n    residual_tag = 'uncertainty',\n"
NEW = ("    data, lons, lats,\n"
       "    temp_param      = \"SST\",\n"
       "    y_param         = \"scaledRI_cren3\",\n"
       "    residual_tag    = 'uncertainty',\n")

nb = nbformat.read(PATH, as_version=4)
cell = nb.cells[89]
assert cell.source.count(OLD) == 1, "cell 89 does not look as expected"
cell.source = cell.source.replace(OLD, NEW)
nbformat.write(nb, PATH)
print("cell 89 source updated; outputs untouched")
PY
```

- [ ] **Step 3: Verify only the one cell's source changed**

Run:
```bash
git diff --stat notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb
git diff notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb | grep -E '^[+-]' | grep -v '^[+-][+-]'
```
Expected: exactly one removed line (`residual_tag = 'uncertainty',`) and three added lines (`temp_param`, `y_param`, `residual_tag`). No `outputs`, `execution_count` or `metadata` lines in the diff. If the diff shows anything else, `git checkout --` the notebook and redo Step 2.

- [ ] **Step 4: Confirm the cache name the call will now produce**

Run:
```bash
python - <<'PY'
import TEXAS.plotting.residual_maps as rm
p = rm._auto_cache_path("SST", "scaledRI_cren3", "uncertainty", krige_res=1)
print(p)
assert p.name == "kriged_grids_1deg_10dmax_woa23_SST_scaledRI_cren3_uncertainty.npz"
assert p.parent.name == "TEXAS_kriged_grids_cache"
PY
```
Expected: the path prints and both asserts pass.

- [ ] **Step 5: Commit**

```bash
git add notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb
git commit -m "fix(SI_code02): let the fig9 uncertainty grid cache

Cell 89 passed residual_tag but no temp_param/y_param, so it never got an auto
cache path and re-kriged four panels on every run. Source only; outputs are the
record of what ran and are untouched.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 6: Per-machine cache migration (dry run, then confirm)

**Files:**
- Create: `scripts/migrate_kriged_cache.py`
- Modify: `RESUME.md` (the "What does NOT travel between machines" table, line ~1542)

**Interfaces:**
- Consumes: `TEXAS.utils.paths.CACHE_ROOT` and `KRIGED_CACHE_DIR` (Task 1).
- Produces: `python scripts/migrate_kriged_cache.py [--apply] [--delete-superseded] [--cache DIR]` — dry-run by default.

**What is on this machine right now** (`data/cache/`, measured 2026-09-07):

| item | count | size | fate |
|---|---|---|---|
| `kriged_grids_1deg_10dmax_woa23_{SST,t_sf2tc_avg}_scaledRI_cren3_temp_residual.npz` | 2 | 95 MB | **move** into `TEXAS_kriged_grids_cache/` |
| `kriged_grids_1.0deg_10dmax_woa23_SST_...npz` | 1 | 57 MB | delete (same grid as `1deg`, old unformatted token) |
| `kriged_grids_2.5deg_...npz` | 2 | 90 MB | delete (the 2.5° cells in SI_code02 are commented out) |
| `kriged_halo_*.npz` | **15** | 42 MB | delete (halo-only format, writer removed in Task 2) |
| `rebuttal_boundedT/run.log` | 1 dir | 217 B | delete (stray) |
| `data_list_extreme_example.pkl` | 1 | 0.1 MB | delete — see the resolution below |
| **total freed** | | **~189 MB** | |

The spec says "13 halo files"; the actual count on this machine is **15**. The script globs rather than hard-coding a count, so it is right on either box. Likewise the spec's "~185 MB" is ~189 MB here — report what the dry run prints, do not repeat the spec's figure.

**`data_list_extreme_example.pkl` — resolved, delete it.** CLAUDE.md's note about SI_code03 and `notebooks/manuscripts/` is about the *variant-suffixed* pickles, not this bare one. The notebook itself settles it:

- `SI_code03_paleo_showcases.ipynb` cell 14 sets `FWD_CACHE = Path(local_github_path) / "data/cache/TEXAS_posterior_cache"`, and its `extreme_pickle()` helper returns `FWD_CACHE / f'data_list_extreme_example_{variant}.pkl'` — the docstring there says *"Deliberately NOT the bare `data_list_extreme_example.pkl`"*.
- Cell 81 prints, when a variant file is missing: *"The bare data_list_extreme_example.pkl is NOT read as a fallback: it belongs to SI_code3 (the original submission) and holds pre-refit reconstructions, which would silently mix calibrations into fig14."*

So the path SI_code03 uses is `data/cache/TEXAS_posterior_cache/data_list_extreme_example_{t0shift,eiv}.pkl`, and the cache-**root** copy (`data/cache/data_list_extreme_example.pkl`) is read by nothing. Delete it. **Do not touch `data/cache/TEXAS_posterior_cache/data_list_extreme_example*.pkl`** — the two suffixed files are live and the bare one there is out of this plan's scope.

- [ ] **Step 1: Write the script**

Create `scripts/migrate_kriged_cache.py`:

```python
#!/usr/bin/env python
"""Move kriged-grid caches into TEXAS_kriged_grids_cache/ and drop the dead ones.

Until 2026-09-07 ``plot_residual_maps`` wrote its ``.npz`` grids straight into
the cache root, next to the two posterior directories. This moves the live
grids into their own folder and deletes four superseded sets:

* ``kriged_grids_1.0deg_*`` — the same grid as ``1deg`` under the old
  unformatted resolution token (the f-string had no ``:g``).
* ``kriged_grids_2.5deg_*`` — the 2.5° cells in SI_code02 are commented out.
* ``kriged_halo_*.npz`` — the halo-only cache format, written by
  ``load_or_build_halo_cache``, which had no callers and has been removed.
* ``rebuttal_boundedT/`` and the bare ``data_list_extreme_example.pkl`` —
  strays. SI_code03 reads the *variant-suffixed* pickles from
  ``TEXAS_posterior_cache/``, never this root copy; it says so in its own
  comments. Files under ``TEXAS_posterior_cache/`` are never touched here.

Everything deleted is regenerable: pass ``recompute='auto'`` to
``plot_residual_maps`` and it re-kriges.

THIS IS PER-MACHINE. ``data/cache/**`` is gitignored, so it does not travel
with a clone — run it on every box. See the "does not travel" table in
RESUME.md.

Usage
-----
    python scripts/migrate_kriged_cache.py                        # dry run
    python scripts/migrate_kriged_cache.py --apply                # move only
    python scripts/migrate_kriged_cache.py --apply --delete-superseded
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

LIVE_PREFIX = "kriged_grids_1deg_"
SUPERSEDED_PREFIXES = (
    "kriged_grids_1.0deg_",
    "kriged_grids_2.5deg_",
    "kriged_halo_",
)
STRAY_FILES = ("data_list_extreme_example.pkl",)
STRAY_DIRS = ("rebuttal_boundedT",)


def _mb(nbytes: int) -> str:
    return f"{nbytes / 1_000_000:.1f} MB"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--apply", action="store_true",
                    help="actually move the live grids")
    ap.add_argument("--delete-superseded", action="store_true",
                    help="also delete the superseded grids, halo caches and strays")
    ap.add_argument("--cache", type=Path, default=None,
                    help="cache root override (default: TEXAS's own)")
    args = ap.parse_args()

    from TEXAS.utils import paths

    root = args.cache if args.cache else paths.CACHE_ROOT
    dest = (args.cache / "TEXAS_kriged_grids_cache") if args.cache \
        else paths.KRIGED_CACHE_DIR

    if not root.is_dir():
        print(f"No cache root at {root} — nothing to do.")
        return 0

    moves = [(f, dest / f.name)
             for f in sorted(root.glob(f"{LIVE_PREFIX}*.npz")) if f.is_file()]

    doomed_files = [f
                    for prefix in SUPERSEDED_PREFIXES
                    for f in sorted(root.glob(f"{prefix}*.npz")) if f.is_file()]
    doomed_files += [root / n for n in STRAY_FILES if (root / n).is_file()]
    doomed_dirs = [root / n for n in STRAY_DIRS if (root / n).is_dir()]

    clashes = [(a, b) for a, b in moves if b.exists()]
    if clashes:
        print("REFUSING: destination already exists for")
        for a, b in clashes:
            print(f"   {a.name}  ->  {b}")
        return 1

    print(f"cache root : {root}")
    print(f"destination: {dest}\n")

    move_bytes = sum(a.stat().st_size for a, _ in moves)
    print(f"MOVE  ({len(moves)} file(s), {_mb(move_bytes)}):")
    for a, _ in moves:
        print(f"   {a.name}")

    del_bytes = sum(f.stat().st_size for f in doomed_files)
    print(f"\nDELETE ({len(doomed_files)} file(s) + {len(doomed_dirs)} dir(s), "
          f"{_mb(del_bytes)}):")
    for f in doomed_files:
        print(f"   {f.name}")
    for d in doomed_dirs:
        print(f"   {d.name}/")

    if not args.apply:
        print("\nDry run — nothing changed. Re-run with --apply to move, "
              "and add --delete-superseded to delete.")
        return 0

    dest.mkdir(parents=True, exist_ok=True)
    for a, b in moves:
        shutil.move(str(a), str(b))
        print(f"moved   {a.name}")

    if not args.delete_superseded:
        print("\nMoved. Nothing deleted — read the DELETE list above, then "
              "re-run with --apply --delete-superseded.")
        return 0

    for f in doomed_files:
        f.unlink()
        print(f"deleted {f.name}")
    for d in doomed_dirs:
        shutil.rmtree(d)
        print(f"deleted {d.name}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Dry run and read the plan**

Run:
```bash
conda activate texas-env
python scripts/migrate_kriged_cache.py
```
Expected: `MOVE (2 file(s), ~95 MB)` listing the two `kriged_grids_1deg_*` files, and `DELETE` listing 1 × `1.0deg`, 2 × `2.5deg`, 15 × `kriged_halo_*`, `data_list_extreme_example.pkl` and `rebuttal_boundedT/`. Nothing on disk changes.

- [ ] **Step 3: STOP — show the user the dry-run output and get explicit confirmation**

Paste the dry-run output and ask, in one line: *"Move the 2 live grids and delete these 19 items (~189 MB)? They are regenerable with `recompute='auto'`."* **Do not proceed to Step 4 without a "yes."** If the user says move-but-do-not-delete, run only `--apply` and stop there.

- [ ] **Step 4: Move the live grids**

Run:
```bash
python scripts/migrate_kriged_cache.py --apply
```
Expected: `moved   kriged_grids_1deg_..._SST_...npz` and `moved   kriged_grids_1deg_..._t_sf2tc_avg_...npz`, then the "Nothing deleted" notice.

- [ ] **Step 5: Verify the moved files are readable before deleting anything**

Run:
```bash
python - <<'PY'
import numpy as np
from TEXAS.utils import paths
for f in sorted(paths.KRIGED_CACHE_DIR.glob("*.npz")):
    with np.load(f) as z:
        print(f.name, sorted(z.files)[:2], "...", len(z.files), "arrays")
PY
```
Expected: both files list `halo_data_0`, `halo_mask_0`, … and open without error.

- [ ] **Step 6: Delete the superseded set (only after Step 3's confirmation)**

Run:
```bash
python scripts/migrate_kriged_cache.py --apply --delete-superseded
du -sh data/cache
ls data/cache
```
Expected: `data/cache` now contains only `TEXAS_posterior_cache/`, `TEXAS_invT_posterior_cache/` and `TEXAS_kriged_grids_cache/`.

- [ ] **Step 7: Add the RESUME.md row**

The table at `RESUME.md:1542` reads:

```markdown
**What does NOT travel between machines**, and what to do about it:

| Local-only | Consequence | Fix |
|---|---|---|
| `stash@{0}` (Phase 0 snapshot) | No safety stash elsewhere | Irrelevant once the branch is pushed — the commits are the backup |
| `backup/pre-merge-20260809` | No rollback point elsewhere | Pushed to origin; `git fetch` brings it down |
| Compiled Stan binaries | First sample recompiles (slow, once) | Nothing — expected, and platform-specific anyway |
| `data/cache/**` posteriors | Reconstructions cannot be loaded | `git lfs pull`, `TEXAS.download_posteriors()`, or re-run |
| CmdStan install | Nothing samples | `texas-install-cmdstan` |
```

Insert one row after the `data/cache/**` posteriors row:

```markdown
| Kriged grids loose in the `data/cache/` **root** (pre-2026-09-07 layout) | Read with a printed fallback note; ~189 MB of superseded `1.0deg`/`2.5deg`/`kriged_halo_*` files never get cleaned up | `python scripts/migrate_kriged_cache.py` (dry run), then `--apply --delete-superseded`. Repeat on the Windows box — `data/cache/**` is gitignored |
```

- [ ] **Step 8: Commit**

```bash
git add scripts/migrate_kriged_cache.py RESUME.md
git commit -m "chore(cache): add the per-machine kriged-cache migration

Dry-run-first script that moves the live 1deg grids into
TEXAS_kriged_grids_cache/ and deletes the superseded 1.0deg/2.5deg grids, the
halo-only caches and two strays. data/cache/** is gitignored, so RESUME.md's
'does not travel' table gains a row to have this repeated on Windows.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 7: Documentation

**Files:**
- Modify: `CLAUDE.md:162-171` ("Posterior caching")
- Modify: `docs/model_validation.md:64-70` (the "Spatially" bullet)
- Modify: `docs/troubleshooting.md` (append a new section at the end)

**Interfaces:**
- Consumes: `KRIGED_CACHE_DIR` (Task 1), `scripts/migrate_kriged_cache.py` (Task 6).
- Produces: nothing other tasks consume.

- [ ] **Step 1: CLAUDE.md**

The section currently reads:

```markdown
### Posterior caching

Posteriors are saved as compressed NetCDF (`.nc`) in:
- `data/cache/TEXAS_posterior_cache/` — forward calibration posteriors
- `data/cache/TEXAS_invT_posterior_cache/` — inverse temperature posteriors
```

Replace those five lines with:

```markdown
### Posterior caching

Posteriors are saved as compressed NetCDF (`.nc`) in:
- `data/cache/TEXAS_posterior_cache/` — forward calibration posteriors
- `data/cache/TEXAS_invT_posterior_cache/` — inverse temperature posteriors

A third sibling holds derived grids rather than posteriors:
- `data/cache/TEXAS_kriged_grids_cache/` — kriged residual-map grids (`.npz`),
  written by `plot_residual_maps`

> **Kriged grids got their own folder (2026-09-07)**: they used to be written
> loose into the cache **root**. `utils/paths.py` now declares
> `KRIGED_CACHE_DIR` beside the two posterior dirs and `set_cache_dir()`
> repoints all three. The resolution token is formatted with `f"{krige_res:g}"`,
> so `krige_res=1` and `krige_res=1.0` name one file — they used to write two
> 57 MB copies of one grid. A grid still sitting in the old location is loaded
> with a printed note (`_legacy_grids_cache`), so an un-migrated machine keeps
> working; writes always go to the new folder.
> **The migration is per-machine** — `data/cache/**` is gitignored:
> `python scripts/migrate_kriged_cache.py` (dry run), then
> `--apply --delete-superseded`.
> `load_or_build_halo_cache` and its halo-only `.npz` format were deleted in the
> same pass (zero callers); `krige_halo_all` stays — `load_or_build_grids_cache`
> and `plot_residual_maps` both call it.
```

- [ ] **Step 2: docs/model_validation.md**

The bullet at lines 64–70 reads:

```markdown
- **Spatially** — kriged residual maps (Fig. 9, Fig. S12–S13), rendered with
  `TEXAS.plotting.plot_residual_maps`. Regional residual patterns (e.g. the
  Mediterranean and Red Sea) shrink once the GDGT-2/3 and NO₃ corrections are
  applied, indicating the non-thermal terms capture a real ecological signal
  rather than overfitting noise.
```

Append two sentences to that bullet:

```markdown
- **Spatially** — kriged residual maps (Fig. 9, Fig. S12–S13), rendered with
  `TEXAS.plotting.plot_residual_maps`. Regional residual patterns (e.g. the
  Mediterranean and Red Sea) shrink once the GDGT-2/3 and NO₃ corrections are
  applied, indicating the non-thermal terms capture a real ecological signal
  rather than overfitting noise. Kriging six panels takes minutes, so the grids
  are cached as `.npz` under `data/cache/TEXAS_kriged_grids_cache/` and the
  figure re-renders in seconds. Pass `recompute='auto'` to build a grid that is
  not there yet, or `recompute=True` to force a re-krige.
```

- [ ] **Step 3: docs/troubleshooting.md**

The file has no cache section at all — it ends with the "compiler not found" entry:

```markdown
- **Windows:** `python -m cmdstanpy.install_cxx_toolchain` (installs the RTools
  MinGW toolchain), or use the conda-forge `cmdstan` package, which ships a pre-built
  compiler.
```

Append, after that last line:

```markdown

---

## Where TEXAS caches things, and what is safe to delete

**Symptom:** a figure or reconstruction spends minutes rebuilding something you
are sure you already computed, or `data/cache/` has grown to gigabytes and you
want to know what can go.

**Cause:** TEXAS keeps three caches under one root — `TEXAS_CACHE_DIR` if it is
set, otherwise `data/cache/` inside a git checkout, otherwise `~/.texas/cache/`:

| Directory | Holds | Rebuilt by |
|---|---|---|
| `TEXAS_posterior_cache/` | forward calibration posteriors (`.nc`) | `get_posterior()`, or `TEXAS.download_posteriors()` |
| `TEXAS_invT_posterior_cache/` | inverse temperature reconstructions (`.nc`) | `predict_T_from_proxyObs()` |
| `TEXAS_kriged_grids_cache/` | kriged residual-map grids (`.npz`) | `plot_residual_maps(..., recompute='auto')` |

**Fix:** all three are caches — deleting any file costs only the time to
recompute it. To move all three at once:

```python
import TEXAS
TEXAS.set_cache_dir("/big/disk/texas-cache")   # or export TEXAS_CACHE_DIR
```

**Kriged grids written before 2026-09-07** sit loose in the cache root instead
of in `TEXAS_kriged_grids_cache/`. They are still read from there, with a
printed note naming the old path. To tidy them up:

```bash
python scripts/migrate_kriged_cache.py                        # dry run
python scripts/migrate_kriged_cache.py --apply --delete-superseded
```

`data/cache/**` is gitignored, so this is per-machine — run it on each clone.
```

- [ ] **Step 4: Check the docs still build**

Run: `jupyter-book build docs/`
Expected: build succeeds; no new warnings about `model_validation.md` or `troubleshooting.md`.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/model_validation.md docs/troubleshooting.md
git commit -m "docs: name the third cache folder

CLAUDE.md's caching section, the residual-map bullet in model_validation.md,
and a new 'where TEXAS caches things' section in troubleshooting.md.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU"
```

---

### Task 8: Verification

**Files:** none modified — this task only runs checks.

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces: a pass/fail report. Nothing downstream.

This closes **spec §10 item 9**: *"SI_code02 cells 81 and 87 load their grids from `data/cache/TEXAS_kriged_grids_cache/` (the printed 'Auto cache path' line names the new folder and no re-kriging occurs)."*

- [ ] **Step 1: Full test suite**

Run:
```bash
# Whichever environment you built in Task 0 of the plan index:
.venv/bin/python -m pytest -q          # the uv venv, which exists today
# or, once `conda env create -f environment.yml` has been run:
#   conda activate texas-env && pytest -q
```
Expected: **351 passed, 11 skipped** from before Task 1, plus 14 new tests in `tests/test_kriged_cache.py`, so 365 passed and 11 skipped. No failures. No test that previously passed now skips.

- [ ] **Step 2: No dead references remain**

Run:
```bash
grep -rn "load_or_build_halo_cache" src/ tests/ scripts/ streamlit_app/ notebooks/ archive/ README.md CLAUDE.md RESUME.md docs/*.md docs/tutorial/
grep -rn "CACHE_DIR / f\"kriged_grids" src/
```
Expected: both print nothing (exit 1).

- [ ] **Step 3: The cache folder holds exactly the two live grids**

Run:
```bash
ls data/cache
ls -la data/cache/TEXAS_kriged_grids_cache/
```
Expected: `data/cache` lists only the three `TEXAS_*_cache` directories; the kriged folder holds `kriged_grids_1deg_10dmax_woa23_SST_scaledRI_cren3_temp_residual.npz` and `kriged_grids_1deg_10dmax_woa23_t_sf2tc_avg_scaledRI_cren3_temp_residual.npz`, and nothing else.

- [ ] **Step 4: Spec item 9 — cells 81 and 87 load, and do not re-krige**

The kriging in these two cells depends on `coretop_df` and `combined_datasets`, which are built earlier in the notebook, so run the notebook in place through cell 87 rather than trying to execute a cell in isolation:

```bash
jupyter nbconvert --to notebook --execute \
  --ExecutePreprocessor.timeout=3600 \
  --output /tmp/claude-1000/-home-ronnie-rattan-Documents-GitHub-TEXAS/68ae6f0f-4a75-4e97-a12d-d6e12fc1b02c/scratchpad/SI_code02_verify.ipynb \
  notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb
```

Then read the two cells' outputs out of the executed copy:

```bash
python - <<'PY'
import nbformat
p = ("/tmp/claude-1000/-home-ronnie-rattan-Documents-GitHub-TEXAS/"
     "68ae6f0f-4a75-4e97-a12d-d6e12fc1b02c/scratchpad/SI_code02_verify.ipynb")
nb = nbformat.read(p, as_version=4)
for idx in (81, 87, 89):
    text = "".join(
        o.get("text", "") for o in nb.cells[idx].get("outputs", [])
        if o.get("output_type") == "stream"
    )
    print("=" * 20, "cell", idx)
    for line in text.splitlines():
        if ("Auto cache path" in line or "grids cache" in line
                or "kriging" in line.lower()):
            print("  ", line)
PY
```

Expected for cells 81 and 87:
- an `Auto cache path: .../data/cache/TEXAS_kriged_grids_cache/kriged_grids_1deg_10dmax_woa23_..._temp_residual.npz` line naming the **new** folder,
- a `Loaded grids cache ← ...TEXAS_kriged_grids_cache/...` line,
- **no** `Parallel kriging:` / `Serial kriging ...` / `Saved grids cache →` lines, and no `legacy cache root` line (Task 6 moved the files).

Expected for cell 89 on this first post-change run: an `Auto cache path:` line ending `..._SST_scaledRI_cren3_uncertainty.npz`, kriging lines (the grid does not exist yet), and a `Saved grids cache →` line into the new folder. A second execution of cell 89 must then print `Loaded grids cache ←` and no kriging lines.

**If the notebook cannot be executed end-to-end** (missing training data, no CmdStan, cartopy unavailable), do not skip the check — report it as blocked, name the reason, and confirm the weaker property directly instead:

```bash
python - <<'PY'
import TEXAS.plotting.residual_maps as rm
from TEXAS.utils import paths
for tag, temp in (("temp_residual", "SST"), ("temp_residual", "t_sf2tc_avg"),
                  ("uncertainty", "SST")):
    p = rm._auto_cache_path(temp, "scaledRI_cren3", tag, krige_res=1)
    print(f"{'HIT ' if p.exists() else 'MISS'} {p}")
    assert p.parent == paths.KRIGED_CACHE_DIR
PY
```
Expected: the two `temp_residual` paths are `HIT` (moved by Task 6), the `uncertainty` path is `MISS` until cell 89 runs once.

- [ ] **Step 5: The dual-read fallback still works after migration**

Run:
```bash
python - <<'PY'
import numpy as np, TEXAS.plotting.residual_maps as rm
from TEXAS.utils import paths

new = rm._auto_cache_path("SST", "scaledRI_cren3", "temp_residual", krige_res=1)
legacy = paths.CACHE_ROOT / new.name
print("new exists   :", new.exists())
print("legacy exists:", legacy.exists(), "(expected False after migration)")
print("fallback for a missing new path:",
      rm._legacy_grids_cache(paths.KRIGED_CACHE_DIR / "nothing_here.npz"))
PY
```
Expected: `new exists: True`, `legacy exists: False`, fallback `None`.

- [ ] **Step 6: The docs build**

Run: `jupyter-book build docs/`
Expected: succeeds, no new missing-file warnings.

- [ ] **Step 7: Report**

Report to the user, in this order: the pytest counts before and after; the dry-run MOVE/DELETE totals and the megabytes actually freed; whether spec item 9 was confirmed by executing the notebook or by the weaker path check (and why); and anything left open.

---

## Self-Review

**1. Spec coverage (§5b, seven numbered design points + verification item 9):**

| spec point | task |
|---|---|
| 1. `KRIGED_CACHE_DIR` in `paths.py`, `set_cache_dir` sets it, docstring says "three subdirectories" | Task 1 (steps 3–5) |
| 2. auto path under `KRIGED_CACHE_DIR`, `mkdir(parents=True, exist_ok=True)`, `f"{krige_res:g}"` | Task 3 (steps 4–6) |
| 3. dual-read fallback with one printed line, mirroring `load_posterior` | Task 4 |
| 3b. delete `load_or_build_halo_cache` + the `plotting/__init__.py` export, keep `krige_halo_all` | Task 2 (zero-callers claim verified by grep, findings written into the task) |
| 4. SI_code02 cell 89 gains `temp_param` / `y_param` | Task 5 |
| 5. `tests/test_kriged_cache.py` — repointing, `1` vs `1.0`, fallback loads, new path used for writes, no real kriging | Tasks 1–4 (14 tests, all written out in full) |
| 6. per-machine migration + RESUME.md "does not travel" row | Task 6 |
| 7. CLAUDE.md + `docs/model_validation.md` + `docs/troubleshooting.md` | Task 7 |
| §10 item 9 verification | Task 8 (step 4) |
| open item: `data_list_extreme_example.pkl` | Task 6 — resolved to **delete the cache-root copy**, with the two notebook quotes that settle it |

No gaps.

**2. Placeholder scan:** every code step carries the literal code to write or the literal command to run. No "TBD", no "add error handling", no "similar to Task N" — Task 4's test file repeats the fixtures it needs by reference to the exact names Task 3 defines, and every helper Task 4 uses (`cache_root`, `no_kriging`, `DATA`, `LONS`, `LATS`) is spelled out in Task 1 or Task 3 in full. The pytest baseline is fixed at 351 passed / 11 skipped, verified 2026-09-07 in `.venv`; an earlier draft left it unfixed on the mistaken belief that the spec disagreed with this machine, which turned out to be an interpreter difference, not a drift.

**3. Type consistency:** `_auto_cache_path(temp_param, y_param, residual_tag, krige_res=1.0, max_dist_deg=10.0) -> Path` is defined in Task 3 and called with exactly that signature in Task 3's tests, Task 4's tests, Task 5 step 4, and Task 8 steps 4–5. `_legacy_grids_cache(cache_path) -> Path | None` is defined in Task 4 and called in Task 4's tests and Task 8 step 5. `KRIGED_CACHE_DIR` is read as a module attribute (`paths.KRIGED_CACHE_DIR`) everywhere — never from-imported — which is what makes `set_cache_dir` visible to it. `load_or_build_grids_cache`'s signature is unchanged throughout, so the notebook and `plot_residual_maps` need no adjustment beyond the auto-path block.

Two corrections made during this review and folded in above: the spec's "13 halo files" is **15** on this machine (the script globs, and Task 6 says so), and `docs/troubleshooting.md` has **no** existing cache section to amend, so Task 7 appends a new one rather than editing prose that does not exist.
