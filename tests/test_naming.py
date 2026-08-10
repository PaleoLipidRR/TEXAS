"""Tests for the CESM-style case naming scheme (TEXAS.utils.naming).

The invariants that matter are: every real model maps to a compset code, two
distinct calibrations never collide on one case id, a case id round-trips
through text, and the legacy-name reproducer matches what is actually on disk
(the dual-read fallback in ``load_posterior`` depends on that last one).
"""
import pytest

from TEXAS.utils.naming import (
    CaseName,
    case_from_attrs,
    decode_compset,
    decode_predictors,
    encode_compset,
    encode_predictors,
    fwd_relpath,
    inv_relpath,
    is_case_id,
    legacy_fwd_name,
    legacy_invT_name,
    parse_case,
)

# The models this project actually ships, with their expected compset codes.
REAL_MODELS = [
    ("gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT", "GHEB"),
    ("gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv", "GHEA"),
    ("gen_logi_fixed_hier_crtp_multiv_priorApprox", "GHPA"),
    ("gen_logi_fixed_hier_crtp_univ_priorApprox", "GHPU"),
    ("gen_logi_fixed_hier_crtp_multiv", "GHDA"),
    ("gen_logi_fixed_culmeso", "GCDU"),
    ("gen_logi_fixed_culmesocore", "GJDU"),
]


@pytest.mark.parametrize("model,code", REAL_MODELS)
def test_encode_compset(model, code):
    assert encode_compset(model) == code


@pytest.mark.parametrize("model,code", REAL_MODELS)
def test_every_code_decodes(model, code):
    d = decode_compset(code)
    assert set(d) == {"curve", "training_set", "estimator", "structure"}
    assert all(d.values())


def test_culmesocore_not_swallowed_by_culmeso():
    """'culmeso' is a prefix of 'culmesocore' -- order must not collapse them."""
    assert encode_compset("gen_logi_fixed_culmesocore")[1] == "J"
    assert encode_compset("gen_logi_fixed_culmeso")[1] == "C"


def test_boundedT_beats_multiv_on_structure_axis():
    """A bounded-T model is also a multiv model; bounded-T must win position 4."""
    assert encode_compset("gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT")[3] == "B"
    assert encode_compset("gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv")[3] == "A"


def test_eiv_beats_priorApprox_on_estimator_axis():
    """'priorApprox' is a substring of 'priorApprox_eiv'; the longer wins."""
    assert encode_compset("gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv")[2] == "E"
    assert encode_compset("gen_logi_fixed_hier_crtp_multiv_priorApprox")[2] == "P"


def test_unknown_curve_is_an_error():
    with pytest.raises(ValueError, match="curve family"):
        encode_compset("some_unrelated_model")


def test_empty_model_name_is_an_error():
    with pytest.raises(ValueError):
        encode_compset("")


# --- predictors -----------------------------------------------------------

@pytest.mark.parametrize("g23,no3,cutoff,expected", [
    (True, True, 1.0, "G23-N10"),
    (True, True, 1.5, "G23-N15"),
    (True, False, None, "G23"),
    (False, True, 1.0, "N10"),
    (False, False, None, "none"),
])
def test_encode_predictors(g23, no3, cutoff, expected):
    assert encode_predictors(g23, no3, cutoff) == expected


@pytest.mark.parametrize("token", ["G23-N10", "G23", "N15", "none"])
def test_predictors_round_trip(token):
    d = decode_predictors(token)
    assert encode_predictors(d["use_gdgt23ratio"], d["use_no3"], d["no3_cutoff"]) == token


def test_no3_without_cutoff_is_an_error():
    with pytest.raises(ValueError, match="no3_cutoff"):
        encode_predictors(False, True, None)


# --- the case -------------------------------------------------------------

def test_case_round_trips_through_text():
    case = CaseName(compset="GHEB", temptype="sst", proxy="ri3",
                    predictors="G23-N10", version="v026", run="001")
    assert str(case) == "tx.v026.GHEB.sst.ri3.G23-N10.001"
    assert str(parse_case(str(case))) == str(case)


def test_run_position_defaults_and_separates_refits():
    a = CaseName("GHEB", "sst", "ri3", "G23-N10", version="v026")
    b = CaseName("GHEB", "sst", "ri3", "G23-N10", version="v026", run="050126")
    assert a.run == "001"
    assert str(a) != str(b), "a refit must not collide with the original"


def test_parse_case_tolerates_a_missing_run():
    assert parse_case("tx.v026.GHEB.sst.ri3.G23-N10").run == "001"


