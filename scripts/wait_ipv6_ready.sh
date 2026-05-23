#!/bin/bash
# Wait until all IPv6 addresses in the pool are routable by the upstream router.
#
# Why: After 'ip -6 addr del' + 'ip -6 addr add' (which happens on every reboot
# when setup_ipv6_addresses.sh re-applies the pool), Timeweb's upstream router
# needs roughly 60-120 seconds to refresh its ND/MAC cache. During that window
# outgoing packets with these source IPs are silently dropped. Starting Xray
# immediately would route 25-75% of user connections through unroutable IPs
# until the cache catches up.
#
# This script polls each address from the pool with curl. It exits 0 only when
# ALL addresses are routable, or non-zero if the overall WAIT_TOTAL_S budget
# is exhausted. It is meant to run in ExecStartPre of a systemd unit before
# the container manager starts the Xray node.
#
# Idempotent: safe to invoke any time.
#
# Usage:
#   /root/cyber-berezka/scripts/wait_ipv6_ready.sh
#   WAIT_TOTAL_S=600 ./wait_ipv6_ready.sh
#
# Env:
#   IPV6_LIST_FILE   default /etc/cyber-berezka/ipv6-pool.txt
#   WAIT_TOTAL_S     overall timeout in seconds (default 300)
#   WAIT_INTERVAL_S  poll interval in seconds (default 15)
#   VERIFY_TARGET    probe URL (default https://api64.ipify.org)
#   VERIFY_TIMEOUT   per-curl timeout in seconds (default 5)
#
# Exit codes:
#   0 - all addresses routable
#   1 - timeout: some addresses never became routable
#   2 - misconfiguration (file missing, empty pool, etc.)

set -euo pipefail

IPV6_LIST_FILE="${IPV6_LIST_FILE:-/etc/cyber-berezka/ipv6-pool.txt}"
WAIT_TOTAL_S="${WAIT_TOTAL_S:-300}"
WAIT_INTERVAL_S="${WAIT_INTERVAL_S:-15}"
VERIFY_TARGET="${VERIFY_TARGET:-https://api64.ipify.org}"
VERIFY_TIMEOUT="${VERIFY_TIMEOUT:-5}"

if [[ ! -f "$IPV6_LIST_FILE" ]]; then
  echo "ERROR: list file not found: $IPV6_LIST_FILE" >&2
  exit 2
fi

addresses=()
while IFS= read -r line; do
  ip_addr=$(echo "$line" | tr -d '[:space:]')
  [[ -z "$ip_addr" || "$ip_addr" == \#* ]] && continue
  addresses+=("$ip_addr")
done < "$IPV6_LIST_FILE"

if [[ ${#addresses[@]} -eq 0 ]]; then
  echo "ERROR: no IPv6 addresses in $IPV6_LIST_FILE" >&2
  exit 2
fi

total=${#addresses[@]}
echo "Waiting for $total IPv6 address(es) to become routable (budget ${WAIT_TOTAL_S}s)" >&2

deadline=$(($(date +%s) + WAIT_TOTAL_S))
attempt=0

while [[ $(date +%s) -lt $deadline ]]; do
  attempt=$((attempt + 1))
  ok=0
  for ip_addr in "${addresses[@]}"; do
    observed=$(timeout "$VERIFY_TIMEOUT" curl -s -6 --interface "$ip_addr" "$VERIFY_TARGET" 2>/dev/null || true)
    if [[ "$observed" == "$ip_addr" ]]; then
      ok=$((ok + 1))
    fi
  done
  if [[ $ok -eq $total ]]; then
    echo "All $total address(es) routable (attempt $attempt)" >&2
    exit 0
  fi
  remaining=$((deadline - $(date +%s)))
  echo "Attempt $attempt: $ok/$total routable; remaining budget ${remaining}s; sleeping ${WAIT_INTERVAL_S}s" >&2
  sleep "$WAIT_INTERVAL_S"
done

echo "ERROR: timeout after ${WAIT_TOTAL_S}s; only $ok/$total address(es) became routable" >&2
exit 1
