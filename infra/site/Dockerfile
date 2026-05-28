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
