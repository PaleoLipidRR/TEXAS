"""
The calibration posteriors that ship inside the wheel.

These pin the promise the appendix makes to a reader: `pip install texas-psm`
and reconstruct, with no download. Three things have to hold for that —
the files are present and readable, they carry every parameter the inverse
model reads, and omitting `fwd_posterior` selects one of them.
"""

import numpy as np
import pytest
import xarray as xr

from TEXAS.constants import (DEFAULT_FWD_POSTERIOR,
                             DEFAULT_FWD_POSTERIOR_UNIVARIATE)
from TEXAS.data.builder import InvTConfig, build_invT_inputData
from TEXAS.stan.io import load_posterior
from TEXAS.utils.paths import BUNDLED_POSTERIOR_DIR

# Everything build_invT_inputData extracts from a multivariate T0-shift fit.
REQUIRED_VARS = [
    "t0_crtp", "k_crtp", "b_crtp", "v_crtp",
    "gamma_G23_crtp", "gamma_NO3_crtp", "sigma_proxyObs_crtp",
]


@pytest.mark.parametrize("case", sorted(DEFAULT_FWD_POSTERIOR.values()))
def test_bundled_file_exists(case):
    assert (BUNDLED_POSTERIOR_DIR / f"{case}.fwd.nc").exists()


@pytest.mark.parametrize("case", sorted(DEFAULT_FWD_POSTERIOR.values()))
def test_bundled_file_is_small_enough_to_ship(case):
    # The per-site EIV latents take the archival file to ~80 MB. If they ever
    # come back the wheel is unshippable, so guard the size directly.
    size_mb = (BUNDLED_POSTERIOR_DIR / f"{case}.fwd.nc").stat().st_size / 1e6
    assert size_mb < 5, f"{case} is {size_mb:.1f} MB — too large to bundle"


@pytest.mark.parametrize("case", sorted(DEFAULT_FWD_POSTERIOR.values()))
def test_bundled_posterior_has_what_the_inverse_model_reads(case, tmp_path):
    # tmp_path as cache_dir: an empty cache, so a hit can only be the bundle.
    ds = load_posterior(case, cache_dir=tmp_path)
    for var in REQUIRED_VARS:
        assert var in ds.data_vars, f"{case} is missing {var}"
    assert ds.attrs["bundled_subset"] == 1
    assert ds.attrs["use_gdgt23ratio"] and ds.attrs["use_no3"]
    assert float(ds.attrs["no3_cutoff"]) == 1.0
    assert ds.attrs["proxy_name"] == "scaledRI_cren3"


def test_cache_wins_over_bundle(tmp_path):
    # A user's own refit of the same case must not be shadowed by the bundled
    # copy, or a recalibration would silently have no effect.
    case = DEFAULT_FWD_POSTERIOR["SST"]
    bundled = load_posterior(case, cache_dir=tmp_path)
    marked = bundled.copy()
    marked.attrs["bundled_subset"] = 0
    marked.attrs["marker"] = "from-cache"
    marked.to_netcdf(tmp_path / f"{case}.nc")

    got = load_posterior(case, cache_dir=tmp_path)
    assert got.attrs.get("marker") == "from-cache"


def test_bundled_posterior_drives_the_inverse_builder(tmp_path):
    ds = load_posterior(DEFAULT_FWD_POSTERIOR["SST"], cache_dir=tmp_path)
    data, kwargs = build_invT_inputData(
        proxyObs=np.array([0.40, 0.55, 0.70]),
        prior_mu_t=20.0,
        prior_sigma_t=10.0,
        fwd_posterior=ds,
        predictors={"gdgt23ratio": np.full(3, 2.0), "no3": np.full(3, 10.0)},
        config=InvTConfig(n_draws=50),
    )
    meta = kwargs["_metadata"]
    # T0-shift is detected from the gamma_* coefficients, not the model name,
    # which is what selects the matching invT Stan program.
    assert meta["is_bounded"] is True
    assert meta["predictor_usage"] == {"gdgt23ratio": True, "no3": True}
    assert data["no3_cutoff"] == 1.0
    assert data["M"] == 50
    assert meta["fwd_case"] == DEFAULT_FWD_POSTERIOR["SST"]


def test_default_target_map_covers_both_temptypes():
    assert set(DEFAULT_FWD_POSTERIOR) == {"SST", "thermoT"}


@pytest.mark.parametrize("case", sorted(DEFAULT_FWD_POSTERIOR.values()))
def test_bundled_posterior_carries_r2_thermal(case, tmp_path):
    # Both bundled files are EIV (_eiv_t0shift) fits, so both must carry the
    # R² their sigma_proxyObs_crtp prior was scaled from -- backfilled from
    # data/revision1/groupA/manuscript_refit/manifest.csv by
    # scripts/backfill_r2_thermal.py, since they predate DIRECT_KEYS stamping
    # it automatically.
    ds = load_posterior(case, cache_dir=tmp_path)
    assert "R2_thermal" in ds.attrs
    assert 0.0 < float(ds.attrs["R2_thermal"]) < 1.0


