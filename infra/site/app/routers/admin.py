"""Admin approval / reject pending users."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import require_admin
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.email import EmailService

router = APIRouter(prefix="/cabinet/admin", tags=["admin"])

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def _email_service() -> EmailService:
    return EmailService(
        api_key=settings.brevo_api_key,
        sender_email=settings.brevo_sender_email,
        sender_name=settings.brevo_sender_name,
    )


async def approve_user_service(db: AsyncSession, target: User, admin: User) -> None:
    target.admin_approved_at = datetime.now(timezone.utc)
    target.admin_approved_by = admin.id
    db.add(AuditLog(user_id=admin.id, event_type="user.approved",
                    event_data={"target_user_id": target.id}))
    await db.commit()


async def reject_user_service(
    db: AsyncSession, target: User, admin: User, reason: str | None,
) -> None:
    target.admin_rejected_at = datetime.now(timezone.utc)
    target.admin_rejected_by = admin.id
    target.rejection_reason = reason
    db.add(AuditLog(user_id=admin.id, event_type="user.rejected",
                    event_data={"target_user_id": target.id, "reason": reason}))
    await db.commit()


@router.get("/pending", response_class=HTMLResponse)
async def pending_list(
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(
            User.email_verified_at.isnot(None),
            User.admin_approved_at.is_(None),
            User.admin_rejected_at.is_(None),
        ).order_by(User.created_at.desc())
    )
    users = list(result.scalars())
    return TEMPLATES.TemplateResponse(
        request, "cabinet/admin_pending.html", {"request": request, "admin": admin, "users": users},
    )


@router.post("/pending/{user_id}/approve")
async def approve_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        return RedirectResponse(url="/cabinet/admin/pending", status_code=303)
    await approve_user_service(db, target, admin)
    try:
        await _email_service().send_approved(
            target.email, cabinet_url=f"https://{settings.site_host}/cabinet",
        )
    except Exception:
        pass
    return RedirectResponse(url="/cabinet/admin/pending", status_code=303)


@router.post("/pending/{user_id}/reject")
async def reject_user(
    user_id: int,
    reason: str = Form(""),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        return RedirectResponse(url="/cabinet/admin/pending", status_code=303)
    await reject_user_service(db, target, admin, reason=reason or None)
    try:
        await _email_service().send_rejected(
            target.email, reason=reason or None, contact=settings.admin_contact_email,
        )
    except Exception:
        pass
    return RedirectResponse(url="/cabinet/admin/pending", status_code=303)
