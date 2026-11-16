# syntax=docker/dockerfile:1
# Digest pins resolved from Docker Hub on 2026-11-15; update deliberately with the release receipt.
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv PATH=/app/.venv/bin:$PATH
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libgdal32 libgeos-c1v5 libproj25 libgomp1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.9.9
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra extra-tanush --extra extra-ayan --extra extra-aradhya
COPY src ./src
COPY config ./config
COPY contracts ./contracts
COPY ops/azure/probe.py /app/probe.py
COPY ops/azure/provision-db.py /app/provision-db.py
RUN uv sync --frozen --no-dev --extra extra-tanush --extra extra-ayan --extra extra-aradhya \
    && groupadd --system --gid 10001 analogforge \
    && useradd --system --uid 10001 --gid 10001 --no-create-home analogforge \
    && mkdir -p /data && chown 10001:10001 /data
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["analogforge"]
CMD ["serve"]

FROM node:24-bookworm-slim@sha256:dc26ae92c9fb15cf6b1d63e20f0944b2efe0f115b20e00be48fb23fceb061c54 AS frontend
ENV NODE_OPTIONS=--max-old-space-size=1536 VITE_API_BASE_URL=/api/v1 VITE_API_MOCK=0
WORKDIR /build
RUN corepack enable && corepack prepare pnpm@10.22.0 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
COPY scripts/ui ./scripts/ui
RUN pnpm install --frozen-lockfile
COPY contracts ./contracts
COPY config/presets/rovers/ares-1.json ./config/presets/rovers/ares-1.json
COPY tests/fixtures/kit ./tests/fixtures/kit
COPY tests/unit/passport_renderer/fixtures/bundles/positive.json ./tests/unit/passport_renderer/fixtures/bundles/positive.json
COPY apps/web ./apps/web
RUN pnpm --filter @analogforge/web run typecheck && pnpm --filter @analogforge/web run build

FROM caddy:2-alpine@sha256:003a97808e781aa9f7e75cc2f43d34d461099031faf5e20faefb9f61126836f0 AS proxy
COPY --from=frontend /build/apps/web/dist /srv
COPY ops/azure/Caddyfile /etc/caddy/Caddyfile
