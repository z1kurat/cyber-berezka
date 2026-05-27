# Site Redesign — Cyber Berezka

**Дата:** 2026-05-28
**Brainstorm session:** `.superpowers/brainstorm/84352-1779911948/` (10 итераций v1–v10)
**Канонический референс:** `docs/superpowers/specs/2026-05-28-site-redesign-assets/landing-canonical.html`
**Status:** APPROVED FOR IMPLEMENTATION (Никита Олегович 2026-05-28: «применяй»)

---

## Цель

Полный визуальный редизайн сайта — заменить текущий Tailwind-скелет на зрелую дизайн-систему. Бренд-направление «Премиум-кремовое с кибер-берёзовым мотивом».

## Принятые решения (10 итераций брейншторма)

| # | Решение |
|---|---|
| Палитра | Cream `#F7F3EB`, gold `#B8935A`, wine `#B8351F`, ink `#1A1818`. Direction A зафиксирован. |
| Шрифт | **Inter везде** (Cormorant Garamond отменён в v8 как «устаревший для UI»). |
| Логотип | Тёмный rounded-square `#1A1818` с gold Cyrillic «Б», 26×26px (favicon аналогично). |
| Эстетика | Cream-premium + лёгкий cyber-edge через circuit-traces на иконке-листе. |
| Hero | Центрированный заголовок (clamp `3.2–5.8rem`), italic-акцент gold. Под ним — preview-stage с 3 server-cards. |
| Lead motif | Лист-PCB — геометрический угловой силуэт с circuit-trace внутри + PCB-pad точки. |
| Анимации | Mesh-blob фон, grain overlay, scroll-progress полоска, stagger-reveal на ВСЕ блоки при scroll, magnetic CTA, **tilt-on-hover** на карточках (perspective + rotateX/Y), бумажные самолётики между серверами, marquee, FAQ smooth-expand. |
| Тон | «Ответственность на системе» (без обвинения пользователя), безличные конструкции, мягкие empty states. |
| Trust | Юр.реквизиты в footer, никаких «As Seen On» / счётчиков пользователей. |

## Дизайн-система

### Цветовые токены (CSS variables)

```css
--cream:     #F7F3EB;  /* base background */
--cream-soft:#FDFAF3;  /* nested cards */
--cream-deep:#EFE6D2;  /* featured/elevated */
--gold:      #B8935A;  /* accents, eyebrow text, dividers, active state */
--gold-deep: #966D40;  /* hover-gold */
--gold-dim:  rgba(184,147,90,0.20);
--wine:      #B8351F;  /* CTA primary only */
--wine-hover:#9A2B17;
--ink:       #1A1818;  /* primary text */
--ink-2:     #2A2624;  /* secondary text */
--muted:     #6B6661;
--muted-2:   #8B7E6A;
--border:    rgba(184,147,90,0.24);
```

### Типографика

- **Стек:** `'Inter', -apple-system, system-ui, sans-serif`
- **Подключение:** `https://rsms.me/inter/inter.css` (используется variable font)
- **Headings:** weight 600, letter-spacing -0.025em to -0.04em (тем туже, чем крупнее)
- **Hero h1:** `clamp(3.2rem, 7.5vw, 5.8rem)`, line-height 1
- **Section h2:** `clamp(2.2rem, 4.6vw, 3.6rem)`, line-height 1.04
- **Body:** weight 400, 1rem / 1.6 line-height, color `--muted`
- **Eyebrow:** uppercase, weight 600, letter-spacing 0.14em, gold color
- **Mono (terminal blocks):** `'JetBrains Mono', 'SF Mono', Menlo, monospace`

### Компоненты

См. канонический HTML для точных CSS-правил. Ключевые компоненты:

