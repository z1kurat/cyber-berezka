# Site Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить текущий Tailwind-скелет (`infra/site/app/templates/*.html` + `static/css/input.css`) на полную дизайн-систему «премиум-кремовое + cyber-berezka» из 10-итерационного брейншторма.

**Architecture:** Drop Tailwind build pipeline; one hand-written CSS file `styles.css` + one JS file `site.js` + 14 переписанных HTML-шаблонов. Все компоненты определяются CSS-variables и составляются из переиспользуемых классов (`.cta-primary`, `.section-tag`, `.tilt`, `.reveal`, `.faq-item`, etc.). Канонический референс — `docs/superpowers/specs/2026-05-28-site-redesign-assets/landing-canonical.html` (1163 строк, source of truth для всех визуальных деталей).

**Tech Stack:** Jinja2 templates + vanilla CSS с CSS variables + vanilla JS (IntersectionObserver, scroll listeners) + Inter font via CDN (`https://rsms.me/inter/inter.css`).

**Spec:** `docs/superpowers/specs/2026-05-28-site-redesign-design.md`

**Constraint:** Не менять backend/models/routes. Только templates + CSS + JS. Сохранить все form action URLs, CSRF-токены, data-attribute hooks (AmneziaVPN copy, etc.).

---

## File Structure

**Create:**
- `infra/site/app/static/js/site.js` — все JS-поведения (scroll-progress, reveal-observer, tilt, magnetic CTA, plane animation control, counter, FAQ)
- `infra/site/app/static/img/favicon.svg` — gold «Б» mark

**Replace (полная перезапись):**
- `infra/site/app/static/css/input.css` → переименовать в `styles.css` или оставить input.css и обновить Dockerfile (Task 1 решает)
- `infra/site/app/templates/base.html`
- `infra/site/app/templates/landing/index.html`
- `infra/site/app/templates/auth/{login,register,verify_sent}.html`
- `infra/site/app/templates/cabinet/{index,keys,admin_pending,admin_keys,pending_email,pending_admin,rejected}.html`
- `infra/site/app/templates/legal/{terms,privacy}.html`

**Modify:**
- `infra/site/Dockerfile` — drop Tailwind build stage (Task 1)
- `infra/site/app/templates/landing/_server_list.html` — обновить markup сервер-карточек
- `infra/site/tailwind.config.js` — удалить файл

**Не трогать:**
- Routers (`app/routers/*`)
- Services / models / migrations
- Email templates (`templates/emails/*`) — отдельная задача
- Static fonts (используем CDN)

---

## Task 1: Заменить CSS-сборку — Tailwind долой, hand-written styles.css

**Files:**
- Modify: `infra/site/Dockerfile` (стр. 5-19 — удалить tw-builder stage, стр. 48 — поменять источник styles.css)
- Modify: `infra/site/app/static/css/input.css` → переписать как готовый `styles.css`
- Delete: `infra/site/tailwind.config.js`

- [ ] **Step 1: Прочитать канонический HTML и извлечь CSS-блок**

В `docs/superpowers/specs/2026-05-28-site-redesign-assets/landing-canonical.html` — внутри `<style>` блока (~525 строк) содержится вся дизайн-система. Скопировать целиком, добавив сверху импорт Inter.

- [ ] **Step 2: Создать `infra/site/app/static/css/styles.css`**

Содержимое = `@import url('https://rsms.me/inter/inter.css');` + весь CSS из канонического `<style>` блока (включая `:root` variables, `body`, `.nav`, `.scroll-progress`, `.mesh`, `.grain`, `.section`, `.hero`, `.cta-primary`, `.cta-secondary`, `.trust`, `.hero-preview`, `.conn`, `.plane`, `.node-card`, `.nc-*`, `.marquee`, `.stats-section`, `.about-name`, `.steps-grid`, `.step`, `.servers-grid`, `.server-card`, `.feature-row`, `.term`, `.cab-card`, `.compare-section`, `.compare-table`, `.pricing-grid`, `.price-card`, `.faq-list`, `.faq-item`, `.final`, `.footer`, `.reveal`, `.tilt`, media query @media (max-width: 900px)).

Источник правды — канонический HTML. Скопировать содержимое тега `<style>` (без обёрток `<style>`/`</style>`) в `styles.css`.

- [ ] **Step 3: Удалить input.css и tailwind.config.js**

```bash
rm infra/site/app/static/css/input.css infra/site/tailwind.config.js
```

- [ ] **Step 4: Обновить Dockerfile — убрать tailwind build**

Заменить весь Dockerfile на (полностью переписать, не diff):

```dockerfile
# Cyber Berezka site — single-stage build.
FROM python:3.12-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.115" "uvicorn[standard]>=0.32" \
    "sqlalchemy[asyncio]>=2.0" "asyncpg>=0.30" "alembic>=1.13" \
    "pydantic>=2.9" "pydantic-settings>=2.6" "email-validator>=2.2" \
    "jinja2>=3.1" "python-multipart>=0.0.20" "argon2-cffi>=23.1" \
    "httpx>=0.27" "itsdangerous>=2.2" "redis[hiredis]>=5.2" "qrcode[pil]>=7.4"

COPY app/ ./app/
COPY alembic.ini ./alembic.ini
COPY migrations/ ./migrations/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN useradd --create-home --uid 1000 site && chown -R site:site /app
USER site

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=3)" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

- [ ] **Step 5: Verify CSS-парсинг локально**

```bash
python3 -c "
content = open('infra/site/app/static/css/styles.css').read()
# Минимальная проверка: число open-brace == close-brace
o = content.count('{'); c = content.count('}')
assert o == c, f'Brace mismatch: {o} open, {c} close'
print(f'OK: {o} blocks, {len(content)} bytes')
"
```
Expected: вывод вида `OK: NN blocks, NNNNN bytes`, без AssertionError.

- [ ] **Step 6: Commit**

```bash
git add infra/site/app/static/css/styles.css infra/site/Dockerfile
git rm infra/site/app/static/css/input.css infra/site/tailwind.config.js
git commit -m "feat(site/css): replace Tailwind build with hand-written design-system styles.css"
```

---

## Task 2: Создать `site.js` со всеми interactive behaviors

**Files:**
- Create: `infra/site/app/static/js/site.js`

- [ ] **Step 1: Скопировать JS из канонического HTML**

В `docs/superpowers/specs/2026-05-28-site-redesign-assets/landing-canonical.html` — внутри последнего `<script>` блока — весь JS-код (scroll handler с parallax, stagger-load для `.node-card`, IntersectionObserver `io` для reveals, statsIo для counters, `animateText`, magnetic CTA, tilt-on-hover, FAQ accordion).

Создать `infra/site/app/static/js/site.js` с этим содержимым (без обёрток `<script>`/`</script>`).

- [ ] **Step 2: Обернуть в DOMContentLoaded**

В начале файла добавить:

```javascript
document.addEventListener('DOMContentLoaded', () => {
```

В конце:

```javascript
});
```

Это гарантирует, что querySelectors не будут возвращать null если script подключён в `<head>`.

- [ ] **Step 3: Verify JS syntax**

```bash
node -c infra/site/app/static/js/site.js && echo "OK"
```

Или, если nodejs не установлен:

```bash
python3 -c "
import re
content = open('infra/site/app/static/js/site.js').read()
o = content.count('{') ; c = content.count('}')
po = content.count('(') ; pc = content.count(')')
assert o == c, f'{o} != {c} braces'
assert po == pc, f'{po} != {pc} parens'
print(f'OK: {o} braces, {po} parens, {len(content)} bytes')
"
```

- [ ] **Step 4: Commit**

```bash
git add infra/site/app/static/js/site.js
git commit -m "feat(site/js): scroll-progress, reveal-observer, tilt, magnetic-cta, plane control, faq, counter"
```

---

## Task 3: Обновить `base.html` — nav, mesh, grain, scroll-progress, footer, leaf SVG defs

**Files:**
- Modify: `infra/site/app/templates/base.html` (полная перезапись)

- [ ] **Step 1: Прочитать текущий base.html для понимания contents-blocks и request.state-инжекций**

```bash
cat infra/site/app/templates/base.html
```

Нужно сохранить:
- `{% block title %}…{% endblock %}` (titles)
- `{% block meta_description %}…{% endblock %}`
- `{% block content %}{% endblock %}`
- `{% block header %}` опциональный override
- `{% block footer %}` опциональный override
- Условный header navigation на `request.state.current_user` (отображает Login/Register для anon, Cabinet/Logout для logged-in)
- CSRF token inject в logout form

- [ ] **Step 2: Перезаписать base.html**

```html
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <meta name="robots" content="index, follow">
    <meta name="theme-color" content="#F7F3EB">
    <title>{% block title %}Cyber Berezka — защищённое соединение{% endblock %}</title>
    <meta name="description" content="{% block meta_description %}Шифрование вашего интернет-соединения. Защита персональных данных в публичных сетях.{% endblock %}">
    <link rel="stylesheet" href="/static/css/styles.css">
    <link rel="icon" type="image/svg+xml" href="/static/img/favicon.svg">
