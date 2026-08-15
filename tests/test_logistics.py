"""Unit tests for TEXAS.models.logistics and TEXAS.models.multivariate."""

import numpy as np
import pytest

from TEXAS.models.logistics import (
    logistic,
    logistic_fixed_upper,
    generalized_logistic_fixed_upper,
)
from TEXAS.models.multivariate import (
    generalized_logistic_fixed_upper_multivariate,
    inverse_generalized_logistic_fixed_upper_multivariate,
)


class TestLogistic:
    def test_midpoint_returns_half_range(self):
        """logistic at t0 returns b + L/2."""
        result = logistic(x=0.0, t0=0.0, L=1.0, k=1.0, b=0.0)
        assert result == pytest.approx(0.5, abs=1e-10)

    def test_midpoint_with_offset(self):
        """logistic at t0 with lower asymptote b returns b + (L/2)."""
        result = logistic(x=5.0, t0=5.0, L=2.0, k=1.0, b=0.1)
        assert result == pytest.approx(1.1, abs=1e-10)

    def test_missing_params_raises(self):
        with pytest.raises(ValueError):
            logistic(x=0.0, t0=None, L=1.0, k=1.0, b=0.0)


class TestLogisticFixedUpper:
    def test_midpoint_returns_midrange(self):
        """logistic_fixed_upper at t0 should return b + (1-b)/2."""
        b = 0.2
        result = logistic_fixed_upper(x=0.0, t0=0.0, k=1.0, b=b)
        assert result == pytest.approx(b + (1.0 - b) / 2.0, abs=1e-10)

    def test_upper_bound_approach(self):
        """At large x, value approaches 1."""
        result = logistic_fixed_upper(x=1000.0, t0=0.0, k=1.0, b=0.0)
        assert result == pytest.approx(1.0, abs=1e-6)

    def test_lower_bound_approach(self):
        """At large negative x, value approaches b."""
        b = 0.05
        result = logistic_fixed_upper(x=-1000.0, t0=0.0, k=1.0, b=b)
        assert result == pytest.approx(b, abs=1e-6)


class TestGeneralizedLogisticFixedUpper:
    def test_approaches_upper_asymptote(self):
        """At large x, result approaches 1."""
        result = generalized_logistic_fixed_upper(
            x=1000.0, t0=0.0, b=0.0, k=1.0, v=1.0
        )
        assert result == pytest.approx(1.0, abs=1e-6)

    def test_approaches_lower_asymptote(self):
        """At large negative x, result approaches b."""
        b = 0.05
        result = generalized_logistic_fixed_upper(
            x=-1000.0, t0=0.0, b=b, k=1.0, v=1.0
        )
        assert result == pytest.approx(b, abs=1e-6)

    def test_array_input(self):
        """Accepts array input and returns array."""
        x = np.linspace(-10, 10, 50)
        result = generalized_logistic_fixed_upper(x=x, t0=0.0, b=0.0, k=1.0, v=1.0)
        assert result.shape == (50,)
        assert np.all(result >= 0.0)
        assert np.all(result <= 1.0)

    def test_v_defaults_to_one(self):
        """Omitting v should give same result as v=1 (Q is fixed at 1)."""
        x = np.array([0.0, 5.0, 10.0])
        r_default = generalized_logistic_fixed_upper(x=x, t0=0.0, b=0.0, k=0.5)
        r_explicit = generalized_logistic_fixed_upper(x=x, t0=0.0, b=0.0, k=0.5, v=1.0)
        np.testing.assert_allclose(r_default, r_explicit)


class TestGeneralizedLogisticMultivariate:
    def test_runs_without_predictors(self):
        """Multivariate function runs fine with no optional predictors."""
        x = np.linspace(-5, 5, 20)
        result = generalized_logistic_fixed_upper_multivariate(
            x=x, t0=0.0, b=0.0, k=1.0, v=1.0
        )
        assert result.shape == (20,)

    def test_gdgt23_correction_applied(self):
        """Adding a nonzero beta_G23 changes the result."""
        x = np.zeros(5)
        gdgt23 = np.ones(5) * 0.1
        r_no_correction = generalized_logistic_fixed_upper_multivariate(
            x=x, t0=0.0, b=0.0, k=1.0
        )
        r_with_correction = generalized_logistic_fixed_upper_multivariate(
            x=x, t0=0.0, b=0.0, k=1.0, beta_G23=0.5, gdgt23ratio=gdgt23
        )
        assert not np.allclose(r_no_correction, r_with_correction)

    def test_no3_correction_applied_below_cutoff(self):
        """NO3 correction is applied where 0 < no3 < no3_cutoff."""
        x = np.zeros(5)
        no3 = np.array([1.0, 5.0, 10.0, 20.0, 30.0])
        r_base = generalized_logistic_fixed_upper_multivariate(
            x=x, t0=0.0, b=0.0, k=1.0
        )
        r_no3 = generalized_logistic_fixed_upper_multivariate(
            x=x, t0=0.0, b=0.0, k=1.0, beta_NO3=0.1, no3=no3, no3_cutoff=50.0
        )
        assert not np.allclose(r_base, r_no3)

    def test_no3_correction_not_applied_above_cutoff(self):
        """NO3 correction is skipped where no3 >= no3_cutoff."""
        x = np.zeros(3)
        no3_above = np.array([100.0, 200.0, 300.0])
        r_base = generalized_logistic_fixed_upper_multivariate(
            x=x, t0=0.0, b=0.0, k=1.0
        )
        r_no3 = generalized_logistic_fixed_upper_multivariate(
            x=x, t0=0.0, b=0.0, k=1.0, beta_NO3=0.5, no3=no3_above, no3_cutoff=50.0
        )
        np.testing.assert_allclose(r_base, r_no3)


