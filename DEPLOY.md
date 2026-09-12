# Deploy — VPS + GitHub Actions

Push lên `main` → GitHub Actions build 2 Docker image (backend, frontend+Caddy),
đẩy lên GHCR, SSH vào VPS pull ảnh mới + restart. Không cần làm gì thủ công sau
lần setup đầu.

## P0 Sync worker và Redis rate limit

Production có thêm `redis` (shared rate limit) và `worker` (PostgreSQL durable
run queue). Chúng được CI khởi động cùng backend; không public port Redis.
Thêm các guardrail vào `/opt/p-004/.env` trước deploy lần đầu (giữ giá trị mặc
định nếu chưa benchmark):

```dotenv
REDIS_URL=redis://redis:6379/0
MAX_CONCURRENT_RUNS=3
MAX_RUNS_PER_USER=1
MAX_TOTAL_LLM_BATCHES_PER_RUN=20
MAX_SYNC_SOURCES=3
MAX_SYNC_RANGE_DAYS=31
MAX_LLM_BATCHES_PER_RUN=1
SSE_POLL_SECONDS=0.5
LLM_QUESTIONS_PER_DAY=10
```

Sau deploy, kiểm tra worker cùng health API:

```bash
cd /opt/p-004
docker compose -f docker-compose.prod.yml ps redis p004-backend worker
docker compose -f docker-compose.prod.yml logs --tail 100 worker
curl -fsS https://p004-api.duckdns.org/health
```

## 1. Setup VPS (chạy 1 lần)

SSH vào VPS, chạy bootstrap (cài Docker, mở firewall 80/443, tạo `/opt/app`):

```bash
scp scripts/vps_bootstrap.sh user@VPS_IP:~/
ssh user@VPS_IP
sudo bash vps_bootstrap.sh
# đăng xuất/đăng nhập lại để nhóm "docker" có hiệu lực
```

Copy 2 file cấu hình vào `/opt/app` trên VPS (scp hoặc git clone repo rồi copy ra):

```bash
scp docker-compose.prod.yml .env.prod.example user@VPS_IP:/opt/app/
```

Trên VPS:

```bash
cd /opt/app
mv .env.prod.example .env
nano .env   # điền DOMAIN, BACKEND_IMAGE/FRONTEND_IMAGE (owner/repo viết thường),
            # APP_SECRET_KEY (tạo bằng: python3 -c "import secrets; print(secrets.token_urlsafe(48))"),
            # POSTGRES_PASSWORD, OPENAI_API_KEY, CORS_ORIGINS=https://<domain>
```

Đăng nhập GHCR để pull được image private (dùng Personal Access Token, scope
`read:packages` — tạo tại GitHub → Settings → Developer settings → Tokens):

```bash
docker login ghcr.io -u <github-username>
# nhập PAT khi được hỏi password
```

