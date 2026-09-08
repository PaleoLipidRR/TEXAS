# Dependency Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every declared dependency of `texas-psm` match what the code actually imports — remove scikit-learn as a hidden core dependency, correct `pyproject.toml` and `environment.yml`, strip dead imports from the finalized notebooks, and regenerate both lockfiles.

**Architecture:** Three declaration-side files (`pyproject.toml`, `environment.yml`, `docker/Dockerfile`) plus two package source files (`plotting/residual_maps.py`, `data/screening.py`) and six notebooks are edited independently, each with its own test cycle. Nothing is rebuilt from the edited environment until the final lockfile task, so the working environment stays usable throughout. Notebook edits are made with `nbformat` on cell **source** only; executed outputs are a record of what ran and are never touched.

**Tech Stack:** Python ≥3.10, setuptools build backend, conda/conda-lock (canonical env), uv (PyPI-side lock), nbformat + jupyter nbconvert, ruff 0.9.7, pytest, Docker + micromamba.

**Spec:** `docs/superpowers/specs/2026-09-07-repo-finalization-design.md` (sections 9.2, 9.3, 9.4, 9.5, plus one line of 9.8)

## Global Constraints

- **Python `>=3.10`.** `pyproject.toml` sets `requires-python = ">=3.10"`; `environment.yml` pins `python=3.10`. Nothing here may raise or lower that floor.
- **conda is the canonical environment, and `conda-lock.yml` is what Docker builds from.** `docker/Dockerfile:22` runs `micromamba create -n texas-env -f conda-lock.yml`. A change to `environment.yml` reaches the image only after `conda-lock` regenerates `conda-lock.yml` (Task 10).
- **`uv.lock` IS tracked** (in `git ls-files`) since 2026-08-27, because the manuscript's Open Research statement promises it. It must be regenerated and committed, never deleted or gitignored. (The older CLAUDE.md/memory note saying `uv.lock` is gitignored is stale — trust `git ls-files`.)
- **`esmpy` is not on PyPI and must never appear in any pip extra.** One non-PyPI package in any extra makes `uv lock` fail for the *whole* project, because uv resolves every extra to build its universal lockfile. It stays a conda-only dependency in `environment.yml`.
- **The package uses `ultraplot`, never `proplot`.** `tests/test_environment_pins.py::test_proplot_is_gone` enforces this; `ultraplot>=2.4.0` must stay in both `pyproject.toml` and `environment.yml`.
- **Pytest baseline 351 passed / 11 skipped must stay green.** No test that passes before a task may fail after it. **Run it as `.venv/bin/python -m pytest -q` from the repo root.** The interpreter is the whole story here and an earlier draft of this plan got it wrong: `texas-env` exists but is stale (created 2026-04-22, before the proplot to ultraplot migration: matplotlib 3.4.3, no `ultraplot`, no `arviz`, no `jupyter-book`), so it cannot run the current notebooks either, and the miniforge base environment pairs numpy 2.5.1 with scipy 1.11.4, an ABI mismatch that makes 11 test modules fail collection outright with `ValueError: numpy.dtype size changed`. Measured 2026-09-07:

  | interpreter | `PROJ_DATA` set | result |
  |---|---|---|
  | `.venv/bin/python` | yes | **351 passed, 11 skipped** |
  | `.venv/bin/python` | no | **351 passed, 11 skipped** |
  | `python` (miniforge base) | yes | 11 collection errors |

  So `PROJ_DATA` / `PROJ_LIB` are **not** needed in `.venv`, and the 349/13 figure an earlier draft recorded came from a different interpreter, not from a real skip difference. The one place a conda environment is legitimately involved is Task 10, which builds a throwaway env to verify the regenerated lockfiles; PROJ variables may matter there and the task says so.

- **The `.venv` is uv-managed and has no pip.** Install into it with `VIRTUAL_ENV=.venv uv pip install <pkg>`. `pytest` itself was missing and was installed that way on 2026-09-07.
- **Notebook edits touch `cell.source` only.** Never edit, clear, or regenerate `cell.outputs` or `execution_count`. Executed outputs record what actually ran, including the old spellings, and that is correct.
- **Only one notebook-editing plan may be in flight at a time.** A separate plan (`02`) edits `SI_code02_t0shift_TEXAS_analysis.ipynb` **cell 89** (a non-import cell), and another plan may touch `SI_code00_PreProcessing.ipynb`. Notebook JSON does not merge. Confirm no other notebook plan is running before starting Tasks 4–9, and **re-read the notebook file immediately before editing it** in every notebook task.
- **Do not rebuild the conda environment from the edited `environment.yml` until Task 10.** Tasks 2 and 3 remove packages that Tasks 4–9 are still removing imports of; the rebuild is deliberately last.
- **Working tree:** spec §8 discards the dirty `SI_code00` / `SI_code02` notebooks (kernel-metadata churn plus a recorded `ModuleNotFoundError: sklearn`). That is another plan's step. If those files are still dirty when you reach their task, `git checkout --` them first — the diff carries no analysis.

## Preflight (do this once, before Task 1)

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git status --short
git checkout -b chore/dependency-audit

# Confirm the baseline. Expect exactly "351 passed, 11 skipped".
.venv/bin/python -m pytest -q --no-header 2>&1 | tail -2 | tee /tmp/pytest-baseline.txt
```

**If you see anything other than 351 passed / 11 skipped, check which Python you
are running before concluding the suite has drifted.** `python` on this machine
is miniforge base, whose numpy 2.5.1 / scipy 1.11.4 pairing fails collection on
11 modules. `.venv/bin/python` is the working interpreter and needs no
`PROJ_DATA` or `PROJ_LIB`.

## File Structure

| file | responsibility | task |
|---|---|---|
| `src/TEXAS/plotting/residual_maps.py` | map figures; owns the new `_r2_score` numpy helper | 1 |
| `src/TEXAS/data/screening.py` | Mahalanobis screening; owns the guarded `PCA` import | 1 |
| `tests/test_optional_deps.py` | proves the package imports and behaves with scikit-learn absent | 1 |
| `pyproject.toml` | PyPI-side dependency declaration | 2 |
| `docs/_config.yml`, `docs/installation.md` | docs that name the extras' contents | 2 |
| `tests/test_environment_pins.py` | regression guards on both declaration files | 2, 3 |
| `environment.yml` | conda-side dependency declaration (canonical) | 3 |
| `docker/Dockerfile` | hardcoded pip line layered on top of the conda env | 3 |
| `notebooks/manuscripts/SI_code00_PreProcessing.ipynb` | import cell 6 | 4 |
| `notebooks/manuscripts/SI_code01_t0shift_variance_partitioning.ipynb` | import cell 2 | 5 |
| `notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb` | cells 4, 42, 65, 83 | 6 |
| `notebooks/manuscripts/SI_code02a_model_param_sensitivity_test.ipynb` | cells 2, 3, 4, 43 | 7 |
| `notebooks/manuscripts/SI_code03_paleo_showcases.ipynb` | cells 2, 14 | 8 |
| `notebooks/quickstart_extended.ipynb` | cells 5, 9, 16, 50, 57 | 9 |
| `uv.lock`, `conda-lock.yml`, `conda-{linux-64,osx-64,osx-arm64,win-64}.lock` | regenerated artifacts | 10 |

`notebooks/quickstart_demo.ipynb` and
`notebooks/reviewer_response/SI_code04_model_comparison_cv.ipynb` need **no
changes** — both already report `All checks passed!` under
`ruff check --select F401`. They appear in spec §9.4's table with empty removal
columns; there is no task for them, by design.

---

### Task 1: Stop scikit-learn being a hidden core dependency

`plotting/residual_maps.py:775` does `from sklearn.metrics import r2_score`
inside `plot_residual_maps`, and `data/screening.py:1062` does `from
sklearn.decomposition import PCA` inside `plot_pca_projection`. Neither is
guarded, and scikit-learn is declared only in the `dev` extra — so
`pip install "texas-psm[maps]"` gives a package whose map figure crashes with a
bare `ModuleNotFoundError`. Replace the first (three lines of numpy), guard the
second.

**Files:**
- Modify: `src/TEXAS/plotting/residual_maps.py:73-77` (insert helper), `:745`, `:775`, `:826`, `:846`
- Modify: `src/TEXAS/data/screening.py:1061-1063`
- Test: `tests/test_optional_deps.py`

**Interfaces:**
- Produces: `TEXAS.plotting.residual_maps._r2_score(y_true, y_pred) -> float` —
  module-level, private. Accepts array-likes (numpy arrays, pandas Series,
  lists). Returns `1 - SS_res/SS_tot`; returns `float("nan")` when `y_true` has
  zero variance.
- Consumes: nothing from earlier tasks (this is the first task).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_optional_deps.py`:

```python
# ── scikit-learn must stay optional ───────────────────────────────────────────
# residual_maps used sklearn.metrics.r2_score and screening used
# sklearn.decomposition.PCA, both unguarded, while scikit-learn was declared
# only in the `dev` extra. See docs/superpowers/specs/2026-09-07-repo-finalization-design.md §9.2.

import subprocess
import sys

import numpy as np
import pandas as pd

_IMPORT_WITHOUT_SKLEARN = """
import sys


class _BlockSklearn:
    def find_spec(self, name, path=None, target=None):
        if name == "sklearn" or name.startswith("sklearn."):
            raise ImportError("scikit-learn is blocked for this test")
        return None


sys.meta_path.insert(0, _BlockSklearn())

import TEXAS                                    # noqa: F401
import TEXAS.plotting.residual_maps             # noqa: F401
import TEXAS.data.screening                     # noqa: F401

assert "sklearn" not in sys.modules, "something imported sklearn at module scope"
print("IMPORTED-WITHOUT-SKLEARN")
"""


def test_package_imports_with_scikit_learn_absent():
    """`import TEXAS` and both sklearn-touching modules load with sklearn blocked."""
    proc = subprocess.run(
        [sys.executable, "-c", _IMPORT_WITHOUT_SKLEARN],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "IMPORTED-WITHOUT-SKLEARN" in proc.stdout


def test_r2_score_matches_the_textbook_definition():
    """1 - SS_res/SS_tot, computed with numpy alone."""
    y_true = np.array([1.0, 2.0, 3.0, 4.0])
    y_pred = np.array([1.1, 1.9, 3.2, 3.7])
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    assert residual_maps._r2_score(y_true, y_pred) == pytest.approx(1 - ss_res / ss_tot)


def test_r2_score_agrees_with_sklearn_when_sklearn_is_installed():
    """Exact agreement on non-degenerate input, so the figures do not move."""
    sklearn_metrics = pytest.importorskip("sklearn.metrics")
    rng = np.random.default_rng(0)
    for n in (5, 50, 500):
        y_true = rng.normal(20.0, 5.0, n)
        y_pred = y_true + rng.normal(0.0, 2.0, n)
        assert residual_maps._r2_score(y_true, y_pred) == pytest.approx(
            sklearn_metrics.r2_score(y_true, y_pred), abs=1e-12
        )


def test_r2_score_is_nan_for_constant_truth():
    """No variance to explain -> undefined. (sklearn returns 0.0; we say NaN.)"""
    assert np.isnan(residual_maps._r2_score([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]))


def test_plot_pca_projection_names_scikit_learn_when_missing(monkeypatch):
    """A missing scikit-learn yields an ImportError that says how to fix it."""
    from TEXAS.data.screening import MahalanobisOutlierDetector

    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "TEX86": rng.uniform(0.3, 0.8, 50),
        "scaledRI_cren3": rng.uniform(0.2, 0.7, 50),
    })
    det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(df)

    # A None entry in sys.modules makes `from X import Y` raise ImportError.
    monkeypatch.setitem(sys.modules, "sklearn", None)
    monkeypatch.setitem(sys.modules, "sklearn.decomposition", None)

    with pytest.raises(ImportError, match="scikit-learn"):
        det.plot_pca_projection(df)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_optional_deps.py -q
```

