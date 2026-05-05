#!/usr/bin/env python3
"""
Upload review_archive_v0.2.0/ to Zenodo as a new draft version.

Usage
-----
    ZENODO_TOKEN=<your_token> python scripts/zenodo_upload.py [--publish]

The script:
  1. Creates a new draft version from the existing data record (RECORD_ID below)
  2. Deletes files carried over from the previous version
  3. Uploads all files in the layout described in FILE_PLAN
  4. Updates the version metadata to "0.2.0"
  5. Leaves the record as a DRAFT (add --publish to publish immediately)

Get a personal token at: https://zenodo.org/account/settings/applications/tokens/new/
Required scopes: deposit:write, deposit:actions
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import requests

# ─── Configuration ─────────────────────────────────────────────────────────────
RECORD_ID = "19666745"          # existing Zenodo data record
ZENODO_BASE = "https://zenodo.org/api"
ARCHIVE_DIR = Path(__file__).parent.parent / "review_archive_v0.2.0"
VERSION = "0.2.0"

# Files to upload as individual flat files (filename on Zenodo → local path)
# These filenames must match POSTERIOR_REGISTRY and TRAINING_DATA_REGISTRY in download.py.
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


def create_new_version(session: requests.Session) -> dict:
    """Fork the existing record into a new draft version."""
    url = f"{ZENODO_BASE}/deposit/depositions/{RECORD_ID}/actions/newversion"
    r = session.post(url)
    r.raise_for_status()
    # The response links to the latest draft — fetch it
    draft_url = r.json()["links"]["latest_draft"]
    r2 = session.get(draft_url)
    r2.raise_for_status()
    draft = r2.json()
    print(f"New draft created: id={draft['id']}  bucket={draft['links']['bucket']}")
    return draft


def delete_existing_files(session: requests.Session, draft: dict) -> None:
    """Remove all files carried over from the previous version."""
    files = draft.get("files", [])
    if not files:
        print("No existing files to delete.")
        return
    print(f"Deleting {len(files)} file(s) from previous version …")
    dep_id = draft["id"]
    for f in files:
        fid = f["id"]
        r = session.delete(f"{ZENODO_BASE}/deposit/depositions/{dep_id}/files/{fid}")
        r.raise_for_status()
        print(f"  deleted: {f['filename']}")


def upload_file(session: requests.Session, bucket_url: str, zenodo_name: str, local_path: Path) -> None:
    """Upload one file to the draft bucket."""
    size_str = _fmt_size(local_path)
    print(f"  uploading {zenodo_name} ({size_str}) …", end="", flush=True)
    url = f"{bucket_url}/{zenodo_name}"
    with local_path.open("rb") as fh:
        r = session.put(url, data=fh)
    r.raise_for_status()
    print(" done")


def build_invt_zip(tmp_path: Path) -> Path:
    """Bundle all invT posteriors into a ZIP and return its path."""
    import zipfile
    zip_path = tmp_path / INVT_ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for d in INVT_DIRS:
            for f in sorted(d.rglob("*.nc")):
                arcname = f"invT/{d.name}/{f.name}"
                zf.write(f, arcname)
    size_str = _fmt_size(zip_path)
    print(f"Built {INVT_ZIP_NAME} ({size_str})")
    return zip_path


def update_metadata(session: requests.Session, draft: dict) -> None:
    """Bump the version string in the draft metadata."""
    dep_id = draft["id"]
    meta = draft["metadata"].copy()
    meta["version"] = VERSION
    # Preserve publication_date if already set, otherwise use today
    if "publication_date" not in meta:
        from datetime import date
        meta["publication_date"] = date.today().isoformat()
    r = session.put(
        f"{ZENODO_BASE}/deposit/depositions/{dep_id}",
        json={"metadata": meta},
    )
    r.raise_for_status()
    print(f"Metadata updated: version → {VERSION}")


def publish_draft(session: requests.Session, draft: dict) -> str:
    """Publish the draft and return the DOI."""
    dep_id = draft["id"]
    r = session.post(f"{ZENODO_BASE}/deposit/depositions/{dep_id}/actions/publish")
    r.raise_for_status()
    doi = r.json()["doi"]
    print(f"Published! DOI: {doi}")
    return doi


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--publish", action="store_true", help="Publish the draft after uploading (default: leave as draft)")
    parser.add_argument("--token", default=os.environ.get("ZENODO_TOKEN"), help="Zenodo personal access token (or set ZENODO_TOKEN env var)")
    args = parser.parse_args()

    if not args.token:
        sys.exit(
            "ERROR: Zenodo token required.\n"
            "  Set ZENODO_TOKEN env var or pass --token <token>\n"
            "  Get a token at: https://zenodo.org/account/settings/applications/tokens/new/\n"
            "  Required scopes: deposit:write, deposit:actions"
        )

    # Validate all local files exist before touching Zenodo
    missing = [name for name, path in INDIVIDUAL_FILES.items() if not path.exists()]
    if missing:
        sys.exit(f"ERROR: local files not found:\n" + "\n".join(f"  {m}" for m in missing))

    session = _session(args.token)

    print(f"\n── Step 1: create new draft version from record {RECORD_ID} ──")
    draft = create_new_version(session)

    print(f"\n── Step 2: delete files from previous version ──")
    delete_existing_files(session, draft)

    bucket_url = draft["links"]["bucket"]

    print(f"\n── Step 3: upload individual files ──")
    for zenodo_name, local_path in INDIVIDUAL_FILES.items():
        upload_file(session, bucket_url, zenodo_name, local_path)

    print(f"\n── Step 4: bundle and upload invT posteriors ──")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = build_invt_zip(Path(tmp))
        upload_file(session, bucket_url, INVT_ZIP_NAME, zip_path)

    print(f"\n── Step 5: update metadata ──")
    # Re-fetch draft to get updated state after file uploads
    draft_url = f"{ZENODO_BASE}/deposit/depositions/{draft['id']}"
    draft = session.get(draft_url).json()
    update_metadata(session, draft)

    if args.publish:
        print(f"\n── Step 6: publish ──")
        doi = publish_draft(session, draft)
        print(f"\nDone! Record: https://zenodo.org/records/{draft['id']}")
        print(f"DOI: {doi}")
    else:
        print(f"\nDraft saved (not published).")
        print(f"Review at: https://zenodo.org/deposit/{draft['id']}")
        print(f"When ready: python scripts/zenodo_upload.py --publish")
        print(f"\nAfter publishing, update ZENODO_RECORD_ID in:")
        print(f"  src/TEXAS/utils/download.py  (if the record ID changed)")
        print(f"  CITATION.cff                 (doi field)")


if __name__ == "__main__":
    main()