Chạy lần đầu:

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Caddy tự lấy chứng chỉ HTTPS (Let's Encrypt) cho `DOMAIN` — cần A record của
domain đã trỏ vào IP VPS trước bước này, và port 80/443 mở ra Internet.

## 1.5. Nếu VPS đã chạy site khác qua nginx hệ thống (dùng chung VPS)

Không đụng gì tới site cũ / config nginx cũ. App này chạy nội bộ, nginx hệ
thống làm cổng public duy nhất, route theo domain sang app qua reverse proxy.

Trong `.env` trên VPS, dùng đúng 2 dòng này (mặc định sẵn trong
`.env.prod.example`):

```
CADDY_ADDR=:80
EDGE_BIND=127.0.0.1:8081
```

`8081` là port nội bộ tuỳ chọn — đổi số khác nếu đã bị chiếm (`ss -tlnp | grep 8081` để check trước).

Tạo vhost nginx mới (thay `DOMAIN_THAT` bằng domain thật, `8081` khớp `EDGE_BIND` ở trên):

```bash
cat > /etc/nginx/sites-available/DOMAIN_THAT <<'EOF'
server {
    listen 80;
    server_name DOMAIN_THAT;

    access_log /var/log/nginx/DOMAIN_THAT_access.log combined;
    error_log  /var/log/nginx/DOMAIN_THAT_error.log warn;

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -s /etc/nginx/sites-available/DOMAIN_THAT /etc/nginx/sites-enabled/DOMAIN_THAT
nginx -t && systemctl reload nginx
```

Đưa app lên trước (để có gì sau nginx proxy tới):

```bash
cd <thư mục deploy>
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Rồi mới lấy HTTPS (certbot tự sửa file vhost thêm block SSL + redirect HTTP→HTTPS, giống hệt cách nó đã làm cho site cũ):

```bash
certbot --nginx -d DOMAIN_THAT
```

`location /` trỏ thẳng vào container Caddy — Caddy tự lo static file, SPA
fallback, và proxy `/api/*` sang backend (xem `client/web-app/Caddyfile`),
nginx không cần biết route bên trong.

## 1.6. VM đang dùng thật (VNPT Cloud) — reverse proxy dùng chung là Caddy

| | |
|---|---|
| Host | `14.225.168.28`, user CI `p004deploy` |
| Thư mục deploy | `/opt/p-004` |
| Domain backend | `https://p004-api.duckdns.org` |

VM này chạy chung 6 hệ thống. Cổng 80/443 do container `minute_caddy` giữ, nên
không có nginx hệ thống như mục 1.5 — routing đi qua Caddyfile dùng chung
`/opt/minute/minute/infra/Caddyfile`, block của app này:

```
p004-api.duckdns.org {
  encode zstd gzip

  redir /grafana /grafana/
  handle /grafana/* {
    reverse_proxy p004-grafana:3000
  }

  redir /prometheus /prometheus/
  handle /prometheus/* {
    reverse_proxy p004-prometheus:9090
  }

  handle {
    reverse_proxy p004-backend:8000
  }
}
```

Các matcher observability phải đứng trước `handle` fallback. Không dùng một
`reverse_proxy p004-backend:8000` duy nhất, vì khi đó `/grafana/*` và
`/prometheus/*` sẽ bị FastAPI nhận và trả `404`.

Sửa file đó xong thì nạp lại, zero-downtime, không restart container:

```bash
docker exec minute_caddy caddy validate --config /etc/caddy/Caddyfile
docker exec minute_caddy caddy reload --config /etc/caddy/Caddyfile
```

`Caddyfile` được bind-mount theo file. Nếu công cụ cập nhật thay inode thay vì
ghi đè nội dung tại chỗ, container đang chạy có thể vẫn nhìn thấy bản cũ. Khi
đó chép candidate đã validate vào container và reload trực tiếp từ candidate,
không cần restart proxy dùng chung:

```bash
docker cp /path/to/Caddyfile minute_caddy:/tmp/Caddyfile.candidate
docker exec minute_caddy caddy validate --config /tmp/Caddyfile.candidate
docker exec minute_caddy caddy reload --config /tmp/Caddyfile.candidate
```

Hai điều kiện khiến `docker-compose.prod.yml` phải khác bản mặc định:

- backend join thêm network ngoài `caddy` để `minute_caddy` phân giải được tên
  container qua Docker DNS;
- service **không được** đặt tên `backend`. Docker DNS đặt alias theo tên
  service trên mọi network nó join, mà Caddyfile dùng chung đã có route trỏ
  tới `backend` của bds-chatbot — trùng tên là cướp traffic của app đó. Tên
  đang dùng là `p004-backend`, và alias `backend` chỉ được giữ trong network
  riêng của app để `client/web-app/Caddyfile` không phải sửa.

Việc không được làm trên VM này: mở `ports:` ra `0.0.0.0` cho `db`, giành cổng
80/443, hay restart container của các app khác khi đang deploy.

## 1.7. VM dùng chung nhưng muốn độc lập hẳn với app khác (phương án khác)

Mục 1.5 ở trên bắt app này phụ thuộc vào reverse proxy của app khác: mỗi lần
đổi routing đều phải sửa file cấu hình không thuộc quyền mình, và app khác
restart sai lúc là mình mất luôn HTTPS. Mode này bỏ hẳn phụ thuộc đó.

Ý tưởng: Caddy của app này nghe **8443**, tự xin chứng chỉ Let's Encrypt bằng
**DNS-01** — chứng minh quyền sở hữu domain qua bản ghi TXT thay vì qua port
80/443. Nhờ vậy không cần mượn cổng của ai.

Đánh đổi: URL có kèm cổng, `https://p004-api.duckdns.org:8443`.

**Điều kiện:** tài khoản DuckDNS sở hữu subdomain phải là của nhóm mình, vì cần
token để sửa TXT. Lấy token ở trang chủ duckdns.org sau khi đăng nhập.

Trong `.env` trên VM:

```
CADDY_ADDR=p004-api.duckdns.org:8443
EDGE_BIND=0.0.0.0:8443
DUCKDNS_API_TOKEN=<token lấy ở duckdns.org>

CORS_ORIGINS=https://p004-api.duckdns.org:8443
APP_PUBLIC_URL=https://p004-api.duckdns.org:8443
```

Cổng phải ghi đủ trong `CORS_ORIGINS` và `APP_PUBLIC_URL`: trình duyệt coi
`:8443` là origin khác hẳn `:443`, và OAuth so khớp redirect_uri từng ký tự.

Mở firewall rồi dựng lên:

```bash
sudo ufw allow 8443/tcp
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs -f edge   # xem ACME cấp cert
curl -fsS https://p004-api.duckdns.org:8443/health
```

Lần đầu Caddy mất khoảng 30–60 giây để lấy cert. Log báo `certificate obtained
successfully` là xong. Cert lưu ở volume `caddy_data`, đừng xoá volume này —
xoá là phải xin lại và Let's Encrypt có giới hạn số lần cấp mỗi tuần.

**Việc phải nhờ chủ app đang giữ 80/443:** xoá route của domain này khỏi
Caddyfile dùng chung của họ. Để lại thì cùng một hostname có hai nơi nhận,
người gõ địa chỉ không kèm cổng sẽ rơi vào proxy của họ và gặp lỗi TLS.

## 2. SSH deploy key cho GitHub Actions

Tạo keypair riêng cho CI (không dùng key cá nhân):

```bash
ssh-keygen -t ed25519 -f deploy_key -N "" -C "github-actions-deploy"
```

Thêm public key vào VPS:

```bash
ssh-copy-id -i deploy_key.pub user@VPS_IP
# hoặc: cat deploy_key.pub | ssh user@VPS_IP "cat >> ~/.ssh/authorized_keys"
```

`deploy_key` (private, KHÔNG có đuôi `.pub`) → paste nguyên văn vào GitHub
Secret `VPS_SSH_KEY` (bước 3). Xoá file `deploy_key`/`deploy_key.pub` khỏi máy
sau khi thêm xong, đừng commit vào repo.

## 3. GitHub repo secrets & variables

**Settings → Secrets and variables → Actions**

Secrets (bắt buộc):

| Name | Giá trị |
|---|---|
| `VPS_HOST` | IP hoặc hostname VPS |
| `VPS_USER` | user SSH (user chạy bootstrap script) |
| `VPS_SSH_KEY` | nội dung file `deploy_key` (private key) ở bước 2 |
| `VPS_PORT` | port SSH, bỏ qua nếu là 22 |

Variables (không bí mật, dùng cho smoke test sau deploy):

| Name | Giá trị |
|---|---|
| `DOMAIN` | host smoke test gọi tới. Kèm cổng nếu khác 443, vd `p004-api.duckdns.org:8443` — thiếu cổng là smoke test đỏ dù deploy thành công |
| `DEPLOY_DIR` | bỏ qua nếu dùng mặc định `/opt/app` |

GHCR image mặc định **private**, gắn liền theo repo, `GITHUB_TOKEN` trong CI
tự có quyền push — không cần thêm secret nào cho việc build/push image.

## 4. Từ giờ chỉ cần

```bash
git push origin main
```

`.github/workflows/deploy.yml` tự: chạy test → build 2 image → push GHCR →
SSH VPS pull + restart → smoke test `https://$DOMAIN/health`. Deploy fail ở
bước nào thì dừng ở đó, không đụng tới bước sau (test fail thì không build,
build fail thì không deploy).

## 5. Theo dõi CI/CD trong Grafana

Production chạy `github-actions-exporter` trong mạng Docker nội bộ. Exporter
đọc workflow của repository P-004 mỗi 30 giây, Prometheus scrape cổng 9999 và
Grafana provision dashboard `P-004 CI/CD` từ file trong `observability/`.

Thêm vào `/opt/p-004/.env` trên VM (không commit token thật):

```dotenv
GITHUB_ACTIONS_EXPORTER_TOKEN=<fine-grained PAT đọc Actions của P-004>
```

Khởi động hoặc cập nhật riêng stack observability:

```bash
cd /opt/p-004
docker compose -f docker-compose.prod.yml up -d \
  github-actions-exporter prometheus grafana
```

Kiểm tra Prometheus đã scrape được exporter:

```bash
docker exec p-004-prometheus-1 wget -qO- \
  'http://localhost:9090/prometheus/api/v1/query?query=up%7Bjob%3D%22github-actions%22%7D'
```

Kết quả phải có value `1`. Dashboard:

```text
https://p004-api.duckdns.org/grafana/d/p004-cicd/p-004-ci-cd
```

Token hiện tại chỉ cần đọc workflow. Nếu muốn thêm trạng thái từng organization
runner, token phải được org admin cấp thêm quyền quản trị runner; thiếu quyền đó
không ảnh hưởng các metric CI/Deploy.

## Rollback nhanh

Image cũ vẫn còn trên GHCR (tag theo commit SHA). Trên VPS:

```bash
cd /opt/app
docker compose -f docker-compose.prod.yml pull   # hoặc sửa .env trỏ tag SHA cụ thể
docker compose -f docker-compose.prod.yml up -d
```

## Xem log / debug trên VPS

```bash
cd /opt/app
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f edge
docker compose -f docker-compose.prod.yml ps
```
