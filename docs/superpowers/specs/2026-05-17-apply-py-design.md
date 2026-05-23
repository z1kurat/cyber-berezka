# apply.py — Declarative Remnawave Provisioning Tool

**Дата:** 2026-05-17
**Назначение:** заменить все ручные операции в Remnawave UI и SQL-INSERT'ы на декларативное управление через REST API. Конфигурация — в git, применение — одной командой.
**Статус:** дизайн утверждён, реализация в этой сессии (Stage 2-3) + следующая (Stage 4-6).

---

## 1. Контекст и проблема

После развёртывания cyber-berezka накоплены ручные операции в Remnawave panel:
- Создание Default-Profile с raw Xray JSON (через UI)
- Подвязка Default-Squad к VLESS-inbound (SQL INSERT)
- Создание Host для inbound (SQL INSERT)
- Создание ноды (через UI)
- UPDATE адреса ноды в БД (SQL UPDATE)
- Изменение routing rules в profile JSON (SQL UPDATE)

Каждая из этих операций воспроизводимо плохо. При пересоздании окружения — повторение всех ручных шагов. При работе в команде — отсутствие audit trail.

**Цель:** один файл — `infra/remnawave/configs/*.yaml` — single source of truth. `apply.py apply` приводит panel к этому состоянию.

---

## 2. Архитектурные решения (закрепляемые)

| # | Вопрос | Решение |
|---|---|---|
| Q1 | state.json в git? | **Да, Terraform-style.** `infra/remnawave/state.json` хранит маппинг declaration→UUID. Приватный репо |
| Q2 | Секреты | `.env` на VPS для MVP, SOPS позже |
| Q3 | YAML уровень | **Гибрид:** базовый Xray-JSON в `profile.json` + параметризация через `.env` (порты, IPv6) |
| Q4 | API token bootstrap | Один UI клик в panel → `.env` |

---

## 3. CLI интерфейс

```
apply.py status                    # текущее состояние Remnawave (read-only)
apply.py plan                      # diff: что изменится при apply
apply.py apply                     # применить YAML
apply.py apply --auto-approve      # без подтверждения
apply.py apply --target=users      # только пользователей
apply.py import                    # импорт текущего состояния → YAML + state.json
apply.py destroy <type> <name>     # удалить объект (только из panel, не из YAML)
apply.py validate                  # валидация YAML без API-запросов
```

Все команды поддерживают `--dry-run` (только plan, без apply).

---

## 4. Файловая структура

```
infra/remnawave/
├── apply.py                        # main entrypoint
├── _lib/
│   ├── __init__.py
│   ├── client.py                   # RemnawaveClient — обёртка над httpx
│   ├── models.py                   # Pydantic models из OpenAPI
│   ├── plan.py                     # diff между YAML и API state
│   ├── apply.py                    # выполнение plan'а
│   ├── state.py                    # state.json IO
│   └── config.py                   # загрузка YAML
├── configs/
│   ├── profile.yaml                # один Xray profile (вкл. inbounds, outbounds, routing)
│   ├── nodes.yaml                  # список нод
│   ├── squads.yaml                 # internal squads (имя, к каким inbound подвязаны)
│   ├── hosts.yaml                  # hosts (как inbound видится клиентам)
│   └── users.yaml                  # тестовые пользователи
├── state.json                      # UUIDs текущего состояния (git-tracked)
├── openapi.json                    # снапшот OpenAPI v2.7.4 (reference)
└── README.md                       # как пользоваться
```

---

## 5. Endpoint mapping (из OpenAPI)

| Тип объекта | List | Create | Update | Delete | Get one |
|---|---|---|---|---|---|
| API token | `GET /api/tokens` | `POST /api/tokens` | — | `DELETE /api/tokens/{uuid}` | — |
| Config Profile | `GET /api/config-profiles` | `POST /api/config-profiles` | `PATCH /api/config-profiles` | `DELETE /api/config-profiles/{uuid}` | `GET /api/config-profiles/{uuid}` |
| Internal Squad | `GET /api/internal-squads` | `POST /api/internal-squads` | `PATCH /api/internal-squads` | `DELETE /api/internal-squads/{uuid}` | `GET /api/internal-squads/{uuid}` |
| Node | `GET /api/nodes` | `POST /api/nodes` | `PATCH /api/nodes` | `DELETE /api/nodes/{uuid}` | `GET /api/nodes/{uuid}` |
| Host | `GET /api/hosts` | `POST /api/hosts` | `PATCH /api/hosts` | `DELETE /api/hosts/{uuid}` | `GET /api/hosts/{uuid}` |
| User | `GET /api/users` | `POST /api/users` | `PATCH /api/users` | `DELETE /api/users/{uuid}` | `GET /api/users/{uuid}` |
| User→Squad | — | `POST /api/internal-squads/{uuid}/bulk-actions/add-users` | — | `DELETE /api/internal-squads/{uuid}/bulk-actions/remove-users` | — |
| Reality keypair | — | `GET /api/system/tools/x25519/generate` (returns 30 pairs) | — | — | — |

**Авторизация:** все требуют `Authorization: Bearer <API_TOKEN>` в header.

