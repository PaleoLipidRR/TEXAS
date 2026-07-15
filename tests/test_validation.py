"""Tests for the revision-1 analysis workflow (TEXAS.validation), Group A.

Uses synthetic posterior-like Datasets so it runs in CI without downloading the
real (78 MB) posteriors. Exercises the credible-interval reduction, the metric
and noise-term summaries, variable-absence handling, and the NetCDF/CSV result
persistence round-trip.
"""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from TEXAS import validation as V


def _fake_posterior(seed: int = 0) -> xr.Dataset:
    """A minimal forward posterior: (chain, draw) metrics + noise scalars."""
    rng = np.random.default_rng(seed)
    dims = ("chain", "draw")
    shape = (4, 250)
    return xr.Dataset(
        {
            "R2_full": (dims, rng.normal(0.75, 0.01, shape)),
            "bayesR2_full": (dims, rng.normal(0.75, 0.02, shape)),
            "RMSE_full": (dims, rng.normal(0.058, 0.002, shape)),
            "sigma_proxyObs_crtp": (dims, np.abs(rng.normal(0.058, 0.002, shape))),
        },
        attrs={"proxy_name": "scaledRI", "stan_diag_max_rhat": 1.001},
    )


def test_credible_interval_ordering_and_level():
    ds = _fake_posterior()
    ci = V.credible_interval(ds["R2_full"], level=0.95)
    assert float(ci["lower"]) <= float(ci["median"]) <= float(ci["upper"])
    assert ci.attrs["interval_level"] == 0.95
    assert ci.attrs["interval_kind"] == "credible"


def test_credible_interval_rejects_unknown_level():
    ds = _fake_posterior()
    with pytest.raises(ValueError):
        V.credible_interval(ds["R2_full"], level=0.5)


def test_summarize_calibration_metrics():
    ds = _fake_posterior()
    m = V.summarize_calibration_metrics(ds, level=0.95)
    assert set(m["metric"].values) == set(V.CALIBRATION_METRICS)
    r2 = m.sel(metric="R2_full")
    assert 0.7 < float(r2["median"]) < 0.8
    assert m.attrs["sample"].startswith("in-sample")


def test_summarize_noise_terms_skips_absent():
    ds = _fake_posterior()  # only sigma_proxyObs_crtp present
    n = V.summarize_noise_terms(ds)
    assert list(n["parameter"].values) == ["sigma_proxyObs_crtp"]
    assert str(n.sel(parameter="sigma_proxyObs_crtp")["kind"].values) == "observation"


def test_summarize_raises_when_nothing_present():
    empty = xr.Dataset({"unrelated": (("chain", "draw"), np.zeros((2, 5)))})
    with pytest.raises(ValueError):
        V.summarize_calibration_metrics(empty)


def test_save_and_load_netcdf_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXAS_REVISION_RESULTS_DIR", str(tmp_path))
    ds = _fake_posterior()
    m = V.summarize_calibration_metrics(ds)
    path = V.save_result(m, "metrics_test", group="groupA", reviewer="R3:test",
                         config={"posterior": "fake"})
    assert path.exists() and path.suffix == ".nc"
    back = V.load_result("metrics_test", group="groupA")
    assert set(back["metric"].values) == set(V.CALIBRATION_METRICS)
    # provenance attrs are attached
    assert back.attrs["reviewer_comment"] == "R3:test"
    assert "texas_version" in back.attrs and "created_utc" in back.attrs


