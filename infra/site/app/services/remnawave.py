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
        # We route through the public host (via Caddy hairpin) because Remnawave
        # 2.7 closes the TCP connection when the request Host doesn't match its
        # configured FRONT_END_DOMAIN, and httpx overwrites our explicit Host
        # header from the URL. Caddy fixes this transparently — it sets the
        # right Host/Origin/X-Forwarded-* when proxying to http://remnawave:3000.
        self.base = settings.remnawave_api_url.rstrip("/")
        self.token = settings.remnawave_api_token
        self.client = client or httpx.AsyncClient(
            timeout=15.0,
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "cyber-berezka-site/0.1",
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
