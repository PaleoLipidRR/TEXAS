"""Group C — spatially-blocked cross-validation of forward calibration skill.

Reviewers R2 and R3 asked TEXAS to support the claim that it "outperforms all
existing calibrations" with **out-of-sample, spatially-independent** skill rather
than the in-sample R2/RMSE reported in Group A. Random k-fold CV is optimistic
here: coretop sites are spatially autocorrelated, so a randomly held-out site
usually has a near neighbour in the training set. Blocking the folds by geography
breaks that leakage (Roberts et al. 2017, *Ecography*).

This module splits into three concerns so the expensive part is isolated:

1. **Fold assignment** (pure, no Stan/optional deps):
   - :func:`assign_block_folds` — bin sites into equal-area lon/lat blocks and
     deal whole blocks into ``k`` folds (spatial block CV; pure NumPy).
   - :func:`assign_ocean_basin_folds` — leave-one-ocean-basin-out via
     ``regionmask`` (reuses the basin definition behind the residual maps).
   - :func:`make_folds` — turn a fold-id array into leave-one-fold-out splits.

2. **Held-out scoring** (pure): :func:`heldout_scores` turns a
   ``(draw, site)`` matrix of held-out predictions into R2/RMSE **credible
   intervals** (per posterior draw), and :func:`fold_score_table` assembles a
   tidy per-fold + pooled table.

3. **Orchestration** (heavy, lazily imported): :func:`crossval_fold` refits the
   forward model on a fold's training sites and predicts its held-out sites;
   :func:`run_spatial_crossval` loops the folds with per-fold checkpointing so an
   hours-scale run is resumable. These call ``build_fwd_data`` /
   ``get_posterior`` / ``predict_proxy_from_T`` and are meant to run from
   ``scripts/revision1/``, not a notebook.

Everything is array-based (no hardcoded DataFrame column names) so it composes
with the variable-name-agnostic API work (Group D).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import xarray as xr

from .intervals import credible_interval

__all__ = [
    "SpatialFold",
    "assign_block_folds",
    "assign_ocean_basin_folds",
    "make_folds",
    "heldout_scores",
    "fold_score_table",
    "crossval_fold",
    "run_spatial_crossval",
]


# --------------------------------------------------------------------------- #
# 1. Fold assignment
# --------------------------------------------------------------------------- #
@dataclass
class SpatialFold:
    """One leave-one-block-out split.

    ``train_idx`` / ``test_idx`` index into the original site arrays. The held-out
    block is ``test_idx``; everything else (in a valid, non-NaN block) is
    ``train_idx``.
    """

    fold_id: int
    label: str
    train_idx: np.ndarray
    test_idx: np.ndarray

    @property
    def n_train(self) -> int:
        return int(self.train_idx.size)

    @property
    def n_test(self) -> int:
        return int(self.test_idx.size)


def assign_block_folds(
    lons: np.ndarray,
    lats: np.ndarray,
    *,
    block_deg: float = 20.0,
    n_folds: int = 5,
    seed: int = 42,
) -> np.ndarray:
    """Assign each site to one of ``n_folds`` spatial-block folds.

    Sites are binned into ``block_deg`` × ``block_deg`` lon/lat blocks; each
    *block* (not each site) is dealt to a fold, so spatially-adjacent sites share
    a fold and a held-out fold is geographically separated from its training set.
    Blocks are shuffled with ``seed`` and dealt round-robin, which keeps fold
    sizes close to balanced without splitting any block across folds.

    Sites with non-finite ``lon``/``lat`` receive fold id ``-1`` (excluded).

    Returns:
        Integer array of fold ids, one per site, in ``{-1, 0, ..., n_folds-1}``.
    """
    lons = np.asarray(lons, dtype=float)
    lats = np.asarray(lats, dtype=float)
    if lons.shape != lats.shape:
        raise ValueError(f"lons {lons.shape} and lats {lats.shape} must match")
    if n_folds < 2:
        raise ValueError(f"n_folds must be >= 2, got {n_folds}")

    folds = np.full(lons.shape, -1, dtype=int)
    finite = np.isfinite(lons) & np.isfinite(lats)
    if not finite.any():
        return folds

    # Block indices on a regular grid, computed only for finite sites (casting a
    # NaN to int is undefined). Longitude wrapped to [0, 360) so the antimeridian
    # does not create a spurious half-width block.
    bx = np.floor((lons[finite] % 360.0) / block_deg).astype(int)
    by = np.floor((lats[finite] + 90.0) / block_deg).astype(int)

    # Unique blocks among finite sites, in a deterministic order, then shuffled.
    keys = np.stack([bx, by], axis=1)
    uniq, inverse = np.unique(keys, axis=0, return_inverse=True)
    order = np.random.default_rng(seed).permutation(uniq.shape[0])
    block_fold = np.empty(uniq.shape[0], dtype=int)
    block_fold[order] = np.arange(uniq.shape[0]) % n_folds

    folds[finite] = block_fold[inverse]
    return folds


def assign_ocean_basin_folds(
    lons: np.ndarray, lats: np.ndarray
) -> tuple[np.ndarray, dict[int, str]]:
    """Leave-one-ocean-basin-out fold ids via ``regionmask``.

    Uses the same Natural Earth v5 ocean-basin definition as the residual maps,
    so a fold corresponds to a named basin (North Atlantic, etc.). Sites outside
    every basin, or with non-finite coordinates, get fold id ``-1``.

    Returns:
        ``(fold_ids, labels)`` where ``labels`` maps each fold id to its basin
        name.

    Raises:
        ImportError: if ``regionmask`` is not installed.
    """
    try:
        import regionmask
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise ImportError(
            "assign_ocean_basin_folds needs regionmask. Install it with "
            "`conda install -c conda-forge regionmask` or use assign_block_folds, "
            "which has no extra dependencies."
        ) from exc

    lons = np.asarray(lons, dtype=float)
    lats = np.asarray(lats, dtype=float)
    basins = regionmask.defined_regions.natural_earth_v5_0_0.ocean_basins_50
    ids = basins.mask(
        xr.DataArray(lons, dims="site"), xr.DataArray(lats, dims="site")
    ).values

    folds = np.full(lons.shape, -1, dtype=int)
    labels: dict[int, str] = {}
    number_to_name = dict(zip(basins.numbers, basins.names))
    present = [int(n) for n in np.unique(ids[np.isfinite(ids)])]
    for new_id, basin_number in enumerate(present):
        folds[ids == basin_number] = new_id
        labels[new_id] = number_to_name.get(basin_number, f"basin_{basin_number}")
    return folds, labels


def make_folds(
    fold_ids: np.ndarray,
    labels: "dict[int, str] | None" = None,
    *,
    min_test: int = 2,
) -> list[SpatialFold]:
    """Build leave-one-fold-out splits from a fold-id array.

    A held-out fold with fewer than ``min_test`` sites is skipped (you cannot
    score R2 on <2 points); its sites still appear in the training set of the
    other folds. Sites with fold id ``-1`` are never held out but are always
    excluded from training (they were unassignable).

    Returns:
        One :class:`SpatialFold` per retained fold, ordered by fold id.
    """
    fold_ids = np.asarray(fold_ids, dtype=int)
    all_idx = np.arange(fold_ids.size)
    assignable = fold_ids >= 0
    out: list[SpatialFold] = []
    for fid in sorted(set(int(f) for f in fold_ids[assignable])):
        test_idx = all_idx[fold_ids == fid]
        if test_idx.size < min_test:
            continue
        train_idx = all_idx[assignable & (fold_ids != fid)]
        label = (labels or {}).get(fid, f"fold_{fid}")
        out.append(SpatialFold(fid, label, train_idx, test_idx))
    if not out:
        raise ValueError(
            f"no fold has >= {min_test} held-out sites "
            f"(fold sizes: {np.bincount(fold_ids[assignable]) if assignable.any() else 'none'})"
        )
    return out


# --------------------------------------------------------------------------- #
# 2. Held-out scoring
# --------------------------------------------------------------------------- #
def _r2_rmse_per_draw(
    observed: np.ndarray, predicted_draws: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """R2 and RMSE for each posterior draw. Shapes: (N,) and (D, N) -> (D,), (D,)."""
    observed = np.asarray(observed, dtype=float)
    predicted_draws = np.asarray(predicted_draws, dtype=float)
    if predicted_draws.ndim != 2:
        raise ValueError(f"predicted_draws must be 2-D (draw, site), got {predicted_draws.shape}")
    if predicted_draws.shape[1] != observed.shape[0]:
        raise ValueError(
            f"predicted_draws sites {predicted_draws.shape[1]} != observed {observed.shape[0]}"
        )
    valid = np.isfinite(observed)
    if valid.sum() < 2:
        raise ValueError("need >= 2 finite observed values to score a fold")
    obs = observed[valid]
    pred = predicted_draws[:, valid]

    resid = pred - obs[None, :]
    ss_res = np.sum(resid**2, axis=1)
    ss_tot = np.sum((obs - obs.mean()) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.full(pred.shape[0], np.nan)
    rmse = np.sqrt(np.mean(resid**2, axis=1))
    return r2, rmse


def heldout_scores(
    observed: np.ndarray,
    predicted_draws: np.ndarray,
    *,
    level: float = 0.95,
) -> xr.Dataset:
    """Out-of-sample R2 / RMSE with credible intervals from held-out predictions.

    ``predicted_draws`` is the held-out prediction ensemble, shape
    ``(draw, site)`` — one prediction per site for each posterior draw (e.g. the
    ``"ensemble"`` array from :func:`TEXAS.predict.predict_proxy_from_T`). A
    metric is computed *per draw*, so the resulting interval propagates
    calibration uncertainty into the held-out skill, mirroring the in-sample
    treatment in :mod:`TEXAS.validation.metrics`.

    Returns:
        Dataset indexed by a ``metric`` coordinate (``R2``, ``RMSE``) with
        ``mean``/``lower``/``median``/``upper`` and an ``n_test`` attr.
    """
    r2, rmse = _r2_rmse_per_draw(observed, predicted_draws)
    rows = {"mean": [], "lower": [], "median": [], "upper": []}
    for series in (r2, rmse):
        ci = credible_interval(xr.DataArray(series, dims="draw"), level=level)
        for k in rows:
            rows[k].append(float(ci[k]))
    out = xr.Dataset(
        {k: ("metric", np.asarray(v)) for k, v in rows.items()},
        coords={"metric": ["R2", "RMSE"]},
    )
    out.attrs["interval_level"] = level
    out.attrs["interval_kind"] = "credible"
    out.attrs["sample"] = "out-of-sample (spatially-blocked CV)"
    out.attrs["n_test"] = int(np.isfinite(np.asarray(observed, float)).sum())
    return out


def fold_score_table(
    fold_scores: "dict[str, xr.Dataset]",
    *,
    pooled: "xr.Dataset | None" = None,
    sig: int = 3,
) -> pd.DataFrame:
    """Assemble per-fold (and optional pooled) held-out scores into a tidy table.

    Args:
        fold_scores: Mapping ``fold label -> heldout_scores() Dataset``.
        pooled: Optional overall :func:`heldout_scores` output (all held-out
            sites at once) added as a final ``"POOLED"`` row.
        sig: Significant figures for the ``"… [lo, hi]"`` string columns.

    Returns:
        DataFrame indexed by fold label with numeric median columns plus
        formatted ``R2`` / ``RMSE`` credible-interval strings.
    """
    def _fmt(ds: xr.Dataset, metric: str) -> str:
        s = ds.sel(metric=metric)
        return (
            f"{float(s['median']):.{sig}g} "
            f"[{float(s['lower']):.{sig}g}, {float(s['upper']):.{sig}g}]"
        )

    records = {}
    items = list(fold_scores.items())
    if pooled is not None:
        items.append(("POOLED", pooled))
    for label, ds in items:
        records[label] = {
            "n_test": int(ds.attrs.get("n_test", 0)),
            "R2_median": float(ds.sel(metric="R2")["median"]),
            "RMSE_median": float(ds.sel(metric="RMSE")["median"]),
            "R2": _fmt(ds, "R2"),
            "RMSE": _fmt(ds, "RMSE"),
        }
    df = pd.DataFrame.from_dict(records, orient="index")
    df.index.name = "fold"
    return df


# --------------------------------------------------------------------------- #
# 3. Orchestration (heavy — lazily imports Stan / predict machinery)
# --------------------------------------------------------------------------- #
@dataclass
class CrossvalArrays:
    """Site-level inputs for a cross-validation run (all aligned, length N).

    Predictor arrays are optional; pass only those the target model uses. Keeping
    inputs as arrays (not a column-named DataFrame) is deliberate — it avoids the
    hardcoded-name coupling flagged in the Group D API work.
    """

    t: np.ndarray                     # temperatures (SST or thermoT), °C
    proxy: np.ndarray                 # proxy observations (e.g. scaled RI)
    lons: np.ndarray
    lats: np.ndarray
    gdgt23ratio: "np.ndarray | None" = None
    no3: "np.ndarray | None" = None
    sd_proxy: "np.ndarray | None" = None
    sd_gdgt23ratio: "np.ndarray | None" = None
    sd_no3: "np.ndarray | None" = None
    extra_builder_kwargs: dict = field(default_factory=dict)

    def _slice(self, idx: np.ndarray) -> dict:
        def s(a):
            return None if a is None else np.asarray(a)[idx]

        d = dict(
            t_crtp=s(self.t),
            proxy_crtp=s(self.proxy),
            gdgt23ratio_crtp=s(self.gdgt23ratio),
            no3_crtp=s(self.no3),
            sd_proxyObs=s(self.sd_proxy),
            sd_gdgt23ratio_crtp=s(self.sd_gdgt23ratio),
            sd_no3_crtp=s(self.sd_no3),
        )
        return {k: v for k, v in d.items() if v is not None}


def crossval_fold(
    fold: SpatialFold,
    arrays: CrossvalArrays,
    *,
    stan_file: str,
    temptype: str,
    proxy_name: str,
    culmeso_posterior: "xr.Dataset | None" = None,
    R2_thermal: "float | None" = None,
    n_draws: int = 500,
    seed: int = 42,
    sampler_kwargs: "dict | None" = None,
) -> dict:
    """Refit the forward model on a fold's training sites and predict its held-out sites.

    Forward held-out skill only (the clean, defensible out-of-sample metric):
    the calibration curve is refit without the held-out block, then evaluated at
    each held-out site's true temperature to predict its proxy, giving a
    ``(draw, site)`` ensemble scored by :func:`heldout_scores`. Inverse
    (proxy→T) held-out skill is a heavier, separate invT run — see the note in
    :func:`run_spatial_crossval`.

    Returns a dict with the refit ``posterior`` (xr.Dataset), the held-out
    ``observed`` proxy, the ``predicted_draws`` ensemble, and the fold metadata.
    """
    from ..data.builder import build_fwd_data
    from ..predict import predict_proxy_from_T
    from ..stan.sampler import get_posterior

    train = arrays._slice(fold.train_idx)
    if culmeso_posterior is not None:
        train["culmeso_posterior"] = culmeso_posterior
    if R2_thermal is not None:
        train["R2_thermal"] = R2_thermal
    train.update(arrays.extra_builder_kwargs)

    data = build_fwd_data(**train)
    posterior, _ = get_posterior(
        data, stan_file, temptype=temptype, proxy_name=proxy_name,
        **(sampler_kwargs or {}),
    )

    t_test = np.asarray(arrays.t)[fold.test_idx]
    fwd = predict_proxy_from_T(
        t_test,
        posterior,
        n_draws=n_draws,
        return_full=True,
        seed=seed,
        gdgt23ratio=None if arrays.gdgt23ratio is None else np.asarray(arrays.gdgt23ratio)[fold.test_idx],
        no3=None if arrays.no3 is None else np.asarray(arrays.no3)[fold.test_idx],
    )
    return {
        "fold_id": fold.fold_id,
        "label": fold.label,
        "n_train": fold.n_train,
        "n_test": fold.n_test,
        "observed": np.asarray(arrays.proxy)[fold.test_idx],
        "predicted_draws": np.asarray(fwd["ensemble"]),  # (n_draws, n_test)
        "posterior": posterior,
    }


def run_spatial_crossval(
    arrays: CrossvalArrays,
    folds: list[SpatialFold],
    *,
    stan_file: str,
    temptype: str,
    proxy_name: str,
    group: str = "groupC",
    level: float = 0.95,
    save_posteriors: bool = True,
    reviewer: str = "R2,R3:spatial-crossval",
    **fold_kwargs,
) -> pd.DataFrame:
    """Run leave-one-block-out CV over ``folds``, checkpointing and scoring each.

    Each fold is refit and scored independently; its held-out predictions and the
    per-fold score are persisted under ``data/revision1/<group>/`` via
    :mod:`TEXAS.validation.io`, so an interrupted hours-scale run resumes by
    skipping folds whose checkpoint already exists. A pooled score over all
    held-out sites (median prediction per site) is appended.

    .. note::
       This scores **forward** (T→proxy) held-out skill. Inverse (proxy→T) skill
       is reported separately (reviewer R1/R2 asked for both): run
       :func:`TEXAS.predict.predict_T_from_proxyObs` per held-out site against
       each fold's refit posterior and feed its temperature draws to
       :func:`heldout_scores`. That path is invT-heavy and left to the batch
       driver in ``scripts/revision1/``.

    Returns:
        The tidy :func:`fold_score_table` (per-fold rows + a ``POOLED`` row).
    """
    from .io import load_result, save_result

    fold_scores: dict[str, xr.Dataset] = {}
    pooled_obs: list[np.ndarray] = []
    pooled_pred_median: list[np.ndarray] = []

    for fold in folds:
        ckpt = f"fold{fold.fold_id}_{_slug(fold.label)}"
        try:
            cached = load_result(ckpt, group=group)
            observed = cached["observed"].values
            predicted_draws = cached["predicted_draws"].values
        except FileNotFoundError:
            res = crossval_fold(
                fold, arrays, stan_file=stan_file, temptype=temptype,
                proxy_name=proxy_name, **fold_kwargs,
            )
            observed = res["observed"]
            predicted_draws = res["predicted_draws"]
            _checkpoint = xr.Dataset(
                {
                    "observed": ("site", np.asarray(observed)),
                    "predicted_draws": (("draw", "site"), np.asarray(predicted_draws)),
                },
                attrs={"label": fold.label, "n_train": fold.n_train},
            )
            save_result(
                _checkpoint, ckpt, group=group, reviewer=reviewer,
                config={"fold_id": fold.fold_id, "label": fold.label,
                        "stan_file": stan_file, "temptype": temptype},
            )
            if save_posteriors:
                from ..stan.io import save_posterior
                save_posterior(res["posterior"], filename_suffix=ckpt)

        score = heldout_scores(observed, predicted_draws, level=level)
        fold_scores[fold.label] = score
        save_result(score, f"{ckpt}_score", group=group, reviewer=reviewer,
                    config={"fold_id": fold.fold_id})
        pooled_obs.append(np.asarray(observed))
        pooled_pred_median.append(np.median(np.asarray(predicted_draws), axis=0))

    # Pooled skill: median held-out prediction per site, concatenated across folds.
    obs_all = np.concatenate(pooled_obs)
    pred_all = np.concatenate(pooled_pred_median)[None, :]  # single "draw" = medians
    pooled = heldout_scores(obs_all, pred_all, level=level)
    pooled.attrs["note"] = "point estimate over per-site median predictions"

    table = fold_score_table(fold_scores, pooled=pooled)
    save_result(table, "crossval_summary", group=group, reviewer=reviewer,
                config={"stan_file": stan_file, "temptype": temptype,
                        "proxy_name": proxy_name, "n_folds": len(folds)})
    return table


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text).strip("_").lower()
