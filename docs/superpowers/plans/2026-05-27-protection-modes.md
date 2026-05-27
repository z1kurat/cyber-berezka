# Protection Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать пользователям сайта выбор между «Полной защитой» (текущее: весь трафик через VPN) и «Умной защитой» (российские ресурсы напрямую, остальное через VPN) через тумблер на `/cabinet`.

**Architecture:** Squad-per-mode в Remnawave: existing `Default-Squad` остаётся «Полной защитой», новый `Mode-Smart` squad содержит дубликаты host'ов с привязанным XRAY_JSON template (содержит `geoip:ru`/`geosite:category-{gov,bank,media}-ru` routing rules → direct). Host'ы используют negative-фильтр `excludedInternalSquads` для cross-squad изоляции. Сайт хранит `User.protection_mode` для UI-рендера; при toggle вызывает PATCH `/api/users/{uuid}` смены `activeInternalSquads`.

**Tech Stack:** FastAPI 0.115 + SQLAlchemy 2.x async + asyncpg + Alembic + Jinja2 + Remnawave REST API 2.7.4 + Xray JSON Advanced.

**Spec:** `docs/superpowers/specs/2026-05-27-protection-modes-design.md`

**Note on testing:** Этот проект **не использует pytest** (см. `pyproject.toml` — нет dev-dependencies на тестирование). Используются manual smoke-tests через curl и `python -c "..."`. План следует этому стилю — не вводим pytest как зависимость отдельной feature'ы.

**Pre-requisite:** Security P1 patches (тот же ветка main) ещё не задеплоены. План этой фичи СОВМЕСТИМ с P1 — будет задеплоено вместе батчем после Task 17.

---

## File Structure

**Создать:**
- `infra/remnawave/configs/template_smart_routing.json` — XRAY_JSON шаблон с routing rules.
- `infra/site/migrations/versions/0002_protection_mode.py` — Alembic миграция.
- `infra/site/app/services/protection.py` — `ProtectionService` (toggle: RW PATCH + DB update).

**Модифицировать:**
- `infra/remnawave/_lib/client.py` — добавить `create_subscription_template`, `create_host`, `update_host`, `create_squad`, `delete_host` (CRUD методы для apply.py).
- `infra/remnawave/apply.py` — добавить subcommand `apply-protection-modes`.
- `infra/site/app/models/user.py` — добавить поле `protection_mode`.
- `infra/site/app/config.py` — добавить settings `remnawave_squad_full_uuid`, `remnawave_squad_smart_uuid`.
- `infra/site/app/routers/cabinet.py` — добавить POST `/cabinet/protection-mode`; обновить `cabinet_home` для рендера mode.
- `infra/site/app/templates/cabinet/index.html` — добавить toggle-карточку наверху.
- `infra/.env` (на VPS) — добавить новые UUID после apply.
- `infra/.env.example` — обновить документацию.

**Production-touch:**
- Запуск `apply-protection-modes` против production Remnawave создаст 1 template + 1 squad + 3 host'а, обновит `excludedInternalSquads` у существующих 3 host'ов. **Никаких изменений** в существующих 6 user'ах.

---

## Task 1: XRAY_JSON template файл с smart routing rules

**Files:**
- Create: `infra/remnawave/configs/template_smart_routing.json`

- [ ] **Step 1: Создать JSON-файл шаблона**

Скопировать структуру из существующего `Default` XRAY_JSON template (probed 2026-05-27, см. spec), расширить `routing.rules` тремя правилами для RU-direct. Файл:

```json
{
  "name": "smart_routing",
  "templateType": "XRAY_JSON",
  "templateJson": {
    "dns": {
      "servers": ["1.1.1.1", "1.0.0.1"],
      "queryStrategy": "UseIP"
    },
    "routing": {
      "rules": [
        {"type": "field", "protocol": ["bittorrent"], "outboundTag": "direct"},
        {"type": "field", "ip": ["geoip:ru", "geoip:private"], "outboundTag": "direct"},
        {"type": "field", "domain": ["geosite:category-gov-ru", "geosite:category-bank-ru", "geosite:category-media-ru"], "outboundTag": "direct"}
      ],
      "domainMatcher": "hybrid",
      "domainStrategy": "IPIfNonMatch"
    },
    "inbounds": [
      {"tag": "socks", "port": 10808, "listen": "127.0.0.1", "protocol": "socks", "settings": {"udp": true, "auth": "noauth"}, "sniffing": {"enabled": true, "routeOnly": false, "destOverride": ["http", "tls", "quic"]}},
      {"tag": "http", "port": 10809, "listen": "127.0.0.1", "protocol": "http", "settings": {"allowTransparent": false}, "sniffing": {"enabled": true, "routeOnly": false, "destOverride": ["http", "tls", "quic"]}}
    ],
    "outbounds": [
      {"tag": "direct", "protocol": "freedom"},
      {"tag": "block", "protocol": "blackhole"}
    ]
  }
}
```

