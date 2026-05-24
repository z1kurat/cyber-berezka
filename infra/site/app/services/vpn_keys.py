"""VPN keys business logic — creates Remnawave user on demand, persists local row."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.vpn_key import VpnKey
from app.services.remnawave import RemnawaveAPI


class VpnKeysService:
    def __init__(self, db: AsyncSession, remnawave: RemnawaveAPI):
        self.db = db
        self.remnawave = remnawave

    async def ensure_remnawave_user(self, user: User) -> None:
        """Create the Remnawave user once, store UUID/short_uuid in local row."""
        if user.remnawave_user_uuid:
            return
        far_future = "2099-12-31T00:00:00Z"
        rw_user = await self.remnawave.create_user(
            username=f"user_{user.id}", expire_at=far_future,
        )
        user.remnawave_user_uuid = rw_user.get("uuid")
        user.remnawave_short_uuid = rw_user.get("shortUuid")
        await self.db.commit()

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
