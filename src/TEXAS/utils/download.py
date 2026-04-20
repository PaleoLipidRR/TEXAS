# TEXAS/utils/download.py
"""
Utilities for downloading data from the TEXAS Zenodo data record.

Both the pre-computed forward posteriors and the GDGT training CSVs live in
the same Zenodo data record.  Set ZENODO_RECORD_ID once the record is
published, then all download functions will resolve automatically.

Data flow
---------
Everything lands in the data/ folder that the notebooks and package already
expect.  Users never have to think about paths:

  Zenodo data record
    └── posteriors (.nc)   →  download_posteriors()   →  data/cache/TEXAS_posterior_cache/
    └── training CSVs      →  download_training_data() →  data/spreadsheets/

Docker/devcontainer users: the container bind-mounts data/ from the host, so
files downloaded on the host are automatically visible inside the container.

Usage
-----
>>> import TEXAS
>>> TEXAS.download_posteriors()       # forward calibration posteriors
>>> TEXAS.download_training_data()    # GDGT training CSVs (needed for SI notebooks)
"""

from __future__ import annotations

import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List

from .paths import POSTERIOR_CACHE_DIR, SPREADSHEETS_DIR

# ─── Zenodo config ────────────────────────────────────────────────────────────
# Replace with the real Zenodo record ID once the record is published.
ZENODO_RECORD_ID: Optional[str] = "19666745"

def _zenodo_url(filename: str) -> Optional[str]:
    if ZENODO_RECORD_ID is None:
        return None
    return f"https://zenodo.org/record/{ZENODO_RECORD_ID}/files/{filename}?download=1"


# ─── Registry of standard posteriors ─────────────────────────────────────────
# Maps the posterior name (without .nc) to its Zenodo filename.
#
# Two canonical model families, each in two proxy variants:
#
#   scaledRI_cren3  (RI₀₋₃, RECOMMENDED) — Ring Index computed from GDGT-0
#                   through GDGT-cren only (excludes GDGT-cren').  This is
#                   the final calibration used in the manuscript.
#
#   scaledRI        (RI₀₋₄, reference) — Ring Index including GDGT-cren'
#                   (GDGT-0 through GDGT-cren').  Retained on Zenodo for
#                   comparison against earlier studies; not the primary model.
#
# Within each proxy variant, two model families:
#
#   univ  — temperature-only (no non-thermal predictors).
#           Use when GDGT-2/3 and/or NO₃ are unavailable.
#
#   eiv   — multivariate error-in-variables with G₂/₃ + NO₃ corrections.
#           Preferred model for sites with known oceanographic context.
#           Pass no3=<array> from ocean_prop_ds["no3_sf2tc_avg"], or
#           pass no3=10.0 (any value above the 1.0 µmol/L cutoff) to
#           disable the NO₃ term while keeping the G₂/₃ correction.
#
# Filenames on Zenodo carry no date suffix (clean, stable names).
POSTERIOR_REGISTRY: dict[str, str] = {
    # ── CANONICAL (scaledRI_cren3, RI₀₋₃) ───────────────────────────────
    # Temperature-only
    "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3":
        "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc",
    "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3":
        "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3.nc",
    # Multivariate EIV (G₂/₃ + NO₃, no₃_cutoff = 1.0 µmol/L)
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3":
        "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc",
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3":
        "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3.nc",

    # ── REFERENCE (scaledRI, RI₀₋₄) — kept for comparison only ──────────
    # Temperature-only
    "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI":
        "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI.nc",
    "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI":
        "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI.nc",
    # Multivariate EIV (G₂/₃ + NO₃, no₃_cutoff = 1.0 µmol/L)
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI":
        "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI.nc",
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI":
        "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI.nc",
}


# ─── Public API ───────────────────────────────────────────────────────────────

