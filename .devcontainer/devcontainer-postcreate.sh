#!/bin/bash
set -e
cd /home/micromamba/app

# Initialize micromamba for this shell
eval "$(micromamba shell hook --shell bash)"

# Now you can activate
micromamba activate texas-env

# Install dependencies
pip install --no-cache-dir baysplinepy baysparpy pygwalker

# Install TEXAS in editable mode
pip install --no-cache-dir -e .

# Fix permissions
sudo chown -R micromamba:micromamba /home/micromamba/app /opt/cmdstan

# Install git-lfs
sudo apt update
sudo apt install -y git-lfs
git lfs update --force

exit 0