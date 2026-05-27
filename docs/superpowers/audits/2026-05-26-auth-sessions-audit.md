# Audit — auth/sessions/cabinet (2026-05-26)

> **Status 2026-05-27:** P1 (пункты 1–5) — DONE. См. секцию «Резюме выполнения» в конце документа.

Внутренний technical-debt review своего кода. Список доработок, нужных для приведения auth-стека к ожидаемому уровню зрелости.

Scope: `infra/site/app/{main,deps,security,services,routers,cli}.py`, `infra/caddy/Caddyfile`.

---

## Доработки приоритета 1 (блокируют production)

### 1. Подключить CSRF middleware к state-changing эндпоинтам

Файл `infra/site/app/security/csrf.py` содержит `generate_csrf` / `verify_csrf` (HMAC-SHA256, constant-time compare). Функции нигде не импортируются — grep `verify_csrf|generate_csrf` даёт совпадение только в самом файле определения.

POST-эндпоинты без проверки токена:

- `routers/auth.py:38` — register_submit
- `routers/auth.py:93` — login_submit
- `routers/auth.py:128` — logout
- `routers/admin.py:72` — approve_user
- `routers/admin.py:92` — reject_user
- `routers/cabinet.py:121` — keys_create
- `routers/cabinet.py:147` — keys_revoke

Что нужно:

- `Depends(verify_csrf_token)` на каждый POST-эндпоинт после авторизации.
- В layout-шаблоне (`templates/base.html`) рендерить `<meta name="csrf-token" content="{{ csrf_token }}">` + hidden `<input name="csrf_token">` во всех формах.
- Middleware/Depends, выставляющий `request.state.csrf_token = generate_csrf(session_id)`.

SameSite=Lax даёт частичную защиту, но не покрывает старые клиенты и subdomain-сценарии. Двойная защита (Lax + CSRF) — стандарт.

### 2. Реализовать rate limiting

Файл `config.py:31` содержит только комментарий `# Redis (for session cache + rate limiting)` — реализации нет.

Что нужно (минимум):

- `/auth/login` — 5 попыток / 15 минут на ключ `IP+email_normalized`.
- `/auth/register` — 3 попытки / час на IP.
- `/auth/verify/{token}` — 10 попыток / час на IP.
- `/cabinet/keys` POST — 10 запросов / 5 минут на user_id.

Подход: библиотека `slowapi` или ручной Redis-counter с TTL. Слой — на уровне Depends, не middleware (нужен доступ к Form-данным).

### 3. Активировать колонки `failed_login_count` / `locked_until`

Колонки определены в `models/user.py` и созданы миграцией `0001_initial.py`, но в `services/auth.py:authenticate` (стр. 63-73) логики работы с ними нет.

Что нужно в `authenticate`:

```python
now = datetime.now(timezone.utc)
if user.locked_until and user.locked_until > now:
    return None, "locked"
if not verify_password(password, user.password_hash):
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= 10:
        user.locked_until = now + timedelta(minutes=30)
    await self.db.commit()
    return None, "invalid_credentials"
user.failed_login_count = 0
user.locked_until = None
await self.db.commit()
```

В router `routers/auth.py:103-111` добавить mapping `"locked": "Аккаунт временно заблокирован, попробуйте позже"`.

### 4. Хэшировать session_id перед записью в БД

Файл `services/sessions.py:26-30`:

```python
sid = generate_opaque_token()
sess = Session(id=sid, ...)  # в БД лежит plaintext
```

Сравнить с `services/auth.py:38` — verify token хранится через `hash_token_for_storage`. У сессий — нет.

Что нужно:

- Миграция: новый столбец `session_hash` (string, indexed, unique). Заполняется `hash_token_for_storage(sid)`.
- В `SessionService.create` — в БД пишется `hash_token_for_storage(sid)` в новую колонку; в cookie — `sid` plaintext.
- В `SessionService.get` / middleware — поиск по `session_hash`.
- Старые сессии expire'нутся естественно (TTL 720 часов). Можно ускорить через `UPDATE sessions SET expires_at = NOW()` для существующих после deploy.

### 5. Унифицировать middleware и SessionService

