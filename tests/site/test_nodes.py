"""Tests for nodes service (Remnawave + redis cache)."""
from __future__ import annotations

import json
import pytest

from app.services.nodes import NodesService


class FakeRedis:
    def __init__(self): self.store = {}
    async def get(self, k): return self.store.get(k)
    async def setex(self, k, ttl, v): self.store[k] = v


class FakeAPI:
    def __init__(self, nodes): self.nodes = nodes; self.calls = 0
    async def list_nodes(self): self.calls += 1; return self.nodes


@pytest.mark.asyncio
async def test_first_call_hits_api_then_caches():
    api = FakeAPI([{"name": "n1", "countryCode": "DE", "isConnected": True, "isConnecting": False}])
    svc = NodesService(api=api, redis=FakeRedis())
    a = await svc.get_nodes()
    b = await svc.get_nodes()
    assert api.calls == 1
    assert a == b
    assert a[0]["country"] == "Германия"


@pytest.mark.asyncio
async def test_empty_api_returns_empty_list():
    api = FakeAPI([])
    svc = NodesService(api=api, redis=FakeRedis())
    assert await svc.get_nodes() == []


@pytest.mark.asyncio
async def test_unknown_country_falls_back_to_code():
    api = FakeAPI([{"name": "x", "countryCode": "ZZ", "isConnected": True, "isConnecting": False}])
    svc = NodesService(api=api, redis=FakeRedis())
    out = await svc.get_nodes()
    assert out[0]["country"] == "ZZ"
    assert out[0]["flag"] == "🌐"
