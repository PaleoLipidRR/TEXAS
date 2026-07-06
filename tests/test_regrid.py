import numpy as np
import pytest
import xarray as xr
from TEXAS.utils.regrid import _prepare_grids


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