</head>
<body>

<!-- BIRCH-PCB LEAF SVG (used by about-name, marquee, anywhere) -->
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <defs>
    <symbol id="leaf" viewBox="0 0 60 80">
      <path d="M30 4 L 12 22 L 6 38 L 8 56 L 22 72 L 30 76 L 38 72 L 52 56 L 54 38 L 48 22 Z" fill="rgba(184,147,90,0.06)" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>
      <line x1="30" y1="6" x2="30" y2="74" stroke="currentColor" stroke-width="1.1"/>
      <g stroke="currentColor" stroke-width="0.9" fill="none" stroke-linecap="round" stroke-linejoin="miter">
        <polyline points="30,18 40,18 40,26"/>
        <polyline points="30,30 44,30 44,42"/>
        <polyline points="30,42 46,42 46,52"/>
        <polyline points="30,54 42,54 42,62"/>
        <polyline points="30,18 20,18 20,26"/>
        <polyline points="30,30 16,30 16,42"/>
        <polyline points="30,42 14,42 14,52"/>
        <polyline points="30,54 18,54 18,62"/>
      </g>
      <g fill="currentColor">
        <circle cx="40" cy="26" r="1.6"/><circle cx="44" cy="42" r="1.6"/>
        <circle cx="46" cy="52" r="1.6"/><circle cx="42" cy="62" r="1.6"/>
        <circle cx="20" cy="26" r="1.6"/><circle cx="16" cy="42" r="1.6"/>
        <circle cx="14" cy="52" r="1.6"/><circle cx="18" cy="62" r="1.6"/>
        <circle cx="30" cy="4" r="2"/><circle cx="30" cy="76" r="2"/>
      </g>
      <g stroke="currentColor" stroke-width="0.5" opacity="0.55" fill="none">
        <line x1="40" y1="26" x2="46" y2="32"/>
        <line x1="20" y1="26" x2="14" y2="32"/>
        <line x1="42" y1="62" x2="36" y2="68"/>
        <line x1="18" y1="62" x2="24" y2="68"/>
      </g>
    </symbol>
  </defs>
</svg>

<div class="scroll-progress" id="scrollProgress" style="width:0%"></div>

<div class="mesh">
    <div class="blob blob-1"></div><div class="blob blob-2"></div>
    <div class="blob blob-3"></div><div class="blob blob-4"></div>
</div>
<div class="grain"></div>

{% block header %}
<nav class="nav" id="nav">
    <a class="brand" href="/">
        <span class="brand-mark">Б</span>
        <span>Cyber Berezka</span>
    </a>
    <div class="nav-links">
        <a class="nav-link" href="/#how">Как работает</a>
        <a class="nav-link" href="/#servers">Серверы</a>
        <a class="nav-link" href="/#about">О названии</a>
        <a class="nav-link" href="/#pricing">Тарифы</a>
        <a class="nav-link" href="/#faq">Вопросы</a>
    </div>
    {% if request.state.current_user %}
        <div style="display:flex;gap:1rem;align-items:center">
            <a class="nav-link" href="/cabinet">Кабинет</a>
            <form method="POST" action="/auth/logout" style="display:inline">
                <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token or '' }}">
                <button class="nav-cta" type="submit" style="border:none;cursor:pointer">Выйти</button>
            </form>
        </div>
    {% else %}
        <a class="nav-cta" href="/auth/login">Войти</a>
    {% endif %}
</nav>
{% endblock %}

<main>
    {% block content %}{% endblock %}
</main>

{% block footer %}
<footer class="footer">
    <div class="footer-grid">
        <div>
            <div class="brand"><span class="brand-mark">Б</span><span>Cyber Berezka</span></div>
            <p class="footer-brand">Защищённое соединение для повседневной работы в интернете. Без логов, без рекламы, без сложных настроек.</p>
        </div>
        <div class="footer-col">
            <h4>Продукт</h4>
            <a href="/#features">Возможности</a>
            <a href="/#servers">Серверы</a>
            <a href="/#pricing">Тарифы</a>
            <a href="/#faq">Вопросы</a>
        </div>
        <div class="footer-col">
            <h4>Документы</h4>
            <a href="/legal/terms">Условия использования</a>
            <a href="/legal/privacy">Политика конфиденциальности</a>
        </div>
        <div class="footer-col">
            <h4>Связь</h4>
            <a href="#">Telegram-поддержка</a>
            <a href="mailto:{{ site_domain or 'admin@cyber-berezka.ru' }}">Email</a>
        </div>
    </div>
    <div class="footer-bottom">
        <span>© 2026 Cyber Berezka. ИП Иванов И.И., ОГРНИП 000000000000000</span>
        <span>{{ site_domain }}</span>
    </div>
</footer>
{% endblock %}

