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
