#!/bin/bash

# Find the directory where this script is located
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# Define the project root, which is one level up from the /scripts directory
export PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

# Export your user and group IDs for file permissions
export HOST_UID=$(id -u)
export HOST_GID=$(id -g)

# Run docker-compose, explicitly pointing to the project directory and compose file.
# This makes the script reliable, no matter where you run it from.
docker compose \
  --project-directory "$PROJECT_ROOT" \
  -f "$PROJECT_ROOT/docker/docker-compose.yml" \
  --profile phylo \
  "$@"