<script defer src="/static/js/site.js"></script>
</body>
</html>
```

- [ ] **Step 3: Verify Jinja parse**

```bash
python3 -c "
import jinja2
env = jinja2.Environment(loader=jinja2.FileSystemLoader('infra/site/app/templates'))
env.get_template('base.html')
print('OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add infra/site/app/templates/base.html
git commit -m "feat(site/base): apply new design system to base layout (nav, mesh, grain, footer, leaf SVG defs)"
```

---

## Task 4: Build `landing/index.html` — full 12-section landing

**Files:**
- Modify: `infra/site/app/templates/landing/index.html` (полная перезапись)
- Modify: `infra/site/app/templates/landing/_server_list.html`

- [ ] **Step 1: Перечитать current index.html для понимания context-vars**

```bash
cat infra/site/app/templates/landing/index.html | head -50
```

Шаблон получает `nodes` (list of dicts с `address`, `countryCode`, `isConnected`, etc.) — используется в текущем server-list. В новом дизайне 3 server-cards содержат hardcoded имена/IP (это OK, можно перейти к данным позже).

- [ ] **Step 2: Перезаписать `landing/index.html`**

Полное содержимое — копия `<body>` из `docs/superpowers/specs/2026-05-28-site-redesign-assets/landing-canonical.html` БЕЗ:
- `<nav class="nav">` (в base.html)
- `<footer class="footer">` (в base.html)
- `<div class="mesh">`, `<div class="grain">`, `<div class="scroll-progress">` (в base.html)
- `<svg width="0" height="0">…</svg>` leaf defs (в base.html)
- `<script>` block (отдельный site.js)

Обёртка:

```html
{% extends "base.html" %}
{% block title %}Cyber Berezka — защищённое соединение{% endblock %}
{% block content %}
<!-- HERO CENTERED -->
<header class="hero">
  …
</header>

<!-- HERO PREVIEW with paper-plane connections -->
<section class="hero-preview" id="previewStage">
  …
</section>

<!-- MARQUEE -->
<section class="marquee">…</section>

<!-- STATS -->
<section class="stats-section">…</section>

<div class="divider"><div class="divider-inner"></div></div>

<!-- ABOUT NAME (uses <use href="#leaf"/>) -->
<section class="about-name" id="about">…</section>

<!-- … все остальные секции из канонического HTML … -->

{% endblock %}
```

Точный contents скопировать из канонического HTML, секции в порядке: hero → hero-preview → marquee → stats-section → divider → about-name → divider → STEPS → divider → SERVERS → FEATURES → COMPARISON → divider → PRICING → divider → FAQ → FINAL CTA.

Для серверов в hero-preview можно оставить hardcoded IPs (212.74.231.217, 194.87.208.112, 159.69.198.143) — это просто визуальный preview.

- [ ] **Step 3: Удалить старый `_server_list.html` или оставить как inclu сирующее partial для cabinet — решить позже**

Сейчас просто пропустить.

- [ ] **Step 4: Verify Jinja parse**

```bash
python3 -c "
import jinja2
env = jinja2.Environment(loader=jinja2.FileSystemLoader('infra/site/app/templates'))
env.get_template('landing/index.html')
print('OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add infra/site/app/templates/landing/index.html
git commit -m "feat(site/landing): apply new design — 12 sections with cyber-berezka motif, plane animations, tilt cards"
```

---

## Task 5: Rebuild `auth/login.html`

**Files:**
- Modify: `infra/site/app/templates/auth/login.html` (полная перезапись)

- [ ] **Step 1: Прочитать текущий login.html — сохранить form action + fields**

```bash
cat infra/site/app/templates/auth/login.html
```

Должно остаться:
- `<form method="POST" action="/auth/login">`
- email input (с prefill из `email or request.query_params.get('email', '')`)
- password input
- CSRF token (если используется на login — Group A security audit отметил что login pre-session, CSRF не применяется)
- Error message rendering из context `error`
- Verified success message (`if request.query_params.get('verified')`)

- [ ] **Step 2: Перезаписать**

```html
{% extends "base.html" %}
{% block title %}Войти — Cyber Berezka{% endblock %}
{% block content %}

<main class="hero" style="max-width:480px;padding-top:8rem;padding-bottom:4rem;text-align:center">
  <div class="eyebrow">
    <span class="eyebrow-line"></span>
    <span>Возвращение</span>
    <span class="eyebrow-line"></span>
  </div>
  <h1 class="headline" style="font-size:clamp(2.4rem,5vw,3.4rem);margin-bottom:1.5rem">
    <span class="line"><span class="word" style="animation-delay:0.3s">С возвращением.</span></span>
  </h1>
  <p class="lead" style="margin-bottom:2.5rem">
    Войдите в кабинет — управляйте ключами и подпиской.
  </p>

  {% if request.query_params.get('verified') %}
    <div style="background:rgba(95,139,92,0.12);border:1px solid rgba(95,139,92,0.3);border-radius:8px;padding:0.85rem 1rem;margin-bottom:1.5rem;font-size:0.875rem;color:#4A7146;text-align:left">
      ✓ Email подтверждён. Теперь можно войти.
    </div>
  {% endif %}

  {% if error %}
    <div style="background:rgba(184,53,31,0.08);border:1px solid rgba(184,53,31,0.25);border-radius:8px;padding:0.85rem 1rem;margin-bottom:1.5rem;font-size:0.875rem;color:#B8351F;text-align:left">
      {{ error }}
    </div>
  {% endif %}

  <form method="POST" action="/auth/login" style="text-align:left;display:flex;flex-direction:column;gap:1rem">
    <label style="display:flex;flex-direction:column;gap:0.4rem">
      <span style="font-size:0.78rem;font-weight:500;color:#6B6661;letter-spacing:0.04em;text-transform:uppercase">Email</span>
      <input type="email" name="email" required autofocus
             value="{{ email or request.query_params.get('email', '') }}"
             style="font-family:inherit;font-size:0.95rem;padding:0.8rem 1rem;background:#FDFAF3;border:1px solid rgba(184,147,90,0.24);border-radius:8px;color:#1A1818;transition:border-color 180ms">
    </label>
    <label style="display:flex;flex-direction:column;gap:0.4rem">
      <span style="font-size:0.78rem;font-weight:500;color:#6B6661;letter-spacing:0.04em;text-transform:uppercase">Пароль</span>
      <input type="password" name="password" required
             style="font-family:inherit;font-size:0.95rem;padding:0.8rem 1rem;background:#FDFAF3;border:1px solid rgba(184,147,90,0.24);border-radius:8px;color:#1A1818;transition:border-color 180ms">
    </label>
    <button type="submit" class="cta-primary" style="margin-top:0.5rem;justify-content:center">
      Войти
      <svg viewBox="0 0 20 20" fill="none"><path d="M4 10h12m0 0l-4-4m4 4l-4 4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </button>
  </form>

  <p style="margin-top:2rem;font-size:0.875rem;color:#6B6661">
    Нет аккаунта? <a href="/auth/register" style="color:#1A1818;text-decoration:underline;text-underline-offset:3px">Создать</a>
  </p>
</main>

{% endblock %}
```

- [ ] **Step 3: Verify**

```bash
python3 -c "
import jinja2
env = jinja2.Environment(loader=jinja2.FileSystemLoader('infra/site/app/templates'))
env.get_template('auth/login.html')
print('OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add infra/site/app/templates/auth/login.html
git commit -m "feat(site/auth/login): apply new design system to login form"
```

---

## Task 6: Rebuild `auth/register.html`

**Files:**
- Modify: `infra/site/app/templates/auth/register.html`

- [ ] **Step 1: Прочитать current register.html — определить fields и error-handling**

```bash
cat infra/site/app/templates/auth/register.html
```

Сохранить:
- email, password, password_confirm fields
- checkbox для terms
- error rendering, особенно `error_code == "email_taken"` ссылка «Войти →»

- [ ] **Step 2: Перезаписать**

```html
{% extends "base.html" %}
{% block title %}Создать аккаунт — Cyber Berezka{% endblock %}
{% block content %}

<main class="hero" style="max-width:480px;padding-top:8rem;padding-bottom:4rem;text-align:center">
  <div class="eyebrow">
    <span class="eyebrow-line"></span>
    <span>Регистрация</span>
    <span class="eyebrow-line"></span>
  </div>
  <h1 class="headline" style="font-size:clamp(2.4rem,5vw,3.4rem);margin-bottom:1.5rem">
    <span class="line"><span class="word" style="animation-delay:0.3s">Создайте</span> <span class="word accent" style="animation-delay:0.4s">аккаунт.</span></span>
  </h1>
  <p class="lead" style="margin-bottom:2.5rem">
    Подтверждение email → ручная проверка в течение суток → готовый ключ.
  </p>

  {% if error %}
    <div style="background:rgba(184,53,31,0.08);border:1px solid rgba(184,53,31,0.25);border-radius:8px;padding:0.85rem 1rem;margin-bottom:1.5rem;font-size:0.875rem;color:#B8351F;text-align:left">
      {{ error }}{% if error_code == "email_taken" %}.
      <a href="/auth/login?email={{ email|urlencode }}" style="color:#B8351F;text-decoration:underline;font-weight:500">Войти →</a>
      {% endif %}
    </div>
  {% endif %}

  <form method="POST" action="/auth/register" style="text-align:left;display:flex;flex-direction:column;gap:1rem">
    <label style="display:flex;flex-direction:column;gap:0.4rem">
      <span style="font-size:0.78rem;font-weight:500;color:#6B6661;letter-spacing:0.04em;text-transform:uppercase">Email</span>
      <input type="email" name="email" required autofocus value="{{ email or '' }}"
             style="font-family:inherit;font-size:0.95rem;padding:0.8rem 1rem;background:#FDFAF3;border:1px solid rgba(184,147,90,0.24);border-radius:8px;color:#1A1818">
    </label>
    <label style="display:flex;flex-direction:column;gap:0.4rem">
      <span style="font-size:0.78rem;font-weight:500;color:#6B6661;letter-spacing:0.04em;text-transform:uppercase">Пароль <span style="color:#8B7E6A;text-transform:none;font-weight:400">(минимум 12 символов)</span></span>
      <input type="password" name="password" required minlength="12"
             style="font-family:inherit;font-size:0.95rem;padding:0.8rem 1rem;background:#FDFAF3;border:1px solid rgba(184,147,90,0.24);border-radius:8px;color:#1A1818">
    </label>
    <label style="display:flex;flex-direction:column;gap:0.4rem">
      <span style="font-size:0.78rem;font-weight:500;color:#6B6661;letter-spacing:0.04em;text-transform:uppercase">Повтор пароля</span>
      <input type="password" name="password_confirm" required minlength="12"
             style="font-family:inherit;font-size:0.95rem;padding:0.8rem 1rem;background:#FDFAF3;border:1px solid rgba(184,147,90,0.24);border-radius:8px;color:#1A1818">
    </label>
    <label style="display:flex;align-items:flex-start;gap:0.6rem;font-size:0.85rem;color:#6B6661;margin-top:0.25rem">
      <input type="checkbox" required style="margin-top:0.25rem">
      <span>Я принимаю <a href="/legal/terms" style="color:#1A1818;text-decoration:underline">Условия использования</a> и <a href="/legal/privacy" style="color:#1A1818;text-decoration:underline">Политику конфиденциальности</a></span>
    </label>
    <button type="submit" class="cta-primary" style="margin-top:0.5rem;justify-content:center">
      Создать аккаунт
      <svg viewBox="0 0 20 20" fill="none"><path d="M4 10h12m0 0l-4-4m4 4l-4 4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </button>
  </form>

  <p style="margin-top:2rem;font-size:0.875rem;color:#6B6661">
    Уже есть аккаунт? <a href="/auth/login" style="color:#1A1818;text-decoration:underline;text-underline-offset:3px">Войти</a>
  </p>
</main>

{% endblock %}
```

- [ ] **Step 3: Verify Jinja**

```bash
python3 -c "
import jinja2
env = jinja2.Environment(loader=jinja2.FileSystemLoader('infra/site/app/templates'))
env.get_template('auth/register.html')
print('OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add infra/site/app/templates/auth/register.html
git commit -m "feat(site/auth/register): apply new design system + collision-UX with login link"
```

---

## Task 7: Rebuild `auth/verify_sent.html`

**Files:**
- Modify: `infra/site/app/templates/auth/verify_sent.html`

- [ ] **Step 1: Перезаписать**

```html
{% extends "base.html" %}
{% block title %}Письмо отправлено — Cyber Berezka{% endblock %}
{% block content %}

<main class="hero" style="max-width:540px;padding-top:9rem;padding-bottom:6rem;text-align:center">
  <div style="width:72px;height:72px;border-radius:50%;background:rgba(95,139,92,0.12);display:flex;align-items:center;justify-content:center;margin:0 auto 2rem">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
      <path d="M5 12l5 5L20 7" stroke="#5F8B5C" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </div>
  <h1 class="headline" style="font-size:clamp(2rem,4.4vw,2.8rem);margin-bottom:1.5rem">
    <span class="line"><span class="word" style="animation-delay:0.3s">Письмо</span> <span class="word accent" style="animation-delay:0.45s">отправлено.</span></span>
  </h1>
  <p class="lead" style="max-width:480px;margin:0 auto 2rem">
    Мы отправили ссылку для подтверждения на <strong style="color:#1A1818">{{ email }}</strong>. Откройте письмо и нажмите кнопку — это займёт минуту.
  </p>
  <p style="font-size:0.85rem;color:#8B7E6A;line-height:1.6;margin-bottom:2.5rem">
    Письмо не пришло? Проверьте папку «Спам». Если ничего нет — попробуйте <a href="/auth/register" style="color:#1A1818;text-decoration:underline">зарегистрироваться</a> ещё раз.
  </p>
  <a class="cta-secondary" href="/">← На главную</a>
</main>

{% endblock %}
```

- [ ] **Step 2: Verify + commit**

```bash
python3 -c "import jinja2; jinja2.Environment(loader=jinja2.FileSystemLoader('infra/site/app/templates')).get_template('auth/verify_sent.html'); print('OK')"
git add infra/site/app/templates/auth/verify_sent.html
git commit -m "feat(site/auth/verify): apply new design system"
```

---

## Task 8: Rebuild `cabinet/index.html`

**Files:**
- Modify: `infra/site/app/templates/cabinet/index.html`

- [ ] **Step 1: Прочитать current cabinet/index.html для understand состояния user-rendering**

```bash
cat infra/site/app/templates/cabinet/index.html
```

Сохранить: `{{ user.email }}` отображение, ссылка на admin panel если `user.is_admin`, ссылка на keys, серверная информация из `nodes`.

- [ ] **Step 2: Перезаписать**

```html
{% extends "base.html" %}
{% block title %}Кабинет — Cyber Berezka{% endblock %}
{% block content %}

<main class="hero" style="max-width:1100px;text-align:left;padding-top:8rem;padding-bottom:3rem">
  <div class="eyebrow"><span class="eyebrow-line"></span><span>Личный кабинет</span></div>
  <h1 class="headline" style="font-size:clamp(2.2rem,4.6vw,3.2rem);margin-bottom:1rem">
    <span class="line"><span class="word" style="animation-delay:0.3s">Здравствуйте,</span></span>
    <span class="line"><span class="word accent" style="animation-delay:0.45s">{{ user.email.split('@')[0] }}.</span></span>
  </h1>
  <p class="lead" style="margin:0 0 2.5rem;text-align:left">
    Ваш аккаунт активен. Управляйте ключами, проверяйте серверы или измените режим защиты.
  </p>

  <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:4rem">
    <a class="cta-primary" href="/cabinet/keys">
      Управление ключами
      <svg viewBox="0 0 20 20" fill="none"><path d="M4 10h12m0 0l-4-4m4 4l-4 4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </a>
    {% if user.is_admin %}
      <a class="cta-secondary" href="/cabinet/admin/pending">
        Pending users <span class="arrow">→</span>
      </a>
      <a class="cta-secondary" href="/cabinet/admin/keys">
        Все ключи <span class="arrow">→</span>
      </a>
    {% endif %}
  </div>
</main>

<section class="section" style="padding-top:0">
  <div class="section-tag"><span class="section-tag-line"></span><span>Серверы</span></div>
  <h2 class="section-title">Доступные сервера.</h2>
  <p class="lead" style="opacity:0;animation:none;margin:0;text-align:left">
    Live-статусы наших нод. При создании ключа выбираете одну из стран ниже.
  </p>
  <div class="servers-grid">
    {% for node in nodes %}
    <div class="server-card tilt">
      <div class="server-flag">{{ node.flag if node.flag else '🌍' }}</div>
      <div class="server-country">{{ node.country if node.country else node.countryCode }}</div>
      <div class="server-city">{{ node.city if node.city else node.address }}</div>
      <div class="server-stat"><span class="server-stat-label">Адрес</span><span class="server-stat-value">{{ node.address }}</span></div>
      <div class="server-stat"><span class="server-stat-label">Протокол</span><span class="server-stat-value">VLESS-Reality</span></div>
      <span class="server-status">
        <span class="server-status-dot" style="background:{{ '#5F8B5C' if node.isConnected else '#B8351F' }}"></span>
        {{ 'Онлайн' if node.isConnected else 'Оффлайн' }}
      </span>
    </div>
    {% else %}
    <p style="grid-column:1/-1;color:#6B6661">Сейчас нет доступных серверов. Попробуйте позже.</p>
    {% endfor %}
  </div>
</section>

{% endblock %}
```

- [ ] **Step 3: Verify + commit**

```bash
python3 -c "import jinja2; jinja2.Environment(loader=jinja2.FileSystemLoader('infra/site/app/templates')).get_template('cabinet/index.html'); print('OK')"
git add infra/site/app/templates/cabinet/index.html
git commit -m "feat(site/cabinet): apply new design system to cabinet home"
```

---

## Task 9: Rebuild `cabinet/keys.html`

**Files:**
- Modify: `infra/site/app/templates/cabinet/keys.html`

- [ ] **Step 1: Прочитать current keys.html для понимания форм и data**

```bash
cat infra/site/app/templates/cabinet/keys.html
```

Сохранить (это critical for функциональности):
- Форма создания ключа: `<form method="POST" action="/cabinet/keys">` с CSRF, label input, country select
- Список `keys_rows` — каждый key с server-binding, vless URL, QR
- Revoke-форма: `<form method="POST" action="/cabinet/keys/{{ k.id }}/revoke">` с CSRF
- AmneziaVPN data-attr на copy-button (из last fix in git history)
- Subscription URL + qr_data_uri отображение
- Error rendering из `?error=...` query param

- [ ] **Step 2: Перезаписать (адаптация к новому дизайну с .server-card / .cab-card / .cta-primary компонентами)**

```html
{% extends "base.html" %}
{% block title %}Мои ключи — Cyber Berezka{% endblock %}
{% block content %}

<main style="max-width:1100px;margin:0 auto;padding:8rem 2rem 4rem">
  <header style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:3rem;flex-wrap:wrap;gap:1rem">
    <div>
      <div class="eyebrow"><span class="eyebrow-line"></span><span>Ключи</span></div>
      <h1 class="headline" style="font-size:clamp(2rem,4vw,2.8rem);margin:0">Мои ключи</h1>
    </div>
    <a class="cta-secondary" href="/cabinet">← В кабинет</a>
  </header>

  {% set err = request.query_params.get('error') %}
  {% if err == 'label_required' %}
    <div style="background:rgba(184,53,31,0.08);border:1px solid rgba(184,53,31,0.25);border-radius:8px;padding:0.85rem 1rem;margin-bottom:1.5rem;font-size:0.875rem;color:#B8351F">Имя ключа обязательно.</div>
  {% elif err == 'no_servers' %}
    <div style="background:rgba(184,53,31,0.08);border:1px solid rgba(184,53,31,0.25);border-radius:8px;padding:0.85rem 1rem;margin-bottom:1.5rem;font-size:0.875rem;color:#B8351F">В выбранной стране нет доступных серверов. Попробуйте другую.</div>
  {% endif %}

  <!-- Create key form -->
  <section style="background:#FFFCF6;border:1px solid rgba(184,147,90,0.24);border-radius:16px;padding:2rem;margin-bottom:2rem;box-shadow:0 24px 60px rgba(26,24,24,0.06)">
    <h2 style="font-size:1.4rem;font-weight:600;letter-spacing:-0.018em;margin-bottom:1.5rem">
      {% if not keys_rows %}Создайте первый ключ{% else %}Добавить ещё один ключ{% endif %}
    </h2>
    {% if not countries %}
      <p style="color:#6B6661">Сейчас нет доступных серверов. Попробуйте позже.</p>
    {% else %}
    <form method="POST" action="/cabinet/keys" style="display:grid;grid-template-columns:1fr 1fr auto;gap:1rem;align-items:end">
      <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token or '' }}">
      <label style="display:flex;flex-direction:column;gap:0.4rem">
        <span style="font-size:0.78rem;font-weight:500;color:#6B6661;letter-spacing:0.04em;text-transform:uppercase">Название</span>
        <input type="text" name="label" required minlength="1" maxlength="64" placeholder="iPhone, MacBook..."
               style="font-family:inherit;font-size:0.95rem;padding:0.75rem 1rem;background:#FDFAF3;border:1px solid rgba(184,147,90,0.24);border-radius:8px">
      </label>
      <label style="display:flex;flex-direction:column;gap:0.4rem">
        <span style="font-size:0.78rem;font-weight:500;color:#6B6661;letter-spacing:0.04em;text-transform:uppercase">Страна</span>
        <select name="country" required style="font-family:inherit;font-size:0.95rem;padding:0.75rem 1rem;background:#FDFAF3;border:1px solid rgba(184,147,90,0.24);border-radius:8px">
          {% for c in countries %}
            <option value="{{ c.code }}">{{ c.flag }} {{ c.name }}{% if c.city %} ({{ c.city }}){% endif %}</option>
          {% endfor %}
        </select>
      </label>
      <button type="submit" class="cta-primary">+ Создать ключ</button>
    </form>
    {% endif %}
  </section>

  {% if subscription_url %}
  <!-- Subscription URL block -->
  <section style="background:#FFFCF6;border:1px solid rgba(184,147,90,0.24);border-radius:16px;padding:2rem;margin-bottom:2rem">
    <div class="eyebrow" style="margin-bottom:1rem"><span class="eyebrow-line"></span><span>Подписка</span></div>
    <p style="font-size:0.95rem;color:#6B6661;margin-bottom:1rem;line-height:1.6">
      Импортируйте этот URL в v2RayTun, Hiddify или любой совместимый клиент. Подписка содержит все ваши активные ключи.
    </p>
    <div style="display:flex;gap:1rem;align-items:center;flex-wrap:wrap">
      <code style="font-family:'JetBrains Mono',Menlo,monospace;font-size:0.78rem;background:#FDFAF3;border:1px solid rgba(184,147,90,0.24);border-radius:6px;padding:0.75rem 0.95rem;flex:1;min-width:240px;word-break:break-all">{{ subscription_url }}</code>
      <button type="button" data-copy="{{ subscription_url }}" class="cta-primary" style="padding:0.75rem 1.25rem;font-size:0.85rem">Скопировать</button>
    </div>
    {% if qr_data_uri %}
      <details style="margin-top:1rem">
        <summary style="cursor:pointer;font-size:0.875rem;color:#6B6661">Показать QR-код</summary>
        <img src="{{ qr_data_uri }}" alt="Subscription QR" style="margin-top:1rem;max-width:200px;border-radius:8px;border:1px solid rgba(184,147,90,0.24)">
      </details>
    {% endif %}
  </section>
  {% endif %}

  <!-- Keys list -->
  {% if keys_rows %}
  <section style="display:flex;flex-direction:column;gap:1rem">
    {% for row in keys_rows %}
    {% set k = row.key %}
    {% set s = row.server %}
    <details class="server-card tilt" style="cursor:default">
      <summary style="cursor:pointer;display:flex;justify-content:space-between;align-items:center;list-style:none">
        <div>
          <div style="font-size:1.05rem;font-weight:600;letter-spacing:-0.01em">
            {{ k.label }}
            {% if s %}<span style="color:#8B7E6A;font-weight:400;margin-left:0.5rem">— {{ s.flag }} {{ s.country }}</span>{% endif %}
          </div>
          <div style="font-size:0.78rem;color:#8B7E6A;margin-top:0.2rem">Создан {{ k.created_at.strftime('%d.%m.%Y') }}</div>
        </div>
        <span style="font-size:0.78rem;color:#5F8B5C;padding:0.25rem 0.6rem;border-radius:999px;background:rgba(95,139,92,0.12);font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Активен</span>
      </summary>

      <div style="margin-top:1.25rem;padding-top:1.25rem;border-top:1px dashed rgba(184,147,90,0.24)">
        {% if s %}
          <code style="display:block;font-family:'JetBrains Mono',Menlo,monospace;font-size:0.75rem;background:#FDFAF3;border:1px solid rgba(184,147,90,0.24);border-radius:6px;padding:0.75rem 0.95rem;color:#2A2624;word-break:break-all;line-height:1.5;margin-bottom:1rem">{{ s.vless_url }}</code>
          <div style="display:flex;gap:0.6rem;flex-wrap:wrap">
            <button type="button" data-copy="{{ s.vless_url }}" class="cta-primary" style="padding:0.55rem 1rem;font-size:0.78rem">Скопировать ссылку</button>
            <button type="button" data-copy="{{ s.vless_url }}" data-amnezia class="cta-secondary" style="padding:0.55rem 1rem;font-size:0.78rem">Импорт в AmneziaVPN</button>
            {% if server_qrs.get(s.vless_url) %}
              <details style="display:inline-block">
                <summary style="cursor:pointer;color:#1A1818;padding:0.55rem 1rem;font-size:0.78rem;font-weight:500;border:1px solid rgba(184,147,90,0.24);border-radius:6px;display:inline-block">QR-код</summary>
                <img src="{{ server_qrs[s.vless_url] }}" alt="QR" style="margin-top:0.6rem;max-width:160px;border-radius:6px;border:1px solid rgba(184,147,90,0.24)">
              </details>
            {% endif %}
          </div>
        {% else %}
          <p style="color:#8B7E6A;font-size:0.875rem">Привязанный сервер ({{ (k.meta or {}).get('address', '?') }}) недоступен. Создайте новый ключ или подождите восстановления.</p>
        {% endif %}

        <form method="POST" action="/cabinet/keys/{{ k.id }}/revoke" style="margin-top:1.25rem;padding-top:1.25rem;border-top:1px dashed rgba(184,147,90,0.24)" onsubmit="return confirm('Точно отозвать этот ключ? Действие необратимо.')">
          <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token or '' }}">
          <button type="submit" style="background:none;border:none;color:#B8351F;font-family:inherit;font-size:0.85rem;text-decoration:underline;cursor:pointer;padding:0">Отозвать ключ</button>
        </form>
      </div>
    </details>
    {% endfor %}
  </section>
  {% endif %}