Expected: the three `_r2_score` tests fail with
`AttributeError: module 'TEXAS.plotting.residual_maps' has no attribute '_r2_score'`,
and `test_plot_pca_projection_names_scikit_learn_when_missing` fails because the
raised `ImportError` message is `import of sklearn.decomposition halted; None in
sys.modules` — which does not contain "scikit-learn".
`test_package_imports_with_scikit_learn_absent` already passes (both sklearn
imports are function-local), and that is fine — it is the regression guard.

- [ ] **Step 3: Add the numpy R² helper**

In `src/TEXAS/plotting/residual_maps.py`, insert immediately after the joblib
guard (currently lines 72–76) and before the `# ── Grid parameters ──` banner:

```python
try:
    from joblib import Parallel, delayed
    _HAS_JOBLIB = True
except ImportError:
    _HAS_JOBLIB = False


def _r2_score(y_true, y_pred) -> float:
    """Coefficient of determination, ``R² = 1 - SS_res / SS_tot``.

    A numpy stand-in for ``sklearn.metrics.r2_score``, so the map figures do not
    make scikit-learn a hidden core dependency (it is declared only in the
    ``dev`` extra).

    Args:
        y_true: Observed values. Any array-like of floats.
        y_pred: Predicted values, same length as ``y_true``.

    Returns:
        The R² statistic. Matches ``sklearn.metrics.r2_score`` exactly for any
        input whose ``y_true`` has non-zero variance; returns NaN (where sklearn
        returns 0.0) when ``y_true`` is constant, because R² is undefined with no
        variance to explain. Callers here pass measured temperatures across many
        sites, which are never constant.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

```

- [ ] **Step 4: Drop the sklearn import and repoint the two call sites**

In `src/TEXAS/plotting/residual_maps.py`, delete line 775:

```python
    _require_cartopy()
    from sklearn.metrics import r2_score      # <- DELETE THIS LINE

    nrows = len(data)
```

becomes

```python
    _require_cartopy()

    nrows = len(data)
```

Then rename both uses (line 826 and line 846):

```python
            r2   = r2_score(meas_vals[idx], pred_vals[idx])
```
→
```python
            r2   = _r2_score(meas_vals[idx], pred_vals[idx])
```

and

```python
        return r2_score(meas, pred), np.sqrt(np.mean((meas - pred) ** 2))
```
→
```python
        return _r2_score(meas, pred), np.sqrt(np.mean((meas - pred) ** 2))
```

And the docstring reference on line 745:

```python
        Pre-computed metrics.  If None, auto-calculated via r2_score.
```
→
```python
        Pre-computed metrics.  If None, auto-calculated via _r2_score.
```

- [ ] **Step 5: Verify no bare `r2_score` remains**

```bash
grep -n "r2_score" src/TEXAS/plotting/residual_maps.py
```

Expected: exactly five hits, all `_r2_score` (the `def`, the docstring line 745,
and the two call sites), plus the helper's own docstring mention of
`sklearn.metrics.r2_score`. No line matching `from sklearn`.

```bash
grep -rn "^\s*from sklearn\|^\s*import sklearn" src/TEXAS/plotting/
```
Expected: no output.

- [ ] **Step 6: Guard the PCA import in screening.py**

In `src/TEXAS/data/screening.py`, replace lines 1061–1063:

```python
        # Fit PCA
        from sklearn.decomposition import PCA
        pca = PCA(n_components=n_components)
```

with:

```python
        # Fit PCA
        try:
            from sklearn.decomposition import PCA
        except ImportError as exc:  # pragma: no cover - exercised via sys.modules patch
            raise ImportError(
                "plot_pca_projection() requires scikit-learn, which TEXAS does not "
                "install by default. Install it with `pip install scikit-learn` or "
                "`pip install \"texas-psm[dev]\"`."
            ) from exc
        pca = PCA(n_components=n_components)
```

`# Fit PCA` occurs exactly once in the file, so that anchor is unique.

- [ ] **Step 7: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_optional_deps.py -q
```
Expected: all tests pass.

```bash
.venv/bin/python -m pytest -q --no-header 2>&1 | tail -2
```
Expected: the same pass/skip counts as `/tmp/pytest-baseline.txt`, plus the 5 new tests.

```bash
ruff check src/TEXAS/plotting/residual_maps.py src/TEXAS/data/screening.py
```
Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add src/TEXAS/plotting/residual_maps.py src/TEXAS/data/screening.py tests/test_optional_deps.py
git commit -m "$(cat <<'EOF'
fix: stop scikit-learn being a hidden core dependency

residual_maps imported sklearn.metrics.r2_score and screening imported
sklearn.decomposition.PCA, both unguarded, while scikit-learn was declared only
in the dev extra. Replace r2_score with a numpy _r2_score helper (exact
agreement on non-degenerate input) and guard the PCA import with an ImportError
that names scikit-learn.

Spec: docs/superpowers/specs/2026-09-07-repo-finalization-design.md §9.2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU
EOF
)"
```

---

### Task 2: Correct `pyproject.toml` and the docs that describe its extras

Spec §9.2's table, applied literally, plus the one line of §9.8 this plan owns.

**Files:**
- Modify: `pyproject.toml:18-31` (core), `:34-36` (plotting), `:40-44` (maps), `:46-68` (dev), `:70-81` (regrid), `:110-115` (`[tool.conda-lock.dependencies]`), `:117-123` (`[tool.uv]`)
- Modify: `docs/_config.yml:66`
- Modify: `docs/installation.md:399`, and (consequential — see Step 6) `:400`, `:402-403`, `:411`
- Test: `tests/test_environment_pins.py`

**Interfaces:**
- Consumes: nothing from Task 1 (independent).
- Produces: the extras `plotting = ["ultraplot>=2.4.0", "cmocean"]`,
  `maps = ["cartopy>=0.21", "regionmask>=0.9", "pykrige>=1.7", "joblib"]`,
  `regrid = ["xesmf"]`. Task 10 locks exactly these.

- [ ] **Step 1: Write the failing regression guards**

Append to `tests/test_environment_pins.py`:

```python
# ── pyproject dependency-audit guards (spec §9.2) ─────────────────────────────
# Each of these encodes a finding from the 2026-09-07 dependency audit. They are
# tests rather than comments because a dependency list drifts silently.

try:
    import tomllib                      # Python 3.11+
except ModuleNotFoundError:             # pragma: no cover - environment.yml pins python=3.10
    tomllib = None

# CI runs 3.11/3.12 so these always execute there; the conda env is 3.10.
needs_tomllib = pytest.mark.skipif(tomllib is None,
                                   reason="tomllib requires Python 3.11+")


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


@needs_tomllib
def test_core_deps_do_not_include_packages_the_package_never_imports():
    """cmocean and plotly are notebook/Streamlit deps, not core runtime deps."""
    core = " ".join(_pyproject()["project"]["dependencies"])
    assert "cmocean" not in core, "cmocean belongs in the `plotting` extra"
    assert "plotly" not in core, (
        "plotly is used only by streamlit_app/, which has its own "
        "requirements.streamlit.txt"
    )


@needs_tomllib
def test_plotting_extra_carries_cmocean():
    extras = _pyproject()["project"]["optional-dependencies"]
    assert any(d.startswith("cmocean") for d in extras["plotting"])


@needs_tomllib
def test_maps_extra_declares_joblib():
    """residual_maps.py:73 imports joblib; it used to arrive via scikit-learn."""
    extras = _pyproject()["project"]["optional-dependencies"]
    assert any(d.startswith("joblib") for d in extras["maps"])


@needs_tomllib
def test_dev_extra_has_no_unreferenced_packages():
    """anywidget/ipylab/duckdb/sqlalchemy/pydantic/statsmodels/odrpack are unused."""
    dev = _pyproject()["project"]["optional-dependencies"]["dev"]
    names = {d.split(">")[0].split("<")[0].split("=")[0].strip() for d in dev}
    for gone in ("anywidget", "ipylab", "duckdb", "sqlalchemy",
                 "pydantic", "statsmodels", "odrpack"):
        assert gone not in names, f"{gone} is back in the dev extra; nothing imports it"


@needs_tomllib
def test_dev_extra_keeps_the_implicit_pandas_backends():
    """pyarrow backs pd.read_parquet, openpyxl backs pd.read_excel."""
    dev = _pyproject()["project"]["optional-dependencies"]["dev"]
    names = {d.split(">")[0].split("<")[0].split("=")[0].strip() for d in dev}
    assert "pyarrow" in names and "openpyxl" in names


@needs_tomllib
def test_regrid_extra_is_just_xesmf():
    """utils/regrid.py imports only xesmf (+ esmpy at runtime, conda-only)."""
    extras = _pyproject()["project"]["optional-dependencies"]
    assert extras["regrid"] == ["xesmf"], extras["regrid"]


def test_no_pyproj_pin_and_no_uv_override_to_undo_it():
    """The `pyproj<3.6` cap and the [tool.uv] override that undid it both go."""
    text = PYPROJECT.read_text(encoding="utf-8")
    assert "pyproj<3.6" not in text
    assert "override-dependencies" not in text, (
        "the only override-dependencies entry existed to undo pyproj<3.6"
    )


@needs_tomllib
def test_no_extra_lists_esmpy():
    """esmpy is not on PyPI; one non-PyPI package in any extra breaks `uv lock`."""
    extras = _pyproject()["project"]["optional-dependencies"]
    for name, deps in extras.items():
        assert not any(d.startswith("esmpy") for d in deps), f"esmpy in [{name}]"
```

