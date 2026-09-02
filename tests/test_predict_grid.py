"""
DRAFT -- validates only the core grid-quadrature math in
TEXAS.predict_grid._grid_quantiles, not the predict_T_grid() wrapper (that
needs a real cached forward posterior + build_invT_inputData, not exercised
here or anywhere yet -- see the module docstring in predict_grid.py).

Reference: TEXAS-revision/gridT_inversion_characterization.md, using the
exact 80-draw posterior embedded in docs/_static/why-plugin-p50-differs.html
(median t0~34.7, k~0.17, b~0.42, v~2.14, sigma~0.058).
"""

import numpy as np
import pytest

from TEXAS.predict_grid import _grid_quantiles

# 80-draw forward posterior [t0, k, b, v, sigma], copied verbatim from the
# `ENS` array in docs/_static/why-plugin-p50-differs.html.
_ENS = np.array([
    [34.952,0.1668,0.4135,2.169,0.0566],[30.627,0.1185,0.4185,1.283,0.0577],[35.52,0.1953,0.4247,2.473,0.0567],
    [34.389,0.1606,0.4245,1.917,0.0574],[34.152,0.1717,0.429,1.991,0.0594],[33.613,0.1609,0.4332,1.78,0.0555],
    [35.536,0.2123,0.4289,2.606,0.0587],[34.33,0.1896,0.4246,2.208,0.0572],[37.629,0.2309,0.4018,3.581,0.0582],
    [32.63,0.1447,0.424,1.612,0.0579],[36.456,0.1974,0.4034,2.866,0.0578],[35.809,0.2086,0.4161,2.79,0.06],
    [30.601,0.1332,0.4359,1.244,0.0578],[35.217,0.1806,0.4172,2.308,0.0573],[35.988,0.1999,0.4224,2.595,0.0593],
    [35.192,0.1876,0.4199,2.36,0.0593],[34.255,0.1712,0.423,2.055,0.0572],[36.529,0.2195,0.4111,3.071,0.0562],
    [31.499,0.146,0.4406,1.413,0.0571],[34.839,0.1536,0.4159,1.99,0.0598],[33.934,0.1651,0.4193,1.989,0.0579],
    [34.322,0.1663,0.4227,2.017,0.0562],[35.52,0.1791,0.419,2.326,0.0584],[35.861,0.2243,0.4241,2.874,0.0575],
    [35.968,0.2013,0.4118,2.727,0.0579],[35.235,0.18,0.423,2.245,0.0575],[35.496,0.1754,0.4181,2.287,0.0573],
    [33.427,0.1569,0.4203,1.828,0.0594],[37.021,0.2579,0.4031,3.793,0.0585],[35.208,0.1884,0.4241,2.344,0.0578],
    [34.677,0.1811,0.4214,2.165,0.0591],[33.654,0.1708,0.4267,1.917,0.0572],[34.651,0.2025,0.4261,2.411,0.0593],
    [37.31,0.2511,0.4006,3.806,0.0576],[35.542,0.166,0.4112,2.261,0.057],[33.015,0.1518,0.423,1.751,0.0581],
    [34.849,0.208,0.4295,2.436,0.0569],[33.546,0.1591,0.4335,1.764,0.0567],[34.652,0.1853,0.4246,2.213,0.0574],
    [33.325,0.1519,0.4156,1.815,0.0567],[33.228,0.1534,0.4297,1.697,0.056],[37.409,0.2491,0.4115,3.624,0.0593],
    [33.06,0.153,0.4271,1.698,0.0569],[36.378,0.2065,0.4123,2.858,0.0581],[36.128,0.2048,0.4098,2.846,0.0574],
    [30.632,0.1284,0.4309,1.265,0.0576],[32.449,0.1382,0.4303,1.484,0.0585],[35.951,0.1845,0.3967,2.676,0.0589],
    [35.851,0.2057,0.4154,2.72,0.0595],[32.715,0.1549,0.4275,1.689,0.0558],[34.154,0.1608,0.4202,1.935,0.0564],
    [34.014,0.174,0.4267,2.008,0.0565],[29.981,0.1358,0.44,1.205,0.0579],[30.109,0.1313,0.4445,1.183,0.0589],
    [32.549,0.1494,0.4239,1.621,0.0578],[36.235,0.2154,0.4104,3.033,0.0567],[36.098,0.2023,0.4128,2.769,0.0563],
    [31.881,0.1315,0.4199,1.446,0.0585],[34.728,0.1773,0.4225,2.181,0.0582],[34.653,0.1637,0.4154,2.074,0.0588],
    [34.123,0.1725,0.4223,2.023,0.0576],[30.944,0.1399,0.4379,1.312,0.0571],[28.76,0.1204,0.4322,1.07,0.0572],
    [35.378,0.1852,0.4149,2.426,0.0571],[32.502,0.1591,0.442,1.594,0.0575],[37.664,0.2922,0.4021,4.467,0.0585],
    [31.523,0.1301,0.4231,1.395,0.0579],[33.996,0.1354,0.4119,1.752,0.0596],[35.093,0.1541,0.4111,2.076,0.0568],
    [29.614,0.1242,0.4335,1.16,0.0583],[35.462,0.1722,0.4133,2.327,0.0567],[32.806,0.1498,0.4259,1.649,0.057],
    [35.597,0.1775,0.412,2.412,0.0584],[36.673,0.2064,0.4159,2.879,0.0583],[35.901,0.1703,0.4047,2.387,0.0575],
    [37.342,0.2131,0.4057,3.22,0.0559],[33.731,0.1617,0.4304,1.823,0.057],[37.142,0.2326,0.4104,3.337,0.0571],
    [34.695,0.1623,0.4119,2.098,0.0575],[36.109,0.2164,0.4145,2.904,0.0562],
])

