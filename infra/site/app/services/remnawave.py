"""Remnawave API wrapper for the site app.

Reuses the same HTTPX-based client pattern as infra/remnawave/_lib/client.py,
but instantiated with site's runtime config (REMNAWAVE_API_URL pointing to
internal http://remnawave:3000).
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class RemnawaveAPIError(Exception):
    def __init__(self, status: int, body: Any):
        super().__init__(f"Remnawave API {status}: {body}")
        self.status = status
        self.body = body


class RemnawaveAPI:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.base = settings.remnawave_api_url.rstrip("/")
        self.token = settings.remnawave_api_token
        # Remnawave 2.7 closes the connection when Origin/Host don't match its
        # configured FRONT_END_DOMAIN. When we talk to it through the internal
        # docker DNS (http://remnawave:3000), the default Host header would be
        # 'remnawave' — the panel rejects that. Forge Caddy-style proxy headers
        # so the panel sees the request as if it came through the public host.
        self.client = client or httpx.AsyncClient(
            timeout=15.0,
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "cyber-berezka-site/0.1",
                "Host": settings.admin_host,
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": settings.admin_host,
                "Origin": f"https://{settings.admin_host}",
            },
        )

    async def _call(self, method: str, path: str, **kwargs) -> Any:
        resp = await self.client.request(method, f"{self.base}{path}", **kwargs)
        try:
            data = resp.json()
        except ValueError:
            data = resp.text
        if not (200 <= resp.status_code < 300):
            raise RemnawaveAPIError(resp.status_code, data)
        if isinstance(data, dict) and "response" in data and len(data) == 1:
            return data["response"]
        return data

    async def list_nodes(self) -> list[dict]:
        return await self._call("GET", "/api/nodes") or []

    async def create_user(self, username: str, expire_at: str | None = None) -> dict:
        payload = {"username": username}
        if expire_at:
            payload["expireAt"] = expire_at
        return await self._call("POST", "/api/users", json=payload)

    async def get_user(self, user_uuid: str) -> dict:
        return await self._call("GET", f"/api/users/{user_uuid}")

    async def revoke_user(self, user_uuid: str) -> None:
        await self._call("PATCH", f"/api/users/{user_uuid}", json={"status": "DISABLED"})

    async def aclose(self) -> None:
        await self.client.aclose()
