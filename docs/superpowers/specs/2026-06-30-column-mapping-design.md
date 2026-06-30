# Design: Decouple logical feature names from physical DataFrame columns

**Date:** 2026-06-30
**Scope:** `src/TEXAS/data/screening.py` — `MahalanobisOutlierDetector`
**Version bump:** `0.2.1` → `0.3.0` (minor, additive feature)

## Problem

`MahalanobisOutlierDetector(features=['TEX86', 'scaledRI_cren3'])` indexes the
caller's DataFrame with the feature names *as* column names (`df['TEX86']`,
`df['scaledRI_cren3']`). Callers whose physical columns differ (e.g.
`TEX86_best`, `ScaledRI03_best`) must hand-alias columns before every call.

This caused a **silent bug**: a forgotten alias made the detector read a column
that was NaN for ~2,900 computed-only samples, yielding NaN Mahalanobis
distances with **no error** — those rows silently received no outlier tag. A
column-name miss yields NaNs, not an exception, so the mismatch was invisible.

## Audit (df-consuming public APIs that index columns by literal name)

`MahalanobisOutlierDetector` is the **only** such API. All other candidates are
already column-agnostic:

- `data/ocean_lookup.py::lookup_no3_from_woa` — lat/lon arrays + xarray dataset.
- `diagnostics.py` — CmdStan fit / xr.Datasets; `R_hat`/`ESS_bulk` are
  CmdStan-fixed names, not caller data.
- `data/builder.py`, `data/filter.py`, `ensemble/*`, `models/*`, `predict.py`,
  `plotting/*`, `stan/*` — numpy arrays / dicts / xarray; `df[...]` appears only
  in docstrings.

Indexing sites inside `MahalanobisOutlierDetector`:
1. **Core path:** `fit` (`df[self.features]`), `_compute_distances`
   (`df[self.features]`; engine behind `transform`/`detect_outliers`/
   `detect_outliers_manual`).
2. **`detect_outliers_manual`:** also indexes hardcoded *logical* names
   (`df['ringIndex']`, `df['TEX86']`, `df['scaledRI_cren3']`, …) for the default
   exception rule.
3. **Plotting:** `plot_decision_boundary`, `plot_multiple_ellipses`,
   `plot_pairwise_ellipses`, `plot_pca_projection`, `plot_corner` index
   `df[self.features[i]]`.

## Design decisions (confirmed)

1. **Mapping location: per-call only.** A `columns: dict[str,str] | None = None`
   parameter on every data-consuming method, default `None` = identity (current
   behavior). `fit()` on TEXAS training data passes nothing; `transform()` /
   `detect_*()` on the caller's data pass the map. Avoids the fit-vs-transform
   asymmetry a constructor-level default would introduce.
2. **Coverage guardrail:** `on_unscorable: {'warn','raise','ignore'} = 'warn'`.
   Counts rows that map to a *present* column but still can't be scored
   (NaN/Inf). Default warns with the count; `'raise'` errors; `'ignore'`
   restores today's fully-silent behavior. A **missing mapped column always
   raises**, independent of this knob.
3. **Plotting included.** The 6 plotting methods accept `columns=` too (they
   share the resolver). They are NaN-tolerant/exploratory, so they suppress the
   coverage warning internally (`on_unscorable='ignore'`) but still raise on a
   missing mapped column.

## Mechanism

A single private helper centralizes all logical→physical translation:

```python
def _resolve_features(
    self,
    df: pd.DataFrame,
    columns: dict[str, str] | None,
    *,
    logical: list[str] | None = None,
    on_unscorable: Literal['warn', 'raise', 'ignore'] = 'warn',
) -> pd.DataFrame:
    """
    Select the feature columns from `df` using a logical→physical map and
    return a COPY whose columns are relabeled back to the logical names.

    - `logical` defaults to `self.features`; callers (e.g. the manual-exception
      builder) may pass a different logical subset.
    - Raises KeyError naming each unresolved `logical→physical` pair if any
      mapped physical column is absent from `df`.
    - After selection, counts rows that are NaN/Inf across the selected columns
      and applies `on_unscorable`.
    - Never mutates `df` (select + `.copy()`; relabel the copy only).
    """
```