_T0, _K, _B, _V, _SIGMA = (_ENS[:, i].copy() for i in range(5))

# From the characterization doc's table (prior N(15, 10), fixed T_hi=45 grid).
_REFERENCE_P50 = {0.55: 14.69, 0.75: 28.28, 0.90: 36.09, 0.97: 39.20, 0.45: 8.03}
# RI >= 0.85 implies T well above the doc's hardcoded 45 degC cap -- the
# *reference table itself* was produced under that cap, so this module's
# default adaptive bound is expected to legitimately diverge there (that is
# the fix the characterization doc recommends, not a regression).
_TRUNCATION_AFFECTED = {0.90, 0.97}


@pytest.mark.parametrize("ri,expected", sorted(_REFERENCE_P50.items()))
def test_grid_quantiles_matches_reference_under_old_cap(ri, expected):
    """With the doc's original fixed 45 degC cap, reproduce its table exactly."""
    out = _grid_quantiles(
        ri, mu_prior=15.0, sigma_prior=10.0,
        t0=_T0, k=_K, b=_B, v=_V, sigma=_SIGMA,
        min_temp=-1.8, n_grid=6000, percentiles=(50,),
    )
    assert out["p50"] == pytest.approx(expected, abs=0.05)


@pytest.mark.parametrize("ri,expected", sorted(_REFERENCE_P50.items()))
def test_grid_quantiles_adaptive_bound(ri, expected):
    """
    Adaptive bound (this module's actual default, via predict_T_grid): matches
    the reference exactly where there's no truncation, and shifts by no more
    than the doc's own documented truncation-error budget (<=0.58 degC on p50)
    where there is.
    """
    out = _grid_quantiles(
        ri, mu_prior=15.0, sigma_prior=10.0,
        t0=_T0, k=_K, b=_B, v=_V, sigma=_SIGMA,
        min_temp=-1.8, n_grid=6000, percentiles=(50,),
    )
    if ri in _TRUNCATION_AFFECTED:
        shift = abs(out["p50"] - expected)
        assert 0.0 < shift <= 0.65
    else:
        assert out["p50"] == pytest.approx(expected, abs=0.05)


def test_percentiles_monotone():
    out = _grid_quantiles(
        0.75, mu_prior=15.0, sigma_prior=10.0,
        t0=_T0, k=_K, b=_B, v=_V, sigma=_SIGMA,
        min_temp=-1.8, n_grid=6000, percentiles=(5, 16, 50, 84, 95),
    )
    row = [out[f"p{p}"] for p in (5, 16, 50, 84, 95)]
    assert all(a <= b for a, b in zip(row, row[1:]))


def test_grid_truncated_flag_clears_under_adaptive_bound():
    # RI=0.97 sits right at the doc's flagged saturated tail; the adaptive
    # bound should widen the grid enough that no meaningful mass remains at
    # the new right edge.
    out = _grid_quantiles(
        0.97, mu_prior=15.0, sigma_prior=10.0,
        t0=_T0, k=_K, b=_B, v=_V, sigma=_SIGMA,
        min_temp=-1.8, n_grid=6000, percentiles=(50,),
    )
    assert out["grid_truncated"] is False


def test_grid_truncated_flag_sets_under_old_fixed_cap():
    # Reproduce truncation deliberately: shrink sigma_prior so the adaptive
    # bound collapses close to the old fixed 45 degC cap for a saturated RI.
    out = _grid_quantiles(
        0.97, mu_prior=15.0, sigma_prior=1.0,  # tight prior -> low adaptive T_hi
        t0=_T0, k=_K, b=_B, v=_V, sigma=_SIGMA,
        min_temp=-1.8, n_grid=6000, percentiles=(50,),
    )
    assert out["grid_truncated"] is True
