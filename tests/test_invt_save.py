"""
The two invT save paths must produce the same filename.

``save_invT_posterior`` is the public, __all__-exported entry point;
``_save_invT_posterior`` is what the production path
(``predict_temperature_from_proxyObs``) calls. They used to build filenames by
different rules, and the public one omitted ``proxy_name`` entirely -- so a
scaledRI and a TEX86 reconstruction of one site resolved to a single path and,
with the default overwrite=True, the second silently destroyed the first.

Tracked as Phase 5B in RESUME.md.
"""
import numpy as np
import pytest
import xarray as xr

from TEXAS.stan.io import (
    _generate_filename_base,
    _save_invT_posterior,
    save_invT_posterior,
)


def _posterior(proxy_name="scaledRI_cren3", site="U1482", **extra):
    ds = xr.Dataset(
        {"t_est": (("quantile", "sample"), np.zeros((3, 5)))},
        coords={"quantile": [0.16, 0.5, 0.84], "sample": np.arange(5)},
    )
    ds.attrs.update({
        "SiteName": site,
        "stan_model_name": "invT_gen_logi_fixed_multiv_marginal_unconstrained",
        "temptype": "SST",
        "use_gdgt23ratio": 1,
        "use_no3": 1,
        "no3_cutoff": 1.0,
        "proxy_name": proxy_name,
    })
    ds.attrs.update(extra)
    return ds


def test_two_proxies_at_one_site_do_not_collide(tmp_path):
    """The bug: these two used to land on one path and overwrite each other."""
    a = save_invT_posterior(_posterior("scaledRI_cren3"), cache_dir=tmp_path)
    b = save_invT_posterior(_posterior("TEX86"), cache_dir=tmp_path)
    assert a != b, "scaledRI and TEX86 reconstructions of one site share a path"
    assert a.exists() and b.exists()


def test_public_and_internal_paths_agree(tmp_path):
    """Two spellings of one format is how a naming scheme rots."""
    public = save_invT_posterior(_posterior(), cache_dir=tmp_path / "a")
    internal = _save_invT_posterior(_posterior(), cache_dir=tmp_path / "b")
    assert public.name == internal.name
    assert public.relative_to(tmp_path / "a") == internal.relative_to(tmp_path / "b")


def test_proxy_name_reaches_the_filename(tmp_path):
    path = save_invT_posterior(_posterior("TEX86"), cache_dir=tmp_path)
    assert "TEX86" in str(path)


def test_filename_tag_is_honoured(tmp_path):
    """The public entry point silently ignored tags; the internal one did not."""
    plain = save_invT_posterior(_posterior(), cache_dir=tmp_path / "a")
    tagged = save_invT_posterior(_posterior(), cache_dir=tmp_path / "b",
                                 filename_tag="050126")
    assert "050126" in tagged.name
    assert plain.name != tagged.name


def test_case_layout_is_used_when_provenance_is_present(tmp_path):
    """
    With a fwd_case attr the reconstruction belongs inside its calibration's
    case directory. The old public path could not do this at all.
    """
    case = "tx.v026.GHEA.sst.sri03.G23-N10.001"
    path = save_invT_posterior(_posterior(fwd_case=case), cache_dir=tmp_path)
    assert path.parent.name == case, f"expected case directory, got {path}"
    assert path.name.startswith(case)


def test_saved_posterior_records_its_own_filename(tmp_path):
    """
    save_posterior stamps this for forward posteriors and resolution depends on
    it; the invT side was not doing it.
    """
    path = save_invT_posterior(_posterior(), cache_dir=tmp_path)
    assert xr.open_dataset(path).attrs["filename"] == path.name


def test_overwrite_false_still_refuses(tmp_path):
    save_invT_posterior(_posterior(), cache_dir=tmp_path)
    with pytest.raises(FileExistsError):
        save_invT_posterior(_posterior(), cache_dir=tmp_path, overwrite=False)


def test_non_dataset_is_rejected(tmp_path):
    with pytest.raises(TypeError):
        save_invT_posterior({"not": "a dataset"}, cache_dir=tmp_path)


def test_missing_no3_cutoff_is_an_error():
    """Silently writing a name with no cutoff would misrecord the run."""
    ds = _posterior()
    del ds.attrs["no3_cutoff"]
    with pytest.raises(ValueError):
        _generate_filename_base(ds.attrs, None)
