# Cyber Berezka — миграция инфраструктуры на Beget (design spec)

**Дата:** 2026-05-23
**Статус:** design, утверждён пользователем по трём итерациям brainstorming
**Связанный snapshot:** `~/.claude/projects/-Users-nikitavorozbitov-pycharmProject-cyber-berezka/memory/project_session_2026-05-22_snapshot.md`
**Связанные docs:** `docs/operations/pitfalls-and-fixes.md`, `docs/superpowers/specs/2026-05-17-vpn-vless-mvp-design.md`, `docs/superpowers/specs/2026-05-17-apply-py-design.md`, `docs/superpowers/specs/2026-05-17-site-design.md`

---

## 1. Цели миграции

1. Перенести сайт (FastAPI + Caddy) и Remnawave panel со старого VPS (Timeweb `194.87.83.31`) на новый VPS (Beget `212.74.231.217`).
2. Старый сервер оставить только в роли удалённого Xray-узла (`remnanode`).
3. Подключить новый домен `cyber-berezka.ru`: `home.cyber-berezka.ru` → лендинг и кабинет, `admin.cyber-berezka.ru` → панель и subscription endpoints.
4. На переходный период (до создания A-записей в Beget DNS) работать через `nip.io`: `212-74-231-217.nip.io` и `admin.212-74-231-217.nip.io`.
5. Закрыть задачи `#27`, `#28`, `#34`, `#41` автоматически в рамках миграции.
6. Соблюсти требование IaC: все шаги — через идемпотентные скрипты в репозитории. Допустимы только две одноразовые ручные паузы (initial admin registration в Remnawave UI и paste API-token), которые архитектурно неустранимы.

## 2. Целевая архитектура

```
Beget VPS  212.74.231.217 (Ubuntu 24.04, 2 vCPU, 3.8 GiB RAM, 38 GB SSD, IPv4-only)
└── Роль: coordinator + local node + site
    ├── Caddy (:80, :443) — TLS-терминатор, IP-allowlist на /api/admin/*
    │   ├── {SITE_HOST}  → site:8000
    │   ├── {ADMIN_HOST} → remnawave:3000 (с allowlist на /admin)
    │   └── {APEX_REDIRECT_HOST} → 301 → https://{SITE_HOST} (только в production stage)
    ├── site (FastAPI + Jinja2 + Tailwind, см. site-design.md)
    ├── db-app (Postgres 17.6 для приложения)
    ├── site-redis (Redis 7-alpine, sessions + rate-limit)
    ├── remnawave backend (panel)
    ├── remnawave-db (Postgres 17.6 для panel)
    ├── remnawave-redis (valkey 9-alpine, unix socket для panel)
    └── remnanode-local (Xray 2.7.0, host network, :2053)

Timeweb VPS  194.87.83.31 (Ubuntu 22.04, IPv6-pool 2a03:6f02::8316/c8af/c8ba/c8c0)
└── Роль: remote node only
    └── remnanode-remote (Xray 2.7.0, host network, :2053, :2222)
        └── outbound: random-balancer по 4 IPv6
```

Связь panel ↔ local-node — через docker network на новом сервере. Связь panel ↔ remote-node — через интернет на `212.74.231.217:* → 194.87.83.31:2222`, TLS+token, allowlist по IP на стороне старого сервера.

## 3. Распределение профилей Xray

В Remnawave panel создаются **два** профиля (не один общий):

| Профиль | Применяется на узле | Outbound стратегия |
|---|---|---|
| `profile_ipv4_only` | `remnanode-local` (новый сервер) | direct через единственный `212.74.231.217` |
| `profile_ipv6_pool` | `remnanode-remote` (старый сервер) | random-balancer по 4 IPv6 из `2a03:6f02::*` |

Squad'ы привязывают пользователей к нодам. На MVP-этапе политика — random. Sticky-per-user — задача `#37`, остаётся в backlog.

`scripts/generate_xray_outbounds.py` расширяется флагом `--mode ipv4-only|ipv6-pool`, выходом служат два YAML-файла:

- `infra/remnawave/configs/profile_ipv4_only.yaml` (новый)
- `infra/remnawave/configs/profile_ipv6_pool.yaml` (переименован из `profile.yaml`)

