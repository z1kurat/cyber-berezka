#!/bin/bash
# Remove Amnezia VPN stack from the VPS.
# Touches ONLY containers/images/networks/files named amnezia-*
# and an iptables rule referencing UDP 46212. Does NOT touch 3X-UI,
# CRM_AI, telegram bots, or any other workload on this host.

set -uo pipefail

section() { echo; echo "=== $1 ==="; }

section "Pre-state: list amnezia containers"
docker ps -a --filter "name=amnezia" --format '{{.Names}} ({{.Status}})'

section "Step 1: stop containers"
docker stop amnezia-awg amnezia-xray amnezia-wireguard amnezia-dns 2>&1 || true

section "Step 2: remove containers"
docker rm amnezia-awg amnezia-xray amnezia-wireguard amnezia-dns 2>&1 || true

section "Step 3: remove docker network amnezia-dns-net"
docker network rm amnezia-dns-net 2>&1 || true

section "Step 4: remove amnezia images"
docker rmi amnezia-awg:latest amnezia-xray:latest amnezia-wireguard:latest amnezia-dns:latest 2>&1 || true

section "Step 5: remove amn0 host interface (if remains)"
if ip link show amn0 >/dev/null 2>&1; then
  ip link delete amn0 && echo "amn0 deleted" || echo "amn0 delete failed"
else
  echo "amn0 already gone"
fi

section "Step 6: remove /opt/amnezia config dir"
if [ -d /opt/amnezia ]; then
  rm -rf /opt/amnezia && echo "/opt/amnezia removed"
else
  echo "/opt/amnezia already absent"
fi

section "Step 7: remove iptables rule for udp/46212"
iptables -D INPUT -p udp --dport 46212 -j ACCEPT 2>&1 && echo "iptables rule removed" || echo "iptables rule already absent or could not remove"

section "Step 8a: verify amnezia containers gone"
remaining=$(docker ps -a --filter "name=amnezia" --format '{{.Names}}' | wc -l)
if [ "$remaining" -eq 0 ]; then
  echo "OK: no amnezia containers"
else
  echo "FAIL: $remaining amnezia container(s) still present"
  docker ps -a --filter "name=amnezia"
fi

section "Step 8b: verify amnezia ports released"
ports_taken=$(ss -tulnp 2>/dev/null | grep -E ":(449|34948|46212) " | wc -l)
if [ "$ports_taken" -eq 0 ]; then
  echo "OK: ports 449, 34948, 46212 released"
else
  echo "FAIL: some ports still bound:"
  ss -tulnp 2>/dev/null | grep -E ":(449|34948|46212) "
fi

section "Step 8c: verify amn0 gone"
ip link show amn0 >/dev/null 2>&1 && echo "FAIL: amn0 still exists" || echo "OK: amn0 absent"

section "Step 8d: verify /opt/amnezia gone"
[ -d /opt/amnezia ] && echo "FAIL: /opt/amnezia still exists" || echo "OK: /opt/amnezia absent"

section "Step 8e: verify amnezia images gone"
imgs=$(docker images --filter "reference=amnezia-*" --format '{{.Repository}}' | wc -l)
if [ "$imgs" -eq 0 ]; then
  echo "OK: no amnezia images"
else
  echo "FAIL: $imgs amnezia image(s) still present"
  docker images --filter "reference=amnezia-*"
fi

section "Step 8f: SAFETY check — 3X-UI and CRM_AI must still be up"
echo "--- x-ui process ---"
pgrep -af x-ui | head -3 || echo "WARNING: x-ui not running"
echo "--- 3X-UI ports (28900, 2096) ---"
ss -tlnp 2>/dev/null | grep -E ":(28900|2096) " || echo "WARNING: 3X-UI ports not bound"
echo "--- CRM_AI containers ---"
docker ps --filter "name=ait" --filter "name=funnel" --format 'table {{.Names}}\t{{.Status}}'

section "Free disk after cleanup"
df -h /

section "DONE"
