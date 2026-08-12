"""
Filenames carry no date; the run/member token and the run_timestamp attr split
the job the date stamp used to do badly.

The stamp was doing two things at once. It distinguished a refit from the run
it repeated -- real work, now done by the member token, which counts and cannot
collide. And it recorded when the run happened -- which belongs in metadata,
where it survives a rename and nobody has to parse it back out of a path.

The failure mode worth guarding is the quiet one: if resolution handed back the
*oldest* member of a configuration, every figure would silently be drawn from a
superseded fit, and nothing downstream reports which member it loaded.
"""
import numpy as np
import pytest
import xarray as xr

from TEXAS.stan.io import save_posterior
from TEXAS.utils.naming import next_free_run, parse_case, resolve_posterior_path

CASE = "tx.v026.GHEA.sst.sri03.G23-N10.001"


def _posterior(proxy="scaledRI_cren3"):
    dims = ("chain", "draw")
    shape = (2, 20)
    rng = np.random.default_rng(0)
    ds = xr.Dataset({
        "t0_crtp": (dims, rng.normal(30, 1, shape)),
        "k_crtp": (dims, rng.normal(0.25, 0.02, shape)),
        "b_crtp": (dims, rng.normal(0.4, 0.02, shape)),
        "v_crtp": (dims, rng.normal(2.5, 0.3, shape)),
    })
    ds.attrs.update({
        "stan_model_name": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv",
        "temptype": "SST", "proxy_name": proxy,
        "use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0,
    })
    return ds


# --- the member token -------------------------------------------------------

def test_next_free_run_starts_at_001(tmp_path):
    assert next_free_run(CASE, tmp_path) == "001"


def test_next_free_run_skips_what_exists(tmp_path):
    from dataclasses import replace
    for run in ("001", "002"):
        (tmp_path / str(replace(parse_case(CASE), run=run))).mkdir()
    assert next_free_run(CASE, tmp_path) == "003"


def test_next_free_run_fills_a_gap(tmp_path):
    from dataclasses import replace
    for run in ("001", "003"):
        (tmp_path / str(replace(parse_case(CASE), run=run))).mkdir()
    assert next_free_run(CASE, tmp_path) == "002"


def test_next_free_run_ignores_other_calibrations(tmp_path):
    """A different proxy is a different case, not another member of this one."""
    from dataclasses import replace
    other = replace(parse_case(CASE), proxy="tex")
    (tmp_path / str(other)).mkdir()
    assert next_free_run(CASE, tmp_path) == "001"


# --- saving -----------------------------------------------------------------

def test_a_refit_does_not_overwrite_the_run_it_repeats(tmp_path):
    first = save_posterior(_posterior(), cache_dir=tmp_path)
    second = save_posterior(_posterior(), cache_dir=tmp_path)
    assert first != second, "the refit landed on top of the original"
    assert first.exists() and second.exists()
    assert parse_case(first.parent.name).run == "001"
    assert parse_case(second.parent.name).run == "002"


def test_no_date_appears_in_the_filename(tmp_path):
    import re
    path = save_posterior(_posterior(), cache_dir=tmp_path)
    # six consecutive digits is what a MMDDYY stamp looked like
    assert not re.search(r"\d{6}", path.name), path.name


def test_the_run_date_is_recorded_in_attrs(tmp_path):
    """
    The date has to live somewhere. The attr is the only place left, so a
    posterior without it has lost when it was run.
    """
    from TEXAS.stan.metadata import extract_and_update_metadata
    ds = extract_and_update_metadata(
        _posterior(), data={"N_crtp": 3}, stan_filename="m.stan")
    stamp = ds.attrs.get("run_timestamp")
    assert stamp, "no run_timestamp attr; the run date is now unrecorded"
    from datetime import datetime
    datetime.fromisoformat(stamp)          # parses, so it is a real timestamp


def test_an_explicit_run_is_honoured(tmp_path):
    path = save_posterior(_posterior(), cache_dir=tmp_path, run="007")
    assert parse_case(path.parent.name).run == "007"


# --- loading ----------------------------------------------------------------

def test_a_legacy_name_resolves_to_the_newest_member(tmp_path):
    """
    The quiet failure: a name that pins no member must not hand back the first
    fit forever. Nothing downstream reports which member it loaded, so an
    ascending scan would draw every figure from a superseded posterior.
    """
    save_posterior(_posterior(), cache_dir=tmp_path)          # .001
    newest = save_posterior(_posterior(), cache_dir=tmp_path)  # .002

    legacy = ("gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv"
              "_SST_gdgt23ratio_no3_1.0_scaledRI_cren3")
    found = resolve_posterior_path(legacy, tmp_path)
    assert found is not None, "legacy name no longer resolves at all"
    assert found == newest, f"resolved to {found}, expected the newest {newest}"


def test_an_exact_case_id_still_pins_its_member(tmp_path):
    first = save_posterior(_posterior(), cache_dir=tmp_path)
    save_posterior(_posterior(), cache_dir=tmp_path)
    assert resolve_posterior_path(first.parent.name, tmp_path) == first
