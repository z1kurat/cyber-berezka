# VPN VLESS MVP — Design

**Дата:** 2026-05-17
**Статус:** черновик, на ревью у заказчика
**Кодовое имя проекта:** cyber-berezka

---

## 1. Назначение и границы

### 1.1. Цель MVP
Развернуть рабочую инфраструктуру для продажи VLESS-подписок: панель управления узлами, веб-кабинет с авторизацией, выдача персонального VLESS-ключа клиенту. Тестовая аудитория — семья и друзья (5–10 человек). Платежи в MVP **не реализуются**; вместо этого администратор вручную активирует подписку через UI/CLI.

### 1.2. Что в скоупе MVP
- Веб-сайт с регистрацией и входом по email + паролю.
- Личный кабинет: одна кнопка "получить мой VLESS-ключ" + просмотр выданных ключей и QR-кода.
- Интеграция с Remnawave Panel через её HTTP API.
- Один Xray-узел в Amsterdam (Timeweb AMS-1), управляемый Remnawave.
- IPv6-разделение: каждое клиентское подключение выходит через свой IPv6-адрес из выделенного провайдером блока — это снимает проблему "20 устройств с одного IPv4", о которой говорил заказчик.

### 1.3. Что НЕ в скоупе MVP (явные non-goals)
- Платёжная подсистема — отложена.
- Реферальная программа, промокоды, скидки.
- Мобильные приложения — клиенты подключаются стандартными приложениями (v2RayTun / Streisand / NekoBox / Hiddify).
- Multi-tenancy / суб-админы — Remnawave это умеет, но в MVP не настраивается.
- Биллинговая отчётность, отчёты для бухгалтерии.
- Антифрод, шеринг-детекция.

### 1.4. Архитектурный принцип
**«Одна VPS, но логически разнесено».** Все компоненты живут в одном `docker-compose.yml` на одном сервере, но: разные Postgres-инстансы, разные сети, обращение между компонентами через переменные `.env`, mTLS между панелью и узлом — чтобы перенос любого компонента на другую VPS не требовал изменений кода.

---

## 2. Зафиксированные технические решения

