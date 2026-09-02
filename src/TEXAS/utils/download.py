# TEXAS/utils/download.py
"""
Utilities for downloading data from the TEXAS Zenodo data record.

Files are downloaded individually from Zenodo so you only fetch what you need.
The full multivariate (EIV) posteriors are ~78–81 MB each — they carry the
per-site latent variables; the wheel already bundles a latent-stripped copy of
the default pair, so most reconstructions need no download at all. All other
files are < 2 MB.  A size notice is printed before any download ≥ 5 MB.

Usage
-----
>>> import TEXAS
>>> TEXAS.download_all()               # everything: posteriors + training data
>>> TEXAS.download_posteriors()        # forward calibration posteriors only
>>> TEXAS.download_training_data()     # training CSVs + NO₃ fields
>>> TEXAS.download_ocean_properties()  # just the WOA23 ocean_prop_ds field

Download a specific posterior:
>>> TEXAS.download_posteriors(["tx.GHPU.sst.sri03.p0"])

Docker/devcontainer users: run on the host machine — the container
bind-mounts ``data/`` automatically.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional

from .paths import POSTERIOR_CACHE_DIR, SPREADSHEETS_DIR

# ─── Zenodo config ────────────────────────────────────────────────────────────
# The current version of the data record (concept DOI 10.5281/zenodo.19666744).
# TODO(v0.3.0 release): replace with the record id of the v0.3.0 deposit as soon
# as `scripts/zenodo_upload.py` creates the draft — the draft's id is final even
# before it is published — then tag the release.
ZENODO_RECORD_ID: str = "22131367"

# Registry entries may pin an older version of the record ("record": "<id>");
# files without a pin are fetched from ZENODO_RECORD_ID.
_V020_RECORD_ID: str = "20032542"   # v0.2.0: initial-submission (additive) files


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
# From v0.3.0 the record carries the revised manuscript's refits under their
# case ids (T₀-shift multivariate `GHEB`, thermal-only `GHPU`, culture+mesocosm
# `GCDU`). The multivariate files are the COMPLETE archival copies, EIV per-site
# latents included (~78–81 MB); the wheel bundles a 0.4 MB latent-stripped copy
# of the default pair, so most users never need these downloads.
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
    # WOA23-derived gridded ocean properties ("ocean_prop_ds" in the SI
    # preprocessing notebooks). Unlike the other three entries this one is
    # also used at inference time — by predict_T_from_proxyObs(site_lat=,
    # site_lon=) — not only to re-run the SI notebooks from scratch, so it
    # has its own download_ocean_properties() convenience wrapper below.
    "ocean_prop_ds": {
        "filename": "ds06_calculated_ocean_properties.nc",
        "size_mb": 20,
    },
}


# ─── Public API ───────────────────────────────────────────────────────────────

def download_all(
    cache_dir: Optional[Path | str] = None,
    data_dir: Optional[Path | str] = None,
    force: bool = False,
) -> None:
    """Download everything from Zenodo: forward posteriors + training data.

    Files are downloaded individually; already-cached files are skipped unless
    *force=True*.  Total download is ~490 MB (dominated by the six full EIV
    multivariate posteriors at ~78–81 MB each).

    Parameters
    ----------
    cache_dir : Path or str, optional
        Destination for ``.nc`` posteriors.  Defaults to the standard
        posterior cache directory.
    data_dir : Path or str, optional
        Destination for training data files.  Defaults to ``data/spreadsheets/``.
    force : bool
        Re-download files that already exist locally.
    """
    download_posteriors(cache_dir=cache_dir, force=force)
    download_training_data(dest_dir=data_dir, force=force)


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
    Download only the univariate SST posterior (~0.3 MB):

    >>> download_posteriors(["gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3"])
    """
    # By default download only the current-record posteriors; superseded
    # entries pinned to an older record version must be asked for by name.
    targets = names if names is not None else [
        k for k, v in POSTERIOR_REGISTRY.items() if "record" not in v
    ]
    dest_dir = Path(cache_dir) if cache_dir else POSTERIOR_CACHE_DIR
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
    Case-id aliases onto the registry's legacy keys.

    Two names refer to one file and both must work. The **key** is what a user
    asks for, and case ids are canonical from the resubmission on. The
    **filename** is what exists on the published Zenodo record, which is a
    frozen DOI carrying the legacy long names -- so it cannot change until a
    new deposit is made, and inventing a case-named URL now would 404.

    Built rather than hand-listed so it cannot fall out of step with the
    registry, and failures are silent because an alias is a convenience: a
    posterior this naming scheme cannot classify simply keeps its legacy key.
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

    The Zenodo record is a **flat** namespace -- it has to be, a DOI deposit has
    no subdirectories -- but the local cache is organised by case directory. So
    a registry key that is a case id is unpacked into ``<case>/<case>.fwd.nc``,
    giving one uniform local layout no matter whether a posterior was sampled
    here or downloaded. Legacy long-name keys (the v0.2.0 record's files) stay
    flat.
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
    uncertainty field used in the EIV calibration, and the WOA23-derived
    ``ocean_prop_ds`` gridded ocean properties.  The CSVs and the CMEMS field
    are needed only to re-run the SI preprocessing and calibration notebooks
    from scratch and are NOT required for inverse temperature
    reconstructions — use :func:`download_posteriors` for that.
    ``ocean_prop_ds`` is the exception: it is also used at inference time by
    :func:`~TEXAS.predict.predict_T_from_proxyObs` for the optional
    ``site_lat``/``site_lon`` NO₃ lookup — see :func:`download_ocean_properties`
    to fetch just that one file.

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
    dest = Path(dest_dir) if dest_dir else SPREADSHEETS_DIR
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
        _download_file(_file_url(entry["filename"]), out, entry["size_mb"], force=force)
        paths.append(out)

    return paths


def download_ocean_properties(
    dest_dir: Optional[Path | str] = None,
    force: bool = False,
) -> Path:
    """Download the WOA23-derived ``ocean_prop_ds`` field from Zenodo.

    This is the single file most users need for the ``site_lat``/``site_lon``
    NO₃ lookup in :func:`~TEXAS.predict.predict_T_from_proxyObs` — a ~20 MB
    gridded ``(lat, lon)`` dataset of thermocline-depth-integrated WOA23
    nitrate, previously only produced by running ``SI_code00_PreProcessing``
    locally. Downloading just this entry (rather than the full
    :func:`download_training_data`, which also fetches the ~17 MB of
    training CSVs and the CMEMS field) is why this has its own function.

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
    dest = Path(dest_dir) if dest_dir else SPREADSHEETS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    entry = TRAINING_DATA_REGISTRY["ocean_prop_ds"]
    out = dest / entry["filename"]
    _download_file(_file_url(entry["filename"]), out, entry["size_mb"], force=force)
    return out
