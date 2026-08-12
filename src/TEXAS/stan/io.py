# TEXAS/stan/io.py

from pathlib import Path
from typing import Union, Optional, Literal, Sequence, Any, Dict
from ..utils.paths import POSTERIOR_CACHE_DIR, INVT_CACHE_DIR
import json
import re
import numpy as np
import xarray as xr

__all__ = [
    "save_posterior",
    "load_posterior",
    "list_posteriors",
    "save_invT_posterior",
]

# By default, write into your repo under TEXAS/posterior_cache
DEFAULT_FORWARD_DIR = POSTERIOR_CACHE_DIR
DEFAULT_INVT_DIR = INVT_CACHE_DIR
DEFAULT_FORWARD_DIR.mkdir(exist_ok=True, parents=True)
DEFAULT_INVT_DIR.mkdir(exist_ok=True, parents=True)


def save_posterior(
    posterior: xr.Dataset,
    cache_dir: Optional[Union[str, Path]] = None,
    overwrite: bool = True,
    filename_suffix: str = "",
    layout: Literal["auto", "case", "legacy"] = "auto",
) -> Path:
    """
    Save a forward-model posterior to disk as compressed NetCDF.

    The filename is auto-generated from the posterior's metadata attrs:
    ``{model}_{temptype}[_gdgt23ratio][_no3_{cutoff}][_{proxy_name}]{suffix}.nc``

    Parameters
    ----------
    posterior : xr.Dataset
        Forward calibration posterior returned by ``get_posterior()``.
        Must have ``stan_model_name``, ``temptype``, and ``proxy_name``
        attrs set (``proxy_name`` is required — a warning is raised if
        missing).
    cache_dir : str or Path, optional
        Directory to write the file.  Defaults to the standard forward
        posterior cache (``data/cache/TEXAS_posterior_cache/`` for
        source installs, ``~/.texas/cache/TEXAS_posterior_cache/`` for
        pip installs).
    overwrite : bool
        If ``False``, raise ``FileExistsError`` when the output path
        already exists.  Default ``True``.
    filename_suffix : str, optional
        Extra tag appended before ``.nc``, e.g. ``"032326"`` for a
        date-stamped run.  Leading/trailing underscores are stripped.
        Under the case layout this becomes the run/member token.
    layout : {"auto", "case", "legacy"}
        Where to write.  ``"case"`` uses the CESM-style case directory
        (``tx.v026.GHEB.sst.ri3.G23-N10/fwd.nc``); ``"legacy"`` uses the
        historical long flat filename; ``"auto"`` (default) prefers the case
        layout and falls back to legacy with a warning if no case id can be
        derived.  See :mod:`TEXAS.utils.naming`.

    Returns
    -------
    Path
        Absolute path of the saved ``.nc`` file.
    """
    if not isinstance(posterior, xr.Dataset):
        raise TypeError("posterior must be an xarray.Dataset")

    outdir = Path(cache_dir) if cache_dir else DEFAULT_FORWARD_DIR
    outdir.mkdir(exist_ok=True, parents=True)

    name  = posterior.attrs.get("stan_model_name", "unknown_model")
    ttype = posterior.attrs.get("temptype", "unknown")
    if posterior.attrs.get("use_gdgt23ratio", 0):
        ttype += "_gdgt23ratio"
    if posterior.attrs.get("use_no3", 0):
        cutoff = posterior.attrs.get("no3_cutoff")
        if cutoff is None:
            raise ValueError("no3_cutoff must be set when use_no3=1")
        ttype += f"_no3_{cutoff}"

    proxy_name = posterior.attrs.get("proxy_name", "") or ""
    proxy_tag = f"_{proxy_name}" if proxy_name and proxy_name != "unknown" else ""

    # sanitize suffix
    if filename_suffix:
        filename_suffix = f"_{filename_suffix.strip('_')}"

    legacy_path = outdir / f"{name}_{ttype}{proxy_tag}{filename_suffix}.nc"

    # Preferred layout: one directory per calibration case, CESM-style, so the
    # forward posterior and every reconstruction derived from it sit together
    # and individual filenames stay short. Falls back to the historical flat
    # name whenever a case id cannot be derived (e.g. a model this naming
    # scheme does not know), so saving can never fail on naming alone.
    outpath = legacy_path
    if layout in ("case", "auto"):
        try:
            from ..utils.naming import case_from_attrs, fwd_relpath, DEFAULT_RUN
            # A date-stamped suffix becomes the run/member token, which is what
            # keeps two refits of one configuration from colliding.
            case = case_from_attrs(posterior.attrs,
                                   run=filename_suffix.strip("_") or DEFAULT_RUN)
            outpath = outdir / fwd_relpath(case)
            outpath.parent.mkdir(exist_ok=True, parents=True)
            posterior.attrs["case_id"] = str(case)
        except Exception as exc:
            if layout == "case":
                raise
            import warnings
            warnings.warn(
                f"Could not derive a case id for this posterior ({exc}); "
                f"falling back to the legacy flat filename. Pass "
                f"layout='legacy' to silence this.",
                UserWarning, stacklevel=2,
            )
            outpath = legacy_path

    if outpath.exists() and not overwrite:
        raise FileExistsError(f"{outpath} exists and overwrite=False")

    posterior.attrs["filename"] = outpath.name
    if not posterior.attrs.get("proxy_name"):
        import warnings
        warnings.warn(
            "proxy_name is not set on this posterior. "
            "Pass proxy_name= to get_posterior() (e.g. proxy_name='scaledRI'). "
            "It is stored in the .nc file and used downstream to validate that "
            "the correct proxy type is passed to predict_T_from_proxyObs().",
            UserWarning, stacklevel=2,
        )
        posterior.attrs["proxy_name"] = "unknown"
    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    sanitized = _sanitize_attrs_for_netcdf(posterior)
    sanitized.to_netcdf(outpath, encoding=encoding)
    print(f"Saved forward posterior to {outpath}  [proxy_name='{posterior.attrs['proxy_name']}']")
    return outpath


