"""FastAPI entry. Mounts static files and routers."""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from redis.asyncio import Redis

from app.config import settings
from app.deps import get_redis
from app.routers import auth, cabinet, landing, legal
from app.routers.landing import render_landing

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Cyber Berezka",
    description="Защищённое соединение",
    version="0.1.0",
    docs_url=None,  # disabled in production-facing builds
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals["site_domain"] = settings.site_domain
templates.env.globals["landing_domain"] = settings.landing_domain

app.state.templates = templates


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
async def readyz() -> dict:
    # When DB and Redis are wired, check them here.
    return {"status": "ready"}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault(
        "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; "
        "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; base-uri 'self'; form-action 'self'; "
        "frame-ancestors 'none'",
    )
    return response


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request, redis: Redis = Depends(get_redis)):
    """Serve landing on the canonical site host; redirect from any other host.

    `landing_domain` in .env is set to the same value as SITE_HOST during
    the beget migration (nip.io stage and onward), so the site host both
    matches `home.*` (production) and the bare nip.io equivalent. The
    self-redirect that used to happen in apex→home is now handled by Caddy
    via APEX_REDIRECT_HOST.
    """
    host = request.headers.get("host", "")
    if host.startswith("home.") or host == settings.landing_domain:
        return await render_landing(request, redis)
    return RedirectResponse(
        url=f"https://{settings.landing_domain}/", status_code=302
    )


app.include_router(auth.router)
app.include_router(cabinet.router)
app.include_router(landing.router)
app.include_router(legal.router)

# Future routers go here: auth, cabinet, api_sub.
