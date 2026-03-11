#!/usr/bin/env bash
# run.sh — one-command launcher for TEXAS Docker environment
set -euo pipefail

# ─── Banner ───────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   TEXAS — Temperature Estimation via Bayesian Approach        ║"
echo "║              with Stan  (texas-psm)                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ─── Profile selection ────────────────────────────────────────────────────────
echo "Available profiles:"
echo "  app   — Streamlit web interface (port 8503)"
echo "  full  — JupyterLab with full Stan environment (port 8888)"
echo "  docs  — MkDocs documentation server (port 8000)"
echo ""
read -rp "Which profile? [full]: " PROFILE
PROFILE="${PROFILE:-full}"

if [[ "$PROFILE" != "app" && "$PROFILE" != "full" && "$PROFILE" != "docs" ]]; then
    echo "Error: profile must be 'app', 'full', or 'docs'." >&2
    exit 1
fi

# ─── OS detection ─────────────────────────────────────────────────────────────
OS="$(uname -s)"
VOLUMES=()

# ─── Google Drive ─────────────────────────────────────────────────────────────
echo ""
read -rp "Mount Google Drive? [y/N]: " GDRIVE_ANSWER
GDRIVE_ANSWER="${GDRIVE_ANSWER:-N}"
if [[ "$GDRIVE_ANSWER" =~ ^[Yy]$ ]]; then
    if [[ "$OS" == "Darwin" ]]; then
        DEFAULT_GDRIVE="$HOME/Google Drive/My Drive"
    else
        # Linux: check common rclone / google-drive-ocamlfuse paths
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

# ─── Launch ───────────────────────────────────────────────────────────────────
echo ""
echo "Starting profile: $PROFILE ..."
echo ""

if [[ "$PROFILE" == "app" ]]; then
    echo "Streamlit app will be available at: http://localhost:8503"
    docker compose --profile app up "${VOLUMES[@]+"${VOLUMES[@]}"}"
elif [[ "$PROFILE" == "docs" ]]; then
    echo "Docs will be available at: http://localhost:8000"
    docker compose --profile docs up "${VOLUMES[@]+"${VOLUMES[@]}"}"
else
    # full — JupyterLab
    echo "JupyterLab will be available at: http://localhost:8888"
    echo "(Look for the token URL in the output below)"
    echo ""
    docker compose --profile full run --rm \
        --service-ports \
        "${VOLUMES[@]+"${VOLUMES[@]}"}" \
        full
fi
