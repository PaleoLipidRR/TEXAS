"""Tests for ``scripts/migrate_kriged_cache.py``'s classification logic.

The migration used to treat every ``kriged_grids_1.0deg_*`` file as a
duplicate of its ``1deg`` counterpart and always delete it. On a machine
whose grids were written through the default ``krige_res=1.0`` rather than an
explicit ``1``, no ``1deg`` counterpart ever existed, so applying the
migration deleted the only copy of that grid. ``build_plan()`` now checks for
a counterpart first: with one, the ``1.0deg`` file is still deleted as a
duplicate; without one, it is renamed into the destination under the
canonical ``1deg`` name instead of being deleted.

``scripts/`` is not a package (no ``__init__.py``), so the module is loaded
directly from its file path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "migrate_kriged_cache.py"
_spec = importlib.util.spec_from_file_location("migrate_kriged_cache", _SCRIPT_PATH)
migrate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate)


def _write_npz(path: Path, value: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, data_0=np.full((2, 2), value))


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "cache_root"
    r.mkdir()
    return r


@pytest.fixture
def dest_dir(tmp_path):
    return tmp_path / "cache_root" / "TEXAS_kriged_grids_cache"


# ── The bug: an orphaned 1.0deg file must never be deleted ─────────────────

def test_orphan_1p0deg_file_is_renamed_not_deleted(root, dest_dir):
    """No 1deg counterpart anywhere -- the only copy must survive."""
    orphan = root / "kriged_grids_1.0deg_10dmax_woa23_SST_scaledRI_cren3_temp_residual.npz"
    _write_npz(orphan)

    plan = migrate.build_plan(root, dest_dir)

    assert plan["doomed_files"] == []
    assert len(plan["orphan_renames"]) == 1
    src, dst = plan["orphan_renames"][0]
    assert src == orphan
    assert dst == dest_dir / "kriged_grids_1deg_10dmax_woa23_SST_scaledRI_cren3_temp_residual.npz"


def test_1p0deg_file_with_a_1deg_sibling_in_root_is_still_deleted(root, dest_dir):
    """The ordinary case: a real duplicate must still be treated as doomed."""
    live = root / "kriged_grids_1deg_10dmax_woa23_SST_scaledRI_cren3_temp_residual.npz"
    dup = root / "kriged_grids_1.0deg_10dmax_woa23_SST_scaledRI_cren3_temp_residual.npz"
    _write_npz(live)
    _write_npz(dup)

    plan = migrate.build_plan(root, dest_dir)

    assert plan["orphan_renames"] == []
    assert dup in plan["doomed_files"]
    assert plan["moves"] == [(live, dest_dir / live.name)]


def test_1p0deg_file_with_a_1deg_sibling_already_migrated_is_still_deleted(root, dest_dir):
    """The 1deg counterpart may already sit in the destination from an
    earlier partial run -- that still counts as a counterpart."""
    dup = root / "kriged_grids_1.0deg_10dmax_woa23_SST_scaledRI_cren3_temp_residual.npz"
    already_migrated = dest_dir / "kriged_grids_1deg_10dmax_woa23_SST_scaledRI_cren3_temp_residual.npz"
    _write_npz(dup)
    _write_npz(already_migrated)

    plan = migrate.build_plan(root, dest_dir)

    assert plan["orphan_renames"] == []
    assert dup in plan["doomed_files"]


def test_orphan_rename_does_not_collide_when_applied(root, dest_dir, capsys, monkeypatch):
    """Full apply path: the orphan actually lands, readable, under the new name."""
    orphan = root / "kriged_grids_1.0deg_10dmax_woa23_SST_scaledRI_cren3_temp_residual.npz"
    _write_npz(orphan, value=42.0)

    # --cache root: the script derives dest_dir=--cache/TEXAS_kriged_grids_cache,
    # matching this test's root/dest_dir fixtures.
    monkeypatch.setattr(sys, "argv", ["migrate_kriged_cache.py", "--apply", "--cache", str(root)])

    rc = migrate.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "RENAME" in out
    dest = dest_dir / "kriged_grids_1deg_10dmax_woa23_SST_scaledRI_cren3_temp_residual.npz"
    assert dest.exists()
    assert not orphan.exists()
    with np.load(dest) as z:
        assert float(z["data_0"][0, 0]) == 42.0


# ── Plan printing mentions the rename, not a silent delete ─────────────────

def test_dry_run_reports_the_rename_plan(root, dest_dir, capsys, monkeypatch):
    orphan = root / "kriged_grids_1.0deg_10dmax_woa23_SST_scaledRI_cren3_temp_residual.npz"
    _write_npz(orphan)

    monkeypatch.setattr(sys, "argv", ["migrate_kriged_cache.py", "--cache", str(root)])
    rc = migrate.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "RENAME" in out
    assert "no 1deg counterpart" in out
    assert "DELETE (0 file(s)" in out
    assert orphan.exists()   # dry run: nothing touched or moved
