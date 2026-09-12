# ---- Stage 1: Build frontend ----
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite injects these values at build time. They are intentionally build args:
# the production VM pulls this image instead of building the frontend locally.
ARG VITE_API_URL=
ARG VITE_GRAFANA_URL=
ARG VITE_PROMETHEUS_URL=
RUN VITE_API_URL="$VITE_API_URL" VITE_GRAFANA_URL="$VITE_GRAFANA_URL" VITE_PROMETHEUS_URL="$VITE_PROMETHEUS_URL" npm run build

# ---- Stage 2: Caddy kèm module DNS DuckDNS ----
# Image caddy chính thức không có sẵn provider DNS nào. Cần module này vì trên
# VM dùng chung, port 80 và 443 do Caddy của app khác giữ, nên không xin được
# chứng chỉ bằng HTTP-01 hay TLS-ALPN-01 — chỉ còn đường DNS-01.
FROM caddy:2-builder-alpine AS caddybuilder

RUN xcaddy build --with github.com/caddy-dns/duckdns

# ---- Stage 3: Serve (static file server + reverse proxy /api sang backend) ----
FROM caddy:2-alpine

COPY --from=caddybuilder /usr/bin/caddy /usr/bin/caddy
COPY --from=builder /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
