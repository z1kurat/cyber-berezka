"""Print actual response shape for list endpoints."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/root/cyber-berezka/infra/remnawave")
for line in Path("/root/cyber-berezka/infra/.env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v)

from _lib.client import RemnawaveClient  # noqa: E402

with RemnawaveClient() as c:
    for path in ("/api/config-profiles", "/api/internal-squads", "/api/nodes", "/api/hosts", "/api/users"):
        print(f"\n=== GET {path} ===")
        raw = c.get(path, params={"size": 100, "start": 0} if "users" in path else None)
        print(f"type: {type(raw).__name__}")
        if isinstance(raw, dict):
            print(f"keys: {list(raw.keys())}")
            for k, v in raw.items():
                preview = type(v).__name__
                if isinstance(v, list):
                    preview += f" len={len(v)}"
                    if v and isinstance(v[0], dict):
                        preview += f" sample_keys={list(v[0].keys())[:8]}"
                print(f"  {k}: {preview}")
        elif isinstance(raw, list):
            print(f"len: {len(raw)}")
            if raw and isinstance(raw[0], dict):
                print(f"sample_keys: {list(raw[0].keys())[:10]}")
            else:
                print(f"sample: {raw[:2]}")
