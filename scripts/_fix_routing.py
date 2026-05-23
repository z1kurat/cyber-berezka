#!/usr/bin/env python3
"""Update profile config in DB: route IPv4 destinations through v4-fallback.

Why: previous config sent all traffic to v6-pool, whose outbounds have
sendThrough on an IPv6 address. TCP connecting from an IPv6 source socket
to an IPv4 destination is not possible at the OS level, so all client
traffic to IPv4 destinations (including DNS queries to 1.1.1.1 / 8.8.8.8)
silently failed. This broke domain resolution end-to-end.

Fix: insert a routing rule that catches any IPv4 destination and sends it
to v4-fallback, which has no sendThrough and uses the default IPv4 egress.
IPv6 destinations continue to balance across v6-pool.
"""

import json
import sys

# This is the existing rules order; we are inserting one rule.
# Read existing config from stdin, emit corrected config on stdout.
config = json.load(sys.stdin)

rules = config["routing"]["rules"]

# Build new rule set preserving precedence:
# 1. block private IPs
# 2. RU-only domains → v4-fallback
# 3. NEW: any IPv4 destination → v4-fallback
# 4. any IPv6 destination → v6-pool balancer (default for everything else)
new_rules = []
for rule in rules:
    new_rules.append(rule)
    # Insert IPv4 rule right after the domain-based v4-fallback rule
    if rule.get("outboundTag") == "v4-fallback" and "domain" in rule:
        new_rules.append({
            "type": "field",
            "ip": ["0.0.0.0/0"],
            "outboundTag": "v4-fallback",
        })

config["routing"]["rules"] = new_rules

# Also tighten domainStrategy to IPOnDemand so domains resolve to IP and
# then the IPv4-catch-all rule applies. Otherwise domain destinations bypass
# IP rules. IPIfNonMatch resolves only when no domain rule matched.
config["routing"]["domainStrategy"] = "IPOnDemand"

json.dump(config, sys.stdout, ensure_ascii=False)
