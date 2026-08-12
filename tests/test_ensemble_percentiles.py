"""
Percentile keys must name the percentile that was asked for.

``generate_ensemble`` built its keys with ``f"p{int(q)}"``. int() truncates, so
a caller asking for the 2.5th percentile got a dict containing "p2" and a
KeyError on "p2.5" -- which is how the calibration-curve figure comparing the
three crenarchaeol conventions failed. The quieter half of the same bug is
worse: 2.5 and 2.9 both truncate to "p2", so one silently overwrites the other
and the figure draws a band it never requested.
"""
import numpy as np
import pytest
import xarray as xr

from TEXAS.ensemble.generator import generate_ensemble_auto


def _posterior(n_draws=200, seed=0):
    """A minimal culmeso-style forward posterior."""
    rng = np.random.default_rng(seed)
    dims = ("chain", "draw")
    shape = (2, n_draws // 2)
    ds = xr.Dataset({
        "t0_culmeso": (dims, rng.normal(30, 1.0, shape)),
        "k_culmeso": (dims, rng.normal(0.25, 0.02, shape)),
        "b_culmeso": (dims, rng.normal(0.40, 0.02, shape)),
        "v_culmeso": (dims, rng.normal(2.5, 0.3, shape)),
    })
    # No use_gdgt23ratio / use_no3 attrs: detect_model_and_params keys off the
    # PRESENCE of those attrs, not their value, so a univariate posterior that
    # carried them set to 0 would be asked for beta_* it does not have. Real
    # univariate and culmeso posteriors omit them, and so does this one.
    ds.attrs.update({"proxy_name": "scaledRI_cren3"})
    return ds


X = np.linspace(-2, 40, 25)


def test_fractional_percentiles_keep_their_name():
    out = generate_ensemble_auto(_posterior(), x_vals=X, percentiles=[2.5, 50, 97.5])
    assert "p2.5" in out and "p97.5" in out, sorted(out)
    assert "p2" not in out and "p97" not in out


def test_integer_percentiles_are_unchanged():
    """Every existing caller uses integers; those keys must not move."""
    out = generate_ensemble_auto(_posterior(), x_vals=X, percentiles=[5, 50, 95])
    assert {"p5", "p50", "p95"} <= set(out)


def test_percentiles_are_ordered():
    out = generate_ensemble_auto(_posterior(), x_vals=X, percentiles=[2.5, 50, 97.5])
    assert np.all(out["p2.5"] <= out["p50"] + 1e-9)
    assert np.all(out["p50"] <= out["p97.5"] + 1e-9)


def test_colliding_percentiles_are_refused_not_silently_merged():
    """
    2.5 and 2.9 both truncated to "p2" before. Returning one band under a key
    naming neither is the failure mode worth refusing outright.
    """
    with pytest.raises(ValueError, match="distinct keys"):
        generate_ensemble_auto(_posterior(), x_vals=X, percentiles=[2.5, 2.5])


def test_x_vals_round_trip():
    out = generate_ensemble_auto(_posterior(), x_vals=X, percentiles=[50])
    np.testing.assert_allclose(out["x_vals"], X)
    assert out["p50"].shape == X.shape