| Слой | Решение |
|---|---|
| Хостинг MVP | Timeweb Cloud, локация Amsterdam (AMS-1) |
| Панель | Remnawave (open-source) |
| Протокол VPN | VLESS + Reality + XTLS-Vision flow |
| VPN-движок | Xray-core (в составе Remnawave Node) |
| Web framework | FastAPI 0.115+ |
| ORM | SQLAlchemy 2.x (async, asyncpg-driver) |
| Migrations | Alembic 1.13+ |
| Validation | Pydantic v2 |
| Templates | Jinja2 (server-side rendering) |
| Sessions | Cookie-based, store в Redis |
| Password hashing | argon2id (argon2-cffi) |
| База приложения | PostgreSQL 16 (отдельный инстанс) |
| База Remnawave | PostgreSQL 16 (отдельный инстанс) |
| Reverse proxy / TLS | Caddy 2.8+ |
| Container runtime | Docker 25+ / Compose v2 |
| DNS для MVP | `nip.io` (TLS от Let's Encrypt через Caddy ACME) |
| Будущий DNS | реальный домен через зарубежного регистратора, под Cloudflare |

---

## 3. Топология контейнеров

### 3.1. Карта сервисов в `docker-compose.yml`

```
                  ┌─────────────────────────────────────────────────────┐
        :443 ───► │  Caddy (reverse proxy + ACME)                       │
        :80  ───► │                                                     │
                  └─────┬───────────────┬────────────────────┬──────────┘
                        │               │                    │
              SITE_DOMAIN         PANEL_DOMAIN          SUB_DOMAIN
                        │               │                    │
                  ┌─────▼─────┐   ┌─────▼─────┐         ┌────▼─────┐
                  │ app       │   │ remnawave │         │ remnawave│
                  │ FastAPI   │   │ Panel API │         │ (subscr. │
                  │ :8000     │   │ :3000     │         │  static) │
                  └─┬───┬─────┘   └─────┬─────┘         └──────────┘
                    │   │               │
              ┌─────▼┐ ┌▼──────┐  ┌─────▼─────┐
              │ db-  │ │redis  │  │ db-       │
              │ app  │ │       │  │ remnawave │
              │ :5432│ │ :6379 │  │ :5432     │
              └──────┘ └───────┘  └───────────┘

                           ┌──────────────────┐
                           │ remnawave-node   │  ◄── клиентский трафик
                           │ (Xray)           │      VLESS+Reality :443
                           │ control: :2222   │      управление от panel
                           └──────────────────┘      по mTLS
```

### 3.2. Docker-сети

Три изолированные bridge-сети плюс **узел Xray в `network_mode: host`** (см. оговорку ниже):

| Сеть | Сервисы | Зачем отдельная |
|---|---|---|
| `net-edge` | `caddy`, `app`, `remnawave` | Reverse proxy и публичные API |
| `net-app` | `app`, `db-app`, `redis` | Изоляция БД приложения и сессий |
| `net-panel` | `remnawave`, `db-remnawave` | Изоляция БД панели |

Контейнер `app` находится в `net-edge` и `net-app`. Контейнер `remnawave` — в `net-edge` и `net-panel`. Базы данных и redis наружу не торчат.

**Узел Xray (`remnawave-node`) запускается с `network_mode: host`** — не входит ни в одну Docker-сеть. Причина: для корректной работы IPv6-ротации (раздел 7) узлу нужен прямой доступ к сетевому стеку VPS со всеми назначенными IPv6-адресами. Docker IPv6 для контейнеров работает, но добавляет слой NAT/маршрутизации, который ломает per-connection `sendThrough` на конкретный IPv6.

Связь панель ↔ узел в MVP-конфигурации: панель из сети `net-edge` обращается к узлу по адресу `host.docker.internal:<NODE_MTLS_PORT>` (Docker для Linux 20.10+ поддерживает этот hostname при добавлении `extra_hosts: ["host.docker.internal:host-gateway"]` в compose-секции `remnawave`). Альтернатива — bind на `172.17.0.1` (адрес docker0 bridge). Порт `NODE_MTLS_PORT` слушается только на интерфейсе host, в firewall закрыт от внешних подключений.

Это даёт: компрометация Caddy → нет прямого доступа к БД. Компрометация Xray-узла → нет доступа к БД панели иначе, чем через её API, защищённый mTLS. Узел в host network mode = увеличенный blast radius при его компрометации (доступ ко всем интерфейсам host), но это компромисс ради IPv6-функциональности. При переходе на T3 (узел на отдельной VPS) этот компромисс исчезает естественным образом — компрометация узла больше не достаёт до панели физически.

### 3.3. Открытые порты на VPS (firewall — ufw / iptables)

| Порт | Протокол | Назначение | Источник |
|---|---|---|---|
| 22 | TCP | SSH | только админский IP (whitelist) |
| 80 | TCP | Caddy HTTP→HTTPS redirect, ACME challenges | 0.0.0.0/0 |
| 443 | TCP | Caddy HTTPS (сайт + панель + subscription) | 0.0.0.0/0 |
| 443 | TCP | Xray VLESS+Reality (входящий VPN-трафик) | 0.0.0.0/0 |

**Важно:** порт 443 одновременно слушают Caddy и Xray-node на **разных IP-адресах**. У VPS должны быть **два IPv4** или один IPv4 и Xray на нестандартном порту. Альтернативно — Xray работает на :443, а Caddy на :8443 (UX хуже, клиенту нужен порт в URL). Рекомендация: запросить у Timeweb **второй IPv4**, либо принять схему "Xray на :443, web на стандартных портах через отдельный IP".

В MVP допустимо: Caddy слушает `:443` на IPv6 публичный, Xray на `:443` на IPv4 — но это запутывает. Рекомендация: **доплатить за второй IPv4** (Timeweb ~50₽/мес).

Все остальные порты закрыты iptables. Управление узлом (порт 2222 для mTLS Remnawave) — только в Docker-сети `net-panel`, наружу не торчит, потому что узел и панель в MVP на одной машине.

---

## 4. Схема базы данных приложения

База `db-app`, миграции через Alembic.

### 4.1. Таблица `users`

```sql
CREATE TABLE users (
    id                       BIGSERIAL PRIMARY KEY,
    email                    VARCHAR(255) NOT NULL UNIQUE,
    email_normalized         VARCHAR(255) NOT NULL UNIQUE,  -- lowercase, для регистронезависимого поиска
    password_hash            VARCHAR(255) NOT NULL,          -- argon2id, соль внутри
    email_verified_at        TIMESTAMPTZ,
    email_verify_token       VARCHAR(64),                    -- одноразовый токен, NULL после верификации
    password_reset_token     VARCHAR(64),                    -- одноразовый токен сброса пароля
    password_reset_expires   TIMESTAMPTZ,                    -- TTL для reset-токена (1 час)
    is_active                BOOLEAN NOT NULL DEFAULT true,
    is_admin                 BOOLEAN NOT NULL DEFAULT false,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at            TIMESTAMPTZ,
    last_login_ip            INET,
    failed_login_count       INT NOT NULL DEFAULT 0,
    locked_until             TIMESTAMPTZ
);
CREATE INDEX idx_users_email_normalized ON users(email_normalized);
CREATE INDEX idx_users_password_reset_token ON users(password_reset_token) WHERE password_reset_token IS NOT NULL;
```

Заметки:
- `email_normalized` — для регистронезависимого UNIQUE: в `email` храним как ввёл пользователь, в `email_normalized` — `LOWER(TRIM(email))`.
- `failed_login_count` + `locked_until` — защита от brute force на уровне БД. После 5 неудачных попыток — блок на 15 минут.
- `email_verify_token` — для подтверждения email при регистрации. NULL после успешной верификации.
- `email_verified_at` — обязательное для активной учётки. Не верифицирован → не может выдать ключ.

### 4.2. Таблица `sessions`

```sql
CREATE TABLE sessions (
    id           VARCHAR(64) PRIMARY KEY,        -- случайный токен, 32 байта в hex
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    ip_address   INET,
    user_agent   TEXT,
    revoked_at   TIMESTAMPTZ
);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
```

Сессии хранятся **и в Postgres, и в Redis**. Redis — горячий кэш для каждого запроса (быстрая валидация cookie без SQL). Postgres — источник правды для аудита/отзыва. При логауте — `revoked_at` ставится в БД и ключ удаляется из Redis.

### 4.3. Таблица `vpn_keys`

```sql
CREATE TABLE vpn_keys (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    remnawave_user_uuid     UUID NOT NULL UNIQUE,        -- ID пользователя в Remnawave
    subscription_url        TEXT NOT NULL,                -- ссылка вида https://sub.../sub/<token>
    short_subscription_id   VARCHAR(64) NOT NULL UNIQUE,  -- последняя часть URL, для прямого доступа
    label                   VARCHAR(64),                  -- человекочитаемое имя ключа, напр. "Phone"
    status                  VARCHAR(16) NOT NULL DEFAULT 'active',  -- active | disabled | expired
    traffic_limit_bytes     BIGINT,                       -- NULL = безлимит
    expires_at              TIMESTAMPTZ,                  -- NULL = бессрочно
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at            TIMESTAMPTZ,
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_vpn_keys_user_id ON vpn_keys(user_id);
CREATE INDEX idx_vpn_keys_status ON vpn_keys(status);
```

Заметки:
- **Источник правды для подписки — Remnawave.** В этой таблице мы храним зеркало плюс owner-связь. Если расходится — Remnawave прав.
- `remnawave_user_uuid` — мы не пересоздаём пользователей при логине, мы один раз делаем `POST /api/users` в Remnawave при первой выдаче ключа и сохраняем UUID.
- `metadata` — JSONB для будущих расширений (используемый сертификат, протокол, нода) без миграций.
- В MVP `traffic_limit_bytes = NULL`, `expires_at = NULL`. Поля заложены под платный режим.

### 4.4. Таблица `audit_log`

```sql
CREATE TABLE audit_log (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT REFERENCES users(id) ON DELETE SET NULL,
    event_type   VARCHAR(64) NOT NULL,    -- 'user.register', 'user.login', 'key.create', 'key.revoke', 'login.failed'
    event_data   JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address   INET,
    user_agent   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_event_type ON audit_log(event_type);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);
```

Логируем: регистрацию, верификацию email, вход (успех/провал), создание ключа, отзыв ключа, смену пароля, выход. Это даст разбор инцидентов при необходимости.

### 4.5. Таблица `email_verification_attempts` и `rate_limit_buckets`

Опционально — для отслеживания попыток подтверждения email и rate limit. В MVP можно отложить, держать счётчики в Redis с TTL.

---

## 5. HTTP API приложения (FastAPI)

Все маршруты возвращают JSON, кроме помеченных `[HTML]` (Jinja2 rendering).

### 5.1. Публичные маршруты (без авторизации)

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/` | [HTML] Лендинг |
| `GET` | `/auth/register` | [HTML] Форма регистрации |
| `POST` | `/auth/register` | Создаёт user (email + password), отправляет письмо с токеном |
| `GET` | `/auth/verify/{token}` | [HTML] Подтверждает email, редирект на /auth/login |
| `GET` | `/auth/login` | [HTML] Форма входа |
| `POST` | `/auth/login` | Создаёт session, ставит cookie, редирект на /cabinet |
| `POST` | `/auth/logout` | Отзывает session, удаляет cookie |
| `GET` | `/auth/password-reset` | [HTML] Форма "забыли пароль" |
| `POST` | `/auth/password-reset` | Отправляет письмо с reset-токеном |
| `GET` | `/auth/password-reset/{token}` | [HTML] Форма нового пароля |
| `POST` | `/auth/password-reset/{token}` | Меняет пароль, отзывает все сессии user |
| `GET` | `/healthz` | Liveness, отвечает 200 OK |
| `GET` | `/readyz` | Readiness: проверяет БД и доступность Remnawave API |

### 5.2. Кабинет (требует session cookie)

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/cabinet` | [HTML] Кабинет: список ключей + кнопка "Создать ключ" |
| `POST` | `/cabinet/keys` | Создаёт нового пользователя в Remnawave (если ещё нет), запрашивает subscription URL, сохраняет в `vpn_keys`, редирект |
| `GET` | `/cabinet/keys/{id}` | [HTML] Детали ключа: VLESS URL, QR-код, инструкции |
| `POST` | `/cabinet/keys/{id}/disable` | Отключает ключ в Remnawave, меняет status='disabled' |
| `POST` | `/cabinet/keys/{id}/delete` | Удаляет ключ из Remnawave и из БД |
| `GET` | `/cabinet/profile` | [HTML] Профиль: email, смена пароля |
| `POST` | `/cabinet/profile/password` | Меняет пароль (требует ввода старого) |

### 5.3. Админский интерфейс (требует session + is_admin=true)

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/admin/users` | [HTML] Список всех пользователей |
| `POST` | `/admin/users/{id}/activate` | Активирует подписку вручную (вместо платежа в MVP) |
| `POST` | `/admin/users/{id}/deactivate` | Деактивирует все ключи пользователя |

В MVP админ создаётся seed-миграцией: `is_admin=true` для одного email из `ADMIN_EMAIL` env-переменной.

### 5.4. Контракт регистрации (пример)

```
POST /auth/register
Content-Type: application/x-www-form-urlencoded
Body: email=user@example.com&password=<min12chars>&password_confirm=<same>

→ 200 OK [HTML] "Письмо отправлено, проверьте почту"
→ 422 Validation error (email невалиден, password короче 12, не совпадают)
→ 409 Email уже зарегистрирован
→ 429 Too Many Requests (более 5 регистраций с одного IP за час)
```

Правила пароля: минимум 12 символов, не из топ-1000 утёкших (через `pwnedpasswords` локальный список Top-100k можно подгрузить файлом и проверять). Для MVP — достаточно длины и одного спецсимвола.

### 5.5. Контракт создания ключа (детально)

```
POST /cabinet/keys
Cookie: session=<token>
Body: label=Phone  (опционально)

Backend pipeline:
1. Авторизация: проверка session в Redis → user_id
2. Проверка email_verified_at NOT NULL → иначе 403
3. Проверка лимита ключей на пользователя (в MVP: 3 ключа max)
4. Транзакция:
   a. Если у user нет remnawave_user_uuid ни в одном ключе — POST /api/users в Remnawave с tg_id=null, username=user_<id>_<rand>, traffic_limit=0 (безлимит), expire=null
   b. Иначе reuse существующий UUID
   c. GET /api/users/<uuid> → получаем subscription URL и shortId
   d. INSERT INTO vpn_keys (...)
   e. INSERT INTO audit_log (event='key.create', ...)
5. Редирект на /cabinet/keys/<id>

→ 201 (редирект)
→ 403 email не подтверждён
→ 409 достигнут лимит ключей
→ 502 Remnawave API недоступен
```

---

## 6. Интеграция с Remnawave API

### 6.1. Подход

Создаём асинхронный клиент `RemnawaveClient` в `app/services/remnawave_client.py` на базе `httpx.AsyncClient`. Все обращения — через него, не в роутерах напрямую.

### 6.2. Конфигурация клиента

```python
class RemnawaveSettings(BaseSettings):
    api_url: str           # http://remnawave:3000  (в Docker-сети) → https://panel.example.com (после переезда)
    api_token: SecretStr   # Bearer token для авторизации в API
    timeout: float = 10.0
    retries: int = 3
```

Токен генерируется в UI панели после первого входа админа, кладётся в `.env` как `REMNAWAVE_API_TOKEN`.

### 6.3. Используемые эндпоинты Remnawave

**ВАЖНО:** точные пути эндпоинтов и схемы payload требуют верификации после деплоя панели и чтения её OpenAPI-спеки на `<panel>/api/docs` или эквиваленте. Ниже — ожидаемый контракт, который мы валидируем перед написанием кода.

| Операция | Метод | Путь (ожидаемый) |
|---|---|---|
| Создать пользователя | `POST` | `/api/users` |
| Получить пользователя | `GET` | `/api/users/{uuid}` |
| Обновить пользователя | `PATCH` | `/api/users/{uuid}` |
| Отключить пользователя | `POST` | `/api/users/{uuid}/disable` |
| Включить пользователя | `POST` | `/api/users/{uuid}/enable` |
| Удалить пользователя | `DELETE` | `/api/users/{uuid}` |
| Получить подписку | `GET` | `/api/users/{uuid}/subscription` |
| Список нод | `GET` | `/api/nodes` |
| Статистика по пользователю | `GET` | `/api/users/{uuid}/stats` |

### 6.4. Обработка ошибок

- 4xx от Remnawave → пробрасываем как HTTPException в наш роутер с сообщением.
- 5xx или таймаут → 3 ретрая с экспоненциальной задержкой (1s, 2s, 4s), затем 502 пользователю.
- Circuit breaker: при 5 подряд неудачах за 1 минуту — открываем circuit на 30 секунд, в этот период `POST /cabinet/keys` отвечает "сервис временно недоступен".

### 6.5. Идемпотентность

Создание пользователя в Remnawave — операция, которую нельзя дублировать. Защита: **до** вызова `POST /api/users` мы проверяем, есть ли уже `remnawave_user_uuid` в `vpn_keys` для этого `user_id`. Если есть — берём существующий. Это закрывает гонку "пользователь дважды нажал кнопку".

---

## 7. IPv6 — критический раздел

**Контекст от заказчика:** "при 20 устройствах на одном IP начинаются проверки безопасности на популярных сайтах". Это типичная для VPN-merchants проблема CGNAT-репутации IPv4. Решение — выделить **каждому клиентскому соединению свой исходящий IPv6**.

### 7.1. Что даёт Timeweb по IPv6

Timeweb Cloud при VPS обычно выделяет один публичный IPv4 + **подсеть IPv6 /64** (стандарт RIPE). /64 = 2^64 адресов. Этого хватает на сколько угодно клиентов. **Перед заказом VPS подтвердить у Timeweb выдачу /64.** Если выдают только /128 — нужно запрашивать /64 отдельно (обычно бесплатно).

### 7.2. Архитектурное решение

**Inbound (вход клиента) — IPv4 + IPv6 dual stack.** Клиент подключается на `<public-ip>:443` или `<public-ipv6>:443` — какой ему доступен.

**Outbound (выход в интернет с узла) — IPv6 c ротацией адреса**. Каждое исходящее соединение Xray использует свой IPv6 из выделенного /64-блока, выбирая адрес псевдослучайно (или по hash от destination). Это снимает проблему "один IP на 20 устройств" — потому что у вас IP столько, сколько в /64, то есть бесконечно.

### 7.3. Реализация в Xray

В конфиге Xray на узле:

```jsonc
{
  "outbounds": [
    {
      "tag": "ipv6-direct",
      "protocol": "freedom",
      "settings": {
        "domainStrategy": "UseIPv6"
      },
      "sendThrough": "::"  // см. ниже
    },
    {
      "tag": "ipv4-fallback",
      "protocol": "freedom",
      "settings": { "domainStrategy": "UseIPv4" }
    }
  ],
  "routing": {
    "rules": [
      // Сайты, которые требуют IPv4 (некоторые российские сайты не имеют AAAA-записей):
      { "type": "field", "domain": ["geosite:cn"], "outboundTag": "ipv4-fallback" },
      // Всё остальное — через IPv6:
      { "type": "field", "outboundTag": "ipv6-direct", "network": "tcp,udp" }
    ]
  }
}
```

### 7.4. Per-connection IPv6 ротация

Один `sendThrough: "::"` отправит весь трафик через **один** IPv6 (тот, что назначен на интерфейсе). Чтобы получить ротацию по адресам, нужен один из подходов:

**Вариант 1 (рекомендуется): множественные outbound + balancer.** Назначаем на сетевом интерфейсе несколько IPv6 из /64, и в Xray делаем outbound на каждый, объединяем балансером:

```bash
# На уровне ОС узла (sysctl + ip addr):
sysctl -w net.ipv6.ip_nonlocal_bind=1
ip -6 addr add 2a03:6f00:1::1/64 dev eth0
ip -6 addr add 2a03:6f00:1::2/64 dev eth0
# ... сколько надо
```

```jsonc
{
  "outbounds": [
    {"tag": "v6-1", "protocol": "freedom", "sendThrough": "2a03:6f00:1::1"},
    {"tag": "v6-2", "protocol": "freedom", "sendThrough": "2a03:6f00:1::2"}
    // ...
  ],
  "routing": {
    "balancers": [
      { "tag": "balancer-v6", "selector": ["v6-"] }
    ],
    "rules": [
      { "type": "field", "balancerTag": "balancer-v6", "network": "tcp,udp" }
    ]
  }
}
```

В MVP — назначаем **8 IPv6** на интерфейс, балансер распределяет round-robin / random. Этого достаточно, чтобы каждое 8-е подключение шло из нового адреса.

**Вариант 2 (продвинутый): полная случайная генерация на лету.** Через `freebind` (Linux IP_FREEBIND socket option) Xray может биндиться на любой адрес из /64, не назначая его явно на интерфейсе. Требуется патч Xray или специальный outbound. **В MVP не делаем, отмечаю как направление для расширения.**

### 7.5. Маршрутизация IPv6 на VPS

В Timeweb IPv6-блок должен быть маршрутизирован на VPS. Шаги:
1. Запросить у Timeweb выдачу /64 (если не выдан автоматически).
2. Получить gateway IPv6 и блок (пример: `2a03:6f00:1::/64`, gateway `2a03:6f00:1::1`).
3. На VPS добавить адреса (через `netplan` / `/etc/network/interfaces` / `systemd-networkd` — зависит от ОС).
4. Проверить: `curl -6 https://api64.ipify.org` с разных bind-адресов:
   ```bash
   curl --interface 2a03:6f00:1::1 -6 https://api64.ipify.org
   curl --interface 2a03:6f00:1::2 -6 https://api64.ipify.org
   ```
   Должны вернуть разные адреса.
5. В Docker-контейнере с Xray-узлом включить IPv6: `network_mode: host` или настроить IPv6 в docker daemon (`/etc/docker/daemon.json`):
   ```json
   { "ipv6": true, "fixed-cidr-v6": "fd00::/80" }
   ```
   Учитывая сложность Docker IPv6, для узла Xray проще использовать **`network_mode: host`** — узел берёт сетевой стек VPS как есть, со всеми IPv6.

### 7.6. Что это решает и не решает

**Решает:**
- "20 устройств за одним IP" проблема: каждое подключение выходит с разного IPv6, fingerprint не накапливается на одном адресе.
- Падение репутации одного IP не валит всех пользователей.

**Не решает:**
- Сайты, не работающие через IPv6 (часть рунета): для них fallback на IPv4 — а это снова "один IP на всех". Минимизируется тем, что таких сайтов ~10–20% и нагрузка на IPv4 падает в 5–10 раз.
- Капчи Cloudflare: они могут сработать вне зависимости от IP, по browser fingerprint. С этим IPv6 не борется.

### 7.7. Альтернативное направление (на будущее)

Покупка пула IPv4 у провайдера (Hetzner, BuyVM, Vultr) — дорого ($1–2/мес за IP), но единственный способ полностью убрать IPv4-репутационные проблемы для тех 10–20% сайтов без IPv6. В MVP — не делаем.

---

## 8. Протокол: VLESS + Reality + XTLS-Vision

### 8.1. Почему именно это сочетание

- **VLESS** — современный протокол Project X, поддерживается всеми основными клиентами (v2RayTun, Streisand, NekoBox, Hiddify, FairVPN).
- **Reality** — антицензурный режим: трафик неотличим от обычного HTTPS к "целевому" сайту-маске (например, www.microsoft.com). DPI Роскомнадзора не видит, что это VPN. Замена устаревшим TLS 1.3 + WS + fake-certificate схемам.
- **XTLS-Vision flow** — оптимизация скорости: внутренний трафик не шифруется дважды, выигрыш ~30–40% throughput.

### 8.2. Что НЕ берём и почему

- **Trojan, Shadowsocks, V2Ray-ws-tls** — детектируются DPI РКН в 2025–2026.
- **VLESS + WS + TLS** (старая схема) — детектируется по handshake fingerprint, неактуальна.
- **WireGuard** — детектируется DPI, обходится только через AmneziaWG (форк). В Remnawave как опция возможна, но не основная.

### 8.3. Выбор сайта-маски (destination для Reality)

Reality "представляется" трафиком на чужой сайт. Требования к сайту-маске:
- TLS 1.3 с X25519
- HTTP/2
- Не российский (РКН не должен иметь к нему доступ для глубокого анализа)
- Популярный (чтобы массовый трафик к нему не вызывал подозрений)

Стандартные кандидаты: `www.microsoft.com`, `dl.google.com`, `www.cloudflare.com`, `aws.amazon.com`.

**Конкретный выбор для MVP:** `www.microsoft.com` — стабильный, всегда доступен, без подозрений.

Конфигурируется в Remnawave при создании inbound. В UI: создать inbound → Reality → ввести `dest: www.microsoft.com:443`, `serverNames: ["www.microsoft.com"]`, сгенерировать `privateKey` и `shortIds`.

---

## 9. Reverse proxy (Caddy)

### 9.1. Caddyfile (шаблон с env)

```caddy
{
    email {$ACME_EMAIL}
}

{$SITE_DOMAIN} {
    reverse_proxy app:8000
    encode gzip zstd
    header {
        Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
        Content-Security-Policy "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'"
        -Server
    }
}

{$PANEL_DOMAIN} {
    @allowed_admin {
        remote_ip {$ADMIN_IP_WHITELIST}
    }
    handle @allowed_admin {
        reverse_proxy remnawave:3000
    }
    respond 403
}

{$SUB_DOMAIN} {
    reverse_proxy remnawave:3000  # subscription URLs panel сам обрабатывает
    header {
        X-Content-Type-Options "nosniff"
    }
}
```

### 9.2. Особенности

- `{$VAR}` — Caddy подставляет переменные окружения при старте.
- ACME — Caddy сам получает Let's Encrypt сертификаты для всех трёх доменов. Для `nip.io` сертификат выпускается через HTTP-01 challenge — Caddy должен быть доступен на :80.
- Панель `{$PANEL_DOMAIN}` доступна **только** с IP из `ADMIN_IP_WHITELIST` (например, "1.2.3.4 5.6.7.0/24"). Со всех остальных IP — 403 без раскрытия наличия панели.
- HSTS, CSP, anti-clickjacking — настроены сразу.

### 9.3. Что в `nip.io` для MVP

Если IP VPS = `5.6.7.8`, тогда:
- `SITE_DOMAIN = vpn.5-6-7-8.nip.io`
- `PANEL_DOMAIN = admin.5-6-7-8.nip.io`
- `SUB_DOMAIN = sub.5-6-7-8.nip.io`

При покупке реального домена `example.com` — меняются три значения в `.env`, перезапускаем Caddy. Сертификаты Caddy перевыпустит автоматически.

---

## 10. Переменные окружения (`.env.example`)

Все секреты — в `.env`, файл в `.gitignore`. Коммитим только `.env.example` с плейсхолдерами.

```bash
# ─── ДОМЕНЫ ─────────────────────────────────────────────────────
SITE_DOMAIN=vpn.5-6-7-8.nip.io          # публичный домен сайта
PANEL_DOMAIN=admin.5-6-7-8.nip.io       # домен Remnawave-панели
SUB_DOMAIN=sub.5-6-7-8.nip.io           # домен subscription URLs
ACME_EMAIL=you@example.com              # email для Let's Encrypt уведомлений
ADMIN_IP_WHITELIST=1.2.3.4              # IP для доступа в админку (можно несколько через пробел)

# ─── ПРИЛОЖЕНИЕ ─────────────────────────────────────────────────
APP_SECRET_KEY=<openssl rand -hex 32>   # для подписи cookie/CSRF
APP_DEBUG=false
APP_BASE_URL=https://${SITE_DOMAIN}     # для построения ссылок в письмах
ADMIN_EMAIL=admin@example.com           # этот user при старте получит is_admin=true
SESSION_LIFETIME_HOURS=720              # 30 дней
PASSWORD_MIN_LENGTH=12

# ─── БД ПРИЛОЖЕНИЯ ──────────────────────────────────────────────
APP_DB_HOST=db-app
APP_DB_PORT=5432
APP_DB_NAME=cyber_berezka
APP_DB_USER=app
APP_DB_PASSWORD=<openssl rand -hex 24>
APP_DB_URL=postgresql+asyncpg://${APP_DB_USER}:${APP_DB_PASSWORD}@${APP_DB_HOST}:${APP_DB_PORT}/${APP_DB_NAME}

# ─── REDIS ──────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
REDIS_SESSION_PREFIX=sess:

# ─── SMTP ───────────────────────────────────────────────────────
SMTP_HOST=smtp.eu.mailgun.org           # или Brevo, Postmark
SMTP_PORT=587
SMTP_USER=postmaster@mg.example.com
SMTP_PASSWORD=<token>
SMTP_FROM=noreply@example.com
SMTP_TLS=true

# ─── REMNAWAVE ──────────────────────────────────────────────────
REMNAWAVE_API_URL=http://remnawave:3000  # через Docker network; при переезде на отдельную VPS — https://panel.example.com
REMNAWAVE_API_TOKEN=<generate-in-panel-ui>
REMNAWAVE_DB_HOST=db-remnawave
REMNAWAVE_DB_PORT=5432
REMNAWAVE_DB_NAME=remnawave
REMNAWAVE_DB_USER=remnawave
REMNAWAVE_DB_PASSWORD=<openssl rand -hex 24>
REMNAWAVE_JWT_SECRET=<openssl rand -hex 32>

# ─── NODE (Xray) ────────────────────────────────────────────────
NODE_PUBLIC_IPV4=5.6.7.8
NODE_IPV6_BLOCK=2a03:6f00:1::/64
NODE_IPV6_POOL_SIZE=8                    # сколько адресов биндить на интерфейс
NODE_REALITY_DEST=www.microsoft.com:443
NODE_REALITY_SERVER_NAMES=www.microsoft.com
```

### 10.1. Подмена доменов

При переходе с `nip.io` на реальный домен:
1. Купить домен у Namecheap/Porkbun.
2. Создать A/AAAA-записи: `vpn`, `admin`, `sub` → IP VPS.
3. Поменять три значения в `.env`.
4. `docker compose restart caddy`.
5. Caddy автоматически выпустит новые TLS-сертификаты.
6. В Remnawave UI обновить subscription domain (если хранится в БД панели — миграция).

Код приложения и схема БД не меняются.

---

## 11. Чек-лист безопасности

### 11.1. Уровень VPS
- [ ] **SSH:** запрет root-логина (`PermitRootLogin no`), вход только по ключу (`PasswordAuthentication no`).
- [ ] **SSH-порт:** менять с 22 опционально (security through obscurity, реально не помогает, но снижает шум в логах).
- [ ] **UFW / iptables:** разрешены только 22 (whitelist IP), 80, 443.
- [ ] **fail2ban:** включён на sshd, на nginx/caddy access log (защита от brute force на /auth/login).
- [ ] **Автоматические обновления безопасности:** `unattended-upgrades` для security-патчей.
- [ ] **Отключена IPv6 RA-автоконфигурация** там, где не нужна — статические адреса предсказуемее.
- [ ] **sysctl:** `net.ipv4.tcp_syncookies=1`, `net.ipv6.conf.all.forwarding=1` (нужен для VPN-маршрутизации).

### 11.2. Уровень Docker
- [ ] **Не запускаем контейнеры от root** там, где не требуется. Caddy и app — от непривилегированного user.
- [ ] **`no-new-privileges: true`** в compose для всех сервисов.
- [ ] **Read-only root FS** для контейнеров без записи (caddy, app — после билда).
- [ ] **Хранение секретов:** только в `.env`, не в `docker-compose.yml`, не в коде.
- [ ] **Docker socket** не пробрасывается в контейнеры.
- [ ] **Логи Docker:** json-file driver с `max-size: 10m, max-file: 3`, чтобы не залить диск.

### 11.3. Уровень приложения
- [ ] **Cookies:** `HttpOnly`, `Secure`, `SameSite=Lax`, имя сессии не выдаёт стек (`__Host-session` префикс).
- [ ] **CSRF:** double-submit cookie pattern для всех `POST`-форм.
- [ ] **Rate limiting:** `/auth/login` — 5 попыток за 15 минут на IP; `/auth/register` — 5 в час на IP; `/cabinet/keys POST` — 10 в час на user.
- [ ] **Password policy:** минимум 12 символов, проверка по списку утёкших.
- [ ] **Argon2id:** memory_cost=65536 (64 MiB), time_cost=3, parallelism=4 — соответствует OWASP-рекомендации 2024.
- [ ] **Email verification обязателен** для выдачи ключа.
- [ ] **SQL injection:** только через SQLAlchemy parametrized queries, никакого raw SQL с конкатенацией.
- [ ] **XSS:** Jinja2 авто-эскейпинг включён (default); CSP заголовок.
- [ ] **Logging:** не пишем пароли, токены, session-IDs, secrets в логи. Хеши паролей — только в БД, ни в логах, ни в metric labels.
- [ ] **Зависимости:** `pip-audit` / `safety` в CI, обновление security-патчей.

### 11.4. Уровень Remnawave
- [ ] **API-токен** длинный (64+ символа), хранится только в `.env` приложения.
- [ ] **Web UI панели за IP-allowlist** через Caddy. Утечка пароля админа без доступа с whitelist-IP бесполезна.
- [ ] **Резервное копирование БД:** автоматический дамп `pg_dump db-remnawave` ежедневно в 03:00, хранение 7 дней на отдельном volume + копия в зашифрованный объектный storage (Backblaze B2 / Selectel S3) — настраивается на этапе production, в MVP опционально.

### 11.5. Уровень узла Xray
- [ ] **Reality privateKey** генерируется на узле, в БД не попадает.
- [ ] **shortIds:** минимум 8 штук, по 4–16 hex-символов каждый.
- [ ] **mTLS** между панелью и узлом — даже на localhost.
- [ ] **Логи Xray:** уровень `warning`, не `info` — не раскрываем, кто куда подключается. Это и для приватности клиентов, и для compliance.

### 11.6. Operational security
- [ ] **Backup-стратегия:** ежедневный `pg_dump` обеих БД, weekly snapshot VPS через Timeweb.
- [ ] **Monitoring (опционально для MVP):** UptimeRobot ping на `/healthz` сайта и публичный endpoint узла.
- [ ] **Доступ к VPS:** SSH-ключ один, парольный fallback выключен. При компрометации ключа — `authorized_keys` чистится.
- [ ] **Секреты в .env:** перенос `.env` на VPS через `scp`, не через git, не через буфер обмена в IDE.

---

## 12. Структура репозитория

```
cyber-berezka/
├── app/                              # FastAPI приложение
│   ├── __init__.py
│   ├── main.py                       # FastAPI entry, mount routers
│   ├── config.py                     # Pydantic Settings из env
│   ├── deps.py                       # Dependency injection (db, current_user)
│   ├── models/                       # SQLAlchemy ORM
│   │   ├── user.py
│   │   ├── session.py
│   │   ├── vpn_key.py
│   │   └── audit.py
│   ├── schemas/                      # Pydantic схемы запрос/ответ
│   ├── services/
│   │   ├── auth.py                   # регистрация, вход, пароли
│   │   ├── email.py                  # отправка писем (verify, reset)
│   │   ├── remnawave_client.py       # клиент Remnawave API
│   │   ├── vpn_keys.py               # бизнес-логика выдачи ключей
│   │   └── audit.py                  # логирование событий
│   ├── routers/
│   │   ├── auth.py
│   │   ├── cabinet.py
│   │   ├── admin.py
│   │   └── health.py
│   ├── templates/                    # Jinja2
│   │   ├── base.html
│   │   ├── auth/
│   │   └── cabinet/
│   ├── static/                       # CSS, JS, изображения
│   ├── security/
│   │   ├── passwords.py              # argon2id wrapper
│   │   ├── csrf.py
│   │   └── ratelimit.py
│   └── tests/
├── migrations/                       # Alembic
│   ├── env.py
│   └── versions/
├── infra/
│   ├── docker/
│   │   ├── Dockerfile.app
│   │   └── entrypoint.sh
│   ├── caddy/
│   │   └── Caddyfile
│   ├── remnawave/
│   │   └── config-templates/         # config Reality, IPv6 routing
│   └── scripts/
│       ├── setup-vps.sh              # первичная настройка VPS (ufw, ipv6, docker)
│       ├── add-node.sh               # развёртывание новой ноды позже
│       └── backup.sh
├── docs/
│   └── superpowers/specs/
│       └── 2026-05-17-vpn-vless-mvp-design.md   # этот документ
├── docker-compose.yml
├── .env.example
├── .env                              # gitignored
├── .gitignore
├── pyproject.toml                    # poetry / uv
├── alembic.ini
├── README.md
└── LICENSE
```

---

## 13. План миграции T1 → T3 (когда понадобится)

### Триггер для миграции
- > 50 активных подписок, или
- первый платный клиент, или
- abuse-репорт на VPS от Timeweb, или
- решение перенести производство.

### Этапы

**Шаг 1: вынос узлов на отдельные VPS.**
- Развернуть новую VPS (Hetzner / Aeza) с Docker.
- Скопировать `infra/scripts/add-node.sh`, запустить — поднимется только `remnawave-node` контейнер с уникальным client cert.
- В Remnawave UI: добавить узел, ввести IP, сертификат, нода зарегистрируется.
- Распределить пользователей по узлам (Remnawave умеет inbound-mapping per-user).
- Постепенно отказаться от локального узла на основной VPS.

**Шаг 2: перенос панели на отдельную VPS.**
- На офшорной VPS поднять `remnawave` + `db-remnawave` через тот же compose.
- Сделать `pg_dump`/`pg_restore` БД.
- Перевыпустить mTLS-сертификаты между панелью и каждым узлом (через CLI Remnawave).
- В `.env` приложения изменить `REMNAWAVE_API_URL=https://panel.real.com`.
- Старый контейнер панели остановить.

**Шаг 3: купить домен, отказаться от nip.io.**
- Регистрация у Namecheap/Porkbun, WHOIS Privacy.
- DNS-записи: A/AAAA `vpn`, `admin`, `sub`.
- Cloudflare поставить **только** перед `vpn`-доменом (не перед панелью и не перед subscription).
- Поменять 3 переменные в `.env`, перезапустить Caddy.

**Шаг 4: переход на платежи.**
- Это отдельная фаза, отдельный спек. Контур: интеграция платёжного провайдера, биллинговая логика, обработка вебхуков, продление подписок, напоминания. ~2–3 недели работы.

---

## 14. Что подлежит верификации после написания плана реализации

Эти пункты содержат ожидания, которые я записал, но которые требуют практической проверки. Они должны быть отдельными задачами в имплементационном плане:

1. **Точная схема API Remnawave** — пути эндпоинтов, формат payload, схема ошибок. Источник: OpenAPI-спека панели после первого деплоя.
2. **Лицензия Remnawave** — что разрешено модифицировать и распространять.
3. **Состояние HA-режима Remnawave** — есть ли встроенная репликация панели.
4. **Совместимость VLESS+Reality+Vision flow с актуальными клиентами** — проверить v2RayTun, Hiddify, Streisand, NekoBox на реальных устройствах.
5. **Выдача /64 IPv6 от Timeweb AMS-1** — подтвердить в support-чате до заказа VPS.
6. **Доступность Let's Encrypt для `*.nip.io`** — нет ли rate-limit на конкретный IP-префикс.
7. **Поведение `microsoft.com` как Reality destination** — стабильность TLS-параметров, как часто меняется fingerprint.

---

## 15. Verification criteria (как поймём, что MVP готов)

Не "запустилось — значит готово". Конкретные критерии:

- [ ] Регистрация: новый user → письмо приходит → ссылка верифицирует → виден в БД с `email_verified_at != NULL`.
- [ ] Вход: правильный пароль → cookie выдан, /cabinet открывается. Неправильный пароль 5 раз → 15 минут блок.
- [ ] Создание ключа: кнопка нажата → в `vpn_keys` запись с `remnawave_user_uuid`, в Remnawave UI виден пользователь с тем же UUID, subscription URL открывается и отдаёт base64-encoded VLESS-конфиг.
- [ ] Импорт ключа в v2RayTun: подключение устанавливается, IP меняется на нидерландский, через `curl -6 ifconfig.me` адрес из выделенного /64-блока.
- [ ] Reality маскировка: с MITM-прокси (например, mitmproxy на промежуточном тестовом VPS) трафик к узлу определяется как TLS handshake к `www.microsoft.com`, не как VPN.
- [ ] IPv6 ротация: два одновременных коннекта с разных устройств → разные исходящие IPv6.
- [ ] Caddy: HSTS, CSP, X-Frame-Options присутствуют (проверка `curl -I`).
- [ ] Панель: `https://admin.<...>` с не-whitelist IP → 403; с whitelist → панель открывается.
- [ ] Backup: `pg_dump` обеих БД успешно выполнен и хранится в volume.
- [ ] Логи: ни одного появления пароля / hash / токена в `docker compose logs`.

---

## 16. Открытые вопросы для финальной проверки

1. **Второй IPv4 у Timeweb** — нужен ли (см. 3.3)? Цена/мес?
2. **SMTP-провайдер** — Mailgun, Brevo, Postmark, или Yandex.SMTP? Влияет на deliverability.
3. **Количество IPv6 в пуле** в MVP — 8 достаточно или сразу 32?
4. **Ограничение количества ключей на пользователя** — 3 ключа в MVP. Подтверждаете?
5. **Лимит времени жизни сессии** — 30 дней. Подтверждаете или короче?
