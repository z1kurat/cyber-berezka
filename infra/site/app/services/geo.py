"""ISO country code → (display name, city, flag emoji)."""
from __future__ import annotations

COUNTRY_NAMES: dict[str, tuple[str, str, str]] = {
    "DE": ("Германия", "Frankfurt", "🇩🇪"),
    "NL": ("Нидерланды", "Amsterdam", "🇳🇱"),
    "LV": ("Латвия", "Riga", "🇱🇻"),
    "FR": ("Франция", "Paris", "🇫🇷"),
    "FI": ("Финляндия", "Helsinki", "🇫🇮"),
    "RU": ("Россия", "Moscow", "🇷🇺"),
}


def resolve_country(code: str | None) -> tuple[str, str, str]:
    if not code:
        return ("Unknown", "", "🌐")
    return COUNTRY_NAMES.get(code.upper(), (code.upper(), "", "🌐"))
