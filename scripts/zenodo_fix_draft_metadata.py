#!/usr/bin/env python3
"""Repair a Zenodo draft whose metadata lost ``creators`` / ``resource_type``.

Why this is needed
------------------
The published record serves metadata in **legacy Zenodo** form::

    "creators": [{"name": "Doe, Jane", "affiliation": "...", "orcid": "..."}]
    "resource_type": {"title": "Dataset", "type": "dataset"}

The InvenioRDM API that ``zenodo_upload.py`` talks to expects the newer form::

    "creators": [{"person_or_org": {"type": "personal", "given_name": ...,
                                    "family_name": ..., "identifiers": [...]},
                  "affiliations": [{"name": ...}]}]
    "resource_type": {"id": "dataset"}

``update_metadata()`` used to GET the draft, copy its metadata and PUT it back.
When the GET returned the legacy shape, InvenioRDM could not parse ``creators``
or ``resource_type`` and silently dropped them, so publishing failed with::

    HTTP 400 ... metadata.resource_type: Missing data for required field.
                 metadata.creators:      Missing data for required field.

This script rewrites the draft's metadata in the correct shape. It changes
**metadata only** -- files are never touched.

Author details are taken from the published parent record so that a format fix
does not silently become an authorship edit. Any difference against
``CITATION.cff`` is reported for you to resolve deliberately.

Usage
-----
    ZENODO_TOKEN=... python scripts/zenodo_fix_draft_metadata.py            # dry run
    ZENODO_TOKEN=... python scripts/zenodo_fix_draft_metadata.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
ZENODO_BASE = "https://zenodo.org/api"
PARENT_RECORD = "20032542"          # published v0.2.0, source of author details

# Deliberate corrections to what the published record carries, keyed by family
# name -- a genuine authorship update, not format drift, so it lives here where
# it is reviewable and survives a re-run rather than being hand-edited in the
# web form. NOTE: the manuscript gives both of these authors TWO affiliations
# (Rattanasriampaipong: Arizona + UCAR; Elling: Kiel + Heidelberg). Zenodo
# accepts a list, so add the second entry here if the record should match.
AFFILIATION_OVERRIDES: dict[str, str] = {
    "Rattanasriampaipong": "University of Arizona",   # was UCAR
    "Elling": "Heidelberg University",                # was Kiel University
}
DEFAULT_TITLE = ("GDGT calibration database and Bayesian posteriors for "
                 "TEXAS (texas-psm)")


def _version() -> str:
    m = re.search(r'^version = "(.+)"', (REPO / "pyproject.toml").read_text(), re.M)
    return m.group(1)


def _draft_id() -> str | None:
    f = REPO / "src" / "TEXAS" / "utils" / "download.py"
    m = re.search(r'^ZENODO_RECORD_ID:\s*str\s*=\s*"(\d+)"', f.read_text(), re.M)
    return m.group(1) if m else None


def _split_name(name: str) -> tuple[str, str]:
    """'Family, Given' -> (given, family); falls back to last-word-is-family."""
    if "," in name:
        family, given = name.split(",", 1)
        return given.strip(), family.strip()
    parts = name.split()
    return " ".join(parts[:-1]), parts[-1]


def creators_from_parent(session: requests.Session) -> list[dict]:
    r = session.get(f"{ZENODO_BASE}/records/{PARENT_RECORD}")
    r.raise_for_status()
    legacy = r.json().get("metadata", {}).get("creators", [])
    out = []
    for c in legacy:
        given, family = _split_name(c["name"])
        person = {"type": "personal", "given_name": given, "family_name": family}
        if c.get("orcid"):
            person["identifiers"] = [{"scheme": "orcid", "identifier": c["orcid"]}]
        entry = {"person_or_org": person}
        aff = AFFILIATION_OVERRIDES.get(family, c.get("affiliation"))
        if aff:
            entry["affiliations"] = [{"name": aff}]
        out.append(entry)
    return out


def citation_cff_affiliations() -> dict[str, str]:
    """family-name -> affiliation, as declared in CITATION.cff."""
    text = (REPO / "CITATION.cff").read_text(encoding="utf-8")
    out, fam = {}, None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("- family-names:"):
            fam = s.split(":", 1)[1].strip().strip('"')
        elif s.startswith("affiliation:") and fam:
            out[fam] = s.split(":", 1)[1].strip().strip('"')
            fam = None
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write (default: dry run)")
    ap.add_argument("--draft-id", default=None)
    ap.add_argument("--token", default=os.environ.get("ZENODO_TOKEN"))
    args = ap.parse_args()

    if not args.token:
        sys.exit("ERROR: set ZENODO_TOKEN (scopes deposit:write, deposit:actions)")
    draft_id = args.draft_id or _draft_id()
    if not draft_id:
        sys.exit("ERROR: no draft id; pass --draft-id")

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {args.token}"})

    r = session.get(f"{ZENODO_BASE}/records/{draft_id}/draft")
    if not r.ok:
        sys.exit(f"ERROR fetching draft {draft_id}: HTTP {r.status_code}\n  {r.text[:400]}")
    draft = r.json()
    meta = dict(draft.get("metadata") or {})

    print(f"Draft {draft_id}")
    print(f"  present now : creators={len(meta.get('creators') or [])}, "
          f"resource_type={meta.get('resource_type')!r}, version={meta.get('version')!r}")

    creators = creators_from_parent(session)

    # Build metadata from scratch rather than mutating what the draft returned.
    # The draft may carry legacy-shaped or read-only keys, and echoing those back
    # makes the API return 500. Only the fields below are sent.
    import datetime
    parent_meta = session.get(f"{ZENODO_BASE}/records/{PARENT_RECORD}").json().get("metadata", {})
    clean = {
        "resource_type": {"id": "dataset"},
        "creators": creators,
        # The deposit now carries inverse reconstructions as well, so the
        # inherited "forward posteriors" title understates it.
        "title": DEFAULT_TITLE,
        "publication_date": meta.get("publication_date") or datetime.date.today().isoformat(),
        "version": _version(),
        # Required for DOI registration; the parent record never set it.
        "publisher": meta.get("publisher") or parent_meta.get("publisher") or "Zenodo",
    }
    desc = meta.get("description") or parent_meta.get("description")
    if desc:
        clean["description"] = desc
    if meta.get("rights"):
        clean["rights"] = meta["rights"]
    meta = clean

    print(f"  will write  : creators={len(creators)}, resource_type={{'id': 'dataset'}}, "
          f"version={meta['version']!r}, publisher={meta['publisher']!r}")
    print(f"  title       : {meta['title']}")
    for c in creators:
        p = c["person_or_org"]
        orcid = next((i["identifier"] for i in p.get("identifiers", [])), "-")
        aff = (c.get("affiliations") or [{}])[0].get("name", "-")
        print(f"      {p['family_name']}, {p['given_name']}  orcid={orcid}  aff={aff}")

    if AFFILIATION_OVERRIDES:
        print("\n  Applied affiliation corrections (AFFILIATION_OVERRIDES):")
        for fam, aff in AFFILIATION_OVERRIDES.items():
            print(f"      {fam} -> {aff}")

    cff = citation_cff_affiliations()
    diffs = [(c["person_or_org"]["family_name"],
              (c.get("affiliations") or [{}])[0].get("name", "-"),
              cff[c["person_or_org"]["family_name"]])
             for c in creators
             if c["person_or_org"]["family_name"] in cff
             and cff[c["person_or_org"]["family_name"]]
             != (c.get("affiliations") or [{}])[0].get("name")]
    diffs = [d for d in diffs if d[0] not in AFFILIATION_OVERRIDES]
    if diffs:
        print("\n  NOTE: these still differ from CITATION.cff, which spells the same"
              "\n  institution at department level. Keeping the record's shorter form;"
              "\n  add an AFFILIATION_OVERRIDES entry if you want the longer one:")
        for fam, rec, cffval in diffs:
            print(f"      {fam}: record={rec!r}  CITATION.cff={cffval!r}")

    if not args.apply:
        print("\nDry run -- nothing written. Re-run with --apply.")
        return 0

    r2 = session.put(f"{ZENODO_BASE}/records/{draft_id}/draft",
                     json={"metadata": meta})
    if not r2.ok:
        sys.exit(f"ERROR writing metadata: HTTP {r2.status_code}\n  {r2.text[:600]}")

    check = session.get(f"{ZENODO_BASE}/records/{draft_id}/draft").json().get("metadata", {})
    print(f"\nWrote. Draft now has creators={len(check.get('creators') or [])}, "
          f"resource_type={check.get('resource_type')!r}, version={check.get('version')!r}")
    print("\nNext: python scripts/zenodo_upload.py --publish")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
