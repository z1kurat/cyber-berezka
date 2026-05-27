# Design — Protection Modes («Полная» / «Умная защита»)

**Дата:** 2026-05-27
**Brainstorm session:** `.superpowers/brainstorm/77960-1779826123/`
**Backlog ref:** «Xray JSON Advanced — продуктовые кейсы, Кейс 1 — RU-direct routing»
**Status:** READY FOR REVIEW

---

## Цель

Дать пользователю возможность выбрать один из двух режимов работы защищённого соединения:

- **«Полная защита»** (default) — весь интернет-трафик идёт через защищённое соединение (текущее поведение).
- **«Умная защита»** — российские ресурсы (geoip:ru + geosite:category-{bank,gov,media}-ru) идут **напрямую**, остальное — через защищённое соединение.

Цель — снизить трение для пользователей, которым российские банк-клиенты / госуслуги мешают работать в режиме «всё через VPN».

## Принятые решения (брейншторм Q1–Q6)

| # | Вопрос | Решение |
|---|---|---|
| Q1 | Default | «Полная защита» |
| Q2 | Scope | Per-user (один тумблер на пользователя сайта) |
| Q3 | Архитектура VpnKey | Текущая (1 Remnawave-user на 1 site-user). Refactoring в backlog. |
| Q4 | Терминология | «Полная защита» / «Умная защита» |
| Q5 | Размещение UI | Карточка наверху `/cabinet`, толкер с динамической сменой описания |
| Q6 | Backend strategy | **Squad-per-mode**: 2 squad'а в Remnawave, host'ы фильтруются по `excludedInternalSquads` |

## Дополнительные constraints

- Существующие 6 пользователей и их подписки не должны заметить никаких изменений.
- Текущий Default-Squad (`5711d10a-02af-42d2-8ffc-b93322f66fd2`) остаётся "источником" для режима «Полная защита».

---

## Архитектура

### Remnawave-сторона

```
Profile: Default-Profile (existing)
   └── Inbound: VLESS-Reality (existing, port 8443, sni microsoft)

Squads:
   ├── Default-Squad (existing, uuid 5711d10a-...)   → «Полная защита»
   └── Mode-Smart (NEW)                              → «Умная защита»

Subscription Templates:
   └── smart_routing (NEW)                           → XRAY_JSON с RU-direct rules

Hosts:
   ├── Cyber Berezka — LV (existing, address 212.74.231.217)
   │      excludedInternalSquads: [Mode-Smart-UUID]   ← обновляем
   │      xrayJsonTemplateUuid: null                  ← flat vless как сейчас
   ├── Cyber Berezka — NL (existing, address 194.87.208.112)
   │      excludedInternalSquads: [Mode-Smart-UUID]   ← обновляем
   ├── Cyber Berezka — DE (existing, address 159.69.198.143)
   │      excludedInternalSquads: [Mode-Smart-UUID]   ← обновляем
   ├── LV — Smart (NEW, same address 212.74.231.217)
   │      excludedInternalSquads: [Default-Squad-UUID]
   │      xrayJsonTemplateUuid: smart_routing-UUID
   ├── NL — Smart (NEW, same address 194.87.208.112)
   │      excludedInternalSquads: [Default-Squad-UUID]
   │      xrayJsonTemplateUuid: smart_routing-UUID
   └── DE — Smart (NEW, same address 159.69.198.143)
          excludedInternalSquads: [Default-Squad-UUID]
          xrayJsonTemplateUuid: smart_routing-UUID

Users:
   ├── 6 existing user_* → activeInternalSquads = [Default-Squad-UUID]
   │                       Видят только 3 full-host'а → нулевое disruption.
   └── New user (post-deploy) → создаётся в Default-Squad (текущий код)
```

### Почему так

- Host имеет поле `excludedInternalSquads: list[uuid]` (negative-фильтр). По умолчанию `[]` = доступен всем.
- Mode-Smart squad содержит **0 явно привязанных host'ов**, но видит smart-host'ы, потому что:
  - smart-host'ы исключают Default-Squad → НЕ показываются user'ам в Default-Squad,
  - и НЕ исключают Mode-Smart → показываются user'ам в Mode-Smart.
- Аналогично для full-host'ов и Default-Squad — взаимно эксклюзивные множества.

### Сайт-сторона (FastAPI)

**Data model:**

```python
# app/models/user.py
class User(...):
    protection_mode: Mapped[str] = mapped_column(
        String(16), default="full", nullable=False, server_default="full"
    )
    # Допустимые значения: "full" | "smart"
```

Поле дублирует squad-attachment в Remnawave для UI-рендера (чтобы не дёргать Remnawave при каждом GET /cabinet). Source of truth для routing-логики — Remnawave squad.

**Config:**

```python
# app/config.py
class Settings(BaseSettings):
    ...
    remnawave_squad_full_uuid: str
    remnawave_squad_smart_uuid: str
```

Заполняются в `infra/.env` после применения migration-скрипта (см. ниже).

**Service:**

