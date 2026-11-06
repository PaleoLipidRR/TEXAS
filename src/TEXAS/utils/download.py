# TEXAS/utils/download.py
"""
Utilities for downloading data from the TEXAS Zenodo data record.

Files are downloaded one at a time, so you only fetch what you need. Most
users need no download at all: the package already ships four forward
calibration posteriors (posterior = the set of calibration-parameter values
the fit found plausible, stored as MCMC draws): tx.GHEB.{sst,thm}.sri03.G23-N1p0
and tx.GHPU.{sst,thm}.sri03.p0.

The full multivariate (EIV) posteriors on Zenodo are ~78–81 MB each, because
they also store the per-site latent (estimated "true") predictor values; the
bundled copies leave those out. The other posteriors are < 1 MB and the
training files are 1–20 MB. A size notice is printed before any download of
5 MB or more.

Usage
-----
>>> import TEXAS
>>> TEXAS.download_all()               # everything: posteriors + training data
>>> TEXAS.download_all(figures=True)   # + invT reconstructions + WOA23 (>1 GB)
>>> TEXAS.download_posteriors()        # forward calibration posteriors only
>>> TEXAS.download_training_data()     # training CSVs + NO₃ fields
>>> TEXAS.download_ocean_properties()  # just the ocean_prop_ds field (CMEMS NO₃ + WOA23 T)
>>> TEXAS.download_invT_posteriors()   # invT reconstructions behind SI_code02/03
>>> TEXAS.download_woa23()             # WOA23 climatologies (>1 GB; SI_code00 only)

Download a specific posterior that is not bundled:
>>> TEXAS.download_posteriors(["tx.GHEB.sst.sri03.G23"])

Docker/devcontainer users: run on the host machine — the container
bind-mounts ``data/`` automatically.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional

from . import paths as _paths

# ─── Zenodo config ────────────────────────────────────────────────────────────
# The current version of the data record (concept DOI 10.5281/zenodo.19666744),
# pointing at the v1.0.0 deposit created by scripts/zenodo_upload.py -- the
# calibration set and posteriors behind the revised manuscript (1,518 gridded
# core-tops, 8 mesocosm, 59 culture experiments; scaledRI_cren3 screen).
ZENODO_RECORD_ID: str = "23954718"

# Registry entries may pin a different record ("record": "<id>"); files
# without a pin are fetched from ZENODO_RECORD_ID.
_V020_RECORD_ID: str = "20032542"   # v0.2.0: initial-submission (additive) files

# ocean_prop_ds isn't a TEXAS-record file at all -- it's produced and hosted
# on the Zenodo record for the companion GRL paper, which is the canonical
# source SI_code00_PreProcessing itself downloads it from.
_GRL_PAPER_RECORD_ID: str = "14806962"

# The invT reconstructions behind SI_code02/SI_code03 (compiled global-coretop
# maps + every paleo-site reconstruction, including the two full-draws files
# behind paper Fig. 13) ship as one zip rather than 46 individual Zenodo files.
# The "v0.4.0" in the name is part of a filename on the published record, not
# the package version: it is the version the zip was built under and stays
# fixed even though the record itself is v1.0.0.
_INVT_ZIP_FILENAME: str = "texas-psm-invT-posteriors-v0.4.0.zip"

# WOA23 (World Ocean Atlas) climatologies are public-domain NOAA/NCEI
# products, fetched directly from NCEI rather than re-hosted on the TEXAS
# record (SI_code00_PreProcessing's own source). Sizes are the files' real
# sizes, not estimates -- the 0.25-degree temperature grid alone is >1 GB.
_WOA23_BASE = "https://www.ncei.noaa.gov/thredds-ocean/fileServer/woa23/DATA"
WOA23_FILES: dict[str, dict] = {
    "temperature_0.25deg": {
        "url": f"{_WOA23_BASE}/temperature/netcdf/decav91C0/0.25/woa23_decav91C0_t00_04.nc",
        "dest": "woa23/temperature/woa23_decav91C0_t00_04.nc",
        "size_mb": 1016,
    },
    "temperature_1deg": {
        "url": f"{_WOA23_BASE}/temperature/netcdf/decav91C0/1.00/woa23_decav91C0_t00_01.nc",
        "dest": "woa23/temperature/woa23_decav91C0_t00_01.nc",
        "size_mb": 78,
    },
    "nitrate_1deg": {
        "url": f"{_WOA23_BASE}/nitrate/netcdf/all/1.00/woa23_all_n00_01.nc",
        "dest": "woa23/nitrate/woa23_all_n00_01.nc",
        "size_mb": 45,
    },
}


def _file_url(filename: str, record: Optional[str] = None) -> str:
    rec = record or ZENODO_RECORD_ID
    return f"https://zenodo.org/records/{rec}/files/{filename}?download=1"


def _fmt_size(size_mb: float) -> str:
    if size_mb >= 1:
        return f"~{size_mb:.0f} MB"
    return f"~{size_mb * 1024:.0f} KB"


def _download_file(url: str, dest: Path, size_mb: float, force: bool = False) -> Path:
    """Download a single file from *url* to *dest*."""
    if dest.exists() and not force:
        print(f"Already cached: {dest.name}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    if size_mb >= 5:
        print(f"Downloading {dest.name} ({_fmt_size(size_mb)}) …")
    else:
        print(f"Downloading {dest.name} …")
    try:
        with urllib.request.urlopen(url) as resp:
            if resp.status != 200:
                raise urllib.error.URLError(
                    f"Zenodo returned HTTP {resp.status} for {url!r}.\n"
                    "  The data record may not be published yet — "
                    "contact the authors or check "
                    f"https://doi.org/10.5281/zenodo.{ZENODO_RECORD_ID}"
                )
            dest.write_bytes(resp.read())
    except urllib.error.URLError:
        raise
    except Exception as e:
        raise urllib.error.URLError(f"Download failed: {e}") from e
    print(f"  → saved to {dest}")
    return dest


# ─── Registry of forward calibration posteriors ───────────────────────────────
# Each entry: name (no .nc) → {"filename": str, "size_mb": float}
# filename is the flat name on the Zenodo record (no subdirectory); an optional
# "record" pins the entry to an older version of the record.
#
# The current record holds the published calibrations under their case ids
# (T₀-shift multivariate `GHEB`, temperature-only `GHPU`, culture+mesocosm
# `GCDU`). The multivariate files are the COMPLETE archival copies, EIV per-site
# latents included (~78–81 MB). The package already bundles small copies of
# tx.GHEB.{sst,thm}.sri03.G23-N1p0 (latents removed) and
# tx.GHPU.{sst,thm}.sri03.p0, so most users never need these downloads.
POSTERIOR_REGISTRY: dict[str, dict] = {
    # ── Default calibration: full multivariate T₀-shift (G₂/₃ + NO₃) ─────────
    "tx.GHEB.sst.sri03.G23-N1p0": {
        "filename": "tx.GHEB.sst.sri03.G23-N1p0.fwd.nc", "size_mb": 78,
    },
    "tx.GHEB.thm.sri03.G23-N1p0": {
        "filename": "tx.GHEB.thm.sri03.G23-N1p0.fwd.nc", "size_mb": 78,
    },
    # ── Single-predictor T₀-shift variants ───────────────────────────────────
    "tx.GHEB.sst.sri03.G23": {
        "filename": "tx.GHEB.sst.sri03.G23.fwd.nc", "size_mb": 78,
    },
    "tx.GHEB.thm.sri03.G23": {
        "filename": "tx.GHEB.thm.sri03.G23.fwd.nc", "size_mb": 78,
    },
    "tx.GHEB.sst.sri03.N1p0": {
        "filename": "tx.GHEB.sst.sri03.N1p0.fwd.nc", "size_mb": 81,
    },
    "tx.GHEB.thm.sri03.N1p0": {
        "filename": "tx.GHEB.thm.sri03.N1p0.fwd.nc", "size_mb": 81,
    },
    # ── Temperature-only calibrations ────────────────────────────────────────
    "tx.GHPU.sst.sri03.p0": {
        "filename": "tx.GHPU.sst.sri03.p0.fwd.nc", "size_mb": 0.3,
    },
    "tx.GHPU.thm.sri03.p0": {
        "filename": "tx.GHPU.thm.sri03.p0.fwd.nc", "size_mb": 0.3,
    },
    # ── Stage-1 culture+mesocosm fit ─────────────────────────────────────────
    "tx.GCDU.cul.sri03.p0": {
        "filename": "tx.GCDU.cul.sri03.p0.fwd.nc", "size_mb": 0.2,
    },
    # ── Initial-submission (additive) posteriors, v0.2.0 record ──────────────
    # Superseded by the T₀-shift refits above; kept resolvable so preprint-era
    # notebooks still run. Pinned to the old version of the record, which
    # Zenodo preserves permanently.
    "gen_logi_fixed_culmeso_cultureT_scaledRI_cren3": {
        "filename": "gen_logi_fixed_culmeso_cultureT_scaledRI_cren3.nc",
        "size_mb": 0.2, "record": _V020_RECORD_ID,
    },
    "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3": {
        "filename": "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc",
        "size_mb": 0.3, "record": _V020_RECORD_ID,
    },
    "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3": {
        "filename": "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3.nc",
        "size_mb": 0.3, "record": _V020_RECORD_ID,
    },
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3": {
        "filename": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc",
        "size_mb": 78, "record": _V020_RECORD_ID,
    },
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3": {
        "filename": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3.nc",
        "size_mb": 78, "record": _V020_RECORD_ID,
    },
}

# ─── Training data registry ───────────────────────────────────────────────────
# Each entry: name → {"filename": str, "size_mb": float}
TRAINING_DATA_REGISTRY: dict[str, dict] = {
    "combined_coretop_culture_mesocosm": {
        "filename": "combined_coretop_culture_mesocosm_rev20260210.csv",
        "size_mb": 1.8,
    },
    "ds_gridded_screened_global": {
        "filename": "ds_gridded_screened_global_compilation_finalized.csv",
        "size_mb": 1.0,
    },
    "cmems_no3_uncertainty_field": {
        "filename": "cmems_no3_uncertainty_field.nc",
        "size_mb": 14,
    },
    # Gridded ocean properties ("ocean_prop_ds" in the SI notebooks): CMEMS
    # nitrate climatology and WOA23 temperature on the WOA23 0.25-degree grid.
    # (The file's own `history` attr records the split; the nitrate is NOT WOA23.)
    # It is the dataset used by the SI
    # preprocessing notebooks). Unlike the other three entries this one is
    # also used at inference time — by predict_T_from_proxyObs(site_lat=,
    # site_lon=) — not only to re-run the SI notebooks from scratch, so it
    # has its own download_ocean_properties() convenience wrapper below.
    #
    # Pinned to the Zenodo record for the companion GRL paper, which is
    # where this file is actually produced and hosted — not the TEXAS
    # record, so no re-upload/re-hosting here.
    "ocean_prop_ds": {
        "filename": "ds06_calculated_ocean_properties.nc",
        "size_mb": 20,
        "record": _GRL_PAPER_RECORD_ID,
    },
}


# ─── Public API ───────────────────────────────────────────────────────────────

def download_all(
    cache_dir: Optional[Path | str] = None,
    data_dir: Optional[Path | str] = None,
    force: bool = False,
    figures: bool = False,
) -> None:
    """Download everything from Zenodo: forward posteriors + training data.

    Files are downloaded individually; already-cached files are skipped unless
    *force=True*.  With the default ``figures=False`` the total is ~510 MB:
    ~475 MB for the nine current-record forward posteriors (almost all of it
    the six full multivariate EIV posteriors, ~78–81 MB each) plus ~37 MB of
    training data (:func:`download_training_data`). The superseded v0.2.0
    posteriors are not included; request them by name with
    :func:`download_posteriors`.

    Parameters
    ----------
    cache_dir : Path or str, optional
        Destination for ``.nc`` posteriors.  Defaults to the standard
        posterior cache directory.
    data_dir : Path or str, optional
        Destination for training data files.  Defaults to ``data/spreadsheets/``.
    force : bool
        Re-download files that already exist locally.
    figures : bool
        Also fetch what the ``notebooks/manuscripts/SI_code*`` figure
        notebooks need beyond the default forward-posterior + training-CSV
        set: the invT reconstructions behind SI_code02/SI_code03
        (:func:`download_invT_posteriors`) and the WOA23 climatologies
        SI_code00 reads (:func:`download_woa23`, **>1 GB**, skipped unless
        this is set). Does not yet cover every external file those
        notebooks read — see ``docs/`` for the current gaps.
    """
    download_posteriors(cache_dir=cache_dir, force=force)
    download_training_data(dest_dir=data_dir, force=force)
    if figures:
        download_invT_posteriors(force=force)
        download_woa23(force=force)


def download_posteriors(
    names: Optional[List[str]] = None,
    cache_dir: Optional[Path | str] = None,
    force: bool = False,
) -> List[Path]:
    """Download forward calibration posteriors from Zenodo.

    Parameters
    ----------
    names : list of str, optional
        Subset of ``POSTERIOR_REGISTRY`` keys to download.  When omitted,
        downloads every posterior of the current record version (~475 MB —
        dominated by the six full multivariate EIV posteriors at ~78–81 MB
        each; pass ``names=`` to fetch only what you need).  Superseded
        initial-submission posteriors are pinned to the v0.2.0 record and
        must be requested by name.
    cache_dir : Path or str, optional
        Destination directory.  Defaults to the standard posterior cache.
    force : bool
        Re-download files that already exist locally.

    Returns
    -------
    list of Path
        Local paths of the downloaded ``.nc`` files.

    Examples
    --------
    Download the G₂/₃-only SST calibration (~78 MB):

    >>> download_posteriors(["tx.GHEB.sst.sri03.G23"])

    The four bundled posteriors (tx.GHEB.{sst,thm}.sri03.G23-N1p0 and
    tx.GHPU.{sst,thm}.sri03.p0) ship with the package and need no download;
    the Zenodo copies of the GHEB pair are the complete archival versions.
    """
    # By default download only the current-record posteriors; superseded
    # entries pinned to an older record version must be asked for by name.
    targets = names if names is not None else [
        k for k, v in POSTERIOR_REGISTRY.items() if "record" not in v
    ]
    dest_dir = Path(cache_dir) if cache_dir else _paths.POSTERIOR_CACHE_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    aliases = _case_aliases()
    POSTERIOR_REGISTRY.update(aliases)      # case ids resolve to the same files

    for name in targets:
        if name not in POSTERIOR_REGISTRY:
            available = "\n  ".join(POSTERIOR_REGISTRY)
            raise KeyError(
                f"'{name}' is not in POSTERIOR_REGISTRY.\n"
                f"Available posteriors:\n  {available}"
            )

    local_paths = {n: _local_dest(dest_dir, n) for n in targets}

    missing = [n for n in targets if not local_paths[n].exists() or force]
    if not missing:
        print("All requested posteriors already cached.")
        return [local_paths[n] for n in targets]

    total_mb = sum(POSTERIOR_REGISTRY[n]["size_mb"] for n in missing)
    if total_mb >= 5:
        print(f"Downloading {len(missing)} posterior(s) — total ~{total_mb:.0f} MB")

    paths = []
    for name in targets:
        entry = POSTERIOR_REGISTRY[name]
        dest = local_paths[name]
        dest.parent.mkdir(parents=True, exist_ok=True)
        _download_file(
            _file_url(entry["filename"], entry.get("record")),
            dest, entry["size_mb"], force=force,
        )
        paths.append(dest)

    return paths


def _case_aliases() -> dict:
    """
    Case-id aliases for the registry's legacy long-name keys.

    The current record already uses case-id filenames and keys. Only the
    superseded posteriors on the old v0.2.0 record still carry legacy long
    names (e.g. ``gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3``),
    and those files cannot be renamed on a published record. This adds a
    case-id key for each of them that points at the same file, so either name
    can be requested.

    Built rather than hand-listed so it cannot fall out of step with the
    registry. Failures are silent because an alias is a convenience: a key
    this naming scheme cannot classify simply keeps only its legacy name.
    """
    from .naming import case_from_attrs, legacy_fwd_name  # noqa: F401
    out = {}
    for key, entry in POSTERIOR_REGISTRY.items():
        try:
            out[_case_id_for(key)] = entry
        except Exception:
            continue
    return {k: v for k, v in out.items() if k and k not in POSTERIOR_REGISTRY}


def _case_id_for(legacy_key: str) -> str:
    """Derive a case id from a legacy registry key, by re-reading its parts."""
    from .naming import case_from_attrs
    import re
    m = re.match(r"^(?P<model>.+?)_(?P<temptype>SST|thermoT|cultureT)"
                 r"(?P<g23>_gdgt23ratio)?(?:_no3_(?P<cut>[0-9.]+))?"
                 r"_(?P<proxy>.+)$", legacy_key)
    if not m:
        return ""
    g = m.groupdict()
    attrs = {"stan_model_name": g["model"], "temptype": g["temptype"],
             "proxy_name": g["proxy"], "use_gdgt23ratio": int(bool(g["g23"])),
             "use_no3": int(g["cut"] is not None)}
    if g["cut"] is not None:
        attrs["no3_cutoff"] = float(g["cut"])
    return str(case_from_attrs(attrs))


def _local_dest(dest_dir: Path, name: str) -> Path:
    """
    Where a Zenodo posterior lands locally.

    The Zenodo record is a **flat** namespace -- a DOI deposit has no
    subdirectories -- and so is the local cache. A registry
    key that is a case id lands at ``<case>.fwd.nc``, the same path
    ``save_posterior`` writes, giving one uniform local layout no matter whether
    a posterior was sampled here or downloaded. Legacy long-name keys (the
    v0.2.0 record's files) keep their long names.
    """
    try:
        from .naming import fwd_relpath, is_case_id
        if is_case_id(name):
            # Flat both sides now, so this is a rename rather than an unpack.
            return dest_dir / fwd_relpath(name)
    except Exception:
        pass  # naming is a convenience; never block a download on it
    return dest_dir / f"{name}.nc"


def download_training_data(
    dest_dir: Optional[Path | str] = None,
    force: bool = False,
) -> List[Path]:
    """Download GDGT training data files from Zenodo.

    Downloads the coretop/culture/mesocosm training CSVs, the CMEMS NO₃
    uncertainty field used in the EIV calibration, and the ``ocean_prop_ds``
    gridded ocean properties (CMEMS nitrate, WOA23 temperature).  The CSVs and the CMEMS field
    are needed only to re-run the SI preprocessing and calibration notebooks
    from scratch and are NOT required for inverse temperature
    reconstructions — use :func:`download_posteriors` for that.
    ``ocean_prop_ds`` is the exception: it is also used at inference time by
    :func:`~TEXAS.predict.predict_T_from_proxyObs` for the optional
    ``site_lat``/``site_lon`` NO₃ lookup — see :func:`download_ocean_properties`
    to fetch just that one file. It also isn't hosted on the TEXAS record at
    all; it comes from the companion GRL paper's Zenodo record (see
    ``TRAINING_DATA_REGISTRY["ocean_prop_ds"]["record"]``).

    Parameters
    ----------
    dest_dir : Path or str, optional
        Destination directory.  Defaults to ``data/spreadsheets/`` in the
        repo (or ``~/.texas/data/spreadsheets/`` when pip-installed).
    force : bool
        Re-download files that already exist locally.

    Returns
    -------
    list of Path
        Local paths of the downloaded files.
    """
    dest = Path(dest_dir) if dest_dir else _paths.SPREADSHEETS_DIR
    dest.mkdir(parents=True, exist_ok=True)

    missing = [
        name for name, entry in TRAINING_DATA_REGISTRY.items()
        if not (dest / entry["filename"]).exists() or force
    ]
    if not missing:
        print("All training data files already present.")
        return [dest / entry["filename"] for entry in TRAINING_DATA_REGISTRY.values()]

    total_mb = sum(TRAINING_DATA_REGISTRY[n]["size_mb"] for n in missing)
    if total_mb >= 5:
        print(f"Downloading {len(missing)} training data file(s) — total ~{total_mb:.0f} MB")

    paths = []
    for name, entry in TRAINING_DATA_REGISTRY.items():
        out = dest / entry["filename"]
        _download_file(
            _file_url(entry["filename"], entry.get("record")),
            out, entry["size_mb"], force=force,
        )
        paths.append(out)

    return paths


def download_ocean_properties(
    dest_dir: Optional[Path | str] = None,
    force: bool = False,
) -> Path:
    """Download the ``ocean_prop_ds`` ocean-properties field from Zenodo.

    This is the single file most users need for the ``site_lat``/``site_lon``
    NO₃ lookup in :func:`~TEXAS.predict.predict_T_from_proxyObs` — a ~20 MB
    gridded ``(lat, lon)`` dataset of thermocline-depth-integrated CMEMS
    nitrate (on the WOA23 grid, beside WOA23 temperature). Downloading just this entry (rather than the full
    :func:`download_training_data`, which also fetches ~17 MB of training
    CSVs and the CMEMS field) is why this has its own function.

    Fetched from the Zenodo record for the companion GRL paper (not the
    TEXAS project's own record) — the same source ``SI_code00_PreProcessing``
    itself downloads it from.

    Idempotent: skips the download if the file is already cached, unless
    *force=True*.

    Parameters
    ----------
    dest_dir : Path or str, optional
        Destination directory.  Defaults to ``data/spreadsheets/`` in the
        repo (or ``~/.texas/data/spreadsheets/`` when pip-installed) — the
        same directory :func:`download_training_data` uses.
    force : bool
        Re-download even if the file already exists locally.

    Returns
    -------
    Path
        Local path of the downloaded ``.nc`` file.  Open it with
        ``xr.open_dataset(path)``, or use
        :func:`TEXAS.data.ocean_lookup.get_ocean_prop_ds` to download and
        open it in one call.
    """
    dest = Path(dest_dir) if dest_dir else _paths.SPREADSHEETS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    entry = TRAINING_DATA_REGISTRY["ocean_prop_ds"]
    out = dest / entry["filename"]
    _download_file(
        _file_url(entry["filename"], entry.get("record")),
        out, entry["size_mb"], force=force,
    )
    return out


def download_invT_posteriors(
    cache_dir: Optional[Path | str] = None,
    force: bool = False,
) -> List[Path]:
    """Download and unpack the invT reconstructions behind SI_code02/SI_code03.

    Fetches ``texas-psm-invT-posteriors-v{N}.zip`` from the TEXAS Zenodo data
    record — the compiled global-coretop reconstructions (paper Figs. 8–9
    and SI Figs. S13–S17, made by SI_code02) and every paleo-site
    reconstruction (SI_code03), including the two full-draws files behind
    paper Fig. 13 — and unpacks it flat into the
    invT posterior cache, the same layout :func:`~TEXAS.stan.io.save_invT_posterior`
    writes locally: ``<case>.inv.<site>.ud[-<variant>].nc`` at the cache root,
    ``_draws.nc`` files under ``draws/``. The zip's own ``invT/coretop/`` and
    ``invT/paleo/`` prefixes are a Zenodo-side packaging detail, not part of
    the local layout, and are discarded on unpack.

    Parameters
    ----------
    cache_dir : Path or str, optional
        Destination directory. Defaults to :data:`TEXAS.utils.paths.INVT_CACHE_DIR`.
    force : bool
        Re-download and re-unpack even if the zip is already cached.
        Existing extracted files are always overwritten (the zip is the
        source of truth for its own contents).

    Returns
    -------
    list of Path
        Local paths of every file extracted from the zip.
    """
    import zipfile

    dest_dir = Path(cache_dir) if cache_dir else _paths.INVT_CACHE_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    zip_path = dest_dir / _INVT_ZIP_FILENAME
    _download_file(_file_url(_INVT_ZIP_FILENAME), zip_path, size_mb=4, force=force)

    extracted: List[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            name = Path(member.filename).name
            out = (dest_dir / "draws" / name) if name.endswith("_draws.nc") \
                else (dest_dir / name)
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(out, "wb") as dst:
                dst.write(src.read())
            extracted.append(out)
    print(f"  → unpacked {len(extracted)} file(s) into {dest_dir}")
    return extracted


def download_woa23(
    dest_dir: Optional[Path | str] = None,
    force: bool = False,
) -> List[Path]:
    """Download the WOA23 climatologies ``SI_code00_PreProcessing`` reads.

    Fetches the three World Ocean Atlas 2023 files directly from NOAA/NCEI
    (public domain — not re-hosted on the TEXAS Zenodo record):
    0.25-degree and 1-degree annual-mean temperature, and 1-degree annual-mean
    nitrate. **This is a >1 GB download** (the 0.25-degree temperature grid
    alone is ~1 GB) — nothing calls this automatically; it's for reproducing
    SI_code00 from scratch, not for inverse temperature reconstructions.

    Parameters
    ----------
    dest_dir : Path or str, optional
        Destination directory. Defaults to
        ``TEXAS.utils.paths.EXTERNAL_DATA_DIR / "woa23"``.
    force : bool
        Re-download files that already exist locally.

    Returns
    -------
    list of Path
        Local paths of the three downloaded files.
    """
    dest = Path(dest_dir) if dest_dir else _paths.EXTERNAL_DATA_DIR
    total_mb = sum(
        e["size_mb"] for e in WOA23_FILES.values()
        if force or not (dest / e["dest"]).exists()
    )
    if total_mb >= 5:
        print(f"Downloading WOA23 climatologies — total ~{total_mb / 1024:.1f} GB "
              "from NOAA/NCEI")

    paths = []
    for entry in WOA23_FILES.values():
        out = dest / entry["dest"]
        _download_file(entry["url"], out, entry["size_mb"], force=force)
        paths.append(out)
    return paths
