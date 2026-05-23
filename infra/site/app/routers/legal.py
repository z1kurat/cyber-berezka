"""Legal pages — Terms of Service and Privacy Policy."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/legal")


@router.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "legal/terms.html", context={}
    )


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "legal/privacy.html", context={}
    )
