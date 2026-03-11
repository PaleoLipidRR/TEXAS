# Publishing Guide — `texas-psm` on PyPI

This document covers everything you need to do when publishing or updating
the package on PyPI for the first time. Read it top to bottom before running
any commands.

---

## Prerequisites (one-time setup)

### 1. Create a PyPI account
Go to [pypi.org](https://pypi.org) and register. Confirm your email.

### 2. Create an API token (safer than password)
- PyPI → Account Settings → API tokens → **Add API token**
- Scope: "Entire account" for first upload (you can restrict to `texas-psm` later)
- Copy the token — it starts with `pypi-` and is shown **only once**

### 3. Store the token in `~/.pypirc` so you don't type it every time
```ini
[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE
```
```bash
chmod 600 ~/.pypirc
```

### 4. Install the publishing tools
```bash
pip install build twine
```

---

## First-ever publish

### Step 1 — Make sure the version in `pyproject.toml` is correct
```toml
version = "0.1.0"
```
PyPI keeps every version forever. You **cannot overwrite** a version once uploaded.
Use [Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`.

### Step 2 — Tag the release in git
Tagging ties the PyPI release to a specific commit in your repo.
```bash
git tag v0.1.0
git push origin v0.1.0
```

### Step 3 — Build the distribution files
Run from the repo root:
```bash
# Remove any stale build artefacts first
rm -rf dist/ build/ src/*.egg-info

python -m build
# Produces:
#   dist/texas_psm-0.1.0.tar.gz       ← source distribution
#   dist/texas_psm-0.1.0-py3-none-any.whl  ← wheel (what pip installs)
```

### Step 4 — Check the package before uploading
```bash
twine check dist/*
# Should print "PASSED" for both files. Fix any warnings before uploading.
```

### Step 5 — Test on TestPyPI first (strongly recommended)
TestPyPI is a sandbox — mistakes there don't matter.
```bash
twine upload --repository testpypi dist/*
# Then test-install in a clean environment:
pip install --index-url https://test.pypi.org/simple/ texas-psm
```

### Step 6 — Upload to real PyPI
```bash
twine upload dist/*
```
Done. Anyone can now install with:
```bash
pip install texas-psm
```

---

## Updating the package (subsequent releases)

### Step 1 — Bump the version
In `pyproject.toml` and `src/TEXAS/__init__.py`, change the version number.
Both must match.
```toml
# pyproject.toml
version = "0.2.0"
```
```python
# src/TEXAS/__init__.py
__version__ = "0.2.0"
```

### Step 2 — Update `CITATION.cff`
```yaml
version: 0.2.0
date-released: "YYYY-MM-DD"
```

### Step 3 — Tag, build, check, upload (same as above)
```bash
git tag v0.2.0 && git push origin v0.2.0
rm -rf dist/ build/ src/*.egg-info
python -m build
twine check dist/*
twine upload dist/*
```

---

## What is included in the wheel

Controlled by `pyproject.toml`:

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["TEXAS*"]          # all subpackages under src/TEXAS/

[tool.setuptools.package-data]
TEXAS = ["stan_models/*.stan"]  # Stan source files (not the archive/ subdirectory)
```

The `stan_models/archive/` folder is intentionally excluded — archived models
are not needed at runtime.

To verify what will be in the next release:
```bash
python -m build
unzip -l dist/texas_psm-*.whl | grep -v ".pyc"
```

---

## Common mistakes

| Mistake | What happens | How to avoid |
|---|---|---|
| Uploading without bumping the version | `twine upload` fails: "File already exists" | Always bump `version` in `pyproject.toml` first |
| Forgetting to rebuild after code changes | Old code gets uploaded | Always `rm -rf dist/ && python -m build` fresh |
| Using a bad token | 403 Forbidden from twine | Re-generate token on pypi.org; update `~/.pypirc` |
| `__version__` in `__init__.py` doesn't match `pyproject.toml` | Inconsistent `TEXAS.__version__` at runtime | Keep both in sync; update both together |
| Publishing with test data or secrets in `src/` | Data lands on PyPI permanently | Check `twine check` output; use `.gitignore` patterns |

---

## Zenodo (software DOI + data record)

See **`docs/zenodo_publishing_guide.md`** for the full step-by-step process,
which covers:

- Linking GitHub to Zenodo and creating the software record (auto via GitHub Release)
- Uploading the data record (GDGT database + forward posteriors `.nc`)
- Filling in the two DOI placeholders (`CITATION.cff` and `utils/download.py`)
- Post-publication checklist

Short version:
1. Make repo public → link GitHub to Zenodo → create GitHub Release
2. Get DOI from Zenodo draft → fill in `CITATION.cff` and `download.py` → push
3. Publish on Zenodo
4. Manually upload data record → update `data/README.md` with data DOI

---

## Quick reference

```bash
# Full release workflow in one block
VERSION="0.2.0"
# 1. bump version in pyproject.toml and __init__.py manually, then:
git add pyproject.toml src/TEXAS/__init__.py CITATION.cff
git commit -m "chore: bump version to $VERSION"
git tag "v$VERSION" && git push origin main "v$VERSION"
rm -rf dist/ build/ src/*.egg-info
python -m build
twine check dist/*
twine upload dist/*
```
