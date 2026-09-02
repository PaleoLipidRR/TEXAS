#!/usr/bin/env python3
"""Add ds06_calculated_ocean_properties.nc to a NEW version of the Zenodo record.

Zenodo files are immutable once a version is published -- you cannot add a
file to ZENODO_RECORD_ID in download.py directly. What you *can* do is create
a new version: unlike zenodo_upload.py (which deletes every inherited file
and re-uploads the whole ~500 MB archive from scratch), a new version starts
as a COPY of the current version's files, so adding one file means uploading
only that one file and publishing -- everything else stays exactly as it was
published before.

Usage
-----
    ZENODO_TOKEN=<token> python scripts/zenodo_add_ocean_prop_ds.py
        # creates the draft, uploads the file, leaves it unpublished

    ZENODO_TOKEN=<token> python scripts/zenodo_add_ocean_prop_ds.py --publish
        # publishes the existing draft (pass --draft-id if it's not the one
        # already pinned in download.py)

After publishing, update ZENODO_RECORD_ID in src/TEXAS/utils/download.py to
the new draft's id -- the concept DOI always resolves to the latest version,
but download.py builds direct file URLs from the pinned numeric record id.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
ZENODO_BASE = "https://zenodo.org/api"
RECORD_ID = "22131367"          # current published version (download.py::ZENODO_RECORD_ID)

# Local source -> the filename download.py's TRAINING_DATA_REGISTRY expects on Zenodo.
LOCAL_FILE = REPO / "data/external/ncfiles/ds06_calculated_ocean_properties.nc"
ZENODO_FILENAME = "ds06_calculated_ocean_properties.nc"


def _check(r: requests.Response, context: str) -> None:
    if not r.ok:
        sys.exit(f"ERROR during {context}: HTTP {r.status_code}\n  {r.text[:600]}")


def _fmt_size(path: Path) -> str:
    mb = path.stat().st_size / 1_048_576
    return f"{mb:.1f} MB" if mb >= 1 else f"{path.stat().st_size / 1024:.0f} KB"


def create_new_version(session: requests.Session) -> str:
    """New draft version, inheriting every file from RECORD_ID -- nothing deleted."""
    r = session.post(f"{ZENODO_BASE}/records/{RECORD_ID}/versions")
    _check(r, "create new version")
    draft_id = str(r.json()["id"])
    print(f"  New draft version created: id={draft_id}")
    return draft_id


def upload_file(session: requests.Session, draft_id: str, zenodo_name: str, local_path: Path) -> None:
    print(f"  uploading {zenodo_name} ({_fmt_size(local_path)}) …", end="", flush=True)
    r = session.post(f"{ZENODO_BASE}/records/{draft_id}/draft/files",
                      json=[{"key": zenodo_name}])
    _check(r, f"initiate upload {zenodo_name}")
    with local_path.open("rb") as fh:
        r2 = session.put(
            f"{ZENODO_BASE}/records/{draft_id}/draft/files/{zenodo_name}/content",
            data=fh, headers={"Content-Type": "application/octet-stream"},
        )
    _check(r2, f"upload content {zenodo_name}")
    r3 = session.post(f"{ZENODO_BASE}/records/{draft_id}/draft/files/{zenodo_name}/commit")
    _check(r3, f"commit {zenodo_name}")
    print(" done")


def describe_draft(session: requests.Session, draft_id: str) -> None:
    r = session.get(f"{ZENODO_BASE}/records/{draft_id}/draft/files")
    _check(r, "list draft files")
    entries = r.json().get("entries", [])
    total = sum(e.get("size") or 0 for e in entries) / 1_048_576
    print(f"  {len(entries)} file(s) in draft, {total:.0f} MB total:")
    for e in sorted(entries, key=lambda x: x["key"]):
        print(f"    {e['key']}")


def publish_draft(session: requests.Session, draft_id: str) -> str:
    r = session.post(f"{ZENODO_BASE}/records/{draft_id}/draft/actions/publish")
    _check(r, "publish")
    result = r.json()
    return (result.get("doi")
            or result.get("pids", {}).get("doi", {}).get("identifier", "unknown"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--publish", action="store_true",
                    help="Publish the EXISTING draft (run with no flags first to create it).")
    ap.add_argument("--draft-id", default=None,
                    help="Draft id to publish. Required with --publish unless it printed "
                         "just now in this same run.")
    ap.add_argument("--yes", action="store_true", help="Skip the publish confirmation prompt.")
    ap.add_argument("--token", default=os.environ.get("ZENODO_TOKEN"))
    args = ap.parse_args()

    if not args.token:
        sys.exit("ERROR: set ZENODO_TOKEN (scopes deposit:write, deposit:actions) "
                  "or pass --token")

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {args.token}"})

    if args.publish:
        if not args.draft_id:
            sys.exit("ERROR: --publish needs --draft-id <id> (printed when the draft was created)")
        print(f"\n── Publishing draft {args.draft_id} ──")
        describe_draft(session, args.draft_id)
        if not args.yes:
            reply = input("\nPublish this draft? Publication is IRREVERSIBLE [y/N]: ")
            if reply.strip().lower() not in ("y", "yes"):
                sys.exit("Aborted; draft left untouched.")
        doi = publish_draft(session, args.draft_id)
        print(f"\nDone! Record: https://zenodo.org/records/{args.draft_id}")
        print(f"DOI: {doi}")
        print(f"\nNOW update src/TEXAS/utils/download.py:")
        print(f'  ZENODO_RECORD_ID: str = "{args.draft_id}"')
        return 0

    if not LOCAL_FILE.exists():
        sys.exit(f"ERROR: {LOCAL_FILE} not found -- this file lives under the gitignored "
                  "data/external/ncfiles/ and is per-machine; run this from the machine "
                  "that has it (e.g. from SI_code00_PreProcessing's output).")

    print(f"\n── Step 1: create new draft version from record {RECORD_ID} ──")
    draft_id = create_new_version(session)

    print("\n── Step 2: upload the new file (existing files are left untouched) ──")
    upload_file(session, draft_id, ZENODO_FILENAME, LOCAL_FILE)

    print("\n── Step 3: verify ──")
    describe_draft(session, draft_id)

    print("\nDraft saved (not published). Review at:")
    print(f"  https://zenodo.org/uploads/{draft_id}")
    print("\nWhen ready to publish:")
    print(f"  ZENODO_TOKEN=<token> python scripts/zenodo_add_ocean_prop_ds.py "
          f"--publish --draft-id {draft_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
