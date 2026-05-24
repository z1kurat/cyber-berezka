"""VPN keys business logic — creates Remnawave user on demand, persists local row."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.vpn_key import VpnKey
from app.services.geo import resolve_country
from app.services.remnawave import RemnawaveAPI


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

    async def create_key(self, user: User, label: str | None) -> tuple[VpnKey, str]:
        """Create a VpnKey row, return (key, subscription_url)."""
        await self.ensure_remnawave_user(user)
        rw_user = await self.remnawave.get_user(user.remnawave_user_uuid)
        subscription_url = rw_user.get("subscriptionUrl") or ""
        key = VpnKey(
            user_id=user.id,
            label=label or f"Ключ от {datetime.now(timezone.utc).strftime('%d.%m.%Y')}",
        )
        self.db.add(key)
        log = AuditLog(user_id=user.id, event_type="key.create", event_data={"label": key.label})
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(key)
        return key, subscription_url

    async def list_keys_with_url(self, user: User) -> tuple[list[VpnKey], str]:
        result = await self.db.execute(
            select(VpnKey).where(VpnKey.user_id == user.id, VpnKey.status == "active").order_by(VpnKey.id.desc())
        )
        keys = list(result.scalars())
        if not user.remnawave_user_uuid or not keys:
            return keys, ""
        rw_user = await self.remnawave.get_user(user.remnawave_user_uuid)
        return keys, rw_user.get("subscriptionUrl", "")

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
            country_code = (node_by_addr.get(addr) or {}).get("countryCode")
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
