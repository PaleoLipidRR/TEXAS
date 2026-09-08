"""The exported names that nothing else exercised.

`tests/test_public_api_docs.py` asserts that every name in `TEXAS.__all__` is
referenced by at least one test or notebook *code cell*. Six were not, which
is a fair description of "exported but never used". A seventh,
`get_invT_posterior`, only ever appears in a notebook's stored *output* (a
captured RuntimeWarning source-line echo), which the guard deliberately does
not count as a reference -- see its test below for the detail. These are real
smoke tests -- each one calls the thing and checks something that would break
if it regressed -- not placeholders to satisfy the scan.
"""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

import TEXAS


def test_simple_logistic_multivariate_applies_the_g23_offset():
    """The G23 term is additive on mu, so the offset is exactly beta * ratio."""
    x = np.linspace(0.0, 30.0, 11)
    base = TEXAS.simple_logistic_fixed_upper_multivariate(x, t0=15.0, b=0.2, k=0.3)
    with_g23 = TEXAS.simple_logistic_fixed_upper_multivariate(
        x, t0=15.0, b=0.2, k=0.3,
        beta_G23=0.05, gdgt23ratio=np.full_like(x, 2.0),
    )
    np.testing.assert_allclose(with_g23 - base, 0.05 * 2.0)


def test_simple_logistic_multivariate_rejects_mismatched_predictor():
    x = np.linspace(0.0, 30.0, 11)
    with pytest.raises(ValueError):
        TEXAS.simple_logistic_fixed_upper_multivariate(
            x, t0=15.0, b=0.2, k=0.3, beta_G23=0.05, gdgt23ratio=np.zeros(3),
        )


def test_find_optimal_no3_threshold_nointercept_recovers_a_planted_cutoff():
    """Below 2.0 the residuals follow -0.1*log10(no3/2); above, they are noise."""
    rng = np.random.default_rng(0)
    no3 = np.concatenate([rng.uniform(0.1, 2.0, 120), rng.uniform(2.0, 8.0, 120)])
    res = np.where(no3 < 2.0, -0.1 * np.log10(no3 / 2.0), 0.0)
    res = res + rng.normal(0.0, 0.002, res.size)

    threshold, table = TEXAS.find_optimal_no3_threshold_nointercept(no3, res)

    assert 1.0 < threshold < 4.0, f"planted cutoff 2.0 not recovered, got {threshold}"
    assert set(["threshold", "beta", "r2_nointercept", "n_points"]).issubset(table.columns)
    # `pd.Series == pytest.approx(scalar)` does not broadcast elementwise (it
    # falls through to a single object-identity comparison), so use np.isclose.
    assert np.isclose(table["threshold"], threshold).any()


def test_bootstrap_se_is_reproducible_and_shaped_per_parameter():
    def line(x, a, b):
        return a * x + b

    rng = np.random.default_rng(1)
    X = np.linspace(0.0, 10.0, 60)
    y = 2.0 * X + 1.0 + rng.normal(0.0, 0.5, X.size)
    bounds = ([-10.0, -10.0], [10.0, 10.0])

    se_a, boots_a = TEXAS.bootstrap_se(line, X, y, p0=[1.0, 0.0],
                                       bounds=bounds, n_boot=40, seed=7)
    se_b, _ = TEXAS.bootstrap_se(line, X, y, p0=[1.0, 0.0],
                                 bounds=bounds, n_boot=40, seed=7)

    assert se_a.shape == (2,)
    assert boots_a.shape[1] == 2
    np.testing.assert_allclose(se_a, se_b), "same seed must give the same SEs"
    assert np.all(np.isfinite(se_a))


def test_create_summary_table_strips_the_prefix_and_names_the_model():
    a = xr.Dataset(attrs={"filename": "run_a.nc", "stan_diag_max_rhat": 1.001,
                          "stan_diag_overall_status": "PASS"})
    b = xr.Dataset(attrs={"stan_diag_max_rhat": 1.20,
                          "stan_diag_overall_status": "FAIL"})

    table = TEXAS.create_summary_table([a, b])

    assert list(table["model"]) == ["run_a.nc", "unknown"]
    assert "max_rhat" in table.columns and "stan_diag_max_rhat" not in table.columns
    assert list(table["overall_status"]) == ["PASS", "FAIL"]
    assert isinstance(table, pd.DataFrame)


def test_posterior_registry_entries_are_well_formed():
    """Every entry must carry the two fields download_posteriors() reads."""
    assert TEXAS.POSTERIOR_REGISTRY, "the registry is empty"
    for name, entry in TEXAS.POSTERIOR_REGISTRY.items():
        assert "filename" in entry, f"{name} has no filename"
        assert entry["filename"].endswith(".nc"), f"{name}: {entry['filename']}"
        assert isinstance(entry.get("size_mb"), (int, float)), f"{name} has no size_mb"


def test_get_invT_posterior_requires_proxyobs():
    """The only place ``get_invT_posterior`` is named in a notebook is inside a
    captured RuntimeWarning's source-line echo (stdout/stderr text emitted by
    Python's own warnings module for the ``predict_T_from_proxyObs`` call that
    wraps it) -- not in any code cell, so the reference scan correctly does not
    count it. This exercises the function directly: it must fail fast on a
    missing required argument before touching Stan at all.
    """
    with pytest.raises(TypeError):
        TEXAS.get_invT_posterior(prior_mu_t=15.0, prior_sigma_t=10.0)


def test_set_cache_dir_redirects_both_caches_and_io_defaults(tmp_path):
    """It mutates module globals, so the test restores them itself."""
    import TEXAS.stan.io as io
    import TEXAS.utils.paths as paths

    saved = (paths.CACHE_ROOT, paths.CACHE_DIR, paths.POSTERIOR_CACHE_DIR,
             paths.INVT_CACHE_DIR, io.DEFAULT_FORWARD_DIR, io.DEFAULT_INVT_DIR)
    try:
        TEXAS.set_cache_dir(tmp_path)
        assert paths.POSTERIOR_CACHE_DIR == tmp_path / "TEXAS_posterior_cache"
        assert paths.INVT_CACHE_DIR == tmp_path / "TEXAS_invT_posterior_cache"
        # The point of the function: io.py bound its defaults at import time.
        assert io.DEFAULT_FORWARD_DIR == paths.POSTERIOR_CACHE_DIR
        assert io.DEFAULT_INVT_DIR == paths.INVT_CACHE_DIR
    finally:
        (paths.CACHE_ROOT, paths.CACHE_DIR, paths.POSTERIOR_CACHE_DIR,
         paths.INVT_CACHE_DIR, io.DEFAULT_FORWARD_DIR, io.DEFAULT_INVT_DIR) = saved
