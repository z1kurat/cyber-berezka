#!/usr/bin/env python3
"""Generate Xray outbounds + routing config for per-connection IPv6 rotation.

Reads IPv6 addresses from stdin (one per line, '#' starts a comment),
emits a JSON document with:

  - one 'freedom' outbound per IPv6 (tag: v6-0000, v6-0001, ...)
  - one IPv4 fallback outbound (tag: v4-fallback)
  - one direct outbound and one blackhole outbound (standard hygiene)
  - 'routing' block with a random balancer over v6 outbounds and rules
    that send IPv4-only destinations through the fallback.

Why this design:
  The pool size is dynamic - Timeweb provides individual /128 addresses
  that come and go through the UI. Hardcoding outbounds is brittle.
  Random balancing across all currently-assigned IPv6 addresses spreads
  egress fingerprints, mitigating per-IP reputation accumulation
  (research doc, sections 7.10 and 7.13).

Usage:
  scripts/detect_ipv6_pool.sh | scripts/generate_xray_outbounds.py
  scripts/detect_ipv6_pool.sh | scripts/generate_xray_outbounds.py --merge config.json

Exit codes:
  0 - success
  1 - empty pool on stdin
  2 - invalid input (malformed IPv6 etc.)
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import sys
from typing import Any

IPV4_ONLY_DOMAINS: list[str] = [
    "geosite:category-gov-ru",
    "domain:gosuslugi.ru",
    "domain:nalog.gov.ru",
    "domain:sberbank.ru",
    "domain:vtb.ru",
    "domain:tinkoff.ru",
    "domain:alfabank.ru",
]


def make_v6_outbound(addr: str, tag: str) -> dict[str, Any]:
    return {
        "tag": tag,
        "protocol": "freedom",
        "settings": {"domainStrategy": "UseIPv6"},
        "sendThrough": addr,
    }


def make_v4_fallback() -> dict[str, Any]:
    return {
        "tag": "v4-fallback",
        "protocol": "freedom",
        "settings": {"domainStrategy": "UseIPv4"},
    }


def make_direct() -> dict[str, Any]:
    return {
        "tag": "direct",
        "protocol": "freedom",
        "settings": {},
    }


def make_blackhole() -> dict[str, Any]:
    return {
        "tag": "block",
        "protocol": "blackhole",
        "settings": {},
    }


def validate_pool(raw: list[str]) -> list[str]:
    out: list[str] = []
    for line in raw:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            addr = ipaddress.IPv6Address(line)
        except ValueError as exc:
            print(f"ERROR: not a valid IPv6 address: {line!r} ({exc})", file=sys.stderr)
            raise SystemExit(2) from exc
        if addr.is_link_local or addr.is_loopback or addr.is_multicast:
            print(f"ERROR: address {addr} is not global-scope (link-local/loopback/multicast)", file=sys.stderr)
            raise SystemExit(2)
        out.append(str(addr))
    return out


def build_config(ipv6_pool: list[str]) -> dict[str, Any]:
    outbounds: list[dict[str, Any]] = []
    v6_tags: list[str] = []
    for idx, addr in enumerate(ipv6_pool):
        tag = f"v6-{idx:04d}"
        outbounds.append(make_v6_outbound(addr, tag))
        v6_tags.append(tag)

    outbounds.append(make_v4_fallback())
    outbounds.append(make_direct())
    outbounds.append(make_blackhole())

    # IPOnDemand resolves domains to IPs before applying rules. The catch-all
    # rules below route by destination IP family:
    #   IPv6 dest -> v6-pool (rotating /128 sendThrough across the pool)
    #   IPv4 dest -> v4-fallback (single shared IPv4, no sendThrough)
    #
    # IPv6 catch-all MUST come before the IPv4 catch-all. For dual-stack
    # domains (both A and AAAA), Xray's matching prefers the rule that
    # matches first; putting IPv6 first means dual-stack domains use v6-pool,
    # i.e., IPv6 rotation. If we ordered IPv4 first, ifconfig.io and similar
    # AAAA-capable sites would silently end up on v4-fallback - the whole
    # point of IPv6 rotation would be lost. See pitfalls doc §V.2.
    routing: dict[str, Any] = {
        "domainStrategy": "IPOnDemand",
        "balancers": [
            {
                "tag": "v6-pool",
                "selector": ["v6-"],
                "strategy": {"type": "random"},
            }
        ],
        "rules": [
            {
                "type": "field",
                "ip": ["geoip:private"],
                "outboundTag": "block",
            },
            {
                "type": "field",
                "domain": IPV4_ONLY_DOMAINS,
                "outboundTag": "v4-fallback",
            },
            {
                "type": "field",
                "ip": ["::/0"],
                "balancerTag": "v6-pool",
            },
            {
                "type": "field",
                "ip": ["0.0.0.0/0"],
                "outboundTag": "v4-fallback",
            },
        ],
    }

    return {"outbounds": outbounds, "routing": routing}


def merge_into_config(base: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    merged["outbounds"] = generated["outbounds"]
    merged["routing"] = generated["routing"]
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--merge",
        metavar="PATH",
        help="Read existing Xray config from PATH, overwrite its outbounds+routing, emit full config",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indent (default: 2; use 0 for single-line)",
    )
    args = parser.parse_args()

    raw_lines = sys.stdin.read().splitlines()
    pool = validate_pool(raw_lines)

    if not pool:
        print("ERROR: empty IPv6 pool on stdin (no addresses to balance over)", file=sys.stderr)
        return 1

    generated = build_config(pool)

    if args.merge:
        try:
            with open(args.merge, encoding="utf-8") as f:
                base = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: cannot read base config {args.merge!r}: {exc}", file=sys.stderr)
            return 2
        output = merge_into_config(base, generated)
    else:
        output = generated

    json.dump(output, sys.stdout, indent=args.indent or None, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
