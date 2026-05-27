#!/usr/bin/env python3
"""apply.py — Declarative Remnawave provisioning.

Stage 2 (this commit): read-only `status` command that calls the Remnawave
REST API and prints current state. Bootstrap requires REMNAWAVE_API_URL
and REMNAWAVE_API_TOKEN in the environment (typically loaded from .env).

Design: docs/superpowers/specs/2026-05-17-apply-py-design.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add _lib/ to sys.path so we can import without installing the package.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _lib.client import RemnawaveClient, RemnawaveError  # noqa: E402


def _load_env_file(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE per line. Skips comments and blanks.

    Does not interpolate, does not strip quotes — values are taken verbatim
    after the first '='. Good enough for our .env where secrets are hex/base64.
    """
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        # Only set if not already in environment so explicit env wins.
        import os
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value


def _print_section(title: str, rows: list[tuple[str, str]]) -> None:
    print(f"\n=== {title} ({len(rows)}) ===")
    if not rows:
        print("  (none)")
        return
    width = max((len(k) for k, _ in rows), default=0)
    for key, val in rows:
        print(f"  {key:<{width}}  {val}")


def cmd_status(client: RemnawaveClient) -> int:
    try:
        health = client.health()
        print(f"Panel health: {health}")
    except RemnawaveError as exc:
        print(f"Panel /health failed: {exc}", file=sys.stderr)
        return 2

    try:
        profiles = client.list_profiles()
        squads = client.list_squads()
        nodes = client.list_nodes()
        hosts = client.list_hosts()
        users_resp = client.list_users(size=200)
    except RemnawaveError as exc:
        print(f"API call failed: {exc}", file=sys.stderr)
        return 2

    # Profiles
    rows = [(p.get("name", "?"), p.get("uuid", "?")) for p in (profiles or [])]
    _print_section("Config Profiles", rows)

    # Squads
    rows = []
    for s in squads or []:
        info = s.get("info") or {}
        rows.append((
            s.get("name", "?"),
            f"members={info.get('membersCount', '?')}, inbounds={info.get('inboundsCount', '?')}, uuid={s.get('uuid','?')}",
        ))
    _print_section("Internal Squads", rows)

    # Nodes
    rows = []
    for n in nodes or []:
        connected = n.get("isConnected")
        flag = "✓" if connected else ("…" if n.get("isConnecting") else "✗")
        rows.append((
            f"{flag} {n.get('name', '?')}",
            f"{n.get('address', '?')}:{n.get('port', '?')} country={n.get('countryCode','?')}",
        ))
    _print_section("Nodes", rows)

    # Hosts
    rows = []
    for h in hosts or []:
        rows.append((
            h.get("remark", "?"),
            f"{h.get('address', '?')}:{h.get('port', '?')} sni={h.get('sni','?')}",
        ))
    _print_section("Hosts", rows)

    # Users
    total = 0
    rows = []
    if isinstance(users_resp, dict):
        total = users_resp.get("total", 0)
        for u in users_resp.get("users", []):
            rows.append((
                u.get("username", "?"),
                f"status={u.get('status','?')} short={u.get('shortUuid','?')}",
            ))
    _print_section(f"Users (total={total})", rows)

    return 0


