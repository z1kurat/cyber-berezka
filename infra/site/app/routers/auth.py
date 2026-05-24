"""Auth routes: register, login, logout, email verify."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import get_current_user, get_session_service
from app.models.user import User
from app.services.auth import AuthError, AuthService
from app.services.email import EmailService
from app.services.sessions import SessionService

router = APIRouter(prefix="/auth", tags=["auth"])

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")
TEMPLATES.env.globals["site_host"] = settings.site_host


def _email_service() -> EmailService:
    return EmailService(
        api_key=settings.brevo_api_key,
        sender_email=settings.brevo_sender_email,
        sender_name=settings.brevo_sender_name,
    )


@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    return TEMPLATES.TemplateResponse("auth/register.html", {"request": request, "error": None})


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if password != password_confirm:
        return TEMPLATES.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Пароли не совпадают", "email": email},
            status_code=400,
        )
    svc = AuthService(db)
    try:
        user, verify_token = await svc.register(email=email, password=password)
    except AuthError as e:
        msg = {
            "email_taken": "Email уже занят",
            "weak_password": "Пароль должен быть не короче 12 символов",
        }.get(str(e), "Ошибка регистрации")
        return TEMPLATES.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": msg, "email": email},
            status_code=400,
        )
    try:
        await _email_service().send_verification(
            user.email, verify_token, verify_base_url=f"https://{settings.site_host}",
        )
    except Exception:
        pass  # email failure is logged but doesn't block registration
    return TEMPLATES.TemplateResponse(
        "auth/verify_sent.html", {"request": request, "email": user.email}
    )


@router.get("/verify/{token}")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    ok = await svc.verify_email(token)
    if not ok:
        raise HTTPException(status_code=400, detail="Ссылка недействительна или уже использована.")
    return RedirectResponse(url="/auth/login?verified=1", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return TEMPLATES.TemplateResponse("auth/login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    svc: SessionService = Depends(get_session_service),
):
    auth = AuthService(db)
    user, err = await auth.authenticate(email=email, password=password)
    if user is None:
        msg = {
            "invalid_credentials": "Неверный email или пароль",
            "rejected": "Доступ к сервису отклонён",
            "inactive": "Аккаунт деактивирован",
        }.get(err, "Ошибка входа")
        return TEMPLATES.TemplateResponse(
            "auth/login.html", {"request": request, "error": msg, "email": email}, status_code=400,
        )
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    sid = await svc.create(user_id=user.id, ip=ip, ua=ua)
    resp = RedirectResponse(url="/cabinet", status_code=303)
    resp.set_cookie(
        key="__Host-session",
        value=sid,
        max_age=settings.session_lifetime_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return resp


@router.post("/logout")
async def logout(
    request: Request,
    svc: SessionService = Depends(get_session_service),
    user: User | None = Depends(get_current_user),
):
    sid = request.cookies.get("__Host-session")
    if sid:
        await svc.revoke(sid)
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("__Host-session", path="/")
    return resp
