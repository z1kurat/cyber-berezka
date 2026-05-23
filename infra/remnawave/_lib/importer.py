"""apply.py import — dump current Remnawave state to YAML + state.json.

Reads every object type via the API and writes declarative configs so that
a future `apply.py apply` can recreate the same state from the YAML alone.
state.json records the UUID -> name mapping for idempotency.

Currently writes minimal-but-complete fields. Internal IDs and timestamps
that the panel generates are kept in state.json, not YAML — YAML stays
human-friendly.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import RemnawaveClient


def _yaml_dump(data: Any) -> str:
    """Minimal YAML emitter for our nested structures.

    Avoids adding pyyaml as a dependency at this stage. The shapes we emit
    are simple: dicts with string/int/bool/list-of-dict values. If the
    project later needs PyYAML for round-trip editing, we can swap this.
    """
    lines: list[str] = []

    def emit(value: Any, indent: int) -> None:
        prefix = "  " * indent
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, (dict, list)) and v:
                    lines.append(f"{prefix}{k}:")
                    emit(v, indent + 1)
                else:
                    lines.append(f"{prefix}{k}: {_scalar(v)}")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    first = True
                    for k, v in item.items():
                        bullet = "- " if first else "  "
                        first = False
                        if isinstance(v, (dict, list)) and v:
                            lines.append(f"{prefix}{bullet}{k}:")
                            emit(v, indent + 1)
                        else:
                            lines.append(f"{prefix}{bullet}{k}: {_scalar(v)}")
                else:
                    lines.append(f"{prefix}- {_scalar(item)}")
        else:
            lines.append(f"{prefix}{_scalar(value)}")

    emit(data, 0)
    return "\n".join(lines) + "\n"


def _scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    needs_quoting = any(ch in s for ch in ":#\n") or s.strip() != s or s == ""
    if needs_quoting:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def cmd_import(client: RemnawaveClient, out_dir: Path, state_file: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)

    profiles = client.list_profiles()
    squads = client.list_squads()
    nodes = client.list_nodes()
    hosts = client.list_hosts()
    users_resp = client.list_users(size=500)
    users = users_resp.get("users", [])

    profile_uuid_to_name: dict[str, str] = {p["uuid"]: p["name"] for p in profiles}
    inbound_uuid_to_tag: dict[str, str] = {}
    for p in profiles:
        for inb in p.get("inbounds", []) or []:
            inbound_uuid_to_tag[inb["uuid"]] = inb["tag"]
    squad_uuid_to_name: dict[str, str] = {s["uuid"]: s["name"] for s in squads}

    # ---- profile.yaml + raw Xray JSON dumped separately for readability ----
    profile_entries = []
    for p in profiles:
        raw_path = out_dir / f"profile_{_safe_filename(p['name'])}.json"
        raw_path.write_text(json.dumps(p.get("config") or {}, indent=2, ensure_ascii=False) + "\n")
        profile_entries.append({
            "name": p["name"],
            "xray_config_file": raw_path.name,
            "inbound_tags": [inb["tag"] for inb in p.get("inbounds", []) or []],
        })
    (out_dir / "profile.yaml").write_text(_yaml_dump(profile_entries))

    # ---- squads.yaml ----
    squad_entries = []
    for s in squads:
        inbound_tags = [inb["tag"] for inb in s.get("inbounds", []) or []]
        squad_entries.append({
            "name": s["name"],
            "inbound_tags": inbound_tags,
        })
    (out_dir / "squads.yaml").write_text(_yaml_dump(squad_entries))

    # ---- nodes.yaml ----
    node_entries = []
    for n in nodes:
        active_profile = (n.get("activeConfigProfileUuid") or None)
        node_entries.append({
            "name": n["name"],
            "address": n["address"],
            "port": n["port"],
            "country_code": n.get("countryCode"),
            "profile": profile_uuid_to_name.get(active_profile, "Default-Profile"),
            "is_disabled": n.get("isDisabled", False),
            "tags": n.get("tags", []) or [],
        })
    (out_dir / "nodes.yaml").write_text(_yaml_dump(node_entries))

    # ---- hosts.yaml ----
    host_entries = []
    for h in hosts:
        host_entries.append({
            "remark": h.get("remark"),
            "address": h.get("address"),
            "port": h.get("port"),
            "sni": h.get("sni"),
            "fingerprint": h.get("fingerprint"),
            "security_layer": h.get("securityLayer"),
            "inbound_tag": inbound_uuid_to_tag.get(h.get("configProfileInboundUuid") or "", "?"),
        })
    (out_dir / "hosts.yaml").write_text(_yaml_dump(host_entries))

    # ---- users.yaml ----
    user_entries = []
    for u in users:
        squad_names = []
        for sq in (u.get("activeInternalSquads") or []):
            sq_uuid = sq.get("uuid") if isinstance(sq, dict) else sq
            if sq_uuid in squad_uuid_to_name:
                squad_names.append(squad_uuid_to_name[sq_uuid])
        user_entries.append({
            "username": u["username"],
            "email": u.get("email"),
            "expire_at": u.get("expireAt"),
            "traffic_limit_bytes": u.get("trafficLimitBytes", 0),
            "traffic_limit_strategy": u.get("trafficLimitStrategy", "NO_RESET"),
            "status": u.get("status", "ACTIVE"),
            "squads": squad_names,
        })
    (out_dir / "users.yaml").write_text(_yaml_dump(user_entries))

    # ---- state.json (Terraform-style) ----
    state = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "profiles": {p["name"]: {"uuid": p["uuid"]} for p in profiles},
        "inbounds": {
            inb["tag"]: {
                "uuid": inb["uuid"],
                "profile": profile_uuid_to_name.get(inb["profileUuid"], "?"),
            }
            for p in profiles for inb in (p.get("inbounds") or [])
        },
        "squads": {s["name"]: {"uuid": s["uuid"]} for s in squads},
        "nodes": {n["name"]: {"uuid": n["uuid"]} for n in nodes},
        "hosts": {h["remark"]: {"uuid": h["uuid"]} for h in hosts},
        "users": {
            u["username"]: {
                "uuid": u["uuid"],
                "short_uuid": u.get("shortUuid"),
            }
            for u in users
        },
    }
    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")

    print(f"Wrote {len(profiles)} profile(s), {len(squads)} squad(s), {len(nodes)} node(s), "
          f"{len(hosts)} host(s), {len(users)} user(s).")
    print(f"  configs:    {out_dir}")
    print(f"  state.json: {state_file}")
    print()
    print("Generated YAML files (review them, edit, then `apply.py apply` in a future stage):")
    for f in sorted(out_dir.iterdir()):
        print(f"  {f.relative_to(out_dir.parent)}")
    return 0


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
