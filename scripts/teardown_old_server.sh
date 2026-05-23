#!/usr/bin/env bash
# Teardown coordinator stack on the old Timeweb VPS.
# Removes only our containers; never touches non-project services
# (3X-UI, CRM_AI, MTProto, Squid, 3proxy, Zabbix).
set -euo pipefail

echo "===> Detecting our stack containers"
OUR_CONTAINERS=(caddy site db-app site-redis remnawave remnawave-db remnawave-redis)

for name in "${OUR_CONTAINERS[@]}"; do
    if docker ps -a --format '{{.Names}}' | grep -qx "${name}"; then
        echo "    stopping ${name}"
        docker stop "${name}" || true
        docker rm "${name}" || true
    fi
done

echo "===> Removing our volumes"
for vol in caddy-data caddy-config db-app-data remnawave-db-data valkey-socket; do
    if docker volume ls --format '{{.Name}}' | grep -qx "${vol}"; then
        docker volume rm "${vol}" || true
    fi
done

echo "===> Removing remnawave-network if no other containers attached"
if docker network ls --format '{{.Name}}' | grep -qx remnawave-network; then
    if [[ -z "$(docker network inspect remnawave-network --format '{{range .Containers}}{{.Name}}{{end}}' || true)" ]]; then
        docker network rm remnawave-network || true
    fi
fi

echo "===> Pruning dangling images"
docker image prune -af

echo "===> Teardown complete. Remaining containers (third-party — not touched):"
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
