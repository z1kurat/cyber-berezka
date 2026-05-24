# Cyber Berezka — Site Design Amendments (2026-05-23)

**Дата:** 2026-05-23
**Статус:** утверждён пользователем 2026-05-23 на этапе brainstorming-2
**Базовый дизайн:** `2026-05-17-site-design.md` (utilities, schema, stack — оттуда без изменений, кроме пунктов ниже)
**Связанный migration spec:** `2026-05-23-migration-to-beget-design.md`

---

## 1. Что меняется vs базовый дизайн

Базовый design 2026-05-17 не покрывает три требования, добавленных пользователем 2026-05-23:

1. **Deep-link «1 кнопкой»** в кабинете — открытие приложения с автоимпортом подписки.
2. **Динамический список серверов** на лендинге и в кабинете — берётся из Remnawave panel API.
3. **Admin approval gate** — после email-verify пользователь не получает доступ к ключам пока админ не одобрил.

Плюс: домены и URL'ы в базовом spec'е устарели после миграции 2026-05-23 — везде заменить `cyber-berezka.tw1.ru` → `cyber-berezka.ru` (с `nip.io` defaults на этапе Stage 1).

Всё остальное (стек, ToS/Privacy, палитра, security recap, Caddy mapping концепт) — без изменений.

---

## 2. Обновление доменов (правка §2 базового spec)

Везде в таблицах и в кодовых сниппетах заменить:

| Старое (базовый spec) | Новое (этот amendment) |
|---|---|
| `home.cyber-berezka.tw1.ru` | `{$SITE_HOST}` (= `212-74-231-217.nip.io` Stage 1, `home.cyber-berezka.ru` Stage 2) |
| `cyber-berezka.tw1.ru` (apex) | `{$APEX_REDIRECT_HOST}` (= `placeholder.invalid` Stage 1 — apex отсутствует, `cyber-berezka.ru` Stage 2) |
| `admin.194-87-83-31.nip.io` | `{$ADMIN_HOST}` (= `admin.212-74-231-217.nip.io` Stage 1, `admin.cyber-berezka.ru` Stage 2) |

**Архитектурное упрощение:** в новой архитектуре (migration spec §2) лендинг и кабинет живут на **одном** хосте `{$SITE_HOST}`. Apex используется только для 301-redirect (Caddy уровня) и не задействован site-кодом. Это упрощает routing — нет различия между «landing host» и «cabinet/auth host». Все user-facing URL'ы на одном хосте.

Соответственно базовый spec §2 «Топология доменов» сжимается до:

| URL | Кто видит | Что |
|---|---|---|
| `{$SITE_HOST}/` | публично | Лендинг |
| `{$SITE_HOST}/auth/register` | публично | Регистрация |
| `{$SITE_HOST}/auth/login` | публично | Вход |
| `{$SITE_HOST}/auth/verify/<token>` | публично | Подтверждение email |
| `{$SITE_HOST}/cabinet/*` | за сессией | Кабинет |
| `{$SITE_HOST}/cabinet/admin/*` | за сессией + `is_admin=true` | Админ-страницы (pending users) |
| `{$SITE_HOST}/legal/terms`, `/legal/privacy` | публично | ToS, Privacy (уже реализовано) |
| `{$ADMIN_HOST}/` | IP-allowlist | Remnawave panel |
| `{$ADMIN_HOST}/api/sub/<short_uuid>` | публично | Subscription URLs (проксируется Caddy в panel) |

---

## 3. Deep-link «1 кнопкой» в кабинете

### 3.1. Поддерживаемые клиенты и схемы

| Клиент | Платформы | Custom scheme |
|---|---|---|
| **v2RayTun** | iOS, Android | `v2raytun://import/<urlencoded_subscription_url>` |
| **Hiddify** | iOS, Android, Windows, macOS, Linux | `hiddify://install-sub?url=<urlencoded_subscription_url>` |
| **NekoBox** | Android, Windows | `sn://subscription?url=<urlencoded_subscription_url>` |

URL-encoding (RFC 3986) обязателен — subscription URL содержит `:` и `/`.

### 3.2. UI

В кабинете рядом с каждым ключом — три кнопки в группе («Подключиться»):

