# Cyber Berezka — Site Design

**Дата:** 2026-05-17
**Статус:** дизайн утверждён, реализация после DNS-настройки доменов
**Связанные доки:** `2026-05-17-vpn-vless-mvp-design.md` (стек), `2026-05-17-apply-py-design.md` (управление Remnawave), `pitfalls-and-fixes.md`

---

## 1. Цель сайта и границы

### 1.1. Что делает сайт

1. **Лендинг** — продаёт «защищённое соединение» (Kaspersky-style positioning, юридически чистый словарь — см. §6.2).
2. **Регистрация** по email + пароль с email-верификацией через Brevo SMTP.
3. **Личный кабинет:** пользователь видит свои ключи, генерирует новые (через Remnawave API), копирует subscription URL и QR-код.
4. **Админка** Remnawave (после миграции туда из `admin.194-87-83-31.nip.io`).

### 1.2. Что НЕ в скоупе MVP

- Платежи / биллинг — отдельная фаза.
- Telegram бот, mobile app — не сейчас.
- Multi-tenancy / суб-админы.
- Локализация на другие языки кроме русского.

---

## 2. Топология доменов

| URL | Кто видит | Что |
|---|---|---|
| `home.cyber-berezka.tw1.ru/` | публично | Лендинг |
| `home.cyber-berezka.tw1.ru/admin/*` | IP-allowlist (вы + админы) | Remnawave panel |
| `cyber-berezka.tw1.ru/` | публично | редирект на `home.*` (canonical) |
| `cyber-berezka.tw1.ru/auth/register` | публично | Регистрация |
| `cyber-berezka.tw1.ru/auth/login` | публично | Вход в кабинет |
| `cyber-berezka.tw1.ru/auth/verify/<token>` | публично | Подтверждение email |
| `cyber-berezka.tw1.ru/cabinet/*` | за сессией | Кабинет |
| `cyber-berezka.tw1.ru/api/sub/<token>` | публично | Subscription URLs для клиентов |

### Caddy mapping (концепт)

```caddy
{$LANDING_DOMAIN} {                              # home.cyber-berezka.tw1.ru
    # admin path с IP-allowlist
    @admin path /admin/*
    @allowed_admin {
        remote_ip {$ADMIN_IP_WHITELIST}
    }
    handle @admin {
        handle @allowed_admin {
            reverse_proxy * http://remnawave:3000
        }
        respond "403 Forbidden" 403
    }
    # всё остальное — лендинг
    reverse_proxy * http://site:8000/landing/*
}

{$SITE_DOMAIN} {                                 # cyber-berezka.tw1.ru
    reverse_proxy * http://site:8000             # FastAPI app
}

:443 {
    tls internal
    respond 204                                  # анти-fingerprint catch-all
}
```

**Внутри Docker:**
- `remnawave` — НЕ доступен публично (только из Docker network)
- `site:8000` (FastAPI) — НЕ доступен публично (только через Caddy)
- `site` ходит в `http://remnawave:3000` через **internal Docker DNS**, с Bearer token из `.env`

Это закрывает беспокойство пользователя: внешний мир видит ТОЛЬКО Caddy, который проксирует ТОЛЬКО специфические пути. `/api/users`, `/api/hosts`, `/api/internal-squads` и т.п. **не торчат публично**.

---

## 3. Архитектура сервисов (docker-compose)

