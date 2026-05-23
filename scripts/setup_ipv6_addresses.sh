#!/bin/bash
# Apply a list of IPv6 addresses to a network interface.
#
# Why: Timeweb registers additional IPv6 addresses in its control panel but
# does not push them to the guest OS. On a reboot only the base address
# survives. This script reads the desired pool from a file and binds each
# entry to the interface, so the pool persists across reboots when invoked
# from a systemd unit at boot time.
#
# Idempotent: running twice is safe. 'ip -6 addr add' returns nonzero if the
# address already exists, which is treated as a no-op.
#
# Usage:
#   IPV6_LIST_FILE=/etc/cyber-berezka/ipv6-pool.txt INTERFACE=eth0 \
#     ./setup_ipv6_addresses.sh
#
# File format:
#   One IPv6 address per line. Lines beginning with '#' and blank lines
#   are ignored. Example:
#     2a03:6f02::c8af
#     2a03:6f02::c8ba
#     2a03:6f02::c8c0
#
# Exit codes:
#   0  - success (at least one address applied or already present)
#   2  - misconfiguration (file missing, interface absent, malformed input)

set -euo pipefail

INTERFACE="${INTERFACE:-eth0}"
IPV6_LIST_FILE="${IPV6_LIST_FILE:-/etc/cyber-berezka/ipv6-pool.txt}"

if ! command -v ip >/dev/null 2>&1; then
  echo "ERROR: 'ip' command not found (install iproute2)" >&2
  exit 2
fi

if [[ ! -f "$IPV6_LIST_FILE" ]]; then
  echo "ERROR: list file not found: $IPV6_LIST_FILE" >&2
  exit 2
fi

if ! ip -6 addr show "$INTERFACE" >/dev/null 2>&1; then
  echo "ERROR: interface '$INTERFACE' not found" >&2
  exit 2
fi

added=0
existed=0
malformed=0

while IFS= read -r line; do
  ip_addr=$(echo "$line" | tr -d '[:space:]')
  [[ -z "$ip_addr" || "$ip_addr" == \#* ]] && continue
  if [[ ! "$ip_addr" =~ : ]]; then
    echo "WARN: skipping malformed entry: $ip_addr" >&2
    malformed=$((malformed + 1))
    continue
  fi
  if ip -6 addr add "${ip_addr}/128" dev "$INTERFACE" 2>/dev/null; then
    echo "added $ip_addr"
    added=$((added + 1))
  else
    echo "exists $ip_addr"
    existed=$((existed + 1))
  fi
done < "$IPV6_LIST_FILE"

echo "Summary: $added added, $existed already present, $malformed skipped (interface $INTERFACE)"

if [[ $added -eq 0 && $existed -eq 0 ]]; then
  echo "ERROR: no addresses applied or recognized in $IPV6_LIST_FILE" >&2
  exit 2
fi
