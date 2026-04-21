# TEXAS/utils/download.py
"""
Utilities for downloading data from the TEXAS Zenodo data record.

The Zenodo data record contains a single ZIP archive
(``texas-psm-zenodo-v0.1.5.zip``) with the following internal layout::

    texas-psm-zenodo/
      posteriors/canonical/   ← recommended RI₀₋₃ posteriors
      posteriors/reference/   ← RI₀₋₄ posteriors (comparison only)
      data/                   ← training CSVs (needed for SI notebooks)

Usage
-----
>>> import TEXAS
>>> TEXAS.download_all()               # recommended: everything at once
>>> TEXAS.download_posteriors()        # forward calibration posteriors only
>>> TEXAS.download_training_data()     # training CSVs only (SI notebooks)

Docker/devcontainer users: run on the host machine — the container
bind-mounts ``data/`` automatically.
"""

from __future__ import annotations

import io
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import List, Optional

from .paths import POSTERIOR_CACHE_DIR, SPREADSHEETS_DIR

# ─── Zenodo config ────────────────────────────────────────────────────────────
ZENODO_RECORD_ID: str = "19666745"
ZENODO_ZIP_FILENAME: str = "texas-psm-zenodo-v0.1.5.zip"
ZENODO_ZIP_ROOT: str = "texas-psm-zenodo"   # folder inside the ZIP

_ZIP_URL = (
    f"https://zenodo.org/records/{ZENODO_RECORD_ID}/files/"
    f"{ZENODO_ZIP_FILENAME}?download=1"
)


def _download_zip(dest: Path, force: bool = False) -> Path:
    """Download the Zenodo ZIP to *dest*, skipping if already present."""
    if dest.exists() and not force:
        # Validate the cached file is actually a ZIP before trusting it
        if zipfile.is_zipfile(dest):
            return dest
        dest.unlink()  # stale/corrupt file — re-download below

    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {ZENODO_ZIP_FILENAME} from Zenodo (~560 MB) …")
    try:
        with urllib.request.urlopen(_ZIP_URL) as resp:
            status = resp.status
            if status != 200:
                raise urllib.error.URLError(
                    f"Zenodo returned HTTP {status} for {_ZIP_URL!r}.\n"
                    "  The data record may not be published yet — "
                    "contact the authors or check https://doi.org/10.5281/zenodo."
                    f"{ZENODO_RECORD_ID}"
                )
            data = resp.read()
    except urllib.error.URLError:
        raise
    except Exception as e:
        raise urllib.error.URLError(f"ZIP download failed: {e}") from e

    dest.write_bytes(data)
    if not zipfile.is_zipfile(dest):
        dest.unlink()
        raise ValueError(
            f"Downloaded file from Zenodo is not a valid ZIP.\n"
            f"  URL     : {_ZIP_URL}\n"
            f"  The Zenodo record ({ZENODO_RECORD_ID}) may not be published yet or "
            "the file name may have changed."
        )
    print(f"ZIP saved to {dest}")
    return dest


def _extract_member(zf: zipfile.ZipFile, zip_rel_path: str, dest: Path) -> Path:
    """Extract one member (path inside ZIP relative to ZENODO_ZIP_ROOT) to *dest*."""
    member = f"{ZENODO_ZIP_ROOT}/{zip_rel_path}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member) as src, open(dest, "wb") as out:
        out.write(src.read())
    return dest


# ─── Registry of standard posteriors ─────────────────────────────────────────
# Maps posterior name (no .nc) → path inside ZIP (relative to ZENODO_ZIP_ROOT).
POSTERIOR_REGISTRY: dict[str, str] = {
    # ── CANONICAL (scaledRI_cren3, RI₀₋₃) — RECOMMENDED ─────────────────
    "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3":
        "posteriors/canonical/gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc",
    "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3":
        "posteriors/canonical/gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3.nc",
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3":
        "posteriors/canonical/gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc",
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3":
        "posteriors/canonical/gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3.nc",

    # ── REFERENCE (scaledRI, RI₀₋₄) — kept for comparison only ──────────
    "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI":
        "posteriors/reference/gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI.nc",
    "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI":
        "posteriors/reference/gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI.nc",
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI":
        "posteriors/reference/gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI.nc",
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI":
        "posteriors/reference/gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI.nc",
}

