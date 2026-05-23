#!/bin/bash
set -u

echo "=== Find xray internal socket and token from Xray cmdline ==="
SOCK=$(ls /run/remnawave-internal-*.sock 2>/dev/null | head -1)
echo "socket: $SOCK"

CMDLINE=$(docker exec remnanode sh -c 'cat /proc/$(pgrep -f "xray run" | head -1)/cmdline 2>/dev/null' | tr '\0' ' ')
echo "xray cmdline: $CMDLINE"

TOKEN=$(echo "$CMDLINE" | grep -oE 'token=[A-Za-z0-9]+' | head -1 | cut -d= -f2)
echo "token prefix: ${TOKEN:0:20}..."

if [ -n "$SOCK" ] && [ -n "$TOKEN" ]; then
  echo
  echo "=== Current running Xray config ==="
  docker exec remnanode sh -c "curl -s --unix-socket '$SOCK' 'http://internal/internal/get-config?token=$TOKEN'" \
    | python3 -m json.tool 2>/dev/null | head -150 \
    || echo "couldn't parse JSON, raw output (first 1000 chars):" \
    && docker exec remnanode sh -c "curl -s --unix-socket '$SOCK' 'http://internal/internal/get-config?token=$TOKEN'" | head -c 1500
fi

echo
echo "=== Active established connections to :2053 ==="
ss -tn state established 2>/dev/null | grep ':2053' | head -5

echo
echo "=== Xray stdout log (look for 'accepted' lines) — last 30 ==="
docker exec remnanode tail -30 /var/log/supervisor/xray.out.log
