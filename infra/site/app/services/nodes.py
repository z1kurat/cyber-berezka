"""Nodes: pull from Remnawave, cache for 30s in Redis."""
from __future__ import annotations

import json

from app.services.geo import resolve_country

CACHE_KEY = "nodes:list"
CACHE_TTL_SECONDS = 30


class NodesService:
    def __init__(self, api, redis):
        self.api = api
        self.redis = redis

    async def get_nodes(self) -> list[dict]:
        cached = await self.redis.get(CACHE_KEY)
        if cached is not None:
            try:
                return json.loads(cached) if isinstance(cached, str) else cached
            except Exception:
                pass
        raw = await self.api.list_nodes()
        result = []
        for n in raw:
            country_code = n.get("countryCode")
            country, city, flag = resolve_country(country_code)
            result.append({
                "name": n.get("name"),
                "country": country,
                "city": city,
                "flag": flag,
                "is_connected": bool(n.get("isConnected")),
                "is_connecting": bool(n.get("isConnecting")),
            })
        await self.redis.setex(CACHE_KEY, CACHE_TTL_SECONDS, json.dumps(result))
        return result
