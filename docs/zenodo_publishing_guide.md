# Zenodo Publishing Guide — TEXAS

This guide covers everything needed to publish TEXAS on Zenodo alongside the
paper.  Follow it top to bottom in order.

There are **two separate Zenodo records** to create:

| Record | Contains | How created | DOI used in |
|---|---|---|---|
| **Software** | The `texas-psm` code (repo snapshot) | Auto — GitHub Release triggers it | `CITATION.cff`, `utils/download.py` |
| **Data** | GDGT database + forward posteriors (`.nc`) | Manual upload on Zenodo | `data/README.md` |

---

## Prerequisites

- GitHub account with push access to `PaleoLipidRR/TEXAS`
- Zenodo account at [zenodo.org](https://zenodo.org) (free; log in with GitHub)
- Repo must be **public** on GitHub before Zenodo can see it

---

## Part 1 — Software record (code)

### Step 1 — Verify what is already in the repo

These files must be present and correct before creating the GitHub Release.
Both were created during repo preparation — just verify they are committed.

```bash
git log --oneline -- .zenodo.json CITATION.cff
```

**`.zenodo.json`** controls all metadata Zenodo sees (title, authors, keywords,
license).  Open it and fill in your ORCID if you have one:

```json
"creators": [
  {
    "name": "Rattanasriampaipong, Ronnakrit",
    "affiliation": "The University of Texas at Austin",
    "orcid": "0000-0000-0000-0000"   ← replace with your real ORCID
  }
]
```

**`CITATION.cff`** — the DOI line currently has a placeholder:

```yaml
doi: 10.5281/zenodo.XXXXXXX
```

Leave it as-is for now.  You will fill in the real DOI in Step 5.

---

### Step 2 — Make the GitHub repo public

GitHub → **Settings** → **Danger Zone** → Change repository visibility → **Public**

> Do this only when the repo is ready.  Once public, the git history
> (including any previously committed sensitive files) is visible.
> The `data/spreadsheets/` cleanup and manuscript removal from earlier
> in this session removed those files from the working tree but they still
> exist in older commits.  If that is a concern, use
> [BFG Repo Cleaner](https://rtyley.github.io/bfg-repo-cleaner/) to
> purge them from history before going public.

---

### Step 3 — Link GitHub to Zenodo

1. Go to [zenodo.org/account/settings/github](https://zenodo.org/account/settings/github)
2. Click **Connect** (logs you in with GitHub OAuth if not already)
3. Find **PaleoLipidRR/TEXAS** in the repository list
4. Flip the toggle **ON**

Zenodo will now watch for new GitHub Releases from this repo.

---

### Step 4 — Create the GitHub Release

A GitHub Release (not just a tag) is what triggers Zenodo archiving.
Tag `v0.1.2` already exists — use it.

On GitHub:

1. Go to **Releases** → **Draft a new release**
2. **Tag**: select existing tag `v0.1.2`
3. **Release title**: `TEXAS v0.1.2 — Initial public release`
4. **Description** (suggested):

```
Initial public release of texas-psm — Bayesian GDGT-temperature calibration using Stan.

## What's included
- 20 Stan models (forward calibration + inverse reconstruction)
- High-level API: predict_RI_from_T / predict_T_from_RI
- Zenodo auto-download support for pre-computed posteriors
- Google Colab / pip-install compatible (fwd_posterior= dataset passthrough)
- Docker image with pre-built CmdStan

## Install
pip install texas-psm

## Data
Pre-computed forward posteriors available in the companion Zenodo data record
(see data/README.md).
```

5. Click **Publish release**

Within ~1 minute, Zenodo creates a **draft record** automatically.

---

### Step 5 — Get the DOI and fill in the two placeholders

1. Go to [zenodo.org/deposit](https://zenodo.org/deposit)
2. Find the draft — it will show the DOI immediately, e.g. `10.5281/zenodo.1234567`
3. Review the metadata (pre-filled from `.zenodo.json`) — edit if needed
4. **Do not click Publish yet** — fill in the placeholders first

**File 1 — `CITATION.cff`**:

```yaml
doi: 10.5281/zenodo.1234567   # ← replace XXXXXXX with real record number
```

**File 2 — `src/TEXAS/utils/download.py`**, line ~22:

```python
ZENODO_RECORD_ID = "1234567"   # ← replace None with the record number (string)
```

Then commit and push:

```bash
git add CITATION.cff src/TEXAS/utils/download.py
git commit -m "chore: add Zenodo software DOI (10.5281/zenodo.1234567)"
git push origin main
```

> Pushing these changes after the release is fine — Zenodo has already
> archived the release snapshot.  The DOI update is metadata-only.

---

### Step 6 — Publish the Zenodo software record

Back on Zenodo, click **Publish**.

The record is now live at `https://zenodo.org/record/1234567`.
The DOI `10.5281/zenodo.1234567` is permanent and citable.

**Add the DOI badge to README.md** (optional but recommended):

```markdown
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1234567.svg)](https://doi.org/10.5281/zenodo.1234567)
```

---

## Part 2 — Data record (GDGT database + posteriors)

This is a **manual upload** — separate from the GitHub integration.

### Step 7 — Prepare files to upload

Decide which files to include.  Recommended minimum:

| File | Description |
|---|---|
| `gen_logi_fixed_hier_crtp_multiv_SST.nc` | Forward posterior — SST calibration |
| `gen_logi_fixed_hier_crtp_multiv_thermoT.nc` | Forward posterior — thermoT calibration |
| GDGT training database (CSV) | Combined culture + mesocosm + coretop dataset |

The `.nc` posteriors live in `data/cache/TEXAS_posterior_cache/` on your machine.
The training CSV is in `data/spreadsheets/` (not in git; lives on your disk).

---

### Step 8 — Create the data record on Zenodo

1. [zenodo.org](https://zenodo.org) → **New upload**
2. **Upload type**: Dataset
3. Drag and drop the files from Step 7
4. Fill in metadata:

| Field | Value |
|---|---|
| **Title** | TEXAS: GDGT calibration database and forward posteriors |
| **Authors** | Rattanasriampaipong, Ronnakrit (+ co-authors if applicable) |
| **Description** | Pre-computed Bayesian forward calibration posteriors (.nc) and the GDGT training database used in Rattanasriampaipong et al. (in prep). Required for running inverse temperature reconstructions with the `texas-psm` Python package. |
| **License** | CC-BY-4.0 |
| **Keywords** | GDGT, TEX86, Ring Index, paleothermometry, Bayesian, Stan |
| **Related identifier** | GitHub repo URL → `is supplement to` |

5. Click **Publish** → you get the data DOI, e.g. `10.5281/zenodo.9999999`

---

### Step 9 — Update data/README.md with the data DOI

Open `data/README.md` and replace the placeholder Zenodo DOI with the real one.

```bash
# Edit data/README.md, then:
git add data/README.md
git commit -m "chore: add Zenodo data DOI (10.5281/zenodo.9999999)"
git push origin main
```

Also add the data DOI to `POSTERIOR_REGISTRY` in `src/TEXAS/utils/download.py`
if the `.nc` files are hosted in this data record (same record ID as `ZENODO_RECORD_ID`
or a separate one — update accordingly).

---

## Part 3 — Bump version and re-publish to PyPI

After the Zenodo DOIs are live and committed, bump the version so the PyPI
package reflects the final published state.

```bash
# Edit pyproject.toml and src/TEXAS/__init__.py: bump to 0.2.0 (or 0.1.3)
# Edit CITATION.cff: update version and date-released

git add pyproject.toml src/TEXAS/__init__.py CITATION.cff
git commit -m "chore: bump to vX.X.X for paper submission"
git tag vX.X.X && git push origin main vX.X.X

rm -rf dist/ build/
python -m build
twine check dist/*
twine upload dist/*
```

See `publishing.md` for the full PyPI workflow.

---

## Post-publication checklist

- [ ] `.zenodo.json` — ORCID filled in
- [ ] `CITATION.cff` — real DOI, correct version and date
- [ ] `src/TEXAS/utils/download.py` — `ZENODO_RECORD_ID` set to real record number
- [ ] `data/README.md` — real data DOI
- [ ] `POSTERIOR_REGISTRY` in `download.py` — filenames match what's on Zenodo
- [ ] Zenodo software record — published, DOI badge added to README
- [ ] Zenodo data record — published, linked as related identifier to software record
- [ ] PyPI — `texas-psm` version matches paper submission version
- [ ] GitHub repo — public
- [ ] GitHub Release `vX.X.X` created

---

## Updating Zenodo after corrections (post-publication)

Zenodo allows **new versions** of an existing record.

- Go to the record → **New version**
- Upload updated files
- The original DOI (`10.5281/zenodo.1234567`) still resolves, and a new
  version DOI is minted
- The "concept DOI" (`10.5281/zenodo.XXXXXXX`) always resolves to the latest version

For minor corrections to metadata (title, description) only — use **Edit** on
the existing record, no new version needed.
