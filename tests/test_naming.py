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
    (False, False, None, "p0"),
])
def test_encode_predictors(g23, no3, cutoff, expected):
    assert encode_predictors(g23, no3, cutoff) == expected


@pytest.mark.parametrize("token", ["G23-N10", "G23", "N15", "p0"])
def test_predictors_round_trip(token):
    d = decode_predictors(token)
    assert encode_predictors(d["use_gdgt23ratio"], d["use_no3"], d["no3_cutoff"]) == token


def test_no3_without_cutoff_is_an_error():
    with pytest.raises(ValueError, match="no3_cutoff"):
        encode_predictors(False, True, None)


# --- the case -------------------------------------------------------------

def test_case_round_trips_through_text():
    case = CaseName(compset="GHEB", temptype="sst", proxy="sri03",
                    predictors="G23-N10", version="v026", run="001")
    assert str(case) == "tx.v026.GHEB.sst.sri03.G23-N10.001"
    assert str(parse_case(str(case))) == str(case)


def test_run_position_defaults_and_separates_refits():
    a = CaseName("GHEB", "sst", "sri03", "G23-N10", version="v026")
    b = CaseName("GHEB", "sst", "sri03", "G23-N10", version="v026", run="050126")
    assert a.run == "001"
    assert str(a) != str(b), "a refit must not collide with the original"


def test_parse_case_tolerates_a_missing_run():
    assert parse_case("tx.v026.GHEB.sst.sri03.G23-N10").run == "001"


def test_parse_case_rejects_junk():
    for bad in ["not-a-case", "tx.v026.TOOLONG.sst.sri03.none", "tx.GHEB.sst"]:
        assert not is_case_id(bad)
        with pytest.raises(ValueError):
            parse_case(bad)


def test_invalid_compset_rejected_at_construction():
    with pytest.raises(ValueError):
        CaseName(compset="ZZZZ", temptype="sst", proxy="sri03")


def test_with_variant_swaps_only_the_structure_axis():
    case = CaseName("GHEA", "sst", "sri03", "G23-N10", version="v026")
    assert str(case.with_variant("B")) == "tx.v026.GHEB.sst.sri03.G23-N10.001"


def test_case_from_attrs():
    attrs = {
        "stan_model_name": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT",
        "temptype": "SST", "proxy_name": "scaledRI_cren3",
        "use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0,
    }
    case = case_from_attrs(attrs, version="v026")
    assert str(case) == "tx.v026.GHEB.sst.sri03.G23-N10.001"
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
    assert fwd_relpath("tx.v026.GHEB.sst.sri03.G23-N10.001").as_posix() == \
        ("tx.v026.GHEB.sst.sri03.G23-N10.001/"
         "tx.v026.GHEB.sst.sri03.G23-N10.001.fwd.nc")


def test_fwd_leaf_is_self_describing_when_detached():
    """
    A posterior copied out of its case directory must still name its case --
    Zenodo's namespace is flat, so many bare ``fwd.nc`` cannot coexist there.
    """
    case = "tx.v026.GHEB.sst.sri03.G23-N10.001"
    assert fwd_relpath(case).name == f"{case}.fwd.nc"


def test_repeating_the_case_costs_path_but_buys_a_portable_leaf():
    """
    The trade this scheme makes, stated explicitly so nobody 'optimises' it away.

    Repeating the case is NOT free: the full path grows from 39 to 72 chars
    against a bare ``fwd.nc``. What it buys is a leaf that still identifies its
    calibration once detached from the directory -- which is mandatory, because
    the Zenodo record is a flat namespace. The full path is still well under
    the legacy flat name.
    """
    case = "tx.v026.GHEB.sst.sri03.G23-N10.001"
    full = str(fwd_relpath(case))
    assert len(full) > len(f"{case}/fwd.nc"), "be honest: the path does grow"
    assert len(fwd_relpath(case).name) == len(f"{case}.fwd.nc")


