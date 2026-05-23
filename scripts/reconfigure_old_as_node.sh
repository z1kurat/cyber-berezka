#!/usr/bin/env bash
# Reconfigure old VPS as remote node only.
# Idempotent. Does NOT modify SSH config or root password (per user decision).
set -euo pipefail

REPO_BASE="${REPO_BASE:-/root/cyber-berezka}"
ENV_FILE="${REPO_BASE}/infra/.env"
HOSTNAME_NEW="berezka-node-tw1"

echo "===> [1/6] Hostname -> ${HOSTNAME_NEW}"
if [[ "$(hostname)" != "${HOSTNAME_NEW}" ]]; then
    hostnamectl set-hostname "${HOSTNAME_NEW}"
    if ! grep -q "${HOSTNAME_NEW}" /etc/hosts; then
        echo "127.0.1.1 ${HOSTNAME_NEW}" >> /etc/hosts
    fi
fi

echo "===> [2/6] Restore IPv6 pool"
bash "${REPO_BASE}/scripts/setup_ipv6_addresses.sh"
bash "${REPO_BASE}/scripts/wait_ipv6_ready.sh"

echo "===> [3/6] Install IPv6 persistence systemd-unit"
cp "${REPO_BASE}/infra/systemd/cyber-berezka-ipv6.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cyber-berezka-ipv6.service

echo "===> [4/6] Install iptables persistence systemd-unit (node role)"
cp "${REPO_BASE}/infra/systemd/cyber-berezka-iptables-node.service" /etc/systemd/system/cyber-berezka-iptables.service
systemctl daemon-reload
systemctl enable cyber-berezka-iptables.service
systemctl restart cyber-berezka-iptables.service || true

echo "===> [5/6] Verify env file exists"
if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: ${ENV_FILE} not found. Copy .env.example and set NODE_SECRET_KEY before running."
    exit 1
fi
chmod 600 "${ENV_FILE}"

echo "===> [6/6] docker compose up (node only)"
cd "${REPO_BASE}/infra/compose"
docker compose -f docker-compose.node.yml --env-file "${ENV_FILE}" pull
docker compose -f docker-compose.node.yml --env-file "${ENV_FILE}" up -d

echo "===> Reconfig complete. Status:"
docker ps --format 'table {{.Names}}\t{{.Status}}'
echo "IPv6 addresses:"
ip -6 addr show scope global
