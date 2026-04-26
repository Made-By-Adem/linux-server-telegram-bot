#!/usr/bin/env bash
# Migrate the legacy ./config.yaml location to ./config/config.yaml.
#
# 2.x bind-mounted ./config.yaml as a single file in Docker. That mount
# breaks when an editor (vim, etc.) replaces the host file via atomic
# rename: subsequent writes from the bot then go to an orphaned inode
# and never reach the host. 2.1 mounts the ./config/ directory instead,
# which is robust against atomic renames.
#
# Run this once on the host before `docker compose up -d` after pulling
# the new layout. Idempotent: no-op if already migrated.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f config/config.yaml ]; then
    echo "config/config.yaml already exists - nothing to migrate."
    exit 0
fi

if [ ! -f config.yaml ]; then
    echo "No config.yaml found at repo root. If this is a fresh install,"
    echo "copy config.example.yaml to config/config.yaml and edit it."
    exit 0
fi

mkdir -p config
mv config.yaml config/config.yaml
echo "Migrated config.yaml -> config/config.yaml"
echo "Now run: docker compose up -d"
