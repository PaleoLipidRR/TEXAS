"""
One canonical path per calibration: flat, no version, no member.

The name used to carry three things it should not have. A **date stamp**, which
belongs in metadata — it cannot be read without parsing, does not survive a
rename, and collides for two runs on one day. A **version**, taken from the pip
release, which was wrong in both directions: a docs-only release orphaned every
name on disk, while a prior change without a release let two incompatible
posteriors share one identity. And a **member counter**, which read as a second
number beside the nitrate cutoff (`.001` next to `N1p0`) and made `overwrite`
meaningless, because a fresh member can never collide with anything.

What replaces them: the run date and package version are attrs, and a re-run
simply overwrites — callers that do not want to re-run check the cache first.

Reads must still find everything written under the older schemes, which is what
keeps migrating a tidiness step rather than a prerequisite.
"""
import numpy as np
import pytest
import xarray as xr

from TEXAS.stan.io import save_posterior
from TEXAS.utils.naming import (case_from_attrs, fwd_relpath, inv_relpath,
                                parse_case, resolve_posterior_path)

CASE = "tx.GHEA.sst.sri03.G23-N1p0"
ATTRS = {
    "stan_model_name": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv",
    "temptype": "SST", "proxy_name": "scaledRI_cren3",
    "use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0,
}


def _posterior(proxy="scaledRI_cren3"):
    dims, shape = ("chain", "draw"), (2, 20)
    rng = np.random.default_rng(0)
    ds = xr.Dataset({k: (dims, rng.normal(1, 0.1, shape))
                     for k in ("t0_crtp", "k_crtp", "b_crtp", "v_crtp")})
    ds.attrs.update({**ATTRS, "proxy_name": proxy})
    return ds


# --- the canonical name -----------------------------------------------------

def test_a_case_built_from_attrs_carries_no_version_or_member():
    assert str(case_from_attrs(ATTRS)) == CASE


def test_paths_are_flat():
    """No case directory: the leaf already carries the whole case id."""
    from pathlib import Path
    fwd = fwd_relpath(CASE)
    inv = inv_relpath(CASE, "U1482", scenario="no3_modern")
    assert fwd.parent == Path("."), fwd
    assert inv.parent == Path("."), inv
    assert fwd.name == f"{CASE}.fwd.nc"
    assert inv.name.startswith(f"{CASE}.inv.U1482.")


def test_no_member_and_no_date_in_a_written_name(tmp_path):
    import re
    path = save_posterior(_posterior(), cache_dir=tmp_path)
    assert path.name == f"{CASE}.fwd.nc"
    assert not re.search(r"\d{6}", path.name), path.name        # no date stamp
    assert not re.search(r"\.\d{3}\.", path.name), path.name    # no member


def test_the_site_name_survives_verbatim():
    """Dots delimit the fields, so a hyphen inside a site name is safe."""
    assert ".inv.MD98-2152." in str(inv_relpath(CASE, "MD98-2152"))


# --- write semantics: overwrite on re-run -----------------------------------

def test_a_rerun_overwrites_rather_than_accumulating(tmp_path):
    first = save_posterior(_posterior(), cache_dir=tmp_path)
    second = save_posterior(_posterior(), cache_dir=tmp_path)
    assert first == second
    assert len(list(tmp_path.glob("*.nc"))) == 1


def test_overwrite_false_refuses_an_existing_file(tmp_path):
    """
    With a deterministic path this guard means something again. Under the
    member counter it could never fire, because a fresh member never collides.
    """
    save_posterior(_posterior(), cache_dir=tmp_path)
    with pytest.raises(FileExistsError):
        save_posterior(_posterior(), cache_dir=tmp_path, overwrite=False)


def test_overwrite_false_is_fine_for_a_first_save(tmp_path):
    assert save_posterior(_posterior(), cache_dir=tmp_path,
                          overwrite=False).exists()


def test_a_run_can_still_be_pinned_deliberately(tmp_path):
    path = save_posterior(_posterior(), cache_dir=tmp_path, run="007")
    assert parse_case(path.name.replace(".fwd.nc", "")).run == "007"


def test_different_proxies_do_not_collide(tmp_path):
    a = save_posterior(_posterior("scaledRI_cren3"), cache_dir=tmp_path)
    b = save_posterior(_posterior("TEX86"), cache_dir=tmp_path)
    assert a != b


# --- what the run recorded instead ------------------------------------------

def test_run_date_and_package_version_are_recorded_as_attrs():
    """Both left the filename, so the attrs are now the only record."""
    from datetime import datetime
    from TEXAS.stan.metadata import extract_and_update_metadata
    ds = extract_and_update_metadata(_posterior(), data={"N_crtp": 3},
                                     stan_filename="m.stan")
    datetime.fromisoformat(ds.attrs["run_timestamp"])   # parses => real
    assert ds.attrs.get("texas_version"), "no texas_version attr"


# --- reads must cover every historical form ---------------------------------

def test_parse_accepts_the_versioned_and_membered_form():
    """
    Every id written before 2026-08-12 carries both, in the cache, in the
    notebooks and in case_ids.json. Strict parsing would strand all of them.
    """
    old = parse_case("tx.v026.GHEA.sst.sri03.G23-N10.002")
    assert old.version == "v026" and old.run == "002"
    assert str(old) == "tx.v026.GHEA.sst.sri03.G23-N10.002"   # lossless


def test_parse_reports_no_member_when_there_is_none():
    assert parse_case(CASE).run == ""


def test_a_flat_leaf_resolves(tmp_path):
    written = save_posterior(_posterior(), cache_dir=tmp_path)
    assert resolve_posterior_path(CASE, tmp_path) == written


def test_a_versioned_request_finds_the_short_file(tmp_path):
    """A notebook still holding the old id must not break."""
    written = save_posterior(_posterior(), cache_dir=tmp_path)
    assert resolve_posterior_path("tx.v026.GHEA.sst.sri03.G23-N10",
                                  tmp_path) == written


def test_a_case_directory_written_earlier_still_resolves(tmp_path):
    """Nothing has to move on disk for reads to keep working."""
    old = "tx.v026.GHEA.sst.sri03.G23-N10.001"
    d = tmp_path / old
    d.mkdir()
    (d / f"{old}.fwd.nc").write_bytes(b"")
    assert resolve_posterior_path(old, tmp_path) == d / f"{old}.fwd.nc"


def test_the_pre_2026_08_11_bare_leaf_still_resolves(tmp_path):
    old = "tx.v026.GHEA.sst.sri03.G23-N10.001"
    d = tmp_path / old
    d.mkdir()
    (d / "fwd.nc").write_bytes(b"")
    assert resolve_posterior_path(old, tmp_path) == d / "fwd.nc"


def test_a_legacy_long_name_still_resolves(tmp_path):
    written = save_posterior(_posterior(), cache_dir=tmp_path)
    legacy = ("gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv"
              "_SST_gdgt23ratio_no3_1.0_scaledRI_cren3")
    assert resolve_posterior_path(legacy, tmp_path) == written