## 4. DNS-стратегия

### Stage 1 — `nip.io` (немедленно после миграции)

| Имя | Тип | Значение |
|---|---|---|
| `212-74-231-217.nip.io` | A (built-in) | `212.74.231.217` |
| `admin.212-74-231-217.nip.io` | A (built-in) | `212.74.231.217` |

`nip.io` — автоматический wildcard-DNS, не требует настройки. Caddy получает Let's Encrypt staging-сертификаты (или production, если rate-limit позволяет — попробуем production сразу).

### Stage 2 — `cyber-berezka.ru` (после ручного создания A-записей в Beget UI)

| Имя | Тип | Значение |
|---|---|---|
| `home.cyber-berezka.ru` | A | `212.74.231.217` |
| `admin.cyber-berezka.ru` | A | `212.74.231.217` |
| `cyber-berezka.ru` (apex) | A | `212.74.231.217` (для 301-redirect на `home.`) |

Переключение между stage'ами — это редактирование `infra/.env` (три переменные) и `docker compose up -d caddy`. Никаких изменений в коде.

DNS-провайдер — Beget. API для автоматизации есть, но пока создание поддоменов делает пользователь в UI (по запросу из чата). Автоматизация через Beget DNS API — задача `#49`, post-migration.

## 5. Структура репозитория (изменения)

```
infra/
├── .env.example                  [NEW]
├── compose/
│   ├── docker-compose.coordinator.yml [MOVED+EXTENDED — для нового сервера, включает remnanode-local]
│   └── docker-compose.node.yml        [MOVED — для старого сервера, только remnanode]
├── caddy/
│   └── Caddyfile                 [MODIFIED — {$SITE_HOST}, {$ADMIN_HOST}, {$APEX_REDIRECT_HOST}]
├── site/                         [no changes]
├── remnawave/
│   ├── apply.py                  [EXTENDED — поддержка двух профилей]
│   ├── configs/
│   │   ├── profile_ipv4_only.yaml    [NEW]
│   │   ├── profile_ipv6_pool.yaml    [RENAMED из profile.yaml]
│   │   ├── nodes.yaml                [MODIFIED — две ноды]
│   │   ├── squads.yaml               [MODIFIED — раскидка по нодам]
│   │   ├── hosts.yaml                [MODIFIED]
│   │   └── users.yaml                [MODIFIED — test-01 пересоздаётся]
│   └── state.json                [REGENERATED после reimport]
├── systemd/
│   ├── cyber-berezka-ipv6.service       [no changes — для старого сервера]
│   └── cyber-berezka-iptables.service   [NEW — для обоих серверов]
└── docker-compose.yml            [DELETED — заменён двумя в compose/]
```

```
scripts/
├── provision_new_server.sh           [NEW]
├── teardown_old_server.sh            [NEW]
├── reconfigure_old_as_node.sh        [NEW]
├── sync_repo_to_server.sh            [NEW]
├── apply_full.sh                     [NEW — единая точка входа]
├── generate_xray_outbounds.py        [EXTENDED — флаг --mode]
└── (существующие IPv6-скрипты без изменений)
```

## 6. Pipeline миграции (`scripts/apply_full.sh`)

Запускается с локальной машины пользователя. Идемпотентен.

