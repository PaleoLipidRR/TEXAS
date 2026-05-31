#!/usr/bin/env python3
"""
Upload review_archive_v0.2.0/ to Zenodo as a new draft version.

Usage
-----
    ZENODO_TOKEN=<your_token> python scripts/zenodo_upload.py [--publish]

The script:
  1. Creates a new draft version from the existing data record (RECORD_ID below)
  2. Deletes files inherited from the previous version
  3. Uploads all files in INDIVIDUAL_FILES + a bundled invT ZIP
  4. Updates the version metadata to "0.2.0"
  5. Leaves the record as a DRAFT (add --publish to publish immediately)

Uses the Zenodo InvenioRDM REST API (/api/records/).
Get a personal token at: https://zenodo.org/account/settings/applications/tokens/new/
Required scopes: deposit:write, deposit:actions
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

# ─── Configuration ─────────────────────────────────────────────────────────────
RECORD_ID = "20032542"          # Zenodo data record (v0.2.0, doi:10.5281/zenodo.20032542)
ZENODO_BASE = "https://zenodo.org/api"
ARCHIVE_DIR = Path(__file__).parent.parent / "review_archive_v0.2.0"
VERSION = "0.2.0"

# Files to upload as individual flat files (filename on Zenodo → local path).
# Filenames must match POSTERIOR_REGISTRY and TRAINING_DATA_REGISTRY in download.py.
INDIVIDUAL_FILES: dict[str, Path] = {
    # ── Forward calibration posteriors ──────────────────────────────────────
    "gen_logi_fixed_culmeso_cultureT_scaledRI_cren3.nc":
        ARCHIVE_DIR / "posteriors/forward/gen_logi_fixed_culmeso_cultureT_scaledRI_cren3.nc",
    "gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc":
        ARCHIVE_DIR / "posteriors/forward/gen_logi_fixed_hier_crtp_univ_priorApprox_SST_scaledRI_cren3.nc",
    "gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3.nc":
        ARCHIVE_DIR / "posteriors/forward/gen_logi_fixed_hier_crtp_univ_priorApprox_thermoT_scaledRI_cren3.nc",
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc":
        ARCHIVE_DIR / "posteriors/forward/gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_SST_gdgt23ratio_no3_1.0_scaledRI_cren3.nc",
    "gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3.nc":
        ARCHIVE_DIR / "posteriors/forward/gen_logi_fixed_hier_crtp_multiv_priorApprox_eiv_thermoT_gdgt23ratio_no3_1.0_scaledRI_cren3.nc",
    # ── Training data ────────────────────────────────────────────────────────
    "combined_coretop_culture_mesocosm_rev20260210.csv":
        ARCHIVE_DIR / "data/combined_coretop_culture_mesocosm_rev20260210.csv",
    "ds_gridded_screened_global_compilation_finalized.csv":
        ARCHIVE_DIR / "data/ds_gridded_screened_global_compilation_finalized.csv",
    "cmems_no3_uncertainty_field.nc":
        ARCHIVE_DIR / "data/cmems_no3_uncertainty_field.nc",
    # ── README ───────────────────────────────────────────────────────────────
    "README.md":
        ARCHIVE_DIR / "README.md",
}

# InvT posteriors bundled as a single ZIP for SI reproducibility
INVT_ZIP_NAME = "texas-psm-invT-posteriors-v0.2.0.zip"
INVT_DIRS = [
    ARCHIVE_DIR / "posteriors/invT/coretop",
    ARCHIVE_DIR / "posteriors/invT/paleo",
]


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _fmt_size(path: Path) -> str:
    mb = path.stat().st_size / 1_048_576
    return f"{mb:.1f} MB" if mb >= 1 else f"{path.stat().st_size / 1024:.0f} KB"


def _check(r: requests.Response, context: str) -> None:
    if not r.ok:
        sys.exit(f"ERROR during {context}: HTTP {r.status_code}\n  {r.text}")


def create_new_version(session: requests.Session) -> dict:
    """Create a new draft version via the InvenioRDM records API."""
    r = session.post(f"{ZENODO_BASE}/records/{RECORD_ID}/versions")
    _check(r, "create new version")
    draft = r.json()
    print(f"  New draft version created: id={draft['id']}")
    return draft


def delete_existing_files(session: requests.Session, draft_id: str) -> None:
    """Remove all files inherited from the previous version."""
    r = session.get(f"{ZENODO_BASE}/records/{draft_id}/draft/files")
    _check(r, "list draft files")
    entries = r.json().get("entries", [])
    if not entries:
        print("  No inherited files to delete.")
        return
    print(f"  Deleting {len(entries)} inherited file(s) …")
    for f in entries:
        fname = f["key"]
        rd = session.delete(f"{ZENODO_BASE}/records/{draft_id}/draft/files/{fname}")
        _check(rd, f"delete {fname}")
        print(f"    deleted: {fname}")


def upload_file(session: requests.Session, draft_id: str, zenodo_name: str, local_path: Path) -> None:
    """Upload one file using the InvenioRDM 3-step flow: init → content → commit."""
    size_str = _fmt_size(local_path)
    print(f"  uploading {zenodo_name} ({size_str}) …", end="", flush=True)

    # 1. Initiate
    r = session.post(
        f"{ZENODO_BASE}/records/{draft_id}/draft/files",
        json=[{"key": zenodo_name}],
    )
    _check(r, f"initiate upload {zenodo_name}")

    # 2. Upload content
    with local_path.open("rb") as fh:
        r2 = session.put(
            f"{ZENODO_BASE}/records/{draft_id}/draft/files/{zenodo_name}/content",
            data=fh,
            headers={"Content-Type": "application/octet-stream"},
        )
    _check(r2, f"upload content {zenodo_name}")

    # 3. Commit
    r3 = session.post(f"{ZENODO_BASE}/records/{draft_id}/draft/files/{zenodo_name}/commit")
    _check(r3, f"commit {zenodo_name}")
    print(" done")


def build_invt_zip(tmp_path: Path) -> Path:
    """Bundle all invT posteriors into a ZIP and return its path."""
    zip_path = tmp_path / INVT_ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for d in INVT_DIRS:
            for f in sorted(d.rglob("*.nc")):
                arcname = f"invT/{d.name}/{f.name}"
                zf.write(f, arcname)
    print(f"  Built {INVT_ZIP_NAME} ({_fmt_size(zip_path)})")
    return zip_path


def update_metadata(session: requests.Session, draft_id: str) -> None:
    """Bump the version string in the draft metadata."""
    r = session.get(f"{ZENODO_BASE}/records/{draft_id}/draft")
    _check(r, "fetch draft metadata")
    meta = r.json().get("metadata", {}).copy()
    meta["version"] = VERSION
    r2 = session.put(
        f"{ZENODO_BASE}/records/{draft_id}/draft",
        json={"metadata": meta},
    )
    _check(r2, "update metadata")
    print(f"  version → {VERSION}")


def publish_draft(session: requests.Session, draft_id: str) -> str:
    """Publish the draft and return the DOI."""
    r = session.post(f"{ZENODO_BASE}/records/{draft_id}/draft/actions/publish")
    _check(r, "publish")
    result = r.json()
    doi = (
        result.get("doi")
        or result.get("pids", {}).get("doi", {}).get("identifier", "unknown")
    )
    print(f"  Published! DOI: {doi}")
    return doi


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--publish", action="store_true",
                        help="Publish the draft after uploading (default: leave as draft)")
    parser.add_argument("--token", default=os.environ.get("ZENODO_TOKEN"),
                        help="Zenodo personal access token (or set ZENODO_TOKEN env var)")
    args = parser.parse_args()

    if not args.token:
        sys.exit(
            "ERROR: Zenodo token required.\n"
            "  Set ZENODO_TOKEN env var or pass --token <token>\n"
            "  Get a token at: https://zenodo.org/account/settings/applications/tokens/new/\n"
            "  Required scopes: deposit:write, deposit:actions"
        )

    missing = [name for name, path in INDIVIDUAL_FILES.items() if not path.exists()]
    if missing:
        sys.exit("ERROR: local files not found:\n" + "\n".join(f"  {m}" for m in missing))

    session = _session(args.token)

    print(f"\n── Step 1: create new draft version from record {RECORD_ID} ──")
    draft = create_new_version(session)
    draft_id = str(draft["id"])

    print("\n── Step 2: delete inherited files ──")
    delete_existing_files(session, draft_id)

    print("\n── Step 3: upload individual files ──")
    for zenodo_name, local_path in INDIVIDUAL_FILES.items():
        upload_file(session, draft_id, zenodo_name, local_path)

    print("\n── Step 4: bundle and upload invT posteriors ──")
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = build_invt_zip(Path(tmp))
        upload_file(session, draft_id, INVT_ZIP_NAME, zip_path)

    print("\n── Step 5: update metadata ──")
    update_metadata(session, draft_id)

    if args.publish:
        print("\n── Step 6: publish ──")
        doi = publish_draft(session, draft_id)
        print(f"\nDone! Record: https://zenodo.org/records/{draft_id}")
        print(f"DOI: {doi}")
    else:
        print("\nDraft saved (not published).")
        print(f"Review at: https://zenodo.org/uploads/{draft_id}")
        print("\nWhen ready to publish:")
        print("  ZENODO_TOKEN=<token> python scripts/zenodo_upload.py --publish")
        print("\nAfter publishing, update:")
        print("  CITATION.cff  →  doi field")
        print("  src/TEXAS/utils/download.py  →  ZENODO_RECORD_ID (if the ID changed)")


if __name__ == "__main__":
    main()
