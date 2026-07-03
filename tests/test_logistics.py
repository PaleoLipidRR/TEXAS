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
