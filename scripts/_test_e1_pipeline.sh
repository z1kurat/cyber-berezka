#!/bin/bash
# Acceptance test for E1 (setup + wait_ipv6_ready). Run on the VPS.
# Simulates a cold boot: removes pool addresses, calls setup to re-add them,
# then calls wait_ipv6_ready and reports the result.

set -uo pipefail

echo "=== Uploaded files ==="
ls -la /root/cyber-berezka/scripts/ /tmp/cyber-berezka-ipv6.service 2>/dev/null || true
echo

echo "=== Cold-boot simulation: remove pool addresses from eth0 ==="
for ip in 2a03:6f02::c8af 2a03:6f02::c8ba 2a03:6f02::c8c0; do
  if ip -6 addr del "${ip}/128" dev eth0 2>/dev/null; then
    echo "removed $ip"
  else
    echo "was not present: $ip"
  fi
done
echo

echo "=== Negative test: wait should exit non-zero quickly (no pool applied yet) ==="
WAIT_TOTAL_S=15 WAIT_INTERVAL_S=5 bash /root/cyber-berezka/scripts/wait_ipv6_ready.sh
echo "negative-test exit=$?"
echo

echo "=== Positive flow: setup_ipv6_addresses.sh re-applies pool ==="
bash /root/cyber-berezka/scripts/setup_ipv6_addresses.sh
echo

echo "=== Positive flow: wait_ipv6_ready.sh with realistic budget (180s) ==="
WAIT_TOTAL_S=180 WAIT_INTERVAL_S=20 bash /root/cyber-berezka/scripts/wait_ipv6_ready.sh
echo "positive-test exit=$?"
echo

echo "=== Final state ==="
bash /root/cyber-berezka/scripts/detect_ipv6_pool.sh