- [ ] **Step 2: Run them to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_environment_pins.py -q
```

Expected: 7 failures (`test_no_extra_lists_esmpy` already passes — it is a
standing guard, not a change).

- [ ] **Step 3: Edit `pyproject.toml`**

Core dependencies (lines 18–31) — drop `cmocean` and `plotly`:

```toml
dependencies = [
  "numpy>=1.18",
  "xarray>=0.16",
  "netcdf4","h5netcdf",   # xarray netCDF backend; required to read/write posterior .nc files
  "cmdstanpy>=1.0",
  "typing-extensions>=3.7.4",
  "scipy>=1.7",
  "pandas>=1.3",
  "stanio>=0.4",
  "matplotlib>=3.3",
  "psutil"
]
```

`plotting` (lines 34–36) — gains `cmocean`:

```toml
[project.optional-dependencies]
plotting = [
    "ultraplot>=2.4.0",
    "cmocean"          # colormaps used by the SI figure notebooks; TEXAS itself never imports it
]
```

`maps` (lines 40–44) — gains `joblib`:

```toml
maps = [
    "cartopy>=0.21",
    "regionmask>=0.9",
    "pykrige>=1.7",
    "joblib"           # residual_maps.py:73 parallelises halo kriging with it;
                       # it used to arrive transitively via scikit-learn
]
```

`dev` (lines 46–68) — drop `anywidget`, `ipylab`, `duckdb`, `sqlalchemy`,
`pydantic`, `odrpack`, `statsmodels`; keep `pyarrow`/`openpyxl` with the
explanatory comments the spec asks for:

```toml
dev = [
  "ipykernel",
  "pytest",
  "jupyter-book<2",
  "jupyterlab",
  "ipywidgets",
  "tqdm",
  "pyarrow",        # not imported directly: backs pd.read_parquet
                    # (data/.../PhanTEX_GIG_df.parquet, read by SI_code02)
  "openpyxl",       # not imported directly: backs pd.read_excel of the
                    # culture/mesocosm .xlsx dataset (SI_code00)
  "scikit-learn",   # SI_code00: LinearRegression; SI_code02: LinearRegression
  "seaborn",        # SI_code00/SI_code03 notebook plotting
  "baysparpy>=0.0.2",   # SI_code02/03: BAYSPAR TEX86 comparison (notebook-only; not used by TEXAS core)
  "baysplinepy>=0.0.1", # SI_code02/03: BAYSPLINE UK'37 comparison (notebook-only)
  "bayfox",
  "pygplates>=1.0"      # SI_code03: paleo plate reconstruction (pip-installable since 1.0; notebook-only)
]
```

`regrid` (lines 70–81) — reduced to `xesmf`; keep the esmpy NOTE beneath it:

```toml
regrid = [
  "xesmf"
]
# NOTE: esmpy (the ESMF Python bindings xesmf needs at *runtime* for regridding)
# is not published on PyPI — install it from conda-forge:
#   conda install -c conda-forge esmpy
# It is intentionally omitted here so pip/uv can resolve texas-psm and its
# extras. Listing a non-PyPI package in any extra makes `uv lock` fail for the
# whole project, since uv resolves every extra to build its universal lockfile.
```

`[tool.conda-lock.dependencies]` (lines 110–115) — drop `odrpack`:

```toml
[tool.conda-lock.dependencies]
pip = [
    "pygwalker",
    "regionmask"
]
```

`[tool.uv]` (lines 117–123) — delete the comment block **and** the table
entirely; it existed only to undo `pyproj<3.6`, which is now gone:

```toml
# uv-only build override. The `regrid` extra pins `pyproj<3.6` (last conda-friendly
# version), but 3.5.0 ships no cp312 wheel, so on Python 3.12 uv builds it from an
# sdist that needs the PROJ C library and fails. 3.6.1+ has cp312 wheels; this
# override lets uv download a wheel instead. Does not touch the published `regrid`
# constraint (conda still resolves pyproj via conda-forge).
[tool.uv]
override-dependencies = ["pyproj>=3.6.1"]
```
→ (delete all seven lines; `[tool.ruff]` now follows `[project.urls]` /
`[tool.conda-lock.dependencies]` directly)

- [ ] **Step 4: Drop odrpack from the docs autodoc mocks**

In `docs/_config.yml`, delete line 66 from `autodoc_mock_imports`:

```yaml
    autodoc_mock_imports:
      - cartopy
      - regionmask
      - pykrige
      - proplot
      - pygwalker
      - odrpack        # <- DELETE THIS LINE
```

- [ ] **Step 5: Fix the `dev` extra line in `docs/installation.md`** (the §9.8 line this plan owns)

Line 399:

```markdown
    - `uv sync --extra dev` — adds Jupyter/ipykernel + the notebook analysis deps (scikit-learn, statsmodels, seaborn, openpyxl, odrpack).
```
→
```markdown
    - `uv sync --extra dev` — adds Jupyter/ipykernel + the notebook analysis deps (scikit-learn, seaborn, openpyxl, pyarrow).
```

- [ ] **Step 6: Fix the three neighbouring lines this task's own edits falsify**

**Coordination note:** these three lines belong to spec §9.8, which a different
plan owns. They are included here because Step 3 is what makes them false — a
reader told the `regrid` extra installs geopandas, or that a `[tool.uv]`
override exists, would be reading a lie introduced by this task. If the §9.8
plan has already corrected them, verify the text matches and skip.

Line 400:

```markdown
    - `uv sync --all-extras` — the above **plus** plotting (ultraplot), maps (cartopy, regionmask), and regrid (geopandas, xesmf). Recommended for the SI notebooks.
```
→
```markdown
    - `uv sync --all-extras` — the above **plus** plotting (ultraplot, cmocean), maps (cartopy, regionmask, pykrige, joblib), and regrid (xesmf). Recommended for the SI notebooks.
```

Lines 402–403:

```markdown
!!! note "Python 3.12"
    uv on Python 3.12 is supported: the project pins a `[tool.uv]` override so `pyproj` resolves to a version with a 3.12 wheel (the `regrid` extra's `pyproj<3.6` cap has no 3.12 wheel and would otherwise force a source build). No action needed on your part.
```
→
```markdown
!!! note "Python 3.12"
    uv on Python 3.12 is supported with no special handling. Until 2026-09 the `regrid` extra pinned `pyproj<3.6`, which ships no cp312 wheel, and a `[tool.uv] override-dependencies` entry existed purely to undo that pin. `regrid` is now just `xesmf`, so both are gone.
```

Line 411:

```markdown
    - The `regrid` extra installs `xesmf` and the rest of the geo stack from PyPI, but **`esmpy` (the ESMF bindings xesmf needs at runtime) is not on PyPI** — install it from conda-forge: `conda install -c conda-forge esmpy`. (esmpy is deliberately kept out of the extra: a non-PyPI package in *any* extra makes `uv lock` fail for the whole project.) For heavy regridding, prefer the conda environment (Option D).
```
→
```markdown
    - The `regrid` extra installs `xesmf` from PyPI, but **`esmpy` (the ESMF bindings xesmf needs at runtime) is not on PyPI** — install it from conda-forge: `conda install -c conda-forge esmpy`. (esmpy is deliberately kept out of the extra: a non-PyPI package in *any* extra makes `uv lock` fail for the whole project.) For heavy regridding, prefer the conda environment (Option D). Without esmpy, `regrid_curvilinear_to_latlon` falls back to its pure-scipy backend.
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_environment_pins.py -q
```
Expected: all pass.

```bash
python -c "import tomllib,pathlib; tomllib.loads(pathlib.Path('pyproject.toml').read_text()); print('pyproject parses')"
python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('docs/_config.yml').read_text()); print('_config parses')"
grep -rn "odrpack" pyproject.toml docs/
```
Expected: `pyproject parses`, `_config parses`, and **no output** from the grep.

```bash
.venv/bin/python -m pytest -q --no-header 2>&1 | tail -2
```
Expected: baseline counts plus the new tests; no failures.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml docs/_config.yml docs/installation.md tests/test_environment_pins.py
git commit -m "$(cat <<'EOF'
chore: align pyproject extras with what the code actually imports

- core: drop cmocean (notebook-only) and plotly (streamlit_app-only)
- plotting: gains cmocean
- maps: gains joblib (residual_maps.py:73; used to ride in with scikit-learn)
- dev: drop anywidget, ipylab, duckdb, sqlalchemy, pydantic, statsmodels,
  odrpack -- nothing in the repo references them; keep pyarrow/openpyxl with
  comments naming pd.read_parquet / pd.read_excel
- regrid: reduced to ["xesmf"], the only thing utils/regrid.py imports; drops
  the pyproj<3.6 pin and the [tool.uv] override that existed only to undo it
- docs: odrpack removed from autodoc mocks and from the installation guide

Spec: docs/superpowers/specs/2026-09-07-repo-finalization-design.md §9.2, §9.8

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU
EOF
)"
```

---

### Task 3: Correct `environment.yml` and the Docker pip line

Spec §9.3. **`plotly` is removed** — evidence in Step 3.

**Files:**
- Modify: `environment.yml` (whole file)
- Modify: `docker/Dockerfile:25`
- Test: `tests/test_environment_pins.py`

**Interfaces:**
- Consumes: nothing from Tasks 1–2 (independent files).
- Produces: the `environment.yml` that Task 10 feeds to `conda-lock`.

- [ ] **Step 1: Write the failing regression guards**

Append to `tests/test_environment_pins.py`:

```python
# ── environment.yml dependency-audit guards (spec §9.3) ───────────────────────

_REMOVED_FROM_ENV = (
    "dask", "distributed", "zarr", "cftime", "gsw", "geopandas", "geopy",
    "pyogrio", "mapclassify", "rtree", "pyshp", "pyproj", "statsmodels",
    "odrpack", "importlib-metadata", "plotly",
)


def _dep_names() -> set[str]:
    """Bare package names from environment.yml -- comments and pins stripped.

    ``_dep_lines()`` keeps trailing ``# ...`` comments and version pins, which is
    what the matplotlib pin tests want. These tests want identity instead.
    """
    names = set()
    for dep in _dep_lines():
        name = dep.split("#", 1)[0].strip()
        name = re.split(r"[<>=!~]", name, maxsplit=1)[0].strip()
        if name:
            names.add(name)
    return names


def test_removed_conda_packages_stay_removed():
    """Nothing in src/, scripts/, streamlit_app/ or any notebook imports these."""
    names = _dep_names()
    for gone in _REMOVED_FROM_ENV:
        assert gone not in names, f"{gone} is back in environment.yml"


def test_psutil_is_declared_explicitly():
    """utils/system_info.py:12 imports psutil unguarded at module level."""
    assert "psutil" in _dep_names(), (
        "psutil must be explicit, not left to arrive via the pip texas-psm entry"
    )


def test_native_libs_behind_xesmf_and_netcdf_are_kept():
    names = _dep_names()
    for keep in ("esmf", "hdf5", "libnetcdf", "esmpy", "xesmf"):
        assert keep in names, f"{keep} was removed; xesmf/netCDF4 need it"


def test_esmpy_is_conda_only():
    """esmpy must be a conda dep and must never move into the pip: block."""
    text = ENV_YML.read_text(encoding="utf-8")
    conda_part, _, pip_part = text.partition("- pip:")
    assert "esmpy" in conda_part and "esmpy" not in pip_part
```

- [ ] **Step 2: Run them to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_environment_pins.py -q
```
Expected: `test_removed_conda_packages_stay_removed` and
`test_psutil_is_declared_explicitly` fail; the other two pass.

- [ ] **Step 3: Record the plotly decision in the plan's own terms, then act on it**

**Decision: remove `plotly` from `environment.yml`.** The Streamlit app is not
meant to run from `texas-env`. Evidence, all verified 2026-09-07:

1. `streamlit_app/requirements.streamlit.txt` declares its own stack, `plotly>=5.14` on line 9.
2. `docker/Dockerfile.streamlit` builds the app from `FROM python:3.11-slim`, `pip install -r requirements.txt`, then a plain `pip install /tmp/texas-pkg` — it never touches `conda-lock.yml` or `environment.yml`.
3. `docker/docker-compose.yml` wires the `app` service to `docker/Dockerfile.streamlit`; only the `full` service uses `docker/Dockerfile` (the conda image), and it runs JupyterLab, not Streamlit.
4. **`streamlit` itself is not in `environment.yml` at all** (`grep -n streamlit environment.yml` → no match). The conda env therefore cannot run `streamlit run main.py` regardless of plotly.
5. Only `streamlit_app/pages/calibration_data.py`, `streamlit_app/debug_imports.py`, and the SI_code02/03 import cells (removed by Tasks 6 and 8) mention plotly.

- [ ] **Step 4: Rewrite `environment.yml`**

Replace the whole file with:

```yaml
name: texas-env
channels:
  - conda-forge