| Шаг | Действие | Тип |
|---|---|---|
| 1 | Sanity-check: SSH-доступ к `212.74.231.217` и `194.87.83.31`, наличие `infra/.env` на каждом сервере (или его создание из `.env.example` с шаблонными значениями). | авто |
| 2 | `sync_repo_to_server.sh 212.74.231.217` — rsync `infra/`, `scripts/`, `docs/`. | авто |
| 3 | `ssh root@212.74.231.217 'bash /root/cyber-berezka/scripts/provision_new_server.sh'` — bootstrap (Docker, swap, ufw, fail2ban, iptables, SSH-hardening, docker compose up). | авто |
| 4 | **Пауза:** пользователь регистрирует admin в Remnawave UI на `https://admin.212-74-231-217.nip.io`. | ручное |
| 5 | `ssh root@212.74.231.217 'python /root/cyber-berezka/infra/remnawave/bootstrap_token.py'` — пользователь вставляет API-token из UI, скрипт пишет в `.env` (mode 600). | полу-ручное (paste) |
| 6 | `python infra/remnawave/apply.py import` — реимпорт profile_ipv4_only, profile_ipv6_pool, squads, hosts, nodes, users (включая test-01). Генерация Remnawave node connection token. | авто |
| 7 | `POST /api/system/tools/x25519/generate` → новые Reality keys, пишутся в `.env` обоих серверов через `apply.py rotate-reality-key`. Закрывает `#28`. | авто |
| 8 | `sync_repo_to_server.sh 194.87.83.31` — rsync на старый сервер. | авто |
| 9 | `ssh root@194.87.83.31 'bash /root/cyber-berezka/scripts/teardown_old_server.sh'` — останавливает и удаляет 7 контейнеров (caddy, site, db-app, site-redis, remnawave, remnawave-db, remnawave-redis), `docker image prune -af`. | авто |
| 10 | `ssh root@194.87.83.31 'bash /root/cyber-berezka/scripts/reconfigure_old_as_node.sh'` — восстановление IPv6-пула, persistent iptables, systemd-units, `docker compose -f compose/docker-compose.node.yml up -d`. | авто |
| 11 | Verification: `python apply.py status` показывает обе ноды `online`. | авто |

Шаги 4 и 5 — единственные неустранимые ручные точки. Все прочие — идемпотентны и переоткатываемы.

## 7. Конфигурация `infra/.env`

```env
# === Hosts (Stage 1 — nip.io) ===
SITE_HOST=212-74-231-217.nip.io
ADMIN_HOST=admin.212-74-231-217.nip.io
APEX_REDIRECT_HOST=

# === Hosts (Stage 2 — production, uncomment when DNS ready) ===
# SITE_HOST=home.cyber-berezka.ru
# ADMIN_HOST=admin.cyber-berezka.ru
# APEX_REDIRECT_HOST=cyber-berezka.ru

# === Secrets ===
REMNAWAVE_API_TOKEN=
REMNAWAVE_NODE_TOKEN=
REALITY_PRIVATE_KEY=
REALITY_PUBLIC_KEY=
DB_APP_PASSWORD=
REMNAWAVE_DB_PASSWORD=
REDIS_PASSWORD=
BREVO_API_KEY=

# === Server role ===
SERVER_ROLE=coordinator  # coordinator | node-only

# === Admin allowlist for /api/admin/* in Caddy ===
ADMIN_IP_ALLOWLIST=1.2.3.4/32,5.6.7.0/24  # IP пользователя
```

`provision_new_server.sh` генерирует случайные значения для `DB_APP_PASSWORD`, `REMNAWAVE_DB_PASSWORD`, `REDIS_PASSWORD` через `openssl rand -base64 32` при первом запуске, если они пусты.

## 8. Безопасность

### Новый сервер `212.74.231.217`

| Аспект | Конечное состояние |
|---|---|
| SSH | Только ключи (`PasswordAuthentication no`, `PermitRootLogin prohibit-password`). Пользовательские 2 ключа уже в `~/.ssh/authorized_keys`. |
| Firewall | ufw enable: allow 22/tcp, 80/tcp, 443/tcp, 2053/tcp; default deny |
| Fail2ban | active, jail для SSH с ban-time 3600s |
| Swap | 2 GB swap-file (`/swapfile`, mode 600) |
| iptables persistent | через `cyber-berezka-iptables.service` |
| Hostname | `berezka-coordinator` |
| Unattended-upgrades | active, security only |
| Docker | CE + compose plugin, `live-restore: true` в daemon.json |
| Caddy | IP-allowlist на `/api/admin/*` через `ADMIN_IP_ALLOWLIST` |

### Старый сервер `194.87.83.31`

