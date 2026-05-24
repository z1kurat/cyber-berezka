# Cyber Berezka site — multi-stage build:
#   stage 1 (tw-builder): generate Tailwind CSS via standalone CLI
#   stage 2 (final):      slim Python with the app + pre-built CSS

# --- Tailwind stage ---------------------------------------------------------
FROM alpine:3.20 AS tw-builder

ARG TAILWIND_VERSION=v3.4.16
RUN apk add --no-cache curl ca-certificates \
    && curl -sSL -o /usr/local/bin/tailwindcss \
        https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-x64 \
    && chmod +x /usr/local/bin/tailwindcss

WORKDIR /work
COPY tailwind.config.js ./
COPY app/static/css/input.css ./app/static/css/input.css
COPY app/templates ./app/templates

RUN tailwindcss -i ./app/static/css/input.css -o ./app/static/css/styles.css --minify

# --- Final stage ------------------------------------------------------------
FROM python:3.12-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.115" "uvicorn[standard]>=0.32" \
    "sqlalchemy[asyncio]>=2.0" "asyncpg>=0.30" "alembic>=1.13" \
    "pydantic>=2.9" "pydantic-settings>=2.6" "email-validator>=2.2" \
    "jinja2>=3.1" "python-multipart>=0.0.20" "argon2-cffi>=23.1" \
    "httpx>=0.27" "itsdangerous>=2.2" "redis[hiredis]>=5.2" "qrcode[pil]>=7.4"

# App source.
COPY app/ ./app/
COPY alembic.ini ./alembic.ini
COPY migrations/ ./migrations/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Tailwind output from builder stage.
COPY --from=tw-builder /work/app/static/css/styles.css ./app/static/css/styles.css

# Run as non-root.
RUN useradd --create-home --uid 1000 site && chown -R site:site /app
USER site

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=3)" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
