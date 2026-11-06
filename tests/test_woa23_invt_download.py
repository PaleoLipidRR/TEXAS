"""
download_woa23() and download_invT_posteriors().

Network is always mocked here -- these never hit NCEI or Zenodo for real.
"""

from __future__ import annotations

import io
import zipfile

import TEXAS.utils.download as download_mod
from TEXAS.utils.download import (
    WOA23_FILES,
    download_invT_posteriors,
    download_woa23,
)


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


# ─── WOA23_FILES registry ──────────────────────────────────────────────────

def test_woa23_files_exported_from_top_level():
    import TEXAS
    assert "WOA23_FILES" in TEXAS.__all__
    assert "download_woa23" in TEXAS.__all__
    assert "download_invT_posteriors" in TEXAS.__all__
    assert TEXAS.WOA23_FILES is WOA23_FILES


def test_woa23_files_has_temperature_and_nitrate():
    assert set(WOA23_FILES) == {
        "temperature_0.25deg", "temperature_1deg", "nitrate_1deg",
    }
    for entry in WOA23_FILES.values():
        assert entry["url"].startswith("https://www.ncei.noaa.gov/")
        assert entry["dest"].startswith("woa23/")
        assert entry["size_mb"] > 0


# ─── download_woa23() ───────────────────────────────────────────────────────

def test_download_woa23_fetches_each_file_once(monkeypatch, tmp_path):
    seen_urls = []

    def _fake_urlopen(url):
        seen_urls.append(url)
        return _FakeResponse(b"fake woa23 bytes")

    monkeypatch.setattr(download_mod.urllib.request, "urlopen", _fake_urlopen)

    paths = download_woa23(dest_dir=tmp_path)
    assert len(paths) == len(WOA23_FILES) == len(seen_urls)
    for p, entry in zip(paths, WOA23_FILES.values()):
        assert p == tmp_path / entry["dest"]
        assert p.read_bytes() == b"fake woa23 bytes"


def test_download_woa23_skips_cached_files(monkeypatch, tmp_path):
    for entry in WOA23_FILES.values():
        out = tmp_path / entry["dest"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"already here")

    def _boom(*a, **kw):
        raise AssertionError("must not hit the network when already cached")

    monkeypatch.setattr(download_mod.urllib.request, "urlopen", _boom)

    download_woa23(dest_dir=tmp_path)  # no AssertionError raised


# ─── download_invT_posteriors() ────────────────────────────────────────────

def _fake_invt_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("invT/coretop/tx.GHEB.sst.sri03.G23.inv.global_coretop.ud.nc", b"c1")
        zf.writestr("invT/coretop/tx.GHEB.sst.sri03.G23.inv.global_coretop_b01.ud.nc", b"c2")
        zf.writestr("invT/paleo/tx.GHEB.sst.sri03.G23-N1p0.inv.DSDP591.ud.nc", b"p1")
        zf.writestr("invT/paleo/tx.GHEB.sst.sri03.G23-N1p0.inv.Co1010.ud_draws.nc", b"d1")
    return buf.getvalue()


def test_download_invt_posteriors_unpacks_flat_with_draws_subdir(monkeypatch, tmp_path):
    def _fake_urlopen(url):
        assert "zenodo.org" in url
        assert download_mod._INVT_ZIP_FILENAME in url
        return _FakeResponse(_fake_invt_zip_bytes())

    monkeypatch.setattr(download_mod.urllib.request, "urlopen", _fake_urlopen)

    paths = download_invT_posteriors(cache_dir=tmp_path)
    names = {p.name for p in paths}
    assert "tx.GHEB.sst.sri03.G23-N1p0.inv.DSDP591.ud.nc" in names

    # coretop compiled + batch files land flat at the cache root, regardless
    # of their "coretop" vs "paleo" prefix inside the zip.
    assert (tmp_path / "tx.GHEB.sst.sri03.G23.inv.global_coretop.ud.nc").exists()
    assert (tmp_path / "tx.GHEB.sst.sri03.G23.inv.global_coretop_b01.ud.nc").exists()
    assert (tmp_path / "tx.GHEB.sst.sri03.G23-N1p0.inv.DSDP591.ud.nc").exists()

    # _draws.nc files go under draws/, matching save_invT_posterior()'s layout.
    draws_file = tmp_path / "draws" / "tx.GHEB.sst.sri03.G23-N1p0.inv.Co1010.ud_draws.nc"
    assert draws_file.exists()
    assert draws_file.read_bytes() == b"d1"
    assert "tx.GHEB.sst.sri03.G23-N1p0.inv.Co1010.ud_draws.nc" not in [
        p.name for p in tmp_path.glob("*.nc")
    ]