channel_priority: strict

dependencies:
  # --- Core & Environment ---
  - python=3.10
  - pip
  - jupyterlab
  - ipywidgets
  - tqdm
  - ipykernel
  - psutil          # utils/system_info.py imports this unguarded at module level

  # --- Core Scientific Stack ---
  - numpy
  - pandas
  - openpyxl        # backs pd.read_excel (culture/mesocosm .xlsx, SI_code00)
  - scipy
  - scikit-learn    # SI_code00/SI_code02: LinearRegression
  - seaborn

  # --- Core Data Handling ---
  - xarray
  - netcdf4
  - h5netcdf

  # --- Plotting ---
  # NOTE: Multiple pins here increase solver complexity.
  # matplotlib was pinned <3.5 for proplot, which this project no longer uses.
  # ultraplot needs matplotlib >=3.9, so the old pin made it uninstallable:
  # the solver fell back to ultraplot 1.0, which then failed to import at all
  # (matplotlib.cm.ColormapRegistry arrived in 3.5). Unpinned 2026-08-27.
  - matplotlib>=3.9,<3.11
  - matplotlib-inline
  # setuptools<81: the reason for this cap was never recorded anywhere in the
  # repo or its history. Left in place deliberately (2026-09-07) -- lifting an
  # unexplained pin is its own change, with its own test.
  - setuptools<81
  - cmocean

  # --- Geo Stack (Complex Dependencies) ---
  - shapely
  - cartopy
  - pygplates

  # --- xESMF Stack (Complex Dependencies) ---
  - xesmf
  - esmpy           # NOT on PyPI; this is why it lives here and in no pip extra
  - esmf
  - hdf5
  - libnetcdf

  # --- Stan & Other Tools ---
  - cmdstan=2.36.0  # [unix]
  - cmdstanpy>=1.0
  - stanio
  - typing-extensions
  - pyarrow         # backs pd.read_parquet (PhanTEX_GIG_df.parquet, SI_code02)

  # --- Pip-only packages (conda-lock skips these if listed under conda) ---
  - pip:
    - ultraplot>=2.4.0      # keep in step with pyproject; <2.4 cannot import
    - pykrige
    - regionmask>=0.9
    - baysparpy>=0.0.2      # SI_code2/3: BAYSPAR TEX86 comparison
    - baysplinepy>=0.0.1    # SI_code2/3: BAYSPLINE UK'37 comparison
    - bayfox                # SI_code2/3: BAYFOX foram δ18O comparison
    - texas-psm>=0.3.2
```

Removed versus the previous file: `dask`, `distributed`, `zarr`, `cftime`,
`gsw`, `geopandas`, `pyproj`, `pyogrio`, `mapclassify`, `rtree`, `geopy`,
`pyshp=2.3.*`, `statsmodels`, `plotly`, `importlib-metadata<5.0`, and the pip
`odrpack`. Added: `psutil`. `shapely`'s stale `# NOTE: shapely<2 is a major
constraint.` comment is dropped with it — nothing in the file pins shapely.

- [ ] **Step 5: Drop odrpack from the Docker pip line**

`docker/Dockerfile` line 25 is the hardcoded pip line CLAUDE.md warns about. It
layers four PyPI packages onto the conda-lock environment:

```dockerfile
RUN micromamba run -n texas-env pip install --no-cache-dir pygwalker pykrige odrpack ultraplot
```

It holds **pygwalker, pykrige, odrpack, ultraplot**. `pykrige` and `ultraplot`
are also in `environment.yml`'s pip block, so they are already in the lock;
`pygwalker` and `odrpack` are here only. Remove `odrpack`:

```dockerfile
RUN micromamba run -n texas-env pip install --no-cache-dir pygwalker pykrige ultraplot
```

Leave `pygwalker` alone — it is not in this plan's scope and nothing in §9.2/§9.3
names it.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('environment.yml').read_text()); print('environment.yml parses')"
grep -rn "odrpack" environment.yml docker/
.venv/bin/python -m pytest tests/test_environment_pins.py -q
```
Expected: `environment.yml parses`, **no output** from the grep, all tests pass.

Do **not** run `conda env update` — Tasks 4–9 still need the packages you just
removed, and Task 10 owns the rebuild.

- [ ] **Step 7: Commit**

```bash
git add environment.yml docker/Dockerfile tests/test_environment_pins.py
git commit -m "$(cat <<'EOF'
chore: drop unimported packages from environment.yml; add psutil

Removed: dask, distributed, zarr, cftime, gsw, geopandas, geopy, pyogrio,
mapclassify, rtree, pyshp, pyproj (cartopy pulls its own), statsmodels, pip
odrpack, importlib-metadata<5.0 (the backport is unnecessary on Python >=3.8),
and plotly.

plotly goes because the Streamlit app never runs from this env: it builds from
python:3.11-slim via docker/Dockerfile.streamlit + requirements.streamlit.txt,
which declares plotly itself, and `streamlit` is not in environment.yml at all.

Kept esmf/hdf5/libnetcdf (native libs behind xesmf and netCDF4),
matplotlib-inline, and setuptools<81 -- whose reason was never recorded; the
comment now says so. Added psutil, which utils/system_info.py imports unguarded.
Dropped odrpack from the Dockerfile's hardcoded pip line to match.

Spec: docs/superpowers/specs/2026-09-07-repo-finalization-design.md §9.3

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU
EOF
)"
```

---

## Notebook tasks (4–9): shared method

Read this once; each task then stands alone.

**Before editing any notebook:**

```bash
git status --short notebooks/          # must be clean for the file you are about to edit
```

Re-read the notebook immediately before editing it. Another plan edits
`SI_code02` cell 89 and may edit `SI_code00`; notebook JSON does not merge, so a
stale read silently reverts someone else's work.

**The edit idiom** (`nbformat`, source only, asserted anchors). Every task gives
you a complete script — run it as written.

**Verification, the spec's (a)(b)(c).** `ruff` 0.9.7 is already installed;
`pyflakes` is not. `ruff --select F821` reports exactly the undefined names
pyflakes does, so it is the primary command; the literal pyflakes form is given
too (`pip install pyflakes` first, if you want it).

`get_ipython` and `display` are **injected by IPython into the notebook
namespace** and are legitimately undefined in an exported script. They are the
only names allowed to appear in the F821 output. Removing a
`from TEXAS.plotting import *` un-suppresses ruff's undefined-name analysis, so
F821 output can legitimately *grow* by `display` lines that were previously
masked by the star import — that is not a regression.

---

### Task 4: `SI_code00_PreProcessing.ipynb` import cleanup

Spec §9.4 row 1. All edits are in **cell 6**, the notebook's single import cell.

**Files:**
- Modify: `notebooks/manuscripts/SI_code00_PreProcessing.ipynb` (cell 6 source only)

**Interfaces:**
- Consumes: nothing (notebook tasks are independent of each other and of Tasks 1–3).
- Produces: nothing other tasks read.

- [ ] **Step 1: Capture the "before" state**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git status --short notebooks/manuscripts/SI_code00_PreProcessing.ipynb
SCRATCH=$(mktemp -d) && echo "$SCRATCH"
jupyter nbconvert --to script --output-dir="$SCRATCH" \
  notebooks/manuscripts/SI_code00_PreProcessing.ipynb
ruff check --isolated --select F401 --no-cache --output-format=concise \
  "$SCRATCH/SI_code00_PreProcessing.py" | tail -2
```
Expected before the edit: `Found 30 errors.` (30 F401 findings).

- [ ] **Step 2: Confirm nothing from `TEXAS.plotting` is used**

`TEXAS.plotting.__all__` is: `compute_sample_range`,
`compute_density_based_range`, `compute_suffix_specific_range`,
`compute_dataset_specific_range`, `plot_prior_distributions`,
`plot_residual_maps`, `plot_proxy_residual_maps`, `krige_halo_all`,
`make_true_grid`, `load_or_build_halo_cache`, `load_or_build_grids_cache`.

```bash
grep -cE "compute_sample_range|compute_density_based_range|compute_suffix_specific_range|compute_dataset_specific_range|plot_prior_distributions|plot_residual_maps|plot_proxy_residual_maps|krige_halo_all|make_true_grid|load_or_build_halo_cache|load_or_build_grids_cache" \
  "$SCRATCH/SI_code00_PreProcessing.py"
```
Expected: `0`. The star import is therefore deleted outright, not replaced.

- [ ] **Step 3: Apply the edit**

```bash
python - <<'PY'
import nbformat

NB = "notebooks/manuscripts/SI_code00_PreProcessing.ipynb"
nb = nbformat.read(NB, as_version=4)
cell = nb.cells[6]
assert cell.cell_type == "code", cell.cell_type
assert "import geopandas as gpd" in cell.source, "cell 6 is not the import cell"

REPLACEMENTS = [
    # entire modules, never used anywhere in the notebook
    ("from numpy.linalg import inv, LinAlgError, pinv\n", ""),
    ("import geopandas as gpd\n", ""),
    ("from scipy.spatial.distance import mahalanobis\n", ""),
    ("from scipy.stats import chi2\n", ""),
    ("from sklearn.neighbors import BallTree\n", ""),
    ("from odrpack import odr_fit\n", ""),
    ("import statsmodels.api as sm\n", ""),
    ("import matplotlib.colors as colors\n", ""),
    ("from geopy.distance import distance, Distance, lonlat\n", ""),
    ("import string\n", ""),
    ("import requests\n", ""),
    ("import io\n", ""),
    ("from tqdm import tqdm\n", ""),
    ("import time\n", ""),
    # names, never used
    ("from scipy.stats import pearsonr, spearmanr\n",
     "from scipy.stats import spearmanr\n"),
    ("from sklearn.linear_model import LinearRegression, RANSACRegressor, "
     "HuberRegressor, TheilSenRegressor\n",
     "from sklearn.linear_model import LinearRegression\n"),
    ("from matplotlib.patches import Rectangle, Patch\n",
     "from matplotlib.patches import Rectangle\n"),
    ("from shapely.geometry import Point, Polygon\n",
     "from shapely.geometry import Point\n"),
    # TEXAS names, never used
    ("from TEXAS.stan.compiler import StanCompiler\n", ""),
    ("from TEXAS.stan.sampler  import StanSampler\n", ""),
    ("from TEXAS.stan.io import load_posterior, save_posterior\n", ""),
    ("from TEXAS.models import predict_sst_from_tex86, predict_tex86_from_sst\n", ""),
    # star import: this notebook uses none of TEXAS.plotting's 11 exports
    ("from TEXAS.plotting import *\n", ""),
]

src = cell.source
for old, new in REPLACEMENTS:
    assert src.count(old) == 1, f"anchor not unique or not found: {old!r}"
    src = src.replace(old, new)
cell.source = src