1. **`.nav`** — fixed top, backdrop-blur 14px, scrolled-state с border-bottom
2. **`.brand-mark`** — rounded-square 26px с «Б» (gradient ink → ink-2 фон, gold буква)
3. **`.cta-primary`** — wine background, shimmer-pass на hover, inset highlight, shadow-lift
4. **`.cta-secondary`** — text-only с scaleX подчёркиванием на hover
5. **`.section-tag`** + `.section-tag-line` — gold uppercase eyebrow с горизонтальной линией, scaleX на in-view
6. **`.reveal`** + `.reveal-delay-{1..4}` — opacity 0 + translateY 80px → 0 на in-view (1100ms cubic-bezier)
7. **`.server-card`** / `.step` / `.price-card` — карточка с border, hover-lift через box-shadow + .tilt JS
8. **`.node-card`** — компактная карточка для hero preview, opacity-load через `.loaded` class
9. **`.conn`** — div-based линии-соединения 4rem длиной, с PCB-точками по концам и `.plane` SVG внутри
10. **`.plane`** — paper-plane SVG с keyframe `planeFly` (3.6s loop, delay 2.6s/4.4s)
11. **`.marquee-track`** — бесконечная бегущая строка 40s linear infinite
12. **`.faq-item`** + `.faq-item.open` — accordion с max-height + plus→minus icon rotation
13. **`.compare-table`** — grid 2fr 1fr 1fr с подсвеченной «нашей» колонкой

### Декоративные элементы

- **Mesh-blob фон:** 4 размытых (`filter: blur(80px)`) gold/wine/cream цветных пятна на `position: fixed`, дрейфующих по keyframe (22–36s циклы)
- **Grain overlay:** SVG-шум через data-URI, opacity 0.45, `mix-blend-mode: multiply`
- **Scroll-progress bar:** fixed top, height 2px, gold→wine градиент, glow shadow
- **Bark-pattern:** `repeating-linear-gradient` тонкие горизонтальные полоски (cyber-берёзовая кора) в compare-section
- **«Б» бэкграунд-буква:** clamp 20rem–36rem, opacity 0.05, центрированный фон в about-name section
- **«Берёзка» текст-фон:** clamp 8rem–14rem, opacity 0.07, фон final-CTA

### JavaScript-поведения

1. **Scroll handler** — обновляет scroll-progress width, nav .scrolled state, parallax preview-cards через CSS variable `--parallax-y` (data-speed: -1/2/-1)
2. **IntersectionObserver `io`** — добавляет `.in` класс к `.reveal` элементам и `.in-view` к секциям при threshold 0.12
3. **`statsIo`** — отдельный observer для секции stats, запускает counter-анимацию чисел
4. **Counter** — текстовая анимация трастовых чисел (3, 99.9, 1)
5. **Magnetic CTA** — на mousemove внутри `#ctaMagnet` translate в направлении курсора с амплитудой 0.18×/0.25×
6. **Tilt-on-hover** — на mousemove внутри `.tilt` perspective(1200px) rotateY/X (±3.5° на обычных, ±6° на `.node-card`), translateY -3/-6px. Транспортирует через CSS-variable, не теряет parallax.
7. **Node-card stagger load** — JS добавляет `.loaded` класс с stagger (1.6s, 1.8s, 2.0s) для opacity fade-in
8. **FAQ accordion** — click на `.faq-q` тогл `.open` на родителе, закрывает другие открытые

## Структура страниц

Все страницы наследуют `base.html` с: `<nav>`, `<div class="mesh">`, `<div class="grain">`, `<div class="scroll-progress">`, `<footer>`. JS из канонического файла — в отдельный `static/js/site.js`. CSS — в `static/css/site.css` (расширение существующего `styles.css` или замена).

### `landing/index.html` (полный референс)

12 секций по порядку:
1. **Hero** (центрированный, h1 `Кибер встречает берёзу.` с italic accent)
2. **Preview stage** — 3 node-cards LV/NL/DE + 2 conn-линии + 2 самолётика
3. **Marquee** — бегущая строка с 6 ключевыми терминами
4. **Stats** — 4 больших числа (3 страны / 99.9% / 1 Гбит/с / 0 логов)
5. **About-name** — editorial moment «Берёзка — не ностальгия. Это спокойствие.» + большой PCB-leaf SVG в bark-карточке
6. **Steps** — 3 шага (регистрация / ключ / подключение)
7. **Servers** — 3 server-cards с detail-stats
8. **Features** — 2 alternating-row блока (Reality, Кабинет) с term/cab-card иллюстрациями
9. **Comparison** — таблица 7 строк Berezka vs обычный VPN
10. **Pricing** — 3 тарифа (Месяц / Полгода featured / Год)
11. **FAQ** — 6 вопросов accordion
12. **Final CTA** — «Готовы начать?» с background «Берёзка»

### `auth/*.html`

Те же tokens, но без landing-специфичных секций. Hero-аналог (центрированный h1 + lead + form-card) на cream BG. Form поля: cream-soft background, gold-dim border, focus → ink border + gold-dim ring. CTA — wine primary.