| Аспект | Конечное состояние |
|---|---|
| **Root password** | **НЕ ротируется в этой миграции.** Остаётся `q,2--zM6eYZ-o1`, скомпрометированный дважды через чат. **Зафиксированный риск.** Mitigation: SSH-пароль не отключаем тоже (по решению пользователя — «пока не трогаем»), доступ остаётся доступным через TTY и rescue-консоль. Долгосрочно — задача `#41` (отдельно вне этой миграции). |
| SSH-config | Не изменяется (без рисковых правок) |
| Firewall | iptables persistent через `cyber-berezka-iptables.service`: INPUT :22, :2053 — ACCEPT; INPUT :2222 — ACCEPT только с `212.74.231.217/32`, иначе DROP |
| IPv6-пул | Persistent через `cyber-berezka-ipv6.service` (закрывает грабли §6.3 снапшота) |
| Hostname | `berezka-node-tw1` |
| Контейнеры наш стек | только `remnanode-remote` |
| Не наши сервисы | не трогаются (3X-UI, CRM_AI, MTProto, Squid, 3proxy, Zabbix) |

### Ротация скомпрометированных секретов

| Секрет | Когда ротируется | Закрытая задача |
|---|---|---|
| Remnawave API token | Шаг 5 `apply_full.sh` | `#41` (частично — только token; root password остаётся) |
| Reality private key | Шаг 7 `apply_full.sh` | `#28` |
| Remnawave node connection token | Шаг 6 `apply_full.sh` (новый, без миграции старого) | — |
| DB/Redis passwords | Шаг 3 `provision_new_server.sh` (новый сервер) | — |

## 9. Миграция данных

**Подход — clean install + reimport (вариант A).** Никакого `pg_dump` со старого сервера.

| Источник | Что переносим | Метод |
|---|---|---|
| `infra/remnawave/configs/*.yaml` в репозитории | На текущий момент **пусты** — будут заполнены после первичного подъёма panel | `apply.py import` (dump текущего state в YAML) после первого `apply.py status` |
| `db-app` Postgres (старый сервер) | Ничего — миграций не было | — |
| Пользователь `test-01` | Пересоздаётся вручную через UI или через будущий `apply.py apply` | — |
| Subscription URL для test-01 | Меняется — новый `short_uuid`, новый домен | Generated by Remnawave |

**Уточнение:** В текущей версии `apply.py` команда `import` — это **dump state в YAML** (Terraform-style observe), а не **apply YAML в panel**. Это значит, реальный pipeline:
1. Подъём чистого panel на новом сервере.
2. Регистрация admin через UI.
3. Создание Reality keys / profile / squads / nodes / hosts через UI (или через будущие команды `apply.py apply` — задача `#46+`).
4. `apply.py import` — фиксирует получившийся state в `configs/*.yaml` для будущего version control.

Это означает, что Шаг 6 в pipeline `apply_full.sh` (§6) — это **сначала ручная UI-настройка panel**, потом `apply.py import` для фиксации state. После этого репозиторий становится source-of-truth, и при следующих миграциях будет уже полноценный `apply.py apply`.

## 10. Закрытие открытых задач

| # | Тип | Что | Статус после миграции |
|---|---|---|---|
| #27 | FINAL | Ограничить panel на localhost | **Закрыта** (panel за Caddy с IP-allowlist) |
| #28 | FINAL | Регенерировать Reality private key | **Закрыта** (шаг 7) |
| #29 | FUTURE | 2-й IPv4 для ingress/egress separation | Остаётся в backlog |
| #30 | FUTURE | Subscription template с RU-direct routing | Остаётся в backlog (phase #46) |
| #31 | FUTURE | Cloudflare WARP wrapper | Остаётся в backlog |
| #34 | FINAL | iptables persistent | **Закрыта** (cyber-berezka-iptables.service на обоих) |
| #36 | ongoing | Поддержка pitfalls doc | Обновим в рамках задачи #47 |
| #37 | ARCH | Sticky-per-user vs random IPv6 routing | Остаётся в backlog |
| #41 | FINAL | Регенерировать Remnawave API token | **Частично закрыта** (token ротирован; root password — нет, по решению пользователя) |
| #44 | блокер | DNS для cyber-berezka.tw1.ru | **Заменена** на DNS для `cyber-berezka.ru` в Beget |
| #46 | в работе | Site implementation (auth + cabinet + Brevo + Alembic) | Отдельная фаза, не в этой миграции |

## 11. Новые follow-up задачи