```
┌────────────────────────────────────────────────────────────┐
│  Phone (создан 17 мая 2026)                                │
│                                                             │
│  Подключить в приложении:                                   │
│  [ v2RayTun ]  [ Hiddify ]  [ NekoBox ]                    │
│                                                             │
│  Или вручную:  [ Скопировать URL ]  [ QR ]  [ Отозвать ]   │
└────────────────────────────────────────────────────────────┘
```

Стилистика: первичные deep-link кнопки — белые с золотой обводкой (`border-accent-gold-dk`), на hover — заливка `accent-gold` + белый текст. Скрипт обработчика `onclick="location.href='v2raytun://...'"` (без AJAX — просто location change, браузер сам передаёт OS).

### 3.3. Edge cases

- **Приложение не установлено** — браузер показывает дефолтное сообщение «Нет приложения для открытия». В UI рядом есть линки на сторы (как было в §6.4 базового spec): `App Store`, `Google Play`, `Hiddify Downloads`. Не пытаемся определять платформу автоматически — оставляем user-агентский выбор.
- **Desktop пользователь** — кнопка `v2RayTun` десктоп не поддерживает (моб. only); подсказка-тултип «Только iOS/Android». Hiddify работает на всех; NekoBox — Windows/Android.
- **Privacy-проблема ссылок:** subscription URL встроен в схему. URL уникальный для каждого пользователя (`short_uuid`). Это нормально — это его же URL, который он копирует в любом случае. Никаких новых утечек.

### 3.4. Реализация

Никаких backend-вызовов — кнопки чисто фронтовые, формируют URL шаблоном:

```html
<a class="btn-deeplink" href="v2raytun://import/{{ subscription_url | urlencode }}">v2RayTun</a>
<a class="btn-deeplink" href="hiddify://install-sub?url={{ subscription_url | urlencode }}">Hiddify</a>
<a class="btn-deeplink" href="sn://subscription?url={{ subscription_url | urlencode }}">NekoBox</a>
```

Jinja2 фильтр `urlencode` встроен.

---

## 4. Динамический список серверов

### 4.1. Источник данных

`GET /api/nodes` Remnawave API через internal Docker DNS (`http://remnawave:3000`), Bearer token из `.env`. Возвращает массив нод с полями: `name`, `address`, `port`, `countryCode`, `isConnected`, `isConnecting`, `createdAt`. Latency — не запрашиваем (panel не даёт это просто; задача для будущей версии).

### 4.2. Кэширование

site-redis ключ `nodes:list` со значением — JSON массив минимизированных полей (`name`, `countryCode`, `isConnected`). TTL = **30 секунд**. При промахе кэша — синхронный вызов в Remnawave API, заполнение кэша, ответ. Это не вызывает race conditions (worst case — несколько concurrent calls в panel, всё read-only).

### 4.3. UI на лендинге

Блок «Наши серверы» под секцией «Технологии» (новый блок в §6.1.3-ish):

```
[Background: bg-section-alt]

      Наши серверы

      ◉ 2 сервера онлайн в 2 странах

      🇩🇪 Германия (Frankfurt)      ◉ онлайн
      🇳🇱 Нидерланды (Amsterdam)    ◉ онлайн

      Подключение распределяется автоматически.
      Чем больше серверов — тем устойчивее ваш канал.
```

`◉` — зелёная точка `--success`. Если нода `isConnecting` или `!isConnected` — серая точка с тултипом «Технические работы».

Если массив пустой (ноды не созданы или ошибка API) — блок не рендерится (не показываем кривое UI).

### 4.4. UI в кабинете

Похожий блок над списком ключей:

```
[Карточка bg-card]

  Доступные серверы

  🇩🇪 Frankfurt    ◉ онлайн
  🇳🇱 Amsterdam    ◉ онлайн

  Reality распределяет подключения автоматически между серверами.
```

Без возможности выбора — VLESS-Reality по squad'у использует автоматическое распределение (random / least-loaded в зависимости от panel настроек).

### 4.5. Сопоставление стран и городов

Локально в коде (`app/services/geo.py`):

