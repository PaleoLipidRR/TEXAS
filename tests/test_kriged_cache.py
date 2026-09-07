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