```
                    ┌──────────────┐
INTERNET ──:80──► │  Caddy 2.9    │ TLS termination + routing
         :443─►  └──────┬───────┘
                        │
       ┌────────────────┼────────────────────┐
       │                │                    │
       ▼                ▼                    ▼
  ┌────────────┐  ┌──────────┐    ┌────────────────┐
  │ site        │  │ remnawave │    │ remnanode      │
  │ FastAPI     │──┤  panel    │    │  (host network)│
  │ :8000       │  │  :3000   │    │  Xray на :2053 │
  └──┬──┬──┬───┘  └─────┬────┘    └────────────────┘
     │  │  │            │
     ▼  ▼  ▼            ▼
  ┌────┐ ┌────┐ ┌─────────────┐
  │ db │ │redis│ │remnawave-db │
  │app │ │     │ │  Postgres   │
  └────┘ └────┘ └─────────────┘
   ▲ ▲    ▲ Postgres / Valkey уже есть для panel; site получает СВОЮ пару
   │ └────┘ db-app — отдельный Postgres (изоляция данных приложения от panel)
   │
   site sessions, audit_log, etc.
```

### Сервисы и их образы

| Service | Image | Покрывает |
|---|---|---|
| `caddy` | `caddy:2.9` | TLS + reverse proxy + IP allowlist (уже есть) |
| `remnawave` | `remnawave/backend:2.7.4` | Panel API + UI (уже есть) |
| `remnanode` | `remnawave/node:2.7.0` | Xray на :2053 (уже есть) |
| `remnawave-db` | `postgres:17.6` | Panel БД (уже есть) |
| `remnawave-redis` | `valkey/valkey:9-alpine` | Panel cache (уже есть) |
| **`site`** | `python:3.12-slim` + наш Dockerfile | FastAPI app (новое) |
| **`db-app`** | `postgres:17.6` | БД приложения (новое) |

---

## 4. Stack — frontend и backend

### Backend (`site`)

```
FastAPI 0.115+        — HTTP framework
SQLAlchemy 2.x async  — ORM
asyncpg               — Postgres driver
Alembic               — миграции
Pydantic v2           — валидация
Jinja2                — рендеринг HTML
argon2-cffi           — пароли (argon2id)
httpx                 — клиент Remnawave API (тот же что в apply.py)
itsdangerous          — подписанные cookies для CSRF
brevo-python (или httpx) — Brevo Transactional Mail API
python-multipart      — формы
```

### Frontend (рендерится Jinja2)

```
Tailwind CSS 3.4      — собирается через CLI в одну минифицированную CSS
Alpine.js 3.x         — лёгкая интерактивность (no SPA, no React)
Cormorant Garamond    — Headlines (Google Fonts, self-hosted)
Inter                 — Body (Google Fonts, self-hosted)
JetBrains Mono        — Технические детали
```

Self-host шрифтов важен: загружаем с нашего домена (без обращения к Google) — privacy + uptime.

---

## 5. Палитра «Премиум-кремовое» — финал

```
/* Base */
--bg-main:        #F7F3EB;   /* тёплый кремовый */
--bg-card:        #FFFFFF;
--bg-section-alt: #EFE9DD;   /* секции-чередование */

/* Text */
--text-primary:   #1A1818;   /* почти чёрный с тёплым подтоном */
--text-secondary: #4A4541;
--text-muted:     #6B6661;
--text-on-dark:   #F7F3EB;

/* Accents */
--accent-gold:    #B8935A;   /* медь/бронза — берёзовая кора */
--accent-gold-dk: #966D40;
--cta-primary:    #B8351F;   /* винно-красный — CTA */
--cta-hover:      #9A2B17;

/* Status */
--success:        #5F8B5C;   /* приглушённый зелёный (НЕ дешёвый ярко-зелёный) */
--danger:         #B8351F;
--warning:        #C48A2C;

/* Borders / Shadows */
--border-light:   #E8DCC0;
--border-strong:  #C9B898;
--shadow-card:    0 8px 24px rgba(26,24,24,0.06);
--shadow-cta:     0 4px 16px rgba(184,53,31,0.25);
```