```python
# app/services/protection.py (NEW)
class ProtectionService:
    """Toggle a user's protection mode = Remnawave squad swap + local DB update."""

    def __init__(self, db: AsyncSession, rw: RemnawaveAPI):
        self.db = db
        self.rw = rw

    async def set_mode(self, user: User, mode: Literal["full", "smart"]) -> None:
        if mode not in ("full", "smart"):
            raise ValueError("invalid mode")
        if user.protection_mode == mode:
            return
        squad_uuid = (
            settings.remnawave_squad_full_uuid if mode == "full"
            else settings.remnawave_squad_smart_uuid
        )
        # Order: RW first, DB second. If RW fails, DB stays consistent.
        # If DB fails, next /cabinet read shows stale mode but routing is already
        # switched — user will see a one-time inconsistency, self-heals on next toggle.
        if user.remnawave_user_uuid:
            await self.rw.update_user(
                user.remnawave_user_uuid,
                activeInternalSquads=[squad_uuid],
            )
        user.protection_mode = mode
        await self.db.commit()
```

**Router:**

```python
# app/routers/cabinet.py (extend)
@router.post("/protection-mode")
async def set_protection_mode(
    mode: str = Form(..., regex="^(full|smart)$"),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(verify_csrf_token),
):
    if not user.is_approved:
        return RedirectResponse(url="/cabinet", status_code=303)
    rw = RemnawaveAPI()
    try:
        await ProtectionService(db, rw).set_mode(user, mode)
    finally:
        await rw.aclose()
    return RedirectResponse(url="/cabinet?mode_updated=1", status_code=303)
```

**UI:** карточка наверху `/cabinet/index.html`, форма POST с CSRF-токеном и hidden `mode=full|smart`. Inline JS для динамической смены описания (вариант A из brainstorm). Решение по выносу inline-JS в static — в backlog (P2 пункт security-аудита, не блокирует эту фичу).

---

## Migration (deploy-time)

### Шаг 1 — Subscription template для smart-режима

JSON-template для XRAY_JSON, ru-direct rules:

```json
{
  "routing": {
    "rules": [
      {
        "type": "field",
        "ip": ["geoip:ru", "geoip:private"],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "domain": [
          "geosite:category-gov-ru",
          "geosite:category-bank-ru",
          "geosite:category-media-ru"
        ],
        "outboundTag": "direct"
      }
    ]
  }
}
```