- [ ] **Step 2: Проверить JSON-синтаксис**

Run: `python3 -c "import json; json.load(open('infra/remnawave/configs/template_smart_routing.json'))"`
Expected: no output (parse OK).

- [ ] **Step 3: Commit**

```bash
git add infra/remnawave/configs/template_smart_routing.json
git commit -m "feat(remnawave): add smart_routing XRAY_JSON template (RU-direct)"
```

---

## Task 2: Расширить RemnawaveClient CRUD методами

**Files:**
- Modify: `infra/remnawave/_lib/client.py:96-115` (add methods after existing `list_*` block)

- [ ] **Step 1: Добавить методы для subscription-templates, hosts, squads**

Открыть `infra/remnawave/_lib/client.py`, после метода `list_users` (стр. ~112) добавить:

```python
    # --- subscription-templates ---
    def list_subscription_templates(self) -> list[dict]:
        data = self.get("/api/subscription-templates") or {}
        return data.get("templates", []) if isinstance(data, dict) else (data or [])

    def get_subscription_template(self, uuid: str) -> dict:
        return self.get(f"/api/subscription-templates/{uuid}")

    def create_subscription_template(self, name: str, template_json: dict, template_type: str = "XRAY_JSON") -> dict:
        return self.post("/api/subscription-templates", json={
            "name": name,
            "templateType": template_type,
            "templateJson": template_json,
        })

    # --- internal squads (write) ---
    def create_squad(self, name: str) -> dict:
        return self.post("/api/internal-squads", json={"name": name})

    # --- hosts (write) ---
    def create_host(self, payload: dict) -> dict:
        return self.post("/api/hosts", json=payload)

    def update_host(self, uuid: str, **fields) -> dict:
        return self.patch("/api/hosts", json={"uuid": uuid, **fields})

    def delete_host(self, uuid: str) -> dict:
        return self.delete(f"/api/hosts/{uuid}")
```

- [ ] **Step 2: Syntax-check**

Run: `python3 -c "import ast; ast.parse(open('infra/remnawave/_lib/client.py').read())"`
Expected: no output (parse OK).

- [ ] **Step 3: Commit**

```bash
git add infra/remnawave/_lib/client.py
git commit -m "feat(remnawave/client): add subscription-templates/hosts/squads CRUD methods"
```

---

## Task 3: Реализовать apply-protection-modes команду

**Files:**
- Modify: `infra/remnawave/apply.py:158-159` (insert new subparser before `# Stages to follow:` comment)
- Modify: `infra/remnawave/apply.py:170` (add handler)
- Create logic inline in `apply.py` (single-file pattern matches `cmd_status`)

- [ ] **Step 1: Добавить функцию `cmd_apply_protection_modes` в `apply.py`**

После функции `cmd_status` (примерно строка 117 текущего файла) добавить:

