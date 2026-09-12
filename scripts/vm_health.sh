#!/usr/bin/env bash
# Health check CHỈ ĐỌC cho P-004 trên VM.
#
# Vì sao có file này: cấp quyền chạy `ssh <host> <lệnh tuỳ ý>` cho một agent là
# cấp root không cần hỏi trên một VM dùng chung 6 hệ thống. Script này chạy đúng
# một tập lệnh đọc cố định, nên allowlist nó là an toàn còn allowlist ssh thì không.
#
# KHÔNG chứa credential. Host và password đọc từ RUNBOOK.local.md (đã .gitignore).
# KHÔNG in ra giá trị secret nào — chỉ in tên biến và độ dài.
#
#   ./scripts/vm_health.sh          # tất cả
#   ./scripts/vm_health.sh --brief  # bỏ phần schema (nhanh hơn)
set -euo pipefail

BRIEF=0
[ "${1:-}" = "--brief" ] && BRIEF=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNBOOK="$ROOT/RUNBOOK.local.md"

# Thiếu cấu hình thì NỔ TO, không đoán và không rơi về giá trị mặc định.
[ -f "$RUNBOOK" ] || { echo "✗ Không thấy $RUNBOOK — không có host/credential để kết nối." >&2; exit 1; }
command -v sshpass >/dev/null || { echo "✗ Thiếu sshpass. Cài: brew install sshpass" >&2; exit 1; }

VM_HOST="$(grep -oE '^ssh root@[0-9a-zA-Z.:_-]+' "$RUNBOOK" | head -1 | sed 's/^ssh //')"
SSHPASS="$(grep -iE '^# ?Password:' "$RUNBOOK" | head -1 | sed -E 's/^# ?Password:[[:space:]]*//')"
[ -n "$VM_HOST" ]  || { echo "✗ Không đọc được host từ $RUNBOOK (mong đợi dòng 'ssh root@<ip>')." >&2; exit 1; }
[ -n "$SSHPASS" ]  || { echo "✗ Không đọc được password từ $RUNBOOK (mong đợi dòng '# Password: ...')." >&2; exit 1; }
export SSHPASS

echo "── P-004 · health check chỉ đọc · $(date '+%Y-%m-%d %H:%M') ──"
echo "host: $VM_HOST"
echo

# Toàn bộ phần chạy trên VM nằm trong đúng một heredoc đã cố định. Không có
# tham số nào của người gọi đi vào đây — đó là lý do script này allowlist được.
sshpass -e ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "$VM_HOST" \
  "BRIEF=$BRIEF bash -s" <<'REMOTE'
set -uo pipefail

echo "=== MÁY ==="
uptime | sed 's/^/  /'
df -h / | tail -1 | awk '{printf "  đĩa : %s / %s (%s đã dùng)\n", $3, $2, $5}'
free -h | awk '/^Mem:/ {printf "  RAM : %s / %s dùng, %s available\n", $3, $2, $7}'

echo
echo "=== CONTAINER P-004 ==="
docker ps --filter "name=p-004" --format '  {{.Names}}\t{{.Status}}' | sort | column -t -s$'\t'

echo
echo "=== CODE ĐANG CHẠY (tag KHÔNG đáng tin — xem Created) ==="
IMG="$(docker inspect -f '{{.Config.Image}}' p-004-p004-backend-1 2>/dev/null || echo '?')"
echo "  tag đang mang : $IMG"
docker image inspect "$IMG" --format '  image build lúc: {{.Created}}' 2>/dev/null || echo "  image build lúc: không đọc được"
docker inspect -f '  container start: {{.State.StartedAt}}' p-004-p004-backend-1 2>/dev/null || true
echo "  rollback có sẵn (tag này sinh từ SHA thật, dùng làm điểm quay lui):"
# docker cắt khoảng trắng đầu chuỗi --format nên phải thụt lề bằng sed sau khi lọc.
docker images "${IMG%:*}" --format '{{.Tag}}\t{{.CreatedSince}}' \
  | grep '^rollback-' | head -3 | column -t -s$'\t' | sed 's/^/    /' \
  || echo "    (không có tag rollback nào — deploy sẽ không có điểm quay lui)"

