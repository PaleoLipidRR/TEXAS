# TEXAS/utils/download.py
"""
Utilities for downloading data from the TEXAS Zenodo data record.

Files are downloaded individually from Zenodo so you only fetch what you need.
The two full multivariate (EIV) posteriors are ~78 MB each; all other files are
< 2 MB.  A size notice is printed before any download ≥ 5 MB.

Usage
-----
>>> import TEXAS
>>> TEXAS.download_all()               # everything: posteriors + training data
>>> TEXAS.download_posteriors()        # forward calibration posteriors only
>>> TEXAS.download_training_data()     # training CSVs + NO₃ field only

Download a specific posterior:
>>> TEXAS.download_posteriors(["gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3"])

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
ZENODO_RECORD_ID: str = "20032542"

_ZENODO_BASE = f"https://zenodo.org/records/{ZENODO_RECORD_ID}/files"


def _file_url(filename: str) -> str:
    return f"{_ZENODO_BASE}/{filename}?download=1"


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
# filename is the flat name on the Zenodo record (no subdirectory).
POSTERIOR_REGISTRY: dict[str, dict] = {
    "gen_logi_fixed_culmeso_cultureT_scaledRI_cren3": {
        "filename": "gen_logi_fixed_culmeso_cultureT_scaledRI_cren3.nc",
        "size_mb": 0.2,
    },
    "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3": {
        "filename": "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc",
        "size_mb": 0.3,
    },
    "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3": {
        "filename": "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3.nc",
        "size_mb": 0.3,
    },
    # EIV multivariate posteriors — large due to per-site latent variables (~1500 coretop sites)
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3": {
        "filename": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc",
        "size_mb": 78,
    },
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3": {
        "filename": "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3.nc",
        "size_mb": 78,
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
}


# ─── Public API ───────────────────────────────────────────────────────────────

def download_all(
    cache_dir: Optional[Path | str] = None,
    data_dir: Optional[Path | str] = None,
    force: bool = False,
) -> None:
    """Download everything from Zenodo: forward posteriors + training data.

    Files are downloaded individually; already-cached files are skipped unless
    *force=True*.  Total download is ~158 MB (dominated by the two EIV
    multivariate posteriors at ~78 MB each).

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
        Subset of ``POSTERIOR_REGISTRY`` keys to download.  Downloads all
        five posteriors when omitted (~158 MB total; the two EIV multivariate
        posteriors are ~78 MB each — pass ``names=`` to download only the
        univariate ones if you don't need the EIV model).
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
    targets = names if names is not None else list(POSTERIOR_REGISTRY)
    dest_dir = Path(cache_dir) if cache_dir else POSTERIOR_CACHE_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

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
        _download_file(_file_url(entry["filename"]), dest, entry["size_mb"], force=force)
        paths.append(dest)

    return paths


def _local_dest(dest_dir: Path, name: str) -> Path:
    """
    Where a Zenodo posterior lands locally.

    The Zenodo record is a **flat** namespace -- it has to be, a DOI deposit has
    no subdirectories -- but the local cache is organised by case directory. So
    a registry key that is a case id is unpacked into ``<case>/<case>.fwd.nc``,
    giving one uniform local layout no matter whether a posterior was sampled
    here or downloaded. Legacy long-name keys stay flat, which is what the
    currently published record 10.5281/zenodo.20032542 uses.
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

    Downloads the coretop/culture/mesocosm training CSVs and the CMEMS
    NO₃ uncertainty field used in the EIV calibration.  These are needed
    only to re-run the SI preprocessing and calibration notebooks from
    scratch; they are NOT required for inverse temperature reconstructions —
    use :func:`download_posteriors` for that.

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
