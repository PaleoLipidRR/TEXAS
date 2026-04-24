# Zenodo Publishing Guide — TEXAS

---

## How Zenodo and GitHub relate

You have **one GitHub repo** and will create **two separate Zenodo records**.
They are completely independent — think of Zenodo as a file hosting service
where each "record" is just a bucket of files with its own DOI and its own
metadata form.

```
GitHub repo (PaleoLipidRR/TEXAS)
    │
    └── triggers (via GitHub Release) ──▶  Zenodo Record A — SOFTWARE
                                            texas-psm code snapshot
                                            DOI: 10.5281/zenodo.AAAAAAA
                                            Cited in: CITATION.cff
                                            Used by: pip install texas-psm users

Zenodo.org (manual drag-and-drop)
    └──────────────────────────────────▶  Zenodo Record B — DATA
                                            .nc posteriors + training CSVs
                                            DOI: 10.5281/zenodo.BBBBBBB
                                            Cited in: data/README.md + manuscript §Data
                                            Used by: download_posteriors() in the package
```

Record B has **nothing to do with GitHub**. You go to zenodo.org, click
"New upload", drag files in, fill a form, click Publish. The two records are
linked by adding each other's DOI in the "related identifier" field — a
one-time manual step.

---

## Version scheme

| Phase | Version | When |
|-------|---------|------|
| Pre-publication / manuscript under review | `0.x.xx` (current: `0.1.10`) | Now — do not change |
| Official published release | `1.0.0` | Bump only at paper acceptance |

The `0.x.xx` range signals that the API and calibration are still subject to
revision during peer review.  `1.0.0` is the first stable citable release.

---

## Can reviewers access data from Zenodo?

**Only if the record is published (open access).**

| Zenodo state | Reviewers can access? |
|---|---|
| Draft | ❌ Owner only |
| Published — Open Access | ✅ Anyone with the DOI link |
| Published — Restricted + secret link | ✅ Anyone you share the link with |
| Published — Embargoed | ❌ Files locked until embargo date |

**Recommendation for AGU submission**: publish Record B (data) as **open access**
at submission — the data (CSVs + posteriors) won't change during review.
Include the DOI in your manuscript's data availability statement.  Reviewers
click it and download directly.

Record A (software) can stay as a draft until acceptance; bump to `1.0.0` and
publish it when the paper is accepted.

---

## Step-by-step: what to do at submission

### 1 — Stage the data files

Run from the repo root:

```bash
bash scripts/prepare_review_archive.sh
# → review_archive_v0.1.10/
#     posteriors/canonical/   4 × scaledRI_cren3 .nc (RI₀₋₃, recommended)
#     posteriors/reference/   4 × scaledRI .nc       (RI₀₋₄, comparison)
#     data/                   2 × training CSVs
#     README.md
```

### 2 — Create and publish Record B (data) on Zenodo

