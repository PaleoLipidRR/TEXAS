# TEXAS/utils/download.py
"""
Utilities for downloading pre-computed forward calibration posteriors.

Posteriors are hosted on Zenodo alongside the paper.  Update ZENODO_RECORD_ID
once the Zenodo record is published (before paper submission).

Usage
-----
>>> import TEXAS
>>> TEXAS.download_posteriors()          # fetch all standard posteriors
>>> TEXAS.download_posterior("gen_logi_fixed_hier_crtp_multiv_SST")   # single file
"""

from __future__ import annotations

import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List

from .paths import POSTERIOR_CACHE_DIR

# ─── Zenodo config ────────────────────────────────────────────────────────────
# Replace with the real Zenodo record ID once the record is published.
ZENODO_RECORD_ID: Optional[str] = None   # e.g., "1234567"

def _zenodo_url(filename: str) -> Optional[str]:
    if ZENODO_RECORD_ID is None:
        return None
    return f"https://zenodo.org/record/{ZENODO_RECORD_ID}/files/{filename}?download=1"


# ─── Registry of standard posteriors ─────────────────────────────────────────
# Maps the posterior name (without .nc) to its Zenodo filename.
# Add entries here as new standard posteriors are produced.
POSTERIOR_REGISTRY: dict[str, str] = {
    "gen_logi_fixed_hier_crtp_multiv_SST":       "gen_logi_fixed_hier_crtp_multiv_SST.nc",
    "gen_logi_fixed_hier_crtp_multiv_thermoT":   "gen_logi_fixed_hier_crtp_multiv_thermoT.nc",
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
