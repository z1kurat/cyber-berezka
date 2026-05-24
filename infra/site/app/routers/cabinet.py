"""Cabinet — user dashboard with state-based rendering."""
from __future__ import annotations

import base64
import io
from pathlib import Path

import qrcode
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import get_redis, require_user
from app.services.nodes import NodesService
from app.models.user import User
from app.services.remnawave import RemnawaveAPI
from app.services.vpn_keys import VpnKeysService

router = APIRouter(prefix="/cabinet", tags=["cabinet"])

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def cabinet_home(
    request: Request,
    user: User = Depends(require_user),
    redis=Depends(get_redis),
):
    """Render cabinet according to user state."""
    if user.is_rejected:
        return TEMPLATES.TemplateResponse(
            "cabinet/rejected.html", {"request": request, "user": user},
        )
    if not user.is_email_verified:
        return TEMPLATES.TemplateResponse(
            "cabinet/pending_email.html", {"request": request, "user": user},
        )
    if not user.is_approved:
        return TEMPLATES.TemplateResponse(
            "cabinet/pending_admin.html", {"request": request, "user": user},
        )
    rw = RemnawaveAPI()
    try:
        nsvc = NodesService(api=rw, redis=redis)
        nodes = await nsvc.get_nodes()
    except Exception:
        nodes = []
    finally:
        await rw.aclose()
    return TEMPLATES.TemplateResponse(
        "cabinet/index.html",
        {"request": request, "user": user, "site_host": settings.site_host, "nodes": nodes},
    )


def _qr_data_uri(payload: str) -> str:
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@router.get("/keys", response_class=HTMLResponse)
async def keys_page(
    request: Request,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.is_approved:
        return RedirectResponse(url="/cabinet", status_code=303)
    rw = RemnawaveAPI()
    try:
        svc = VpnKeysService(db, rw)
        keys, sub_url = await svc.list_keys_with_url(user)
    finally:
        await rw.aclose()
    qr = _qr_data_uri(sub_url) if sub_url else ""
    return TEMPLATES.TemplateResponse(
        "cabinet/keys.html",
        {"request": request, "user": user, "keys": keys,
         "subscription_url": sub_url, "qr_data_uri": qr,
         "site_host": settings.site_host},
    )


@router.post("/keys")
async def keys_create(
    request: Request,
    label: str = Form(""),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.is_approved:
        return RedirectResponse(url="/cabinet", status_code=303)
    rw = RemnawaveAPI()
    try:
        svc = VpnKeysService(db, rw)
        await svc.create_key(user, label=label or None)
    finally:
        await rw.aclose()
    return RedirectResponse(url="/cabinet/keys", status_code=303)


@router.post("/keys/{key_id}/revoke")
async def keys_revoke(
    key_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    rw = RemnawaveAPI()
    try:
        svc = VpnKeysService(db, rw)
        await svc.revoke_key(user, key_id)
    finally:
        await rw.aclose()
    return RedirectResponse(url="/cabinet/keys", status_code=303)