def cmd_apply_protection_modes(client, template_file):
    """Идемпотентная установка инфраструктуры для «Полной» / «Умной защиты».

    1. Создать subscription-template smart_routing (если нет).
    2. Создать internal squad Mode-Smart (если нет).
    3. Для каждого существующего host'а: создать smart-копию (если нет),
       обновить excludedInternalSquads на full-host'ах.

    Печатает финальные UUID'ы для добавления в .env.
    """
    import json as _json

    DEFAULT_SQUAD_NAME = "Default-Squad"
    SMART_SQUAD_NAME = "Mode-Smart"
    SMART_TEMPLATE_NAME = "smart_routing"
    smart_remark_marker = " — Smart"

    template_payload = _json.loads(template_file.read_text())
    template_name = template_payload.get("name", SMART_TEMPLATE_NAME)
    template_json = template_payload["templateJson"]
    template_type = template_payload.get("templateType", "XRAY_JSON")

    # 1. Subscription template — idempotent by name.
    # NOTE: POST /api/subscription-templates silently drops some routing.rules
    # (only `protocol`-typed rules survive). We always follow up with PATCH so
    # the stored templateJson exactly matches our file regardless of whether
    # the template existed before.
    templates = client.list_subscription_templates()
    smart_template = next(
        (t for t in templates if t.get("name") == template_name and t.get("templateType") == template_type),
        None,
    )
    if smart_template is None:
        smart_template = client.create_subscription_template(template_name, template_json, template_type)
        print(f"Created subscription-template '{template_name}' uuid={smart_template.get('uuid')}")
    else:
        print(f"Skip subscription-template '{template_name}' — already exists uuid={smart_template.get('uuid')}")
    smart_template_uuid = smart_template["uuid"]
    client.update_subscription_template(smart_template_uuid, template_json)
    print(f"Synced templateJson body for '{template_name}' (POST drops some rules; PATCH preserves all)")

    # 2. Squads — find Default, create Mode-Smart if missing
    squads = client.list_squads()
    default_squad = next((s for s in squads if s.get("name") == DEFAULT_SQUAD_NAME), None)
    if default_squad is None:
        print(f"ERROR: Default squad '{DEFAULT_SQUAD_NAME}' not found. Aborting.")
        return 2
    default_squad_uuid = default_squad["uuid"]
    # Mode-Smart must use the same inbound(s) as Default-Squad — both squads
    # carry VLESS-Reality traffic; only the client-side routing template differs.
    default_inbound_uuids = [ib["uuid"] for ib in (default_squad.get("inbounds") or [])]
    if not default_inbound_uuids:
        print(f"ERROR: Default squad has no inbounds — cannot derive Mode-Smart inbounds. Aborting.")
        return 2

    smart_squad = next((s for s in squads if s.get("name") == SMART_SQUAD_NAME), None)
    if smart_squad is None:
        smart_squad = client.create_squad(SMART_SQUAD_NAME, inbounds=default_inbound_uuids)
        print(f"Created squad '{SMART_SQUAD_NAME}' uuid={smart_squad.get('uuid')}")
    else:
        print(f"Skip squad '{SMART_SQUAD_NAME}' — already exists uuid={smart_squad.get('uuid')}")
    smart_squad_uuid = smart_squad["uuid"]

    # 3. Hosts — for each existing host (not yet a smart-copy), create smart sibling
    hosts = client.list_hosts()
    full_hosts = [h for h in hosts if smart_remark_marker not in h.get("remark", "")]
    smart_hosts = [h for h in hosts if smart_remark_marker in h.get("remark", "")]

    # 3a. Create missing smart-copies
    smart_by_remark = {h["remark"]: h for h in smart_hosts}
    for full_h in full_hosts:
        full_remark = full_h.get("remark", "")
        smart_remark = full_remark + smart_remark_marker
        if smart_remark in smart_by_remark:
            print(f"Skip smart-host '{smart_remark}' — already exists uuid={smart_by_remark[smart_remark]['uuid']}")
            continue
        payload = {
            "inbound": full_h["inbound"],
            "remark": smart_remark,
            "address": full_h["address"],
            "port": full_h["port"],
            "sni": full_h.get("sni") or "",
            "host": full_h.get("host") or "",
            "fingerprint": full_h.get("fingerprint") or "chrome",
            "isDisabled": False,
            "securityLayer": full_h.get("securityLayer") or "DEFAULT",
            "excludedInternalSquads": [default_squad_uuid],
            "xrayJsonTemplateUuid": smart_template_uuid,
        }
        created = client.create_host(payload)
        print(f"Created smart-host '{smart_remark}' uuid={created.get('uuid')}")

    # 3b. Update existing full-hosts: exclude them from Mode-Smart squad
    for full_h in full_hosts:
        existing_excludes = set(full_h.get("excludedInternalSquads") or [])
        if smart_squad_uuid in existing_excludes:
            print(f"Skip full-host '{full_h['remark']}' — already excludes Mode-Smart")
            continue
        new_excludes = list(existing_excludes | {smart_squad_uuid})
        client.update_host(full_h["uuid"], excludedInternalSquads=new_excludes)
        print(f"Updated full-host '{full_h['remark']}' — excludedInternalSquads += Mode-Smart")

    print()
    print("=== Append these to infra/.env ===")
    print(f"REMNAWAVE_SQUAD_FULL_UUID={default_squad_uuid}")
    print(f"REMNAWAVE_SQUAD_SMART_UUID={smart_squad_uuid}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Declarative Remnawave provisioning (read-only stage)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=HERE.parent / ".env",
        help="Path to .env (default: infra/.env, relative to apply.py)",
    )
    subs = parser.add_subparsers(dest="cmd", required=True)
    subs.add_parser("status", help="show current Remnawave state")
    p_import = subs.add_parser(
        "import",
        help="dump current Remnawave state to configs/*.yaml + state.json (Terraform-style)",
    )
    p_import.add_argument(
        "--out-dir",
        type=Path,
        default=HERE / "configs",
        help="Directory for generated YAML (default: infra/remnawave/configs/)",
    )
    p_import.add_argument(
        "--state-file",
        type=Path,
        default=HERE / "state.json",
        help="Path for state.json (default: infra/remnawave/state.json)",
    )
    p_rotate = subs.add_parser(
        "rotate-reality-key",
        help="generate new Reality keypair via Remnawave x25519 endpoint, write to .env",
    )
    p_rotate.add_argument(
        "--env-file-target",
        type=Path,
        default=HERE.parent / ".env",
        help="Path to .env where new keys are written (default: infra/.env)",
    )
    p_pm = subs.add_parser(
        "apply-protection-modes",
        help="create smart_routing template + Mode-Smart squad + smart-host copies",
    )
    p_pm.add_argument(
        "--template-file",
        type=Path,
        default=HERE / "configs" / "template_smart_routing.json",
        help="Path to smart template JSON (default: configs/template_smart_routing.json)",
    )
    # Stages to follow: plan, apply, validate, destroy.
    args = parser.parse_args(argv)

    _load_env_file(args.env_file)

    try:
        with RemnawaveClient() as client:
            if args.cmd == "status":
                return cmd_status(client)
            if args.cmd == "import":
                from _lib.importer import cmd_import
                return cmd_import(client, args.out_dir, args.state_file)
            if args.cmd == "rotate-reality-key":
                from _lib.reality import rotate_reality_keys, write_keys_to_env
                priv, pub = rotate_reality_keys(client)
                write_keys_to_env(args.env_file_target, priv, pub)
                print(f"Reality keys rotated. Written to {args.env_file_target}")
                print(f"Public key (use for hosts.yaml / clients): {pub}")
                return 0
            if args.cmd == "apply-protection-modes":
                return cmd_apply_protection_modes(client, args.template_file)
    except RuntimeError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        print(
            "Set REMNAWAVE_API_URL (e.g., https://admin.example.com) and "
            "REMNAWAVE_API_TOKEN in the .env file.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