Сохранить в `infra/remnawave/configs/template_smart_routing.json`. Создать через `POST /api/subscription-templates` (нужно уточнить точное имя endpoint'а — `apply.py` сейчас не реализует subscription-templates CRUD).

### Шаг 2 — Создать Mode-Smart squad

`POST /api/internal-squads` payload:
```json
{"name": "Mode-Smart"}
```

### Шаг 3 — Создать 3 smart-host'а

Для каждого из 3 существующих host'ов делаем "копию" с modifications:
- Same `address`, `port`, `sni`, `host`, `inbound`, `fingerprint`.
- `remark` = `LV — Smart` / `NL — Smart` / `DE — Smart`.
- `excludedInternalSquads = [Default-Squad-UUID]`.
- `xrayJsonTemplateUuid = <smart_template_uuid>`.

Open question (см. ниже): Remnawave допускает 2 host'а с одинаковым `address:port`?

### Шаг 4 — Обновить existing host'ы

`PATCH /api/hosts/{uuid}` для каждого из 3 existing host'ов:
- `excludedInternalSquads = [Mode-Smart-UUID]`.

### Шаг 5 — Записать UUID'ы в .env

```bash
REMNAWAVE_SQUAD_FULL_UUID=5711d10a-02af-42d2-8ffc-b93322f66fd2
REMNAWAVE_SQUAD_SMART_UUID=<new-uuid>
```

### Шаг 6 — DB migration

Alembic 0002:
```python
op.add_column(
    "users",
    sa.Column(
        "protection_mode", sa.String(16),
        nullable=False, server_default="full",
    ),
)
```

### Шаг 7 — Deploy code

После шагов 1-6 — выкатить новый код. Существующие user'ы остаются в Default-Squad, видят те же host'ы. UI показывает toggle с `mode = "full"` (default), переключение работает.

### Шаг 8 — Verification

- `curl https://<admin-domain>/api/users/<existing-uuid>` → `activeInternalSquads = [DefaultSquadUUID]`.
- Скачать подписку существующего user'а → vless URL'ы те же, что и до миграции.
- Создать нового user'а через регистрацию → `activeInternalSquads = [DefaultSquadUUID]`, подписка показывает full-host'ы.
- Переключить mode на smart через UI → `activeInternalSquads = [SmartSquadUUID]`, подписка переключается на smart-host'ы.
- На клиенте (v2RayTun): обновить подписку, проверить через `curl -x` что `2ip.ru` показывает наш IP, а `lkbank.ru` (или любой geosite:category-bank-ru) идёт direct.

---

## Migration-скрипт

Добавить в `infra/remnawave/apply.py` команду `apply-protection-modes`:

```bash
python3 apply.py apply-protection-modes \
    --template-file configs/template_smart_routing.json
```

Скрипт:
1. Идемпотентно создаёт subscription-template (если нет).
2. Идемпотентно создаёт `Mode-Smart` squad (если нет).
3. Для каждого существующего host'а — создаёт smart-копию (если нет).
4. Обновляет `excludedInternalSquads` на existing и new host'ах.
5. Печатает UUID'ы для добавления в `.env`.

Скрипт коммитится в репо, выполняется один раз вручную перед deploy кода.

---

## Verified (2026-05-27 via live API)

1. **Дубликаты `address:port` — РАЗРЕШЕНЫ.** Тестовый `POST /api/hosts` с тем же `address:212.74.231.217 port:8443` что у существующего LV-host'а вернул 200 с новым UUID. Удалили cleanup-ом. → Migration работает без второго port'а.

2. **Endpoint subscription-templates — `/api/subscription-templates`.** Уже существует 5 default-шаблонов (XRAY_JSON / MIHOMO / STASH / CLASH / SINGBOX). XRAY_JSON-шаблон `Default` (uuid `0b37f7d9-...`) **не привязан** ни к одному host'у — существующие host'ы имеют `xrayJsonTemplateUuid: null` и отдают плоский base64-vless. Это важно: при привязке нашего нового `smart_routing` template к smart-host'ам клиенты в smart-режиме получат XRAY_JSON, а full-host'ы продолжат отдавать flat vless (нулевое disruption).

3. **VpnKey.meta.address работает** — поскольку smart-host'ы имеют ТЕ ЖЕ `address` что и full-host'ы, существующее поле `meta.address` (хранящее IP) корректно матчится в обоих режимах.

## Open Questions (verify в implementation-фазе)

1. **Точная структура XRAY_JSON template с `injectHosts`** — существующий `Default` template не содержит `outbounds.proxy`, что значит Remnawave добавляет proxy-outbound автоматически из данных host'а. Документация упоминает `injectHosts` поле, но в API-detail оно не видно. Нужно опытным путём проверить: добавить рутинг-правила в smart template и проверить, что Remnawave корректно генерирует client-config с правильным proxy-outbound.

2. **Client-side cache подписки** — как быстро v2RayTun/Hiddify подхватывают новый template после toggle? Если кэшируют дольше 5 минут — нужен UI-prompt «Откройте приложение и нажмите Обновить подписку».

3. **Failure mode при недоступности Remnawave** — план: `set_mode` сначала вызывает Remnawave, при ошибке — exception, DB не меняется, UI показывает «Не удалось переключить». Для MVP оставляем sync-fail.

---

## Не в скоупе этой задачи

- Refactoring «1 Remnawave-user на 1 VpnKey» — отдельный эпик в backlog. Без него **режим всё равно per-user, не per-key**.
- Выбор конкретных geosite-категорий для RU-direct — стартуем с `category-{gov,bank,media}-ru`, расширяем по фидбеку.
- UI redesign (Direction A «Премиум-кремовое») — отдельный эпик, новая карточка получит финальный visual когда дойдём.
- Перенос inline-JS toggle в static — security-аудит P2 пункт 6, отдельной волной.

---

## Verification criteria (Phase 3 plan-do-verify)

- [ ] DB migration 0002 применяется без ошибок; `users.protection_mode` default="full".
- [ ] `apply-protection-modes` создаёт template, squad, 3 smart-host'а; повторный запуск — no-op.
- [ ] Существующие 6 user'ов после migration: `activeInternalSquads = [DefaultSquadUUID]`, подписка отдаёт те же 3 host'а.
- [ ] Новый user после deploy: `protection_mode = "full"`, попадает в DefaultSquad, видит 3 host'а.
- [ ] Toggle на «Умную» через UI: `protection_mode = "smart"`, `activeInternalSquads = [SmartSquadUUID]`, подписка отдаёт 3 smart-host'а с XRAY_JSON template.
- [ ] На клиенте проверено что в smart-режиме `lkbank.ru` идёт direct (геолокация показывает RU), а `whoer.net` показывает наш IP.
- [ ] Toggle обратно на «Полную»: всё возвращается. Counter повторных переключений в audit-log.
- [ ] CSRF проверка работает на `/cabinet/protection-mode`.
- [ ] AST + Jinja parse OK для всех затронутых файлов.

---

## Файлы, которые будут затронуты

- `infra/remnawave/configs/template_smart_routing.json` (NEW)
- `infra/remnawave/apply.py` (extend: команда apply-protection-modes)
- `infra/remnawave/_lib/client.py` (extend: subscription-templates CRUD, host POST/PATCH с smart-полями)
- `infra/site/migrations/versions/0002_protection_mode.py` (NEW)
- `infra/site/app/models/user.py` (+protection_mode)
- `infra/site/app/config.py` (+squad UUID env vars)
- `infra/site/app/services/protection.py` (NEW)
- `infra/site/app/routers/cabinet.py` (+/protection-mode POST + cabinet_home рендер)
- `infra/site/app/templates/cabinet/index.html` (+toggle card + inline JS)
- `infra/.env` (+ REMNAWAVE_SQUAD_{FULL,SMART}_UUID)
- `infra/.env.example` (same — для документации)