nbformat.write(nb, NB)
print("SI_code00 cell 6 rewritten")
PY
```

- [ ] **Step 4 (a): zero unused imports**

```bash
SCRATCH2=$(mktemp -d)
jupyter nbconvert --to script --output-dir="$SCRATCH2" \
  notebooks/manuscripts/SI_code00_PreProcessing.ipynb
ruff check --isolated --select F401 --no-cache --output-format=concise \
  "$SCRATCH2/SI_code00_PreProcessing.py"
```
Expected: `All checks passed!`

- [ ] **Step 5 (c): no undefined names beyond the IPython builtins**

```bash
ruff check --isolated --select F821 --no-cache --output-format=concise \
  "$SCRATCH2/SI_code00_PreProcessing.py" \
  | grep -v "Undefined name \`get_ipython\`" \
  | grep -v "Undefined name \`display\`"
```
Expected: only the trailing `Found 15 errors.` summary line, nothing else.
(1 × `get_ipython` + 14 × `display`; `display` is IPython-injected and was
previously masked by the star import — spec §9.2 explicitly says "no change" for
`IPython.display`.)

The spec's literal form, if you install it:
```bash
pip install pyflakes
python -m pyflakes "$SCRATCH2/SI_code00_PreProcessing.py" | grep "undefined name" \
  | grep -vE "'get_ipython'|'display'"
```
Expected: no output.

- [ ] **Step 6 (b): the import cell executes cleanly**

```bash
python - <<'PY'
import nbformat
nb = nbformat.read("notebooks/manuscripts/SI_code00_PreProcessing.ipynb", as_version=4)
nb.cells = [nb.cells[6]]
nbformat.write(nb, "/tmp/imports_SI_code00.ipynb")
PY
jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 \
  --output /tmp/imports_SI_code00_out.ipynb /tmp/imports_SI_code00.ipynb
```
Expected: `[NbConvertApp] Writing ... /tmp/imports_SI_code00_out.ipynb`, no traceback.

- [ ] **Step 7: Confirm no outputs were disturbed**

```bash
git diff --stat notebooks/manuscripts/SI_code00_PreProcessing.ipynb
git diff notebooks/manuscripts/SI_code00_PreProcessing.ipynb | grep -c '"output_type"'
```
Expected: one file changed; the second command prints `0` (no output objects in the diff).

- [ ] **Step 8: Commit**

```bash
git add notebooks/manuscripts/SI_code00_PreProcessing.ipynb
git commit -m "$(cat <<'EOF'
chore(notebooks): remove dead imports from SI_code00 import cell

Drops geopandas, odrpack.odr_fit, statsmodels, geopy, requests, tqdm, string,
io, time; the unused numpy/scipy/sklearn/matplotlib/shapely names; and the four
unused TEXAS imports. `from TEXAS.plotting import *` is deleted rather than
narrowed -- the notebook uses none of that module's 11 exports.

Source cells only; executed outputs untouched.
Spec: docs/superpowers/specs/2026-09-07-repo-finalization-design.md §9.4

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU
EOF
)"
```

---

### Task 5: `SI_code01_t0shift_variance_partitioning.ipynb` import cleanup

Spec §9.4 row 2 — a single unused name.

**Files:**
- Modify: `notebooks/manuscripts/SI_code01_t0shift_variance_partitioning.ipynb` (cell 2 source only)

**Interfaces:**
- Consumes: nothing. Produces: nothing other tasks read.

- [ ] **Step 1: Capture the "before" state**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git status --short notebooks/manuscripts/SI_code01_t0shift_variance_partitioning.ipynb
SCRATCH=$(mktemp -d)
jupyter nbconvert --to script --output-dir="$SCRATCH" \
  notebooks/manuscripts/SI_code01_t0shift_variance_partitioning.ipynb
ruff check --isolated --select F401 --no-cache --output-format=concise \
  "$SCRATCH/SI_code01_t0shift_variance_partitioning.py"
```
Expected: exactly one finding —
`...:56:25: F401 [*] \`scipy.stats.spearmanr\` imported but unused`.

- [ ] **Step 2: Apply the edit**

```bash
python - <<'PY'
import nbformat

NB = "notebooks/manuscripts/SI_code01_t0shift_variance_partitioning.ipynb"
nb = nbformat.read(NB, as_version=4)
cell = nb.cells[2]
assert cell.cell_type == "code", cell.cell_type
assert "from scipy.odr import ODR, Model, RealData" in cell.source, "cell 2 is not the import cell"

old = "from scipy.stats import spearmanr\n"
assert cell.source.count(old) == 1, "anchor not unique or not found"
cell.source = cell.source.replace(old, "")

nbformat.write(nb, NB)
print("SI_code01 cell 2 rewritten")
PY
```

- [ ] **Step 3 (a): zero unused imports**

```bash
SCRATCH2=$(mktemp -d)
jupyter nbconvert --to script --output-dir="$SCRATCH2" \
  notebooks/manuscripts/SI_code01_t0shift_variance_partitioning.ipynb
ruff check --isolated --select F401 --no-cache --output-format=concise \
  "$SCRATCH2/SI_code01_t0shift_variance_partitioning.py"
```
Expected: `All checks passed!`

- [ ] **Step 4 (c): no undefined names**

```bash
ruff check --isolated --select F821 --no-cache --output-format=concise \
  "$SCRATCH2/SI_code01_t0shift_variance_partitioning.py"
```
Expected: `All checks passed!` (this notebook has no `get_ipython` or `display` uses).

- [ ] **Step 5 (b): the import cell executes cleanly**

```bash
python - <<'PY'
import nbformat
nb = nbformat.read("notebooks/manuscripts/SI_code01_t0shift_variance_partitioning.ipynb", as_version=4)
nb.cells = [nb.cells[2]]
nbformat.write(nb, "/tmp/imports_SI_code01.ipynb")
PY
jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 \
  --output /tmp/imports_SI_code01_out.ipynb /tmp/imports_SI_code01.ipynb
```
Expected: written, no traceback.

- [ ] **Step 6: Confirm no outputs were disturbed**

```bash
git diff notebooks/manuscripts/SI_code01_t0shift_variance_partitioning.ipynb | grep -c '"output_type"'
```
Expected: `0`.

- [ ] **Step 7: Commit**

```bash
git add notebooks/manuscripts/SI_code01_t0shift_variance_partitioning.ipynb
git commit -m "$(cat <<'EOF'
chore(notebooks): drop unused scipy.stats.spearmanr from SI_code01

Source cell only; executed outputs untouched.
Spec: docs/superpowers/specs/2026-09-07-repo-finalization-design.md §9.4

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU
EOF
)"
```

---

### Task 6: `SI_code02_t0shift_TEXAS_analysis.ipynb` import cleanup

Spec §9.4 row 3. Cell 4 is the import cell; cells 42, 65 and 83 each carry one
unused *inline* import that §9.4 also lists (`sklearn.utils.resample`, and two
of the three `matplotlib.pyplot as plt` bindings). All three `plt` bindings go —
`grep -c '\bplt\.' ` on the exported script returns **0**; this notebook plots
with `ultraplot`, not pyplot.

> **Conflict warning.** A separate plan (`02`) edits **cell 89** of this
> notebook. Cell 89 is not touched here. Do not run both plans concurrently, and
> re-read the file immediately before editing.

**Files:**
- Modify: `notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb` (cells 4, 42, 65, 83 — source only)

**Interfaces:**
- Consumes: nothing. Produces: nothing other tasks read.

- [ ] **Step 1: Capture the "before" state**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git status --short notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb
SCRATCH=$(mktemp -d)
jupyter nbconvert --to script --output-dir="$SCRATCH" \
  notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb
ruff check --isolated --select F401 --no-cache --output-format=concise \
  "$SCRATCH/SI_code02_t0shift_TEXAS_analysis.py" | tail -2
grep -c '\bplt\.' "$SCRATCH/SI_code02_t0shift_TEXAS_analysis.py"
```
Expected: `Found 40 errors.` from ruff (F401 only), and `0` from the grep —
confirming pyplot is genuinely unused before you remove it.

- [ ] **Step 2: Decide the `TEXAS.plotting` replacement list**

```bash
grep -oE "compute_sample_range|compute_density_based_range|compute_suffix_specific_range|compute_dataset_specific_range|plot_prior_distributions|plot_residual_maps|plot_proxy_residual_maps|krige_halo_all|make_true_grid|load_or_build_halo_cache|load_or_build_grids_cache" \
  "$SCRATCH/SI_code02_t0shift_TEXAS_analysis.py" | sort | uniq -c
```
Expected: `4 plot_prior_distributions` and `12 plot_residual_maps`, nothing else.
The star import therefore becomes
`from TEXAS.plotting import plot_prior_distributions, plot_residual_maps`.

- [ ] **Step 3: Apply the edits**

```bash
python - <<'PY'
import nbformat

NB = "notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb"
nb = nbformat.read(NB, as_version=4)

# ── cell 4: the import cell ───────────────────────────────────────────────────
cell = nb.cells[4]
assert cell.cell_type == "code", cell.cell_type
assert "from pykrige.ok import OrdinaryKriging" in cell.source, "cell 4 is not the import cell"

CELL4 = [
    # entire modules, never used
    ("from pykrige.ok import OrdinaryKriging\n", ""),
    ("import cmocean.cm as cmo\n", ""),
    ("import seaborn as sns\n", ""),
    ("import plotly.graph_objects as go\n", ""),
    ("import plotly.express as px\n", ""),
    ("from plotly.subplots import make_subplots\n", ""),
    ("from ipywidgets import FloatRangeSlider, VBox\n", ""),
    ("from geopy.distance import distance, Distance, lonlat\n", ""),
    ("import bayspline as bsl\n", ""),
    ("from functools import partial\n", ""),
    ("import requests\n", ""),
    ("import string\n", ""),
    ("import io\n", ""),
    ("import time\n", ""),
    # names, never used
    ("from scipy import stats\n", ""),
    ("from scipy.optimize import curve_fit\n", ""),
    ("from scipy.stats import pearsonr, spearmanr, truncnorm\n", ""),
    ("from scipy.stats import gaussian_kde\n", ""),
    ("from sklearn.linear_model import LinearRegression, RANSACRegressor, "
     "HuberRegressor, TheilSenRegressor\n",
     "from sklearn.linear_model import LinearRegression\n"),
    ("import matplotlib.pyplot as plt\n", ""),
    ("import matplotlib.patches as mpatches\n", ""),
    ("from matplotlib.lines import Line2D\n", ""),
    ("from matplotlib.patches import Circle\n", ""),
    ("from shapely.geometry import Point, Polygon\n",
     "from shapely.geometry import Point\n"),
    ("from IPython.display import display\n", ""),
    ("from cmdstanpy import CmdStanModel\n", ""),
    # TEXAS names, never used
    ("from TEXAS.stan.compiler import StanCompiler\n", ""),
    ("from TEXAS.stan.sampler  import StanSampler\n", ""),
    ("from TEXAS import predict_T_from_proxyObs, predict_proxy_from_T\n", ""),
    ("from TEXAS.data import MahalanobisOutlierDetector, build_invT_inputData, "
     "build_fwd_data\n",
     "from TEXAS.data import build_fwd_data\n"),
    # star import -> the two names this notebook actually uses
    ("from TEXAS.plotting import *\n",
     "from TEXAS.plotting import plot_prior_distributions, plot_residual_maps\n"),
]
src = cell.source
for old, new in CELL4:
    assert src.count(old) == 1, f"cell 4 anchor not unique or not found: {old!r}"
    src = src.replace(old, new)
