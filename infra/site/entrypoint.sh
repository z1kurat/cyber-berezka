#!/usr/bin/env bash
# Site container entrypoint:
#   1. Wait for db-app to be reachable.
#   2. Run alembic upgrade head.
#   3. Exec the main command (uvicorn).
set -euo pipefail

echo "[entrypoint] Waiting for db-app..."
python - <<'PY'
import asyncio, os, sys
import asyncpg
async def wait():
    url = os.environ["APP_DB_URL"]
    # Convert SQLAlchemy URL to asyncpg-compatible one.
    url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    for i in range(60):
        try:
            c = await asyncpg.connect(url)
            await c.close()
            print(f"[entrypoint] DB reachable on attempt {i+1}")
            return
        except Exception as e:
            print(f"[entrypoint] attempt {i+1}: {e}")
            await asyncio.sleep(1)
    print("[entrypoint] FATAL: DB never became reachable", file=sys.stderr)
    sys.exit(1)
asyncio.run(wait())
PY

echo "[entrypoint] Running alembic upgrade head..."
# Pass the original asyncpg URL — migrations/env.py uses async_engine_from_config
# (Task 1) which expects postgresql+asyncpg://, not the sync psycopg2 URL.
alembic -c /app/alembic.ini upgrade head

echo "[entrypoint] Starting uvicorn..."
exec "$@"