---

## 6. Pydantic-модели (из OpenAPI POST schemas)

### User (POST /api/users)
```python
class UserCreate(BaseModel):
    username: str
    status: Literal["ACTIVE", "DISABLED", "LIMITED", "EXPIRED"] = "ACTIVE"
    expireAt: datetime  # required
    trafficLimitBytes: int = 0  # 0 = unlimited
    trafficLimitStrategy: Literal["NO_RESET", "DAY", "WEEK", "MONTH", "MONTH_ROLLING"] = "NO_RESET"
    activeInternalSquads: list[UUID] = []
    email: EmailStr | None = None
    telegramId: int | None = None
    description: str | None = None
    hwidDeviceLimit: int | None = None
    tag: str | None = None
    # advanced (auto-generated if not set):
    shortUuid: str | None = None
    vlessUuid: UUID | None = None
    trojanPassword: str | None = None
    ssPassword: str | None = None
```

### Internal Squad
```python
class InternalSquadCreate(BaseModel):
    name: str
    inbounds: list[UUID]  # UUIDs of inbounds (from profile)
```

### Node
```python
class NodeConfigProfile(BaseModel):
    activeConfigProfileUuid: UUID
    activeInbounds: list[UUID]

class NodeCreate(BaseModel):
    name: str
    address: str  # 172.21.0.1 (от panel container к host)
    port: int = 2222
    countryCode: str  # "NL"
    configProfile: NodeConfigProfile
    isTrafficTrackingActive: bool = False
    consumptionMultiplier: float = 1.0
    tags: list[str] = []
```

### Host
```python
class HostInbound(BaseModel):
    configProfileUuid: UUID
    configProfileInboundUuid: UUID

class HostCreate(BaseModel):
    inbound: HostInbound
    remark: str  # "NL Amsterdam" — видно клиенту
    address: str  # 194.87.83.31 — публичный IP/hostname
    port: int  # 2053
    sni: str  # "www.microsoft.com"
    fingerprint: Literal["chrome", "firefox", "safari", "ios", "android", "edge", "qq", "random", "randomized"] = "chrome"
    securityLayer: Literal["DEFAULT", "TLS", "NONE"] = "DEFAULT"
    alpn: Literal["h3", "h2", "http/1.1", "h2,http/1.1", "h3,h2,http/1.1", "h3,h2"] | None = None
    isDisabled: bool = False
    isHidden: bool = False
```

### Config Profile
```python
class ConfigProfileCreate(BaseModel):
    name: str  # "Default-Profile"
    config: dict  # raw Xray config: {log, dns, inbounds, outbounds, routing}
```

---

## 7. YAML структура (примеры)

### `configs/profile.yaml`
```yaml
name: Default-Profile
xray_config_template: profile.json   # путь к raw Xray JSON
xray_config_params:                  # параметры подставляются в JSON
  reality_port: 2053
  reality_dest: www.microsoft.com:443
  reality_server_names: ["www.microsoft.com"]
  reality_private_key: ${REALITY_PRIVATE_KEY}  # из .env
  reality_short_ids: ${REALITY_SHORT_IDS}      # из .env (8 hex)
  ipv6_pool: ${IPV6_POOL}                       # список через запятую
  ipv4_only_domains:
    - geosite:category-gov-ru
    - domain:gosuslugi.ru
    # ...
```

### `configs/squads.yaml`
```yaml
- name: Default-Squad
  inbound_tags:                       # ссылки на inbound по tag (не по UUID)
    - VLESS-Reality-Vision
```

### `configs/nodes.yaml`
```yaml
- name: cuber-berezka-nl-01
  address: 172.21.0.1               # для panel-container connect
  port: 2222
  country_code: NL
  profile: Default-Profile          # ссылка на profile.yaml.name
  active_inbound_tags:
    - VLESS-Reality-Vision
  tags: [primary]
```

### `configs/hosts.yaml`
```yaml
- remark: NL Amsterdam
  inbound_tag: VLESS-Reality-Vision  # ссылка
  address: 194.87.83.31              # публичный
  port: 2053
  sni: www.microsoft.com
  fingerprint: chrome
  security_layer: DEFAULT
```

### `configs/users.yaml`
```yaml
- username: test-01
  email: test01@example.com
  expire_at: "2099-12-31T23:59:59Z"
  traffic_limit_bytes: 0           # unlimited
  squads:
    - Default-Squad
```

---

## 8. state.json (Terraform-style)

После `apply.py import` или первого `apply.py apply`:

```json
{
  "version": 1,
  "updated_at": "2026-05-17T20:00:00Z",
  "profiles": {
    "Default-Profile": {"uuid": "00000000-0000-0000-0000-000000000000"}
  },
  "inbounds": {
    "VLESS-Reality-Vision": {
      "uuid": "2d11279f-f188-47d5-bbee-4fd4145a53d6",
      "profile": "Default-Profile"
    }
  },
  "squads": {
    "Default-Squad": {"uuid": "abc69b33-4de4-40a7-8b12-9c77cc5570dc"}
  },
  "nodes": {
    "cuber-berezka-nl-01": {"uuid": "8e658171-fef6-4ac4-b6c2-c9705312ba86"}
  },
  "hosts": {
    "NL Amsterdam": {"uuid": "b138fc06-892b-4fe7-8a41-4f8b08132a6f"}
  },
  "users": {
    "test-01": {"uuid": "...", "short_uuid": "nz-uR1yqk4aJdWcs"}
  }
}
```

