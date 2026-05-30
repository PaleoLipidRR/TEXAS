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
