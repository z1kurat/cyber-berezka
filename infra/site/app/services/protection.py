"""Protection mode toggle (full/smart) — Remnawave squad swap + local DB."""
from __future__ import annotations

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.services.remnawave import RemnawaveAPI


ProtectionMode = Literal["full", "smart"]


class ProtectionService:
    def __init__(self, db: AsyncSession, rw: RemnawaveAPI):
        self.db = db
        self.rw = rw

    def _squad_for(self, mode: ProtectionMode) -> str:
        if mode == "full":
            uuid = settings.remnawave_squad_full_uuid
        elif mode == "smart":
            uuid = settings.remnawave_squad_smart_uuid
        else:
            raise ValueError(f"unknown protection mode: {mode!r}")
        if not uuid:
            raise RuntimeError(f"REMNAWAVE_SQUAD_{mode.upper()}_UUID is not configured")
        return uuid

    async def set_mode(self, user: User, mode: ProtectionMode) -> None:
        if mode not in ("full", "smart"):
            raise ValueError(f"unknown protection mode: {mode!r}")
        if user.protection_mode == mode:
            return
        squad_uuid = self._squad_for(mode)
        if user.remnawave_user_uuid:
            await self.rw.update_user(
                user.remnawave_user_uuid,
                activeInternalSquads=[squad_uuid],
            )
        user.protection_mode = mode
        await self.db.commit()
