#!/usr/bin/env python3
"""Summarize Remnawave OpenAPI spec endpoints grouped by tag."""
import json
import sys
from collections import defaultdict

spec = json.load(open("/tmp/openapi.json"))

print(f"Title:    {spec.get('info', {}).get('title')}")
print(f"Version:  {spec.get('info', {}).get('version')}")
paths = spec.get("paths", {})
print(f"Endpoints: {sum(1 for _, m in paths.items() for v in m if v in ['get','post','put','delete','patch'])}")
print()

by_tag = defaultdict(list)
for path, methods in sorted(paths.items()):
    for method, info in methods.items():
        if method not in ("get", "post", "put", "delete", "patch"):
            continue
        tags = info.get("tags") or ["(no-tag)"]
        sec = "AUTH" if info.get("security") else "----"
        for tag in tags:
            by_tag[tag].append(f"{sec} {method.upper():6} {path}")

for tag, lines in sorted(by_tag.items()):
    print(f"=== {tag} ({len(lines)} endpoints) ===")
    for line in lines[:25]:
        print(f"  {line}")
    if len(lines) > 25:
        print(f"  ... and {len(lines) - 25} more")
    print()
