#!/bin/bash
# Read-only recon for Amnezia removal. Does NOT modify anything.

set -uo pipefail

echo "================================================================"
echo "1. Amnezia containers (running + stopped)"
echo "================================================================"
docker ps -a --filter "name=amnezia" --format 'table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}'
echo

echo "================================================================"
echo "2. Amnezia images"
echo "================================================================"
docker images --filter "reference=amnezia-*" --format 'table {{.ID}}\t{{.Repository}}\t{{.Tag}}\t{{.Size}}'
echo

echo "================================================================"
echo "3. Amnezia volumes"
echo "================================================================"
docker volume ls --filter "name=amnezia" --format 'table {{.Name}}\t{{.Driver}}'
echo
echo "Size of amnezia volumes:"
docker system df -v 2>/dev/null | grep -A1 "amnezia" | head -20 || true
echo

echo "================================================================"
echo "4. Amnezia networks (br-* used by amnezia containers)"
echo "================================================================"
for c in $(docker ps -a --filter "name=amnezia" --format '{{.Names}}'); do
  echo "--- $c networks ---"
  docker inspect "$c" --format '{{range $net,$conf := .NetworkSettings.Networks}}{{$net}} {{end}}'
  echo
done
echo

echo "================================================================"
echo "5. Compose project for Amnezia (if any)"
echo "================================================================"
for c in $(docker ps -a --filter "name=amnezia" --format '{{.Names}}' | head -3); do
  proj=$(docker inspect "$c" --format '{{index .Config.Labels "com.docker.compose.project"}}' 2>/dev/null)
  conf=$(docker inspect "$c" --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' 2>/dev/null)
  echo "$c: project='$proj' config='$conf'"
done
echo

echo "================================================================"
echo "6. amn0 network interface and routes"
echo "================================================================"
ip -4 addr show amn0 2>/dev/null || echo "no amn0"
ip route | grep -E "(amn0|172\.29)" || echo "no amn0 routes"
echo

echo "================================================================"
echo "7. /opt/amnezia contents"
echo "================================================================"
ls -la /opt/amnezia/ 2>/dev/null
du -sh /opt/amnezia/* 2>/dev/null
echo

echo "================================================================"
echo "8. systemd units related to amnezia"
echo "================================================================"
systemctl list-units --all 2>/dev/null | grep -i amnezia || echo "no systemd amnezia units"
echo

echo "================================================================"
echo "9. iptables rules referencing amnezia ports (449, 34948, 46212)"
echo "================================================================"
iptables -L INPUT -n --line-numbers 2>/dev/null | grep -E "(449|34948|46212)" || echo "no iptables rules on amnezia ports"
iptables -t nat -L PREROUTING -n --line-numbers 2>/dev/null | grep -E "(449|34948|46212)" || echo "no iptables nat rules"
echo

echo "================================================================"
echo "DONE"
echo "================================================================"
