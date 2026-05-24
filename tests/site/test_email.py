"""Tests for Brevo email service.

We stub httpx.AsyncClient to assert the right payload is sent, no network IO.
"""
from __future__ import annotations

import pytest

from app.services.email import EmailService


class _StubResponse:
    status_code = 201
    def json(self): return {"messageId": "test"}
    def raise_for_status(self): pass


class _StubClient:
    def __init__(self):
        self.calls = []
    async def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return _StubResponse()
    async def aclose(self): pass


@pytest.mark.asyncio
async def test_send_verification_calls_brevo_with_correct_payload():
    client = _StubClient()
    svc = EmailService(client=client, api_key="testkey", sender_email="n@x", sender_name="N")
    await svc.send_verification("u@x.com", token="abc", verify_base_url="https://h")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == "https://api.brevo.com/v3/smtp/email"
    assert call["headers"]["api-key"] == "testkey"
    assert call["json"]["to"][0]["email"] == "u@x.com"
    assert "Подтверждение" in call["json"]["subject"]
    assert "https://h/auth/verify/abc" in call["json"]["htmlContent"]


@pytest.mark.asyncio
async def test_send_approved():
    client = _StubClient()
    svc = EmailService(client=client, api_key="testkey", sender_email="n@x", sender_name="N")
    await svc.send_approved("u@x.com", cabinet_url="https://h/cabinet")
    assert "выдан" in client.calls[0]["json"]["subject"]


@pytest.mark.asyncio
async def test_send_rejected_with_reason():
    client = _StubClient()
    svc = EmailService(client=client, api_key="testkey", sender_email="n@x", sender_name="N")
    await svc.send_rejected("u@x.com", reason="spam", contact="admin@x.com")
    assert "отклонена" in client.calls[0]["json"]["subject"]
    assert "spam" in client.calls[0]["json"]["htmlContent"]
