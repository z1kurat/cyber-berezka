# Cyber Berezka — Накопленные грабли и тонкие моменты

**Назначение:** живой документ. Сюда пишем каждую неочевидную проблему, её симптом, корень и фикс. Цель — не наступать дважды + дать готовую базу для declarative-provisioning (task #32) и runbook'а.

**Структура каждого пункта:** Симптом → Корень → Фикс → Где зафиксировано в коде/конфиге → Когда применять при следующем развёртывании.

---

## I. Провайдер (Timeweb)

### I.1. Timeweb выдаёт `/128`, не маршрутизирует `/64` целиком

- **Симптом:** `ip -6 addr show eth0` показывает только один глобальный IPv6 с маской `/128`. Попытка биндинга произвольного адреса из того же префикса — `ip addr add 2a03:6f02::abcd/128` — добавляется на интерфейс, но `curl -6 --interface 2a03:6f02::abcd ...` зависает.
- **Корень:** Timeweb на стороне роутера маршрутизирует только тот конкретный `/128`, который выдал в UI. Любые другие адреса из того же `/64` отбрасываются на upstream.
- **Фикс:** дополнительные IPv6 добавлять через UI «Облачные серверы → IP-адреса → IPv6 → Добавить». Каждый — отдельный `/128`.
- **Где:** `docs/research/2026-05-17-vpn-vless-technical-research.md` §7.13.

### I.2. Активация добавленного IPv6 задерживается ~10–40 минут

- **Симптом:** добавили адрес в UI, в БД UI он есть, но `curl --interface` сразу не работает.
- **Корень:** Timeweb пушит конфигурацию роутера асинхронно. Возможно требуется тикет в поддержку, если задержка > 40 мин.
- **Фикс:** ждать. Не паниковать. В первый раз потребовался один тикет «активируйте, пожалуйста».
- **Когда применять:** при расширении пула IPv6.

### I.3. Timeweb не добавляет IPv6 в гостевую ОС

- **Симптом:** Добавил адрес в UI → `ip -6 addr show eth0` его не видит.
- **Корень:** Timeweb на reboot пробрасывает только базовый IPv6 через cloud-init. Дополнительные адреса нужно биндить вручную в гостевой ОС.
- **Фикс:** `scripts/setup_ipv6_addresses.sh` читает `/etc/cyber-berezka/ipv6-pool.txt` и применяет `ip -6 addr add` для каждого. Запускается из systemd-юнита `infra/systemd/cyber-berezka-ipv6.service` (но юнит ещё не enabled — task #34).
- **Когда:** при reboot VPS или после добавления нового IPv6 в UI.

### I.4. Router cache refresh после re-add (60–120s)

- **Симптом:** Сразу после `ip -6 addr del` + `ip -6 addr add` (как делает наш setup-скрипт на boot) — `curl` через адрес зависает 60–120 секунд.
- **Корень:** Timeweb upstream-роутер кеширует ND/MAC entries. Удалённый адрес считается «мёртвым» некоторое время после возвращения.
- **Фикс:** `scripts/wait_ipv6_ready.sh` polling-цикл проверяет routability перед стартом Xray-ноды. Запускается из systemd-юнита между setup и docker.
- **Когда:** при каждом reboot.

---

## II. iptables / firewall

### II.1. INPUT policy = DROP, разрешены только конкретные порты

- **Симптом 1:** Panel timeout к 172.21.0.1:2222 несмотря на то что node слушает `*:2222`. Pkt доходит до bridge, no reply.
- **Симптом 2:** Клиенты не подключаются к Reality на :2053 — `tcpdump 0 packets captured` при попытке коннекта извне.
- **Корень:** На VPS унаследована строгая firewall-конфигурация от прошлого владельца (для CRM_AI / 3X-UI). INPUT policy DROP, разрешены только: 22, 53, 80, 443, 8000, 8443, 18443, 20001, 58128, lo, 172.17.0.0/16. Наш бридж 172.21.0.0/16 и наш порт 2053 не были в списке.
- **Фикс (live):**
  ```bash
  iptables -I INPUT 9 -s 172.21.0.0/16 -j ACCEPT    # panel↔node на :2222
  iptables -I INPUT 10 -p tcp --dport 2053 -j ACCEPT # клиенты на Reality
  ```
- **Не persistent:** оба правила в памяти ядра, на reboot пропадут. **Task #34** — сделать persistent (через `iptables-persistent` или ExecStartPre в systemd).
- **Когда применять:** на любой VPS со строгим default-DROP firewall — открывать каждый новый порт явно.

### II.2. Host → 127.0.0.1:2222 работает, panel-container → 172.21.0.1:2222 не работает (до фикса II.1)

- **Симптом:** Curl с самого host'a проходит, из контейнера — timeout.
- **Корень:** Host-to-self трафик идёт через OUTPUT chain (минует INPUT). Контейнер-to-host идёт через bridge → INPUT chain → DROP. Это **постоянная ловушка при отладке** firewall в Docker.
- **Фикс:** тестировать связность ИЗНУТРИ соответствующего контейнера, не с host'a.

---

## III. Docker / containers

### III.1. Custom-network gateway != docker0 gateway

- **Симптом:** Panel в `remnawave-network` (172.21.0.0/16) не может достучаться до 172.17.0.1 (default docker0 gateway).
- **Корень:** Docker bridge networks изолированы. У каждой свой gateway. У нашего bridge — `172.21.0.1`. Не `172.17.0.1`.
- **Фикс:** при настройке node address в panel использовать `172.21.0.1` (= host со стороны нашей сети), не `172.17.0.1`. Альтернатива: `extra_hosts: ["host.docker.internal:host-gateway"]` в compose + использовать `host.docker.internal` как адрес.
- **Где:** `infra/docker-compose.yml`, SQL update в БД nodes.address.

### III.2. `docker compose restart` НЕ перечитывает `.env`

- **Симптом:** Изменил `.env`, сделал `docker compose restart` — контейнер видит **старые** env-переменные.
- **Корень:** `restart` перезапускает существующий контейнер с его существующим конфигом. Чтобы перечитать env_file нужно пересоздать контейнер.
- **Фикс:** `docker compose down && docker compose up -d` после изменения `.env`.
- **Когда:** каждый раз после правки `.env`.

### III.3. macOS tar добавляет AppleDouble метадату

- **Симптом:** После tar→ssh→untar на Linux появляются файлы `._<имя>` рядом с реальными.
- **Корень:** macOS tar сохраняет xattr через AppleDouble.
- **Фикс:** `find . -name '._*' -delete` после распаковки. Или использовать `tar --no-xattrs` при создании.

### III.4. macOS tar сохраняет UID 501 / staff GID

- **Симптом:** После распаковки на Linux файлы принадлежат UID 501 (на VPS это бывает чужой пользователь).
- **Фикс:** `chown -R root:root .` после распаковки на VPS.

### III.5. `network_mode: host` для Xray-ноды обязателен

- **Симптом:** Без `network_mode: host` Xray не может биндить произвольные IPv6 из host'a (контейнер видит только свой Docker-NAT IPv6).
- **Корень:** Контейнерные bridge-сети по умолчанию имеют свой IPv6-subnet (если включён), не публичные адреса host'a.
- **Фикс:** в `infra/docker-compose.node.yml` — `network_mode: host` для `remnanode`.

### III.6. CAP_NET_ADMIN warning в Remnawave node

- **Симптом:** В логах ноды `[HandlerService] CAP_NET_ADMIN is not available.`
- **Корень:** Сетевая статистика Remnawave (NetworkStatsService) использует CAP_NET_ADMIN для чтения интерфейсных счётчиков. Контейнер не имеет.
- **Эффект:** В UI панели «Трафик: 0.00 GiB» даже когда трафик реально идёт. **Сам VPN работает.**
- **Фикс (опционально):** добавить `cap_add: [NET_ADMIN]` в compose ноды, если хотим точную статистику.

### III.7. Docker build cache раздувает диск

- **Симптом:** `/var/lib/docker = 40 GB`, `df -h /` показывает 81%.
- **Корень:** Build cache не чистится автоматически. На VPS с активной разработкой накапливается до десятков GB.
- **Фикс:** `docker builder prune -af && docker image prune -af`. У нас высвободило 24 GB одним махом.
- **Когда:** периодически проверять `docker system df`.

---

## IV. Remnawave (panel + node)

### IV.1. Node env var называется `NODE_PORT`, не `APP_PORT`

- **Симптом:** Node container стартует и сразу падает: `❌ NODE_PORT: Required`.
- **Корень:** Конвенции отличаются. Panel использует `APP_PORT`. Node — `NODE_PORT`. Я перепутал по аналогии.
- **Фикс:** в `infra/docker-compose.node.yml`: `NODE_PORT=${NODE_PORT}` (а не `APP_PORT`).

### IV.2. Valkey (не Redis), Postgres 17.6 (не 16)

- **Симптом:** Если ставить generic `redis:7` — Remnawave не подключается через Unix socket.
- **Корень:** Официальный compose Remnawave использует `valkey/valkey:9-alpine` и `postgres:17.6`. Valkey — fork Redis от Linux Foundation, совместим, но имя другое.
- **Фикс:** использовать **точно** официальные образы и теги. См. `infra/docker-compose.yml`.

### IV.3. Valkey слушает Unix socket, не TCP

- **Симптом:** Backend падает: `REDIS_HOST: Either REDIS_SOCKET or both REDIS_HOST and REDIS_PORT must be provided`.
- **Корень:** Официальный compose запускает valkey с `--port 0 --unixsocket /var/run/valkey/valkey.sock`. TCP отключён.
- **Фикс:** в `.env` указать `REDIS_SOCKET=/var/run/valkey/valkey.sock`. Volume `valkey-socket` смонтирован в обоих контейнерах: backend и valkey.

### IV.4. Default-Profile создаётся ПУСТЫМ (Shadowsocks-заглушка)

- **Симптом:** Subscription URL возвращает плейсхолдер-ссылки `vless://0...0@0.0.0.0:1?...→ No hosts found / → Check Hosts tab / → Check Internal Squads tab`.
- **Корень:** UI Remnawave при первом запуске создаёт стартовый профиль с Shadowsocks-инбаундом без клиентов. Это **не работает** для нашей задачи. Реально надо: создать VLESS+Reality inbound с нашими ключами.
- **Фикс:** Заменить JSON профиля целиком на наш через UI «Профили → Default-Profile → Сохранить». Шаблон в `docs/research/...` и в task #32 для автоматизации.

### IV.5. Default-Squad НЕ связан с inbound автоматически

- **Симптом:** Создал inbound + node, добавил пользователя — subscription URL по-прежнему выдаёт плейсхолдеры.
- **Корень:** В Remnawave модель: User → Squad → Inbound. Связь Squad↔Inbound создаётся отдельно. UI «Внутренние сквады → Default-Squad → выбрать inbound». Дефолтно — пусто.
- **Фикс:** `INSERT INTO internal_squad_inbounds (internal_squad_uuid, inbound_uuid) VALUES ('<squad>', '<inbound>')`. Или через UI. В task #32 будет автоматизировано.

### IV.6. Создание node не создаёт Host

- **Симптом:** Все компоненты есть (inbound, squad, user, node), но subscription URL всё равно отдаёт плейсхолдеры с подсказкой "Check Hosts tab".
- **Корень:** Host = "публичная маска" inbound: hostname/IP, порт, SNI, fingerprint, что показывать клиенту в его конфиге. Создаётся ОТДЕЛЬНО от node entry. Пропущен у нас.
- **Фикс:** INSERT в `hosts` с минимум:
  ```sql
  INSERT INTO hosts (
      remark, address, port, sni, fingerprint, security_layer,
      config_profile_inbound_uuid, config_profile_uuid
  ) VALUES ('NL Amsterdam', '194.87.83.31', 2053, 'www.microsoft.com', 'chrome',
            'DEFAULT', '<inbound-uuid>', '<profile-uuid>');
  ```

### IV.7. Node `address` в panel != какой адрес использовать панели

- **Симптом:** В форме создания ноды поле «Адрес» по умолчанию `172.17.0.1`. После сохранения panel пишет в логах: `timeout 15000ms exceeded` к этому адресу.
- **Корень:** Panel-контейнер живёт в `remnawave-network` (172.21.0.0/16). Адрес 172.17.0.1 — gateway другого bridge (docker0), не виден из этой сети.
- **Фикс:** UPDATE nodes SET address = '172.21.0.1' WHERE name = '<node>'. Или в UI указать `172.21.0.1`.

### IV.8. Panel↔Node SECRET_KEY = base64(JSON{nodeCertPem, nodeKeyPem, caCertPem, jwtPublicKey})

- **Симптом:** SECRET_KEY в UI выглядит как `eyJub2RlQ2VydFBlbSI6...` — очень длинная base64-строка.
- **Корень:** Это full mTLS bundle: серверный сертификат ноды, её приватный ключ, CA-сертификат, публичный ключ для JWT-валидации. Генерируется панелью при создании ноды entry.
- **Фикс:** в `.env` положить как `NODE_SECRET_KEY=eyJub2RlQ2VydFBlbSI6...`. **Не публиковать в публичные репо.**

### IV.9. После изменения link'ов в БД node нужно перезапустить

- **Симптом:** Добавил пользователя в squad, или squad↔inbound — Xray на ноде по-прежнему имеет `inbounds:[]` или `usersCount:0`.
- **Корень:** Panel пушит конфиг в ноду при подключении и периодически. После изменения в БД нужно либо подождать reload-цикл, либо принудительно перезапустить ноду.
- **Фикс:** `docker compose -f docker-compose.node.yml restart`. После restart смотреть `docker logs remnanode --tail 10` — должно быть `VLESS-Reality-Vision has N users`.

### IV.10b. Inconsistent wrapping в list-эндпоинтах Remnawave API

- **Симптом:** `GET /api/config-profiles` отдаёт `{"total": N, "configProfiles": [...]}`, `GET /api/internal-squads` — `{"total": N, "internalSquads": [...]}`, `GET /api/users` — `{"total": N, "users": [...]}`, но `GET /api/nodes` и `GET /api/hosts` отдают **list напрямую**.
- **Корень:** разные controller'ы NestJS возвращают разные shape'ы. Часть paginated, часть нет.
- **Фикс:** в `_lib/client.py` каждый list-helper знает свой ключ:
  ```python
  list_profiles → data.get("configProfiles", [])
  list_squads   → data.get("internalSquads", [])
  list_users    → {total, users}
  list_nodes    → list as-is
  list_hosts    → list as-is
  ```
- **Где зафиксировано:** `infra/remnawave/_lib/client.py`, см. doc-комментарий в `# --- domain helpers ---`.

### IV.10. API-tokens ОБЯЗАНЫ создаваться через UI

- **Симптом:** `POST /api/tokens` с login JWT возвращает **403 Forbidden**: `"For API requests you must create own API-token in the admin dashboard."`
- **Корень:** Remnawave намеренно блокирует создание API-токена через login-JWT (admin-session). Это security feature: admin-сессия короткоживущая, API-token долгоживущий. Чтобы предотвратить «слив» долгоживущего токена через скомпрометированную короткую сессию — backend требует явного клика админа в UI.
- **Фикс:** в bootstrap — один UI-клик: Settings → API Tokens → Create → скопировать → передать в `bootstrap_token.py`. См. `infra/remnawave/bootstrap_token.py` (просит paste, валидирует через `/api/system/health`, кладёт в `.env`).
- **Когда применять:** при каждом setup новой VPS / переинсталляции panel. Не пытаться автоматизировать — это пойдёт против security design Remnawave.

### IV.11. Subscription URL отдаёт base64 в дефолтном UA

- **Симптом:** `curl <subscription-url>` возвращает base64-blob, не plain `vless://...`.
- **Корень:** v2ray-family клиентов ждут base64-encoded list. Только некоторые UA получают plain text.
- **Фикс:** для отладки `curl <url> | base64 -d` или `curl <url>/json` (Remnawave формат).

---

## V. VLESS / Reality / Xray-config

### V.1. Reality на не-:443 порту вызывает warning от GFW

- **Симптом:** В Xray-логе `[Warning] infra/conf: REALITY: Listening on non-443 ports may get your IP blocked by the GFW`.
- **Корень:** GFW (и аналогичные DPI) считают Reality на нестандартном порту менее правдоподобным. У нас :2053 потому что :443 занят Caddy и нет второго IPv4.
- **Фикс долгосрочный:** task #29 — заказать 2-й IPv4. Caddy → IP1:443, Xray → IP2:443.
- **Фикс на сейчас:** не нужен, :2053 (Cloudflare HTTPS-alt) plausibly. Просто warning.

### V.2. **КРИТИЧЕСКИЙ:** routing rules для IPv6/IPv4 — порядок имеет значение

**Часть 1 — sendThrough IPv6 + IPv4 destination = silent fail:**
- **Симптом:** Клиент подключается, в логах Xray `accepted tcp:8.8.8.8:53`, но в браузере ничего не открывается. Трафик-counter в UI = 0.
- **Корень:** TCP socket с IPv6 source IP **физически не может** соединиться к IPv4 destination. ОС не строит маршрут. Connect fails silently.
- **Фикс:** правило `ip:[0.0.0.0/0] → v4-fallback` + `domainStrategy: IPOnDemand`.

**Часть 2 — порядок IPv6/IPv4 catch-all rules:**
- **Симптом после Части 1:** Сайты открываются, но `ifconfig.io` показывает **только IPv4** (наш единственный `194.87.83.31`) для **всех** клиентов. IPv6 ротация не работает.
- **Корень:** В `IPOnDemand` Xray резолвит домены и сматчивает правила по порядку. Для dual-stack доменов (с обоими A и AAAA) первое подходящее правило выигрывает. Если правило IPv4 (`0.0.0.0/0`) стоит ДО IPv6 (`::/0`) — все dual-stack-домены идут через v4-fallback. IPv6-пул простаивает.
- **Фикс:** правило `ip:[::/0] → v6-pool` ДО `ip:[0.0.0.0/0] → v4-fallback`. Тогда:
  - Dual-stack домены → IPv6 → ротация по 4 адресам ✓
  - IPv4-only домены/IP → IPv4 fallback ✓
  - IPv6-only → IPv6 ✓
  - Pure-IPv4 (literal IP) → IPv4 fallback ✓
- **Где зафиксировано:** `scripts/generate_xray_outbounds.py` обновлён; live-конфиг в БД исправлен; **этот пункт — single source of truth для порядка правил**.

### V.3. `domainStrategy: AsIs` vs `IPIfNonMatch` vs `IPOnDemand`

- **AsIs** (default): домены проверяются только против domain-rules. IP-rules не применяются к доменам.
- **IPIfNonMatch:** если ни одно domain-rule не сматчилось — резолвим в IP и проверяем IP-rules.
- **IPOnDemand:** при каждом матчинге резолвим домены и применяем IP-rules первыми.
- **Когда что:** для нашей цели (route IPv4 dest через v4-fallback) — `IPOnDemand`, чтобы домены резолвились и проверялись IPv4-правилом.

### V.4. Reality "fallback to target" маскирует ошибки

- **Симптом:** Клиент с неверным ключом подключается, видит TLS handshake, думает что в VPN, но на самом деле получает прямой microsoft.com.
- **Корень:** Это **запланированное** поведение Reality: при неверной подписи клиента — прозрачный TCP-proxy на target-сайт. Это и есть anti-detect.
- **Эффект для нас:** Если user'у выдан неправильный ключ (UUID не в инбаунде) — он будет видеть Microsoft, думая что в VPN. Симптом «трафик идёт, но не свой».
- **Когда замечать:** если клиент «подключился но ничего не работает» — проверить что user в squad, squad связан с inbound, inbound на ноде (`docker logs remnanode | grep usersCount`).

### V.5. ShortIDs: пустая строка vs хеши

- **Деталь:** Reality `shortIds` массив. Можно положить пустую строку `""` — тогда клиенты без short ID будут приниматься (security-relaxed). Лучше — только конкретные random hex значения.
- **У нас:** 8 random hex по 16 символов. Без пустой строки.

---

## VI. Caddy

### VI.1. Two compose-файлов или один

- **Симптом:** Официальные доки Remnawave рекомендуют отдельный compose для Caddy с external network. Мы объединили в один.
- **Эффект:** Работает. В будущем при разделении (Caddy + сайт на одной VPS, panel на другой) — компонент Caddy легче извлечь, потому что он у нас уже в одном файле с panel. Возможный refactor.

### VI.2. Caddy `:443` блок без домена возвращает 204

- **Использование:** В `Caddyfile`:
  ```caddy
  :443 {
      tls internal
      respond 204
  }
  ```
- **Зачем:** анти-fingerprint. Сканеры, бьющие по IP без правильного Host-заголовка, получают пустой 204 с самоподписанным сертификатом — не узнают какие домены живут.

### VI.3. Caddy reload не требует restart

- **Команда:** `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile`. Применяет изменения без drop existing connections.
- **Когда:** после правки Caddyfile.

---

## VII. Network / клиентская сторона

### VII.1. Утечка egress IP через локальный SOCKS5 на устройстве (habr.com/ru/articles/1020080)

- **Симптом:** Malware/private-spaces на телефоне обходят VPN, читают локальный SOCKS5 от Xray, узнают наш egress IP.
- **Корень:** Все Xray-based VPN-клиенты на Android запускают локальный SOCKS5 без auth. Любой процесс на устройстве может его использовать.
- **Фиксы на сервере:**
  - Blocked Happ через UA-фильтр в Caddy (Happ хуже всех — также Xray API дампит).
  - Task #29: 2-й IPv4 для разделения ingress/egress.
  - Task #30: subscription template с RU-direct routing (RU-трафик НЕ через VPN, не виден на egress).
  - Task #31: WARP wrapper для IPv4-fallback egress.

### VII.2. Subscription URL содержит секреты

- **Деталь:** URL вида `https://admin.../api/sub/<token>` отдаёт VLESS-конфиг с user UUID, который = доступ к VPN.
- **Эффект:** Распространение URL == выдача доступа. Не публиковать.

### VII.3. v2RayTun / Hiddify в норме корректно роутят, Happ — нет

- **Список одобренных:** v2RayTun, Hiddify, NekoBox, FairVPN.
- **Заблокированы у нас:** Happ (через Caddy UA-block) — Xray API без auth.

---

## VIII. Безопасность сессии (мета)

### VIII.1. Reality private key выведен в чат (тестовая фаза)

- **Текущий ключ:** `WLIU5f3McbmcfRUe98ZuYxqCvZVNHcLSOmW7NcyB90s` (приватный).
- **Действие на production:** перегенерировать (task #28) и удалить старый из всех клиентов.

### VIII.2. Root SSH пароль выведен в чат

- **Действие:** `passwd root`, отключить PasswordAuthentication, использовать SSH-ключи.

---

## IX. Что относить к "single-source-of-truth" в репо

- **Конфиги:** `infra/.env.example`, `infra/docker-compose.yml`, `infra/docker-compose.node.yml`, `infra/caddy/Caddyfile`, `infra/systemd/cyber-berezka-ipv6.service`.
- **Скрипты:** `scripts/setup_ipv6_addresses.sh`, `scripts/wait_ipv6_ready.sh`, `scripts/detect_ipv6_pool.sh`, `scripts/verify_ipv6_routability.sh`, `scripts/generate_xray_outbounds.py`.
- **Документы:** `docs/superpowers/specs/...` (design), `docs/research/...` (research), `docs/operations/pitfalls-and-fixes.md` (ЭТОТ файл).
- **Не в репо:** `.env` (gitignored), пароли, секретные ключи.

---

## X. Список того что НЕ покрыто скриптами и требует ручной операции

| Операция | Способ сейчас | Куда автоматизировать |
|---|---|---|
| Добавить новый IPv6 в Timeweb | UI Timeweb, кнопка «Добавить» | task #32 + Timeweb API если есть |
| Создать VPN-пользователя | UI Remnawave «Пользователи → Создать» | task #32: Remnawave API `/api/users` |
| Подвязать пользователя к Squad | UI или SQL INSERT | task #32: Remnawave API + SQL fallback |
| Создать новую ноду | UI Remnawave + manual SQL UPDATE address | task #32 |
| Изменить routing rules / outbounds | SQL UPDATE config_profiles.config | task #32: Remnawave API + jsonb_set |
| Восстановить iptables после reboot | вручную | task #34 |
| Обновить Reality keys | UI Remnawave + регенерация ключей | task #32 |
| Перенос на новый VPS | полностью вручную | task #32 + setup-vps.sh |

---

## XI. Открытые архитектурные вопросы (на финальное ревью)

### XI.1. Random vs sticky-per-user IPv6 routing

- **Сейчас:** `balancer strategy: random` — каждое соединение случайно через один из 4 IPv6.
- **Альтернатива:** закрепить за каждым пользователем один IPv6 (hash(user_uuid) → outbound).
- **Когда обсуждать:** при росте до платных подписок и расширении пула IPv6 ≥16.
- **Подробно:** task #37 — все плюсы/минусы и варианты реализации.

---

## Правила ведения этого файла

1. **Каждая новая граблями** добавляется в момент обнаружения, не «потом запишу».
2. Структура: **Симптом → Корень → Фикс → Где зафиксировано** (если в коде/конфиге — путь файла).
3. Если фикс временный (live, не в репо) — обязательно ссылка на task с дедлайном.
4. При повторении одной и той же ошибки — обновлять пункт, не плодить дубликаты.