```python
COUNTRY_NAMES = {
    "DE": ("Германия", "Frankfurt", "🇩🇪"),
    "NL": ("Нидерланды", "Amsterdam", "🇳🇱"),
    "RU": ("Россия", "Moscow", "🇷🇺"),
    # ... добавляем по мере появления новых нод
}
```

Если страны нет в карте — показываем код ISO как есть (`countryCode + 🌐`). На MVP-этапе у нас две страны, остальные добавляем когда нужно.

### 4.6. Тех. детали

- Endpoint `GET /api/site/nodes` (новый, на site) — отдаёт ту же информацию из кэша (для возможного будущего dashboard live-обновления через Alpine.js + setInterval, в MVP не нужно).
- На server-side рендеринге (Jinja2 в `landing/index.html` и `cabinet/index.html`) шаблон получает `nodes` контекст переменную; контекст заполняется в роутер-функции.

---

## 5. Admin approval gate

### 5.1. Изменения в DB schema

К таблице `users` из §7.1 базового spec добавить два поля:

```sql
ALTER TABLE users
    ADD COLUMN admin_approved_at  TIMESTAMPTZ,
    ADD COLUMN admin_approved_by  BIGINT REFERENCES users(id);
```

Семантика:
- `admin_approved_at IS NULL AND email_verified_at IS NOT NULL` → user в состоянии «pending admin approval»
- `admin_approved_at IS NOT NULL` → доступ выдан, ключи можно создавать
- `is_admin = TRUE` — flag-bit (уже есть в базовом дизайне) для людей, которые могут заходить на admin-страницы

### 5.2. Lifecycle пользователя

```
[ register ] → [ email-verify pending ] → [ admin approval pending ] → [ full access ]
                  (verify_token в URL)        (никаких действий)         (cabinet ключи)
```

Состояния и их UI:

| Состояние | Где видит | Что в UI |
|---|---|---|
| **Не верифицировал email** | `/cabinet` (после login) | Большой блок: «Подтвердите email — мы отправили письмо на `<email>`. Не пришло? [Отправить заново]» |
| **Pending admin approval** | `/cabinet` | Большой блок: «Ваша заявка на рассмотрении. Мы сообщим вам, как только выдадим доступ к сервису. Это обычно занимает не более суток.» Никаких кнопок-ключей. |
| **Approved** | `/cabinet` | Полный кабинет с кнопкой «Получить ключ» и списком ключей (как в базовом дизайне §6.4). |
| **Approved + is_admin** | `/cabinet` | Полный кабинет + дополнительная навигация-ссылка «Pending users» → `/cabinet/admin/pending`. |

### 5.3. Admin pending page

`GET /cabinet/admin/pending` — список user'ов с `admin_approved_at IS NULL AND email_verified_at IS NOT NULL`:

```
[Шапка кабинета]   ... [ Pending users ]

Pending approval

┌────────────────────────────────────────────────────────┐
│ email@example.com                                      │
│ Зарегистрирован: 23.05.2026 14:32                      │
│ Email подтверждён: 23.05.2026 14:35                    │
│ Регистрация с IP: 1.2.3.4                              │
│ [ Approve ]  [ Reject ]                                │
└────────────────────────────────────────────────────────┘
```

`Approve`: POST `/cabinet/admin/pending/{user_id}/approve`. Сервер:
1. Проверяет `current_user.is_admin == True`.
2. `UPDATE users SET admin_approved_at=now(), admin_approved_by=<admin_id> WHERE id=<target>`.
3. Отправляет user'у email через Brevo: «Доступ к Cyber Berezka выдан». Email содержит ссылку на кабинет.
4. INSERT в `audit_log` (event=`user.approved`).
5. Redirect обратно на `/cabinet/admin/pending`.

`Reject`: POST `/cabinet/admin/pending/{user_id}/reject` + опциональное поле `reason` (textarea). Сервер:
1. Проверяет `current_user.is_admin == True`.
2. **НЕ удаляет** запись (audit-trail сохраняем) — добавляет `rejected_at`, `rejected_by`, `rejection_reason` поля. *(Этот доп. набор полей включить в migration)*.
3. Отправляет user'у email: «Заявка отклонена. Reason: ...» (если reason есть).
4. INSERT в `audit_log` (event=`user.rejected`).
5. Redirect.

