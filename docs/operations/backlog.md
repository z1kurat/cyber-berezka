# Backlog

Активные и отложенные задачи, не покрытые отдельными планами/спеками. Когда задача переходит в реализацию — для неё создаётся `tmp/plans/<date>-<slug>.md`, а здесь остаётся ссылка.

---

## Xray JSON Advanced — продуктовые кейсы (зафиксировано 2026-05-26)

Документация: `https://docs.rw/docs/learn/xray-json-advanced`. Требует Remnawave 2.6.3+ (наша версия 2.7.4 — поддерживается).

Принцип: subscription отдаёт клиенту не плоский список `vless://`, а полноценный `XRAY_JSON` template с `outbounds` / `routing` / `balancer`, где Remnawave при генерации **инжектит реальные хосты** в позиции `injectHosts`. Шаблоны хранятся как `subscription-templates` (тип `XRAY_JSON`) и привязываются к хосту через поле `xrayJsonTemplateUuid`. Шаблоны кладутся в `infra/remnawave/configs/` и применяются через `apply.py` (IaC, см. `feedback_prefer_declarative_iac.md`).

### Кейс 1 — RU-direct routing (приоритет: средний)

**Status 2026-05-27:** **DONE.** Реализовано через Squad-per-mode архитектуру.
- Spec: `docs/superpowers/specs/2026-05-27-protection-modes-design.md`
- Plan: `docs/superpowers/plans/2026-05-27-protection-modes.md`
- 2 squad'а (Default-Squad → «Полная», Mode-Smart → «Умная»), 6 host'ов (3 full + 3 smart с одинаковыми `address:port`), subscription-template `smart_routing` с `geoip:ru`/`geosite:category-{gov,bank,media}-ru` → direct.
- Toggle на `/cabinet` (карточка наверху).

**Известное ограничение:** базовый subscription URL отдаёт base64-flat в обоих режимах. Routing-rules применяются только при доступе к `<sub_url>/json`. Это нужно либо отрабатывать в клиенте (sing-box SFA/SFI получают JSON автоматически по UA), либо документировать для v2RayTun/Hiddify пользователей. Открыт **подбэклог** «Smart-mode URL exposure» — показать `/json` вариант ссылки в кабинете при `protection_mode='smart'`, либо переписать subscription-flow через site-proxy (Option B из спеки).


Трафик до российских ресурсов (geoip:ru + geosite:category-gov-ru / category-bank-ru / category-media-ru) маршрутизировать **в обход** Reality-туннеля, через `outbound: direct` на стороне клиента. Остальной трафик — через нашу ноду.

Зачем:
- Скорость до российских сайтов (без петли через LV/NL/DE).
- Снижение нагрузки на ноды и трафик-биллинг VPS.
- Юр-позиционирование: «трафик до российских ресурсов не маршрутизируется через защищённое соединение» — усиливает narrative «защита данных в публичном интернете», а не «обход блокировок» (см. `project_legal_positioning.md`).
- Российские сайты (банк-клиенты, госуслуги) реже триггерят антифрод-проверки.

Зависит от: Xray JSON Advanced infrastructure (см. подготовительный шаг ниже).

### Кейс 2 — Failover + load-balancing между нодами (приоритет: средний, после массового запуска)

Сейчас в subscription отдаются 3 отдельных `vless://` (LV / NL / DE). Клиент сам выбирает / переключает руками. Через Xray JSON Advanced: `balancer` + `observatory` — клиент **сам** мониторит latency до 3 нод и выбирает быструю/живую, автоматически переключаясь при падении.

Зачем:
- Прозрачный failover при падении ноды.
- Latency-aware routing — пользователь не страдает от того, что Remnawave подсунул дальнюю ноду первой в списке.
- UX-улучшение без действий пользователя.

Зависит от: тоже Xray JSON Advanced infrastructure.

### Кейс 3 — Multi-tier outbound для платных пользователей (приоритет: низкий, после биллинга)

Разделить хосты по тегам/remarks: `^free-` и `^premium-`. Через `injectHosts.tagRegex` отдавать платным subscription с premium-хостами (например, отдельный пул IP, выделенные ноды), бесплатным — общий пул.

Зачем:
- Реализация платных тарифов без отдельной инфры — просто разные template для разных squad'ов.
- Премиум-сегрегация трафика → выше скорость / приватность для платящих.

Зависит от: биллинг-фаза проекта, кейсы 1 и 2 как foundation.

---

## Site UX / визуальный редизайн (приоритет: высокий, обозначен 2026-05-26)

Никита Олегович зафиксировал: текущая реализация сайта (`infra/site/app/templates/*.html`) **визуально плохая и с плохим UX**. Шаблоны существуют и работают, но не соответствуют brand-спецификации Direction A «Премиум-кремовое» (Cormorant Garamond + Inter, BG `#F7F3EB`, gold `#B8935A`, CTA wine `#B8351F`) на уровне реализации — это копия скелета на Tailwind без выверенных композиций, типографики, отступов, иконок, состояний (loading/empty/error), мобильных адаптаций.

