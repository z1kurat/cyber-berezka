"""HTTPX wrapper for Remnawave Panel REST API."""
from __future__ import annotations

import os
from typing import Any

import httpx


class RemnawaveError(Exception):
    """Non-2xx response from the API."""

    def __init__(self, status: int, body: Any, method: str, url: str):
        super().__init__(f"{method} {url} -> {status}: {body}")
        self.status = status
        self.body = body


class RemnawaveClient:
    """Thin wrapper. Auth via static API token from .env.

    A Remnawave panel response wraps payload in {"response": ...}. This
    client returns the inner payload by default, leaving wrapper handling
    in one place.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 15.0,
        verify: bool = True,
    ):
        self.base_url = (base_url or os.environ.get("REMNAWAVE_API_URL") or "").rstrip("/")
        self.token = token or os.environ.get("REMNAWAVE_API_TOKEN") or ""
        if not self.base_url:
            raise RuntimeError("REMNAWAVE_API_URL not set")
        if not self.token:
            raise RuntimeError("REMNAWAVE_API_TOKEN not set")
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            verify=verify,
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "cyber-berezka-apply/0.1",
            },
        )

    def __enter__(self) -> "RemnawaveClient":
        return self

    def __exit__(self, *_):
        self._http.close()

    def _call(self, method: str, path: str, **kwargs) -> Any:
        resp = self._http.request(method, path, **kwargs)
        try:
            data = resp.json()
        except ValueError:
            data = resp.text
        if not (200 <= resp.status_code < 300):
            raise RemnawaveError(resp.status_code, data, method, path)
        # Remnawave wraps single objects in {"response": ...}.
        if isinstance(data, dict) and "response" in data and len(data) == 1:
            return data["response"]
        return data

    def get(self, path: str, params: dict | None = None) -> Any:
        return self._call("GET", path, params=params)

    def post(self, path: str, json: Any = None) -> Any:
        return self._call("POST", path, json=json)

    def patch(self, path: str, json: Any = None) -> Any:
        return self._call("PATCH", path, json=json)

    def delete(self, path: str) -> Any:
        return self._call("DELETE", path)

    # --- domain helpers ---
    #
    # The wrapping is inconsistent across endpoints:
    #   /api/config-profiles -> {"total": N, "configProfiles": [...]}
    #   /api/internal-squads -> {"total": N, "internalSquads": [...]}
    #   /api/users           -> {"total": N, "users": [...]}
    #   /api/nodes           -> [...]
    #   /api/hosts           -> [...]
    # These helpers unify the shape and return a plain list, except for
    # paginated endpoints where the caller may want the total.

    def list_profiles(self) -> list[dict]:
        data = self.get("/api/config-profiles") or {}
        return data.get("configProfiles", []) if isinstance(data, dict) else (data or [])

    def list_squads(self) -> list[dict]:
        data = self.get("/api/internal-squads") or {}
        return data.get("internalSquads", []) if isinstance(data, dict) else (data or [])

    def list_nodes(self) -> list[dict]:
        return self.get("/api/nodes") or []

    def list_hosts(self) -> list[dict]:
        return self.get("/api/hosts") or []

    def list_users(self, size: int = 100, start: int = 0) -> dict:
        """Returns {'total': N, 'users': [...]} — paginated; callers iterate
        the 'users' list and can fetch more pages by total / size."""
        data = self.get("/api/users", params={"size": size, "start": start}) or {}
        if isinstance(data, list):
            return {"total": len(data), "users": data}
        return data

    def health(self) -> dict:
        return self.get("/api/system/health")

    def generate_x25519(self) -> dict[str, str]:
        """POST /api/system/tools/x25519/generate — generate new Reality keypair.

        Returns dict with 'privateKey' and 'publicKey' (the client unwraps the
        Remnawave {"response": ...} envelope automatically).
        """
        return self.post("/api/system/tools/x25519/generate", json={})
