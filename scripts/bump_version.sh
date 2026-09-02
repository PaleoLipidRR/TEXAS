#!/usr/bin/env bash
# bump_version.sh — bump texas-psm version, publish to PyPI, and refresh conda-lock + uv.lock
#
# Usage:
#   ./scripts/bump_version.sh 0.1.8
#
# What it does (in order):
#   1. Validate inputs and working-tree state
#   2. Update version in pyproject.toml and CITATION.cff
#   3. Regenerate uv.lock (resolves from local pyproject.toml -- no PyPI wait needed)
#   4. Build wheel + sdist, run twine check
#   5. Commit version bump (pyproject.toml, CITATION.cff, environment.yml, uv.lock)
#   6. Upload to PyPI (twine)
#   7. Git tag + push tag + push branch
#   8. Clear pip HTTP cache and conda-lock cache
#   9. Regenerate conda-lock.yml (resolves texas-psm from PyPI, so this must run after upload)
#   10. Commit updated conda-lock.yml
#
# Note on the Docker image: only the TEXAS package itself bypasses the
# lockfiles -- docker/Dockerfile installs it from the tagged commit's local
# pyproject.toml + src/TEXAS, not from either lockfile or PyPI. But the
# image's base environment (numpy, xarray, cmdstanpy, etc.) IS built from
# conda-lock.yml (`micromamba create -f conda-lock.yml`), and step 7 below
# pushes the tag -- which triggers .github/workflows/docker.yml -- BEFORE
# step 9 regenerates conda-lock.yml. So the image always builds from
# whatever conda-lock.yml was already committed, not a fresh resolve
# triggered by this release; that lag is pre-existing and this script does
# not attempt to close it.

set -euo pipefail

# ── helpers ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[bump]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
abort() { echo -e "${RED}[abort]${NC} $*"; exit 1; }

confirm() {
    local prompt="$1"
    read -rp "$(echo -e "${YELLOW}[?]${NC} ${prompt} [y/N] ")" ans
    [[ "${ans,,}" == "y" ]]
}

# ── 1. validate ───────────────────────────────────────────────────────────────
NEW_VERSION="${1:-}"
[[ -z "$NEW_VERSION" ]] && abort "Usage: $0 <new-version> [commit-message-body]  e.g. $0 0.1.8"

# Optional second argument: extra lines appended to the commit message body.
COMMIT_BODY="${2:-}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

CURRENT_VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
info "Current version : $CURRENT_VERSION"
info "New version     : $NEW_VERSION"

# Check for uncommitted changes in tracked files (warn, don't abort)
if ! git diff --quiet HEAD -- ':(exclude)conda-lock.yml'; then
    warn "Uncommitted changes detected (excluding conda-lock.yml). Continuing anyway."
fi

confirm "Proceed with bump $CURRENT_VERSION → $NEW_VERSION?" || abort "Aborted."

TODAY=$(date +%Y-%m-%d)

# ── 2. update version strings ─────────────────────────────────────────────────
info "Updating pyproject.toml ..."
sed -i "s/^version = \"${CURRENT_VERSION}\"/version = \"${NEW_VERSION}\"/" pyproject.toml

info "Updating CITATION.cff ..."
sed -i "s/^version: ${CURRENT_VERSION}/version: ${NEW_VERSION}/" CITATION.cff
sed -i "s/^date-released: \".*\"/date-released: \"${TODAY}\"/" CITATION.cff

info "Updating environment.yml texas-psm floor ..."
sed -i "s/- texas-psm>=[0-9.]*/- texas-psm>=${NEW_VERSION}/" environment.yml

# Verify changes landed
grep "version = \"${NEW_VERSION}\"" pyproject.toml > /dev/null \
    || abort "pyproject.toml version update failed — check manually."
grep "version: ${NEW_VERSION}" CITATION.cff > /dev/null \
    || abort "CITATION.cff version update failed — check manually."

# ── 3. regenerate uv.lock ─────────────────────────────────────────────────────
info "Regenerating uv.lock ..."
uv lock

if grep -A1 '^name = "texas-psm"' uv.lock | grep -q "version = \"${NEW_VERSION}\""; then
    info "uv.lock resolved texas-psm ${NEW_VERSION} ✓"
else
    abort "uv.lock still shows the old version — check manually."
fi

# ── 4. build + check ──────────────────────────────────────────────────────────
info "Building distributions ..."
rm -rf dist/
python -m build

info "Running twine check ..."
twine check dist/*

# Verify the wheel carries the right version (catches pyproject.toml sed failures)
ls dist/texas_psm-"${NEW_VERSION}"-*.whl dist/texas_psm-"${NEW_VERSION}".tar.gz \
    > /dev/null 2>&1 \
    || abort "Wheel/sdist for v${NEW_VERSION} not found in dist/ — pyproject.toml update may have failed."
info "Wheel version verified: texas_psm-${NEW_VERSION} ✓"

# ── 5. commit version bump ────────────────────────────────────────────────────
info "Committing version bump ..."
git add pyproject.toml CITATION.cff environment.yml uv.lock
if [[ -n "$COMMIT_BODY" ]]; then
    git commit -m "$(printf "bump version to v%s\n\n%s" "${NEW_VERSION}" "${COMMIT_BODY}")"
else
    git commit -m "bump version to v${NEW_VERSION}"
fi

# ── 6. upload to PyPI ─────────────────────────────────────────────────────────
confirm "Upload to PyPI now?" || abort "Aborted before PyPI upload."
info "Uploading to PyPI ..."
twine upload dist/*

# ── 7. tag + push ─────────────────────────────────────────────────────────────
info "Tagging v${NEW_VERSION} ..."
git tag "v${NEW_VERSION}"

confirm "Push branch and tag to origin?" || abort "Aborted before git push."
git push origin main
git push origin "v${NEW_VERSION}"
info "Tag pushed -- .github/workflows/docker.yml will rebuild and publish the GHCR image"
info "(from the conda-lock.yml already committed -- not yet refreshed by step 9 below)."

# ── 8. clear caches ───────────────────────────────────────────────────────────
info "Clearing pip HTTP cache ..."
rm -rf ~/.cache/pip/

info "Clearing conda-lock resolver cache ..."
rm -rf ~/.cache/conda-lock/

# ── 9. regenerate conda-lock ──────────────────────────────────────────────────
info "Regenerating conda-lock.yml ..."
conda-lock lock -f environment.yml \
    -p linux-64 -p osx-arm64 -p osx-64 -p win-64

# Verify texas-psm resolved to the new version
if grep -q "texas_psm-${NEW_VERSION}" conda-lock.yml; then
    info "conda-lock.yml resolved texas-psm ${NEW_VERSION} ✓"
else
    warn "texas-psm ${NEW_VERSION} not found in conda-lock.yml — PyPI CDN may need a moment."
    warn "Re-run: conda-lock lock -f environment.yml -p linux-64 -p osx-arm64 -p osx-64 -p win-64"
fi

# ── 10. commit conda-lock ─────────────────────────────────────────────────────
git add conda-lock.yml
git commit -m "update conda-lock.yml for v${NEW_VERSION}"
git push origin main

info "Done! v${NEW_VERSION} is live on PyPI, uv.lock and conda-lock.yml are up to date."
