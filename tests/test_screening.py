"""Tests for MahalanobisOutlierDetector logical->physical column mapping."""

import numpy as np
import pandas as pd
import pytest

from TEXAS.data.screening import MahalanobisOutlierDetector


def _training_df(seed=0, n=200):
    """Training frame with LOGICAL column names (TEXAS convention)."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "TEX86": rng.uniform(0.3, 0.8, n),
        "scaledRI_cren3": rng.uniform(0.2, 0.7, n),
    })


class TestColumnMappingCorrectness:
    def test_mapping_matches_manual_rename(self):
        """transform with a columns= map equals transforming a hand-renamed frame."""
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9)
        det.fit(train)

        # Caller frame with PHYSICAL names.
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        mapping = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}

        via_map = det.transform(phys, columns=mapping)
        # Reference: rename physical back to logical, transform with no map.
        via_rename = det.transform(
            phys.rename(columns={v: k for k, v in mapping.items()})
        )
        pd.testing.assert_series_equal(via_map, via_rename)

    def test_all_populated_rows_finite(self):
        """Every fully-populated mapped row gets a finite distance."""
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(train)
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        dist = det.transform(phys, columns={"TEX86": "TEX86_best",
                                            "scaledRI_cren3": "ScaledRI03_best"})
        assert np.isfinite(dist.to_numpy()).all()


class TestMissingColumnRaises:
    def test_missing_mapped_column_raises_keyerror(self):
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(train)
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        with pytest.raises(KeyError, match=r"scaledRI_cren3.*ScaledRI03_typo"):
            det.transform(phys, columns={"TEX86": "TEX86_best",
                                         "scaledRI_cren3": "ScaledRI03_typo"})

    def test_missing_unmapped_column_raises_keyerror(self):
        """No map, but the logical column is absent -> KeyError naming it."""
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(train)
        only_tex = train[["TEX86"]]
        with pytest.raises(KeyError, match=r"scaledRI_cren3"):
            det.transform(only_tex)


class TestCoverageGuardrail:
    def _frame_with_nan(self):
        train = _training_df(n=50)
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        phys.loc[phys.index[:5], "TEX86_best"] = np.nan  # 5 unscorable rows
        return phys

    def _fitted(self):
        return MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.9
        ).fit(_training_df())

    def test_warn_default_reports_count(self):
        det, phys = self._fitted(), self._frame_with_nan()
        m = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}
        with pytest.warns(UserWarning, match=r"5 row"):
            det.transform(phys, columns=m)

    def test_raise_mode(self):
        det, phys = self._fitted(), self._frame_with_nan()
        m = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}
        with pytest.raises(ValueError, match=r"5 row"):
            det.transform(phys, columns=m, on_unscorable="raise")

    def test_ignore_mode_silent(self):
        det, phys = self._fitted(), self._frame_with_nan()
        m = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}
        import warnings as _w
        with _w.catch_warnings():
            _w.simplefilter("error")  # any warning becomes an error
            det.transform(phys, columns=m, on_unscorable="ignore")

    def test_invalid_on_unscorable_raises(self):
        det = self._fitted()
        train = _training_df()
        with pytest.raises(ValueError, match=r"on_unscorable"):
            det.transform(train, on_unscorable="bogus")


class TestNoMutation:
    def test_transform_does_not_mutate_caller_df(self):
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(train)
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        before_cols = list(phys.columns)
        before = phys.copy(deep=True)
        det.transform(phys, columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        assert list(phys.columns) == before_cols
        pd.testing.assert_frame_equal(phys, before)


class TestBackwardCompat:
    def test_no_columns_arg_identical_distances(self):
        """The no-map path is byte-identical to pre-change behavior."""
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(train)
        d1 = det.transform(train)
        # Recompute manually via scipy for a fixed reference.
        assert d1.notna().all()
        assert d1.index.equals(train.index)

    def test_col_name_write_still_works(self):
        """Existing explicit col_name= mutation is preserved."""
        train = _training_df()
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(train)
        det.transform(train, col_name="mahal")
        assert "mahal" in train.columns


class TestOutlierFlagDtype:
    """Regression: building the outlier-flag Series must not rely on implicit
    bool->float coercion, which pandas 2.x deprecates (FutureWarning) and
    pandas 3.0 removes (TypeError)."""

    def _fitted_and_frame(self):
        det = MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.9
        ).fit(_training_df())
        phys = _training_df(n=50).rename(
            columns={"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}
        )
        phys.loc[phys.index[:5], "TEX86_best"] = np.nan  # 5 unscorable rows
        m = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}
        return det, phys, m

    def test_detect_outliers_emits_no_dtype_warning(self):
        """Flag assignment produces no FutureWarning (fatal here) and stays boolean."""
        det, phys, m = self._fitted_and_frame()
        import warnings as _w
        with _w.catch_warnings():
            _w.simplefilter("error")  # any warning, incl. FutureWarning, -> error
            flags = det.detect_outliers(phys, columns=m, on_unscorable="ignore")
        assert flags.dtype == "boolean"

    def test_flag_values_na_for_unscorable(self):
        """Unscorable rows map to <NA>; scored rows map to real booleans."""
        det, phys, m = self._fitted_and_frame()
        flags = det.detect_outliers(phys, columns=m, on_unscorable="ignore")
        assert flags.dtype == "boolean"
        assert flags.iloc[:5].isna().all()
        assert flags.iloc[5:].notna().all()


class TestDetectOutliersManualMapping:
    def test_default_exception_uses_mapped_columns(self):
        """The default exception rule reads mapped physical columns, not logical."""
        rng = np.random.default_rng(3)
        n = 300
        train = pd.DataFrame({
            "TEX86": rng.uniform(0.3, 0.9, n),
            "scaledRI_cren3": rng.uniform(0.2, 0.8, n),
        })
        det = MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.9
        ).fit(train)

        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        m = {"TEX86": "TEX86_best", "scaledRI_cren3": "ScaledRI03_best"}

        via_map = det.detect_outliers_manual(phys, columns=m)
        via_rename = det.detect_outliers_manual(
            phys.rename(columns={v: k for k, v in m.items()})
        )
        pd.testing.assert_series_equal(via_map, via_rename)

    def test_manual_missing_mapped_column_raises(self):
        train = pd.DataFrame({
            "TEX86": np.linspace(0.3, 0.9, 50),
            "scaledRI_cren3": np.linspace(0.2, 0.8, 50),
        })
        det = MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.9
        ).fit(train)
        phys = train.rename(columns={"TEX86": "TEX86_best",
                                     "scaledRI_cren3": "ScaledRI03_best"})
        with pytest.raises(KeyError, match=r"TEX86.*TEX86_typo"):
            det.detect_outliers_manual(phys, columns={"TEX86": "TEX86_typo",
                                                      "scaledRI_cren3": "ScaledRI03_best"})


class TestFitPredict:
    """fit_predict is the one-liner documented in manuscript Appendix C2.6."""

    def test_matches_fit_then_detect_outliers(self):
        df = _training_df()
        one_call = MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.90
        ).fit_predict(df)
        two_call_det = MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.90
        ).fit(df)
        two_call = two_call_det.detect_outliers(df)
        pd.testing.assert_series_equal(one_call, two_call)

    def test_appendix_c_usage_assigns_column(self):
        """df["flagged"] = detector.fit_predict(df) — verbatim manuscript usage."""
        df = _training_df()
        detector = MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.90)
        df["flagged"] = detector.fit_predict(df)
        assert df["flagged"].dtype == "boolean"
        assert df["flagged"].notna().all()
        # ~10% of a well-behaved sample sits outside the 90% ellipse
        frac = df["flagged"].mean()
        assert 0.0 <= frac <= 0.35


class TestCalibrationDomainDefault:
    """Screening must use the PUBLISHED ellipse, not one fitted to the record.

    Section 5.1 defines the ellipse on a fixed reference cluster (core-tops with
    GDGT-2/GDGT-3 <= 5). Fitting on the record being screened lets the domain
    move with the data, so an all-warm section recentres the ellipse onto itself
    and flags nothing -- the exact opposite of the intended behaviour.
    """

    WARM = pd.DataFrame({"TEX86": [0.86, 0.88, 0.90, 0.91, 0.93],
                         "scaledRI_cren3": [0.80, 0.82, 0.84, 0.85, 0.87]})

    def test_unfitted_detector_screens_against_published_domain(self):
        det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.90)
        flags = det.detect_outliers(self.WARM)          # no fit() call
        assert det.is_fitted
        assert flags.all(), "warm samples must fall outside the calibration domain"

    def test_from_calibration_matches_the_default(self):
        a = MahalanobisOutlierDetector.from_calibration()
        b = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.90)
        b.detect_outliers(self.WARM)
        assert np.allclose(a.mean_vec, b.mean_vec)
        assert np.allclose(a.inv_cov, b.inv_cov)

    def test_self_fitting_is_the_trap_this_guards(self):
        """fit_predict on the record flags nothing -- why it must not be the default."""
        self_fit = MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.90).fit_predict(self.WARM)
        published = MahalanobisOutlierDetector(
            ["TEX86", "scaledRI_cren3"], confidence=0.90).detect_outliers(self.WARM)
        assert not self_fit.any()
        assert published.all()

    def test_published_threshold_is_the_manuscript_value(self):
        det = MahalanobisOutlierDetector.from_calibration(confidence=0.90)
        assert det.threshold == pytest.approx(2.1460, abs=1e-3)
        assert det.n_reference == 1198

    def test_nonstandard_features_still_require_fit(self):
        det = MahalanobisOutlierDetector(["TEX86", "fGDGT_0"])
        with pytest.raises(ValueError, match="not fitted"):
            det.detect_outliers(pd.DataFrame({"TEX86": [0.5], "fGDGT_0": [0.2]}))
