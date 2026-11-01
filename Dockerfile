# syntax=docker/dockerfile:1
#
# Single-server image set for the SOC L2 incident analyzer.
#
# Three stages, because the target VM (GCP e2-micro: 1 GB RAM) cannot build the
# Angular bundle: compilation happens in stage 1 on the build host (or during
# `docker compose build` on the VM, which is why the VM needs swap), and only the
# emitted `dist/frontend/browser` tree travels into the runtime images.
#
#   api  — FastAPI + pandas + ReportLab, no dev dependencies, non-root.
#   web  — Caddy, the public entry point: static bundle + `/api/*` proxy.

# ---------------------------------------------------------------------------
# Stage 1 — frontend build (Angular production bundle).
# ---------------------------------------------------------------------------
FROM node:22 AS frontend-build

WORKDIR /build

# Cap the V8 heap so the build fails loudly instead of OOM-killing the VM.
ENV NODE_OPTIONS=--max-old-space-size=768 \
    NG_CLI_ANALYTICS=false

# Lockfile first: a source-only change reuses the cached dependency layer.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --fund=false

COPY frontend/ ./
# `ng build` (defaultConfiguration: production) writes dist/frontend/browser.
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2 — API runtime (the backend image).
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS api

# uv ships as its own image; the venv is built from the committed uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/backend/.venv/bin:$PATH"

WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
# `--no-dev` keeps pytest/ruff/pypdf out of the runtime image; `--no-cache`
# keeps the ~190 MB wheel cache out of the layer; uvicorn runs the venv directly,
# so the uv binaries themselves are removed once the sync is done.
RUN uv sync --frozen --no-dev --no-install-project --no-cache \
    && rm -f /bin/uv /bin/uvx

COPY backend/app ./app
# `/srv` in the web stage and `/app/static` here are the same build output.
COPY --from=frontend-build /build/dist/frontend/browser /app/static

# Unprivileged runtime user; /app and its venv stay root-owned and read-only
# for that user, so a compromised process cannot rewrite the application.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app
USER app

EXPOSE 8000

# `--proxy-headers` makes uvicorn rewrite the peer address from
# `X-Forwarded-For`, but only when the direct peer is listed in
# FORWARDED_ALLOW_IPS (uvicorn's `--forwarded-allow-ips`, default
# 127.0.0.1,::1). docker-compose.yml sets that variable to the `web`
# container, so the rate limiter sees the real client instead of the proxy.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

# ---------------------------------------------------------------------------
# Stage 3 — Caddy: serves the same bundle and proxies `/api/*` to the API.
# ---------------------------------------------------------------------------
FROM caddy:2-alpine AS web

COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /build/dist/frontend/browser /srv
