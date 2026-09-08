"""Optional map-plotting dependencies (cartopy/regionmask) must stay optional.

`import TEXAS` and the core calibration API must not hard-require the geo stack;
plot_residual_maps should raise a clear, actionable error when it is missing.
"""

import pytest

from TEXAS.plotting import residual_maps


def test_require_cartopy_passes_when_available(monkeypatch):
    """No error raised when cartopy is present."""
    monkeypatch.setattr(residual_maps, "_CARTOPY_AVAILABLE", True)
    residual_maps._require_cartopy()  # should not raise


def test_require_cartopy_raises_helpful_error_when_missing(monkeypatch):
    """A missing geo stack yields an ImportError naming the optional extra."""
    monkeypatch.setattr(residual_maps, "_CARTOPY_AVAILABLE", False)
    with pytest.raises(ImportError, match=r"texas-psm\[maps\]"):
        residual_maps._require_cartopy()


def test_core_api_importable_without_touching_plotting():
    """The user-facing prediction API imports without the map stack."""
    from TEXAS import predict_proxy_from_T, predict_T_from_proxyObs  # noqa: F401


# ── scikit-learn must stay optional ───────────────────────────────────────────
# residual_maps used sklearn.metrics.r2_score and screening used
# sklearn.decomposition.PCA, both unguarded, while scikit-learn was declared
# only in the `dev` extra. See docs/superpowers/specs/2026-09-07-repo-finalization-design.md §9.2.

import subprocess
import sys

import numpy as np
import pandas as pd

_IMPORT_WITHOUT_SKLEARN = """
import sys


class _BlockSklearn:
    def find_spec(self, name, path=None, target=None):
        if name == "sklearn" or name.startswith("sklearn."):
            raise ImportError("scikit-learn is blocked for this test")
        return None


sys.meta_path.insert(0, _BlockSklearn())

import TEXAS                                    # noqa: F401
import TEXAS.plotting.residual_maps             # noqa: F401
import TEXAS.data.screening                     # noqa: F401

assert "sklearn" not in sys.modules, "something imported sklearn at module scope"
print("IMPORTED-WITHOUT-SKLEARN")
"""


def test_package_imports_with_scikit_learn_absent():
    """`import TEXAS` and both sklearn-touching modules load with sklearn blocked."""
    proc = subprocess.run(
        [sys.executable, "-c", _IMPORT_WITHOUT_SKLEARN],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "IMPORTED-WITHOUT-SKLEARN" in proc.stdout


def test_r2_score_matches_the_textbook_definition():
    """1 - SS_res/SS_tot, computed with numpy alone."""
    y_true = np.array([1.0, 2.0, 3.0, 4.0])
    y_pred = np.array([1.1, 1.9, 3.2, 3.7])
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    assert residual_maps._r2_score(y_true, y_pred) == pytest.approx(1 - ss_res / ss_tot)


def test_r2_score_agrees_with_sklearn_when_sklearn_is_installed():
    """Exact agreement on non-degenerate input, so the figures do not move."""
    sklearn_metrics = pytest.importorskip("sklearn.metrics")
    rng = np.random.default_rng(0)
    for n in (5, 50, 500):
        y_true = rng.normal(20.0, 5.0, n)
        y_pred = y_true + rng.normal(0.0, 2.0, n)
        assert residual_maps._r2_score(y_true, y_pred) == pytest.approx(
            sklearn_metrics.r2_score(y_true, y_pred), abs=1e-12
        )


def test_r2_score_is_nan_for_constant_truth():
    """No variance to explain -> undefined. (sklearn returns 0.0; we say NaN.)"""
    assert np.isnan(residual_maps._r2_score([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]))


def test_plot_pca_projection_names_scikit_learn_when_missing(monkeypatch):
    """A missing scikit-learn yields an ImportError that says how to fix it."""
    from TEXAS.data.screening import MahalanobisOutlierDetector

    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "TEX86": rng.uniform(0.3, 0.8, 50),
        "scaledRI_cren3": rng.uniform(0.2, 0.7, 50),
    })
    det = MahalanobisOutlierDetector(["TEX86", "scaledRI_cren3"], confidence=0.9).fit(df)

    # A None entry in sys.modules makes `from X import Y` raise ImportError.
    monkeypatch.setitem(sys.modules, "sklearn", None)
    monkeypatch.setitem(sys.modules, "sklearn.decomposition", None)

    with pytest.raises(ImportError, match="scikit-learn"):
        det.plot_pca_projection(df)
