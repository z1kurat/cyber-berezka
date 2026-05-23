#!/usr/bin/env bash
# Sync local repo (infra/, scripts/, docs/) to a remote server via rsync.
# Idempotent — only modified files are transferred.
#
# Usage: scripts/sync_repo_to_server.sh <host>
# Example: scripts/sync_repo_to_server.sh 212.74.231.217
set -euo pipefail

HOST="${1:?Usage: $0 <host>}"
REMOTE_BASE="${REMOTE_BASE:-/root/cyber-berezka}"
LOCAL_BASE="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Sync ${LOCAL_BASE} -> root@${HOST}:${REMOTE_BASE}"

ssh "root@${HOST}" "mkdir -p ${REMOTE_BASE}"

rsync -avz --delete \
    --exclude '.git/' \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    --exclude 'node_modules/' \
    --exclude 'tmp/' \
    --exclude 'infra/.env' \
    --exclude 'infra/remnawave/state.json' \
    --exclude 'tests/' \
    "${LOCAL_BASE}/infra" \
    "${LOCAL_BASE}/scripts" \
    "${LOCAL_BASE}/docs" \
    "root@${HOST}:${REMOTE_BASE}/"

echo "==> Sync complete"