def load_posterior(
    model_name: str,
    model_type: Literal["forward", "invT"] = "forward",
    cache_dir: Optional[Union[str, Path]] = None,
) -> xr.Dataset:
    """
    Load a posterior from disk: `{model_name}.nc` in the appropriate cache directory.
    
    Args:
        model_name: Name of the model file (without .nc extension)
        model_type: Type of posterior ("forward" or "invT")
        cache_dir: Custom cache directory (overrides default locations)
    
    Returns:
        xarray.Dataset containing the posterior
        
    Raises:
        FileNotFoundError: If the posterior file doesn't exist
    """
    # Determine cache directory
    if cache_dir:
        indir = Path(cache_dir)
    elif model_type == "forward":
        indir = DEFAULT_FORWARD_DIR
    elif model_type == "invT":
        indir = DEFAULT_INVT_DIR
    else:
        # This shouldn't happen due to type hints, but just in case
        raise ValueError(f"Invalid model_type: {model_type}. Must be 'forward' or 'invT'")
    
    # Ensure directory exists
    indir.mkdir(exist_ok=True, parents=True)

    # Dual-read: accept either a case id (tx.v026.GHEB.sst.ri3.G23-N10) or a
    # historical long name, and find the file under either layout. Exact-path
    # lookups come first; the attr-matching scan only runs if those miss.
    fpath = None
    if model_type == "forward":
        try:
            from ..utils.naming import resolve_posterior_path
            fpath = resolve_posterior_path(model_name, indir)
        except Exception:
            fpath = None
    if fpath is None:
        candidate = indir / f"{model_name}.nc"
        fpath = candidate if candidate.exists() else None

    if fpath is None:
        # Case dirs hold "<case>.fwd.nc"; dirs written before 2026-08-11 hold a
        # bare "fwd.nc". Either way the case id is the directory name.
        cased = sorted(indir.glob("*/*.fwd.nc")) + sorted(indir.glob("*/fwd.nc"))
        available = sorted(indir.glob("*.nc")) + cased
        available_str = "\n    ".join(
            dict.fromkeys(
                f.parent.name if f.name.endswith("fwd.nc") else f.stem
                for f in available
            )
        ) if available else "(none)"
        model_name = str(model_name)
        raise FileNotFoundError(
            f"Posterior file not found: '{model_name}.nc'\n"
            f"Searched in: {indir}\n"
            f"Files present in that directory:\n    {available_str}\n\n"
            f"Options:\n"
            f"  1. The file is in a different directory — load it yourself and pass the Dataset:\n"
            f"       import xarray as xr\n"
            f"       ds = xr.open_dataset('/your/path/{model_name}.nc')\n"
            f"       predict_T_from_proxyObs(..., fwd_posterior=ds)\n\n"
            f"  2. Search a different cache directory:\n"
            f"       load_posterior('{model_name}', cache_dir='/your/path/here')\n\n"
            f"  3. Download from Zenodo:\n"
            f"       from TEXAS.utils.download import download_posteriors\n"
            f"       download_posteriors(['{model_name}'])"
        )

    return xr.load_dataset(fpath)