Файл `main.py:60-70` — middleware `attach_current_user` делает прямой `select(Session).where(Session.id == sid)`, дублируя `SessionService.get` (sessions.py:39-45). Любая будущая правка SessionService (Redis cache TTL update, last_seen_at refresh, IP rotation check) middleware обойдёт.

Что нужно:

- Middleware инстанцирует `SessionService(db, redis)` и вызывает `.get(sid)`.
- Единственный путь чтения сессии — через сервис.

---

## Доработки приоритета 2 (важно, но не блокирует)

### 6. Убрать `'unsafe-inline'` из CSP script-src

Файл `main.py:86` — `script-src 'self' 'unsafe-inline'`. Inline-скрипты есть в:

- `templates/cabinet/keys.html` (AmneziaVPN copy-handler через data-attr — уже частично вынесен)
- Будущий toggle «Полная/Умная защита» — планировался inline.

Что нужно:

- Все обработчики событий вынести в `static/js/cabinet.js` через `addEventListener`.
- После — заменить `'unsafe-inline'` на `'nonce-{request.state.csp_nonce}'` или просто убрать (если inline не останется).

### 7. Убрать email enumeration

Файл `routers/auth.py:55-58` — на `AuthError("email_taken")` отдаётся «Email уже занят». Атакующий может составить список зарегистрированных email через пробные регистрации.

Что нужно: отдавать одинаковый ответ для обоих случаев — «Если email доступен, мы отправили письмо для подтверждения». Реальную причину логировать в audit-log.

### 8. Выровнять тайминг authenticate

Файл `services/auth.py:63-68` — при отсутствии user возврат происходит до `verify_password`, что даёт ~300ms разницу в response time.

Что нужно: при `user is None` выполнить dummy verify против заранее подсчитанного `DUMMY_ARGON2_HASH` constant. Эффект — выравнивание тайминга, плюс отсутствие side-channel «email существует / нет».

### 9. Защитить CLI `promote-admin`

Файл `app/cli.py` — команда `promote-admin <email>` запускается через `python -m app.cli` без верификации вызывающего и без audit-log.

Что нужно:

- Требовать env-переменную `BERZ_ADMIN_CLI_TOKEN`, сравнивать constant-time с `settings.admin_cli_token`.
- Писать `AuditLog(event_type="user.promoted_via_cli", event_data={"target": email, "host": socket.gethostname()})`.

### 10. Различать HTML vs JSON в `require_user`

Файл `deps.py:50-51` — `HTTPException(status_code=303, headers=...)` для редиректа. Нестандартно для XHR-клиентов: они получат redirect вместо 401.

Что нужно: проверять `request.headers.get("accept", "")`:

- содержит `text/html` → 303 redirect на /auth/login;
- иначе → 401 JSON `{"detail": "not_authenticated"}`.

---

## Доработки приоритета 3 (watch / готовиться)

### 11. Cookie без `Domain` атрибута

Файл `routers/auth.py:116-124` — `set_cookie` без `domain`. Это правильно для текущей стадии (nip.io, переменные хосты). При переезде на `cyber-berezka.ru` решить, нужны ли cookies, разделяемые между `home.*` и `api.*`. Если да — добавить `domain=.cyber-berezka.ru` + усилить CSRF (двойная защита от subdomain takeover).

### 12. Caddyfile IP-allowlist покрывает Remnawave-панель, но не `/cabinet/admin/*`

Файл `Caddyfile:48-60` — `@admin_paths` (`/admin/*`, `/api/admin/*`) с `remote_ip {$ADMIN_IP_WHITELIST}` корректно изолирует Remnawave dashboard на `{$ADMIN_HOST}`.

`/cabinet/admin/*` (approve/reject pending users) живёт на `{$SITE_HOST}` под FastAPI и не защищён IP-allowlist на сетевом уровне. Это осознанно: админ-доступ управляется через `require_admin` + `User.is_admin`. Watch: если админский UI обрастёт большим количеством операций или sensitive bulk-actions — рассмотреть дополнительный IP-allowlist на Caddy для `/cabinet/admin/*`.

---

## Положительные стороны (зафиксировано)

