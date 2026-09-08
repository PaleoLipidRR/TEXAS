"""Predictor-mismatch warnings in predict_T_from_proxyObs.

Four combinations of (predictor supplied?, calibration uses it?) exist for
each of gdgt23ratio and no3. Three were wired up; the fourth -- the
calibration uses NO3 but none was supplied -- was silent, which is the
consequential gap: supplying an unused predictor is harmless (and already
warns twice), but omitting one the calibration actually applies silently
biases the reconstruction (NO3 is treated as 0, which is not the same as
switching the correction off). This test locks in the missing warning,
mirroring the existing GDGT-2/3 counterpart in wording, severity (UserWarning)
and category.
"""
import warnings

import numpy as np
import pytest
import xarray as xr

import TEXAS.predict as predict_mod


def _reduced_posterior():
    """A minimal quantile-reduced invT posterior, standing in for a Stan run."""
    ds = xr.Dataset(
        {"t_est": (("quantile", "obs_idx"),
                   np.tile(np.array([[5.0], [20.0], [35.0]]), (1, 3)))},
        coords={"quantile": [0.05, 0.5, 0.95], "obs_idx": np.arange(3)},
    )
    ds.attrs.update({
        "SiteName": "TestSite", "temptype": "SST", "proxy_name": "scaledRI_cren3",
        "stan_model_name": "invT_gen_logi_fixed_multiv_marginal_unconstrained",
        "use_gdgt23ratio": 0, "use_no3": 0, "no3_cutoff": 0.0,
        "model_type": "direct",
    })
    return ds


def _fwd(use_no3, use_gdgt23ratio=0):
    return xr.Dataset(attrs={
        "use_gdgt23ratio": use_gdgt23ratio, "use_no3": use_no3,
        "proxy_name": "scaledRI_cren3", "temptype": "SST",
        "no3_cutoff": 1.0,
    })


def _call(monkeypatch, fwd_posterior, **kwargs):
    monkeypatch.setattr(predict_mod, "_get_invT_posterior",
                        lambda *a, **k: _reduced_posterior())
    return predict_mod.predict_T_from_proxyObs(
        np.array([0.3, 0.4, 0.5]), prior_mu_t=20.0, prior_sigma_t=10.0,
        fwd_posterior=fwd_posterior, flags=False, **kwargs,
    )


def test_warns_when_calibration_uses_no3_but_none_supplied(monkeypatch):
    """The gap this test closes: this combination used to be silent."""
    with pytest.warns(UserWarning, match="uses the NO.? correction, but none was supplied"):
        _call(monkeypatch, _fwd(use_no3=1))


def test_no_warning_when_no3_supplied_and_used(monkeypatch):
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        _call(monkeypatch, _fwd(use_no3=1), no3=0.5)
    messages = [str(w.message) for w in record]
    assert not any("none was supplied" in m for m in messages), messages


def test_no_warning_when_no3_not_used_and_not_supplied(monkeypatch):
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        _call(monkeypatch, _fwd(use_no3=0))
    messages = [str(w.message) for w in record]
    assert not any("none was supplied" in m and "NO" in m for m in messages), messages


def test_mirrors_the_gdgt23_missing_warning_wording(monkeypatch):
    """Same shape of warning as the existing GDGT-2/3 counterpart."""
    with pytest.warns(UserWarning) as gdgt_record:
        _call(monkeypatch, _fwd(use_no3=0, use_gdgt23ratio=1))
    gdgt_msgs = [str(w.message) for w in gdgt_record.list
                 if "GDGT-2/3 ratio, but none was supplied" in str(w.message)]
    assert len(gdgt_msgs) == 1

    with pytest.warns(UserWarning) as no3_record:
        _call(monkeypatch, _fwd(use_no3=1))
    no3_msgs = [str(w.message) for w in no3_record.list
                if "NO" in str(w.message) and "none was supplied" in str(w.message)]
    assert len(no3_msgs) == 1

    gdgt_msg, no3_msg = gdgt_msgs[0], no3_msgs[0]
    for phrase in ("treated as 0", "not the same as switching",
                   "biases the reconstruction"):
        assert phrase in gdgt_msg
        assert phrase in no3_msg