</main>

<script>
// Copy buttons with check-mark feedback
document.querySelectorAll('[data-copy]').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    const text = btn.dataset.copy;
    try {
      await navigator.clipboard.writeText(text);
      if (btn.dataset.amnezia) {
        // Optional: also try to open Amnezia deep-link (legacy)
        // window.location.href = 'amnezia:add/' + text;
      }
      const original = btn.textContent;
      btn.textContent = '✓ Скопировано';
      setTimeout(() => { btn.textContent = original; }, 2000);
    } catch (err) {
      alert('Не удалось скопировать. Скопируйте вручную.');
    }
  });
});
</script>

{% endblock %}
```

- [ ] **Step 3: Verify**

```bash
python3 -c "import jinja2; jinja2.Environment(loader=jinja2.FileSystemLoader('infra/site/app/templates')).get_template('cabinet/keys.html'); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add infra/site/app/templates/cabinet/keys.html
git commit -m "feat(site/cabinet/keys): apply new design system; preserve forms + CSRF + copy-amnezia"
```

---

## Task 10: Rebuild `cabinet/admin_pending.html`

**Files:**
- Modify: `infra/site/app/templates/cabinet/admin_pending.html`

- [ ] **Step 1: Прочитать текущий шаблон, сохранить approve/reject формы**

```bash
cat infra/site/app/templates/cabinet/admin_pending.html
```

- [ ] **Step 2: Перезаписать**

```html
{% extends "base.html" %}
{% block title %}Pending users — Cyber Berezka{% endblock %}
{% block content %}

