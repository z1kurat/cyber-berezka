"""Cabinet — user dashboard with state-based rendering."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.deps import require_user
from app.models.user import User

router = APIRouter(prefix="/cabinet", tags=["cabinet"])

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def cabinet_home(request: Request, user: User = Depends(require_user)):
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
    return TEMPLATES.TemplateResponse(
        "cabinet/index.html",
        {"request": request, "user": user, "site_host": settings.site_host},
    )
