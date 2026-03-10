#!/usr/bin/env bash
# .devcontainer/setup-cloud-drives.sh
#
# Run this ONCE from your terminal (outside VS Code) before opening the
# devcontainer. It detects your OS, finds your cloud-drive folders, and
# patches devcontainer.json so you never have to edit JSON manually.
#
# Usage:
#   bash .devcontainer/setup-cloud-drives.sh
#
# After running, do:  Ctrl+Shift+P → "Dev Containers: Rebuild Container"

set -euo pipefail

DEVCONTAINER_JSON="$(dirname "$0")/devcontainer.json"

# ─── OS detection ─────────────────────────────────────────────────────────────
OS="$(uname -s)"

# ─── Helper: uncomment a line in devcontainer.json ────────────────────────────
uncomment_line() {
    # Remove leading `// ` from a line containing the given pattern
    local pattern="$1"
    sed -i "s|// \"source=${pattern}|\"source=${pattern}|g" "$DEVCONTAINER_JSON"
}

recomment_line() {
    # Re-add `// ` to a line containing the given pattern (idempotent reset)
    local pattern="$1"
    sed -i "s|^    \"source=${pattern}|    // \"source=${pattern}|g" "$DEVCONTAINER_JSON"
}

# Reset all cloud-drive mounts to commented-out state first
recomment_line "\\\${localEnv:HOME}/OneDrive"
recomment_line "\\\${localEnv:HOME}/Library/CloudStorage/OneDrive-Personal"
recomment_line "\\\${localEnv:HOME}/Library/CloudStorage/OneDrive-University"
recomment_line "/mnt/c/Users"
recomment_line "\\\${localEnv:HOME}/GoogleDrive"
recomment_line "\\\${localEnv:HOME}/Google Drive"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TEXAS devcontainer — cloud drive setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ─── OneDrive ─────────────────────────────────────────────────────────────────
read -rp "Mount OneDrive? [y/N]: " OD_ANSWER
OD_ANSWER="${OD_ANSWER:-N}"

if [[ "$OD_ANSWER" =~ ^[Yy]$ ]]; then
    if [[ "$OS" == "Darwin" ]]; then
        # macOS: detect personal vs work account
        PERSONAL="$HOME/Library/CloudStorage/OneDrive-Personal"
        WORK=$(find "$HOME/Library/CloudStorage/" -maxdepth 1 -name "OneDrive-*" ! -name "OneDrive-Personal" 2>/dev/null | head -1)
        if [[ -d "$PERSONAL" ]]; then
            DEFAULT_OD="$PERSONAL"
        elif [[ -n "$WORK" ]]; then
            DEFAULT_OD="$WORK"
        else
            DEFAULT_OD="$HOME/Library/CloudStorage/OneDrive-Personal"
        fi
    else
        # Linux
        DEFAULT_OD="$HOME/OneDrive"
    fi

    read -rp "OneDrive path [$DEFAULT_OD]: " OD_PATH
    OD_PATH="${OD_PATH:-$DEFAULT_OD}"

    if [[ ! -d "$OD_PATH" ]]; then
        echo "  ⚠  '$OD_PATH' not found — skipping OneDrive mount."
        echo "     (Make sure OneDrive is synced locally first.)"
    else
        # Write the exact path as an absolute mount line
        # Replace the Linux placeholder line with the resolved absolute path
        ESCAPED=$(echo "$OD_PATH" | sed 's|/|\\/|g')
        # Add an absolute-path mount entry after the last existing mount comment block
        python3 - "$DEVCONTAINER_JSON" "$OD_PATH" <<'PYEOF'
import sys, re

json_file = sys.argv[1]
od_path   = sys.argv[2]

with open(json_file) as f:
    content = f.read()

mount_line = f'    "source={od_path},target=/mnt/onedrive,type=bind,consistency=cached",'
placeholder = '    // Linux — OneDrive via rclone or onedrive client (~/OneDrive)'

if mount_line in content:
    print("  OneDrive mount already present — no change.")
else:
    content = content.replace(placeholder,
        placeholder + '\n' + mount_line)
    with open(json_file, 'w') as f:
        f.write(content)
    print(f"  ✓ OneDrive mounted: {od_path} → /mnt/onedrive")
PYEOF
    fi
fi

# ─── Google Drive ─────────────────────────────────────────────────────────────
echo ""
read -rp "Mount Google Drive? [y/N]: " GD_ANSWER
GD_ANSWER="${GD_ANSWER:-N}"

if [[ "$GD_ANSWER" =~ ^[Yy]$ ]]; then
    if [[ "$OS" == "Darwin" ]]; then
        DEFAULT_GD="$HOME/Google Drive/My Drive"
    else
        if [[ -d "$HOME/GoogleDrive" ]]; then
            DEFAULT_GD="$HOME/GoogleDrive"
        else
            DEFAULT_GD="$HOME/google-drive"
        fi
    fi

    read -rp "Google Drive path [$DEFAULT_GD]: " GD_PATH
    GD_PATH="${GD_PATH:-$DEFAULT_GD}"

    if [[ ! -d "$GD_PATH" ]]; then
        echo "  ⚠  '$GD_PATH' not found — skipping Google Drive mount."
        echo "     (Make sure Google Drive is synced locally first.)"
    else
        python3 - "$DEVCONTAINER_JSON" "$GD_PATH" <<'PYEOF'
import sys

json_file = sys.argv[1]
gd_path   = sys.argv[2]

with open(json_file) as f:
    content = f.read()

mount_line = f'    "source={gd_path},target=/mnt/gdrive,type=bind,consistency=cached",'
placeholder = '    // Linux — Google Drive via rclone or google-drive-ocamlfuse (~/GoogleDrive)'

if mount_line in content:
    print("  Google Drive mount already present — no change.")
else:
    content = content.replace(placeholder,
        placeholder + '\n' + mount_line)
    with open(json_file, 'w') as f:
        f.write(content)
    print(f"  ✓ Google Drive mounted: {gd_path} → /mnt/gdrive")
PYEOF
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Done. Next step:"
echo "  Open VS Code → Ctrl+Shift+P → Dev Containers: Rebuild Container"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