Соответственно к schema добавляются ещё:

```sql
ALTER TABLE users
    ADD COLUMN admin_rejected_at   TIMESTAMPTZ,
    ADD COLUMN admin_rejected_by   BIGINT REFERENCES users(id),
    ADD COLUMN rejection_reason    TEXT;
```

User с `rejected_at IS NOT NULL` при попытке login видит сообщение «Доступ отклонён» с reason — и не получает session.

### 5.4. Бэкдор для первого админа

В свежей системе нет ни одного `is_admin=true` user'a. Делаем management-команду:

```bash
docker compose exec site python -m app.cli promote-admin --email admin@example.com
```

Скрипт `app/cli.py` с командой `promote-admin <email>` устанавливает `is_admin=true` для уже зарегистрированного user'a. Вы регистрируетесь как обычный user, подтверждаете email, потом через SSH `docker compose exec site python -m app.cli promote-admin --email ваш@email` — сами себя апрувите и делаете админом.

После этого все остальные регистрации проходят через ваш approval.

### 5.5. Login проверка

В `services/auth.py` функция `authenticate`:

```python
async def authenticate(email, password, ...) -> User | LoginError:
    user = await get_user_by_email(email)
    if not user or not verify_password(password, user.password_hash):
        return LoginError("invalid_credentials")
    if user.admin_rejected_at is not None:
        return LoginError("rejected", reason=user.rejection_reason)
    # email verification и admin approval НЕ блокируют login —
    # пользователь видит cabinet с pending-сообщениями
    return user
```

Это важно: pending-юзер должен иметь доступ к кабинету, чтобы видеть свой статус и понимать что заявка на рассмотрении. Только rejected — блокируем на login-этапе.

---

## 6. Email-шаблоны (новое)

Новые шаблоны для Brevo, в дополнение к существующему `verify.html`:

- `app/templates/emails/approved.html` — отправляется при approve. Содержит CTA «Открыть кабинет» → `{$SITE_HOST}/cabinet`.
- `app/templates/emails/rejected.html` — отправляется при reject. Содержит reason (если был) и контакт для апелляции (email админа из `.env`).

Стилистика та же, что у `verify.html` (кремовый фон, бронзовый CTA).

---

## 7. Изменения в Verification criteria (правка §12 базового spec)

К существующему списку добавляем:

- [ ] После регистрации + email-verify кабинет показывает «На рассмотрении», нет кнопок ключей
- [ ] CLI `promote-admin --email ...` делает указанного user'a админом
- [ ] Админ видит pending users на `/cabinet/admin/pending`
- [ ] Approve → user получает email + при логине видит полный кабинет
- [ ] Reject → user получает email + при логине видит «Доступ отклонён»
- [ ] Без `is_admin=true` `/cabinet/admin/pending` возвращает 403
- [ ] Список серверов на лендинге обновляется когда добавляешь/удаляешь ноду в panel (с учётом 30-сек кэша)
- [ ] Список серверов в кабинете отображает обе ноды как online
- [ ] Кнопки v2RayTun / Hiddify / NekoBox формируют корректные deep-link с URL-encoded subscription URL

---

## 8. Open questions (для следующих фаз)

| # | Вопрос | Когда решать |
|---|---|---|
| 1 | Latency-метрики нод (показывать на лендинге?) | После запуска, когда будут реальные клиенты |
| 2 | Email-уведомление админу при новой регистрации — пользователь отклонил (вариант B), но может передумать когда поток вырастет | После первых 10–20 регистраций |
| 3 | Auto-approve trusted-domain emails (например, корпоративный домен) | Когда появятся стейкхолдеры с конкретной потребностью |
| 4 | Платежи (вне MVP, из базового spec) | После семейного теста |

---

## 9. Approval

Утверждено пользователем (Никита Олегович) на этапе brainstorming 2026-05-23:

- Дельта vs базовый spec — три новых блока + обновление доменов: одобрено («найди и делай»).
- Admin notification механизм — выбран вариант **B** (без уведомлений, админ периодически открывает `/cabinet/admin/pending`).

Следующий шаг — invoke skill `superpowers:writing-plans` для пошагового implementation plan.
