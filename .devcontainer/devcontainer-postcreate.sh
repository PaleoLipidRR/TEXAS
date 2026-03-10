#!/bin/bash
set -e
cd /home/micromamba/app

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