```python
def cmd_apply_protection_modes(client: "RemnawaveClient", template_file: Path) -> int:
    """Идемпотентная установка инфраструктуры для «Полной» / «Умной защиты».

    1. Создать subscription-template smart_routing (если нет).
    2. Создать internal squad Mode-Smart (если нет).
    3. Для каждого существующего host'а: создать smart-копию (если нет),
       обновить excludedInternalSquads на full-host'ах.

    Печатает финальные UUID'ы для добавления в .env.
    """
    import json as _json
    from _lib.client import RemnawaveError

    DEFAULT_SQUAD_NAME = "Default-Squad"
    SMART_SQUAD_NAME = "Mode-Smart"
    SMART_TEMPLATE_NAME = "smart_routing"

    # Read template payload
    template_payload = _json.loads(template_file.read_text())
    template_name = template_payload.get("name", SMART_TEMPLATE_NAME)
    template_json = template_payload["templateJson"]
    template_type = template_payload.get("templateType", "XRAY_JSON")

    # 1. Subscription template — idempotent by name
    templates = client.list_subscription_templates()
    smart_template = next(
        (t for t in templates if t.get("name") == template_name and t.get("templateType") == template_type),
        None,
    )
    if smart_template is None:
        smart_template = client.create_subscription_template(template_name, template_json, template_type)
        print(f"Created subscription-template '{template_name}' uuid={smart_template.get('uuid')}")
    else:
        print(f"Skip subscription-template '{template_name}' — already exists uuid={smart_template.get('uuid')}")
    smart_template_uuid = smart_template["uuid"]

    # 2. Squads — find Default, create Mode-Smart if missing
    squads = client.list_squads()
    default_squad = next((s for s in squads if s.get("name") == DEFAULT_SQUAD_NAME), None)
    if default_squad is None:
        print(f"ERROR: Default squad '{DEFAULT_SQUAD_NAME}' not found. Aborting.")
        return 2
    default_squad_uuid = default_squad["uuid"]

    smart_squad = next((s for s in squads if s.get("name") == SMART_SQUAD_NAME), None)
    if smart_squad is None:
        smart_squad = client.create_squad(SMART_SQUAD_NAME)
        print(f"Created squad '{SMART_SQUAD_NAME}' uuid={smart_squad.get('uuid')}")
    else:
        print(f"Skip squad '{SMART_SQUAD_NAME}' — already exists uuid={smart_squad.get('uuid')}")
    smart_squad_uuid = smart_squad["uuid"]

    # 3. Hosts — for each existing host (not yet a smart-copy), create smart sibling
    hosts = client.list_hosts()
    smart_remark_marker = " — Smart"
    full_hosts = [h for h in hosts if smart_remark_marker not in h.get("remark", "")]
    smart_hosts = [h for h in hosts if smart_remark_marker in h.get("remark", "")]

    # 3a. Create missing smart-copies
    smart_by_remark = {h["remark"]: h for h in smart_hosts}
    for full_h in full_hosts:
        full_remark = full_h.get("remark", "")
        smart_remark = full_remark + smart_remark_marker
        if smart_remark in smart_by_remark:
            print(f"Skip smart-host '{smart_remark}' — already exists uuid={smart_by_remark[smart_remark]['uuid']}")
            continue
        payload = {
            "inbound": full_h["inbound"],
            "remark": smart_remark,
            "address": full_h["address"],
            "port": full_h["port"],
            "sni": full_h.get("sni") or "",
            "host": full_h.get("host") or "",
            "fingerprint": full_h.get("fingerprint") or "chrome",
            "isDisabled": False,
            "securityLayer": full_h.get("securityLayer") or "DEFAULT",
            "excludedInternalSquads": [default_squad_uuid],
            "xrayJsonTemplateUuid": smart_template_uuid,
        }
        created = client.create_host(payload)
        print(f"Created smart-host '{smart_remark}' uuid={created.get('uuid')}")

    # 3b. Update existing full-hosts: exclude them from Mode-Smart squad
    for full_h in full_hosts:
        existing_excludes = set(full_h.get("excludedInternalSquads") or [])
        if smart_squad_uuid in existing_excludes:
            print(f"Skip full-host '{full_h['remark']}' — already excludes Mode-Smart")
            continue
        new_excludes = list(existing_excludes | {smart_squad_uuid})
        client.update_host(full_h["uuid"], excludedInternalSquads=new_excludes)
        print(f"Updated full-host '{full_h['remark']}' — excludedInternalSquads += Mode-Smart")

    # Final: print UUIDs for .env
    print()
    print("=== Append these to infra/.env ===")
    print(f"REMNAWAVE_SQUAD_FULL_UUID={default_squad_uuid}")
    print(f"REMNAWAVE_SQUAD_SMART_UUID={smart_squad_uuid}")
    return 0
```

- [ ] **Step 2: Зарегистрировать subcommand в `main()`**

Найти строку (примерно 157): `# Stages to follow: plan, apply, validate, destroy.`. Прямо ПЕРЕД ней добавить:

```python
    p_pm = subs.add_parser(
        "apply-protection-modes",
        help="create smart_routing template + Mode-Smart squad + smart-host copies",
    )
    p_pm.add_argument(
        "--template-file",
        type=Path,
        default=HERE / "configs" / "template_smart_routing.json",
        help="Path to smart template JSON (default: configs/template_smart_routing.json)",
    )
```

И ниже, в блоке `with RemnawaveClient() as client:` после блока `if args.cmd == "rotate-reality-key":` — добавить:

```python
            if args.cmd == "apply-protection-modes":
                return cmd_apply_protection_modes(client, args.template_file)
```

- [ ] **Step 3: Syntax-check**

Run: `python3 -c "import ast; ast.parse(open('infra/remnawave/apply.py').read())"`
Expected: no output (parse OK).

- [ ] **Step 4: Dry CLI-test**

Run: `python3 infra/remnawave/apply.py apply-protection-modes --help`
Expected: usage text shown, includes `--template-file` argument.

- [ ] **Step 5: Commit**

```bash
git add infra/remnawave/apply.py
git commit -m "feat(remnawave): apply-protection-modes — idempotent infra for full/smart"
```

---

## Task 4: Применить apply-protection-modes против production Remnawave

**Files:** none (runtime action)

- [ ] **Step 1: Скопировать обновлённый код на VPS**