def list_posteriors(
    model_type: Literal["forward", "invT", "both"] = "both",
    cache_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, list]:
    """
    List available posterior files in the cache directory.

    Prints a summary and returns a dict of stem names that can be passed
    directly to ``predict_T_from_proxyObs(fwd_posterior=...)``.

    Parameters
    ----------
    model_type : "forward", "invT", or "both"
        Which cache to inspect.  Default ``"both"``.
    cache_dir : Path or str, optional
        Override the default cache root.  When given, both forward and invT
        subdirectories are looked for under this path.

    Returns
    -------
    dict
        ``{"forward": [...], "invT": [...]}`` — lists of stem names (no ``.nc``).
    """
    if cache_dir:
        root = Path(cache_dir)
        fwd_dir = root / "TEXAS_posterior_cache"
        invt_dir = root / "TEXAS_invT_posterior_cache"
    else:
        fwd_dir = DEFAULT_FORWARD_DIR
        invt_dir = DEFAULT_INVT_DIR

    result: Dict[str, list] = {"forward": [], "invT": []}

    def _list(directory: Path, label: str) -> list:
        files = sorted(directory.glob("*.nc")) if directory.exists() else []
        stems = [f.stem for f in files]
        print(f"{label} posteriors  [{directory}]")
        if stems:
            for name in stems:
                print(f"  {name}")
        else:
            print("  (none)")
        return stems

    if model_type in ("forward", "both"):
        result["forward"] = _list(fwd_dir, "Forward calibration")
    if model_type in ("invT", "both"):
        if model_type == "both":
            print()
        result["invT"] = _list(invt_dir, "Inverse temperature (invT)")

    return result


def save_invT_posterior(
    posterior: xr.Dataset,
    cache_dir: Optional[Union[str, Path]] = None,
    overwrite: bool = True,
    filename_tag: Optional[Union[str, Sequence[str]]] = None,
) -> Path:
    """
    Save an inverse-T posterior to disk as compressed NetCDF.

    Default location: repo/.../TEXAS/invT_posterior_cache/

    The filename comes from :func:`_generate_filename_base`, the same builder
    the internal save path uses, so a reconstruction lands in one place however
    it was produced.

    This function used to build ``{site}_{model}_{temptype}.nc`` itself, which
    omitted ``proxy_name``: a ``scaledRI`` and a ``TEX86`` reconstruction of one
    site collided on a single path, and with the default ``overwrite=True`` the
    second silently replaced the first. It was also case-unaware, so it could
    not place a reconstruction inside its calibration's case directory. Nothing
    on disk used that spelling -- every cached invT posterior came from the
    internal path -- so unifying them changes no existing file.
    """
    if not isinstance(posterior, xr.Dataset):
        raise TypeError("posterior must be an xarray.Dataset")

    return _save_invT_posterior(
        posterior=posterior,
        cache_dir=cache_dir,
        overwrite=overwrite,
        filename_tag=filename_tag,
    )


