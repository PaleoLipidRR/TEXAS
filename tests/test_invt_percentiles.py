"""The percentile reduction that used to live in predict_temperature_from_proxyObs.

Layer 2 hard-coded eleven keys against a thirteen-quantile posterior, so p40 and
p60 were computed and thrown away, and any non-default quantile set raised
KeyError on 0.01. The keys now follow the quantiles the dataset actually has.
"""
import inspect

import numpy as np
import pytest
import xarray as xr

from TEXAS.stan.invT import _percentiles_from_posterior


def _quantile_ds(quantiles, n_obs=4):
    """A reduced invT posterior: t_est over (quantile, obs)."""
    values = np.tile(np.asarray(quantiles, dtype=float)[:, None] * 100.0, (1, n_obs))
    return xr.Dataset(
        {"t_est": (("quantile", "obs_idx"), values)},
        coords={"quantile": list(quantiles), "obs_idx": np.arange(n_obs)},
    )


def test_default_quantiles_give_thirteen_keys_including_p40_and_p60():
    """The eleven hard-coded keys silently dropped these two."""
    defaults = (0.01, 0.05, 0.1, 0.16, 0.25, 0.4, 0.5,
                0.6, 0.75, 0.84, 0.9, 0.95, 0.99)
    out = _percentiles_from_posterior(_quantile_ds(defaults))
    assert set(out) == {"p1", "p5", "p10", "p16", "p25", "p40", "p50",
                        "p60", "p75", "p84", "p90", "p95", "p99"}


def test_values_match_the_quantile_they_are_named_for():
    out = _percentiles_from_posterior(_quantile_ds((0.05, 0.5, 0.95)))
    np.testing.assert_allclose(out["p5"], 5.0)
    np.testing.assert_allclose(out["p50"], 50.0)
    np.testing.assert_allclose(out["p95"], 95.0)


def test_arrays_are_one_per_observation():
    out = _percentiles_from_posterior(_quantile_ds((0.05, 0.5, 0.95), n_obs=7))
    assert out["p50"].shape == (7,)


def test_a_custom_quantile_set_is_honoured_not_rejected():
    """The old code raised KeyError on 0.01 for any set that omitted it."""
    out = _percentiles_from_posterior(_quantile_ds((0.025, 0.5, 0.975)))
    assert set(out) == {"p2", "p50", "p98"}, out.keys()


def test_colliding_keys_raise_rather_than_overwrite():
    """0.005 and 0.0049 both round to p0; silently keeping one is the bug."""
    with pytest.raises(ValueError, match="distinct keys"):
        _percentiles_from_posterior(_quantile_ds((0.005, 0.0049, 0.5)))


def test_missing_t_est_is_a_clear_error():
    ds = xr.Dataset({"sigma": (("quantile",), [1.0])}, coords={"quantile": [0.5]})
    with pytest.raises(KeyError, match="t_est"):
        _percentiles_from_posterior(ds)


def test_layer_two_is_gone():
    """predict_temperature_from_proxyObs folded into predict_T_from_proxyObs."""
    import TEXAS
    import TEXAS.stan
    import TEXAS.stan.invT as invT

    assert not hasattr(invT, "predict_temperature_from_proxyObs")
    assert not hasattr(TEXAS, "predict_temperature_from_proxyObs")
    assert "predict_temperature_from_proxyObs" not in TEXAS.__all__
    assert "predict_temperature_from_proxyObs" not in TEXAS.stan.__all__


@pytest.mark.parametrize("param", ["use_opencl", "scaledRI", "model_type", "save"])
def test_dead_parameters_are_gone_from_get_invT_posterior(param):
    from TEXAS.stan.invT import get_invT_posterior
    assert param not in inspect.signature(get_invT_posterior).parameters


def test_the_three_inputs_are_positional_required():
    """They were keyword-with-None and raised a runtime TypeError instead."""
    from TEXAS.stan.invT import get_invT_posterior
    params = inspect.signature(get_invT_posterior).parameters
    for name in ("proxyObs", "prior_mu_t", "prior_sigma_t"):
        assert params[name].default is inspect.Parameter.empty, f"{name} still defaults"
        assert params[name].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD


def test_save_results_defaults_to_false_everywhere():
    from TEXAS.predict import predict_T_from_proxyObs
    from TEXAS.stan.invT import get_invT_posterior
    for fn in (predict_T_from_proxyObs, get_invT_posterior):
        assert inspect.signature(fn).parameters["save_results"].default is False


def test_scaledRI_alias_is_gone_from_the_builder():
    from TEXAS.data.builder import build_invT_inputData
    assert "scaledRI" not in inspect.signature(build_invT_inputData).parameters


def test_sampler_invT_posterior_does_not_forward_model_type(monkeypatch):
    """It used to reach CmdStanModel.sample, which has no such parameter."""
    from TEXAS.stan import sampler as sampler_mod

    seen = {}

    def fake_sample(self, data, stan_file, cpp_options=None, **kwargs):
        seen.update(kwargs)
        return "posterior", "diagnostics"

    monkeypatch.setattr(sampler_mod.StanSampler, "sample", fake_sample)
    sampler_mod.sampler_invT_posterior({"N": 1}, "invT_gen_logi_fixed_univ_marginal_unconstrained")

    assert "model_type" not in seen
    assert "model_type" not in inspect.signature(sampler_mod.sampler_invT_posterior).parameters