| # | Тип | Что |
|---|---|---|
| #47 | FOLLOW-UP | Обновить `docs/operations/pitfalls-and-fixes.md` под новую топологию: два сервера, разные роли, IPv6 только на старом. |
| #48 | FOLLOW-UP | `scripts/_verify_migration.sh` — 7-пунктный verification-сьют (см. §13). |
| #49 | FOLLOW-UP | Beget DNS API integration — `scripts/manage_dns.py`. |
| #50 | RISK | Ротация root-пароля старого сервера + SSH-hardening — отложено по решению пользователя, держим в backlog. |

## 12. Risks и assumptions

| Risk | Mitigation |
|---|---|
| Root password старого сервера остаётся скомпрометированным | Аккаунт root защищён только сложностью пароля и fail2ban. Перевод на ключи + ротация пароля отложен (задача `#50`). |
| Beget может не дать IPv6-пул на этот тариф | Новый сервер работает IPv4-only. Архитектура поддерживает оба сценария — если IPv6 появится, добавляется новый профиль через `apply.py import`. |
| Beget DNS API недоступен пользователю | Поддомены создаются вручную в UI по запросу. Это инвариант на момент миграции (см. правило IaC, исключения для UI-only ресурсов). |
| Прерывание migration pipeline между шагами 3 и 10 | Все шаги идемпотентны. Можно перезапустить `apply_full.sh` — он определяет, что уже сделано (например, по наличию контейнеров в `docker ps`), и доделает остальное. |
| OOM на новом сервере (3.8 GiB на 8 контейнеров) | Включается 2 GB swap. Если в продакшене всё равно тесно — апгрейд тарифа или вынос db-app на отдельный сервер. |
| RemnaWave node connection token mismatch при reimport | `apply.py import` пересоздаёт ноды в panel и одновременно обновляет токен в `.env` обоих серверов. Атомарно. |
| Let's Encrypt rate-limit при тестовых запусках на nip.io | Стартуем с production-ACME, fallback на staging-ACME если rate-limit достигнут (Caddy умеет автоматически). |

## 13. Verification (Phase 3 plan-do-verify)

`scripts/_verify_migration.sh` (задача `#48`, отдельно от миграции):

1. `docker ps --format 'table {{.Names}}\t{{.Status}}'` на новом сервере — все 8 контейнеров `healthy`.
2. `curl -sI https://{SITE_HOST}/` → 200, валидный TLS.
3. `curl -sI https://{ADMIN_HOST}/api/admin/users` без allowlist → 403; с allowlist → 200.
4. `python apply.py status` → обе ноды `online`, Reality handshake-метрики ненулевые.
5. `nmap -p 22,80,443,2053 212.74.231.217` → только эти 4 порта открыты.
6. `nmap -p 22,2053 194.87.83.31` → :22, :2053 открыты; :2222 закрыт извне; открыт только при `nmap -p 2222 -S 212.74.231.217 194.87.83.31`.
7. Клиент: импорт subscription URL test-01 → подключение → `curl -4 ifconfig.me` и `curl -6 ifconfig.me` — IP меняется в зависимости от squad (новый узел = IPv4 `212.74.231.217`, старый узел = один из IPv6 `2a03:6f02::*`).

## 14. Что НЕ входит в эту миграцию

- Phase 3–7 site implementation (auth + cabinet + Brevo + Alembic — задача `#46`). Продолжаем сразу после миграции.
- Beget DNS API integration (задача `#49`).
- Ротация root password старого сервера (задача `#50`).
- Sticky-per-user IPv6 routing (задача `#37`).
- IPv4 ingress/egress separation (задача `#29`).
- Cloudflare WARP (задача `#31`).
- Subscription template с RU-direct (задача `#30`).

## 15. Approval

Утверждено пользователем (Никита Олегович) по итогам трёх итераций brainstorming в сессии 2026-05-23:

- Часть 1 (архитектура) — «а» (одобрено).
- Часть 2 (репозиторий + автоматизация) — «а» (одобрено).
- Часть 3 (безопасность + ротация + closing задач) — «пароль пока не трогаем, оставляем все задачи, отдельная задача — поехали» (одобрено с поправкой: root password старого сервера — задача `#50`).

Следующий шаг — invoke skill `superpowers:writing-plans` для implementation plan.