# ─── Private helpers for invT I/O ──────────────────────────────────────────

def _slug(x: str) -> str:
    s = str(x).strip().replace(" ", "-")
    return re.sub(r"[^a-zA-Z0-9._-]+", "", s)


def _generate_filename_base(
    meta: Dict[str, Any],
    filename_tag: Optional[Union[str, Sequence[str]]],
) -> str:
    """
    Generate the base filename for saving invT results.

    Format: {site}_{model}_{temptype}_{tags}_{model_type}
    Model type (direct/ensemble) goes at the end for easy identification.
    """
    site_name = _slug(meta.get("SiteName", meta.get("site_name", "unknown_site")))
    stan_model = meta.get("stan_model_name", meta.get("stan_model", "unknown_model"))
    temptype = meta.get("temptype", "unknown_temptype")

    if "marginal" in stan_model:
        model_type = "direct"
        clean_stan_model = stan_model.replace("_marginal", "")
    else:
        model_type = "ensemble"
        clean_stan_model = stan_model

    # Case layout: a reconstruction belongs to the calibration it marginalised
    # over, so it is written inside that calibration's case directory under a
    # short leaf name. Requires the fwd_case attr that build_invT_inputData
    # attaches; posteriors produced before that fall through to the legacy name.
    fwd_case = meta.get("fwd_case", "")
    if fwd_case:
        try:
            from ..utils.naming import CONSTRAINT_CODES, KIND_CODES, is_case_id
            if is_case_id(fwd_case):
                constraint = next(
                    (c for c in CONSTRAINT_CODES if c in stan_model), "unconstrained"
                )
                parts = [f"{CONSTRAINT_CODES[constraint]}{KIND_CODES[model_type]}"]
                if filename_tag:
                    tags = [filename_tag] if isinstance(filename_tag, str) else filename_tag
                    parts.extend(_slug(t) for t in tags if t)
                # Leaf repeats the case so a reconstruction copied out of its
                # case directory still names the calibration it came from.
                # NOTE: this still duplicates naming.inv_relpath() rather than
                # calling it (it omits the run number). Consolidating the two is
                # Phase 5A in RESUME.md; do not add a third spelling here.
                return f"{fwd_case}/{fwd_case}.inv.{site_name}.{'-'.join(parts)}"
        except Exception:
            pass  # naming is a convenience; never block a save on it

    temp_parts = [temptype]
    if int(meta.get("use_gdgt23ratio", 0)) == 1:
        temp_parts.append("gdgt23ratio")
    if int(meta.get("use_no3", 0)) == 1:
        no3_cutoff = meta.get("no3_cutoff")
        if no3_cutoff is None:
            raise ValueError("no3_cutoff missing but use_no3=1.")
        temp_parts.append(f"no3_{no3_cutoff}")
    temptype_str = "_".join(temp_parts)

    proxy_name = meta.get("proxy_name", "") or ""
    proxy_segment = f"_{_slug(proxy_name)}" if proxy_name and proxy_name != "unknown" else ""

    tag_segment = ""
    if filename_tag:
        tags = [filename_tag] if isinstance(filename_tag, str) else filename_tag
        tag_segment = "_" + "+".join(_slug(t) for t in tags if t)

    return f"{site_name}_{clean_stan_model}_{temptype_str}{proxy_segment}{tag_segment}_{model_type}"