def test_inv_relpath():
    p = inv_relpath("tx.v026.GHEB.sst.sri03.G23-N10.001", "U1482",
                    scenario="mod", run=1)
    assert p.as_posix() == ("tx.v026.GHEB.sst.sri03.G23-N10.001/"
                            "tx.v026.GHEB.sst.sri03.G23-N10.001.inv.U1482.ud-mod-001.nc")


def test_inv_relpath_slugs_a_site_with_spaces():
    p = inv_relpath("tx.v026.GHEB.sst.sri03.none.001", "South Dover Bridge")
    assert "South-Dover-Bridge" in p.name


def test_inv_relpath_rejects_unknown_constraint():
    with pytest.raises(ValueError, match="constraint"):
        inv_relpath("tx.v026.GHEB.sst.sri03.none.001", "U1482", constraint="nope")


def test_new_names_are_much_shorter():
    """The whole point: names must stop growing with every added axis."""
    attrs = {
        "stan_model_name": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_boundedT",
        "temptype": "SST", "proxy_name": "scaledRI_cren3",
        "use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0,
    }
    legacy = legacy_fwd_name(attrs) + ".nc"          # 98 chars
    case = case_from_attrs(attrs, version="v026")
    full = str(fwd_relpath(case))                    # case dir + leaf
    leaf = fwd_relpath(case).name                    # what you actually read

    # The leaf is what you read, type, and publish to Zenodo -- that is the
    # number that must halve. The full path carries the case twice by design,
    # so it only has to beat the legacy name, not halve it.
    assert len(leaf) < len(legacy) / 2, (
        f"leaf {leaf!r} ({len(leaf)}) should be under half of "
        f"{legacy!r} ({len(legacy)})"
    )
    assert len(full) < len(legacy), (
        f"case path {full!r} ({len(full)}) should still beat "
        f"{legacy!r} ({len(legacy)})"
    )


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
    assert p.name == f"{p.parent.name}.fwd.nc"
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
        "fwd_case": "tx.v025.GHEB.sst.sri03.G23-N10.001",
    }
    base = _generate_filename_base(meta, "050126")
    assert base.startswith("tx.v025.GHEB.sst.sri03.G23-N10.001/")
    assert base.endswith("/tx.v025.GHEB.sst.sri03.G23-N10.001.inv.U1482.ud-050126")


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


# --- backward compatibility of the token spellings -------------------------
# The proxy code changed ri3 -> sri03 and the no-predictor token none -> p0 on
# 2026-08-11. Case ids written before that must still parse, or the two case
# directories already on disk become unreadable.

@pytest.mark.parametrize("old,proxy", [
    ("tx.v026.GHEB.sst.ri3.G23-N10.001", "scaledRI_cren3"),
    ("tx.v026.GHEB.sst.ri4.G23-N10.001", "scaledRI_cren4"),
    ("tx.v026.GCDU.cul.ri3.none.001", "scaledRI_cren3"),
])
def test_pre_20260811_case_ids_still_parse(old, proxy):
    from TEXAS.utils.naming import PROXY_DECODE
    case = parse_case(old)
    assert is_case_id(old)
    assert PROXY_DECODE[case.proxy] == proxy


def test_legacy_none_token_decodes_like_p0():
    assert decode_predictors("none") == decode_predictors("p0")


def test_texri_no_longer_collides_with_scaledri():
    """Two distinct proxies must not collapse onto one case id."""
    base = {"stan_model_name": "gen_logi_fixed_hier_crtp_univ_priorApprox",
            "temptype": "SST"}
    a = case_from_attrs({**base, "proxy_name": "scaledRI_cren3"}, version="v026")
    b = case_from_attrs({**base, "proxy_name": "TEXRI_cren3"}, version="v026")
    assert str(a) != str(b), "scaledRI_cren3 and TEXRI_cren3 shared the code 'ri3'"


# --- run-token recovery (Phase 5C) -----------------------------------------
# save_posterior stamps the name it wrote onto the dataset, so a file later
# renamed without its date suffix still carries the suffix in attrs. Recovering
# it is what stops two refits of one configuration from colliding on run 001.

