"""Pydantic Settings — read from environment / .env."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Domains
    site_domain: str = Field(default="cyber-berezka.tw1.ru", alias="SITE_DOMAIN")
    landing_domain: str = Field(default="home.cyber-berezka.tw1.ru", alias="LANDING_DOMAIN")
    public_base_url: str = Field(
        default="https://cyber-berezka.tw1.ru",
        alias="SITE_PUBLIC_URL",
        description="Used for absolute links in emails",
    )

    # App
    secret_key: str = Field(default="change_me_in_env", alias="APP_SECRET_KEY")
    debug: bool = Field(default=False, alias="APP_DEBUG")
    session_lifetime_hours: int = Field(default=24 * 30, alias="SESSION_LIFETIME_HOURS")

    # Postgres (app DB, separate from panel DB)
    db_app_url: str = Field(
        default="postgresql+asyncpg://app:app@db-app:5432/cyber_berezka",
        alias="APP_DB_URL",
    )

    # Redis (for session cache + rate limiting)
    redis_url: str = Field(default="redis://site-redis:6379/0", alias="SITE_REDIS_URL")

    # Remnawave (panel) — internal Docker DNS, not public
    remnawave_api_url: str = Field(
        default="http://remnawave:3000",
        alias="REMNAWAVE_API_URL",
    )
    remnawave_api_token: str = Field(default="", alias="REMNAWAVE_API_TOKEN")

    # Protection-modes: squad UUIDs (set via apply.py apply-protection-modes)
    remnawave_squad_full_uuid: str = Field(default="", alias="REMNAWAVE_SQUAD_FULL_UUID")
    remnawave_squad_smart_uuid: str = Field(default="", alias="REMNAWAVE_SQUAD_SMART_UUID")

    # Brevo (transactional email)
    brevo_api_key: str = Field(default="", alias="BREVO_API_KEY")
    brevo_sender_email: str = Field(
        default="noreply@cyber-berezka.tw1.ru", alias="BREVO_SENDER_EMAIL"
    )
    brevo_sender_name: str = Field(default="Cyber Berezka", alias="BREVO_SENDER_NAME")

    # Limits
    max_keys_per_user: int = Field(default=3, alias="MAX_KEYS_PER_USER")
    password_min_length: int = Field(default=12, alias="PASSWORD_MIN_LENGTH")

    # --- Added in Task 3 ---

    # Cookie security (relax to False only for local dev over plain HTTP)
    cookie_secure: bool = Field(default=True, alias="COOKIE_SECURE")

    # Admin contact (used in rejection emails)
    admin_contact_email: str = Field(
        default="admin@cyber-berezka.ru", alias="ADMIN_CONTACT_EMAIL"
    )

    # New host names (Stage-aware via .env; defaults match Stage 1 nip.io).
    site_host: str = Field(default="212-74-231-217.nip.io", alias="SITE_HOST")
    admin_host: str = Field(
        default="admin.212-74-231-217.nip.io", alias="ADMIN_HOST"
    )


settings = Settings()
