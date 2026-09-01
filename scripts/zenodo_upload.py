#!/usr/bin/env python3
"""
Upload the staged resubmission archive to Zenodo as a new draft version.

Stage first:  python scripts/prepare_resubmission_archive.py --apply
Then:         ZENODO_TOKEN=<your_token> python scripts/zenodo_upload.py [--publish]

The script:
  1. Creates a new draft version from the existing data record (RECORD_ID below)
  2. Deletes files inherited from the previous version (they stay on the old,
     permanently accessible version — nothing is lost)
  3. Uploads the archive's forward posteriors, data files, MANIFEST.csv and
     README.md as individual flat files + a bundled invT ZIP
  4. Updates the version metadata to the package version
  5. Leaves the record as a DRAFT (add --publish to publish immediately)

The draft's record id is FINAL even before publishing — as soon as this
script prints it, put it into ``download.py::ZENODO_RECORD_ID`` so the tagged
release ships pointing at the record that will exist.

Uses the Zenodo InvenioRDM REST API (/api/records/).
Get a personal token at: https://zenodo.org/account/settings/applications/tokens/new/
Required scopes: deposit:write, deposit:actions
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

# ─── Configuration ─────────────────────────────────────────────────────────────
RECORD_ID = "20032542"          # v0.2.0 (initial-submission) version of the data
                                # record; the concept DOI 10.5281/zenodo.19666744
                                # resolves to whichever version is newest — check
                                # download.py::ZENODO_RECORD_ID for that id
ZENODO_BASE = "https://zenodo.org/api"
REPO = Path(__file__).resolve().parent.parent
VERSION = re.search(r'^version = "(.+)"', (REPO / "pyproject.toml").read_text(),
                    re.M).group(1)
ARCHIVE_DIR = REPO / f"review_archive_v{VERSION}"

# Expected archive shape — a mismatch means the staging script and this one
# disagree, so stop rather than upload a partial record.
EXPECTED_FORWARD = 9
EXPECTED_INVT_MIN = 40


def collect_individual_files() -> dict[str, Path]:
    """Flat files: forward posteriors + data + MANIFEST.csv + README.md.

    Forward-posterior filenames are the case ids ``download.py``'s
    POSTERIOR_REGISTRY points at; data filenames must match
    TRAINING_DATA_REGISTRY.
    """
    files: dict[str, Path] = {}
    fwd = sorted((ARCHIVE_DIR / "posteriors/forward").glob("*.nc"))
    if len(fwd) != EXPECTED_FORWARD:
        sys.exit(f"ERROR: expected {EXPECTED_FORWARD} forward posteriors, "
                 f"found {len(fwd)} — re-run prepare_resubmission_archive.py")
    for f in fwd:
        files[f.name] = f
    for f in sorted((ARCHIVE_DIR / "data").iterdir()):
        files[f.name] = f
    for name in ("MANIFEST.csv", "README.md"):
        files[name] = ARCHIVE_DIR / name
    return files


# InvT posteriors bundled as a single ZIP for SI reproducibility
INVT_ZIP_NAME = f"texas-psm-invT-posteriors-v{VERSION}.zip"
INVT_DIRS = [
    ARCHIVE_DIR / "posteriors/invT/coretop",
    ARCHIVE_DIR / "posteriors/invT/paleo",
]


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _record_id_from_download_py() -> str | None:
    """The record id the package currently ships, i.e. the draft made earlier."""
    f = REPO / "src" / "TEXAS" / "utils" / "download.py"
    m = re.search(r'^ZENODO_RECORD_ID:\s*str\s*=\s*"(\d+)"', f.read_text(), re.M)
    return m.group(1) if m else None


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
    n = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for d in INVT_DIRS:
            for f in sorted(d.rglob("*.nc")):
                arcname = f"invT/{d.name}/{f.name}"
                zf.write(f, arcname)
                n += 1
    if n < EXPECTED_INVT_MIN:
        sys.exit(f"ERROR: only {n} invT files staged (expected ≥ "
                 f"{EXPECTED_INVT_MIN}) — re-run prepare_resubmission_archive.py")
    print(f"  Built {INVT_ZIP_NAME} ({n} files, {_fmt_size(zip_path)})")
    return zip_path


def update_metadata(session: requests.Session, draft_id: str) -> None:
    """Bump the version string, keeping the metadata InvenioRDM-valid.

    The published record serves metadata in LEGACY Zenodo form
    (``creators: [{name, affiliation, orcid}]``, ``resource_type: {type: ...}``).
    Reading that and PUT-ing it back makes InvenioRDM drop both fields, and the
    publish then fails with "Missing data for required field". So verify the
    round-trip and say so loudly rather than failing later at publish time.
    """
    r = session.get(f"{ZENODO_BASE}/records/{draft_id}/draft")
    _check(r, "fetch draft metadata")
    draft = r.json()
    meta = dict(draft.get("metadata") or {})
    meta["version"] = VERSION
    r2 = session.put(
        f"{ZENODO_BASE}/records/{draft_id}/draft",
        json={"metadata": meta},
    )
    _check(r2, "update metadata")
    print(f"  version → {VERSION}")

    after = session.get(f"{ZENODO_BASE}/records/{draft_id}/draft").json().get("metadata", {})
    missing = [f for f in ("creators", "resource_type") if not after.get(f)]
    if missing:
        print(f"  WARNING: the draft has no {', '.join(missing)} -- publishing will")
        print("  fail with 'Missing data for required field'. Repair it with:")
        print("      python scripts/zenodo_fix_draft_metadata.py --apply")


def describe_draft(session: requests.Session, draft_id: str) -> None:
    """Print what is actually in a draft, so it can be checked before publishing."""
    r = session.get(f"{ZENODO_BASE}/records/{draft_id}/draft")
    _check(r, f"fetch draft {draft_id}")
    meta = r.json().get("metadata", {})
    print(f"  draft {draft_id}: version={meta.get('version')!r}  title={meta.get('title','')[:60]!r}")
    rf = session.get(f"{ZENODO_BASE}/records/{draft_id}/draft/files")
    _check(rf, "list draft files")
    entries = rf.json().get("entries", [])
    total = sum(e.get("size") or 0 for e in entries) / 1_048_576
    print(f"  {len(entries)} file(s), {total:.0f} MB total")
    for e in sorted(entries, key=lambda x: x["key"]):
        print(f"    {e['key']}")


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
                        help="Publish the EXISTING draft. Does not upload anything; "
                             "run this script with no flags first to create the draft.")
    parser.add_argument("--draft-id", default=None,
                        help="Draft to publish (default: ZENODO_RECORD_ID in download.py)")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the confirmation prompt when publishing")
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

    if not ARCHIVE_DIR.is_dir():
        sys.exit(f"ERROR: {ARCHIVE_DIR} not found — run "
                 "prepare_resubmission_archive.py --apply first")
    individual_files = collect_individual_files()
    missing = [name for name, path in individual_files.items() if not path.exists()]
    if missing:
        sys.exit("ERROR: local files not found:\n" + "\n".join(f"  {m}" for m in missing))

    session = _session(args.token)

    # --publish acts on the draft that ALREADY exists. It must not create a new
    # version or re-upload: that would abandon the draft whose id is already
    # baked into download.py and the tagged release, and repeat a ~500 MB upload.
    if args.publish:
        draft_id = args.draft_id or _record_id_from_download_py()
        if not draft_id:
            sys.exit(
                "ERROR: --publish needs the draft id.\n"
                "  Pass --draft-id <id>, or set ZENODO_RECORD_ID in\n"
                "  src/TEXAS/utils/download.py to the draft you created earlier."
            )
        print(f"\n── Publishing existing draft {draft_id} (no re-upload) ──")
        describe_draft(session, draft_id)
        if not args.yes:
            reply = input("\nPublish this draft? Publication is IRREVERSIBLE [y/N]: ")
            if reply.strip().lower() not in ("y", "yes"):
                sys.exit("Aborted; draft left untouched.")
        doi = publish_draft(session, draft_id)
        print(f"\nDone! Record: https://zenodo.org/records/{draft_id}")
        print(f"DOI: {doi}")
        return 0

    print(f"\n── Step 1: create new draft version from record {RECORD_ID} ──")
    draft = create_new_version(session)
    draft_id = str(draft["id"])

    print("\n── Step 2: delete inherited files ──")
    delete_existing_files(session, draft_id)

    print("\n── Step 3: upload individual files ──")
    for zenodo_name, local_path in individual_files.items():
        upload_file(session, draft_id, zenodo_name, local_path)

    print("\n── Step 4: bundle and upload invT posteriors ──")
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = build_invt_zip(Path(tmp))
        upload_file(session, draft_id, INVT_ZIP_NAME, zip_path)

    print("\n── Step 5: update metadata ──")
    update_metadata(session, draft_id)

    if True:
        print("\nDraft saved (not published).")
        print(f"Review at: https://zenodo.org/uploads/{draft_id}")
        print("\nNOW, before tagging the release (the draft id is final):")
        print(f"  src/TEXAS/utils/download.py  →  ZENODO_RECORD_ID = \"{draft_id}\"")
        print("\nWhen ready to publish:")
        print("  ZENODO_TOKEN=<token> python scripts/zenodo_upload.py --publish")


if __name__ == "__main__":
    main()