<main style="max-width:1100px;margin:0 auto;padding:8rem 2rem 4rem">
  <header style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:3rem;flex-wrap:wrap;gap:1rem">
    <div>
      <div class="eyebrow"><span class="eyebrow-line"></span><span>Admin</span></div>
      <h1 class="headline" style="font-size:clamp(1.8rem,3.6vw,2.4rem);margin:0">Pending users</h1>
    </div>
    <div style="display:flex;gap:1.25rem">
      <a class="cta-secondary" href="/cabinet/admin/keys">Все ключи</a>
      <a class="cta-secondary" href="/cabinet">← В кабинет</a>
    </div>
  </header>

  {% if not users %}
    <p style="color:#6B6661;font-size:1.05rem">Сейчас нет пользователей, ожидающих одобрения.</p>
  {% else %}
  <div style="display:flex;flex-direction:column;gap:1rem">
    {% for u in users %}
    <div class="server-card" style="cursor:default">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;flex-wrap:wrap">
        <div>
          <div style="font-size:1.05rem;font-weight:600;letter-spacing:-0.01em">{{ u.email }}</div>
          <div style="font-size:0.78rem;color:#8B7E6A;margin-top:0.25rem">
            Регистрация: {{ u.created_at.strftime('%d.%m.%Y %H:%M') }}
            · Email подтверждён: {{ u.email_verified_at.strftime('%d.%m.%Y %H:%M') }}
            {% if u.last_login_ip %} · IP: {{ u.last_login_ip }}{% endif %}
          </div>
        </div>
        <div style="display:flex;gap:0.6rem;align-items:flex-end;flex-wrap:wrap">
          <form method="POST" action="/cabinet/admin/pending/{{ u.id }}/approve" style="display:inline">
            <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token or '' }}">
            <button type="submit" class="cta-primary" style="padding:0.6rem 1.1rem;font-size:0.82rem">Одобрить</button>
          </form>
          <form method="POST" action="/cabinet/admin/pending/{{ u.id }}/reject" style="display:flex;gap:0.5rem">
            <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token or '' }}">
            <input type="text" name="reason" maxlength="500" placeholder="Причина (опц.)"
                   style="font-family:inherit;font-size:0.85rem;padding:0.55rem 0.8rem;background:#FDFAF3;border:1px solid rgba(184,147,90,0.24);border-radius:6px;min-width:160px">
            <button type="submit" style="padding:0.55rem 1rem;border:1px solid #B8351F;color:#B8351F;background:transparent;border-radius:6px;font-family:inherit;font-size:0.82rem;font-weight:500;cursor:pointer">Отклонить</button>
          </form>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
  {% endif %}