```bash
rsync -avz infra/remnawave/ root@212.74.231.217:/root/cyber-berezka/infra/remnawave/
```

Expected: 3 файла отправлены — `apply.py`, `_lib/client.py`, `configs/template_smart_routing.json`.

- [ ] **Step 2: Запустить apply-protection-modes (первый прогон — создание)**

```bash
ssh root@212.74.231.217 'cd /root/cyber-berezka/infra/remnawave && python3 apply.py apply-protection-modes'
```

Expected output (примерно):
```
Created subscription-template 'smart_routing' uuid=<UUID1>
Created squad 'Mode-Smart' uuid=<UUID2>
Created smart-host 'Cyber Berezka — LV — Smart' uuid=...
Created smart-host 'Cyber Berezka — NL — Smart' uuid=...
Created smart-host 'Cyber Berezka — DE (Hetzner) — Smart' uuid=...
Updated full-host 'Cyber Berezka — LV' — excludedInternalSquads += Mode-Smart
Updated full-host 'Cyber Berezka — NL' — excludedInternalSquads += Mode-Smart
Updated full-host 'Cyber Berezka — DE (Hetzner)' — excludedInternalSquads += Mode-Smart

=== Append these to infra/.env ===
REMNAWAVE_SQUAD_FULL_UUID=5711d10a-02af-42d2-8ffc-b93322f66fd2
REMNAWAVE_SQUAD_SMART_UUID=<UUID2>
```

- [ ] **Step 3: Прогнать второй раз — проверить идемпотентность**

```bash
ssh root@212.74.231.217 'cd /root/cyber-berezka/infra/remnawave && python3 apply.py apply-protection-modes'
```

Expected: каждая строка начинается с `Skip ... already exists` или `Skip ... already excludes`.

- [ ] **Step 4: Записать UUID'ы в `infra/.env` на VPS**

```bash
ssh root@212.74.231.217 'cd /root/cyber-berezka/infra && grep -v "REMNAWAVE_SQUAD_" .env > .env.tmp && mv .env.tmp .env'
ssh root@212.74.231.217 'cat >> /root/cyber-berezka/infra/.env <<EOF
REMNAWAVE_SQUAD_FULL_UUID=5711d10a-02af-42d2-8ffc-b93322f66fd2
REMNAWAVE_SQUAD_SMART_UUID=<UUID2-fill-in>
EOF'
```

Подставить `<UUID2-fill-in>` из Step 2.

- [ ] **Step 5: Verification — существующие user'ы не затронуты**

```bash
ssh root@212.74.231.217 'cd /root/cyber-berezka/infra/remnawave && python3 -c "
import sys, os
sys.path.insert(0, \".\")
for line in open(\"../.env\").read().splitlines():
    if line.startswith(\"REMNAWAVE_\") and \"=\" in line:
        k, _, v = line.partition(\"=\"); os.environ[k.strip()] = v
from _lib.client import RemnawaveClient
with RemnawaveClient() as c:
    users = c.list_users(size=20)
    for u in users[\"users\"]:
        squads = u.get(\"activeInternalSquads\", [])
        squad_uuids = [s.get(\"uuid\") if isinstance(s, dict) else s for s in squads]
        print(f\"{u[\\\"username\\\"]}: activeInternalSquads={squad_uuids}\")
"'
```

Expected: каждый из 6 пользователей имеет `activeInternalSquads = ['5711d10a-02af-42d2-8ffc-b93322f66fd2']` (Default-Squad).

- [ ] **Step 6: Verification — скачать подписку существующего user'а**

```bash
ssh root@212.74.231.217 'cd /root/cyber-berezka/infra/remnawave && python3 -c "
import sys, os
sys.path.insert(0, \".\")
for line in open(\"../.env\").read().splitlines():
    if line.startswith(\"REMNAWAVE_\") and \"=\" in line:
        k, _, v = line.partition(\"=\"); os.environ[k.strip()] = v
from _lib.client import RemnawaveClient
import httpx, base64
with RemnawaveClient() as c:
    users = c.list_users(size=20)
    u = next(x for x in users[\"users\"] if x[\"username\"] == \"user_1\")
    sub_url = c.get(f\"/api/users/{u[\\\"uuid\\\"]}\").get(\"subscriptionUrl\")
    print(\"Subscription URL:\", sub_url)
    with httpx.Client(verify=False) as hc:
        r = hc.get(sub_url, headers={\"User-Agent\": \"v2RayTun/1.0\"})
        decoded = base64.b64decode(r.text + \"==\").decode(\"utf-8\")
        for line in decoded.splitlines():
            if line.startswith(\"vless://\"):
                print(line[:80] + \"...\")
"'
```

Expected: ровно 3 vless:// URL (LV, NL, DE) — те же, что отдавались до миграции.

