# infra/remnawave — declarative provisioning

Управление Remnawave через декларативные конфиги в git, без UI-кликов. Дизайн — `docs/superpowers/specs/2026-05-17-apply-py-design.md`.

## Bootstrap (один раз)

```bash
# На VPS (или любой машине с HTTPS-доступом к panel):
cd /root/cyber-berezka/infra/remnawave
pip install httpx          # минимальная зависимость для bootstrap
python3 bootstrap_token.py
# Введите admin username + password (как при логине в panel)
# Скрипт создаст API-token, добавит REMNAWAVE_API_TOKEN в /root/cyber-berezka/infra/.env
```

После этого `.env` содержит:
```
REMNAWAVE_API_URL=https://admin.194-87-83-31.nip.io
REMNAWAVE_API_TOKEN=<long-jwt-string>
```

## Status (текущее состояние)

```bash
pip install httpx          # для apply.py тоже нужна
python3 apply.py status
```

Выведет:
- Config Profiles (имя, uuid)
- Internal Squads (имя, кол-во пользователей, кол-во inbound'ов)
- Nodes (имя, адрес, статус подключения)
- Hosts (remark, address:port, SNI)
- Users (username, status, shortUuid)

## Что появится позже

- `apply.py import` — выгрузить текущее состояние в `configs/*.yaml` + `state.json`
- `apply.py plan` — diff между YAML и API
- `apply.py apply` — привести API к состоянию YAML
- `apply.py validate` — проверить YAML без API

См. design-doc для деталей.
