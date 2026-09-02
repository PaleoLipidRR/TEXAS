"""Tests for per-observation quality flags on an inverse reconstruction.

These run on synthetic posteriors, so none of them needs CmdStan or a sampling
run --- the flags are a pure function of the calibration draws, the inputs and
the returned percentiles.
"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from TEXAS.quality import (
    ADVISORY_COLUMNS,
    DEFAULT_PRIOR_DOMINATED_RATIO,
    FLAG_COLUMNS,
    compute_quality_flags,
)


def _posterior(
    *,
    t0shift=True,
    b=(0.40, 0.42),
    use_g23=1,
    use_no3=1,
    no3_cutoff=1.0,
    proxy_range=(0.33, 0.87),
    **extra_attrs,
):
    """A minimal forward posterior carrying only what the flags read."""
    n = len(b)
    dims = ("chain", "draw")
    shape = (1, n)

    def var(values):
        return (dims, np.asarray(values, dtype=float).reshape(shape))

    data = {
        "t0_crtp": var(np.full(n, 20.0)),
        "k_crtp": var(np.full(n, 0.5)),
        "b_crtp": var(b),
        "v_crtp": var(np.full(n, 3.0)),
    }
    coef = "gamma" if t0shift else "beta"
    data[f"{coef}_G23_crtp"] = var(np.full(n, 0.1))
    data[f"{coef}_NO3_crtp"] = var(np.full(n, -0.2))

    attrs = {
        "use_gdgt23ratio": use_g23,
        "use_no3": use_no3,
        "no3_cutoff": no3_cutoff,
        "proxy_name": "scaledRI_cren3",
        "proxyObs_crtp_min": proxy_range[0],
        "proxyObs_crtp_max": proxy_range[1],
        "gdgt23ratio_crtp_min": 0.76,
        "gdgt23ratio_crtp_max": 35.1,
        "no3_crtp_min": 0.0002,
        "no3_crtp_max": 36.4,
    }
    attrs.update(extra_attrs)
    return xr.Dataset(data, attrs=attrs)


def _preds(n, g23=5.0, no3=0.5):
    return {"gdgt23ratio": np.full(n, g23), "no3": np.full(n, no3)}


class TestAttainableRange:
    """The motivating case: values the curve cannot produce at any temperature."""

    def test_below_the_lower_asymptote_is_flagged(self):
        ds = _posterior(b=(0.40, 0.42))
        f = compute_quality_flags(np.array([0.20]), ds, predictors=_preds(1))
        assert bool(f["proxy_below_floor"][0]) is True
        assert f["frac_draws_below_floor"][0] == 1.0

    def test_above_the_upper_asymptote_is_flagged(self):
        ds = _posterior()
        f = compute_quality_flags(np.array([1.05]), ds, predictors=_preds(1))
        assert bool(f["proxy_above_ceiling"][0]) is True
        assert f["frac_draws_above_ceiling"][0] == 1.0

    def test_a_value_inside_the_range_is_not_flagged(self):
        ds = _posterior()
        f = compute_quality_flags(np.array([0.60]), ds, predictors=_preds(1))
        assert bool(f["proxy_below_floor"][0]) is False
        assert bool(f["proxy_above_ceiling"][0]) is False
        assert bool(f["any_flag"][0]) is False

    def test_the_floor_is_graded_across_draws(self):
        """b is a distribution, so a value between its draws is partly ruled out."""
        ds = _posterior(b=(0.40, 0.50))
        f = compute_quality_flags(np.array([0.45]), ds, predictors=_preds(1))
        assert f["frac_draws_below_floor"][0] == pytest.approx(0.5)
        # Exactly half is not a majority, so the boolean stays clear while the
        # graded column records the ambiguity.
        assert bool(f["proxy_below_floor"][0]) is False

    def test_majority_of_draws_trips_the_boolean(self):
        # 0.55 sits below the 0.60 and 0.70 draws but above the 0.40 one.
        ds = _posterior(b=(0.40, 0.60, 0.70))
        f = compute_quality_flags(np.array([0.55]), ds, predictors=_preds(1))
        assert f["frac_draws_below_floor"][0] == pytest.approx(2 / 3)
        assert bool(f["proxy_below_floor"][0]) is True


class TestParameterization:
    """Where the floor sits depends on how predictors enter the curve."""

    def test_t0shift_floor_ignores_predictors(self):
        """gamma shifts T0, so the range stays (b, 1) for every predictor value."""
        ds = _posterior(t0shift=True, b=(0.40, 0.40))
        a = compute_quality_flags(np.array([0.38]), ds, predictors=_preds(1, g23=1.0))
        z = compute_quality_flags(np.array([0.38]), ds, predictors=_preds(1, g23=30.0))
        assert a["frac_draws_below_floor"][0] == z["frac_draws_below_floor"][0] == 1.0

    def test_additive_floor_moves_with_predictors(self):
        """beta shifts mu, so a large G23 raises the floor above the same value."""
        ds = _posterior(t0shift=False, b=(0.40, 0.40))
        # no3 above the cutoff zeroes the NO3 term, isolating G23's effect.
        low = compute_quality_flags(
            np.array([0.45]), ds, predictors=_preds(1, g23=0.0, no3=10.0)
        )
        high = compute_quality_flags(
            np.array([0.45]), ds, predictors=_preds(1, g23=30.0, no3=10.0)
        )
        assert low["frac_draws_below_floor"][0] == 0.0
        assert high["frac_draws_below_floor"][0] == 1.0

    def test_additive_no3_correction_also_moves_the_floor(self):
        """Inside the window the NO3 term shifts mu, so it shifts the floor too."""
        ds = _posterior(t0shift=False, b=(0.40, 0.40))
        # beta_NO3 = -0.2 and log10(0.5) < 0, so an in-window NO3 raises the floor
        # to 0.46 -- above a 0.45 observation that clears the bare b of 0.40.
        inside = compute_quality_flags(
            np.array([0.45]), ds, predictors=_preds(1, g23=0.0, no3=0.5)
        )
        outside = compute_quality_flags(
            np.array([0.45]), ds, predictors=_preds(1, g23=0.0, no3=10.0)
        )
        assert inside["frac_draws_below_floor"][0] == 1.0
        assert outside["frac_draws_below_floor"][0] == 0.0


class TestExtrapolation:
    def test_outside_the_calibration_proxy_range(self):
        ds = _posterior(proxy_range=(0.33, 0.87))
        f = compute_quality_flags(
            np.array([0.30, 0.60, 0.90]), ds, predictors=_preds(3)
        )
        assert list(f["proxy_extrapolated"]) == [True, False, True]

    def test_predictor_outside_the_calibration_range(self):
        ds = _posterior()
        f = compute_quality_flags(
            np.array([0.6, 0.6]), ds,
            predictors={"gdgt23ratio": np.array([5.0, 99.0]),
                        "no3": np.array([0.5, 0.5])},
        )
        assert list(f["predictor_extrapolated"]) == [False, True]


class TestPredictors:
    def test_missing_predictor_the_calibration_uses_is_flagged(self):
        """Absent is not neutral -- Stan receives 0, asserting a ratio of zero."""
        ds = _posterior(use_g23=1, use_no3=1)
        f = compute_quality_flags(np.array([0.6]), ds, predictors={"no3": 0.5})
        assert bool(f["predictor_missing"][0]) is True

    def test_nan_predictor_is_flagged(self):
        ds = _posterior()
        f = compute_quality_flags(
            np.array([0.6, 0.6]), ds,
            predictors={"gdgt23ratio": np.array([5.0, np.nan]),
                        "no3": np.array([0.5, 0.5])},
        )
        assert list(f["predictor_missing"]) == [False, True]

    def test_not_assessed_when_the_calibration_uses_no_predictors(self):
        ds = _posterior(use_g23=0, use_no3=0)
        f = compute_quality_flags(np.array([0.6]), ds)
        assert f["predictor_missing"].isna().all()

    def test_no3_outside_the_window_is_reported_inactive(self):
        """no3=10 with cutoff 1.0 is the documented way to switch NO3 off."""
        ds = _posterior(no3_cutoff=1.0)
        f = compute_quality_flags(
            np.array([0.6, 0.6, 0.6]), ds,
            predictors={"gdgt23ratio": np.full(3, 5.0),
                        "no3": np.array([0.5, 10.0, 0.0])},
        )
        assert list(f["no3_correction_inactive"]) == [False, True, True]

    def test_scalar_predictors_broadcast(self):
        ds = _posterior()
        f = compute_quality_flags(
            np.array([0.6, 0.7]), ds, predictors={"gdgt23ratio": 5.0, "no3": 0.5}
        )
        assert len(f) == 2
        assert not f["predictor_missing"].any()

    def test_length_mismatch_is_an_error(self):
        ds = _posterior()
        with pytest.raises(ValueError, match="one value per observation"):
            compute_quality_flags(
                np.array([0.6, 0.7]), ds,
                predictors={"gdgt23ratio": np.array([1.0, 2.0, 3.0]), "no3": 0.5},
            )


class TestPriorDominated:
    def test_a_wide_posterior_is_flagged(self):
        ds = _posterior()
        # p84-p16 = 2*sigma_post; a ratio of 1.0 means the data added nothing.
        result = {"p16": np.array([15.0]), "p84": np.array([35.0])}
        f = compute_quality_flags(
            np.array([0.6]), ds, predictors=_preds(1),
            prior_sigma_t=10.0, result=result,
        )
        assert f["posterior_prior_width_ratio"][0] == pytest.approx(1.0)
        assert bool(f["prior_dominated"][0]) is True

    def test_a_narrow_posterior_is_not_flagged(self):
        ds = _posterior()
        result = {"p16": np.array([24.0]), "p84": np.array([26.0])}
        f = compute_quality_flags(
            np.array([0.6]), ds, predictors=_preds(1),
            prior_sigma_t=10.0, result=result,
        )
        assert f["posterior_prior_width_ratio"][0] == pytest.approx(0.1)
        assert bool(f["prior_dominated"][0]) is False

    def test_not_assessed_without_a_result(self):
        ds = _posterior()
        f = compute_quality_flags(
            np.array([0.6]), ds, predictors=_preds(1), prior_sigma_t=10.0
        )
        assert f["prior_dominated"].isna().all()

    def test_threshold_is_configurable(self):
        ds = _posterior()
        result = {"p16": np.array([20.0]), "p84": np.array([30.0])}  # ratio 0.5
        base = compute_quality_flags(
            np.array([0.6]), ds, predictors=_preds(1),
            prior_sigma_t=10.0, result=result,
        )
        strict = compute_quality_flags(
            np.array([0.6]), ds, predictors=_preds(1),
            prior_sigma_t=10.0, result=result, prior_dominated_ratio=0.4,
        )
        assert bool(base["prior_dominated"][0]) is False
        assert bool(strict["prior_dominated"][0]) is True
        assert DEFAULT_PRIOR_DOMINATED_RATIO > 0.5


class TestNotAssessedIsNotPassed:
    """A check that could not run must never read as one that passed."""

    def test_nan_observations_are_na_not_false(self):
        ds = _posterior()
        f = compute_quality_flags(
            np.array([0.6, np.nan]), ds, predictors=_preds(2)
        )
        assert bool(f["proxy_below_floor"][0]) is False
        assert pd.isna(f["proxy_below_floor"][1])
        assert pd.isna(f["proxy_above_ceiling"][1])
        assert pd.isna(f["proxy_extrapolated"][1])

    def test_domain_is_na_without_tex86(self):
        ds = _posterior()
        f = compute_quality_flags(np.array([0.6]), ds, predictors=_preds(1))
        assert f["outside_domain"].isna().all()

    def test_domain_is_na_for_a_proxy_the_ellipse_is_not_built_on(self):
        ds = _posterior(proxy_name="TEX86")
        with pytest.warns(UserWarning, match="scaledRI_cren3"):
            f = compute_quality_flags(
                np.array([0.6]), ds, predictors=_preds(1), tex86=np.array([0.7])
            )
        assert f["outside_domain"].isna().all()

    def test_an_all_na_column_does_not_poison_any_flag(self):
        ds = _posterior()
        f = compute_quality_flags(np.array([0.6]), ds, predictors=_preds(1))
        assert f["outside_domain"].isna().all()      # never evaluated
        assert f["prior_dominated"].isna().all()     # never evaluated
        assert bool(f["any_flag"][0]) is False       # yet the row is clean


class TestAdvisoriesDoNotVote:
    """Switching NO3 off is a configuration choice, not a defect."""

    def test_disabling_no3_does_not_flag_a_healthy_record(self):
        # no3=10 against a cutoff of 1.0 is the documented way to switch the
        # correction off, so it fires on every row -- it must not make every
        # row read as suspect.
        ds = _posterior(no3_cutoff=1.0)
        ri = np.array([0.50, 0.60, 0.70])
        f = compute_quality_flags(ri, ds, predictors=_preds(3, no3=10.0))
        assert f["no3_correction_inactive"].all()
        assert not f["any_flag"].any()

    def test_an_advisory_still_appears_in_the_frame(self):
        ds = _posterior()
        f = compute_quality_flags(np.array([0.6]), ds, predictors=_preds(1, no3=10.0))
        for col in ADVISORY_COLUMNS:
            assert col in f.columns
            assert col in FLAG_COLUMNS

    def test_a_real_defect_still_votes_alongside_an_advisory(self):
        ds = _posterior(b=(0.40, 0.42), no3_cutoff=1.0)
        f = compute_quality_flags(np.array([0.20]), ds, predictors=_preds(1, no3=10.0))
        assert bool(f["no3_correction_inactive"][0]) is True
        assert bool(f["proxy_below_floor"][0]) is True
        assert bool(f["any_flag"][0]) is True


class TestFrameShape:
    def test_every_declared_column_is_present_with_one_row_per_input(self):
        ds = _posterior()
        n = 7
        f = compute_quality_flags(np.linspace(0.4, 0.8, n), ds, predictors=_preds(n))
        assert len(f) == n
        for col in FLAG_COLUMNS:
            assert col in f.columns
        assert "any_flag" in f.columns

    def test_the_frame_filters_a_record(self):
        ds = _posterior(b=(0.40, 0.42))
        ri = np.array([0.20, 0.60, 0.70, 1.05])
        f = compute_quality_flags(ri, ds, predictors=_preds(4))
        keep = ~f["any_flag"].to_numpy(dtype=bool)
        assert list(ri[keep]) == [0.60, 0.70]

    def test_missing_b_is_a_clear_error(self):
        ds = _posterior()
        ds = ds.drop_vars("b_crtp")
        with pytest.raises(ValueError, match="lower-asymptote"):
            compute_quality_flags(np.array([0.6]), ds)
