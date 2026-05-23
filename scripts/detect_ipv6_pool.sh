#!/bin/bash
# Detect IPv6 pool on a network interface and print one address per line.
#
# Why: Xray outbound configuration is generated dynamically from the pool
# of IPv6 addresses currently assigned to eth0. This avoids hardcoding the
# pool and lets us add addresses via the provider UI without touching code.
#
# Usage:
#   ./detect_ipv6_pool.sh                  # uses defaults
#   INTERFACE=eth1 PREFIX=2a01:4f8:: ./detect_ipv6_pool.sh
#
# Output: one IPv6 address per line, scope-global, matching PREFIX.
# Exit codes: 0 on success (even if zero matches), 2 on invalid usage.

set -euo pipefail

INTERFACE="${INTERFACE:-eth0}"
PREFIX="${PREFIX:-2a03:6f02::}"

if ! command -v ip >/dev/null 2>&1; then
  echo "ERROR: 'ip' command not found (install iproute2)" >&2
  exit 2
fi

if ! ip -6 addr show "$INTERFACE" >/dev/null 2>&1; then
  echo "ERROR: interface '$INTERFACE' not found" >&2
  exit 2
fi

ip -6 addr show "$INTERFACE" | awk -v prefix="$PREFIX" '
  /inet6/ && /scope global/ {
    split($2, parts, "/")
    addr = parts[1]
    if (index(addr, prefix) == 1) {
      print addr
    }
  }
'