def test_parse_case_rejects_junk():
    for bad in ["not-a-case", "tx.v026.TOOLONG.sst.ri3.none", "tx.GHEB.sst"]:
        assert not is_case_id(bad)
        with pytest.raises(ValueError):
            parse_case(bad)


def test_invalid_compset_rejected_at_construction():
    with pytest.raises(ValueError):
        CaseName(compset="ZZZZ", temptype="sst", proxy="ri3")


def test_with_variant_swaps_only_the_structure_axis():
    case = CaseName("GHEA", "sst", "ri3", "G23-N10", version="v026")
    assert str(case.with_variant("B")) == "tx.v026.GHEB.sst.ri3.G23-N10.001"


def test_case_from_attrs():
    attrs = {
        "stan_model_name": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT",
        "temptype": "SST", "proxy_name": "scaledRI_cren3",
        "use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0,
    }
    case = case_from_attrs(attrs, version="v026")
    assert str(case) == "tx.v026.GHEB.sst.ri3.G23-N10.001"
    assert case.temptype_full == "SST"
    assert case.proxy_full == "scaledRI_cren3"


def test_thermoT_and_sst_do_not_collide():
    base = {"stan_model_name": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv",
            "proxy_name": "scaledRI_cren3", "use_gdgt23ratio": 1,
            "use_no3": 1, "no3_cutoff": 1.0}
    sst = case_from_attrs({**base, "temptype": "SST"}, version="v026")
    thm = case_from_attrs({**base, "temptype": "thermoT"}, version="v026")
    assert str(sst) != str(thm)