Объекты идентифицируются по **имени** в YAML (unique). UUID — на стороне Remnawave. state.json — мост.

---

## 9. Алгоритм diff и apply

```
1. Load YAML → desired state
2. Load state.json → expected UUIDs  
3. For each type (profiles, inbounds, squads, nodes, hosts, users):
   a. GET current state from API
   b. Match by name/tag → compute diff:
      - to_create: in YAML, not in API (or no UUID in state)
      - to_update: in both, fields differ
      - to_delete: in state.json, not in YAML (if --prune flag)
   c. Print plan
4. If apply: execute in correct order:
   profiles → squads ← inbounds-link → nodes → hosts → users → user-squad-link
5. Update state.json with new UUIDs
```

Порядок важен: nodes требуют profile_uuid; hosts требуют inbound_uuid; users требуют squad_uuid.

---

## 10. Идемпотентность

**Создание (POST):** если объект с таким `name` уже есть в state.json — пропустить (или PATCH, если поля изменились).

**Обновление (PATCH):** только если diff показал расхождение. Только изменённые поля передаём.

**Удаление (DELETE):** только при `--prune` flag. Защита от случайного сноса.

**Связи:** squad↔inbound — пересчитываем целиком при изменении (PATCH internal-squad с новым inbounds list).

---

## 11. Bootstrap

```bash
# 1. На VPS: создать API-token в Remnawave UI ("Настройки → API Tokens → Добавить")
# 2. Скопировать токен, положить в /root/cyber-berezka/infra/.env:
echo "REMNAWAVE_API_TOKEN=<token>" >> .env

# 3. Установить зависимости (или через uv):
pip install httpx pydantic pyyaml

# 4. Импортировать текущее состояние:
cd /root/cyber-berezka/infra/remnawave
python3 apply.py import

# 5. Закоммитить state.json + YAML в git
git add infra/remnawave/state.json infra/remnawave/configs/
git commit -m "infra: import remnawave state"
```

После этого — все изменения через `apply.py apply`.

---

## 12. Что **НЕ** делает apply.py (out of scope)

- **Не создаёт admin-аккаунт** — первоначальный setup через UI.
- **Не управляет Reality private key** — он в `.env`, регенерируется отдельной командой `apply.py generate-reality-key`.
- **Не управляет внешними системами** — IPv6 в Timeweb (нет API), DNS у регистратора, SSL у Caddy (Caddy сам).
- **Не управляет docker-стеком** — для compose есть отдельные команды.
- **Не делает миграции БД** — Remnawave сам через Prisma.

---

## 13. План реализации (Stages)

### Stage 2 — этой сессии: skeleton + status
- [x] Sub: client.py — HTTPX-обёртка с auth
- [x] Sub: config.py — load YAML configs
- [x] CLI: `apply.py status` — выводит current state Remnawave (read-only API calls)
- [ ] Bootstrap docs (как создать API token)

### Stage 3 — этой сессии (если успеем): import
- [ ] `apply.py import` — сохраняет current state в YAML + state.json

### Stage 4 — следующая сессия: plan + apply
- [ ] Pydantic models для всех типов
- [ ] plan.py — вычисление diff
- [ ] apply.py — выполнение
- [ ] `apply.py validate` — без API

### Stage 5 — Tests
- [ ] Unit: plan/diff корректность
- [ ] Integration: apply на dev-окружение

### Stage 6 — Cleanup
- [ ] Удалить ad-hoc скрипты (`_apply_routing_fix.sh`, `_swap_rules_ipv6_first.sh`, и т.п.)
- [ ] README с примерами
- [ ] Возможно: GitHub Actions для validate на PR

---

## 14. Verification criteria

`apply.py status` должен показать:
- 1 profile: Default-Profile
- 1 squad: Default-Squad (с 1 inbound)
- 1 node: cuber-berezka-nl-01 (connected=true)
- 1 host: NL Amsterdam
- 1 user: test-01

`apply.py import` должен создать YAML, который при `apply.py apply` не вызывает изменений (idempotent identity).

`apply.py plan` после добавления нового user в `users.yaml` должен показать "create test-02", и `apply.py apply` должен создать его без побочных эффектов.

---

## 15. Открытые вопросы для будущих stages

| # | Вопрос | Когда решать |
|---|---|---|
| 1 | Per-user routing для sticky-IPv6 — генерировать ли rules автоматически? | Stage 4-5 (task #37) |
| 2 | Migrate Reality private key из `.env` в SOPS? | Stage 6+ |
| 3 | GitOps: PR → CI runs `apply.py plan` → comment в PR | После Stage 5 |
| 4 | Multi-environment (dev / prod) — папки `configs/dev/`, `configs/prod/`? | Когда появится отдельный prod |
