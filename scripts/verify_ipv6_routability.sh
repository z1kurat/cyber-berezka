#!/bin/bash
# Filter IPv6 addresses from stdin to only those that actually route.
#
# Why: detect_ipv6_pool.sh only sees what is currently bound to the interface.
# An address can be bound via 'ip -6 addr add' yet not be routed by the
# upstream provider (Timeweb only routes addresses registered through their
# UI). Traffic from an unrouted address is silently dropped, which in Xray
# becomes timeouts on a fraction of user connections.
#
# This script tests each address by making an outbound HTTPS request bound
# to it as source IP. If the echo service returns the same address we sent
# from, routing is confirmed.
#
# Slow on purpose: ~1-3 seconds per address. Run at startup or when the
# pool changes, not on every connection.
#
# Usage:
#   detect_ipv6_pool.sh | verify_ipv6_routability.sh | generate_xray_outbounds.py
#
# Env:
#   VERIFY_TARGET   probe URL (default: https://api64.ipify.org)
#   VERIFY_TIMEOUT  seconds per probe (default: 5)

set -euo pipefail

VERIFY_TARGET="${VERIFY_TARGET:-https://api64.ipify.org}"
VERIFY_TIMEOUT="${VERIFY_TIMEOUT:-5}"

routable=0
dropped=0

while IFS= read -r line; do
  ip=$(echo "$line" | tr -d '[:space:]')
  [[ -z "$ip" || "$ip" == \#* ]] && continue
  observed=$(timeout "$VERIFY_TIMEOUT" curl -s -6 --interface "$ip" "$VERIFY_TARGET" 2>/dev/null || true)
  if [ "$observed" = "$ip" ]; then
    echo "$ip"
    routable=$((routable + 1))
  else
    echo "DROP $ip (observed: ${observed:-TIMEOUT})" >&2
    dropped=$((dropped + 1))
  fi
done

echo "verify_ipv6_routability: $routable routable, $dropped dropped" >&2
