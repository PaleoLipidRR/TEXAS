"""
Every sampled dataset must carry its stan_diag_* summary.

This is not a cosmetic metadata check. ``StanSampler.sample_from_model`` is the
entry point the whole inverse-temperature path uses, and the CmdStanMCMC object
is the only thing that knows R-hat, ESS and the divergence count. It goes out of
scope the moment that method returns, and ``get_invT_post_quantiles`` then
reduces the draws over chain and draw before the reconstruction is saved -- so a
fit whose diagnostics were not attached here can never have them recomputed from
the file on disk. That is exactly how 35 cached invT posteriors ended up with no
convergence record at all.

No CmdStan required: these drive the method with a stub fit.
"""
import numpy as np
import pytest
import xarray as xr

from TEXAS.stan.sampler import StanSampler, _with_diagnostics


class _StubFit:
    """Minimal stand-in for CmdStanMCMC: draws plus the diagnostic surface."""

    def __init__(self, n_chains=4, n_draws=50, diverging=0):
        self.chains = n_chains
        rng = np.random.default_rng(0)
        self._draws = rng.normal(size=(n_chains, n_draws))
        self._diverging = diverging
        self.method_variables_called = False

    def draws_xr(self):
        return xr.Dataset(
            {"t_est": (("chain", "draw"), self._draws)},
            coords={"chain": np.arange(self.chains),
                    "draw": np.arange(self._draws.shape[1])},
        )

    def method_variables(self):
        self.method_variables_called = True
        n = self._draws.shape[1]
        div = np.zeros((n, self.chains))
        div.flat[:self._diverging] = 1
        return {"divergent__": div,
                "treedepth__": np.full((n, self.chains), 3.0),
                "energy__": np.tile(np.linspace(0, 1, n)[:, None], self.chains)}

    def summary(self):
        import pandas as pd
        return pd.DataFrame({"R_hat": [1.002], "ESS_bulk": [1200.0],
                             "ESS_tail": [900.0]}, index=["t_est"])


class _StubModel:
    def __init__(self, fit):
        self._fit = fit
        self.stan_file = "stub.stan"

    def sample(self, data=None, **kwargs):
        return self._fit


def test_sample_from_model_attaches_diagnostics():
    sampler = StanSampler(compiler=None)
    ds = sampler.sample_from_model(_StubModel(_StubFit()), {"N": 10})
    stamped = {k for k in ds.attrs if k.startswith("stan_diag_")}
    assert stamped, (
        "no stan_diag_* attrs on the returned dataset; the fit object is gone "
        "by now, so these can never be recovered downstream"
    )
    assert "stan_diag_max_rhat" in stamped
    assert "stan_diag_min_ess_bulk" in stamped


def test_divergences_survive_to_the_dataset():
    """A silent divergence count is worse than none: it reads as a clean run."""
    sampler = StanSampler(compiler=None)
    ds = sampler.sample_from_model(_StubModel(_StubFit(diverging=7)), {"N": 10})
    assert ds.attrs["stan_diag_n_divergent"] == 7


def test_draws_are_unchanged_by_the_stamping():
    fit = _StubFit()
    ds = _with_diagnostics(fit)
    xr.testing.assert_allclose(ds["t_est"], fit.draws_xr()["t_est"])


def test_a_failed_summary_does_not_lose_the_fit():
    """
    Diagnostics are advisory; the sampling is the expensive part. If summarising
    raises, the draws must still come back rather than an exception discarding
    an hour of compute.
    """
    class _Broken(_StubFit):
        def method_variables(self):
            raise RuntimeError("cmdstanpy build lacks this")

    with pytest.warns(RuntimeWarning, match="diagnostics"):
        ds = _with_diagnostics(_Broken())
    assert "t_est" in ds
