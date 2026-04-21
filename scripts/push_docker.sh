#!/usr/bin/env bash
# push_docker.sh — build and push the TEXAS Docker image to GHCR
#
# Usage:
#   ./scripts/push_docker.sh [version]
#
# If version is omitted, reads it from pyproject.toml.
# Builds from the current conda-lock.yml and Dockerfile.
#
# Prerequisites:
#   - Docker running
#   - Logged in to GHCR:
#       echo $GITHUB_TOKEN | docker login ghcr.io -u PaleoLipidRR --password-stdin
#     (token needs write:packages scope)

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[docker]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
abort() { echo -e "${RED}[abort]${NC} $*"; exit 1; }

confirm() {
    read -rp "$(echo -e "${YELLOW}[?]${NC} $1 [y/N] ")" ans
    [[ "${ans,,}" == "y" ]]
}

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# ── resolve version ───────────────────────────────────────────────────────────
VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
fi

IMAGE="ghcr.io/paleolipidrr/texas"
info "Image  : ${IMAGE}"
info "Tags   : latest, v${VERSION}"

# ── check Docker is running ───────────────────────────────────────────────────
docker info > /dev/null 2>&1 || abort "Docker is not running."

# ── check GHCR login ─────────────────────────────────────────────────────────
if ! docker system info 2>/dev/null | grep -q "ghcr.io"; then
    warn "Not logged in to ghcr.io. Run:"
    warn "  echo \$GITHUB_TOKEN | docker login ghcr.io -u PaleoLipidRR --password-stdin"
fi

confirm "Build and push ${IMAGE}:v${VERSION}?" || abort "Aborted."

# ── build ─────────────────────────────────────────────────────────────────────
info "Building image (this takes ~20 min on first build) ..."
docker build \
    -f docker/Dockerfile \
    -t "${IMAGE}:latest" \
    -t "${IMAGE}:v${VERSION}" \
    .

# ── push ──────────────────────────────────────────────────────────────────────
confirm "Push to GHCR?" || abort "Aborted before push."

info "Pushing ${IMAGE}:latest ..."
docker push "${IMAGE}:latest"

info "Pushing ${IMAGE}:v${VERSION} ..."
docker push "${IMAGE}:v${VERSION}"

info "Done! Image available at:"
info "  docker pull ${IMAGE}:latest"
info "  docker pull ${IMAGE}:v${VERSION}"