cell.source = src

# ── cell 42: unused sklearn.utils.resample inside a plotting helper ───────────
c42 = nb.cells[42]
assert c42.cell_type == "code"
old = "    from sklearn.utils import resample\n"
assert c42.source.count(old) == 1, "cell 42 anchor not unique or not found"
c42.source = c42.source.replace(old, "")

# ── cell 65: second unused pyplot binding ────────────────────────────────────
c65 = nb.cells[65]
assert c65.cell_type == "code"
old = "import matplotlib.pyplot as plt\n"
assert c65.source.count(old) == 1, "cell 65 anchor not unique or not found"
c65.source = c65.source.replace(old, "")

# ── cell 83: third unused pyplot binding, on a shared import line ────────────
c83 = nb.cells[83]
assert c83.cell_type == "code"
old = "import matplotlib.pyplot as plt, matplotlib.colors as mcolors\n"
assert c83.source.count(old) == 1, "cell 83 anchor not unique or not found"
c83.source = c83.source.replace(old, "import matplotlib.colors as mcolors\n")

nbformat.write(nb, NB)
print("SI_code02 cells 4, 42, 65, 83 rewritten")
PY
```

- [ ] **Step 4 (a): zero unused imports**

```bash
SCRATCH2=$(mktemp -d)
jupyter nbconvert --to script --output-dir="$SCRATCH2" \
  notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb
ruff check --isolated --select F401 --no-cache --output-format=concise \
  "$SCRATCH2/SI_code02_t0shift_TEXAS_analysis.py"
```
Expected: `All checks passed!`

- [ ] **Step 5 (c): no undefined names beyond the IPython builtins**

```bash
ruff check --isolated --select F821 --no-cache --output-format=concise \
  "$SCRATCH2/SI_code02_t0shift_TEXAS_analysis.py" \
  | grep -v "Undefined name \`get_ipython\`" \
  | grep -v "Undefined name \`display\`"
```
Expected: only the `Found 5 errors.` summary line (5 × `get_ipython`).

- [ ] **Step 6 (b): the import cell executes cleanly**

Only cell 4 is a pure-import cell; cells 42/65/83 mix imports with analysis and
cannot run standalone. Their one-line deletions are covered by (a) and (c).

```bash
python - <<'PY'
import nbformat
nb = nbformat.read("notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb", as_version=4)
nb.cells = [nb.cells[4]]
nbformat.write(nb, "/tmp/imports_SI_code02.ipynb")
PY
jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 \
  --output /tmp/imports_SI_code02_out.ipynb /tmp/imports_SI_code02.ipynb
```
Expected: written, no traceback.

- [ ] **Step 7: Confirm cell 89 and all outputs are untouched**

```bash
git diff notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb | grep -c '"output_type"'
python - <<'PY'
import json, subprocess
old = json.loads(subprocess.run(
    ["git", "show", "HEAD:notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb"],
    capture_output=True, text=True, check=True).stdout)
new = json.load(open("notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb"))
changed = [i for i, (a, b) in enumerate(zip(old["cells"], new["cells"]))
           if a.get("source") != b.get("source")]
print("cells whose source changed:", changed)
assert changed == [4, 42, 65, 83], changed
PY
```
Expected: `0` output objects in the diff, and `cells whose source changed: [4, 42, 65, 83]`.

- [ ] **Step 8: Commit**

```bash
git add notebooks/manuscripts/SI_code02_t0shift_TEXAS_analysis.ipynb
git commit -m "$(cat <<'EOF'
chore(notebooks): remove dead imports from SI_code02

Cell 4: drops pykrige, cmocean, seaborn, plotly, ipywidgets, geopy, bayspline,
functools.partial, requests, string, io, time, and the unused
scipy/sklearn/matplotlib/shapely/IPython/cmdstanpy/TEXAS names. All three
matplotlib.pyplot bindings go (cells 4, 65, 83) -- the notebook plots with
ultraplot and never references `plt`. Cell 42 loses sklearn.utils.resample.

`from TEXAS.plotting import *` becomes an explicit
`from TEXAS.plotting import plot_prior_distributions, plot_residual_maps`,
the only two of that module's 11 exports the notebook uses.

Source cells only; executed outputs untouched. Cell 89 not touched.
Spec: docs/superpowers/specs/2026-09-07-repo-finalization-design.md §9.4

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU
EOF
)"
```

---

### Task 7: `SI_code02a_model_param_sensitivity_test.ipynb` import cleanup

Spec §9.4 row 4. This notebook has **three** import cells (2, 3, 4) plus one
inline import in cell 43. There is no `from TEXAS import *` here.

**Files:**
- Modify: `notebooks/manuscripts/SI_code02a_model_param_sensitivity_test.ipynb` (cells 2, 3, 4, 43 — source only)

**Interfaces:**
- Consumes: nothing. Produces: nothing other tasks read.

- [ ] **Step 1: Capture the "before" state**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git status --short notebooks/manuscripts/SI_code02a_model_param_sensitivity_test.ipynb
SCRATCH=$(mktemp -d)
jupyter nbconvert --to script --output-dir="$SCRATCH" \
  notebooks/manuscripts/SI_code02a_model_param_sensitivity_test.ipynb
ruff check --isolated --select F401 --no-cache --output-format=concise \
  "$SCRATCH/SI_code02a_model_param_sensitivity_test.py"
```
Expected: 8 findings — `os`, `math`, `dataclasses.dataclass`,
`matplotlib.colors.TwoSlopeNorm`, `TEXAS.stan.sampler.StanSampler`,
`TEXAS.stan.sampler.auto_detect_predictors`,
`TEXAS.models.multivariate.generalized_logistic_fixed_upper_multivariate`, and
`numpy` (the `_np` alias at the bottom).

- [ ] **Step 2: Apply the edits**

```bash
python - <<'PY'
import nbformat

NB = "notebooks/manuscripts/SI_code02a_model_param_sensitivity_test.ipynb"
nb = nbformat.read(NB, as_version=4)

# ── cell 2 ────────────────────────────────────────────────────────────────────
c2 = nb.cells[2]
assert c2.cell_type == "code"
assert "!python --version" in c2.source, "cell 2 is not the version/warnings cell"
old = "import os\n"
assert c2.source.count(old) == 1, "cell 2 anchor not unique or not found"
c2.source = c2.source.replace(old, "")

# ── cell 3 ────────────────────────────────────────────────────────────────────
c3 = nb.cells[3]
assert c3.cell_type == "code"
assert "from dataclasses import dataclass" in c3.source, "cell 3 is not the stdlib/plot import cell"
for old in ("import math\n",
            "from dataclasses import dataclass\n",
            "from matplotlib.colors import TwoSlopeNorm\n"):
    assert c3.source.count(old) == 1, f"cell 3 anchor not unique or not found: {old!r}"
    c3.source = c3.source.replace(old, "")

# ── cell 4 ────────────────────────────────────────────────────────────────────
c4 = nb.cells[4]
assert c4.cell_type == "code"
assert "from TEXAS.utils.paths import CMDSTAN_DIR" in c4.source, "cell 4 is not the TEXAS import cell"
CELL4 = [
    ("from TEXAS.stan.sampler import StanSampler, get_posterior, auto_detect_predictors\n",
     "from TEXAS.stan.sampler import get_posterior\n"),
    ("    generalized_logistic_fixed_upper_multivariate,\n", ""),
]
for old, new in CELL4:
    assert c4.source.count(old) == 1, f"cell 4 anchor not unique or not found: {old!r}"
    c4.source = c4.source.replace(old, new)

# ── cell 43: inline `numpy as _np`, never used ───────────────────────────────
c43 = nb.cells[43]
assert c43.cell_type == "code"
old = "    import pandas as _pd, numpy as _np\n"
assert c43.source.count(old) == 1, "cell 43 anchor not unique or not found"
c43.source = c43.source.replace(old, "    import pandas as _pd\n")

nbformat.write(nb, NB)
print("SI_code02a cells 2, 3, 4, 43 rewritten")
PY
```

- [ ] **Step 3 (a): zero unused imports**

```bash
SCRATCH2=$(mktemp -d)
jupyter nbconvert --to script --output-dir="$SCRATCH2" \
  notebooks/manuscripts/SI_code02a_model_param_sensitivity_test.ipynb
ruff check --isolated --select F401 --no-cache --output-format=concise \
  "$SCRATCH2/SI_code02a_model_param_sensitivity_test.py"
```
Expected: `All checks passed!`

- [ ] **Step 4 (c): no undefined names beyond the IPython builtins**

```bash
ruff check --isolated --select F821 --no-cache --output-format=concise \
  "$SCRATCH2/SI_code02a_model_param_sensitivity_test.py" \
  | grep -v "Undefined name \`get_ipython\`" \
  | grep -v "Undefined name \`display\`"
```
Expected: only the `Found 2 errors.` summary line (1 × `get_ipython`, 1 × `display`) —
identical to the pre-edit baseline.

- [ ] **Step 5 (b): the import cells execute cleanly**

Cells 2, 3 and 4 are all pure-import/setup cells and run as a group. Cell 43 is
analysis and is covered by (a) and (c).

```bash
python - <<'PY'
import nbformat
nb = nbformat.read("notebooks/manuscripts/SI_code02a_model_param_sensitivity_test.ipynb", as_version=4)
nb.cells = [nb.cells[2], nb.cells[3], nb.cells[4]]
nbformat.write(nb, "/tmp/imports_SI_code02a.ipynb")
PY
jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 \
  --output /tmp/imports_SI_code02a_out.ipynb /tmp/imports_SI_code02a.ipynb
```
Expected: written, no traceback. (Cell 4 calls `set_cmdstan_path(str(CMDSTAN_DIR))`
and prints the path; that requires CmdStan to be installed, which it is in
`texas-env`.)

- [ ] **Step 6: Confirm no outputs were disturbed**

```bash
git diff notebooks/manuscripts/SI_code02a_model_param_sensitivity_test.ipynb | grep -c '"output_type"'
```
Expected: `0`.

- [ ] **Step 7: Commit**

```bash
git add notebooks/manuscripts/SI_code02a_model_param_sensitivity_test.ipynb
git commit -m "$(cat <<'EOF'
chore(notebooks): remove dead imports from SI_code02a

Drops os, math, dataclasses.dataclass, matplotlib TwoSlopeNorm, the unused
numpy `_np` alias, and the TEXAS names StanSampler, auto_detect_predictors and
generalized_logistic_fixed_upper_multivariate.

Source cells only; executed outputs untouched.
Spec: docs/superpowers/specs/2026-09-07-repo-finalization-design.md §9.4

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU
EOF
)"
```

---

### Task 8: `SI_code03_paleo_showcases.ipynb` import cleanup

Spec §9.4 row 5. Cell 2 is the import cell; cell 14 carries the unused
`CONSTRAINT_CODES` / `KIND_CODES` names.

**Files:**
- Modify: `notebooks/manuscripts/SI_code03_paleo_showcases.ipynb` (cells 2, 14 — source only)

**Interfaces:**
- Consumes: nothing. Produces: nothing other tasks read.