Принципы:
- Фон — **тёплый кремовый**, не больнично-белый.
- Текст — **почти чёрный с тёплым подтоном** (не #000), для премиума.
- CTA — **винный**, единственный «громкий» цвет на странице, мгновенно читается.
- Бронза — для тонких акцентов (подчёркивания, иконки, разделители).

### Tailwind config (фрагмент)

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        bg: { main: '#F7F3EB', card: '#FFFFFF', alt: '#EFE9DD' },
        text: { primary: '#1A1818', secondary: '#4A4541', muted: '#6B6661' },
        accent: { gold: '#B8935A', goldDk: '#966D40' },
        cta: { DEFAULT: '#B8351F', hover: '#9A2B17' },
        success: '#5F8B5C',
        warning: '#C48A2C',
        border: { light: '#E8DCC0', strong: '#C9B898' },
      },
      fontFamily: {
        serif: ['"Cormorant Garamond"', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'Menlo', 'monospace'],
      },
      boxShadow: {
        card: '0 8px 24px rgba(26,24,24,0.06)',
        cta: '0 4px 16px rgba(184,53,31,0.25)',
      },
    },
  },
};
```

---

## 6. Структура страниц

### 6.1. Лендинг `home.cyber-berezka.tw1.ru/`

#### 6.1.1. Hero

```
[Bg: тёплый кремовый, очень тонкие силуэты берёз справа, parallax]

         КИБЕР                       (Cormorant 96px, gold underline)
         БЕРЁЗКА

         Своё. Цифровое. Защищённое.   (Inter 24px, muted)

         [ Начать защиту → ]            (CTA винно-красный, scale-on-hover)
         [ Узнать больше    ]           (secondary link)
```

#### 6.1.2. «Зачем это нужно» — 4 use case

Сетка 2×2 из карточек с hover-эффектом (`translateY(-4px)` + усиленный shadow):

| Иконка | Заголовок | Описание |
|---|---|---|
| ☕︎ | Защита в публичных Wi-Fi | Кафе, аэропорты, отели — шифруем ваше соединение от перехвата |
| 💳 | Безопасные онлайн-платежи | Банковские операции под защитой 256-битного шифрования |
| 🔒 | Приватность данных | Ваши персональные данные не становятся товаром |
| 🌐 | Стабильное соединение | Шифрование без потери скорости — современный протокол Reality |

#### 6.1.3. «Технологии» — trust block

Касперский-style: 3-4 «солидных» факта:

| Цифра | Текст |
|---|---|
| 256-bit | Шифрование военного уровня (ChaCha20-Poly1305) |
| Reality | Современный протокол (Project XTLS) |
| NL | Сервера в Нидерландах — за пределами юрисдикции РФ |
| 0 | Логов персонального трафика |

#### 6.1.4. «Как это работает» — 3 шага

```
① Регистрация по email      ②  Получите ключ за 30 сек     ③  Подключение в один клик
   (защищённый процесс)        (мгновенная генерация)         (поддержка iOS, Android, ...)
```

#### 6.1.5. FAQ

Аккордеоны:
- **Это легально?** «Да. Сервис обеспечивает шифрование трафика. Использование подобных решений для защиты персональных данных закон не ограничивает.»
- **Что вы сохраняете обо мне?** «Только email и факт регистрации. Содержимое и адресаты вашего трафика мы не пишем.»
- **Какие приложения поддерживаются?** v2RayTun (iOS/Android), Hiddify (все платформы), NekoBox (Android). Только эти — другие не гарантируем.
- **Можно ли использовать с нескольких устройств?** В MVP — до 3 устройств на одну подписку.

#### 6.1.6. CTA повторно + Footer

```
[ Зарегистрироваться бесплатно ]   (golden border + красная заливка)

Footer:
  Cyber Berezka © 2026
  Условия использования | Политика конфиденциальности | Контакты
  Telegram: @cyber_berezka (если запустим)
```

### 6.2. Регистрация `/auth/register`

```
       [Glassmorphism card по центру, белый на тёплом кремовом]

       Создать аккаунт

       Email:    [____________]
       Пароль:   [____________]
       Повтор:   [____________]

       [ Согласен с условиями использования ]    (checkbox с ссылкой)

       [ Создать аккаунт → ]                      (CTA)

       Уже есть аккаунт? Войти
