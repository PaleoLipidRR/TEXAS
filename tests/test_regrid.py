import numpy as np
import pytest
import xarray as xr
from TEXAS.utils.regrid import _prepare_grids, _regrid_scipy, regrid_curvilinear_to_latlon, _esmf_available


def _curvilinear_ds():
    # 2-D (rectilinear-as-curvilinear) source grid, lon in [0, 360)
    jj, ii = np.meshgrid(np.linspace(-80, 80, 9), np.linspace(0, 350, 12), indexing="ij")
    return xr.Dataset(
        {"TEMP": (("nj", "ni"), jj.copy())},          # field == latitude
        coords={"TLAT": (("nj", "ni"), jj), "TLONG": (("nj", "ni"), ii)},
    )


def test_prepare_grids_autodetects_and_builds_target():
    ds = _curvilinear_ds()
    g = _prepare_grids(ds, None, None, target_res=1.0,
                       lat_range=(-90, 90), lon_range=(0, 360))
    assert g["lat_name"] == "TLAT" and g["lon_name"] == "TLONG"
    assert g["src_lat"].shape == (9, 12) and g["src_lon"].shape == (9, 12)
    # target axes use arange(range0, range1 + res/2, res)
    assert g["lat_out"][0] == -90.0 and g["lat_out"][-1] == 90.0
    assert g["lon_out"][0] == 0.0 and g["lon_out"][-1] == 360.0


def test_regrid_scipy_reproduces_linear_field():
    ds = _curvilinear_ds()  # TEMP == latitude
    grids = _prepare_grids(ds, None, None, 2.0, (-90, 90), (0, 360))
    out = _regrid_scipy(ds, ["TEMP"], grids, method="bilinear",
                        periodic=False, squeeze_dims=None, keep_attrs=True)
    assert set(out["TEMP"].dims) == {"lat", "lon"}
    # interior target point: value must equal its latitude (linear field, linear interp)
    val = out["TEMP"].sel(lat=0.0, lon=180.0).item()
    assert abs(val - 0.0) < 1e-6
    val2 = out["TEMP"].sel(lat=40.0, lon=100.0).item()
    assert abs(val2 - 40.0) < 1e-6


def test_periodic_padding_bridges_the_seam():
    # field varying with longitude; a target point near the 0/360 seam
    jj, ii = np.meshgrid(np.linspace(-10, 10, 5), np.linspace(2, 358, 20), indexing="ij")
    ds = xr.Dataset({"TEMP": (("nj", "ni"), np.cos(np.deg2rad(ii)))},
                    coords={"TLAT": (("nj", "ni"), jj), "TLONG": (("nj", "ni"), ii)})
    grids = _prepare_grids(ds, None, None, 1.0, (-10, 10), (0, 360))
    out = _regrid_scipy(ds, ["TEMP"], grids, method="bilinear",
                        periodic=True, squeeze_dims=None, keep_attrs=False)
    # at lon=0 (inside the seam gap of the unpadded source [2,358]) value must be finite
    assert np.isfinite(out["TEMP"].sel(lat=0.0, lon=0.0).item())


def test_conservative_method_raises_in_scipy_backend():
    ds = _curvilinear_ds()
    grids = _prepare_grids(ds, None, None, 2.0, (-90, 90), (0, 360))
    with pytest.raises(ValueError, match="conservative"):
        _regrid_scipy(ds, ["TEMP"], grids, method="conservative",
                      periodic=False, squeeze_dims=None, keep_attrs=False)


def test_backend_scipy_forces_fallback():
    ds = _curvilinear_ds()
    out = regrid_curvilinear_to_latlon(ds, "TEMP", target_res=2.0, backend="scipy")
    assert abs(out["TEMP"].sel(lat=30.0, lon=200.0).item() - 30.0) < 1e-6


def test_backend_auto_uses_scipy_when_esmpy_absent():
    ds = _curvilinear_ds()
    if _esmf_available():
        pytest.skip("esmpy present; auto would use xesmf")
    with pytest.warns(UserWarning, match="fallback"):
        out = regrid_curvilinear_to_latlon(ds, "TEMP", target_res=2.0, backend="auto")
    assert set(out["TEMP"].dims) == {"lat", "lon"}


def test_backend_xesmf_raises_without_esmpy():
    ds = _curvilinear_ds()
    if _esmf_available():
        pytest.skip("esmpy present; xesmf would succeed")
    with pytest.raises(ImportError, match="esmpy"):
        regrid_curvilinear_to_latlon(ds, "TEMP", target_res=2.0, backend="xesmf")