- [ ] **Step 1: Capture the "before" state**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git status --short notebooks/manuscripts/SI_code03_paleo_showcases.ipynb
SCRATCH=$(mktemp -d)
jupyter nbconvert --to script --output-dir="$SCRATCH" \
  notebooks/manuscripts/SI_code03_paleo_showcases.ipynb
ruff check --isolated --select F401 --no-cache --output-format=concise \
  "$SCRATCH/SI_code03_paleo_showcases.py" | tail -2
```
Expected: `Found 38 errors.` (F401 only).

- [ ] **Step 2: Confirm nothing from `TEXAS.plotting` is used**

```bash
grep -cE "compute_sample_range|compute_density_based_range|compute_suffix_specific_range|compute_dataset_specific_range|plot_prior_distributions|plot_residual_maps|plot_proxy_residual_maps|krige_halo_all|make_true_grid|load_or_build_halo_cache|load_or_build_grids_cache" \
  "$SCRATCH/SI_code03_paleo_showcases.py"
```
Expected: `0`. The star import is deleted outright.

- [ ] **Step 3: Apply the edits**

```bash
python - <<'PY'
import nbformat

NB = "notebooks/manuscripts/SI_code03_paleo_showcases.ipynb"
nb = nbformat.read(NB, as_version=4)

# ── cell 2: the import cell ───────────────────────────────────────────────────
cell = nb.cells[2]
assert cell.cell_type == "code", cell.cell_type
assert "from TEXAS import regrid_curvilinear_to_latlon" in cell.source, "cell 2 is not the import cell"

CELL2 = [
    # entire modules, never used
    ("from sklearn.linear_model import LinearRegression, RANSACRegressor, "
     "HuberRegressor, TheilSenRegressor\n", ""),
    ("import cmocean.cm as cmo\n", ""),
    ("from ipywidgets import FloatRangeSlider, VBox\n", ""),
    ("from geopy.distance import distance, Distance, lonlat\n", ""),
    ("import requests\n", ""),
    ("from tqdm import tqdm\n", ""),
    ("import string\n", ""),
    ("import io\n", ""),
    ("import time\n", ""),
    ("import importlib\n", ""),
    ("from functools import partial\n", ""),
    # names, never used
    ("from scipy.optimize import curve_fit\n", ""),
    ("from scipy.stats import pearsonr, spearmanr, truncnorm\n", ""),
    ("import matplotlib.colors as colors\n", ""),
    ("from matplotlib.lines import Line2D\n", ""),
    ("from matplotlib.patches import Rectangle\n", ""),
    ("from matplotlib.patches import Circle\n", ""),
    ("import plotly.graph_objects as go\n", ""),
    ("from plotly.subplots import make_subplots\n", ""),
    ("from cmdstanpy import CmdStanModel\n", ""),
    ("from shapely.geometry import Point, Polygon\n",
     "from shapely.geometry import Point\n"),
    # TEXAS names, never used
    ("from TEXAS.stan.compiler import StanCompiler\n", ""),
    ("from TEXAS.stan.sampler  import StanSampler\n", ""),
    ("from TEXAS.stan.sampler import get_posterior\n", ""),
    ("from TEXAS.stan.io import load_posterior, save_posterior\n",
     "from TEXAS.stan.io import load_posterior\n"),
    ("from TEXAS import predict_T_from_proxyObs, predict_proxy_from_T\n",
     "from TEXAS import predict_T_from_proxyObs\n"),
    ("from TEXAS.ensemble import generate_ensemble_auto\n", ""),
    ("from TEXAS import regrid_curvilinear_to_latlon\n", ""),
    # star import: this notebook uses none of TEXAS.plotting's 11 exports
    ("from TEXAS.plotting import *\n", ""),
]
src = cell.source
for old, new in CELL2:
    assert src.count(old) == 1, f"cell 2 anchor not unique or not found: {old!r}"
    src = src.replace(old, new)
cell.source = src

# ── cell 14: unused naming constants ─────────────────────────────────────────
c14 = nb.cells[14]
assert c14.cell_type == "code"
old = ("from TEXAS.utils.naming import (case_from_attrs, inv_relpath,\n"
       "                                CONSTRAINT_CODES, KIND_CODES)\n")
assert c14.source.count(old) == 1, "cell 14 anchor not unique or not found"
c14.source = c14.source.replace(
    old, "from TEXAS.utils.naming import case_from_attrs, inv_relpath\n")

nbformat.write(nb, NB)
print("SI_code03 cells 2, 14 rewritten")
PY
```

- [ ] **Step 4 (a): zero unused imports**

```bash
SCRATCH2=$(mktemp -d)
jupyter nbconvert --to script --output-dir="$SCRATCH2" \
  notebooks/manuscripts/SI_code03_paleo_showcases.ipynb
ruff check --isolated --select F401 --no-cache --output-format=concise \
  "$SCRATCH2/SI_code03_paleo_showcases.py"
```
Expected: `All checks passed!`

- [ ] **Step 5 (c): no undefined names beyond the IPython builtins**

```bash
ruff check --isolated --select F821 --no-cache --output-format=concise \
  "$SCRATCH2/SI_code03_paleo_showcases.py" \
  | grep -v "Undefined name \`get_ipython\`" \
  | grep -v "Undefined name \`display\`"
```
Expected: only the `Found 3 errors.` summary line (3 × `get_ipython`).

- [ ] **Step 6 (b): the import cell executes cleanly**

Only cell 2 is a pure-import cell; cell 14 is analysis and is covered by (a) and (c).

```bash
python - <<'PY'
import nbformat
nb = nbformat.read("notebooks/manuscripts/SI_code03_paleo_showcases.ipynb", as_version=4)
nb.cells = [nb.cells[2]]
nbformat.write(nb, "/tmp/imports_SI_code03.ipynb")
PY
jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 \
  --output /tmp/imports_SI_code03_out.ipynb /tmp/imports_SI_code03.ipynb
```
Expected: written, no traceback.

- [ ] **Step 7: Confirm no outputs were disturbed**

```bash
git diff notebooks/manuscripts/SI_code03_paleo_showcases.ipynb | grep -c '"output_type"'
```
Expected: `0`.

- [ ] **Step 8: Commit**

```bash
git add notebooks/manuscripts/SI_code03_paleo_showcases.ipynb
git commit -m "$(cat <<'EOF'
chore(notebooks): remove dead imports from SI_code03

Cell 2: drops the sklearn regressors, cmocean, ipywidgets, geopy, requests,
tqdm, string, io, time, importlib, functools.partial, and the unused
scipy/matplotlib/plotly/cmdstanpy/shapely/TEXAS names. Cell 14 loses the unused
CONSTRAINT_CODES and KIND_CODES. `from TEXAS.plotting import *` is deleted --
the notebook uses none of that module's 11 exports.

Source cells only; executed outputs untouched.
Spec: docs/superpowers/specs/2026-09-07-repo-finalization-design.md §9.4

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU
EOF
)"
```

---

### Task 9: `quickstart_extended.ipynb` import cleanup

Spec §9.4 last row. Four modules, spread over five cells: `interp1d` is imported
twice (cells 50 and 57) and used neither time, so **both** must go — remove only
one and ruff will flag the other, since the first binding was previously masked
by the second (`F811 Redefinition of unused interp1d`).

**Files:**
- Modify: `notebooks/quickstart_extended.ipynb` (cells 5, 9, 16, 50, 57 — source only)

**Interfaces:**
- Consumes: nothing. Produces: nothing other tasks read.

- [ ] **Step 1: Capture the "before" state**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git status --short notebooks/quickstart_extended.ipynb
SCRATCH=$(mktemp -d)
jupyter nbconvert --to script --output-dir="$SCRATCH" notebooks/quickstart_extended.ipynb
ruff check --isolated --select F401 --no-cache --output-format=concise \
  "$SCRATCH/quickstart_extended.py"
ruff check --isolated --select F821 --no-cache --output-format=concise \
  "$SCRATCH/quickstart_extended.py" | tail -2
```
Expected F401: 4 findings (`xarray`, `os`, `ultraplot`, `scipy.interpolate.interp1d`).
Expected F821: `Found 7 errors.` — 1 × `display` and 6 × `result_PETM`.
`result_PETM` is a **pre-existing** undefined name in this notebook and is out of
scope; record the count so Step 4 can show it is unchanged.

- [ ] **Step 2: Apply the edits**

```bash
python - <<'PY'
import nbformat

NB = "notebooks/quickstart_extended.ipynb"
nb = nbformat.read(NB, as_version=4)

# ── cell 5: os + xarray ───────────────────────────────────────────────────────
c5 = nb.cells[5]
assert c5.cell_type == "code"
assert "print(f\"TEXAS version: {TEXAS.__version__}\")" in c5.source, "cell 5 is not the first import cell"
for old in ("import os\n", "import xarray as xr\n"):
    assert c5.source.count(old) == 1, f"cell 5 anchor not unique or not found: {old!r}"
    c5.source = c5.source.replace(old, "")

# ── cell 9: second unused os binding ─────────────────────────────────────────
c9 = nb.cells[9]
assert c9.cell_type == "code"
old = "import os\n"
assert c9.source.count(old) == 1, "cell 9 anchor not unique or not found"
c9.source = c9.source.replace(old, "")

# ── cell 16: ultraplot, imported but never used in this notebook ─────────────
c16 = nb.cells[16]
assert c16.cell_type == "code"
old = "import ultraplot as plot\n"
assert c16.source.count(old) == 1, "cell 16 anchor not unique or not found"
c16.source = c16.source.replace(old, "")

# ── cells 50 and 57: interp1d, imported twice, used neither time ─────────────
for idx in (50, 57):
    c = nb.cells[idx]
    assert c.cell_type == "code"
    old = "from scipy.interpolate import interp1d\n"
    assert c.source.count(old) == 1, f"cell {idx} anchor not unique or not found"
    c.source = c.source.replace(old, "")

nbformat.write(nb, NB)
print("quickstart_extended cells 5, 9, 16, 50, 57 rewritten")
PY
```

- [ ] **Step 3 (a): zero unused imports**

```bash
SCRATCH2=$(mktemp -d)
jupyter nbconvert --to script --output-dir="$SCRATCH2" notebooks/quickstart_extended.ipynb
ruff check --isolated --select F401 --no-cache --output-format=concise \
  "$SCRATCH2/quickstart_extended.py"
```
Expected: `All checks passed!`

- [ ] **Step 4 (c): undefined names unchanged from the baseline**

```bash
ruff check --isolated --select F821 --no-cache --output-format=concise \
  "$SCRATCH2/quickstart_extended.py" | tail -2
```
Expected: `Found 7 errors.` — identical to Step 1. The set is 1 × `display`
(IPython-injected) and 6 × `result_PETM` (pre-existing; a cell references a name
an earlier cell never assigns). This task must not change that count in either
direction.

- [ ] **Step 5 (b): the import cell executes cleanly**

Only cell 5 is a pure-import cell; cells 9, 16, 50 and 57 mix imports with
analysis (cell 16 plots, cells 50/57 build colormaps) and cannot run standalone.
Their single-line deletions are covered by (a) and (c).

