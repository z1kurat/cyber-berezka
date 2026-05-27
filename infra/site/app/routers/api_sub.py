"""Public subscription proxy router.

Stable per-user URL: `/api/sub/<remnawave_short_uuid>`. No auth — the
short_uuid is the implicit secret (32+ chars of entropy, same as the
Remnawave upstream). Format selection happens server-side based on
the user's `protection_mode`, so the client URL never changes after
the user toggles modes on /cabinet.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.remnawave import RemnawaveAPI
from app.services.subscription import SubscriptionService

router = APIRouter(prefix="/api/sub", tags=["subscription"])


@router.get("/{token}")
async def get_subscription(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    ua = request.headers.get("user-agent", "v2RayTun/1.0")
    rw = RemnawaveAPI()
    try:
        body, content_type = await SubscriptionService(db, rw).fetch(token, ua)
    finally:
        await rw.aclose()
    return Response(content=body, media_type=content_type)
