# Remnawave declarative configs

This directory is the source-of-truth for everything that Remnawave panel
holds in its database (profiles, squads, hosts, nodes, users). Per project
rule "prefer declarative/IaC over manual UI" — these files exist so the
panel can be re-created on a fresh install from scratch.

## Current files

| File | Purpose |
|---|---|
| `profile_default.template.json` | Xray JSON config for the default profile. Contains `${REALITY_PRIVATE_KEY}` placeholder — the actual key lives in `infra/.env` and is substituted at apply time. |

## Future files (per migration spec §3 — not yet present)

- `profile_ipv4_only.yaml` — IPv4-only outbound for the Beget coordinator
- `profile_ipv6_pool.yaml` — IPv6 random-balancer outbound for the Timeweb node
- `nodes.yaml` — two node entries (coordinator + remote)
- `squads.yaml` — squad → inbound + node associations
- `hosts.yaml` — host entries with public Reality keys for clients
- `users.yaml` — provisioned users (test-01 etc.)

These will appear as `apply.py` gains an `apply` subcommand
(see `2026-05-17-apply-py-design.md` — current state stops at `import`).

## How to use the profile template (manual paste flow, until `apply.py apply` is implemented)

```bash
# Substitute the Reality private key from infra/.env into the template
PRIV=$(grep '^REALITY_PRIVATE_KEY=' infra/.env | cut -d= -f2-)
sed "s|\${REALITY_PRIVATE_KEY}|$PRIV|" infra/remnawave/configs/profile_default.template.json | tee /tmp/profile.json
# Now copy contents of /tmp/profile.json and paste into Remnawave UI:
# Config Profiles -> Default-Profile -> Edit Config -> paste -> Save
```

To regenerate the Reality keypair (rotation):

```bash
# Run on the coordinator server (locally on whichever host has cryptography)
python3 - <<'PY'
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import base64
priv = X25519PrivateKey.generate()
pub = priv.public_key()
enc = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
print(f"REALITY_PRIVATE_KEY={enc(priv.private_bytes_raw())}")
print(f"REALITY_PUBLIC_KEY={enc(pub.public_bytes_raw())}")
PY
# Paste the two lines into infra/.env on both servers, then re-substitute the template above and re-paste into UI.
```

Note: the `apply.py rotate-reality-key` subcommand currently fails on Remnawave
2.7.4 (endpoint `/api/system/tools/x25519/generate` returns 404). Tracked as
task #52 — rewrite to use the local Python `cryptography` generator above.
