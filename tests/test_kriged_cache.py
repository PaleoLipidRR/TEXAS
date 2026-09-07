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


# ── Call-time resolution of KRIGED_CACHE_DIR ────────────────────────────────

def test_auto_cache_path_honours_a_cache_dir_change_after_import(cache_root, tmp_path):
    """Regression guard for the io.py-style hoisting bug.

    ``stan/io.py`` does ``from TEXAS.utils.paths import POSTERIOR_CACHE_DIR``
    at module scope, so ``set_cache_dir()`` rebinds the attribute on the
    paths module but io.py's local name still points at the old directory.
    ``_auto_cache_path`` must not reproduce that: importing
    ``TEXAS.plotting.residual_maps`` (already done, at collection time, well
    before this test's ``cache_root`` fixture repoints the cache) must not
    freeze the directory it resolves.
    """
    other_root = tmp_path / "elsewhere"
    set_cache_dir(other_root)
    try:
        p = rm._auto_cache_path("SST", "scaledRI_cren3", "temp_residual", krige_res=1)
        assert p.parent == other_root / "TEXAS_kriged_grids_cache"
        assert p.parent != cache_root / "TEXAS_kriged_grids_cache"
    finally:
        set_cache_dir(cache_root)
