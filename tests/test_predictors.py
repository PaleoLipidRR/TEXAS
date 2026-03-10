"""Tests for auto_detect_predictors() in TEXAS.stan.sampler."""

import numpy as np
import pytest

from TEXAS.stan.sampler import auto_detect_predictors


def _base_data():
    """Minimal data dict with coretop arrays."""
    n = 10
    return {
        "N_crtp": n,
        "scaledRI_crtp": np.random.default_rng(0).uniform(0.1, 0.9, n).tolist(),
        "SST_crtp": np.random.default_rng(1).uniform(5, 30, n).tolist(),
    }


class TestAutoDetectPredictors:
    def test_detects_gdgt23_when_present(self):
        """Dict with a non-empty gdgt23ratio array → use_gdgt23ratio == 1."""
        data = _base_data()
        data["gdgt23ratio_crtp"] = np.ones(10).tolist()
        result = auto_detect_predictors(data)
        assert result.get("use_gdgt23ratio") == 1

    def test_no_gdgt23_flag_when_absent(self):
        """Dict without any gdgt23ratio array → use_gdgt23ratio == 0."""
        data = _base_data()
        result = auto_detect_predictors(data)
        assert result.get("use_gdgt23ratio") == 0

    def test_detects_no3_when_present(self):
        """Dict with a non-empty no3 array → use_no3 == 1."""
        data = _base_data()
        data["no3_crtp"] = np.full(10, 5.0).tolist()
        result = auto_detect_predictors(data)
        assert result.get("use_no3") == 1

    def test_no_no3_flag_when_absent(self):
        """Dict without any no3 array → use_no3 == 0."""
        data = _base_data()
        result = auto_detect_predictors(data)
        assert result.get("use_no3") == 0

    def test_explicit_flag_overrides_auto_detect(self):
        """Explicit use_gdgt23ratio in dict is not overwritten by auto-detect."""
        data = _base_data()
        data["gdgt23ratio_crtp"] = np.ones(10).tolist()
        # Explicitly set to 0 (override)
        data["use_gdgt23ratio"] = 0
        result = auto_detect_predictors(data)
        assert result.get("use_gdgt23ratio") == 0

    def test_explicit_no3_flag_overrides_auto_detect(self):
        """Explicit use_no3 in dict is not overwritten by auto-detect."""
        data = _base_data()
        data["no3_crtp"] = np.full(10, 5.0).tolist()
        data["use_no3"] = 0
        result = auto_detect_predictors(data)
        assert result.get("use_no3") == 0

    def test_all_nan_array_not_detected(self):
        """An all-NaN gdgt23ratio array is NOT counted as 'present'."""
        data = _base_data()
        data["gdgt23ratio_crtp"] = [float("nan")] * 10
        result = auto_detect_predictors(data)
        assert result.get("use_gdgt23ratio") == 0

    def test_original_data_not_mutated(self):
        """auto_detect_predictors returns a new dict; original is unchanged."""
        data = _base_data()
        original_keys = set(data.keys())
        auto_detect_predictors(data)
        assert set(data.keys()) == original_keys
