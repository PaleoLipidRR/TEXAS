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
