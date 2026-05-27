"""VPN keys business logic — creates Remnawave user on demand, persists local row."""
from __future__ import annotations

import base64
import random
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.vpn_key import VpnKey
from app.services.geo import resolve_country
from app.services.remnawave import RemnawaveAPI


def _build_proxied_sub_url(short_uuid: str) -> str:
    """Subscription URL exposed to the client — proxied through our site.

    Our /api/sub handler picks the upstream format (flat vs JSON) based on
    `user.protection_mode`, so the URL stays stable across mode toggles.
    """
    if not short_uuid:
        return ""
    return f"https://{settings.site_host}/api/sub/{short_uuid}"


class NoServersInCountry(Exception):
    """Raised when no online servers exist for the requested country code."""


class VpnKeysService:
    def __init__(self, db: AsyncSession, remnawave: RemnawaveAPI):
        self.db = db
        self.remnawave = remnawave

    async def ensure_remnawave_user(self, user: User) -> None:
        """Create the Remnawave user once, store UUID/short_uuid in local row.

        Also attach the new user to the first available squad — otherwise the
        subscription URL falls back to placeholder hosts (0.0.0.0:1 / "No hosts
        found") and the client cannot connect.
        """
        if user.remnawave_user_uuid:
            return
        far_future = "2099-12-31T00:00:00Z"
        # Pick a default squad before creating the user so we can bind in one go.
        squads = await self.remnawave.list_squads()
        default_squad_uuid = squads[0]["uuid"] if squads else None

        rw_user = await self.remnawave.create_user(
            username=f"user_{user.id}", expire_at=far_future,
        )
        user.remnawave_user_uuid = rw_user.get("uuid")
        user.remnawave_short_uuid = rw_user.get("shortUuid")
        await self.db.commit()

        if default_squad_uuid and user.remnawave_user_uuid:
            await self.remnawave.update_user(
                user.remnawave_user_uuid,
                activeInternalSquads=[default_squad_uuid],
            )

    async def create_key(
        self, user: User, label: str, country_code: str,
    ) -> tuple[VpnKey, dict]:
        """Create a VpnKey bound to a random server in `country_code`.

        The bound server's address and country are snapshotted into
        VpnKey.meta. At render time the cabinet looks up the current server
        with that address from the user's subscription URL and shows ONLY
        that one server's deep-links for this key.

        Raises NoServersInCountry if no online server is available there.
        """
        await self.ensure_remnawave_user(user)
        servers = await self.list_servers_for_user(user)
        target_cc = country_code.upper()
        matching = [
            s for s in servers
            if (s.get("country_code") or "").upper() == target_cc and s.get("is_connected")
        ]
        if not matching:
            raise NoServersInCountry(target_cc)
        chosen = random.choice(matching)
        key = VpnKey(
            user_id=user.id,
            label=label,
            meta={
                "country_code": chosen["country_code"],
                "address": chosen["address"],
            },
        )
        self.db.add(key)
        log = AuditLog(
            user_id=user.id,
            event_type="key.create",
            event_data={
                "label": label,
                "country": chosen["country_code"],
                "address": chosen["address"],
            },
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(key)
        return key, chosen

    async def list_keys_with_servers(self, user: User) -> tuple[list[dict], str, list[dict]]:
        """Return per-key resolved-server info + sub_url + full server list.

        Each entry: {"key": VpnKey, "server": dict|None, "is_legacy": bool}.
        - is_legacy=True for old keys (no address in meta) — those fall back
          to showing all servers.
        - server=None when the key's bound address is no longer online.
        """
        if not user.remnawave_user_uuid:
            return [], "", []
        servers = await self.list_servers_for_user(user)
        addr_to_srv = {s["address"]: s for s in servers}
        sub_url = _build_proxied_sub_url(user.remnawave_short_uuid or "")
        result = await self.db.execute(
            select(VpnKey).where(VpnKey.user_id == user.id, VpnKey.status == "active")
            .order_by(VpnKey.id.desc())
        )
        keys = list(result.scalars())
        out: list[dict] = []
        for k in keys:
            meta = k.meta if isinstance(k.meta, dict) else {}
            bound_addr = meta.get("address")
            srv = addr_to_srv.get(bound_addr) if bound_addr else None
            out.append({"key": k, "server": srv, "is_legacy": not bound_addr})
        return out, sub_url, servers

    async def list_keys_with_url(self, user: User) -> tuple[list[VpnKey], str]:
        result = await self.db.execute(
            select(VpnKey).where(VpnKey.user_id == user.id, VpnKey.status == "active").order_by(VpnKey.id.desc())
        )
        keys = list(result.scalars())
        if not user.remnawave_user_uuid or not keys:
            return keys, ""
        return keys, _build_proxied_sub_url(user.remnawave_short_uuid or "")

    async def list_servers_for_user(self, user: User) -> list[dict]:
        """Parse the user's subscription URL into per-server entries.

        Returns a list of dicts with: vless_url, address, port, remark,
        country, city, flag. Empty list if user has no Remnawave account yet
        or the subscription fetch fails.
        """
        if not user.remnawave_user_uuid:
            return []
        rw_user = await self.remnawave.get_user(user.remnawave_user_uuid)
        sub_url = rw_user.get("subscriptionUrl") or ""
        if not sub_url:
            return []
        async with httpx.AsyncClient(timeout=10.0) as c:
            resp = await c.get(sub_url, headers={"User-Agent": "v2RayTun/1.0"})
            resp.raise_for_status()
            raw = resp.text.strip()
        try:
            decoded = base64.b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8")
        except Exception:
            decoded = raw
        nodes = await self.remnawave.list_nodes()
        node_by_addr = {n.get("address"): n for n in nodes}
        out: list[dict] = []
        for line in decoded.splitlines():
            line = line.strip()
            if not line.startswith("vless://"):
                continue
            parsed = urlparse(line)
            addr = parsed.hostname or ""
            port = parsed.port or 0
            remark = unquote(parsed.fragment or "")
            node = node_by_addr.get(addr) or {}
            country_code = node.get("countryCode")
            is_connected = bool(node.get("isConnected"))
            country, city, flag = resolve_country(country_code)
            out.append({
                "vless_url": line,
                "address": addr,
                "port": port,
                "remark": remark,
                "country": country,
                "city": city,
                "flag": flag,
                "country_code": country_code or "",
                "is_connected": is_connected,
            })
        return out

    async def revoke_key(self, user: User, key_id: int) -> None:
        result = await self.db.execute(
            select(VpnKey).where(VpnKey.id == key_id, VpnKey.user_id == user.id)
        )
        key = result.scalar_one_or_none()
        if key is None:
            return
        key.status = "revoked"
        log = AuditLog(user_id=user.id, event_type="key.revoke", event_data={"key_id": key_id})
        self.db.add(log)
        await self.db.commit()
