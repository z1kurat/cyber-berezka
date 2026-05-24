"""Landing routes."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from redis.asyncio import Redis

from app.deps import get_redis
from app.services.nodes import NodesService
from app.services.remnawave import RemnawaveAPI

router = APIRouter()

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


async def _load_nodes_context(redis: Redis) -> dict:
    rw = RemnawaveAPI()
    try:
        svc = NodesService(api=rw, redis=redis)
        nodes = await svc.get_nodes()
    except Exception:
        nodes = []
    finally:
        await rw.aclose()
    countries = {n["country"] for n in nodes if n["is_connected"]}
    return {
        "nodes": nodes,
        "nodes_online_count": sum(1 for n in nodes if n["is_connected"]),
        "nodes_countries_count": len(countries),
    }


@router.get("/landing", response_class=HTMLResponse, include_in_schema=False)
async def landing(request: Request, redis: Redis = Depends(get_redis)):
    ctx = {"request": request, **(await _load_nodes_context(redis))}
    return TEMPLATES.TemplateResponse("landing/index.html", ctx)


async def render_landing(request: Request, redis: Redis):
    """Render landing — called from main.py root handler with explicit redis."""
    ctx = {"request": request, **(await _load_nodes_context(redis))}
    return TEMPLATES.TemplateResponse("landing/index.html", ctx)


async def index(request: Request):
    """Backward-compat shim used from main.py's root handler when redis is not available.

    Returns a minimal response without nodes context.
    """
    return TEMPLATES.TemplateResponse("landing/index.html", {"request": request, "nodes": []})