```bash
python - <<'PY'
import nbformat
nb = nbformat.read("notebooks/quickstart_extended.ipynb", as_version=4)
nb.cells = [nb.cells[5]]
nbformat.write(nb, "/tmp/imports_quickstart_extended.ipynb")
PY
jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 \
  --output /tmp/imports_quickstart_extended_out.ipynb /tmp/imports_quickstart_extended.ipynb
```
Expected: written, no traceback.

- [ ] **Step 6: Confirm no outputs were disturbed**

```bash
git diff notebooks/quickstart_extended.ipynb | grep -c '"output_type"'
```
Expected: `0`.

- [ ] **Step 7: Commit**

```bash
git add notebooks/quickstart_extended.ipynb
git commit -m "$(cat <<'EOF'
chore(notebooks): remove dead imports from quickstart_extended

Drops os (cells 5 and 9), xarray, ultraplot, and both unused
scipy.interpolate.interp1d bindings (cells 50 and 57) -- the second was masking
the first from ruff, so removing only one would have surfaced the other.

Source cells only; executed outputs untouched. The 6 pre-existing
`result_PETM` undefined-name findings are unchanged and out of scope.
Spec: docs/superpowers/specs/2026-09-07-repo-finalization-design.md §9.4

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU
EOF
)"
```

---

### Task 10: Regenerate both lockfiles and rebuild the Docker image

Spec §9.5, run verbatim, once Tasks 2 and 3 have landed.

**Files:**
- Modify (generated): `uv.lock`, `conda-lock.yml`, `conda-linux-64.lock`,
  `conda-osx-64.lock`, `conda-osx-arm64.lock`, `conda-win-64.lock`

**Interfaces:**
- Consumes: the `pyproject.toml` extras from Task 2
  (`plotting = ["ultraplot>=2.4.0", "cmocean"]`,
  `maps = [..., "joblib"]`, `regrid = ["xesmf"]`, no `[tool.uv]`) and the
  `environment.yml` from Task 3.
- Produces: the lockfiles the Docker image and the Open Research statement point at.

- [ ] **Step 1: Confirm the inputs are the edited ones**

```bash
cd /home/ronnie-rattan/Documents/GitHub/TEXAS
git log --oneline -6
grep -n "override-dependencies\|pyproj<3.6" pyproject.toml   # expect no output
grep -n "plotly\|statsmodels\|odrpack\|geopandas" environment.yml   # expect no output
which uv conda-lock docker
```
Expected: the Task 2 and Task 3 commits present, both greps silent, all three
tools resolvable (`uv 0.11.26`, `conda-lock 3.0.4`, `docker 26.1.5` on this machine).

- [ ] **Step 2: Regenerate `uv.lock`**

```bash
uv lock
git diff --stat uv.lock
```
Expected: `uv.lock` shrinks. It resolved 238 packages before this audit; expect
fewer, with `geopandas`, `pyogrio`, `mapclassify`, `rtree`, `geopy`, `gsw`,
`pyproj`, `statsmodels`, `odrpack`, `anywidget`, `ipylab`, `duckdb`,
`sqlalchemy` and `pydantic` gone, and `joblib` present. `uv lock` must succeed —
if it fails with a resolution error mentioning a package that is not on PyPI,
that package has leaked into an extra; see the Global Constraints.

- [ ] **Step 3: Regenerate `conda-lock.yml` for all four platforms**

`environment.yml` declares **no** `platforms:` key, so omitting the `-p` flags
silently drops macOS and Windows and produces a linux-only lock. Always pass all
four:

```bash
conda-lock -f environment.yml --lockfile conda-lock.yml \
  -p linux-64 -p osx-64 -p osx-arm64 -p win-64
```

- [ ] **Step 4: Verify all four platforms actually made it in**

```bash
python - <<'PY'
import yaml
lock = yaml.safe_load(open("conda-lock.yml"))
plats = sorted(lock["metadata"]["platforms"])
print("platforms:", plats)
assert plats == ["linux-64", "osx-64", "osx-arm64", "win-64"], plats
print("packages:", len(lock["package"]))
PY
```
Expected: all four platforms listed. (The pre-audit lock held 1802 package entries;
expect fewer.)

- [ ] **Step 5: Render the four explicit lock files**

```bash
conda-lock render -p linux-64 -p osx-64 -p osx-arm64 -p win-64
git status --short conda-*.lock
```
Expected: `conda-linux-64.lock`, `conda-osx-64.lock`, `conda-osx-arm64.lock`,
`conda-win-64.lock` all modified.

- [ ] **Step 6: Spot-check that the removals reached the lock**

```bash
for p in dask distributed zarr cftime gsw geopandas geopy pyogrio mapclassify \
         rtree pyshp statsmodels odrpack plotly; do
  printf '%-14s %s\n' "$p" "$(grep -c "^https.*/${p}-" conda-linux-64.lock)"
done
grep -c "^https.*/psutil-" conda-linux-64.lock
```
Expected: `0` for every removed package (transitive pulls are possible — if a
count is non-zero, confirm with `conda-lock`'s dependency graph that it arrives
via something you kept, e.g. `pyproj` under `cartopy`, and note it rather than
re-editing). `psutil` must be ≥ 1.

- [ ] **Step 7: Rebuild the Docker image**

The image builds from `conda-lock.yml`, then layers the hardcoded pip line
`docker/Dockerfile:25` (`pygwalker pykrige ultraplot` after Task 3), then installs
TEXAS with **no extras**. This takes 20–40 minutes and needs network.

```bash
docker compose -f docker/docker-compose.yml build full
```
Expected: build succeeds, including the final verification layer
`RUN micromamba run -n texas-env python -c "from TEXAS.utils.paths import find_cmdstan; ..."`
which prints `CmdStan OK: <path>`.

- [ ] **Step 8: Verify the rebuilt image can import the package and the maps path**

```bash
docker run --rm ghcr.io/paleolipidrr/texas:latest \
  python -c "import TEXAS, joblib, cmocean, ultraplot; \
             from TEXAS.plotting.residual_maps import _r2_score; \
             print(TEXAS.__version__, _r2_score([1,2,3],[1,2,3]))"
```
Expected: the version string and `1.0`.

- [ ] **Step 9: Rebuild the local conda env and re-run the full suite**

This is the first point at which rebuilding is safe — all notebook tasks have landed.

```bash
conda env create -n texas-env-audit -f environment.yml
conda run -n texas-env-audit pip install -e .
conda run -n texas-env-audit python -m pytest -q --no-header 2>&1 | tail -2
```
Expected: the same pass/skip counts as `/tmp/pytest-baseline.txt`, plus the tests
added in Tasks 1–3, and no failures. If `pyproj`'s `CRSError` appears, set
`PROJ_DATA`/`PROJ_LIB` to `$(conda info --base)/envs/texas-env-audit/share/proj`
as in Preflight.

- [ ] **Step 10: Commit**

```bash
git add uv.lock conda-lock.yml conda-linux-64.lock conda-osx-64.lock \
        conda-osx-arm64.lock conda-win-64.lock
git commit -m "$(cat <<'EOF'
chore: regenerate uv.lock and conda-lock for the audited dependency set

conda-lock run with all four platforms explicitly (-p linux-64 -p osx-64
-p osx-arm64 -p win-64): environment.yml declares no platforms key, so omitting
them silently drops macOS and Windows.

Docker image rebuilt from the new conda-lock.yml and verified to import TEXAS,
joblib, cmocean and ultraplot, and to resolve CmdStan.

Spec: docs/superpowers/specs/2026-09-07-repo-finalization-design.md §9.5

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AMiZnMJ9WZhRrKHxKhtSYU
EOF
)"
```

---

## Self-Review

Run after the plan is written; recorded here so an executor can see what was checked.

**1. Spec coverage**

| spec item | task |
|---|---|
| §9.2 scikit-learn hidden core dep (`r2_score`, `PCA`) | 1 |
| §9.2 `joblib` → `maps` | 2 |
| §9.2 `cmocean` core → `plotting` | 2 |
| §9.2 `plotly` dropped from core | 2 |
| §9.2 dev: anywidget, ipylab, duckdb, sqlalchemy, pydantic removed | 2 |
| §9.2 dev: statsmodels, odrpack removed (+ `docs/_config.yml` mock) | 2 (deps/docs), 4 (imports) |
| §9.2 pyarrow/openpyxl kept with comments | 2 |
| §9.2 `regrid = ["xesmf"]`, `pyproj<3.6` and `[tool.uv]` override dropped | 2 |
| §9.2 `requests` imports removed, nothing declared | 4, 6, 8 |
| §9.2 `IPython`/`display` — no change | documented in the shared notebook method and in each F821 step |
| §9.2 `psutil` added to `environment.yml` | 3 |
| §9.3 all removals, keeps, `setuptools<81` note, plotly decision | 3 |
| §9.4 per-notebook import cleanup, `from TEXAS.plotting import *` replaced, (a)(b)(c) verification | 4–9 |
| §9.5 `uv lock`, `conda-lock` ×4, `conda-lock render` ×4, docker build | 10 |
| §9.8 `docs/installation.md:399` | 2 |

No gaps. Two spec inaccuracies were found while reading the real files and are
corrected in the plan rather than propagated:

- §9.4 says the star import is `from TEXAS import *`. It is actually
  **`from TEXAS.plotting import *`** in all three notebooks (verified by
  grepping every notebook for `from ... import *`). The replacement lists were
  derived against `TEXAS.plotting.__all__`, not `TEXAS`'s.
- §9.4 lists `pykrige.OrdinaryKriging` for SI_code02; the actual import line is
  `from pykrige.ok import OrdinaryKriging`, which is the anchor used.

Two §9.4 entries sit in cells that are *not* the import cell
(`sklearn.utils.resample` in SI_code02 cell 42; `matplotlib.pyplot` in SI_code02
cells 65/83; `CONSTRAINT_CODES`/`KIND_CODES` in SI_code03 cell 14;
`numpy as _np` in SI_code02a cell 43; three of the four quickstart_extended
removals). The spec's verification (a) demands *zero* F401 on the exported
script, which is unsatisfiable without them, so each task names the exact cells.

**2. Placeholder scan**

No "TBD", "as needed", "similar to Task N", or "add appropriate error handling".
Every removal list is the literal output of
`ruff check --select F401` on the notebook exported with `jupyter nbconvert --to
script`, re-verified by applying `--fix` to a scratch copy and diffing; every
anchor string was copied from the file. Every code step carries a code block.
Task 6's `plt` removal, which looks wrong at a glance, is backed by an explicit
`grep -c '\bplt\.'` → `0` check placed *before* the edit.

**3. Type consistency**

`_r2_score` is defined once in Task 1 with signature `(y_true, y_pred) -> float`
and referenced under that exact name in Task 1's tests, in Task 1 Step 5's grep,
and in Task 10 Step 8's Docker smoke test. `_dep_lines()`, `ENV_YML` and
`PYPROJECT` in Tasks 2–3's new tests are the helpers that already exist in
`tests/test_environment_pins.py`; `_pyproject()` is defined once, in Task 2, and
used only there. `residual_maps` and `pytest` are already imported at the top of
`tests/test_optional_deps.py`, so Task 1's appended tests resolve both; the file
gains `subprocess`, `sys`, `numpy` and `pandas`, all listed in its import block.
The extras named in Task 10's Interfaces block match the ones Task 2 writes,
verbatim.