echo
echo "=== HEALTH ==="
# Gọi qua docker network. KHÔNG dùng localhost:8000 của host — cổng đó là app khác.
docker exec minute_caddy wget -qS -O /dev/null http://p004-backend:8000/health 2>&1 \
  | grep -m1 -i 'HTTP/' | sed 's/^ */  nội bộ  p004-backend:8000\/health → /' || echo "  nội bộ  : không gọi được"
for p in /health /docs; do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://p004-api.duckdns.org$p" || echo ERR)"
  printf '  công khai%-7s → %s\n' "$p" "$code"
done
echo | openssl s_client -connect p004-api.duckdns.org:443 -servername p004-api.duckdns.org 2>/dev/null \
  | openssl x509 -noout -enddate 2>/dev/null | sed 's/notAfter=/  cert hết hạn : /' || echo "  cert: không đọc được"

echo
echo "=== BIẾN CẤU HÌNH (chỉ tên và độ dài, KHÔNG in giá trị) ==="
for k in OPENAI_API_KEY OPENROUTER_API_KEY APP_SECRET_KEY BACKEND_IMAGE DUCKDNS_API_TOKEN CADDY_ADDR EDGE_BIND; do
  v="$(grep -E "^$k=" /opt/p-004/.env 2>/dev/null | head -1 | cut -d= -f2-)"
  if [ "$k" = "BACKEND_IMAGE" ]; then
    printf '  %-20s = %s\n' "$k" "${v:-TRỐNG}"
  elif [ -n "$v" ]; then
    printf '  %-20s = có (%s ký tự)\n' "$k" "${#v}"
  else
    printf '  %-20s = TRỐNG/THIẾU\n' "$k"
  fi
done

if [ "${BRIEF:-0}" != "1" ]; then
  echo
  echo "=== GUARDRAIL vs REGISTRY (tool nào bị chặn ở đường thật) ==="
  # Test đơn vị gọi thẳng hàm tool nên không đi qua action_node — 6 tool từng bị
  # chặn trên production trong khi mọi lớp kiểm đều xanh. Đây là chỗ đo đúng đơn
  # vị: hỏi chính container đang chạy xem registry và guardrail có khớp nhau không.
  docker exec p-004-p004-backend-1 python -c '
from src.agents.nodes.core_nodes import _BASE_TOOLS
from src.guardrail.policy import is_tool_allowed
# Phải hỏi ĐÚNG predicate mà action_node dùng (read OR compute OR draft).
# Hỏi mỗi phase="read" mặc định sẽ báo nhầm mọi tool compute/draft là bị chặn.
def allowed(n):
    return any(is_tool_allowed(n, phase=p) for p in ("read", "compute", "draft"))
names = sorted({getattr(t, "name", getattr(t, "__name__", str(t))) for t in _BASE_TOOLS})
blocked = [n for n in names if not allowed(n)]
print(f"  registry: {len(names)} tool")
print(f"  ✗ BỊ CHẶN {len(blocked)}: " + " · ".join(blocked) if blocked else "  ✓ không tool nào bị chặn")
print("  fail-closed:", "còn nguyên" if not allowed("tool_khong_ton_tai_abc") else "✗ ĐÃ HỎNG")
' 2>/dev/null || echo "  không kiểm được guardrail trong container"

  echo
  echo "=== SCHEMA (đếm để so với model, không dump dữ liệu) ==="
  U="$(docker exec p-004-db-1 printenv POSTGRES_USER 2>/dev/null || echo app)"
  D="$(docker exec p-004-db-1 printenv POSTGRES_DB 2>/dev/null || echo ai20k)"
  docker exec p-004-db-1 psql -U "$U" -d "$D" -tA -c \
    "select '  bảng: '||count(distinct table_name)||' · cột: '||count(*)
     from information_schema.columns where table_schema='public'" 2>/dev/null \
    || echo "  không truy vấn được DB"
fi
REMOTE

echo
echo "── xong · không có lệnh ghi nào được chạy ──"
