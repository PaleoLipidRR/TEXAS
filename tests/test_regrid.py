import numpy as np
import pytest
import xarray as xr
from TEXAS.utils.regrid import _prepare_grids, _regrid_scipy


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
