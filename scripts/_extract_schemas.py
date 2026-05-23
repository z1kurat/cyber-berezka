#!/usr/bin/env python3
"""Extract request body schemas for key POST endpoints from Remnawave OpenAPI."""
import json

spec = json.load(open("/tmp/openapi.json"))
components = spec.get("components", {}).get("schemas", {})

INTERESTING_PATHS = [
    ("POST", "/api/auth/login"),
    ("POST", "/api/tokens"),
    ("POST", "/api/users"),
    ("POST", "/api/internal-squads"),
    ("POST", "/api/internal-squads/{uuid}/bulk-actions/add-users"),
    ("POST", "/api/nodes"),
    ("POST", "/api/hosts"),
    ("POST", "/api/config-profiles"),
    ("GET", "/api/system/tools/x25519/generate"),
]

def resolve_ref(ref):
    name = ref.rsplit("/", 1)[-1]
    return components.get(name, {})

def short(obj, level=0):
    if level > 4:
        return "..."
    if not isinstance(obj, dict):
        return obj
    if "$ref" in obj:
        return short(resolve_ref(obj["$ref"]), level + 1)
    props = obj.get("properties")
    if props:
        return {k: short(v, level + 1) for k, v in props.items()}
    if obj.get("type") == "array":
        return [short(obj.get("items", {}), level + 1)]
    return {k: obj.get(k) for k in ("type", "enum", "format", "example") if k in obj}

paths = spec["paths"]
for method, path in INTERESTING_PATHS:
    op = paths.get(path, {}).get(method.lower())
    if not op:
        print(f"=== {method} {path}  (NOT FOUND) ===\n")
        continue
    print(f"=== {method} {path} ===")
    summary = op.get("summary", "")
    if summary:
        print(f"  summary: {summary}")

    rb = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
    if rb:
        print("  request body:")
        print(json.dumps(short(rb), indent=4, ensure_ascii=False)[:1500])

    resp = op.get("responses", {}).get("200") or op.get("responses", {}).get("201")
    if resp:
        rs = resp.get("content", {}).get("application/json", {}).get("schema")
        if rs:
            print("  response (200/201):")
            print(json.dumps(short(rs), indent=4, ensure_ascii=False)[:800])
    print()