Resolution rule per logical name `f`: physical = `(columns or {}).get(f, f)`.

`fit` and `_compute_distances` route `df[self.features]` through
`_resolve_features`. `detect_outliers_manual` resolves its hardcoded logical
names (`ringIndex`, `TEX86`, `scaledRI_cren3`, `proxyObs`, `ringIndex_cren3`,
`scaledRI`) through the same map via `(columns or {}).get(logical, logical)`
when building `exclude_condition`. Plotting methods resolve `self.features`
through the helper, then read the relabeled copy by logical name.

### Method signatures (additive — existing positional/keyword args unchanged)

```python
fit(df, *, columns=None, on_unscorable='warn')
transform(df, col_name=None, *, columns=None, on_unscorable='warn')
detect_outliers(df, col_name=None, *, columns=None, on_unscorable='warn')
detect_outliers_manual(df, col_name=None, exclude_condition=None, *,
                       columns=None, on_unscorable='warn')
fit_transform(df, dist_col=None, outlier_col=None, manual_outlier_col=None, *,
              columns=None, on_unscorable='warn')
# plotting methods: add `columns=None` only (warning suppressed internally)
```

`columns` and `on_unscorable` are keyword-only so they never collide with the
existing positional `col_name`/`*_col` arguments.

### Mutation policy

- The new mapping/selection logic **never mutates** the caller's DataFrame:
  `_resolve_features` does `df[physical].copy()` then relabels the copy.
- The pre-existing `col_name=` / `*_col=` writes (`df[col_name] = ...`) are an
  explicit, opt-in, documented feature and are **preserved unchanged** for
  backward compatibility. They are the only writes, and only when the caller
  asks for them.

## Backward compatibility

- Every existing call with no `columns`/`on_unscorable` argument behaves
  identically: `columns=None` → identity lookup; `on_unscorable='warn'` only
  fires when unscorable rows exist (rows with NaN already silently dropped
  today — now they get a *warning*, not an error, and only when present). To
  guarantee byte-identical behavior for legacy callers who relied on silence,
  the default could be revisited, but per the task the silent-NaN bug is the
  thing we are eliminating, so a default warning is intended and acceptable.
- Regression tests assert identical distances/flags for the no-arg path.

## Testing (TDD — failing tests first)

1. **Mapping correctness:** fitted detector + `transform(my_df, columns=...)`
   produces distances identical to renaming the columns by hand.
2. **Missing mapped column:** `transform(df, columns={'TEX86': 'absent'})`
   raises `KeyError` naming `TEX86 → absent` (not NaNs).
3. **Coverage warning:** a frame with present-but-NaN mapped column emits a
   `UserWarning` with the unscorable row count under default; `'raise'` raises;
   `'ignore'` is silent.
4. **No mutation:** caller DataFrame columns/values unchanged after
   `transform`/`detect_*` with a map (snapshot equality).
5. **Backward compat:** all existing no-`columns` calls return identical results
   (distances, outlier flags, manual flags); existing suite stays green.
6. **End-to-end realistic case:** fit on `TEX86`/`scaledRI_cren3` training
   frame; transform a `TEX86_best`/`ScaledRI03_best` frame via `columns=` →
   finite distance for every fully-populated row; missing mapped column raises.

## Docs & release

- Docstrings: add `columns=` / `on_unscorable=` with a worked example using a
  physical-column frame.
- README / usage docs: short "mapping your column names" example.
- New `CHANGELOG.md` with a `0.3.0` entry (additive `columns=` mapping +
  coverage guardrail).
- Bump `pyproject.toml` version `0.2.1` → `0.3.0`.

## Out of scope (unchanged)

Array-based prediction API (`predict_T_from_proxyObs`, `predict_proxy_from_T`,
`compute_scaledRI`, `build_invT_inputData`) — already column-agnostic.