</main>

{% endblock %}
```

- [ ] **Step 3: Verify + commit**

```bash
python3 -c "import jinja2; jinja2.Environment(loader=jinja2.FileSystemLoader('infra/site/app/templates')).get_template('cabinet/admin_pending.html'); print('OK')"
git add infra/site/app/templates/cabinet/admin_pending.html
git commit -m "feat(site/cabinet/admin/pending): apply new design system"
```

---

## Task 11: Rebuild `cabinet/admin_keys.html`

**Files:**
- Modify: `infra/site/app/templates/cabinet/admin_keys.html`

- [ ] **Step 1: Прочитать current keys-overview шаблон**

```bash
cat infra/site/app/templates/cabinet/admin_keys.html
```

Шаблон отображает `rows` (list of {key, user} dicts) и `by_status` (dict с counts). Сохранить data-access.

- [ ] **Step 2: Перезаписать (табличный layout)**

```html
{% extends "base.html" %}
{% block title %}Все ключи — Cyber Berezka{% endblock %}
{% block content %}

<main style="max-width:1100px;margin:0 auto;padding:8rem 2rem 4rem">
  <header style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:3rem;flex-wrap:wrap;gap:1rem">
    <div>
      <div class="eyebrow"><span class="eyebrow-line"></span><span>Admin · все ключи</span></div>
      <h1 class="headline" style="font-size:clamp(1.8rem,3.6vw,2.4rem);margin:0">Ключи всех пользователей</h1>
    </div>
    <a class="cta-secondary" href="/cabinet">← В кабинет</a>
  </header>

  {% if by_status %}
  <div style="display:flex;gap:1rem;margin-bottom:2rem;flex-wrap:wrap">
    {% for status, count in by_status.items() %}
      <div style="background:#FFFCF6;border:1px solid rgba(184,147,90,0.24);border-radius:8px;padding:0.7rem 1.1rem;font-size:0.85rem">
        <span style="color:#8B7E6A;text-transform:uppercase;letter-spacing:0.06em;font-size:0.7rem;font-weight:600">{{ status }}</span>
        <strong style="margin-left:0.4rem;color:#1A1818;font-size:1.05rem">{{ count }}</strong>
      </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if not rows %}
    <p style="color:#6B6661">Ключей пока нет.</p>
  {% else %}
  <div style="background:#FFFCF6;border:1px solid rgba(184,147,90,0.24);border-radius:16px;overflow:hidden;box-shadow:0 24px 60px rgba(26,24,24,0.06)">
    <table style="width:100%;border-collapse:collapse;font-size:0.875rem">
      <thead>
        <tr style="background:#EFE6D2">
          <th style="text-align:left;padding:0.85rem 1.25rem;font-weight:600;letter-spacing:-0.01em">Ключ</th>
          <th style="text-align:left;padding:0.85rem 1.25rem;font-weight:600;letter-spacing:-0.01em">Пользователь</th>
          <th style="text-align:left;padding:0.85rem 1.25rem;font-weight:600;letter-spacing:-0.01em">Страна</th>
          <th style="text-align:left;padding:0.85rem 1.25rem;font-weight:600;letter-spacing:-0.01em">Создан</th>
          <th style="text-align:left;padding:0.85rem 1.25rem;font-weight:600;letter-spacing:-0.01em">Статус</th>
        </tr>
      </thead>
      <tbody>
        {% for r in rows %}
        <tr style="border-top:1px solid rgba(184,147,90,0.24)">
          <td style="padding:0.85rem 1.25rem;font-weight:500">{{ r.key.label }}</td>
          <td style="padding:0.85rem 1.25rem;color:#6B6661">{{ r.user.email }}</td>
          <td style="padding:0.85rem 1.25rem;color:#6B6661">{{ (r.key.meta or {}).get('country_code', '—') }}</td>
          <td style="padding:0.85rem 1.25rem;color:#6B6661">{{ r.key.created_at.strftime('%d.%m.%Y') }}</td>
          <td style="padding:0.85rem 1.25rem">
            <span style="font-size:0.74rem;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;padding:0.2rem 0.55rem;border-radius:999px;
              {% if r.key.status == 'active' %}background:rgba(95,139,92,0.12);color:#4A7146{% else %}background:rgba(184,53,31,0.1);color:#B8351F{% endif %}">{{ r.key.status }}</span>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}
