"""
R2_thermal must travel with the posterior when the model used it.

The EIV forward models (``..._priorApprox_eiv_t0shift.stan``) take
``R2_thermal`` as data and use it to scale the prior on
``sigma_proxyObs_crtp`` -- ``mean(sd_proxyObs) * sqrt(1 - R2_thermal)`` -- so
it shapes what the noise term means and therefore every interval width. That
value was previously recorded only in an external refit manifest, never on
the ``.nc`` file itself, so a shipped posterior could not be traced back to
the input that set its noise prior. ``extract_and_update_metadata`` now
stamps it onto ``ds.attrs`` whenever it was actually present in the Stan
data dict, via ``DIRECT_KEYS`` in ``TEXAS.constants``.

A univariate or non-EIV fit never has ``R2_thermal`` in its data dict (only
``data/builder.py::build_fwd_data(..., R2_thermal=...)`` puts it there), so
it must come back with no ``R2_thermal`` attr at all -- an invented 0.0 would
misrepresent the noise prior of a model that never took the input.

No CmdStan required: these drive ``extract_and_update_metadata`` directly
with a bare xr.Dataset standing in for sampled draws.
"""
import numpy as np
import xarray as xr

from TEXAS.stan.metadata import extract_and_update_metadata


def _stub_dataset():
    """Minimal draws dataset, standing in for a real posterior."""
    return xr.Dataset(
        {"t0_crtp": (("chain", "draw"), np.zeros((2, 5)))},
        coords={"chain": np.arange(2), "draw": np.arange(5)},
    )


class TestR2ThermalProvenance:
    def test_stamped_when_present_in_data(self):
        """EIV-style data dict with R2_thermal -> attr written, as a float."""
        data = {"N_crtp": 10, "R2_thermal": 0.87}
        ds = extract_and_update_metadata(_stub_dataset(), data, "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift")
        assert "R2_thermal" in ds.attrs
        assert isinstance(ds.attrs["R2_thermal"], float)
        assert ds.attrs["R2_thermal"] == 0.87

    def test_absent_when_not_in_data(self):
        """Non-EIV data dict (no R2_thermal key) -> no attr, not 0.0 or None."""
        data = {"N_crtp": 10}
        ds = extract_and_update_metadata(_stub_dataset(), data, "gen_logi_fixed_hier_crtp_univ_priorApprox")
        assert "R2_thermal" not in ds.attrs

    def test_netcdf_safe_type(self):
        """Written as a plain Python float (NetCDF-safe), even from a numpy scalar."""
        data = {"R2_thermal": np.float64(0.5)}
        ds = extract_and_update_metadata(_stub_dataset(), data, "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_t0shift")
        assert type(ds.attrs["R2_thermal"]) is float