def download_posterior(
    name: str,
    cache_dir: Optional[Path | str] = None,
    force: bool = False,
) -> Path:
    """
    Download a single forward calibration posterior from Zenodo.

    Parameters
    ----------
    name : str
        Posterior name without ``.nc`` extension (must be in POSTERIOR_REGISTRY).
    cache_dir : Path or str, optional
        Destination directory.  Defaults to the standard posterior cache
        (``~/.texas/data/cache/TEXAS_posterior_cache/`` when pip-installed).
    force : bool
        Re-download even if the file already exists locally.

    Returns
    -------
    Path
        Local path of the downloaded ``.nc`` file.

    Raises
    ------
    KeyError
        If *name* is not in POSTERIOR_REGISTRY.
    RuntimeError
        If the Zenodo record ID has not been set yet (pre-publication).
    urllib.error.URLError
        If the download fails due to a network error.
    """
    if name not in POSTERIOR_REGISTRY:
        available = "\n  ".join(POSTERIOR_REGISTRY)
        raise KeyError(
            f"'{name}' is not in POSTERIOR_REGISTRY.\n"
            f"Available posteriors:\n  {available}"
        )

    dest_dir = Path(cache_dir) if cache_dir else POSTERIOR_CACHE_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{name}.nc"

    if dest.exists() and not force:
        print(f"Already cached: {dest}")
        return dest

    url = _zenodo_url(POSTERIOR_REGISTRY[name])
    if url is None:
        raise RuntimeError(
            f"Pre-computed posteriors will be available on Zenodo upon paper submission.\n"
            f"Until then, run forward calibration with get_posterior() to generate '{name}.nc',\n"
            f"or pass a loaded xr.Dataset directly via the fwd_posterior= argument."
        )

    print(f"Downloading {name}.nc from Zenodo …")
    try:
        urllib.request.urlretrieve(url, dest)
    except urllib.error.URLError as e:
        dest.unlink(missing_ok=True)   # remove partial download
        raise urllib.error.URLError(f"Download failed for '{name}': {e}") from e

    print(f"Saved to {dest}")
    return dest


def download_posteriors(
    names: Optional[List[str]] = None,
    cache_dir: Optional[Path | str] = None,
    force: bool = False,
) -> List[Path]:
    """
    Download all (or a subset of) standard forward calibration posteriors.

    Parameters
    ----------
    names : list of str, optional
        Subset of POSTERIOR_REGISTRY keys to download.  Downloads everything
        in the registry when omitted.
    cache_dir : Path or str, optional
        Destination directory (see :func:`download_posterior`).
    force : bool
        Re-download files that already exist locally.

    Returns
    -------
    list of Path
        Local paths of all downloaded ``.nc`` files.
    """
    targets = names if names is not None else list(POSTERIOR_REGISTRY)
    paths = []
    for name in targets:
        paths.append(download_posterior(name, cache_dir=cache_dir, force=force))
    return paths


# ─── Training data registry ───────────────────────────────────────────────────
# Maps a short local name to the filename on Zenodo.
# These CSVs are needed only to re-run the SI notebooks from scratch
# (forward calibration / preprocessing).  They are NOT needed for running
# inverse temperature reconstructions with pre-computed posteriors.
TRAINING_DATA_REGISTRY: dict[str, str] = {
    "combined_coretop_culture_mesocosm": "combined_coretop_culture_mesocosm_rev20260210.csv",
    "ds_gridded_screened_global":        "ds_gridded_screened_global_compilation_finalized.csv",
}


def download_training_data(
    dest_dir: Optional[Path | str] = None,
    force: bool = False,
) -> List[Path]:
    """
    Download the GDGT training CSVs from Zenodo into data/spreadsheets/.

    These files are needed to re-run the SI preprocessing and calibration
    notebooks from scratch.  They are NOT required for inverse temperature
    reconstructions — use :func:`download_posteriors` for that instead.

    The files land in ``data/spreadsheets/`` inside the repo (or
    ``~/.texas/data/spreadsheets/`` when pip-installed outside a git checkout).
    Docker/devcontainer users: run this on the host machine before starting
    the container — the container bind-mounts ``data/`` automatically.

    Parameters
    ----------
    dest_dir : Path or str, optional
        Override the destination directory.  Defaults to
        ``SPREADSHEETS_DIR`` (resolved from the repo root or
        the ``TEXAS_DATA_DIR`` environment variable).
    force : bool
        Re-download files that already exist locally.

    Returns
    -------
    list of Path
        Local paths of the downloaded CSV files.

    Raises
    ------
    RuntimeError
        If the Zenodo record ID has not been set yet (pre-publication).
    """
    dest = Path(dest_dir) if dest_dir else SPREADSHEETS_DIR
    dest.mkdir(parents=True, exist_ok=True)

    paths = []
    for name, zenodo_filename in TRAINING_DATA_REGISTRY.items():
        out = dest / zenodo_filename
        if out.exists() and not force:
            print(f"Already present: {out}")
            paths.append(out)
            continue

        url = _zenodo_url(zenodo_filename)
        if url is None:
            raise RuntimeError(
                "Training data will be available on Zenodo upon paper submission.\n"
                "Until then, obtain the CSVs from the corresponding author or\n"
                "regenerate them by running SI_code1_PreProcessing_finalized.ipynb."
            )

        print(f"Downloading {zenodo_filename} from Zenodo …")
        try:
            urllib.request.urlretrieve(url, out)
        except urllib.error.URLError as e:
            out.unlink(missing_ok=True)
            raise urllib.error.URLError(f"Download failed for '{zenodo_filename}': {e}") from e

        print(f"Saved to {out}")
        paths.append(out)

    return paths