---

## Task 5: Alembic-миграция для `users.protection_mode`

**Files:**
- Create: `infra/site/migrations/versions/0002_protection_mode.py`

- [ ] **Step 1: Найти текущий head revision**

Run: `cd infra/site && ls migrations/versions/`
Expected: `0001_initial.py`. Считать revision = `0001` (или открыть файл и посмотреть `revision = ...`).

- [ ] **Step 2: Создать файл миграции**

`infra/site/migrations/versions/0002_protection_mode.py`:

```python
"""add users.protection_mode

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-27 00:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "protection_mode",
            sa.String(16),
            nullable=False,
            server_default="full",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "protection_mode")
```

- [ ] **Step 3: Syntax-check**

Run: `python3 -c "import ast; ast.parse(open('infra/site/migrations/versions/0002_protection_mode.py').read())"`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add infra/site/migrations/versions/0002_protection_mode.py
git commit -m "feat(site/migrations): add users.protection_mode column"
```

---

## Task 6: Добавить `protection_mode` в User-модель

**Files:**
- Modify: `infra/site/app/models/user.py:40-41`

- [ ] **Step 1: Добавить mapped_column**

Открыть `infra/site/app/models/user.py`. После строки `locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))` (стр. 41), на новой строке добавить:

```python
    protection_mode: Mapped[str] = mapped_column(
        String(16), default="full", nullable=False, server_default="full"
    )
```

- [ ] **Step 2: Syntax-check**

Run: `python3 -c "import ast; ast.parse(open('infra/site/app/models/user.py').read())"`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add infra/site/app/models/user.py
git commit -m "feat(site/models): add User.protection_mode field (full|smart)"
```

---

## Task 7: Расширить settings новыми env vars

**Files:**
- Modify: `infra/site/app/config.py` (add 2 fields)

- [ ] **Step 1: Открыть `app/config.py` и найти класс `Settings`**

Run: `grep -n 'class Settings' infra/site/app/config.py`
Expected: одна строка `class Settings(BaseSettings):`.

- [ ] **Step 2: Добавить 2 поля в Settings (около других `remnawave_*` полей)**

Найти строки вида `remnawave_api_url: str` или `remnawave_api_token: str`. Прямо после них добавить:

```python
    remnawave_squad_full_uuid: str = ""
    remnawave_squad_smart_uuid: str = ""
```

Default пустая строка — config грузится даже если переменные не заданы (на dev/CI), но `ProtectionService` ругнётся при попытке toggle до их установки.

- [ ] **Step 3: Syntax-check**

Run: `python3 -c "import ast; ast.parse(open('infra/site/app/config.py').read())"`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add infra/site/app/config.py
git commit -m "feat(site/config): add remnawave_squad_{full,smart}_uuid settings"
```

---

## Task 8: ProtectionService — бизнес-логика toggle

**Files:**
- Create: `infra/site/app/services/protection.py`

- [ ] **Step 1: Создать файл сервиса**

`infra/site/app/services/protection.py`:

```python
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
```

- [ ] **Step 2: Syntax-check**

Run: `python3 -c "import ast; ast.parse(open('infra/site/app/services/protection.py').read())"`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add infra/site/app/services/protection.py
git commit -m "feat(site/services): ProtectionService — toggle user protection mode"
```

---

## Task 9: Endpoint POST /cabinet/protection-mode

**Files:**
- Modify: `infra/site/app/routers/cabinet.py` (add new route after `keys_revoke`)

- [ ] **Step 1: Добавить импорт ProtectionService**

В начале `infra/site/app/routers/cabinet.py`, в блоке импортов после `from app.services.vpn_keys import VpnKeysService`, добавить:

```python
from app.services.protection import ProtectionService
```

- [ ] **Step 2: Добавить route в конец файла**

После функции `keys_revoke` (последняя в файле) добавить:

```python
@router.post("/protection-mode")
async def set_protection_mode(
    mode: str = Form(..., pattern="^(full|smart)$"),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(verify_csrf_token),
):
    if not user.is_approved:
        return RedirectResponse(url="/cabinet", status_code=303)
    rw = RemnawaveAPI()
    try:
        await ProtectionService(db, rw).set_mode(user, mode)  # type: ignore[arg-type]
    finally:
        await rw.aclose()
    return RedirectResponse(url="/cabinet?mode_updated=1", status_code=303)
```

- [ ] **Step 3: Syntax-check**