1. Go to [zenodo.org](https://zenodo.org) → **New upload**
2. **Upload type**: Dataset
3. Drag all files from `review_archive_v0.1.5/` into the upload form
   *(posteriors from both subfolders + both CSVs + README.md)*
4. Fill in metadata:

| Field | Value |
|---|---|
| **Title** | TEXAS: GDGT calibration database and forward posteriors |
| **Authors** | Rattanasriampaipong, Ronnakrit |
| **Version** | 0.1.5 |
| **Description** | Pre-computed Bayesian forward calibration posteriors (.nc) and the GDGT training database used in Rattanasriampaipong et al. (in prep), *TEXAS: A proxy system model for TEX86 paleothermometry*, AGU Paleoceanography and Paleoclimatology. Required for running inverse temperature reconstructions with the `texas-psm` Python package. |
| **License** | CC-BY-4.0 |
| **Access** | Open — No restrictions |
| **Keywords** | GDGT, TEX86, Ring Index, paleothermometry, Bayesian, Stan |
| **Related identifier** | `https://github.com/PaleoLipidRR/TEXAS` → `is supplement to` |

5. Click **Publish** → Zenodo gives you a DOI, e.g. `10.5281/zenodo.BBBBBBB`
6. Copy this DOI into your manuscript's data availability statement

### 3 — Update the two DOI placeholders in the package

**`data/README.md`** — replace the placeholder data DOI.

**`src/TEXAS/utils/download.py`** — set the record ID so users can
`TEXAS.download_posteriors()`:

```python
ZENODO_RECORD_ID = "BBBBBBB"   # ← the number from your data record DOI
```

Then commit:

```bash
git add data/README.md src/TEXAS/utils/download.py
git commit -m "chore: add Zenodo data DOI (10.5281/zenodo.BBBBBBB)"
git push origin main
```

---

## Step-by-step: what to do at acceptance

### 4 — Bump version to 1.0.0

In `pyproject.toml`, `src/TEXAS/__init__.py`, and `CITATION.cff`:

```bash
# Edit the three files, then:
git add pyproject.toml src/TEXAS/__init__.py CITATION.cff
git commit -m "chore: bump to v1.0.0 for publication"
git tag v1.0.0 && git push origin main v1.0.0
```

### 5 — Make the GitHub repo public

GitHub → **Settings** → **Danger Zone** → Change visibility → **Public**

> Check the git history first — any previously committed sensitive files
> are visible once the repo is public.  Use
> [BFG Repo Cleaner](https://rtyley.github.io/bfg-repo-cleaner/) to
> purge them if needed.

### 6 — Link GitHub to Zenodo and create Record A (software)

1. Go to [zenodo.org/account/settings/github](https://zenodo.org/account/settings/github)
2. Click **Connect** → find **PaleoLipidRR/TEXAS** → flip toggle **ON**
3. On GitHub: **Releases** → **Draft a new release**
   - Tag: `v1.0.0`
   - Title: `TEXAS v1.0.0 — Published release`
   - Click **Publish release**
4. Within ~1 min, Zenodo creates a draft software record automatically
5. Go to [zenodo.org/deposit](https://zenodo.org/deposit) → find the draft
6. Check the metadata (pre-filled from `.zenodo.json`) → do NOT publish yet

### 7 — Fill in the software DOI placeholder

The draft already shows its DOI, e.g. `10.5281/zenodo.AAAAAAA`.

**`CITATION.cff`**:
```yaml
doi: 10.5281/zenodo.AAAAAAA
```

**`src/TEXAS/utils/download.py`** — add as a related comment or second constant
if you want to distinguish software vs data record IDs.

Commit and push:

```bash
git add CITATION.cff
git commit -m "chore: add Zenodo software DOI (10.5281/zenodo.AAAAAAA)"
git push origin main
```

### 8 — Publish Record A on Zenodo

Back on Zenodo, click **Publish**.

Add the DOI badge to `README.md` (optional but visible to users):

```markdown
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.AAAAAAA.svg)](https://doi.org/10.5281/zenodo.AAAAAAA)
```

### 9 — Cross-link the two records

On Zenodo Record B (data), click **Edit** → add a related identifier:
- Identifier: `10.5281/zenodo.AAAAAAA`
- Relation: `is supplement to`
- Click Save

This makes both records discoverable from each other.

### 10 — Publish to PyPI

```bash
rm -rf dist/ build/ src/*.egg-info
python -m build
twine check dist/*
twine upload dist/*
```

---

## Post-publication checklist

- [ ] `CITATION.cff` — real software DOI, version `1.0.0`, date-released filled in
- [ ] `src/TEXAS/utils/download.py` — `ZENODO_RECORD_ID` set to data record number
- [ ] `data/README.md` — data DOI filled in
- [ ] `POSTERIOR_REGISTRY` in `download.py` — filenames match what's on Zenodo
- [ ] Zenodo Record A (software) — published, DOI badge in README.md
- [ ] Zenodo Record B (data) — published open access, linked to software record
- [ ] PyPI — `texas-psm` v1.0.0 live
- [ ] GitHub repo — public, Release v1.0.0 created
- [ ] `.zenodo.json` — ORCID filled in

---

## Updating Zenodo after corrections (post-publication)

Zenodo allows **new versions** of any record.

- Open the record → **New version** → upload updated files → Publish
- The original DOI still resolves; a new version DOI is minted
- The "concept DOI" always resolves to the latest version

For metadata-only fixes (title, description): use **Edit** on the existing
record — no new version needed.
