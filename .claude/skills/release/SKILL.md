---
name: release
description: Cut a new TEXAS release — bump version, update CITATION.cff, build dist, run twine check, tag git. Requires a version number argument.
disable-model-invocation: true
allowed-tools: Read Edit Bash
argument-hint: [new-version e.g. 0.1.5]
---

Cut a new `texas-psm` release. Argument: `$ARGUMENTS` (the new version string, e.g. `0.1.5`).

If no version argument is given, read the current version from `pyproject.toml` and ask the user what the new version should be before proceeding.

**Stop and confirm with the user before each destructive step** (git tag, git push, twine upload).

---

## Step 1 — Confirm current state

```bash
git status
git log --oneline -5
```

Warn if there are uncommitted changes. Ask user whether to proceed anyway or commit first.

Read current version:
```bash
grep '^version' pyproject.toml
```

## Step 2 — Bump version in `pyproject.toml`

Edit `pyproject.toml`: change `version = "X.Y.Z"` to `version = "$ARGUMENTS"`.

Also check `src/TEXAS/__init__.py` for a `__version__` string and update it to match if present.

## Step 3 — Update `CITATION.cff`

Read `CITATION.cff`. Update the `version:` field to `$ARGUMENTS`.
Update the `date-released:` field to today's date in `YYYY-MM-DD` format.
If `doi:` still contains `10.5281/zenodo.XXXXXXX` (placeholder), warn the user that the real Zenodo DOI must be filled in before submission.

## Step 4 — Update `CHANGELOG` or release notes (if present)

Check if `CHANGELOG.md` or `docs/changelog.md` exists. If so, prompt the user:
"Do you want to add a changelog entry for $ARGUMENTS? (y/n)"
If yes, read recent `git log --oneline` output and draft a short entry.

## Step 5 — Build distribution

```bash
rm -rf dist/
python -m build
```

Check for errors. List the produced files:
```bash
ls -lh dist/
```

## Step 6 — Run twine check

```bash
twine check dist/*
```

FAIL and stop if twine check does not pass. Show the errors to the user.

## Step 7 — Commit the version bump

Stage only the version-related files:
```bash
git add pyproject.toml CITATION.cff src/TEXAS/__init__.py
git status
```

Show the diff. Ask user to confirm before committing:
"Ready to commit version bump to $ARGUMENTS. Proceed? (y/n)"

```bash
git commit -m "chore: bump to v$ARGUMENTS"
```

## Step 8 — Tag the release

**Confirm with user before tagging:**
"Ready to create git tag v$ARGUMENTS. Proceed? (y/n)"

```bash
git tag -a "v$ARGUMENTS" -m "Release v$ARGUMENTS"
git log --oneline -3
```

## Step 9 — Push to remote

**Confirm with user before pushing:**
"Ready to push commit + tag to origin. This cannot be undone easily. Proceed? (y/n)"

```bash
git push origin main
git push origin "v$ARGUMENTS"
```

## Step 10 — PyPI upload (optional)

Ask: "Upload to PyPI now? This will make v$ARGUMENTS publicly available on pip. (y/n)"

If yes:
```bash
twine upload dist/*
```

---

## Checklist summary

After completing, print:
- [ ] `pyproject.toml` version updated
- [ ] `CITATION.cff` version + date updated
- [ ] `__init__.py` version updated (if applicable)
- [ ] `dist/` rebuilt and twine check passed
- [ ] Version bump committed
- [ ] Git tag `v$ARGUMENTS` created
- [ ] Pushed to origin
- [ ] PyPI upload: done / skipped
- [ ] Zenodo DOI: filled in / still placeholder (warn if placeholder)
