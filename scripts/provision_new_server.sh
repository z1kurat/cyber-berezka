#!/usr/bin/env bash
# Provision the new Beget VPS (coordinator role).
# Runs ON the server (executed via SSH from apply_full.sh).
# Idempotent — every step checks current state before mutating.
set -euo pipefail

REPO_BASE="${REPO_BASE:-/root/cyber-berezka}"
ENV_FILE="${REPO_BASE}/infra/.env"
HOSTNAME_NEW="berezka-coordinator"

echo "===> [1/10] Apt update + base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg lsb-release rsync ufw openssl

echo "===> [2/10] Hostname -> ${HOSTNAME_NEW}"
if [[ "$(hostname)" != "${HOSTNAME_NEW}" ]]; then
    hostnamectl set-hostname "${HOSTNAME_NEW}"
    if ! grep -q "${HOSTNAME_NEW}" /etc/hosts; then
        echo "127.0.1.1 ${HOSTNAME_NEW}" >> /etc/hosts
    fi
fi

echo "===> [3/10] Install Docker CE if missing"
if ! command -v docker &>/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    UBUNTU_CODENAME=$(lsb_release -cs)
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    echo '{"live-restore": true, "log-driver": "json-file", "log-opts": {"max-size": "100m", "max-file": "5"}}' > /etc/docker/daemon.json
    systemctl restart docker
fi

echo "===> [4/10] 2GB swap file"
if [[ ! -f /swapfile ]]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile >/dev/null
    swapon /swapfile
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
fi

echo "===> [5/10] UFW firewall"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP (Caddy)'
ufw allow 443/tcp comment 'HTTPS (Caddy)'
ufw allow 2053/tcp comment 'Reality (Xray)'
ufw --force enable

echo "===> [6/10] SSH hardening (key-only)"
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true

echo "===> [7/10] Bootstrap .env if missing"
if [[ ! -f "${ENV_FILE}" ]]; then
    cp "${REPO_BASE}/infra/.env.example" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
fi

gen() { openssl rand -base64 32 | tr -d '/+=' | head -c 40; }

fill_if_empty() {
    local key="$1"
    if grep -q "^${key}=$" "${ENV_FILE}"; then
        local val
        val=$(gen)
        sed -i "s|^${key}=$|${key}=${val}|" "${ENV_FILE}"
        echo "     generated ${key}"
    fi
}
fill_if_empty POSTGRES_PASSWORD
fill_if_empty APP_DB_PASSWORD

echo "===> [8/10] systemd-unit for iptables (coordinator)"
cp "${REPO_BASE}/infra/systemd/cyber-berezka-iptables-coordinator.service" /etc/systemd/system/cyber-berezka-iptables.service
systemctl daemon-reload
systemctl enable --now cyber-berezka-iptables.service

echo "===> [9/10] docker compose pull + up"
cd "${REPO_BASE}/infra/compose"
docker compose -f docker-compose.coordinator.yml --env-file "${ENV_FILE}" pull
docker compose -f docker-compose.coordinator.yml --env-file "${ENV_FILE}" up -d --build

echo "===> [10/10] Wait for healthcheck (max 120s)"
for i in {1..40}; do
    UNHEALTHY=$(docker ps --filter "name=^(caddy|site|db-app|site-redis|remnawave|remnawave-db|remnawave-redis)$" --format '{{.Names}}\t{{.Status}}' | grep -v 'healthy' | grep -v 'starting' || true)
    if [[ -z "${UNHEALTHY}" ]]; then
        echo "    all containers healthy"
        break
    fi
    sleep 3
done

docker ps --format 'table {{.Names}}\t{{.Status}}'
echo "===> Provisioning complete on $(hostname)"