def test_additive_and_boundedT_do_not_collide():
    base = {"temptype": "SST", "proxy_name": "scaledRI_cren3",
            "use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0}
    a = case_from_attrs({**base, "stan_model_name":
                         "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv"}, version="v026")
    b = case_from_attrs({**base, "stan_model_name":
                         "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT"},
                        version="v026")
    assert str(a) != str(b)


# --- paths ----------------------------------------------------------------

def test_fwd_relpath():
    assert fwd_relpath("tx.v026.GHEB.sst.ri3.G23-N10.001").as_posix() == \
        "tx.v026.GHEB.sst.ri3.G23-N10.001/fwd.nc"


def test_inv_relpath():
    p = inv_relpath("tx.v026.GHEB.sst.ri3.G23-N10.001", "U1482",
                    scenario="mod", run=1)
    assert p.as_posix() == "tx.v026.GHEB.sst.ri3.G23-N10.001/inv.U1482.ud-mod-001.nc"


def test_inv_relpath_slugs_a_site_with_spaces():
    p = inv_relpath("tx.v026.GHEB.sst.ri3.none.001", "South Dover Bridge")
    assert "South-Dover-Bridge" in p.name


def test_inv_relpath_rejects_unknown_constraint():
    with pytest.raises(ValueError, match="constraint"):
        inv_relpath("tx.v026.GHEB.sst.ri3.none.001", "U1482", constraint="nope")


def test_new_names_are_much_shorter():
    """The whole point: names must stop growing with every added axis."""
    attrs = {
        "stan_model_name": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT",
        "temptype": "SST", "proxy_name": "scaledRI_cren3",
        "use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0,
    }
    legacy = legacy_fwd_name(attrs) + ".nc"          # 98 chars
    case = case_from_attrs(attrs, version="v026")
    full = str(fwd_relpath(case))                    # case dir + "fwd.nc"
    leaf = fwd_relpath(case).name                    # what you actually read

    assert len(full) < len(legacy) / 2, (
        f"case path {full!r} ({len(full)}) should be under half of "
        f"{legacy!r} ({len(legacy)})"
    )
    assert len(leaf) <= 8, "the filename inside a case directory stays tiny"


# --- legacy reproducers (the dual-read fallback depends on these) ----------

def test_legacy_fwd_name_matches_the_historical_convention():
    attrs = {
        "stan_model_name": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT",
        "temptype": "SST", "proxy_name": "scaledRI_cren3",
        "use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0,
    }
    assert legacy_fwd_name(attrs) == (
        "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT"
        "_SST_gdgt23ratio_no3_1.0_scaledRI_cren3"
    )


def test_legacy_invT_name_matches_the_historical_convention():
    assert legacy_invT_name(
        "MD98-2152", "invT_gen_logi_fixed_multiv_marginal_unconstrained", "sst",
        proxy_name="scaledRI_cren3", use_gdgt23ratio=True, use_no3=True,
        no3_cutoff=1.0, tags="050126",
    ) == (
        "MD98-2152_invT_gen_logi_fixed_multiv_unconstrained"
        "_sst_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct"
    )


def test_legacy_invT_marks_ensemble_when_not_marginal():
    name = legacy_invT_name("X", "invT_gen_logi_fixed_multiv_unconstrained", "sst")
    assert name.endswith("_ensemble")


# --- io integration -------------------------------------------------------

FWD_ATTRS = {
    "stan_model_name": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT",
    "temptype": "SST", "proxy_name": "scaledRI_cren3",
    "use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0,
}


@pytest.fixture
def fwd_posterior():
    import numpy as np
    import xarray as xr
    ds = xr.Dataset({"t0_crtp": ("draw", np.arange(5.0))}, attrs=dict(FWD_ATTRS))
    return ds


def test_save_posterior_uses_the_case_directory(tmp_path, fwd_posterior):
    from TEXAS.stan.io import save_posterior
    p = save_posterior(fwd_posterior, cache_dir=tmp_path)
    assert p.name == "fwd.nc"
    assert is_case_id(p.parent.name)
    assert fwd_posterior.attrs["case_id"] == p.parent.name


def test_saved_posterior_loads_by_case_id_and_by_legacy_name(tmp_path, fwd_posterior):
    """Dual-read: one file on disk, reachable under either naming scheme."""
    from TEXAS.stan.io import load_posterior, save_posterior
    save_posterior(fwd_posterior, cache_dir=tmp_path)

    by_case = load_posterior(fwd_posterior.attrs["case_id"], cache_dir=tmp_path)
    by_legacy = load_posterior(legacy_fwd_name(FWD_ATTRS), cache_dir=tmp_path)
    assert by_case.attrs["stan_model_name"] == by_legacy.attrs["stan_model_name"]


def test_legacy_layout_still_loads_by_case_id(tmp_path, fwd_posterior):
    """An existing flat cache must be reachable by the new short name."""
    from TEXAS.stan.io import load_posterior, save_posterior
    save_posterior(fwd_posterior, cache_dir=tmp_path, layout="legacy")
    assert (tmp_path / f"{legacy_fwd_name(FWD_ATTRS)}.nc").exists()

    case = str(case_from_attrs(FWD_ATTRS))
    assert load_posterior(case, cache_dir=tmp_path).attrs["temptype"] == "SST"


def test_filename_suffix_becomes_the_run_token(tmp_path, fwd_posterior):
    from TEXAS.stan.io import save_posterior
    p = save_posterior(fwd_posterior, cache_dir=tmp_path, filename_suffix="050126")
    assert parse_case(p.parent.name).run == "050126"


def test_two_runs_of_one_config_do_not_overwrite(tmp_path, fwd_posterior):
    from TEXAS.stan.io import save_posterior
    a = save_posterior(fwd_posterior, cache_dir=tmp_path)
    b = save_posterior(fwd_posterior, cache_dir=tmp_path, filename_suffix="050126")
    assert a != b and a.exists() and b.exists()


def test_invT_name_lands_in_the_parent_case_directory():
    from TEXAS.stan.io import _generate_filename_base
    meta = {
        "SiteName": "U1482",
        "stan_model_name": "invT_gen_logi_fixed_multiv_marginal_unconstrained_boundedT",
        "temptype": "sst", "proxy_name": "scaledRI_cren3",
        "use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0,
        "fwd_case": "tx.v025.GHEB.sst.ri3.G23-N10.001",
    }
    base = _generate_filename_base(meta, "050126")
    assert base.startswith("tx.v025.GHEB.sst.ri3.G23-N10.001/")
    assert base.endswith("/inv.U1482.ud-050126")


def test_invT_without_provenance_keeps_the_legacy_name():
    """Posteriors predating the fwd_case attr must keep working unchanged."""
    from TEXAS.stan.io import _generate_filename_base
    meta = {
        "SiteName": "U1482",
        "stan_model_name": "invT_gen_logi_fixed_multiv_marginal_unconstrained",
        "temptype": "sst", "proxy_name": "scaledRI_cren3",
        "use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0,
    }
    base = _generate_filename_base(meta, "050126")
    assert "/" not in base
    assert base == ("U1482_invT_gen_logi_fixed_multiv_unconstrained_sst"
                    "_gdgt23ratio_no3_1.0_scaledRI_cren3_050126_direct")