Run: `python3 -c "import ast; ast.parse(open('infra/site/app/routers/cabinet.py').read())"`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add infra/site/app/routers/cabinet.py
git commit -m "feat(site/routers): POST /cabinet/protection-mode endpoint"
```

---

## Task 10: Toggle-карточка в /cabinet/index.html

**Files:**
- Modify: `infra/site/app/templates/cabinet/index.html` (insert above «Доступные серверы»)

- [ ] **Step 1: Прочитать текущий index.html для context**

Run: `head -30 infra/site/app/templates/cabinet/index.html`
Expected: видим `<section>Доступные серверы</section>` блок около стр. 19.

- [ ] **Step 2: Добавить toggle-карточку ПЕРЕД блоком «Доступные серверы»**

Открыть `infra/site/app/templates/cabinet/index.html`. Найти строку `<section class="bg-bg-card border border-border-light rounded-lg shadow-card p-6 mb-6">` (которая открывает «Доступные серверы», стр. ~19). Прямо ПЕРЕД ней добавить:

```html
  <section id="protection-mode-card" class="bg-bg-card border-2 border-accent-gold rounded-lg shadow-card p-6 mb-6">
    {% if request.query_params.get('mode_updated') %}
      <p class="text-success text-sm mb-3">Режим переключён. Обновите подписку в VPN-клиенте, чтобы применить.</p>
    {% endif %}
    <div class="flex items-center justify-between gap-4 mb-2">
      <div>
        <div id="mode-title" class="font-medium text-base">
          {% if user.protection_mode == 'smart' %}⚡ Умная защита{% else %}🛡️ Полная защита{% endif %}
        </div>
        <div id="mode-short" class="text-sm text-text-muted mt-1">
          {% if user.protection_mode == 'smart' %}Российские сайты — напрямую, остальное — через защищённое соединение.{% else %}Весь интернет-трафик идёт через защищённое соединение.{% endif %}
        </div>
      </div>
      <div class="flex gap-2">
        <form method="POST" action="/cabinet/protection-mode" class="inline">
          <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token or '' }}">
          <input type="hidden" name="mode" value="full">
          <button type="submit"
                  class="px-4 py-2 rounded-full text-sm {% if user.protection_mode != 'smart' %}bg-bg-main text-accent-goldDk font-medium shadow-sm{% else %}text-text-muted hover:bg-bg-main/60{% endif %}">
            🛡️ Полная
          </button>
        </form>
        <form method="POST" action="/cabinet/protection-mode" class="inline">
          <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token or '' }}">
          <input type="hidden" name="mode" value="smart">
          <button type="submit"
                  class="px-4 py-2 rounded-full text-sm {% if user.protection_mode == 'smart' %}bg-bg-main text-accent-goldDk font-medium shadow-sm{% else %}text-text-muted hover:bg-bg-main/60{% endif %}">
            ⚡ Умная
          </button>
        </form>
      </div>
    </div>
    <p class="text-xs text-text-muted mt-3 pt-3 border-t border-border-light">
      {% if user.protection_mode == 'smart' %}
        Банк-клиенты, госуслуги и российские медиа открываются <strong>напрямую</strong> — без замедления и антифрод-предупреждений. Зарубежные сервисы — через защищённое соединение.
      {% else %}
        Все сайты и приложения подключаются <strong>через защищённое соединение</strong>. Российские банк-клиенты и госуслуги могут срабатывать с антифрод-проверкой («вход из необычного места») или открываться медленнее.
      {% endif %}
    </p>
  </section>
