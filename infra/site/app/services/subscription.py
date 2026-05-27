"""Subscription proxy — sits between the VPN client and Remnawave.

Why this exists: Remnawave's base subscription URL always returns flat
base64-vless. To get the XRAY_JSON template with routing rules (used by
the «Умная защита» mode), the client would have to hit `<sub_url>/json`.
Most user-facing clients (v2RayTun, Hiddify) don't do that.

Solution: expose a single stable URL `<site_host>/api/sub/<short_uuid>`
that picks the right upstream URL based on the user's `protection_mode`.
Toggling «Полная» / «Умная» takes effect on next subscription refresh
without the client changing anything on its end.
"""
from __future__ import annotations

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.remnawave import RemnawaveAPI


class SubscriptionService:
    def __init__(self, db: AsyncSession, rw: RemnawaveAPI):
        self.db = db
        self.rw = rw

    async def fetch(self, short_uuid: str, user_agent: str) -> tuple[bytes, str]:
        """Return (body bytes, Content-Type) proxied from Remnawave."""
        result = await self.db.execute(
            select(User).where(User.remnawave_short_uuid == short_uuid)
        )
        user = result.scalar_one_or_none()
        if user is None or not user.remnawave_user_uuid:
            raise HTTPException(status_code=404, detail="subscription not found")

        rw_user = await self.rw.get_user(user.remnawave_user_uuid)
        upstream_sub_url = rw_user.get("subscriptionUrl", "")
        if not upstream_sub_url:
            raise HTTPException(status_code=502, detail="upstream returned no subscriptionUrl")

        # Smart mode → ask Remnawave for the XRAY_JSON template variant.
        # Full mode → keep the legacy flat-vless format.
        if user.protection_mode == "smart":
            upstream_url = upstream_sub_url.rstrip("/") + "/json"
        else:
            upstream_url = upstream_sub_url

        ua = user_agent or "v2RayTun/1.0"
        async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
            resp = await client.get(upstream_url, headers={"User-Agent": ua})
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"upstream returned {resp.status_code}")
        return resp.content, resp.headers.get("content-type", "text/plain; charset=utf-8")
