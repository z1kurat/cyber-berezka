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
from app.deps import get_redis, require_user, verify_csrf_token
from app.services.geo import resolve_country
from app.services.nodes import NodesService
from app.models.user import User
from app.services.protection import ProtectionService
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
            request, "cabinet/rejected.html", {"request": request, "user": user},
        )
    if not user.is_email_verified:
        return TEMPLATES.TemplateResponse(
            request, "cabinet/pending_email.html", {"request": request, "user": user},
        )
    if not user.is_approved:
        return TEMPLATES.TemplateResponse(
            request, "cabinet/pending_admin.html", {"request": request, "user": user},
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
        request, "cabinet/index.html",
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
        # Always derive available countries directly from panel nodes,
        # independent of whether the user already has a Remnawave account.
        # A first-time user without keys still needs to see the country picker.
        nodes_for_countries = await rw.list_nodes()
        if user.remnawave_user_uuid:
            keys_rows, sub_url, servers = await svc.list_keys_with_servers(user)
        else:
            keys_rows, sub_url, servers = [], "", []
    finally:
        await rw.aclose()
    qr = _qr_data_uri(sub_url) if sub_url else ""
    # Country dropdown — from online nodes (global, not per-user).
    seen_cc: set[str] = set()
    countries: list[dict] = []
    for n in nodes_for_countries:
        if not n.get("isConnected"):
            continue
        cc = (n.get("countryCode") or "").upper()
        if not cc or cc in seen_cc:
            continue
        seen_cc.add(cc)
        country_name, city, flag = resolve_country(cc)
        countries.append({
            "code": cc, "name": country_name, "city": city, "flag": flag,
        })
    # Per-server QR codes (for legacy keys' fallback rendering).
    server_qrs = {s["vless_url"]: _qr_data_uri(s["vless_url"]) for s in servers}
    for row in keys_rows:
        srv = row.get("server")
        if srv and srv["vless_url"] not in server_qrs:
            server_qrs[srv["vless_url"]] = _qr_data_uri(srv["vless_url"])
    return TEMPLATES.TemplateResponse(
        request, "cabinet/keys.html",
        {"request": request, "user": user, "keys_rows": keys_rows,
         "subscription_url": sub_url, "qr_data_uri": qr,
         "servers": servers, "countries": countries,
         "server_qrs": server_qrs,
         "site_host": settings.site_host},
    )


@router.post("/keys")
async def keys_create(
    request: Request,
    label: str = Form(..., min_length=1, max_length=64),
    country: str = Form(..., min_length=2, max_length=4),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(verify_csrf_token),
):
    from app.services.vpn_keys import NoServersInCountry
    if not user.is_approved:
        return RedirectResponse(url="/cabinet", status_code=303)
    label = label.strip()
    if not label:
        return RedirectResponse(url="/cabinet/keys?error=label_required", status_code=303)
    rw = RemnawaveAPI()
    try:
        svc = VpnKeysService(db, rw)
        try:
            await svc.create_key(user, label=label, country_code=country)
        except NoServersInCountry:
            return RedirectResponse(url=f"/cabinet/keys?error=no_servers&country={country}", status_code=303)
    finally:
        await rw.aclose()
    return RedirectResponse(url="/cabinet/keys", status_code=303)


@router.post("/keys/{key_id}/revoke")
async def keys_revoke(
    key_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(verify_csrf_token),
):
    rw = RemnawaveAPI()
    try:
        svc = VpnKeysService(db, rw)
        await svc.revoke_key(user, key_id)
    finally:
        await rw.aclose()
    return RedirectResponse(url="/cabinet/keys", status_code=303)


@router.post("/protection-mode")
async def set_protection_mode(
    mode: str = Form(..., pattern="^(full|smart)$"),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(verify_csrf_token),
):
    if not user.is_approved:
        return RedirectResponse(url="/cabinet", status_code=303)
    rw = RemnawaveAPI()
    try:
        await ProtectionService(db, rw).set_mode(user, mode)  # type: ignore[arg-type]
    finally:
        await rw.aclose()
    return RedirectResponse(url="/cabinet/keys?mode_updated=1", status_code=303)