```

- [ ] **Step 3: Jinja-check**

Run: `python3 -c "import jinja2; jinja2.Environment(loader=jinja2.FileSystemLoader('infra/site/app/templates')).get_template('cabinet/index.html')"`
Expected: no output (parse OK).

- [ ] **Step 4: Commit**

```bash
git add infra/site/app/templates/cabinet/index.html
git commit -m "feat(site/cabinet): protection-mode toggle card on cabinet home"
```

---

## Task 11: Документация в .env.example (опц.)

**Files:**
- Modify: `infra/.env.example` (если существует) — добавить новые vars в шаблон.

- [ ] **Step 1: Проверить существование `.env.example`**

Run: `ls infra/.env.example 2>/dev/null && echo EXISTS || echo MISSING`

- [ ] **Step 2: Если EXISTS — добавить документацию**

Открыть `infra/.env.example`. После последней `REMNAWAVE_*` строки добавить:

```
# Protection-modes feature (filled in by `apply.py apply-protection-modes`)
REMNAWAVE_SQUAD_FULL_UUID=
REMNAWAVE_SQUAD_SMART_UUID=
```

- [ ] **Step 3: Если MISSING — skip task** (нет конвенции .env.example в проекте).

- [ ] **Step 4: Commit (только если файл был изменён)**

```bash
git add infra/.env.example
git commit -m "docs(env): document REMNAWAVE_SQUAD_{FULL,SMART}_UUID"
```

---

## Task 12: Deploy объединённого батча (Security P1 + protection-modes)

**Files:** none (runtime action на VPS)

- [ ] **Step 1: Push local commits в remote**

```bash
git push origin main
```

Expected: pushed ~6 коммитов (security A/B/C/D + protection-modes Tasks 1-11).

- [ ] **Step 2: Pull на VPS**

```bash
ssh root@212.74.231.217 'cd /root/cyber-berezka && git fetch origin main && git reset --hard origin/main'
```

Expected: HEAD на текущем main.

- [ ] **Step 3: Применить миграцию БД**

```bash
ssh root@212.74.231.217 'cd /root/cyber-berezka && docker compose -f infra/compose/docker-compose.coordinator.yml exec site alembic upgrade head'
```

Expected: log `Running upgrade 0001 -> 0002, add users.protection_mode`.

- [ ] **Step 4: Restart site container**

```bash
ssh root@212.74.231.217 'cd /root/cyber-berezka && docker compose -f infra/compose/docker-compose.coordinator.yml restart site'
```

Expected: container up в течение 10s.

- [ ] **Step 5: Smoke-test — site доступен**

```bash
ssh root@212.74.231.217 'curl -fs http://localhost:8000/healthz'
```

Expected: `{"status":"ok"}`.

- [ ] **Step 6: Smoke-test — auth работает**

```bash
curl -I https://212-74-231-217.nip.io/auth/login 2>&1 | head -1
```

Expected: `HTTP/2 200`.

---

## Task 13: Регрессионная проверка существующих пользователей

**Files:** none (runtime)

- [ ] **Step 1: Существующий user может залогиниться**

В браузере (manual): открыть `https://212-74-231-217.nip.io/auth/login`, ввести creds одного из 6 существующих user'ов, нажать «Войти».
Expected: попадает на `/cabinet`, видит карточку «🛡️ Полная защита» (active), сервера, кнопку «Управление ключами».

- [ ] **Step 2: Существующий ключ в подписке тот же**

В кабинете → «Управление ключами» → раскрыть существующий ключ. Скопировать vless://-URL.
Expected: URL совпадает с тем, что был до deploy (тот же address, port, uuid).

- [ ] **Step 3: Подписка отдаёт те же 3 host'а**

В терминале:
```bash
curl -s -H "User-Agent: v2RayTun/1.0" "<subscription-url>" | base64 -d | grep -c "^vless://"
```
Expected: `3`.

---

## Task 14: Toggle на «Умная защиту» работает

**Files:** none (runtime)

- [ ] **Step 1: Нажать «⚡ Умная» в браузере**

После Task 13 Step 1 — в карточке нажать кнопку «⚡ Умная».
Expected: страница перезагружается, карточка показывает «⚡ Умная защита» (active), сообщение «Режим переключён. Обновите подписку...».

- [ ] **Step 2: В БД protection_mode обновился**

```bash
ssh root@212.74.231.217 'cd /root/cyber-berezka && docker compose -f infra/compose/docker-compose.coordinator.yml exec -T site psql $DATABASE_URL -c "SELECT id, email, protection_mode FROM users ORDER BY id"'
```

Expected: 5 user'ов с `protection_mode=full`, 1 (текущий) с `protection_mode=smart`.

- [ ] **Step 3: В Remnawave activeInternalSquads обновился**

```bash
ssh root@212.74.231.217 'cd /root/cyber-berezka/infra/remnawave && python3 -c "
import sys, os
sys.path.insert(0, \".\")
for line in open(\"../.env\").read().splitlines():
    if line.startswith(\"REMNAWAVE_\") and \"=\" in line:
        k, _, v = line.partition(\"=\"); os.environ[k.strip()] = v
from _lib.client import RemnawaveClient
with RemnawaveClient() as c:
    user = next(u for u in c.list_users(size=20)[\"users\"] if u[\"username\"] == \"user_1\")
    print(user[\"username\"], user.get(\"activeInternalSquads\"))
"'
```

Expected: `activeInternalSquads` user_1 содержит UUID Mode-Smart squad.

- [ ] **Step 4: Подписка отдаёт smart-host'ы**

В кабинете обновить страницу /cabinet/keys → скопировать subscription URL → выполнить:
```bash
curl -s -H "User-Agent: v2RayTun/1.0" "<subscription-url>" | head -100
```
Expected: НЕ base64-blob, а JSON c полем `routing.rules` содержащим `geoip:ru` и `geosite:category-bank-ru`.

---

## Task 15: Toggle обратно на «Полную» работает

**Files:** none (runtime)

- [ ] **Step 1: Нажать «🛡️ Полная» в браузере**

Expected: страница перезагружается, состояние возвращается к «Полная защита».

- [ ] **Step 2: БД и Remnawave обновились в обратную сторону**