def test_save_dataframe_writes_csv_and_meta(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXAS_REVISION_RESULTS_DIR", str(tmp_path))
    df = pd.DataFrame({"a": [1, 2]}, index=["x", "y"])
    path = V.save_result(df, "table_test", group="groupA", reviewer="R2:diag")
    assert path.suffix == ".csv"
    assert (path.parent / "table_test.meta.json").exists()
    back = V.load_result("table_test", group="groupA")
    assert list(back["a"]) == [1, 2]


def test_list_results(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXAS_REVISION_RESULTS_DIR", str(tmp_path))
    ds = _fake_posterior()
    V.save_result(V.summarize_noise_terms(ds), "n", group="groupA")
    found = V.list_results("groupA")
    assert any(p.name == "n.nc" for p in found)


# --------------------------------------------------------------------------- #
# Group C — spatially-blocked cross-validation (pure core, no Stan)
# --------------------------------------------------------------------------- #
def test_block_folds_keep_blocks_together():
    # Two clusters, each well inside one 20-deg block (away from block edges) and
    # far apart -> each cluster lands in a single block, never split across folds.
    lons = np.array([-49.0, -48.0, -47.0, 141.0, 142.0, 143.0])
    lats = np.array([22.0, 24.0, 26.0, -29.0, -27.0, -25.0])
    folds = V.assign_block_folds(lons, lats, block_deg=20.0, n_folds=2, seed=1)
    assert len(set(folds[:3])) == 1  # Atlantic cluster shares a fold
    assert len(set(folds[3:])) == 1  # Pacific cluster shares a fold
    assert folds[0] != folds[3]      # the two blocks land in different folds


def test_block_folds_mark_nonfinite_excluded():
    lons = np.array([10.0, np.nan, 20.0])
    lats = np.array([10.0, 5.0, np.nan])
    folds = V.assign_block_folds(lons, lats, n_folds=2)
    assert folds[1] == -1 and folds[2] == -1
    assert folds[0] >= 0


def test_make_folds_leave_one_out_and_min_test():
    fold_ids = np.array([0, 0, 0, 1, 1, 2])  # fold 2 has a single site
    folds = V.make_folds(fold_ids, min_test=2)
    labels = {f.fold_id for f in folds}
    assert labels == {0, 1}  # fold 2 dropped (n_test < 2)
    f0 = next(f for f in folds if f.fold_id == 0)
    assert f0.n_test == 3 and set(f0.test_idx) == {0, 1, 2}
    # the dropped fold's site (index 5) still trains the others
    assert 5 in set(f0.train_idx)
    # train and test never overlap
    assert not (set(f0.train_idx) & set(f0.test_idx))


def test_make_folds_raises_when_all_too_small():
    with pytest.raises(ValueError):
        V.make_folds(np.array([0, 1, 2]), min_test=2)


def test_heldout_scores_perfect_and_noisy():
    rng = np.random.default_rng(0)
    observed = rng.normal(0.5, 0.1, 40)
    # Perfect predictions across all draws -> R2 = 1, RMSE = 0.
    perfect = np.tile(observed, (100, 1))
    s = V.heldout_scores(observed, perfect)
    assert abs(float(s.sel(metric="R2")["median"]) - 1.0) < 1e-9
    assert float(s.sel(metric="RMSE")["median"]) < 1e-9
    assert s.attrs["n_test"] == 40
    assert s.attrs["sample"].startswith("out-of-sample")
    # Noisy predictions -> R2 below 1, interval ordered.
    noisy = observed[None, :] + rng.normal(0, 0.05, (100, 40))
    s2 = V.heldout_scores(observed, noisy)
    r2 = s2.sel(metric="R2")
    assert float(r2["lower"]) <= float(r2["median"]) <= float(r2["upper"])
    assert float(r2["median"]) < 1.0


def test_heldout_scores_shape_validation():
    with pytest.raises(ValueError):
        V.heldout_scores(np.zeros(5), np.zeros((10, 4)))  # site mismatch


def test_fold_score_table_with_pooled():
    obs = np.linspace(0, 1, 20)
    draws = obs[None, :] + np.random.default_rng(1).normal(0, 0.02, (50, 20))
    s = V.heldout_scores(obs, draws)
    table = V.fold_score_table({"North Atlantic": s}, pooled=s)
    assert "North Atlantic" in table.index and "POOLED" in table.index
    assert "R2" in table.columns and "RMSE_median" in table.columns
    assert table.loc["North Atlantic", "n_test"] == 20
