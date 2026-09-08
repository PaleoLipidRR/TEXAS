"""``download.py`` must honor a cache-dir redirect issued after import.

Regression guard for the same collision bug ``stan/io.py`` used to have:
``from .paths import POSTERIOR_CACHE_DIR, SPREADSHEETS_DIR`` at module scope
binds a local name at import time, so ``TEXAS.set_cache_dir()`` rebinding the
attribute on the ``paths`` module never reaches ``download.py``'s own default.
``download.py`` now resolves both names through the ``paths`` module object at
call time instead of importing them by value.

Network is always mocked here — these never hit Zenodo for real.
"""

from __future__ import annotations

import pytest

import TEXAS.utils.download as download_mod
from TEXAS.utils import paths
from TEXAS.utils.paths import set_cache_dir


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


@pytest.fixture
def cache_root(tmp_path):
    original = paths.CACHE_ROOT
    set_cache_dir(tmp_path)
    yield tmp_path
    set_cache_dir(original)


def test_download_posteriors_honors_cache_dir_set_after_import(
    monkeypatch, cache_root
):
    """A redirect issued after ``download.py`` was already imported must land."""
    monkeypatch.setattr(
        download_mod.urllib.request, "urlopen",
        lambda url: _FakeResponse(b"fake posterior bytes"),
    )

    name = next(
        k for k, v in download_mod.POSTERIOR_REGISTRY.items() if "record" not in v
    )
    out = download_mod.download_posteriors([name])

    assert len(out) == 1
    # Must land under the *current* POSTERIOR_CACHE_DIR (post set_cache_dir),
    # not whatever download.py resolved at its own import time.
    assert out[0].is_relative_to(paths.POSTERIOR_CACHE_DIR)
    assert out[0].is_relative_to(cache_root)
    assert out[0].read_bytes() == b"fake posterior bytes"


def test_download_posteriors_default_dest_dir_reads_live_paths_module(cache_root):
    """``dest_dir`` inside download_posteriors() must resolve via the module,
    not a value captured at import time."""
    # download.py no longer has a bare POSTERIOR_CACHE_DIR name to go stale.
    assert not hasattr(download_mod, "POSTERIOR_CACHE_DIR")
    assert not hasattr(download_mod, "SPREADSHEETS_DIR")
    assert download_mod._paths.POSTERIOR_CACHE_DIR == paths.POSTERIOR_CACHE_DIR


def test_download_training_data_honors_a_spreadsheets_dir_change(
    monkeypatch, tmp_path
):
    """Same collision-bug shape for SPREADSHEETS_DIR, exercised directly since
    there is no public setter for it yet."""
    new_dir = tmp_path / "redirected_spreadsheets"
    monkeypatch.setattr(paths, "SPREADSHEETS_DIR", new_dir)

    monkeypatch.setattr(
        download_mod.urllib.request, "urlopen",
        lambda url: _FakeResponse(b"x"),
    )

    out = download_mod.download_training_data()

    assert all(p.is_relative_to(new_dir) for p in out)
