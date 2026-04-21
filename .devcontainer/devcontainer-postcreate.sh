#!/bin/bash
set -e
cd /home/micromamba/app

# ── Cloud drive reminder ───────────────────────────────────────────────────────
# If neither /mnt/onedrive nor /mnt/gdrive is mounted, remind the user how to
# set them up. This is a one-time step on each machine.
if [[ ! -d /mnt/onedrive && ! -d /mnt/gdrive ]]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  No cloud drives mounted."
    echo "  To mount OneDrive or Google Drive, run once from your terminal"
    echo "  (outside VS Code, in the repo root):"
    echo ""
    echo "    bash .devcontainer/setup-cloud-drives.sh"
    echo ""
    echo "  Then: Ctrl+Shift+P → Dev Containers: Rebuild Container"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
fi

# Initialize micromamba for this shell
eval "$(micromamba shell hook --shell bash)"
micromamba activate texas-env

# Install TEXAS in editable mode so source changes are reflected immediately.
# (The Dockerfile installs a snapshot; this overwrites it with the live workspace.)
pip install --no-cache-dir -q -e .

# Fix permissions
sudo chown -R micromamba:micromamba /home/micromamba/app /opt/cmdstan

# Install git-lfs
sudo apt-get update -qq && sudo apt-get install -y -qq git-lfs
git lfs update --force

exit 0
