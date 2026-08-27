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

from TEXAS.constants import DEFAULT_FWD_POSTERIOR
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