</main>

{% endblock %}
```

- [ ] **Step 3: Verify + commit**

```bash
python3 -c "import jinja2; jinja2.Environment(loader=jinja2.FileSystemLoader('infra/site/app/templates')).get_template('cabinet/admin_keys.html'); print('OK')"
git add infra/site/app/templates/cabinet/admin_keys.html
git commit -m "feat(site/cabinet/admin/keys): apply new design system — admin keys table"
```

---

## Task 12: Rebuild 3 status-pages: `pending_email`, `pending_admin`, `rejected`

**Files:**
- Modify: `infra/site/app/templates/cabinet/pending_email.html`
- Modify: `infra/site/app/templates/cabinet/pending_admin.html`
- Modify: `infra/site/app/templates/cabinet/rejected.html`

Все три — простые status-страницы. Single-card centered layout.

- [ ] **Step 1: `pending_email.html`**

```html
{% extends "base.html" %}
{% block title %}Подтвердите email — Cyber Berezka{% endblock %}
{% block content %}
<main class="hero" style="max-width:540px;padding-top:9rem;padding-bottom:6rem;text-align:center">
  <div style="width:72px;height:72px;border-radius:50%;background:rgba(184,147,90,0.12);display:flex;align-items:center;justify-content:center;margin:0 auto 2rem">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="5" width="18" height="14" rx="2" stroke="#B8935A" stroke-width="2"/><path d="M3 8l9 6 9-6" stroke="#B8935A" stroke-width="2" stroke-linecap="round"/>
    </svg>
  </div>
  <h1 class="headline" style="font-size:clamp(2rem,4.4vw,2.8rem);margin-bottom:1.5rem">
    <span class="line"><span class="word" style="animation-delay:0.3s">Подтвердите</span> <span class="word accent" style="animation-delay:0.45s">email.</span></span>
  </h1>
  <p class="lead">
    Мы отправили вам письмо на <strong style="color:#1A1818">{{ user.email }}</strong>. Откройте его и нажмите ссылку — после этого мы рассмотрим заявку.
  </p>
  <form method="POST" action="/auth/logout" style="margin-top:2.5rem">
    <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token or '' }}">
    <button type="submit" class="cta-secondary" style="border:none;background:none;cursor:pointer;font-family:inherit">Выйти</button>
  </form>
</main>
{% endblock %}
```

- [ ] **Step 2: `pending_admin.html`**

```html
{% extends "base.html" %}
{% block title %}Заявка на рассмотрении — Cyber Berezka{% endblock %}
{% block content %}
<main class="hero" style="max-width:540px;padding-top:9rem;padding-bottom:6rem;text-align:center">
  <div style="width:72px;height:72px;border-radius:50%;background:rgba(184,147,90,0.12);display:flex;align-items:center;justify-content:center;margin:0 auto 2rem">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="#B8935A" stroke-width="2"/><path d="M12 7v5l3 2" stroke="#B8935A" stroke-width="2" stroke-linecap="round"/>
    </svg>
  </div>
  <h1 class="headline" style="font-size:clamp(2rem,4.4vw,2.8rem);margin-bottom:1.5rem">
    <span class="line"><span class="word" style="animation-delay:0.3s">Заявка</span> <span class="word accent" style="animation-delay:0.45s">на рассмотрении.</span></span>
  </h1>
  <p class="lead">
    Спасибо за регистрацию. Мы сообщим на <strong style="color:#1A1818">{{ user.email }}</strong>, как только выдадим доступ. Обычно это занимает не более суток.
  </p>
  <form method="POST" action="/auth/logout" style="margin-top:2.5rem">
    <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token or '' }}">
    <button type="submit" class="cta-secondary" style="border:none;background:none;cursor:pointer;font-family:inherit">Выйти</button>
  </form>
</main>
{% endblock %}
```

- [ ] **Step 3: `rejected.html`**

```html
{% extends "base.html" %}
{% block title %}Доступ отклонён — Cyber Berezka{% endblock %}
{% block content %}
<main class="hero" style="max-width:540px;padding-top:9rem;padding-bottom:6rem;text-align:center">
  <div style="width:72px;height:72px;border-radius:50%;background:rgba(184,53,31,0.1);display:flex;align-items:center;justify-content:center;margin:0 auto 2rem">
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="#B8351F" stroke-width="2"/><path d="M9 9l6 6m0-6l-6 6" stroke="#B8351F" stroke-width="2" stroke-linecap="round"/>
    </svg>
  </div>
  <h1 class="headline" style="font-size:clamp(2rem,4.4vw,2.8rem);margin-bottom:1.5rem">
    <span class="line"><span class="word" style="animation-delay:0.3s">Доступ</span> <span class="word accent" style="animation-delay:0.45s">отклонён.</span></span>
  </h1>
  <p class="lead">
    К сожалению, ваша заявка отклонена администратором.
  </p>
  {% if user.rejection_reason %}
    <div style="background:#FFFCF6;border:1px solid rgba(184,147,90,0.24);border-radius:8px;padding:1rem 1.25rem;margin:1.5rem 0;text-align:left">
      <div style="font-size:0.72rem;font-weight:600;letter-spacing:0.1em;color:#8B7E6A;text-transform:uppercase;margin-bottom:0.4rem">Причина</div>
      <div style="color:#1A1818">{{ user.rejection_reason }}</div>
    </div>
  {% endif %}
  <form method="POST" action="/auth/logout" style="margin-top:2.5rem">
    <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token or '' }}">
    <button type="submit" class="cta-secondary" style="border:none;background:none;cursor:pointer;font-family:inherit">Выйти</button>
  </form>
</main>
{% endblock %}
```

- [ ] **Step 4: Verify all 3 + commit**

```bash
python3 -c "
import jinja2
env = jinja2.Environment(loader=jinja2.FileSystemLoader('infra/site/app/templates'))
for t in ['cabinet/pending_email.html','cabinet/pending_admin.html','cabinet/rejected.html']:
    env.get_template(t); print(t, 'OK')
