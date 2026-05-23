#!/bin/bash
# Read-only inventory of the VPS before installing Remnawave alongside Amnezia.
# Does NOT modify anything.

set -uo pipefail

echo "===================================================================="
echo "1. OS and kernel"
echo "===================================================================="
cat /etc/os-release | grep -E '^(NAME|VERSION)='
uname -r
echo

echo "===================================================================="
echo "2. CPU / RAM / Disk"
echo "===================================================================="
echo "--- CPU ---"
grep -c ^processor /proc/cpuinfo
echo
echo "--- RAM ---"
free -h
echo
echo "--- Disk usage ---"
df -h / /var /tmp 2>/dev/null
echo
echo "--- Top 10 largest directories in /var ---"
du -h --max-depth=2 /var 2>/dev/null | sort -rh | head -10
echo
echo "--- Top 5 largest dirs in /var/lib/docker (if exists) ---"
[ -d /var/lib/docker ] && du -h --max-depth=2 /var/lib/docker 2>/dev/null | sort -rh | head -10 || echo "no /var/lib/docker"
echo

echo "===================================================================="
echo "3. Docker — what is running"
echo "===================================================================="
echo "--- docker info (size) ---"
docker system df 2>/dev/null || echo "docker not available?"
echo
echo "--- docker ps ---"
docker ps --format 'table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Names}}' 2>/dev/null
echo
echo "--- docker compose projects ---"
docker compose ls 2>/dev/null || true
echo

echo "===================================================================="
echo "4. Listening ports (TCP + UDP, with process name)"
echo "===================================================================="
ss -tulnp 2>/dev/null | head -40
echo

echo "===================================================================="
echo "5. systemd services (enabled, top user-relevant)"
echo "===================================================================="
systemctl list-unit-files --state=enabled --type=service 2>/dev/null | grep -E '^(amnezia|docker|ssh|ufw|fail2ban|nginx|caddy|postgres|redis)' || echo "no relevant matches"
echo

echo "===================================================================="
echo "6. Amnezia footprint"
echo "===================================================================="
ls -la /opt/amnezia 2>/dev/null | head -5 || echo "no /opt/amnezia"
ls -la /etc/amnezia 2>/dev/null | head -5 || echo "no /etc/amnezia"
which amnezia 2>/dev/null || echo "no amnezia binary in PATH"
echo

echo "===================================================================="
echo "7. Network interfaces summary"
echo "===================================================================="
ip -4 addr show | grep -E "^[0-9]+:|inet " | head -20
echo
ip -6 addr show eth0 | grep "inet6 2a03"
echo

echo "===================================================================="
echo "8. Firewall (ufw / iptables)"
echo "===================================================================="
ufw status 2>/dev/null | head -5 || echo "ufw not active or not installed"
echo
iptables -L INPUT -n --line-numbers 2>/dev/null | head -10
echo

echo "===================================================================="
echo "9. SSH configuration"
echo "===================================================================="
grep -E '^(PermitRootLogin|PasswordAuthentication|Port)' /etc/ssh/sshd_config 2>/dev/null
echo

echo "===================================================================="
echo "10. /etc/cyber-berezka — what's already there"
echo "===================================================================="
ls -la /etc/cyber-berezka 2>/dev/null
cat /etc/cyber-berezka/ipv6-pool.txt 2>/dev/null
echo

echo "===================================================================="
echo "DONE"
echo "===================================================================="
