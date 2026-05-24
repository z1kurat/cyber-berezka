"""Brevo Transactional Mail API client.

We pass an httpx.AsyncClient instance in for testability.
"""
from __future__ import annotations

from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


class EmailService:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        api_key: str = "",
        sender_email: str = "",
        sender_name: str = "",
    ):
        self.client = client or httpx.AsyncClient(timeout=15.0)
        self.api_key = api_key
        self.sender_email = sender_email
        self.sender_name = sender_name

    async def _send(self, to_email: str, subject: str, html: str) -> None:
        resp = await self.client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": self.api_key, "accept": "application/json"},
            json={
                "sender": {"name": self.sender_name, "email": self.sender_email},
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": html,
            },
            timeout=15.0,
        )
        resp.raise_for_status()

    async def send_verification(self, to_email: str, token: str, verify_base_url: str) -> None:
        verify_url = f"{verify_base_url.rstrip('/')}/auth/verify/{token}"
        html = _env.get_template("verify.html").render(verify_url=verify_url)
        await self._send(to_email, "Подтверждение регистрации в Cyber Berezka", html)

    async def send_approved(self, to_email: str, cabinet_url: str) -> None:
        html = _env.get_template("approved.html").render(cabinet_url=cabinet_url)
        await self._send(to_email, "Доступ к Cyber Berezka выдан", html)

    async def send_rejected(self, to_email: str, reason: str | None, contact: str) -> None:
        html = _env.get_template("rejected.html").render(reason=reason, contact=contact)
        await self._send(to_email, "Заявка в Cyber Berezka отклонена", html)
