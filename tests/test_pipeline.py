"""Behavioral tests for the core TEXAS pipeline.

Unlike test_logistics (pure curve math) these exercise the user-facing science:
compute_scaledRI, build_fwd_data, and the forward ensemble path
(predict_proxy_from_T → generate_ensemble_auto → detect_model_and_params).

The prediction test builds a small synthetic posterior in-memory so it runs in
CI without a cached .nc file or any network access.
"""

import numpy as np
import pytest
import xarray as xr

from TEXAS import compute_scaledRI, predict_proxy_from_T
from TEXAS.data.builder import build_fwd_data


class TestComputeScaledRI:
    def test_known_value(self):
        """Matches the hand-computed RI₀₋₃ for a fixed set of abundances.

        numerator = 0.10 + 2·0.08 + 3·0.05 + 3·0.30 + 3·0.02 = 1.37
        denominator = (0.45+0.10+0.08+0.05+0.30+0.02)·3 = 3.0
        scaledRI = 1.37 / 3.0 = 0.45666…
        """
        v = compute_scaledRI(0.45, 0.10, 0.08, 0.05, 0.30, 0.02)
        assert float(v) == pytest.approx(0.456667, abs=1e-5)

    def test_scale_invariance(self):
        """Common scale factor cancels (raw peak areas vs fractions agree)."""
        a = compute_scaledRI(0.45, 0.10, 0.08, 0.05, 0.30, 0.02)
        b = compute_scaledRI(4.5, 1.0, 0.8, 0.5, 3.0, 0.2)
        assert float(a) == pytest.approx(float(b), abs=1e-12)

    def test_cren_rings_changes_result(self):
        """cren_rings=4 (RI₀₋₄) differs from the default cren_rings=3."""
        v3 = compute_scaledRI(0.45, 0.10, 0.08, 0.05, 0.30, 0.02)
        v4 = compute_scaledRI(0.45, 0.10, 0.08, 0.05, 0.30, 0.02, cren_rings=4)
        assert float(v3) != pytest.approx(float(v4))

    def test_all_gdgt0_gives_zero(self):
        """A sample that is pure GDGT-0 has no rings → scaledRI = 0."""
        assert float(compute_scaledRI(1.0, 0.0, 0.0, 0.0, 0.0, 0.0)) == pytest.approx(0.0)

    def test_monotonic_in_ring_content(self):
        """Shifting abundance from GDGT-0 to a high-ring component raises RI."""
        low = compute_scaledRI(0.9, 0.1, 0.0, 0.0, 0.0, 0.0)
        high = compute_scaledRI(0.1, 0.1, 0.0, 0.0, 0.8, 0.0)  # cren carries 3 rings
        assert float(high) > float(low)

    def test_vectorized(self):
        """Array inputs return an array of matching shape, bounded in [0, 1]."""
        g0 = np.array([0.45, 0.20, 0.80])
        out = compute_scaledRI(g0, np.array([0.10, 0.30, 0.05]),
                               np.array([0.08, 0.20, 0.05]),
                               np.array([0.05, 0.10, 0.02]),
                               np.array([0.30, 0.18, 0.07]),
                               np.array([0.02, 0.02, 0.01]))
        assert out.shape == (3,)
        assert np.all(out >= 0.0) and np.all(out <= 1.0)


class TestBuildFwdData:
    def test_culmeso_dict_shape_and_contents(self):
        """A culture+mesocosm build yields the expected keys, counts, arrays."""
        t_cul = np.array([5.0, 25.0])
        p_cul = np.array([0.2, 0.7])
        t_meso = np.array([10.0, 20.0, 30.0])
        p_meso = np.array([0.3, 0.6, 0.8])

        d = build_fwd_data(t_cul=t_cul, proxy_cul=p_cul,
                           t_meso=t_meso, proxy_meso=p_meso)

        assert set(d) >= {"N_cul", "N_meso", "proxyObs_cul",
                          "proxyObs_meso", "t_cul", "t_meso"}
        assert d["N_cul"] == 2
        assert d["N_meso"] == 3
        np.testing.assert_allclose(d["proxyObs_cul"], p_cul)
        np.testing.assert_allclose(d["t_meso"], t_meso)


def _synthetic_posterior(seed: int = 0) -> xr.Dataset:
    """A minimal valid univariate (crtp) generalized-logistic forward posterior."""
    rng = np.random.default_rng(seed)
    nd = 60
    return xr.Dataset(
        {
            "t0_crtp": (("chain", "draw"), rng.normal(20.0, 0.8, (2, nd))),
            "k_crtp": (("chain", "draw"), rng.normal(0.20, 0.01, (2, nd))),
            "b_crtp": (("chain", "draw"), rng.normal(0.10, 0.01, (2, nd))),
            "v_crtp": (("chain", "draw"), rng.normal(1.00, 0.05, (2, nd))),
        },
        attrs={"proxy_name": "scaledRI_cren3"},
    )


class TestPredictProxyFromT:
    """Forward ensemble path on an in-memory posterior (no cache / network)."""

    def test_returns_expected_quantile_keys(self):
        out = predict_proxy_from_T(np.array([10.0, 20.0]), _synthetic_posterior())
        assert {"x_vals", "p5", "p50", "p95"} <= set(out)

    def test_quantiles_ordered_and_bounded(self):
        out = predict_proxy_from_T(np.array([5.0, 15.0, 25.0, 35.0]),
                                   _synthetic_posterior())
        assert np.all(out["p5"] <= out["p50"])
        assert np.all(out["p50"] <= out["p95"])
        assert np.all(out["p50"] >= 0.0) and np.all(out["p50"] <= 1.0)

    def test_proxy_increases_with_temperature(self):
        """RI is a rising S-curve in temperature → median is non-decreasing."""
        out = predict_proxy_from_T(np.array([5.0, 15.0, 25.0, 35.0]),
                                   _synthetic_posterior())
        assert np.all(np.diff(out["p50"]) >= 0.0)
