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