@pytest.mark.parametrize("filename,expected", [
    ("gen_logi_fixed_culmeso_cultureT_scaledRI_cren3_050126.nc", "050126"),
    ("..._SST_gdgt23ratio_no3_1.0_scaledRI_cren3_041526_eiv.nc", "041526"),
    ("..._scaledRI_cren3.nc", None),
    ("fwd.nc", None),
    ("", None),
])
def test_run_from_attrs(filename, expected):
    from TEXAS.utils.naming import run_from_attrs
    assert run_from_attrs({"filename": filename}) == expected


def test_run_stamp_ignores_short_scenario_tokens():
    """no3_001 is three digits and must not be mistaken for a run stamp."""
    from TEXAS.utils.naming import run_from_attrs
    fn = "MD98-2152_invT_gen_logi_fixed_multiv_sst_cren3_050126_no3_001_direct.nc"
    assert run_from_attrs({"filename": fn}) == "050126"


def test_refits_recover_distinct_runs_from_attrs():
    """The exact collision that blocked migrating the real cache."""
    base = {"stan_model_name": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv",
            "temptype": "SST", "proxy_name": "scaledRI_cren3",
            "use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0}
    a = case_from_attrs({**base, "filename": "x_cren3_041526_eiv.nc"}, version="v026")
    b = case_from_attrs({**base, "filename": "x_cren3_041626_eiv.nc"}, version="v026")
    assert a.run == "041526" and b.run == "041626"
    assert str(a) != str(b)


def test_explicit_run_still_wins_over_recovery():
    """save_posterior passes a run explicitly; a fresh fit must not inherit one."""
    attrs = {"stan_model_name": "gen_logi_fixed_culmeso", "temptype": "cultureT",
             "proxy_name": "scaledRI_cren3", "filename": "old_050126.nc"}
    assert case_from_attrs(attrs, version="v026", run="001").run == "001"


def test_stamped_legacy_name_still_resolves_after_migration(tmp_path, fwd_posterior):
    """
    A date-stamped legacy name must survive the *migration* into a case dir.

    legacy_fwd_name() reconstructs only the unstamped form, so a request for
    "..._041626_eiv" would miss it -- and that stamped form is exactly what the
    SI notebooks pass. The `filename` attr, which the migration copies through
    untouched, is what closes the gap.
    """
    from TEXAS.stan.io import load_posterior
    from TEXAS.utils.naming import case_from_attrs, fwd_relpath, resolve_posterior_path

    stamped = "gen_logi_fixed_run_041626_eiv"
    fwd_posterior.attrs["filename"] = f"{stamped}.nc"

    # Exactly what migrate_cache_layout.py produces: the file lands in its case
    # directory with its original attrs, `filename` included.
    case = case_from_attrs(fwd_posterior.attrs)
    dest = tmp_path / fwd_relpath(case)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fwd_posterior.to_netcdf(dest)

    assert case.run == "041626", "the stamp is recovered as the run token"
    assert resolve_posterior_path(stamped, tmp_path) == dest
    assert load_posterior(stamped, cache_dir=tmp_path) is not None


def test_a_rerun_does_not_answer_to_the_old_stamped_name(tmp_path, fwd_posterior):
    """
    The other half of the story, and the one that surprises people.

    Re-running Stan writes a *new* file, and save_posterior stamps the new leaf
    name onto `filename`. Nothing on disk remembers the old stamped name any
    more, so a notebook asking for "..._050126_eiv" will not find it -- while
    the *unstamped* legacy name still resolves, because that one is
    reconstructed from attrs rather than remembered.
    """
    from TEXAS.stan.io import save_posterior
    from TEXAS.utils.naming import legacy_fwd_name, resolve_posterior_path

    fwd_posterior.attrs["filename"] = "gen_logi_fixed_run_050126_eiv.nc"
    save_posterior(fwd_posterior, cache_dir=tmp_path, layout="case",
                   filename_suffix="050126")

    assert resolve_posterior_path("gen_logi_fixed_run_050126_eiv", tmp_path) is None
    assert resolve_posterior_path(legacy_fwd_name(fwd_posterior.attrs), tmp_path) is not None