```

**Правила:**
- Пароль ≥ 12 символов
- Email-валидация (regex + Brevo)
- После сабмита: «Письмо подтверждения отправлено на ваш email»
- Verify-token хранится в `users.email_verify_token` (см. design doc)

### 6.3. Вход `/auth/login`

Минималистичная форма, та же стилистика.

### 6.4. Кабинет `/cabinet`

```
[Шапка кабинета]
   Cyber Berezka      [ Профиль ▾ ] [ Выйти ]

[Hero-блок состояния]
   ◯ Активная защита                       статус-точка + soft pulse green
   test01@example.com

[CTA — получить новый ключ]
   [ + Получить ключ ]                     golden border, hover-scale

[Карточка: Мои ключи]
   ▸ Phone (создан 17 мая 2026)
      Subscription URL: https://...sub/...
      [ Скопировать ]  [ Показать QR ]  [ Отозвать ]
   ▸ Laptop (создан 17 мая 2026)
      ...

[Карточка: Установка приложений]
   iOS:      v2RayTun        →  App Store
   Android:  Hiddify         →  Google Play
   Windows:  Hiddify Desktop →  Download
   macOS:    Hiddify         →  Mac App Store

[Footer-инструкции]
   Скопируйте subscription URL → откройте приложение → «Добавить из URL»
```

---

## 7. Backend — структура

```
infra/site/
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── migrations/
├── app/
│   ├── main.py                 # FastAPI entry
│   ├── config.py               # Pydantic Settings
│   ├── deps.py                 # DI: db session, current_user
│   ├── models/
│   │   ├── user.py
│   │   ├── session.py
│   │   ├── vpn_key.py
│   │   └── audit_log.py
│   ├── services/
│   │   ├── auth.py             # регистрация, login, password hash
│   │   ├── email.py            # Brevo SMTP / API
│   │   ├── remnawave.py        # клиент API (импорт из infra/remnawave/_lib/client.py)
│   │   └── vpn_keys.py         # бизнес-логика выдачи ключей
│   ├── routers/
│   │   ├── landing.py          # GET /, /about, /faq
│   │   ├── auth.py             # /auth/*
│   │   ├── cabinet.py          # /cabinet/*
│   │   └── api_sub.py          # PROXY /api/sub/* → remnawave/api/sub/*
│   ├── templates/
│   │   ├── base.html
│   │   ├── landing/index.html
│   │   ├── auth/register.html
│   │   ├── auth/login.html
│   │   └── cabinet/index.html
│   ├── static/
│   │   ├── css/                # сгенерированный Tailwind output
│   │   ├── fonts/              # self-hosted Cormorant + Inter
│   │   └── img/                # логотип, силуэты берёз, иконки
│   └── security/
│       ├── passwords.py        # argon2id wrapper
│       ├── csrf.py             # double-submit
│       └── ratelimit.py        # Redis-based
```

### 7.1. DB schema приложения (db-app)

Перенос из `2026-05-17-vpn-vless-mvp-design.md` §4 с минимальными правками:

```sql
CREATE TABLE users (
    id                       BIGSERIAL PRIMARY KEY,
    email                    VARCHAR(255) NOT NULL UNIQUE,
    email_normalized         VARCHAR(255) NOT NULL UNIQUE,
    password_hash            VARCHAR(255) NOT NULL,
    email_verified_at        TIMESTAMPTZ,
    email_verify_token       VARCHAR(64),
    password_reset_token     VARCHAR(64),
    password_reset_expires   TIMESTAMPTZ,
    is_active                BOOLEAN NOT NULL DEFAULT true,
    is_admin                 BOOLEAN NOT NULL DEFAULT false,
    -- Связь с Remnawave: один сайт-пользователь = один Remnawave-user
    remnawave_user_uuid      UUID UNIQUE,
    remnawave_short_uuid     VARCHAR(64),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at            TIMESTAMPTZ,
    last_login_ip            INET,
    failed_login_count       INT NOT NULL DEFAULT 0,
    locked_until             TIMESTAMPTZ
);

