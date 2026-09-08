"""
The two invT save paths must produce the same filename.

``save_invT_posterior`` is the public, __all__-exported entry point;
``_save_invT_posterior`` is what the production path
(``predict_T_from_proxyObs`` -> ``get_invT_posterior``) calls. They used to
build filenames by different rules, and the public one omitted ``proxy_name``
entirely -- so a scaledRI and a TEX86 reconstruction of one site resolved to a
single path and, with the default overwrite=True, the second silently
destroyed the first.

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


def test_the_leaf_names_its_parent_calibration(tmp_path):
    """
    With a fwd_case attr the reconstruction is named for the calibration it
    marginalised over -- beside it, not inside it. The case directory was
    dropped on 2026-08-12; the leaf already carried the whole case id, so the
    directory only repeated it. The old public path could do neither.
    """
    case = "tx.GHEA.sst.sri03.G23-N10"
    path = save_invT_posterior(_posterior(fwd_case=case), cache_dir=tmp_path)
    assert path.parent == tmp_path, f"writes should be flat, got {path}"
    assert path.name.startswith(f"{case}.inv."), path.name


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


def test_predict_T_from_proxyObs_writes_the_npz_itself(tmp_path, monkeypatch):
    """The .npz save moved out of the deleted wrapper and into predict.py."""
    import numpy as np
    import TEXAS.predict as predict_mod

    reduced = xr.Dataset(
        {"t_est": (("quantile", "obs_idx"),
                   np.tile(np.array([[5.0], [20.0], [35.0]]), (1, 3)))},
        coords={"quantile": [0.05, 0.5, 0.95], "obs_idx": np.arange(3)},
    )
    reduced.attrs.update({
        "SiteName": "TestSite", "temptype": "SST", "proxy_name": "scaledRI_cren3",
        "stan_model_name": "invT_gen_logi_fixed_univ_marginal_unconstrained",
        "use_gdgt23ratio": 0, "use_no3": 0, "no3_cutoff": 0.0,
        "model_type": "direct",
    })
    monkeypatch.setattr(predict_mod, "_get_invT_posterior",
                        lambda *a, **k: reduced)

    fwd = xr.Dataset(attrs={"use_gdgt23ratio": 0, "use_no3": 0,
                            "proxy_name": "scaledRI_cren3", "temptype": "SST"})
    result = predict_mod.predict_T_from_proxyObs(
        np.array([0.3, 0.4, 0.5]), prior_mu_t=20.0, prior_sigma_t=10.0,
        fwd_posterior=fwd, flags=False, save_results=True, cache_dir=tmp_path,
    )

    assert set(["p5", "p50", "p95"]).issubset(result)
    np.testing.assert_allclose(result["p50"], 20.0)
    written = list(tmp_path.glob("*.npz"))
    assert len(written) == 1, f"expected one .npz, got {written}"
    assert "TestSite" in written[0].name
