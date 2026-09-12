# Cổng vào HTTPS chỉ cho API, dùng khi VM đã có reverse proxy của app khác
# giữ port 80/443. Xem DEPLOY.md mục 1.6.
#
# Tách khỏi image frontend (client/web-app/Dockerfile) có chủ đích: backend
# cần ra Internet ngay, còn frontend thì chưa xong — gộp chung thì mỗi lần
# dựng cổng vào là đẩy luôn UI đang làm dở ra địa chỉ công khai.

FROM caddy:2-builder-alpine AS builder

# Image caddy chính thức không kèm provider DNS nào, mà DNS-01 là cách duy
# nhất xin được cert khi không có port 80/443.
RUN xcaddy build --with github.com/caddy-dns/duckdns

FROM caddy:2-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY Caddyfile /etc/caddy/Caddyfile