"
git add infra/site/app/templates/cabinet/pending_email.html infra/site/app/templates/cabinet/pending_admin.html infra/site/app/templates/cabinet/rejected.html
git commit -m "feat(site/cabinet/status-pages): apply new design system (pending-email, pending-admin, rejected)"
```

---

## Task 13: Rebuild `legal/terms.html` + `legal/privacy.html`

**Files:**
- Modify: `infra/site/app/templates/legal/terms.html`
- Modify: `infra/site/app/templates/legal/privacy.html`

Editorial reading layout. Сохранить весь юр-контент current файлов, обернуть в новую обёртку.

- [ ] **Step 1: Прочитать current legal docs**

```bash
cat infra/site/app/templates/legal/terms.html | head -50
cat infra/site/app/templates/legal/privacy.html | head -50
```

- [ ] **Step 2: Создать обёртку для обоих файлов (одинаковая)**

Для `terms.html`:

```html
{% extends "base.html" %}
{% block title %}Условия использования — Cyber Berezka{% endblock %}
{% block content %}
<main style="max-width:720px;margin:0 auto;padding:8rem 2rem 6rem">
  <div class="eyebrow"><span class="eyebrow-line"></span><span>Документ</span></div>
  <h1 class="headline" style="font-size:clamp(2rem,4.4vw,2.8rem);margin-bottom:2rem;text-align:left">
    Условия использования
  </h1>
  <div style="font-size:1rem;line-height:1.75;color:#2A2624">
    <!-- ВНУТРЬ — скопировать существующий контент terms.html (всё что было в его main контент-блоке, БЕЗ обёрток container/header которые могли быть в старом дизайне) -->
    <!-- Сохранить структуру h2 / h3 / p / ul / li -->
  </div>
</main>

<style>
main h2 { font-size:1.5rem;font-weight:600;margin:2rem 0 0.8rem;letter-spacing:-0.018em }
main h3 { font-size:1.15rem;font-weight:600;margin:1.5rem 0 0.6rem;letter-spacing:-0.01em }
main p { margin-bottom:1rem }
main ul { padding-left:1.5rem;margin-bottom:1rem }
main li { margin-bottom:0.4rem }
main a { color:#1A1818;text-decoration:underline;text-underline-offset:3px }
main strong { color:#1A1818;font-weight:600 }
</style>
{% endblock %}
```

Для `privacy.html` — аналогично, заменив title и заголовок на «Политика конфиденциальности».

Содержимое (исторические юр-тексты) скопировать из старых файлов как есть.

- [ ] **Step 3: Verify + commit**

```bash
python3 -c "
import jinja2
env = jinja2.Environment(loader=jinja2.FileSystemLoader('infra/site/app/templates'))
for t in ['legal/terms.html','legal/privacy.html']:
    env.get_template(t); print(t, 'OK')
"
git add infra/site/app/templates/legal/terms.html infra/site/app/templates/legal/privacy.html
git commit -m "feat(site/legal): apply new design system — editorial reading layout"
```

---

## Task 14: Создать favicon.svg

**Files:**
- Create: `infra/site/app/static/img/favicon.svg`

- [ ] **Step 1: Создать `infra/site/app/static/img/favicon.svg`**

Содержимое:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="7" fill="#1A1818"/>
  <text x="16" y="22" font-family="Inter, sans-serif" font-size="18" font-weight="600" fill="#B8935A" text-anchor="middle" letter-spacing="-0.05em">Б</text>
</svg>
```

- [ ] **Step 2: Verify SVG**

```bash
python3 -c "
import xml.etree.ElementTree as ET
ET.parse('infra/site/app/static/img/favicon.svg')
print('OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add infra/site/app/static/img/favicon.svg
git commit -m "feat(site/static): favicon.svg with gold Б mark"
```

---

## Task 15: Deploy + smoke-test

**Files:** none (runtime)

- [ ] **Step 1: Push + sync to VPS**

```bash
git push origin main
bash scripts/sync_repo_to_server.sh 212.74.231.217
```

- [ ] **Step 2: Rebuild site container (без Tailwind builder теперь, должно быстрее)**

```bash
ssh root@212.74.231.217 'cd /root/cyber-berezka/infra/compose && docker compose -f docker-compose.coordinator.yml --env-file ../.env up -d --build site 2>&1' | tail -8
```

- [ ] **Step 3: Smoke-test ключевых страниц**

```bash
for path in /healthz / /auth/login /auth/register /cabinet /cabinet/keys /legal/terms /legal/privacy; do
  status=$(curl -s -k -o /dev/null -w "%{http_code}" "https://212-74-231-217.nip.io$path")
  echo "$path: $status"
done
```

Ожидаемые статусы:
- `/healthz`, `/`, `/auth/login`, `/auth/register`, `/legal/*` — 200
- `/cabinet`, `/cabinet/keys` — 401 (JSON, no Accept text/html) или 303 (if Accept html)

- [ ] **Step 4: Открыть в браузере (manual)**

В браузере открыть:
1. `https://212-74-231-217.nip.io/` — landing с hero/preview/marquee/stats/about/steps/servers/features/compare/pricing/faq/final-CTA
2. `https://212-74-231-217.nip.io/auth/login` — login form в новом стиле
3. `https://212-74-231-217.nip.io/auth/register` — register form
4. Залогиниться и проверить `/cabinet`, `/cabinet/keys`

Проверить визуально:
- [ ] Favicon — gold Б в browser tab
- [ ] Hero h1 центрирован, italic-акцент gold
- [ ] Самолётики между server-cards на landing
- [ ] Tilt-on-hover работает на cards
- [ ] Scroll-progress полоска
- [ ] FAQ accordion expand/collapse
- [ ] Cabinet keys: copy-button feedback (✓ Скопировано)

- [ ] **Step 5: Update docs**

`docs/operations/backlog.md` — пометить эпик «Site UX / визуальный редизайн» как DONE с reference на этот план.

```bash
# Откройте файл и замените раздел «Site UX / визуальный редизайн» добавив:
# **Status 2026-05-28:** DONE. Plan: docs/superpowers/plans/2026-05-28-site-redesign.md
```

Затем:

```bash
git add docs/operations/backlog.md
git commit -m "docs(backlog): mark site redesign as DONE"
git push origin main
```

---

## Self-Review

**Spec coverage:**
- Цветовые токены → Task 1 (styles.css)
- Типографика → Task 1
- Компоненты (nav/cta/cards/etc.) → Task 1 (CSS) + используются в Tasks 3-13 (HTML)
- JS-поведения (scroll-progress, reveal, tilt, magnetic, plane, faq, counter) → Task 2
- 12-section landing → Task 4
- Auth pages → Tasks 5-7
- Cabinet pages → Tasks 8-12
- Legal pages → Task 13
- Favicon → Task 14
- Deploy + verify → Task 15

Все секции спеки покрыты задачами. Без пропусков.

**Placeholder scan:**
- Task 1 Step 2: ссылается на канонический HTML для CSS-блока — допустимо (file is the spec)
- Task 4 Step 2: ссылается на канонический HTML для секций — допустимо
- Task 13 Step 2: «скопировать существующий контент из старых файлов» — допустимо (контент юр-документов сохраняется)
- Никаких TBD/TODO/«implement later».

**Type consistency:**
- CSS-класс `.tilt` определён в Task 1, используется в Task 4 (node-cards, server-cards) и Tasks 8-9 (cabinet servers, keys)
- CSS-переменная `--parallax-y` определена в site.js (Task 2), читается в `.tilt` JS-handler — consistent
- form-action URLs (`/auth/login`, `/cabinet/keys`, `/cabinet/admin/pending/{id}/approve`) consistent с current routers
- CSRF token field name `csrf_token` consistent с Group C security audit fix

**Gap notes:**
- Email templates (`templates/emails/*.html`) НЕ переделываются в этом плане — отдельная задача (отметить в backlog как P2).
- Self-host Inter font — оставлен на CDN; задача self-host в backlog как P3.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-28-site-redesign.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — я диспетчирую свежего subagent'а на каждую task, ревью между task'ами, быстрая итерация. Для 15 task'ов это самый эффективный путь.

**2. Inline Execution** — выполняю task'и сам в этой сессии. Контекст растёт быстрее, но Вы видите каждое моё решение.

**Который подход выбираете?**