CREATE TABLE sessions (
    id           VARCHAR(64) PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    ip_address   INET,
    user_agent   TEXT,
    revoked_at   TIMESTAMPTZ
);

CREATE TABLE vpn_keys (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label           VARCHAR(64),
    status          VARCHAR(16) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at    TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE audit_log (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT REFERENCES users(id) ON DELETE SET NULL,
    event_type   VARCHAR(64) NOT NULL,
    event_data   JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address   INET,
    user_agent   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Изменение vs первоначальный дизайн:**
- `users.remnawave_user_uuid` — ссылка на пользователя в panel БД. **Один сайт-юзер = один Remnawave-юзер.** Имя в panel генерится по hash (или просто `user_<id>`).
- `vpn_keys` упрощён: подробности (subscription URL, short_uuid) лежат в panel; в нашей таблице — только метаданные (label, status).

### 7.2. Dataflow создания ключа

```
1. Browser POST /cabinet/keys (form CSRF-token + optional label)
2. site проверяет: session valid, user email_verified, не превышен лимит ключей
3. Если у user'а нет remnawave_user_uuid:
      POST /api/users в Remnawave с username=user_<id>_<rand>, traffic_limit=0, expire=far-future
      → сохранить uuid, short_uuid в users
4. Запросить subscription URL: GET /api/users/{uuid}
5. INSERT в vpn_keys (label=...)
6. INSERT в audit_log (event='key.create')
7. Редирект /cabinet/keys/{id}, показать subscription URL + QR
```

Все Remnawave-вызовы — **через внутреннее Docker DNS** (`http://remnawave:3000`), Bearer token из `.env`. Никакого публичного API.

---

## 8. Brevo SMTP интеграция

Brevo (бывший Sendinblue) даёт **300 mail/day бесплатно** — хватит на семейный MVP с запасом.

### 8.1. Bootstrap

1. Регистрация на `brevo.com` — free план
2. Settings → SMTP & API → создать API key
3. Положить в `.env` приложения:
   ```
   BREVO_API_KEY=<api-key>
   BREVO_SENDER_EMAIL=noreply@cyber-berezka.tw1.ru
   BREVO_SENDER_NAME="Cyber Berezka"
   ```

### 8.2. Использование

Через **Transactional API**, не SMTP (надёжнее, лучше delivery):

```python
async def send_verification(email: str, token: str) -> None:
    verify_url = f"https://cyber-berezka.tw1.ru/auth/verify/{token}"
    await httpx_client.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": settings.brevo_api_key, "accept": "application/json"},
        json={
            "sender": {"name": "Cyber Berezka", "email": settings.brevo_sender_email},
            "to": [{"email": email}],
            "subject": "Подтверждение регистрации в Cyber Berezka",
            "htmlContent": render_template("emails/verify.html", verify_url=verify_url),
        },
    )
```

Шаблон письма — той же стилистики что и сайт (кремовый фон, бронзовый CTA).

### 8.3. Что нужно в Brevo до запуска

- **DKIM** — настроить домен `cyber-berezka.tw1.ru` для подписания писем (иначе всё в спам)
- **SPF** — TXT-запись в DNS у `tw1.ru`. Может потребовать поддержки Timeweb (если они блокируют редактирование TXT для tw1.ru)
- **DMARC** — после DKIM+SPF

Для MVP может работать без DKIM, но письма часто будут в спаме. Решаем когда дойдём.

---

## 9. ToS / Privacy Policy — драфт

### 9.1. Принципы

- **Никогда** не использовать слова: "VPN", "обход блокировок", "анонимность", "скрыть IP", "запрещённые ресурсы", "доступ к заблокированным сайтам" (см. memory: `project_legal_positioning.md`)
- **Услугу называем:** «Защищённое соединение», «Сервис шифрования трафика»
- Privacy = no-log как **архитектурный факт**, а не маркетинг
- Юрисдикция: пока не фиксируем (за пределами MVP). Когда будут юр-лица — править.

### 9.2. Структура ToS

```
1. Определения
   • Сервис — «Cyber Berezka» — программно-аппаратный комплекс для шифрования
     интернет-трафика пользователя.
   • Пользователь — физическое лицо, прошедшее регистрацию.
   • Ключ доступа — уникальный идентификатор, открывающий доступ к Сервису.

2. Что делает Сервис
   2.1 Сервис обеспечивает шифрование трафика по протоколу VLESS+Reality
       с алгоритмом ChaCha20-Poly1305.
   2.2 Сервис защищает соединение от перехвата в публичных Wi-Fi.
   2.3 Сервис не модифицирует и не цензурирует содержимое передаваемых данных.

3. Что мы НЕ делаем
   3.1 Не логируем содержимое вашего трафика.
   3.2 Не записываем IP-адреса посещаемых вами сайтов.
   3.3 Не модифицируем DNS-запросы.

4. Обязанности Пользователя
   4.1 Не передавать Ключ доступа третьим лицам.
   4.2 Не использовать Сервис для нарушения законодательства РФ.
   4.3 Не использовать Сервис для DDoS-атак, спама, скрейпинга, нарушения
       авторских прав или других вредоносных действий.

5. Право отзыва доступа
   5.1 Мы оставляем за собой право отозвать Ключ при нарушении пп. 4.1-4.3.
   5.2 Уведомление об отзыве направляется на email Пользователя.

6. Ограничение ответственности
   6.1 Сервис предоставляется «как есть» без гарантий бесперебойной работы.
   6.2 Мы не несём ответственность за содержание и доступность сторонних
       интернет-ресурсов.

7. Изменение условий
   7.1 Мы можем изменять Условия. Изменения вступают в силу через 14 дней
       с момента публикации на сайте.
```

### 9.3. Privacy Policy

```
1. Какие данные мы собираем
   1.1 Регистрация: email, пароль (в зашифрованном виде).
   1.2 Технические: IP последнего логина, время регистрации/последнего входа.
   1.3 НЕ собираем: содержимое трафика, посещаемые сайты, время сессий
       шифрованного соединения, метаданные подключений.

2. Зачем мы их собираем
   2.1 Email — для подтверждения регистрации и восстановления доступа.
   2.2 IP логина — для разбора инцидентов компрометации учётной записи.

3. Срок хранения
   3.1 Email и связанные данные — пока существует учётная запись.
   3.2 После удаления учётной записи — до 30 дней (для восстановления при
       ошибочном удалении), затем безвозвратное удаление.

4. Передача третьим лицам
   4.1 Мы не передаём ваши данные третьим лицам.
   4.2 Brevo (поставщик услуг email-рассылок) получает email-адрес и
       содержимое транзакционных писем. Брево обрабатывает данные согласно GDPR.

5. Ваши права
   5.1 Вы можете запросить экспорт всех ваших данных.
   5.2 Вы можете удалить учётную запись из кабинета.
```

### 9.4. Где живут

- `cyber-berezka.tw1.ru/legal/terms` — ToS
- `cyber-berezka.tw1.ru/legal/privacy` — Privacy
- Ссылки в footer и в чекбоксе при регистрации

---

## 10. Безопасность (recap §11 design-doc + новое)

### 10.1. Сетевой уровень

- ✅ FastAPI приложение **не имеет публичного порта** — Caddy единственная точка входа
- ✅ Remnawave panel API **не торчит наружу** — site вызывает через internal Docker DNS
- ✅ `/admin/*` на `home.*` — за IP-allowlist
- ✅ Один общий Docker bridge `remnawave-network` для site + remnawave; БД (`db-app`, `remnawave-db`) и Redis в отдельных под-сетях

### 10.2. Auth уровень

- argon2id для паролей (m=64 MiB, t=3, p=4)
- Email-верификация **обязательна** для выдачи ключа
- Session cookies: `HttpOnly`, `Secure`, `SameSite=Lax`, `__Host-session` префикс
- CSRF double-submit для всех POST
- Rate limit: login 5/15min/IP, register 5/h/IP, key-create 10/h/user
- Sessions хранятся в `sessions` + горячий кэш в Redis с TTL

### 10.3. Application уровень

- Все Remnawave-вызовы — после проверки сессии и бизнес-логики
- Token хранится только в `.env` site-контейнера (chmod 600)
- Audit-log каждой операции изменения (создание ключа, login fail, и т.п.)
- Логи site — `loglevel: warning`, не пишем тела форм, не пишем токены/пароли

---

## 11. Реализация — поэтапно

| Phase | Что | Время |
|---|---|---|
| **0. DNS** | Пользователь настраивает A-records для `cyber-berezka.tw1.ru` и `home.*` → `194.87.83.31` | 5–15 мин |
| **1. Caddy + scaffolding** | Обновить Caddyfile под новые домены, добавить пустой `site` контейнер с healthcheck | 1 ч |
| **2. БД + миграции** | Поднять `db-app` Postgres, написать Alembic-миграции для users/sessions/vpn_keys/audit_log | 1 ч |
| **3. Auth + landing** | Регистрация, login, password reset, базовый лендинг с Direction A стилями | 4 ч |
| **4. Cabinet + Remnawave integration** | Кнопка «Получить ключ», список ключей, QR, integration с panel API | 2 ч |
| **5. Brevo** | Email-верификация, шаблон письма | 1 ч |
| **6. ToS + Privacy** | Финальный текст, страницы `/legal/*` | 1 ч |
| **7. Polish** | Анимации, hover, mobile-responsive | 2 ч |

**Итого MVP: ~12 часов реализации.** Может растянуться на 2-3 сессии.

---

## 12. Verification criteria

Сайт готов к семейному тесту когда:

- [ ] `https://home.cyber-berezka.tw1.ru` показывает лендинг с правильной стилистикой
- [ ] `https://cyber-berezka.tw1.ru/auth/register` создаёт пользователя, отправляет email
- [ ] Подтверждение email через ссылку → переход к login
- [ ] `https://cyber-berezka.tw1.ru/auth/login` логинит, создаёт session
- [ ] `https://cyber-berezka.tw1.ru/cabinet` показывает «нет ключей» → кнопка «Получить» создаёт ключ через Remnawave API
- [ ] Ключ имеет рабочий subscription URL — открывается в браузере, отдаёт VLESS-конфиг
- [ ] QR-код в кабинете отображается, сканируется v2RayTun/Hiddify
- [ ] `home.*/admin` доступен только с IP-allowlist
- [ ] Любые POST без CSRF-token → 403
- [ ] Rate limits срабатывают (5 wrong-password логинов → 15-минутный lockout)
- [ ] ToS/Privacy в footer и при регистрации
- [ ] HSTS, CSP, X-Frame-Options присутствуют в headers

---

## 13. Открытые вопросы

| # | Вопрос | Когда решать |
|---|---|---|
| 1 | DKIM/SPF для cyber-berezka.tw1.ru для писем Brevo | Phase 5 (email) |
| 2 | Логотип / favicon — рисуем или текст-only? | Phase 3 (landing) |
| 3 | Локализация на английский — нужно ли? | После запуска |
| 4 | Платежи — где интегрируем (CryptoCloud / Telegram Stars / ЮKassa)? | После семейного теста |
| 5 | Регистрация через Telegram Login Widget — добавить ли как опцию? | После платежей |