def _sanitize_attrs_for_netcdf(ds: xr.Dataset) -> xr.Dataset:
    """Convert posterior attrs to NetCDF-compatible types."""
    clean_attrs = {}
    for k, v in ds.attrs.items():
        if v is None:
            continue
        elif isinstance(v, bool):
            clean_attrs[k] = int(v)
        elif isinstance(v, (str, bytes, int, float, np.number)):
            clean_attrs[k] = v
        elif isinstance(v, (list, tuple, np.ndarray)):
            arr = np.asarray(v)
            if arr.dtype == bool:
                clean_attrs[k] = arr.astype(int).tolist()
            else:
                clean_attrs[k] = arr.tolist()
        else:
            try:
                clean_attrs[k] = json.dumps(v)
            except TypeError:
                clean_attrs[k] = str(v)

    ds_copy = ds.copy()
    ds_copy.attrs = clean_attrs
    return ds_copy


def _save_invT_posterior(
    posterior: xr.Dataset,
    cache_dir: Optional[Union[str, Path]] = None,
    overwrite: bool = True,
    filename_tag: Optional[Union[str, Sequence[str]]] = None,
) -> Path:
    """Save an invT posterior with detailed auto-generated filename."""
    output_dir = Path(cache_dir) if cache_dir else DEFAULT_INVT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    base = _generate_filename_base(posterior.attrs, filename_tag)
    filepath = output_dir / f"{base}.nc"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    if filepath.exists() and not overwrite:
        raise FileExistsError(f"{filepath} already exists and overwrite=False.")
    posterior.attrs.setdefault("proxy_name", "")
    # Record the name we wrote, as save_posterior does for forward posteriors.
    # It is what lets a file renamed later still be resolved by its original
    # name, and what run_from_attrs() reads to recover a run token.
    posterior.attrs["filename"] = filepath.name
    encoding = {var: {"zlib": True} for var in posterior.data_vars}
    sanitized = _sanitize_attrs_for_netcdf(posterior)
    sanitized.to_netcdf(filepath, encoding=encoding)
    print(f"✅ Posterior saved to {filepath}")
    return filepath


def _save_invT_draws(
    draws: xr.Dataset,
    cache_dir: Optional[Union[str, Path]] = None,
    filename_tag: Optional[Union[str, Sequence[str]]] = None,
    overwrite: bool = True,
) -> Path:
    """Save raw invT posterior draws (pre-quantile) as a compressed .nc file.

    The filename mirrors the quantile posterior but with a ``_draws`` suffix,
    e.g. ``ODP1259_..._040226_direct_draws.nc``.
    
    Draws are automatically organized into a ``draws/`` subdirectory.
    """
    base_dir = Path(cache_dir) if cache_dir else DEFAULT_INVT_DIR
    output_dir = base_dir / "draws"  # Auto-organize into draws subfolder
    output_dir.mkdir(parents=True, exist_ok=True)
    base = _generate_filename_base(draws.attrs, filename_tag)
    filepath = output_dir / f"{base}_draws.nc"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    if filepath.exists() and not overwrite:
        raise FileExistsError(f"{filepath} already exists and overwrite=False.")
    encoding = {var: {"zlib": True} for var in draws.data_vars}
    sanitized = _sanitize_attrs_for_netcdf(draws)
    sanitized.to_netcdf(filepath, encoding=encoding)
    print(f"✅ Raw draws saved to {filepath}")
    return filepath


def _save_invT_results(
    results: Dict[str, Any],
    path: Optional[Union[str, Path]] = None,
    overwrite: bool = True,
) -> Path:
    """Save invT quantile results dict as a compressed .npz file."""
    meta = results.get("metadata", {})
    if path is None:
        output_dir = DEFAULT_INVT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        filename_tag = meta.get("filename_tag")
        base = _generate_filename_base(meta, filename_tag)
        path = output_dir / f"{base}.npz"
    else:
        path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists and overwrite=False.")
    savez_dict = {k: np.asarray(v) for k, v in results.items() if k != "metadata"}
    savez_dict["__metadata__"] = np.array([json.dumps(meta)])
    np.savez(path, **savez_dict)
    print(f"✅ invT results saved: {path}")
    return path