Повторить запросы из Task 14 Step 2-4 — `protection_mode = full`, `activeInternalSquads` снова `[Default-Squad-UUID]`, подписка снова отдаёт base64 vless-список.

---

## Task 16: Проверка реальной маршрутизации (опционально, требует VPN-клиента)

**Files:** none (runtime, требует VPN-клиента на устройстве проверяющего)

- [ ] **Step 1: На клиенте установить smart-режим, обновить подписку**

В VPN-клиенте (v2RayTun или Hiddify) импортировать subscription URL, обновить, подключиться.

- [ ] **Step 2: Проверить direct-routing российских ресурсов**

В браузере открыть `https://www.gosuslugi.ru`. Включить devtools → Network → посмотреть IP-адрес resolve'а — должен быть прямой (не через 212.74.231.217). Альтернативно — открыть `https://2ip.ru` (он покажет внешний IP клиента → должен совпадать с реальным IP пользователя, не нашей ноды).

- [ ] **Step 3: Проверить proxy-routing зарубежных**

Открыть `https://whoer.net` или `https://ipinfo.io` → IP должен совпадать с одной из наших нод (LV/NL/DE).

- [ ] **Step 4: Если step 2 не проходит — fallback расследование**

Если `gosuslugi.ru` идёт через наш VPN — значит:
- routing rule не применился (geoip:ru файлы не подгружены на клиенте → нужно обновить клиент)
- ИЛИ Xray template неправильный — проверить JSON через `curl <sub_url>` → grep `routing`.

---

## Task 17: Обновить документацию

**Files:**
- Modify: `docs/operations/backlog.md` (зачеркнуть Кейс 1 как сделанное)
- Modify: `docs/superpowers/audits/2026-05-26-auth-sessions-audit.md` (отметить deploy P1 как done)

- [ ] **Step 1: backlog.md — отметить Кейс 1 как DONE**

В разделе «Xray JSON Advanced — продуктовые кейсы», перед заголовком «Кейс 1 — RU-direct routing» добавить:

```markdown
**Status 2026-05-27:** DONE. Реализовано через Squad-per-mode архитектуру (`docs/superpowers/specs/2026-05-27-protection-modes-design.md`, plan `docs/superpowers/plans/2026-05-27-protection-modes.md`).
```

- [ ] **Step 2: audit doc — отметить deploy как done**

Открыть `docs/superpowers/audits/2026-05-26-auth-sessions-audit.md`, в конце секции «Резюме выполнения» добавить:

```markdown

**Deploy status 2026-05-27:** P1 батч задеплоен на production (Beget VPS 212.74.231.217) вместе с protection-modes фичей. Существующие пользователи разлогинены (ожидаемо после хэширования session_id) — повторно вошли без проблем.
```

- [ ] **Step 3: Commit**

```bash
git add docs/
git commit -m "docs: mark protection-modes case 1 + security P1 as deployed"
git push origin main
```

---

## Self-Review

**Spec coverage:**
- Архитектура (Squad-per-mode, excludedInternalSquads) → Tasks 1-4 ✓
- Data model (User.protection_mode) → Tasks 5-6 ✓
- Config (settings) → Task 7 ✓
- Service (ProtectionService) → Task 8 ✓
- Router (POST /protection-mode) → Task 9 ✓
- UI (toggle card в /cabinet) → Task 10 ✓
- Migration без disruption → Tasks 4 step 5-6 (verification) + Task 13 ✓
- Verification criteria — все 8 пунктов покрыты Tasks 4 step 5-6 / 13 / 14 / 15 / 16 ✓
- Open Questions (точная структура XRAY_JSON с injectHosts, client-cache) → Task 14 step 4 + Task 16 (если не сработает — fallback в Task 16 step 4) ✓

**Placeholder scan:** none — все шаги содержат конкретный код / команды / expected output.

**Type consistency:** `ProtectionMode = Literal["full", "smart"]` определён в Task 8, используется в Task 9 (без явного re-import — FastAPI Form pattern accepts str с runtime regex). Mode-Smart squad UUID появляется в Task 4 → используется в Task 7 / 14. Consistency OK.

**Gap notes:**
- Security P1 деплоится В ТОМ ЖЕ батче (Task 12). Этот план явно про protection-modes, но Task 12 объединяет с P1 — это сознательный батч, согласован с пользователем.
- Тесты pytest — отсутствуют в проекте, не добавляем. Manual smoke + AST + Jinja + production curl-verification — текущий стиль проекта.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-27-protection-modes.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — я диспетчирую свежего subagent'а на каждую task, ревью между task'ами, быстрая итерация.

**2. Inline Execution** — выполнение task'ов в этой сессии, batch-execution с checkpoints для ревью.

**Который подход выбираете?**