- `login.html` — заголовок «Войти», email + password fields, CTA «Войти». Под формой: «Нет аккаунта? Зарегистрироваться →»
- `register.html` — заголовок «Создать аккаунт», email + password + confirm + checkbox terms, CTA «Создать аккаунт». Под: «Уже есть аккаунт? Войти →»
- `verify_sent.html` — большой success-icon (gold checkmark), заголовок «Письмо отправлено», параграф-инструкция, CTA-secondary «Вернуться на главную»

### `cabinet/index.html`

- Header: «Кабинет» h1, email справа + Выйти
- 3 секции (server-cards с live-статусами / Ключи с CTA / справочные ссылки)
- Заменяет текущий Tailwind-скелет на дизайн-систему

### `cabinet/keys.html`

- Header «Мои ключи» + breadcrumb «← В кабинет»
- Форма создания ключа (label + country select + create-button) — на крупной карточке
- Список ключей-аккордионов: каждый ключ = `.cab-card` с key uuid, копировать-кнопка с micro-interaction (галочка на 2с), QR-кнопка, revoke-link

### `cabinet/admin_pending.html`, `admin_keys.html`

Та же дизайн-система, табличный layout для bulk-actions.

### `cabinet/pending_email.html`, `pending_admin.html`, `rejected.html`

Centered single-card layout. Заголовок-объяснение + 1-2 line описание + secondary CTA («Выйти» или «Связаться с поддержкой»).

### `legal/terms.html`, `legal/privacy.html`

Editorial reading layout: max-width 720px, увеличенный line-height (1.7), structured h2/h3 hierarchy, типографика как в about-name секции.

---

## Файлы под изменение

**Templates (13):**
- `infra/site/app/templates/base.html`
- `infra/site/app/templates/landing/index.html`
- `infra/site/app/templates/landing/_server_list.html`
- `infra/site/app/templates/auth/{login,register,verify_sent}.html`
- `infra/site/app/templates/cabinet/{index,keys,admin_pending,admin_keys,pending_email,pending_admin,rejected}.html`
- `infra/site/app/templates/legal/{terms,privacy}.html`

**CSS (1 новый + 1 update):**
- `infra/site/app/static/css/site.css` (NEW) — все компоненты дизайн-системы из v10
- `infra/site/app/static/css/styles.css` — заменяется или дополняется
- `infra/site/tailwind.config.js` — токены могут пригодиться, но v10 использует чистый CSS + variables (не Tailwind)

**JS (1 новый):**
- `infra/site/app/static/js/site.js` (NEW) — scroll-progress, intersection-observer reveals, counter, magnetic CTA, tilt-on-hover, FAQ accordion, node-card stagger-load

**Static assets:**
- `infra/site/app/static/img/favicon.svg` — обновить под новый «Б» mark

---

## Не делаем в этой задаче

- Backend, модели данных, API — без изменений.
- Routing — без изменений.
- Logic-уровень `services/` / `routers/` — без изменений (только пересмотр HTML, который они рендерят).
- Перевод документов / контент policy — содержимое legal/terms/privacy остаётся как есть, только обёртка визуальная.

## Источник правды

**`docs/superpowers/specs/2026-05-28-site-redesign-assets/landing-canonical.html`** — этот файл является каноничным эталоном для всех компонентов, цветов, анимаций, JS-поведения. При любом сомнении в реализации — смотрите этот HTML.

---

## Verification criteria (Phase 3 plan-do-verify)

- [ ] `/cabinet`, `/cabinet/keys`, `/auth/login`, `/auth/register`, `/` — все рендерятся в новом стиле, без визуальных регрессий
- [ ] Hero на `/` центрирован, h1 ≥ 3.2rem, отвечает на reduce-motion / mobile breakpoint
- [ ] Tilt-on-hover работает на cards (можно проверить в Chrome DevTools — element.style.transform меняется на mousemove)
- [ ] Самолётики появляются после загрузки серверных карточек (не одновременно)
- [ ] Scroll-progress полоска видна сверху
- [ ] Logo в browser tab показывает gold «Б» на тёмном square
- [ ] Mobile breakpoint (max-width 900) — grid'ы стянуты в одну колонку, nav-links спрятаны
- [ ] AST + Jinja syntax checks на всех `.html`
- [ ] Не сломались формы login/register/keys-create (CSRF token остаётся, action remained correct)
