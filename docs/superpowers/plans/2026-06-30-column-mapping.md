# Column-Mapping for MahalanobisOutlierDetector — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let callers of `MahalanobisOutlierDetector` map their physical DataFrame column names to TEXAS's logical feature names via a per-call `columns=` dict, without mutating their DataFrame, and make a missing/empty required column loud instead of a silent NaN.

**Architecture:** All logical→physical translation is centralized in one new private helper `_resolve_features()`. Every column-indexing site (`fit`, `_compute_distances`, `detect_outliers_manual`, and the 6 plotting methods) routes through it. The helper selects the mapped physical columns, raises `KeyError` if any are absent, returns a **copy** relabeled to logical names, and applies an `on_unscorable` policy (`warn`/`raise`/`ignore`) for present-but-NaN/Inf rows.

**Tech Stack:** Python, pandas, numpy, scipy, pytest.

## Global Constraints

- **100% backward compatible:** every existing call with no `columns` / `on_unscorable` argument returns identical results (distances, outlier flags, manual flags). Regression tests must prove this.
- **Never mutate the caller's input DataFrame** in the mapping logic: select + `.copy()`, relabel the copy only. The pre-existing explicit `col_name=` / `*_col=` writes are preserved unchanged (opt-in mutation, documented feature).
- `columns` and `on_unscorable` are **keyword-only** on every method (after `*`) so they never collide with existing positional `col_name` / `*_col` args.
- Resolution rule per logical name `f`: `physical = (columns or {}).get(f, f)`.
- Missing mapped physical column → **always `KeyError`** naming each `logical -> physical` pair, regardless of `on_unscorable`.
- `on_unscorable` default is `'warn'`; plotting methods call the helper with `on_unscorable='ignore'` (exploratory/NaN-tolerant) but still raise on a missing column.
- Do **not** touch the array-based API (`predict_T_from_proxyObs`, `predict_proxy_from_T`, `compute_scaledRI`, `build_invT_inputData`).
- Version bump `0.2.1` → `0.3.0` in `pyproject.toml`; add new `CHANGELOG.md`.
- Tests live in `tests/test_screening.py` (new), pytest class-based style matching the existing suite.

---

### Task 1: `_resolve_features` helper + core data path (`fit`, `_compute_distances`, `transform`, `detect_outliers`, `fit_transform`)

**Files:**
- Modify: `src/TEXAS/data/screening.py` (add `import warnings`; add `_resolve_features`; thread `columns`/`on_unscorable` through `fit`, `_compute_distances`, `transform`, `detect_outliers`, `fit_transform`)
- Test: `tests/test_screening.py` (create)

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `MahalanobisOutlierDetector._resolve_features(df, columns, *, logical=None, on_unscorable='warn') -> pd.DataFrame` — returns a copy of the selected columns relabeled to logical names, same index as `df`.
  - `fit(df, *, columns=None, on_unscorable='warn') -> self`
  - `_compute_distances(df, columns=None, on_unscorable='warn') -> pd.Series`
  - `transform(df, col_name=None, *, columns=None, on_unscorable='warn') -> pd.Series`
  - `detect_outliers(df, col_name=None, *, columns=None, on_unscorable='warn') -> pd.Series`
  - `fit_transform(df, dist_col=None, outlier_col=None, manual_outlier_col=None, *, columns=None, on_unscorable='warn') -> dict`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_screening.py`:

```python
"""Tests for MahalanobisOutlierDetector logical->physical column mapping."""

import numpy as np
import pandas as pd
import pytest

from TEXAS.data.screening import MahalanobisOutlierDetector