# ─── Training data registry ───────────────────────────────────────────────────
# Maps local name → path inside ZIP (relative to ZENODO_ZIP_ROOT).
TRAINING_DATA_REGISTRY: dict[str, str] = {
    "combined_coretop_culture_mesocosm":
        "data/combined_coretop_culture_mesocosm_rev20260210.csv",
    "ds_gridded_screened_global":
        "data/ds_gridded_screened_global_compilation_finalized.csv",
}


# ─── Public API ───────────────────────────────────────────────────────────────

def download_all(
    cache_dir: Optional[Path | str] = None,
    data_dir: Optional[Path | str] = None,
    force: bool = False,
) -> None:
    """Download everything from Zenodo: posteriors + training CSVs.

    This is the recommended one-shot function for new users.  The ZIP
    (~560 MB) is downloaded once and extracted; subsequent calls are skipped
    unless *force=True*.

    Parameters
    ----------
    cache_dir : Path or str, optional
        Destination for ``.nc`` posteriors.  Defaults to the standard
        posterior cache directory.
    data_dir : Path or str, optional
        Destination for training CSVs.  Defaults to ``data/spreadsheets/``.
    force : bool
        Re-download and re-extract even if files already exist locally.
    """
    download_posteriors(cache_dir=cache_dir, force=force)
    download_training_data(dest_dir=data_dir, force=force)


def download_posteriors(
    names: Optional[List[str]] = None,
    cache_dir: Optional[Path | str] = None,
    force: bool = False,
) -> List[Path]:
    """Download forward calibration posteriors from Zenodo.

    Downloads the Zenodo ZIP once (cached in a temp directory for the
    session) and extracts only the requested ``.nc`` files.

    Parameters
    ----------
    names : list of str, optional
        Subset of POSTERIOR_REGISTRY keys to extract.  Downloads all
        canonical and reference posteriors when omitted.
    cache_dir : Path or str, optional
        Destination directory.  Defaults to the standard posterior cache.
    force : bool
        Re-download and overwrite files that already exist locally.

    Returns
    -------
    list of Path
        Local paths of the extracted ``.nc`` files.
    """
    targets = names if names is not None else list(POSTERIOR_REGISTRY)
    dest_dir = Path(cache_dir) if cache_dir else POSTERIOR_CACHE_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Check which files are already present
    missing = [n for n in targets if not (dest_dir / f"{n}.nc").exists() or force]
    if not missing:
        print("All posteriors already cached.")
        return [dest_dir / f"{n}.nc" for n in targets]

    zip_path = Path(tempfile.gettempdir()) / ZENODO_ZIP_FILENAME
    _download_zip(zip_path, force=force)

    paths = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in targets:
            dest = dest_dir / f"{name}.nc"
            if dest.exists() and not force:
                print(f"Already cached: {dest}")
                paths.append(dest)
                continue
            if name not in POSTERIOR_REGISTRY:
                available = "\n  ".join(POSTERIOR_REGISTRY)
                raise KeyError(
                    f"'{name}' is not in POSTERIOR_REGISTRY.\n"
                    f"Available posteriors:\n  {available}"
                )
            _extract_member(zf, POSTERIOR_REGISTRY[name], dest)
            print(f"Extracted → {dest}")
            paths.append(dest)

    return paths


def download_training_data(
    dest_dir: Optional[Path | str] = None,
    force: bool = False,
) -> List[Path]:
    """Download the GDGT training CSVs from Zenodo.

    These CSVs are needed only to re-run the SI preprocessing and
    calibration notebooks from scratch.  They are NOT required for inverse
    temperature reconstructions — use :func:`download_posteriors` for that.

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
        Local paths of the downloaded CSV files.
    """
    dest = Path(dest_dir) if dest_dir else SPREADSHEETS_DIR
    dest.mkdir(parents=True, exist_ok=True)

    missing = [
        fn for fn in TRAINING_DATA_REGISTRY.values()
        if not (dest / Path(fn).name).exists() or force
    ]
    if not missing:
        print("All training CSVs already present.")
        return [dest / Path(fn).name for fn in TRAINING_DATA_REGISTRY.values()]

    zip_path = Path(tempfile.gettempdir()) / ZENODO_ZIP_FILENAME
    _download_zip(zip_path, force=force)

    paths = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name, zip_rel in TRAINING_DATA_REGISTRY.items():
            out = dest / Path(zip_rel).name
            if out.exists() and not force:
                print(f"Already present: {out}")
                paths.append(out)
                continue
            _extract_member(zf, zip_rel, out)
            print(f"Extracted → {out}")
            paths.append(out)

    return paths
