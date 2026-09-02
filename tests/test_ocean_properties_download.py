"""
The WOA23 ocean_prop_ds field: registered for lazy Zenodo download, and
predict_T_from_proxyObs(site_lat=, site_lon=) fetches it automatically when
no3_dataset is omitted.

Network is always mocked here — these never hit Zenodo for real.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

import TEXAS.utils.download as download_mod
from TEXAS.utils.download import (
    TRAINING_DATA_REGISTRY,
    download_ocean_properties,
)
from TEXAS.data.ocean_lookup import get_ocean_prop_ds
import TEXAS.predict as predict_mod


# ─── Registry entry ─────────────────────────────────────────────────────────

def test_ocean_prop_ds_is_registered():
    assert "ocean_prop_ds" in TRAINING_DATA_REGISTRY
    entry = TRAINING_DATA_REGISTRY["ocean_prop_ds"]
    assert entry["filename"] == "ds06_calculated_ocean_properties.nc"
    # too big to bundle in the wheel (see test_bundled_posteriors.py's 5 MB
    # ceiling) but small enough that "download on first use" is reasonable
    assert 1 < entry["size_mb"] < 50
    # Hosted on the companion GRL paper's own Zenodo record, not the TEXAS
    # project's record (download_mod.ZENODO_RECORD_ID) -- this file is never
    # uploaded/re-hosted by TEXAS's own release tooling.
    assert entry["record"] == download_mod._GRL_PAPER_RECORD_ID
    assert entry["record"] != download_mod.ZENODO_RECORD_ID


def test_ocean_prop_ds_exported_from_top_level():
    import TEXAS
    assert "download_ocean_properties" in TEXAS.__all__
    assert "get_ocean_prop_ds" in TEXAS.__all__
    assert callable(TEXAS.download_ocean_properties)
    assert callable(TEXAS.get_ocean_prop_ds)


# ─── download_ocean_properties() ────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, data: bytes):
        self._data = data
        self.status = 200

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_download_ocean_properties_skips_when_cached(monkeypatch, tmp_path):
    entry = TRAINING_DATA_REGISTRY["ocean_prop_ds"]
    cached = tmp_path / entry["filename"]
    cached.write_bytes(b"already here")

    def _boom(*a, **kw):
        raise AssertionError("must not hit the network when already cached")

    monkeypatch.setattr(download_mod.urllib.request, "urlopen", _boom)

    out = download_ocean_properties(dest_dir=tmp_path)
    assert out == cached
    assert cached.read_bytes() == b"already here"  # untouched


def test_download_ocean_properties_fetches_when_missing(monkeypatch, tmp_path):
    entry = TRAINING_DATA_REGISTRY["ocean_prop_ds"]
    seen_urls = []

    def _fake_urlopen(url):
        seen_urls.append(url)
        return _FakeResponse(b"fake netcdf bytes")

    monkeypatch.setattr(download_mod.urllib.request, "urlopen", _fake_urlopen)

    out = download_ocean_properties(dest_dir=tmp_path)
    assert out == tmp_path / entry["filename"]
    assert out.read_bytes() == b"fake netcdf bytes"
    assert len(seen_urls) == 1
    assert entry["filename"] in seen_urls[0]
    assert "zenodo.org" in seen_urls[0]
    # Pulled from the pinned GRL-paper record, not the main TEXAS record.
    assert f"/records/{download_mod._GRL_PAPER_RECORD_ID}/" in seen_urls[0]
    assert f"/records/{download_mod.ZENODO_RECORD_ID}/" not in seen_urls[0]


def test_download_ocean_properties_force_redownloads(monkeypatch, tmp_path):
    entry = TRAINING_DATA_REGISTRY["ocean_prop_ds"]
    cached = tmp_path / entry["filename"]
    cached.write_bytes(b"stale")

    monkeypatch.setattr(
        download_mod.urllib.request, "urlopen",
        lambda url: _FakeResponse(b"fresh"),
    )

    out = download_ocean_properties(dest_dir=tmp_path, force=True)
    assert out.read_bytes() == b"fresh"


def test_download_training_data_also_uses_the_pinned_record(monkeypatch, tmp_path):
    # download_training_data() sweeps the whole registry, including
    # ocean_prop_ds -- it must honor that entry's "record" pin too, not just
    # download_ocean_properties()'s dedicated path.
    from TEXAS.utils.download import download_training_data, TRAINING_DATA_REGISTRY as REG

    seen_urls = []

    def _fake_urlopen(url):
        seen_urls.append(url)
        return _FakeResponse(b"x")

    monkeypatch.setattr(download_mod.urllib.request, "urlopen", _fake_urlopen)
    download_training_data(dest_dir=tmp_path)

    ocean_urls = [u for u in seen_urls if "ds06_calculated_ocean_properties.nc" in u]
    assert len(ocean_urls) == 1
    assert f"/records/{REG['ocean_prop_ds']['record']}/" in ocean_urls[0]


# ─── get_ocean_prop_ds() ─────────────────────────────────────────────────────

def _write_fake_ocean_prop_ds(path: Path) -> None:
    ds = xr.Dataset(
        {"no3_sf2tc_avg": (("lat", "lon"), np.full((3, 3), 5.0))},
        coords={"lat": [-10.0, 0.0, 10.0], "lon": [-10.0, 0.0, 10.0]},
    )
    ds.to_netcdf(path)


def test_get_ocean_prop_ds_downloads_and_opens(monkeypatch, tmp_path):
    nc_path = tmp_path / "ds06_calculated_ocean_properties.nc"
    _write_fake_ocean_prop_ds(nc_path)

    called = {}

    def _fake_download(dest_dir=None, force=False):
        called["dest_dir"] = dest_dir
        called["force"] = force
        return nc_path

    # get_ocean_prop_ds imports download_ocean_properties lazily from
    # TEXAS.utils.download inside the function body, so patch it there.
    monkeypatch.setattr(download_mod, "download_ocean_properties", _fake_download)

    ds = get_ocean_prop_ds(cache_dir=tmp_path)
    assert called == {"dest_dir": tmp_path, "force": False}
    assert "no3_sf2tc_avg" in ds
    assert float(ds["no3_sf2tc_avg"].isel(lat=1, lon=1)) == 5.0


# ─── predict_T_from_proxyObs wiring ─────────────────────────────────────────

class _WiringReached(Exception):
    """Sentinel raised once lookup_no3_from_woa receives the auto-downloaded ds."""


def _fake_lookup_no3_from_woa(*, lat, lon, woa_dataset, variable):
    raise _WiringReached(f"reached with variable={variable!r}")


def test_predict_T_from_proxyObs_auto_downloads_when_no3_dataset_omitted(monkeypatch):
    fake_ds = xr.Dataset({"no3_sf2tc_avg": (("lat", "lon"), np.zeros((2, 2)))},
                          coords={"lat": [0.0, 1.0], "lon": [0.0, 1.0]})
    calls = {"n": 0}

    def _fake_get_ocean_prop_ds():
        calls["n"] += 1
        return fake_ds

    monkeypatch.setattr(predict_mod, "get_ocean_prop_ds", _fake_get_ocean_prop_ds)
    monkeypatch.setattr(predict_mod, "lookup_no3_from_woa", _fake_lookup_no3_from_woa)

    with pytest.raises(_WiringReached):
        predict_mod.predict_T_from_proxyObs(
            proxyObs=np.array([0.5]),
            prior_mu_t=20.0,
            prior_sigma_t=10.0,
            site_lat=0.5,
            site_lon=0.5,
        )
    assert calls["n"] == 1


def test_predict_T_from_proxyObs_skips_download_when_no3_dataset_given(monkeypatch):
    explicit_ds = xr.Dataset({"no3_sf2tc_avg": (("lat", "lon"), np.zeros((2, 2)))},
                              coords={"lat": [0.0, 1.0], "lon": [0.0, 1.0]})

    def _boom():
        raise AssertionError("must not auto-download when no3_dataset is given")

    monkeypatch.setattr(predict_mod, "get_ocean_prop_ds", _boom)
    monkeypatch.setattr(predict_mod, "lookup_no3_from_woa", _fake_lookup_no3_from_woa)

    with pytest.raises(_WiringReached):
        predict_mod.predict_T_from_proxyObs(
            proxyObs=np.array([0.5]),
            prior_mu_t=20.0,
            prior_sigma_t=10.0,
            site_lat=0.5,
            site_lon=0.5,
            no3_dataset=explicit_ds,
        )


def test_predict_T_from_proxyObs_raises_actionable_error_on_download_failure(monkeypatch):
    def _fake_get_ocean_prop_ds():
        raise RuntimeError("HTTP 404")

    monkeypatch.setattr(predict_mod, "get_ocean_prop_ds", _fake_get_ocean_prop_ds)

    with pytest.raises(ValueError, match="no3_dataset must be provided"):
        predict_mod.predict_T_from_proxyObs(
            proxyObs=np.array([0.5]),
            prior_mu_t=20.0,
            prior_sigma_t=10.0,
            site_lat=0.5,
            site_lon=0.5,
        )