class TestInverseGeneralizedLogisticMultivariate:
    # A single, realistic parameter set reused across round-trip tests.
    PARAMS = dict(t0=15.0, b=0.05, k=0.4, v=1.3)

    def test_roundtrip_no_predictors(self):
        """inverse(forward(x)) recovers x with no corrections."""
        x = np.linspace(0.0, 30.0, 25)
        y = generalized_logistic_fixed_upper_multivariate(x=x, **self.PARAMS)
        x_rec = inverse_generalized_logistic_fixed_upper_multivariate(
            y=y, **self.PARAMS
        )
        np.testing.assert_allclose(x_rec, x, atol=1e-8)

    def test_roundtrip_with_gdgt23_per_sample(self):
        """Round-trip holds with a per-sample GDGT-2/3 correction."""
        x = np.linspace(0.0, 30.0, 25)
        g23 = np.linspace(-0.3, 0.4, 25)
        kw = dict(**self.PARAMS, beta_G23=0.12, gdgt23ratio=g23)
        y = generalized_logistic_fixed_upper_multivariate(x=x, **kw)
        x_rec = inverse_generalized_logistic_fixed_upper_multivariate(y=y, **kw)
        np.testing.assert_allclose(x_rec, x, atol=1e-8)

    def test_roundtrip_with_no3_below_cutoff(self):
        """Round-trip holds with an NO3 correction (all below cutoff)."""
        x = np.linspace(5.0, 28.0, 20)
        no3 = np.linspace(0.5, 4.0, 20)
        kw = dict(**self.PARAMS, beta_NO3=0.08, no3=no3, no3_cutoff=5.0)
        y = generalized_logistic_fixed_upper_multivariate(x=x, **kw)
        x_rec = inverse_generalized_logistic_fixed_upper_multivariate(y=y, **kw)
        np.testing.assert_allclose(x_rec, x, atol=1e-8)

    def test_roundtrip_with_both_corrections(self):
        """Round-trip holds with both G23 and NO3 corrections together."""
        x = np.linspace(5.0, 28.0, 20)
        g23 = np.linspace(-0.2, 0.3, 20)
        no3 = np.linspace(0.5, 4.0, 20)
        kw = dict(
            **self.PARAMS,
            beta_G23=0.1, gdgt23ratio=g23,
            beta_NO3=0.08, no3=no3, no3_cutoff=5.0,
        )
        y = generalized_logistic_fixed_upper_multivariate(x=x, **kw)
        x_rec = inverse_generalized_logistic_fixed_upper_multivariate(y=y, **kw)
        np.testing.assert_allclose(x_rec, x, atol=1e-8)

    def test_scalar_predictor_broadcasts(self):
        """A scalar gdgt23ratio is applied to every sample."""
        x = np.linspace(5.0, 25.0, 10)
        # Forward with a constant array vs inverse with a scalar → same recovery.
        y = generalized_logistic_fixed_upper_multivariate(
            x=x, **self.PARAMS, beta_G23=0.15, gdgt23ratio=np.full(10, 0.2)
        )
        x_rec = inverse_generalized_logistic_fixed_upper_multivariate(
            y=y, **self.PARAMS, beta_G23=0.15, gdgt23ratio=0.2
        )
        np.testing.assert_allclose(x_rec, x, atol=1e-8)

    def test_scalar_input_returns_scalar_shape(self):
        """Scalar proxy in → 0-d array out (matches forward convention)."""
        y = generalized_logistic_fixed_upper_multivariate(x=15.0, **self.PARAMS)
        x_rec = inverse_generalized_logistic_fixed_upper_multivariate(
            y=float(y), **self.PARAMS
        )
        assert x_rec.shape == ()
        assert x_rec == pytest.approx(15.0, abs=1e-8)

    def test_out_of_range_returns_nan_and_warns(self):
        """Proxy values outside (b, 1) return NaN with a RuntimeWarning."""
        b = self.PARAMS["b"]
        # 0.5 is reconstructable; b-0.1 (below lower asymptote) and 1.5 are not.
        y = np.array([b - 0.1, 0.5, 1.5])
        with pytest.warns(RuntimeWarning):
            x_rec = inverse_generalized_logistic_fixed_upper_multivariate(
                y=y, **self.PARAMS
            )
        assert np.isnan(x_rec[0])
        assert np.isfinite(x_rec[1])
        assert np.isnan(x_rec[2])

    def test_unbroadcastable_predictor_raises(self):
        """A predictor whose length mismatches the proxy raises ValueError."""
        y = np.full(5, 0.5)
        with pytest.raises(ValueError):
            inverse_generalized_logistic_fixed_upper_multivariate(
                y=y, **self.PARAMS, beta_G23=0.1, gdgt23ratio=np.ones(3)
            )

    def test_missing_params_raises(self):
        with pytest.raises(ValueError):
            inverse_generalized_logistic_fixed_upper_multivariate(
                y=0.5, t0=None, b=0.05, k=0.4
            )


