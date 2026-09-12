#!/usr/bin/env bash
# Chạy 1 LẦN trên VPS trần (Ubuntu/Debian) trước khi CI/CD deploy được.
# Cách chạy: SSH vào VPS rồi `sudo bash vps_bootstrap.sh`.
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/app}"
DEPLOY_USER="${DEPLOY_USER:-$SUDO_USER}"

if [ -z "$DEPLOY_USER" ]; then
  echo "Chạy bằng sudo từ user thường (không phải root trực tiếp) để xác định DEPLOY_USER." >&2
  exit 1
fi

echo "==> Cài Docker Engine + Compose plugin"
apt-get update
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "==> Cho $DEPLOY_USER dùng docker không cần sudo"
usermod -aG docker "$DEPLOY_USER"

echo "==> Mở firewall: SSH, 80, 443, 8443"
apt-get install -y ufw
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
# 8443 cho mode "tự lo HTTPS trên cổng riêng" khi VM dùng chung và 80/443 đã
# thuộc về app khác. Không dùng mode đó thì gỡ dòng này cho gọn bề mặt tấn công.
ufw allow 8443/tcp
ufw --force enable

echo "==> Tạo thư mục deploy $DEPLOY_DIR"
mkdir -p "$DEPLOY_DIR"
chown "$DEPLOY_USER":"$DEPLOY_USER" "$DEPLOY_DIR"

cat <<EOF

Xong. Bước tiếp theo (đăng xuất/đăng nhập lại SSH để nhóm "docker" có hiệu lực):

  1. Copy docker-compose.prod.yml và .env.prod.example vào $DEPLOY_DIR
     (ví dụ: scp từ máy local, hoặc git clone repo vào đây rồi copy 2 file ra).
  2. cd $DEPLOY_DIR && cp .env.prod.example .env && nano .env   # điền giá trị thật
  3. docker login ghcr.io -u <github-username>   # dùng PAT scope read:packages
  4. docker compose -f docker-compose.prod.yml pull
  5. docker compose -f docker-compose.prod.yml up -d

Xem DEPLOY.md ở repo để lấy SSH deploy key + cấu hình GitHub Actions secrets.
EOF
