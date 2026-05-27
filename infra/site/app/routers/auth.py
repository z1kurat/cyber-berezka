"""Auth routes: register, login, logout, email verify."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from redis.asyncio import Redis

from app.config import settings
from app.db import get_db
from app.deps import get_current_user, get_redis, get_session_service, verify_csrf_token
from app.models.user import User
from app.security.rate_limit import RateLimitExceeded, check_rate
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
    return TEMPLATES.TemplateResponse(request, "auth/register.html", {"request": request, "error": None})


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    ip = request.client.host if request.client else "unknown"
    try:
        await check_rate(redis, f"rl:register:{ip}", limit=3, window_seconds=3600)
    except RateLimitExceeded:
        return TEMPLATES.TemplateResponse(
            request, "auth/register.html",
            {"request": request, "error": "Слишком много попыток. Попробуйте позже.", "email": email},
            status_code=429,
        )
    if password != password_confirm:
        return TEMPLATES.TemplateResponse(
            request, "auth/register.html",
            {"request": request, "error": "Пароли не совпадают", "email": email},
            status_code=400,
        )
    svc = AuthService(db)
    try:
        user, verify_token = await svc.register(email=email, password=password)
    except AuthError as e:
        code = str(e)
        msg = {
            "email_taken": "Email уже занят",
            "weak_password": "Пароль должен быть не короче 12 символов",
        }.get(code, "Ошибка регистрации")
        return TEMPLATES.TemplateResponse(
            request, "auth/register.html",
            {"request": request, "error": msg, "error_code": code, "email": email},
            status_code=400,
        )
    try:
        await _email_service().send_verification(
            user.email, verify_token, verify_base_url=f"https://{settings.site_host}",
        )
    except Exception:
        pass  # email failure is logged but doesn't block registration
    return TEMPLATES.TemplateResponse(
        request, "auth/verify_sent.html", {"request": request, "email": user.email}
    )


@router.get("/verify/{token}")
async def verify_email(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    ip = request.client.host if request.client else "unknown"
    try:
        await check_rate(redis, f"rl:verify:{ip}", limit=10, window_seconds=3600)
    except RateLimitExceeded:
        raise HTTPException(status_code=429, detail="Слишком много попыток. Попробуйте позже.")
    svc = AuthService(db)
    ok = await svc.verify_email(token)
    if not ok:
        raise HTTPException(status_code=400, detail="Ссылка недействительна или уже использована.")
    return RedirectResponse(url="/auth/login?verified=1", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return TEMPLATES.TemplateResponse(request, "auth/login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    svc: SessionService = Depends(get_session_service),
    redis: Redis = Depends(get_redis),
):
    ip = request.client.host if request.client else "unknown"
    norm = email.strip().lower()
    try:
        await check_rate(redis, f"rl:login:{ip}:{norm}", limit=5, window_seconds=900)
    except RateLimitExceeded:
        return TEMPLATES.TemplateResponse(
            request, "auth/login.html",
            {"request": request, "error": "Слишком много попыток входа. Попробуйте через 15 минут.", "email": email},
            status_code=429,
        )
    auth = AuthService(db)
    user, err = await auth.authenticate(email=email, password=password)
    if user is None:
        msg = {
            "invalid_credentials": "Неверный email или пароль",
            "rejected": "Доступ к сервису отклонён",
            "inactive": "Аккаунт деактивирован",
            "locked": "Аккаунт временно заблокирован после нескольких неудачных попыток. Повторите через 30 минут.",
        }.get(err, "Ошибка входа")
        return TEMPLATES.TemplateResponse(
            request, "auth/login.html", {"request": request, "error": msg, "email": email}, status_code=400,
        )
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    sid = await svc.create(user_id=user.id, ip=ip, ua=ua)
    resp = RedirectResponse(url="/cabinet", status_code=303)
    resp.set_cookie(
        key="session",
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
    _csrf: None = Depends(verify_csrf_token),
):
    sid = request.cookies.get("session")
    if sid:
        await svc.revoke(sid)
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("session", path="/")
    return resp