**Скоуп:**
- Полный пересмотр всех страниц кабинета (`/cabinet`, `/cabinet/keys`, `/cabinet/admin/*`), auth (`/auth/register`, `/auth/login`, `/auth/verify-sent`), landing.
- Дизайн-система: компоненты (Card, Button, Toggle, Input, Badge, Toast) в `infra/site/app/static/css/input.css`.
- Empty states, loading states, error states.
- Микро-анимации (transitions, hover).
- Мобильная вёрстка (responsive breakpoints).
- Visual hierarchy: расстановка priority элементов, focal points, белое пространство.
- Иконографика (single source, унифицированный visual language).

**Не делать в этой задаче:** менять backend, менять модели данных, менять API. Только templates + CSS + минимально JS для интерактива.

**Подход:** перед началом — отдельная brainstorming-сессия с visual companion + спека под `docs/superpowers/specs/<date>-site-redesign.md`. Возможно — использовать subagent `ui-designer` или `frontend-developer`.

---

## Рефакторинг Remnawave-модели — отдельный Remnawave-user на каждый VpnKey (приоритет: высокий, будет нужно перед per-key фичами)

Сейчас `VpnKeysService.ensure_remnawave_user` создаёт **один** Remnawave-user на каждого пользователя сайта; все 1–3 `VpnKey` этого пользователя живут под одним subscription URL и фильтруются на фронте по `meta.address`. Это создаёт долг:

- ключи нельзя ревокать независимо (отзыв одного зацепит всех);
- лимиты трафика и device-quota применяются «суммарно», не на ключ;
- subscription отдаёт клиенту **все** ноды (LV+NL+DE) для каждого `vless://`, фронт прячет лишнее — клиенту фактически утекают endpoint'ы, к которым он не привязан;
- per-key routing-mode (RU-direct vs всё-через-VPN) технически возможен только при separate Remnawave-users;
- per-key audit (когда/кем/на каком устройстве использован ключ) тоже требует separate users.

**Скоуп:**
- Изменить `VpnKeysService.create_key` — для каждого нового `VpnKey` создавать отдельного Remnawave-user (`user_<site_user_id>_<vpn_key_id>`), привязывать к нужному squad.
- В `VpnKey` модель — добавить `remnawave_user_uuid` / `remnawave_short_uuid` (хранятся на ключе, не на пользователе сайта).
- В `revoke_key` — `DELETE /api/users/<uuid>` (или `PATCH status=DISABLED`).
- Использовать **squad-per-country** или `excludedInternalSquads` хосту, чтобы subscription отдавала только привязанные к ключу ноды (а не все).
- Миграция существующих 5 user'ов: открыто — переводить «как есть» (1 legacy user на старые ключи) или дробить (если у юзера 3 ключа — создаём 3 новых Remnawave-users + revoke старого).
- Cleanup устаревших полей `User.remnawave_user_uuid` / `User.remnawave_short_uuid` после миграции.

**Зависит от:** ничего критичного. **Блокирует:** per-key RU-direct, per-key лимиты, per-key биллинг.

**Не делать в этой задаче:** менять UI кабинета (поведение для пользователя идентично), менять формат subscription URL.

---

### Подготовительный шаг (общий для всех 3 кейсов Xray JSON Advanced)

1. Дизайн-док: `docs/superpowers/specs/2026-05-26-xray-json-advanced.md` — выбор стратегии селекторов (uuids / tagRegex / remarkRegex), формат tag'ов, политика naming хостов.
2. Положить XRAY_JSON template в `infra/remnawave/configs/subscription_template_xray.json`.
3. Добавить в `apply.py` команду `apply-subscription-template` (создаёт/обновляет template + привязывает к хостам через `xrayJsonTemplateUuid`).
4. Verification: скачать subscription через `curl -H 'User-Agent: v2RayTun'` и убедиться, что отдаётся JSON, а не плоский base64-список.

---

## Прочие активные задачи (наследие)

| # | Задача | Источник |
|---|---|---|
| #27 | Ограничить Remnawave panel на localhost (перед production) | session snapshot 2026-05-22 |
| #28 | Регенерировать Reality private key | session snapshot 2026-05-22 |
| #34 | iptables persistent (172.21.0.0/16 + 2053) | session snapshot 2026-05-22 |
| #41 | Регенерировать Remnawave API token (компрометация в чате 2026-05-25/26) | этот разговор + snapshot |
| #44 | DNS `cyber-berezka.ru` в Beget UI → 194.87.208.112 / 212.74.231.217 | session snapshot 2026-05-22 |
| #46 | Site auth + cabinet + Brevo + Alembic (большая часть выполнена, остаются amendments) | `tmp/plans/2026-05-23-site-amendments.md` |
| — | Синхронизировать `infra/remnawave/configs/profile_default.template.json` с live state (port=8443, dest=microsoft, shortIds=["a1b2c3d4"]) | reconnaissance 2026-05-25 |
| — | Сменить SSH-пароль root на VPS Hetzner DE `159.69.198.143` + перейти на ключи | компрометация в чате 2026-05-25 |