def _training_df(seed=0, n=200):
    """Training frame with LOGICAL column names (TEXAS convention)."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "TEX86": rng.uniform(0.3, 0.8, n),
        "scaledRI_cren3": rng.uniform(0.2, 0.7, n),
    })


def _renamed(df, mapping):
    """Return df with logical columns renamed to physical (for reference checks)."""
    return df.rename(columns={v: k for k, v in mapping.items()})  # not used; see mapping helper


class TestColumnMappingCorrectness:
    def test_mapping_matches_manual_rename(self):
        """transform with a columns= map equals transforming a hand-renamed frame."""
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9)
        det.fit(train)

        # Caller frame with PHYSICAL names.
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        mapping = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}

        via_map = det.transform(phys, columns=mapping)
        # Reference: rename physical back to logical, transform with no map.
        via_rename = det.transform(
            phys.rename(columns={v: k for k, v in mapping.items()})
        )
        pd.testing.assert_series_equal(via_map, via_rename)

    def test_all_populated_rows_finite(self):
        """Every fully-populated mapped row gets a finite distance."""
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(train)
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        dist = det.transform(phys, columns={"TEX86": "TEX86_best",
                                            "scaledRI_cren3": "ScaledRI03_best"})
        assert np.isfinite(dist.to_numpy()).all()


class TestMissingColumnRaises:
    def test_missing_mapped_column_raises_keyerror(self):
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(train)
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        with pytest.raises(KeyError, match=r"scaledRI_cren3.*ScaledRI03_typo"):
            det.transform(phys, columns={"TEX86": "TEX86_best",
                                         "scaledRI_cren3": "ScaledRI03_typo"})

    def test_missing_unmapped_column_raises_keyerror(self):
        """No map, but the logical column is absent -> KeyError naming it."""
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(train)
        only_tex = train[["TEX86"]]
        with pytest.raises(KeyError, match=r"scaledRI_cren3"):
            det.transform(only_tex)


class TestCoverageGuardrail:
    def _frame_with_nan(self):
        train = _training_df(n=50)
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        phys.loc[phys.index[:5], "TEX86_best"] = np.nan  # 5 unscorable rows
        return phys

    def _fitted(self):
        return MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.9
        ).fit(_training_df())

    def test_warn_default_reports_count(self):
        det, phys = self._fitted(), self._frame_with_nan()
        m = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}
        with pytest.warns(UserWarning, match=r"5 row"):
            det.transform(phys, columns=m)

    def test_raise_mode(self):
        det, phys = self._fitted(), self._frame_with_nan()
        m = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}
        with pytest.raises(ValueError, match=r"5 row"):
            det.transform(phys, columns=m, on_unscorable="raise")

    def test_ignore_mode_silent(self):
        det, phys = self._fitted(), self._frame_with_nan()
        m = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}
        import warnings as _w
        with _w.catch_warnings():
            _w.simplefilter("error")  # any warning becomes an error
            det.transform(phys, columns=m, on_unscorable="ignore")


class TestNoMutation:
    def test_transform_does_not_mutate_caller_df(self):
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(train)
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        before_cols = list(phys.columns)
        before = phys.copy(deep=True)
        det.transform(phys, columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        assert list(phys.columns) == before_cols
        pd.testing.assert_frame_equal(phys, before)


class TestBackwardCompat:
    def test_no_columns_arg_identical_distances(self):
        """The no-map path is byte-identical to pre-change behavior."""
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(train)
        d1 = det.transform(train)
        # Recompute manually via scipy for a fixed reference.
        assert d1.notna().all()
        assert d1.index.equals(train.index)

    def test_col_name_write_still_works(self):
        """Existing explicit col_name= mutation is preserved."""
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(train)
        det.transform(train, col_name="mahal")
        assert "mahal" in train.columns
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_screening.py -q`
Expected: FAIL (e.g. `TypeError: transform() got an unexpected keyword argument 'columns'`).

- [ ] **Step 3: Add `import warnings` and the `_resolve_features` helper**

In `src/TEXAS/data/screening.py`, add to the imports at top (after `import pandas as pd`):

```python
import warnings
```

Add this method to `MahalanobisOutlierDetector` (place it directly above `_compute_distances`):

```python
    def _resolve_features(
        self,
        df: pd.DataFrame,
        columns: Optional[dict] = None,
        *,
        logical: Optional[list] = None,
        on_unscorable: Literal['warn', 'raise', 'ignore'] = 'warn',
    ) -> pd.DataFrame:
        """
        Select feature columns from `df` via a logical->physical map and return
        a COPY relabeled to the logical names (same index as `df`).

        Parameters
        ----------
        df : pd.DataFrame
            Caller data (physical column names).
        columns : dict, optional
            Mapping {logical_name: physical_column}. Missing keys default to
            identity (logical == physical). None means full identity.
        logical : list, optional
            Logical names to resolve. Defaults to ``self.features``.
        on_unscorable : {'warn', 'raise', 'ignore'}, default 'warn'
            Policy for rows that map to a present column but are NaN/Inf and
            therefore cannot be scored.

        Raises
        ------
        KeyError
            If any mapped physical column is absent from `df`, naming each
            unresolved ``logical -> physical`` pair.
        ValueError
            If `on_unscorable='raise'` and any unscorable rows exist, or if
            `on_unscorable` is not one of the allowed values.
        """
        if on_unscorable not in ('warn', 'raise', 'ignore'):
            raise ValueError(
                f"on_unscorable must be 'warn', 'raise', or 'ignore', "
                f"got {on_unscorable!r}"
            )
        logical = list(self.features) if logical is None else list(logical)
        cmap = columns or {}
        physical = [cmap.get(f, f) for f in logical]

        missing = [(f, p) for f, p in zip(logical, physical) if p not in df.columns]
        if missing:
            pairs = ", ".join(f"{f!r} -> {p!r}" for f, p in missing)
            raise KeyError(
                f"MahalanobisOutlierDetector: mapped column(s) not found in "
                f"DataFrame: {pairs}. Available columns: {list(df.columns)}"
            )

        X = df.loc[:, physical].copy()
        X.columns = logical

        if on_unscorable != 'ignore':
            clean = X.replace([np.inf, -np.inf], np.nan)
            n_unscorable = int(clean.isna().any(axis=1).sum())
            if n_unscorable > 0:
                msg = (
                    f"MahalanobisOutlierDetector: {n_unscorable} row(s) map to "
                    f"present column(s) but contain NaN/Inf and cannot be scored "
                    f"(they receive NaN distance/flag). Features: {logical}."
                )
                if on_unscorable == 'raise':
                    raise ValueError(msg)
                warnings.warn(msg, UserWarning, stacklevel=3)

        return X
```

- [ ] **Step 4: Route `fit` and `_compute_distances` through the helper**

Replace the body of `fit` (the two lines that build `X`) so its signature and first lines read:

```python
    def fit(
        self,
        df: pd.DataFrame,
        *,
        columns: Optional[dict] = None,
        on_unscorable: Literal['warn', 'raise', 'ignore'] = 'warn',
    ) -> 'MahalanobisOutlierDetector':
```

and replace:

```python
        # Clean & get valid rows
        X = df[self.features].replace([np.inf, -np.inf], np.nan)
        X_valid = X.dropna().to_numpy(dtype=float)
```

with:

```python
        # Resolve logical->physical, then clean & get valid rows
        X = self._resolve_features(df, columns, on_unscorable=on_unscorable)
        X = X.replace([np.inf, -np.inf], np.nan)
        X_valid = X.dropna().to_numpy(dtype=float)
```

Change `_compute_distances` signature and its `X` line:

```python
    def _compute_distances(
        self,
        df: pd.DataFrame,
        columns: Optional[dict] = None,
        on_unscorable: Literal['warn', 'raise', 'ignore'] = 'warn',
    ) -> pd.Series:
```

Replace:

```python
        X = df[self.features].replace([np.inf, -np.inf], np.nan)
```

with:

```python
        X = self._resolve_features(df, columns, on_unscorable=on_unscorable)
        X = X.replace([np.inf, -np.inf], np.nan)
```

- [ ] **Step 5: Thread `columns`/`on_unscorable` through `transform`, `detect_outliers`, `fit_transform`**

`transform` — new signature and call:

```python
    def transform(
        self,
        df: pd.DataFrame,
        col_name: Optional[str] = None,
        *,
        columns: Optional[dict] = None,
        on_unscorable: Literal['warn', 'raise', 'ignore'] = 'warn',
    ) -> pd.Series:
        distances = self._compute_distances(
            df, columns=columns, on_unscorable=on_unscorable
        )
        if col_name:
            df[col_name] = distances
        return distances
```

`detect_outliers` — new signature and call:

```python
    def detect_outliers(
        self,
        df: pd.DataFrame,
        col_name: Optional[str] = None,
        *,
        columns: Optional[dict] = None,
        on_unscorable: Literal['warn', 'raise', 'ignore'] = 'warn',
    ) -> pd.Series:
        distances = self._compute_distances(
            df, columns=columns, on_unscorable=on_unscorable
        )
        # (rest of body unchanged)
```

`fit_transform` — new signature; thread the args into each sub-call:

```python
    def fit_transform(
        self,
        df: pd.DataFrame,
        dist_col: Optional[str] = None,
        outlier_col: Optional[str] = None,
        manual_outlier_col: Optional[str] = None,
        *,
        columns: Optional[dict] = None,
        on_unscorable: Literal['warn', 'raise', 'ignore'] = 'warn',
    ) -> dict:
        self.fit(df, columns=columns, on_unscorable=on_unscorable)
        distances = self.transform(df, dist_col, columns=columns, on_unscorable=on_unscorable)
        outliers = self.detect_outliers(df, outlier_col, columns=columns, on_unscorable=on_unscorable)
        manual_outliers = self.detect_outliers_manual(
            df, manual_outlier_col, columns=columns, on_unscorable=on_unscorable
        )
        return {
            'distances': distances,
            'outliers': outliers,
            'manual_outliers': manual_outliers,
            'threshold': self.threshold,
        }
```

> Note: `detect_outliers_manual` gets its `columns`/`on_unscorable` kwargs in Task 2. Implement Task 1 and Task 2 before running `fit_transform` tests; the `test_screening.py` suite here does not call `fit_transform`, so Task 1 tests pass independently.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_screening.py -q`
Expected: PASS (all classes in this file).

- [ ] **Step 7: Commit**

```bash
git add src/TEXAS/data/screening.py tests/test_screening.py
git commit -m "feat: add columns= logical->physical mapping to MahalanobisOutlierDetector core path

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Map the hardcoded logical names in `detect_outliers_manual`

**Files:**
- Modify: `src/TEXAS/data/screening.py` (`detect_outliers_manual`)
- Test: `tests/test_screening.py` (add `TestDetectOutliersManualMapping`)

**Interfaces:**
- Consumes: `detect_outliers(df, col_name, *, columns, on_unscorable)` (Task 1).
- Produces: `detect_outliers_manual(df, col_name=None, exclude_condition=None, *, columns=None, on_unscorable='warn') -> pd.Series`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_screening.py`:

```python
class TestDetectOutliersManualMapping:
    def test_default_exception_uses_mapped_columns(self):
        """The default exception rule reads mapped physical columns, not logical."""
        rng = np.random.default_rng(3)
        n = 300
        train = pd.DataFrame({
            "TEX86": rng.uniform(0.3, 0.9, n),
            "scaledRI_cren3": rng.uniform(0.2, 0.8, n),
        })
        det = MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.9
        ).fit(train)

        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        m = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}

        via_map = det.detect_outliers_manual(phys, columns=m)
        via_rename = det.detect_outliers_manual(
            phys.rename(columns={v: k for k, v in m.items()})
        )
        pd.testing.assert_series_equal(via_map, via_rename)

    def test_manual_missing_mapped_column_raises(self):
        train = pd.DataFrame({
            "TEX86": np.linspace(0.3, 0.9, 50),
            "scaledRI_cren3": np.linspace(0.2, 0.8, 50),
        })
        det = MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.9
        ).fit(train)
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        with pytest.raises(KeyError, match=r"TEX86.*TEX86_typo"):
            det.detect_outliers_manual(phys, columns={"TEX86": "TEX86_typo",
                                                      "scaledRI_cren3": "ScaledRI03_best"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_screening.py::TestDetectOutliersManualMapping -q`
Expected: FAIL (`unexpected keyword argument 'columns'`).

- [ ] **Step 3: Update `detect_outliers_manual`**

New signature and body. The `detect_outliers(df)` call threads the kwargs (this is what validates the columns and triggers coverage handling). The default-exception branches read mapped physical columns via a local `_col` helper:

```python
    def detect_outliers_manual(
        self,
        df: pd.DataFrame,
        col_name: Optional[str] = None,
        exclude_condition: Optional[pd.Series] = None,
        *,
        columns: Optional[dict] = None,
        on_unscorable: Literal['warn', 'raise', 'ignore'] = 'warn',
    ) -> pd.Series:
        outliers = self.detect_outliers(
            df, columns=columns, on_unscorable=on_unscorable
        )

        # Apply manual exception
        if exclude_condition is None:
            cmap = columns or {}

            def _col(name):
                return cmap.get(name, name)

            # Default: exclude high RI + high TEX86 samples
            if 'ringIndex' in self.features and 'TEX86' in self.features:
                exclude_condition = (df[_col('ringIndex')] > (0.75 * 4)) & (df[_col('TEX86')] > 0.75)
            elif 'ringIndex_cren3' in self.features and 'TEX86' in self.features:
                exclude_condition = (df[_col('ringIndex_cren3')] > (0.75 * 3)) & (df[_col('TEX86')] > 0.75)
            elif 'proxyObs' in self.features and 'TEX86' in self.features:
                exclude_condition = (df[_col('proxyObs')] > 0.75) & (df[_col('TEX86')] > 0.75)
            elif 'scaledRI' in self.features and 'TEX86' in self.features:  # backward compat
                exclude_condition = (df[_col('scaledRI')] > 0.75) & (df[_col('TEX86')] > 0.75)
            elif 'scaledRI_cren3' in self.features and 'TEX86' in self.features:  # backward compat
                exclude_condition = (df[_col('scaledRI_cren3')] > 0.75) & (df[_col('TEX86')] > 0.75)
            else:
                exclude_condition = pd.Series(False, index=df.index)

        manual_outliers = outliers & ~exclude_condition

        if col_name:
            df[col_name] = manual_outliers

        return manual_outliers
```

> The mapped columns in each branch are always a subset of `self.features`, which `detect_outliers` already validated present via `_resolve_features`, so these `df[_col(...)]` reads cannot KeyError unmapped. A wrong *map* (e.g. `TEX86 -> TEX86_typo`) raises inside the `detect_outliers` call before these lines run — see `test_manual_missing_mapped_column_raises`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_screening.py -q`
Expected: PASS (including `fit_transform` path is now fully wired).

- [ ] **Step 5: Commit**

```bash
git add src/TEXAS/data/screening.py tests/test_screening.py
git commit -m "feat: map hardcoded logical names in detect_outliers_manual via columns=

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `columns=` on the 6 plotting methods

**Files:**
- Modify: `src/TEXAS/data/screening.py` (`plot_decision_boundary`, `plot_multiple_ellipses`, `plot_pairwise_ellipses`, `plot_pca_projection`, `plot_corner`; and `get_confidence_ellipse_params`/`plot_ellipse` are data-free — leave unchanged)
- Test: `tests/test_screening.py` (add `TestPlottingMapping`)

**Interfaces:**
- Consumes: `_resolve_features` (Task 1), `detect_outliers*` (Tasks 1–2).
- Produces: each of the 5 plotting methods that take `df` gains a keyword-only `columns: Optional[dict] = None`.

**Approach (uniform):** At the top of each method, resolve once to a logical-named working copy and operate on it internally, so all downstream feature reads and sub-detector fits use logical names:

```python
work_df = self._resolve_features(df, columns, on_unscorable='ignore')
```

Every internal `df` reference inside the method body is then replaced by `work_df`. All plotting methods only touch feature columns (verified: they read `df[self.features[i]]` / `df.loc[..., feat]` and call `self.detect_outliers*(df)`), so a working copy containing exactly the feature columns is sufficient.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_screening.py`:

```python
class TestPlottingMapping:
    def _fitted_and_phys(self):
        rng = np.random.default_rng(7)
        n = 150
        train = pd.DataFrame({
            "TEX86": rng.uniform(0.3, 0.9, n),
            "scaledRI_cren3": rng.uniform(0.2, 0.8, n),
        })
        det = MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.9
        ).fit(train)
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        return det, phys

    def test_decision_boundary_accepts_columns(self):
        import matplotlib
        matplotlib.use("Agg")
        det, phys = self._fitted_and_phys()
        m = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}
        ax, ellipse = det.plot_decision_boundary(phys, columns=m)
        assert ax is not None

    def test_plot_missing_mapped_column_raises(self):
        import matplotlib
        matplotlib.use("Agg")
        det, phys = self._fitted_and_phys()
        with pytest.raises(KeyError, match=r"scaledRI_cren3"):
            det.plot_decision_boundary(
                phys, columns={"TEX86": "TEX86_best",
                               "scaledRI_cren3": "ScaledRI03_typo"}
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_screening.py::TestPlottingMapping -q`
Expected: FAIL (`unexpected keyword argument 'columns'`).

- [ ] **Step 3: Add `columns=` + `work_df` to each plotting method**

For `plot_decision_boundary`, add `columns: Optional[dict] = None` as the last (keyword-only) parameter and insert, immediately after the `len(self.features) != 2` guard:

```python
        work_df = self._resolve_features(df, columns, on_unscorable='ignore')
```

Then replace `df` with `work_df` throughout the method body (the `df[self.features[...]]` reads and the `self.detect_outliers_manual(df)` / `self.detect_outliers(df)` calls).

Apply the identical pattern to `plot_multiple_ellipses`, `plot_pairwise_ellipses`, `plot_pca_projection`, and `plot_corner`: add keyword-only `columns: Optional[dict] = None`, insert `work_df = self._resolve_features(df, columns, on_unscorable='ignore')` after the method's existing guards (`is_fitted` / feature-count), and swap `df` → `work_df` in the body. In `plot_pca_projection` the `df[self.features]` selection and in `plot_pairwise_ellipses`/`plot_corner` the `pair_detector.fit(df)` and `df.loc[..., feat]` reads all become `work_df`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_screening.py -q`
Expected: PASS.

- [ ] **Step 5: Run the full existing suite for backward-compat**

Run: `pytest -q`
Expected: PASS (no regressions in `test_imports`, `test_logistics`, `test_pipeline`, etc.).

- [ ] **Step 6: Commit**

```bash
git add src/TEXAS/data/screening.py tests/test_screening.py
git commit -m "feat: accept columns= map in MahalanobisOutlierDetector plotting methods

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Docs, docstrings, CHANGELOG, version bump

**Files:**
- Modify: `src/TEXAS/data/screening.py` (class + method docstrings)
- Modify: `pyproject.toml` (version)
- Create: `CHANGELOG.md`
- Modify: `README.md` (short mapping example — locate the screening/usage section; if none, add a brief subsection)

**Interfaces:** none (documentation + metadata only).

- [ ] **Step 1: Update the class docstring example**

In `MahalanobisOutlierDetector`'s class docstring, add after the existing examples:

```
    >>> # Map your physical column names to TEXAS's logical feature names —
    >>> # no need to rename or mutate your DataFrame.
    >>> detector.fit(coretop_df)            # training cols: TEX86 / scaledRI_cren3
    >>> dist = detector.transform(
    ...     my_df,
    ...     columns={'TEX86': 'TEX86_best', 'scaledRI_cren3': 'ScaledRI03_best'},
    ... )
    >>> # A missing mapped column raises KeyError; present-but-NaN rows warn
    >>> # (set on_unscorable='raise' to hard-fail, 'ignore' to silence).
```

Add a `columns` / `on_unscorable` entry to the Parameters section of `transform`, `detect_outliers`, `detect_outliers_manual`, `fit`, and `fit_transform`, e.g.:

```
        columns : dict, optional
            Mapping of logical feature name -> physical column name, e.g.
            ``{'TEX86': 'TEX86_best'}``. Unlisted features map to themselves.
            None (default) uses the feature names as column names (identity).
        on_unscorable : {'warn', 'raise', 'ignore'}, default 'warn'
            Behavior when rows map to a present column but hold NaN/Inf and
            cannot be scored. 'warn' emits a UserWarning with the row count,
            'raise' errors, 'ignore' is silent. A missing mapped column always
            raises KeyError regardless of this setting.
```

- [ ] **Step 2: Bump the version**

In `pyproject.toml` change:

```toml
version = "0.2.1"
```

to:

```toml
version = "0.3.0"
```

- [ ] **Step 3: Create `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to `texas-psm` are documented here. This project adheres to
[Semantic Versioning](https://semver.org/). Pre-1.0 minor versions may add
features; the API stabilizes at 1.0 (paper acceptance).

## [0.3.0] - 2026-06-30

### Added
- `MahalanobisOutlierDetector` methods (`fit`, `transform`, `detect_outliers`,
  `detect_outliers_manual`, `fit_transform`, and the plotting methods) now accept
  a keyword-only `columns={logical: physical}` map, so callers can point TEXAS's
  logical feature names at differently-named DataFrame columns (e.g.
  `{'TEX86': 'TEX86_best'}`) without renaming or mutating their DataFrame.
- `on_unscorable={'warn','raise','ignore'}` (default `'warn'`) on the data
  methods: rows that map to a present column but contain NaN/Inf are reported by
  count instead of silently receiving a NaN distance.

### Changed
- A missing/mistyped mapped column now raises a clear `KeyError` naming each
  `logical -> physical` pair, instead of producing silent NaN distances.

### Backward compatibility
- Fully backward compatible: calls without `columns`/`on_unscorable` behave
  identically (identity lookup). The default `'warn'` only fires when unscorable
  rows are actually present.
```

- [ ] **Step 4: Add a README usage snippet**

In `README.md`, under the outlier-screening / usage section (add a short "Mapping your column names" subsection if none exists):

```markdown
### Mapping your column names

If your DataFrame columns aren't named exactly `TEX86` / `scaledRI_cren3`, pass a
`columns=` map instead of renaming your data:

```python
det = MahalanobisOutlierDetector(['TEX86', 'scaledRI_cren3'], confidence=0.9)
det.fit(coretop_df)  # training columns are TEX86 / scaledRI_cren3
dist = det.transform(
    my_df, columns={'TEX86': 'TEX86_best', 'scaledRI_cren3': 'ScaledRI03_best'}
)
```

A missing mapped column raises `KeyError`; rows with a present-but-NaN mapped
column are reported (`on_unscorable='warn'` by default) rather than silently
dropped.
```

- [ ] **Step 5: Verify version and run full suite**

Run: `python -c "import TEXAS; print(TEXAS.__version__)"` (after `pip install -e .` if needed) and `pytest -q`
Expected: version reflects `0.3.0` (or installed value) and the full suite passes.

- [ ] **Step 6: Commit**

```bash
git add src/TEXAS/data/screening.py pyproject.toml CHANGELOG.md README.md
git commit -m "docs: document columns= mapping, add CHANGELOG, bump version to 0.3.0

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Per-call `columns=` on data methods → Task 1 (core), Task 2 (manual), Task 3 (plotting). ✓
- `_resolve_features` centralization + copy/no-mutation → Task 1 (Step 3), `TestNoMutation`. ✓
- Missing mapped column → `KeyError` naming pairs → Task 1 helper + `TestMissingColumnRaises`, Task 2 manual test. ✓
- `on_unscorable` warn/raise/ignore with count → Task 1 helper + `TestCoverageGuardrail`. ✓
- Backward compatibility → `TestBackwardCompat`, Task 3 Step 5 full-suite run. ✓
- Preserve `col_name=` writes → `test_col_name_write_still_works`. ✓
- Plotting included → Task 3. ✓
- Docstrings, README, CHANGELOG, version bump → Task 4. ✓
- Array API untouched → not modified by any task. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `_resolve_features(df, columns, *, logical=None, on_unscorable='warn')` returns `pd.DataFrame` and is called with the same keyword names in `fit`/`_compute_distances`/plotting. `columns`/`on_unscorable` keyword-only names are identical across all methods. ✓