# --- one fact, one attr ----------------------------------------------------
# Duplicated metadata is how a rename leaves one name current and another
# stale: `stan_model_name` said `_t0shift` while arviz's echoed `model` still
# said `_boundedT`, and `version` was this package's own default argument
# masquerading as provenance. Both are gone; these pin that.

@pytest.mark.parametrize("case", sorted(DEFAULT_FWD_POSTERIOR.values()))
def test_no_duplicate_model_or_version_attrs(case, tmp_path):
    ds = load_posterior(case, cache_dir=tmp_path)
    assert "model" not in ds.attrs, "arviz's duplicate of stan_model_name is back"
    assert "version" not in ds.attrs, "the fossil '1.0.0' default is back"
    assert ds.attrs["stan_model_name"].endswith("_t0shift")
    assert ds.attrs["generated_by"] == "texas-psm"


def test_metadata_writer_records_one_model_name_and_no_version():
    import numpy as np
    from TEXAS.stan.metadata import extract_and_update_metadata

    # (the arviz `model` attr is dropped one layer up, in StanSampler, so this
    # covers only what the metadata writer itself is responsible for)
    ds = xr.Dataset({"t0_crtp": ("draw", np.zeros(4))})
    out = extract_and_update_metadata(ds, {}, "gen_logi_fixed_culmeso")

    assert out.attrs["stan_model_name"] == "gen_logi_fixed_culmeso"
    assert out.attrs["generated_by"] == "texas-psm"
    assert "version" not in out.attrs
    assert "texas_version" in out.attrs


# ── the thermal-only pair, and the fallback that selects it ──────────────────
# predict_T_from_proxyObs switches to these when it is handed a proxy and no
# predictors, so they must ship too -- otherwise the fallback would need a
# network round-trip on a bare `pip install texas-psm`.

@pytest.mark.parametrize("case", sorted(DEFAULT_FWD_POSTERIOR_UNIVARIATE.values()))
def test_univariate_bundled_file_exists(case):
    assert (BUNDLED_POSTERIOR_DIR / f"{case}.fwd.nc").is_file()


@pytest.mark.parametrize("case", sorted(DEFAULT_FWD_POSTERIOR_UNIVARIATE.values()))
def test_univariate_bundled_file_is_small_enough_to_ship(case):
    mb = (BUNDLED_POSTERIOR_DIR / f"{case}.fwd.nc").stat().st_size / 1e6
    assert mb < 2.0, f"{case} is {mb:.2f} MB"


@pytest.mark.parametrize("case", sorted(DEFAULT_FWD_POSTERIOR_UNIVARIATE.values()))
def test_univariate_bundled_posterior_is_thermal_only(case, tmp_path):
    """It must NOT declare the corrections, or the fallback would demand them."""
    ds = load_posterior(case, cache_dir=tmp_path)
    assert not ds.attrs.get("use_gdgt23ratio", 0)
    assert not ds.attrs.get("use_no3", 0)
    for p in ("t0_crtp", "k_crtp", "b_crtp", "v_crtp", "sigma_proxyObs_crtp"):
        assert p in ds.data_vars, f"{case} is missing {p}"


def test_univariate_targets_match_the_multivariate_ones():
    """Every target with a multivariate default needs a thermal-only counterpart."""
    assert set(DEFAULT_FWD_POSTERIOR_UNIVARIATE) == set(DEFAULT_FWD_POSTERIOR)


def test_no_predictors_selects_the_thermal_only_calibration(monkeypatch):
    """The fallback picks the univariate case and says so, loudly.

    A silent switch would be worse than the error it replaces: the thermal-only
    fit is a different calibration, not the multivariate one with its
    corrections off, so a user who does not notice would get numbers that do not
    match the manuscript.
    """
    import warnings as _w
    from TEXAS import predict as _predict

    seen = {}

    def _capture(**kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop before sampling")

    monkeypatch.setattr(_predict, "predict_T_from_proxyObs_core", _capture,
                        raising=False)
    with _w.catch_warnings(record=True) as rec:
        _w.simplefilter("always")
        try:
            _predict.predict_T_from_proxyObs(np.array([0.55, 0.62]),
                                             prior_mu_t=20.0, prior_sigma_t=10.0)
        except Exception:
            pass
        msgs = " ".join(str(x.message) for x in rec)
    assert "thermal-only" in msgs, msgs
    assert "DIFFERENT calibration" in msgs or "different calibration" in msgs.lower()