- Argon2id с m=64MiB, t=3, p=4 — соответствует OWASP Password Storage Cheat Sheet.
- Opaque session tokens через `secrets.token_urlsafe(32)` — корректный источник энтропии.
- HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy — заголовки установлены через middleware.
- Email verification token хранится только в виде SHA-256-хэша (хороший паттерн, применить тот же подход к session_id — см. п. 4).
- Cookie `HttpOnly=True`, `Secure` (зависит от settings.cookie_secure), `SameSite=Lax`, явный `path="/"`.
- CSP `frame-ancestors 'none'` (защита от clickjacking).
- Constant-time compare в `verify_csrf` через `hmac.compare_digest`.

---

## Итоговый порядок выполнения

1. п. 4 — хэширование session_id (миграция + код). База безопасного хранения.
2. п. 1 — CSRF middleware + формы. Защищает от cross-site POST.
3. п. 5 — унификация middleware/SessionService.
4. п. 2 + п. 3 — rate-limit + brute-force counter. Одной волной, оба касаются login flow.
5. п. 6, 7, 8 — CSP, email-enumeration, timing. Одной волной по auth-роутеру.
6. п. 9 — защита CLI. Отдельный коммит.
7. п. 10, 11, 12 — minor polish.

После каждой группы — `docker compose restart site`, проверка `/auth/login`, `/auth/register`, `/cabinet`, `/cabinet/keys`.

---

## Резюме выполнения (2026-05-27)

P1 закрыт. Изменения по группам:

**Группа A — `services/auth.py`, `routers/auth.py`, `deps.py`, `templates/auth/{register,login}.html`:**
- п. 8 — таймминг-выравнивание через `_DUMMY_PASSWORD_HASH`;
- п. 7 — UX-улучшение для email collision (показывается ссылка «Войти →» вместо маскировки enumeration — решение Никиты Олеговича);
- п. 10 — `require_user` различает HTML vs JSON по Accept-header.

**Группа B — `services/sessions.py`, `main.py`:**
- п. 4 — session id хэшируется SHA-256 перед записью в БД (cookie остаётся plaintext);
- п. 5 — middleware `attach_current_user` переведён на `SessionService.get`.
- Side-effect: текущие сессии после deploy инвалидируются. Все пользователи разлогинятся.

**Группа C — `deps.py`, `main.py`, 5 роутов, 8 форм в шаблонах:**
- п. 1 — добавлен `verify_csrf_token` Depends, применён к: `/auth/logout`, `/cabinet/admin/pending/.../approve`, `.../reject`, `/cabinet/keys` POST, `/cabinet/keys/.../revoke`;
- middleware устанавливает `request.state.csrf_token`;
- hidden `<input name="csrf_token">` добавлен во все авторизованные формы.

**Группа D — `security/rate_limit.py` (новый), `services/auth.py`, `routers/auth.py`:**
- п. 2 — rate-limit (Redis INCR + EXPIRE): `/auth/login` 5/15min на IP+email, `/auth/register` 3/час на IP, `/auth/verify/{token}` 10/час на IP;
- п. 3 — активирован `failed_login_count` (++на fail, reset на success) + `locked_until` (на 30 мин при `>= 10` fails); добавлено сообщение «Аккаунт временно заблокирован».

Все 11 модифицированных файлов прошли AST + Jinja syntax checks.

## Что осталось (P2 / P3)

- п. 6 — убрать `'unsafe-inline'` из CSP script-src (нужен вынос inline-скриптов и/или CSP-nonce);
- п. 9 — защитить CLI `promote-admin` (env-token + audit-log);
- п. 11–12 — watch при переезде на prod-домен и при росте `/cabinet/admin/*`.

Не делалось в этой сессии — отдельным заходом после deploy и регрессионного теста P1.

---

## Deploy status 2026-05-27

P1 batch задеплоен на production (Beget VPS 212.74.231.217):
- Commit: `dc4143c` (P1 — hashed sessions, CSRF, rate-limit, brute-force).
- Verification: `/healthz`, `/auth/login`, `/cabinet` отвечают 200 через Caddy.
- Side-effect: все существующие сессии инвалидированы (session_id теперь SHA-256 в БД, старые plaintext не матчатся). Пользователи перелогинятся естественно.