class TestBoundedTMultivariate:
    """Bounded-T shifts T0 instead of mu, so the curve cannot leave (b, 1).

    Added 2026-08-12 with the function itself: bounded-T support landed across
    the package (builder, invT, metadata, naming, prior_plot) but the ensemble
    path was missed, so generate_ensemble_auto() raised
    "Missing parameters: ['beta_G23_crtp', 'beta_NO3_crtp']" on every bounded-T
    posterior -- it has gamma_* coefficients, not beta_*.
    """

    def _kw(self):
        return dict(t0=25.0, b=0.4, k=0.3, v=1.5)

    def test_reduces_to_plain_curve_without_predictors(self):
        import numpy as np
        from TEXAS.models.multivariate import (
            generalized_logistic_fixed_upper_t0shift as fbnd)
        from TEXAS.models.logistics import generalized_logistic_fixed_upper

        x = np.linspace(0, 40, 25)
        np.testing.assert_allclose(
            fbnd(x, **self._kw()),
            generalized_logistic_fixed_upper(x, **self._kw()),
            rtol=1e-12)

    def test_stays_inside_open_interval_for_extreme_predictors(self):
        import numpy as np
        from TEXAS.models.multivariate import (
            generalized_logistic_fixed_upper_t0shift as fbnd,
            generalized_logistic_fixed_upper_multivariate as fadd)

        x = np.linspace(0, 40, 25)
        b = self._kw()["b"]
        huge = np.full_like(x, 50.0)          # absurd G2/3, to make the point

        y = fbnd(x, **self._kw(), gamma_G23=3.0, gdgt23ratio=huge)
        assert np.all(y > b) and np.all(y < 1.0)

        # the additive form is what bounded-T exists to fix: it leaves (b, 1)
        y_add = fadd(x, **self._kw(), beta_G23=3.0, gdgt23ratio=huge)
        assert np.any(y_add > 1.0)

    def test_no3_gate_matches_the_stan_model(self):
        import numpy as np
        from TEXAS.models.multivariate import (
            generalized_logistic_fixed_upper_t0shift as fbnd)

        x = np.linspace(0, 40, 4)
        # only the middle two are inside (0, cutoff) and may be shifted
        no3 = np.array([0.0, 0.5, 0.9, 5.0])
        base = fbnd(x, **self._kw())
        y = fbnd(x, **self._kw(), gamma_NO3=4.0, no3=no3, no3_cutoff=1.0)
        np.testing.assert_allclose(y[[0, 3]], base[[0, 3]], rtol=1e-12)
        assert not np.allclose(y[[1, 2]], base[[1, 2]])

    def test_detector_dispatches_on_gamma_coefficients(self):
        import numpy as np
        import xarray as xr
        from TEXAS.ensemble.detection import detect_model_and_params
        from TEXAS.models.multivariate import (
            generalized_logistic_fixed_upper_t0shift as fbnd)

        dims = ("chain", "draw")
        shape = (1, 3)
        ds = xr.Dataset(
            {n: (dims, np.ones(shape)) for n in
             ("t0_crtp", "b_crtp", "k_crtp", "v_crtp",
              "gamma_G23_crtp", "gamma_NO3_crtp")},
            attrs={"use_gdgt23ratio": 1, "use_no3": 1, "no3_cutoff": 1.0},
        )
        det = detect_model_and_params(ds)
        assert det["model_function"] is fbnd
        assert det["param_names"] == ["t0", "b", "k", "v",
                                      "gamma_G23", "gamma_NO3"]
        assert det["suffix"] == "crtp"


def test_bounded_t_legacy_alias():
    """The pre-rename callable name must keep working (2026-08-15 rename)."""
    from TEXAS.models.multivariate import (
        generalized_logistic_fixed_upper_bounded_t,
        generalized_logistic_fixed_upper_t0shift,
    )
    assert generalized_logistic_fixed_upper_bounded_t is generalized_logistic_fixed_upper_t0shift
