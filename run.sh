#!/usr/bin/env bash
# run.sh — one-command launcher for TEXAS Docker environment
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
export REPO_ROOT
COMPOSE_FILE="$REPO_ROOT/docker/docker-compose.yml"

# ─── Banner ───────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   TEXAS — Temperature Estimation via Bayesian Approach        ║"
echo "║              with Stan  (texas-psm)                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ─── Requirements check ───────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "Error: Docker is not installed. Install Docker Desktop from https://docker.com" >&2
    exit 1
fi
if ! docker info &>/dev/null 2>&1; then
    echo "Error: Docker daemon is not running. Please start Docker Desktop and try again." >&2
    exit 1
fi

# Detect docker compose v2 plugin or fall back to v1 standalone
if docker compose version &>/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose &>/dev/null; then
    DC="docker-compose"
else
    echo "Error: Docker Compose not found. Install Docker Desktop (includes Compose) from https://docker.com" >&2
    exit 1
fi

# ─── OS / WSL detection ───────────────────────────────────────────────────────
OS="$(uname -s)"
IS_WSL=false
if grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=true
fi
VOLUMES=()

# ─── Profile selection ────────────────────────────────────────────────────────
echo "Available profiles:"
echo "  full  — JupyterLab with full Stan environment (port 8890)  [recommended]"
echo "  app   — Streamlit app for exploring posterior distributions (port 8503)"
echo "  docs  — MkDocs documentation server (port 8000)"
echo ""
read -rp "Which profile? [full]: " PROFILE
PROFILE="${PROFILE:-full}"

if [[ "$PROFILE" != "app" && "$PROFILE" != "full" && "$PROFILE" != "docs" ]]; then
    echo "Error: profile must be 'full', 'app', or 'docs'." >&2
    exit 1
fi

# ─── Google Drive ─────────────────────────────────────────────────────────────
echo ""
read -rp "Mount Google Drive? [y/N]: " GDRIVE_ANSWER
GDRIVE_ANSWER="${GDRIVE_ANSWER:-N}"
if [[ "$GDRIVE_ANSWER" =~ ^[Yy]$ ]]; then
    if [[ "$OS" == "Darwin" ]]; then
        DEFAULT_GDRIVE="$HOME/Google Drive/My Drive"
    elif [[ "$IS_WSL" == true ]]; then
        WIN_USER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
        DEFAULT_GDRIVE="/mnt/c/Users/${WIN_USER}/Google Drive/My Drive"
    else
        if [[ -d "$HOME/GoogleDrive" ]]; then
            DEFAULT_GDRIVE="$HOME/GoogleDrive"
        else
            DEFAULT_GDRIVE="$HOME/google-drive"
        fi
    fi
    read -rp "Google Drive path [$DEFAULT_GDRIVE]: " GDRIVE_PATH
    GDRIVE_PATH="${GDRIVE_PATH:-$DEFAULT_GDRIVE}"
    if [[ ! -d "$GDRIVE_PATH" ]]; then
        echo "Warning: '$GDRIVE_PATH' does not exist — skipping Google Drive mount." >&2
    else
        VOLUMES+=("--volume" "${GDRIVE_PATH}:/mnt/gdrive:ro")
        echo "  Mounting Google Drive: $GDRIVE_PATH -> /mnt/gdrive"
    fi
fi

# ─── OneDrive ─────────────────────────────────────────────────────────────────
echo ""
read -rp "Mount OneDrive? [y/N]: " ONEDRIVE_ANSWER
ONEDRIVE_ANSWER="${ONEDRIVE_ANSWER:-N}"
if [[ "$ONEDRIVE_ANSWER" =~ ^[Yy]$ ]]; then
    if [[ "$OS" == "Darwin" ]]; then
        DEFAULT_ONEDRIVE="$HOME/Library/CloudStorage/OneDrive-Personal"
    elif [[ "$IS_WSL" == true ]]; then
        WIN_USER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
        DEFAULT_ONEDRIVE="/mnt/c/Users/${WIN_USER}/OneDrive"
    else
        DEFAULT_ONEDRIVE="$HOME/OneDrive"
    fi
    read -rp "OneDrive path [$DEFAULT_ONEDRIVE]: " ONEDRIVE_PATH
    ONEDRIVE_PATH="${ONEDRIVE_PATH:-$DEFAULT_ONEDRIVE}"
    if [[ ! -d "$ONEDRIVE_PATH" ]]; then
        echo "Warning: '$ONEDRIVE_PATH' does not exist — skipping OneDrive mount." >&2
    else
        VOLUMES+=("--volume" "${ONEDRIVE_PATH}:/mnt/onedrive:ro")
        echo "  Mounting OneDrive: $ONEDRIVE_PATH -> /mnt/onedrive"
    fi
fi

# ─── Pull pre-built image (full profile only) ─────────────────────────────────
if [[ "$PROFILE" == "full" ]]; then
    echo ""
    echo "Image options for the 'full' profile:"
    echo "  [Y] Pull pre-built image from GHCR  (~2-3 GB download, no build time)"
    echo "  [n] Build locally from source        (~10 min, requires internet for packages)"
    echo ""
    read -rp "Pull pre-built image? [Y/n]: " PULL_ANSWER
    PULL_ANSWER="${PULL_ANSWER:-Y}"
    if [[ "$PULL_ANSWER" =~ ^[Yy]$ ]]; then
        echo "Pulling ghcr.io/paleolipidrr/texas:latest ..."
        $DC -f "$COMPOSE_FILE" --profile full pull full
    fi
fi

# ─── Launch ───────────────────────────────────────────────────────────────────
echo ""
echo "Starting profile: $PROFILE ..."
echo ""

if [[ "$PROFILE" == "app" ]]; then
    echo "Streamlit app will be available at: http://localhost:8503"
elif [[ "$PROFILE" == "docs" ]]; then
    echo "Docs will be available at: http://localhost:8000"
else
    echo "JupyterLab will be available at: http://localhost:8890"
    echo "(Look for the token URL in the output below)"
fi
echo ""

if [[ "$PROFILE" == "full" ]]; then
    docker run --rm \
        --user root \
        --entrypoint "" \
        --workdir /app \
        -e GIT_CONFIG_COUNT=1 \
        -e GIT_CONFIG_KEY_0=safe.directory \
        -e GIT_CONFIG_VALUE_0=/app \
        -p 8890:8890 \
        -v "${REPO_ROOT}:/app" \
        -v "${REPO_ROOT}/docker/jupyter_server_config.py:/root/.jupyter/jupyter_server_config.py:ro" \
        "${VOLUMES[@]+"${VOLUMES[@]}"}" \
        ghcr.io/paleolipidrr/texas:latest \
        /opt/conda/envs/texas-env/bin/jupyter lab \
            --ip=0.0.0.0 \
            --port=8890 \
            --no-browser \
            --allow-root \
            --IdentityProvider.token=''
else
    $DC -f "$COMPOSE_FILE" --profile "$PROFILE" run --rm \
        --service-ports \
        "${VOLUMES[@]+"${VOLUMES[@]}"}" \
        "$PROFILE"
fi
