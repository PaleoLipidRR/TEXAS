"""lookup_modern_no3: lat/lon axis resolution, including the lat_name/lon_name override.

resolve_latlon_names() auto-detects standard spellings (lat/lon, latitude/
longitude, ...), but a caller's grid may use something else entirely. These
tests would fail if lat_name/lon_name were dropped from lookup_modern_no3's
signature, or if it stopped threading them through to resolve_latlon_names.
"""
import numpy as np
import pytest
import xarray as xr

from TEXAS.data.ocean_lookup import lookup_modern_no3


def _woa_ds():
    """Standard-spelling (lat, lon) grid; value = lat + lon (exact on-grid)."""
    lat = np.array([-10.0, 0.0, 10.0, 20.0])
    lon = np.array([0.0, 10.0, 20.0, 30.0])
    field = lat[:, None] + lon[None, :]
    return xr.Dataset(
        {"no3_sf2tc_avg": (("lat", "lon"), field)},
        coords={"lat": lat, "lon": lon},
    )


def _custom_name_ds():
    """Same field, but on axes named Y/X -- not in resolve_latlon_names' candidates."""
    lat = np.array([-10.0, 0.0, 10.0, 20.0])
    lon = np.array([0.0, 10.0, 20.0, 30.0])
    field = lat[:, None] + lon[None, :]
    return xr.Dataset(
        {"no3_sf2tc_avg": (("Y", "X"), field)},
        coords={"Y": lat, "X": lon},
    )


def test_lookup_autodetects_standard_lat_lon_names():
    ds = _woa_ds()
    out = lookup_modern_no3(0.0, 10.0, ds)
    assert np.isclose(float(out), 10.0)


def test_lookup_with_custom_names_matches_manual_rename():
    """The lat_name/lon_name override on a non-standard grid gives the same
    answer as renaming the axes to the standard spelling and omitting it."""
    custom = _custom_name_ds()
    via_override = lookup_modern_no3(0.0, 10.0, custom, lat_name="Y", lon_name="X")

    standard = custom.rename({"Y": "lat", "X": "lon"})
    via_default = lookup_modern_no3(0.0, 10.0, standard)

    assert np.isclose(float(via_override), float(via_default))
    assert np.isclose(float(via_override), 10.0)


def test_lookup_custom_names_required_when_autodetect_cannot_match():
    """Without lat_name/lon_name, a Y/X grid can't be auto-detected."""
    custom = _custom_name_ds()
    with pytest.raises(ValueError, match="Could not auto-detect"):
        lookup_modern_no3(0.0, 10.0, custom)


def test_lookup_custom_names_work_for_array_input():
    custom = _custom_name_ds()
    out = lookup_modern_no3(
        np.array([-10.0, 20.0]), np.array([0.0, 30.0]), custom,
        lat_name="Y", lon_name="X",
    )
    np.testing.assert_allclose(out, [-10.0, 50.0])


def test_lookup_no3_from_woa_is_a_deprecated_alias():
    """The old name must keep working (notebooks call it) but say why it is wrong."""
    import warnings
    from TEXAS.data.ocean_lookup import lookup_no3_from_woa
    ds = xr.Dataset({"no3_sf2tc_avg": (("lat", "lon"), np.full((3, 3), 0.42))},
                    coords={"lat": [-1.0, 0.0, 1.0], "lon": [9.0, 10.0, 11.0]})
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        out = lookup_no3_from_woa(0.0, 10.0, ds)
    assert float(out) == pytest.approx(0.42)
    deprec = [w for w in rec if issubclass(w.category, DeprecationWarning)]
    assert len(deprec) == 1 and "CMEMS" in str(deprec[0].message)
    assert float(lookup_modern_no3(0.0, 10.0, ds)) == pytest.approx(0.42)
