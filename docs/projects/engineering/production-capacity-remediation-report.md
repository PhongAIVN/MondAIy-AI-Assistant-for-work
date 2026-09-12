# Production capacity & remediation report — P-004

| Thuộc tính | Giá trị |
| --- | --- |
| Status | P0 queue/rate-limit/quota deployed and smoke-tested on production |
| Observed at | 2026-08-10, Asia/Ho_Chi_Minh |
| Scope | Backend P-004 trên VM VNPT Cloud dùng chung |
| Evidence | Read-only host/container inspection, Docker state, Prometheus targets và public health check |
| Related | [Architecture](architecture.md) · [Evaluation plan](../qa/evaluation-plan.md) · [Deploy runbook](../../../DEPLOY.md) |

## 1. Executive summary

P-004 đang vận hành ổn định khi nhàn rỗi, nhưng chưa có bằng chứng để công bố
số lượng người dùng hoặc số Sync/AI run chịu được. P0 đã chuyển Sync từ task
nền trong API sang PostgreSQL durable queue với worker riêng; Redis chia sẻ
rate-limit giữa replicas. Việc còn lại là deploy, benchmark và theo dõi
production trước khi nâng guardrail.

Cho tới khi hoàn thành benchmark và các remediation P0, vận hành theo guardrail
sau, không xem đây là SLO hay con số capacity đã chứng minh:

| Loại tải | Guardrail tạm thời |
| --- | ---: |
| Người dùng pilot hoạt động | 5–10 |
| Sync/AI run chạy đồng thời trên production | **Tối đa 3** |
| Public capacity commitment | Chưa công bố |

Người dùng chỉ đọc dữ liệu/API không tương đương một Sync/AI run. Capacity cuối
cùng phụ thuộc dữ liệu mỗi nguồn, số batch, độ trễ/quota của LLM provider, và tải
từ các hệ thống khác cùng VM.

## 2. Snapshot production đã quan sát

### Host và workload

| Signal | Giá trị quan sát | Nhận định |
| --- | --- | --- |
| CPU | 6 vCPU Intel Xeon | Dùng chung nhiều hệ thống |
| RAM | 15 GiB total; ~4.3 GiB available tại thời điểm đo | Không có swap |
| Disk root | 158 GiB; đã dùng 77%; còn ~35 GiB | Cần alert trước khi đầy |
| Load average | 0.16 / 0.15 / 0.11 | Mẫu nhàn rỗi, không đại diện peak |
| `p004-backend` | ~213 MiB RAM, ~0.1–0.4% CPU | Không phản ánh khi Sync/LLM fan-out |
| Uvicorn | 1 process | Không có process worker song song |
| Backend restart/OOM | 0 restart, `OOMKilled=false` | Tín hiệu tốt, nhưng thời gian quan sát ngắn |
| Public health | `https://p004-api.duckdns.org/health` = 200 | Chỉ xác nhận liveness cơ bản |

Các workload khác có mức dùng RAM lớn (ví dụ một container ~5.3 GiB và một
service khác ~2.6 GiB). Vì vậy RAM host còn lại không phải ngân sách riêng của
P-004.

### Monitoring và deployment

- Prometheus target `p004-backend` đang `up`; endpoint `/metrics` trong backend
  trả HTTP 200 (`text/plain; version=0.0.4`). Các target node, containers,
  GitHub Actions và Prometheus cũng đang `up`.
- `docker-compose.prod.yml` không áp `memory`, CPU hay PID limit cho backend.
- Compose state đang chạy Loki và Promtail, trong khi hai service này không có
  trong compose production hiện có ở repository. Đây là configuration drift cần
  đối chiếu trước thay đổi deploy kế tiếp.

## 3. Các nút thắt đã xác định

| Ưu tiên | Rủi ro | Bằng chứng trong code/hạ tầng | Hậu quả |
| --- | --- | --- | --- |
| P0 | Run không có hàng đợi/concurrency cap | `asyncio.create_task` và state in-memory trong `src/api/runs.py` | Spike Sync làm cạn LLM/DB/RAM; restart làm mất task đang chạy |
| P0 | Fan-out không giới hạn | `asyncio.gather` theo sources và LLM batches | Một run lớn tạo burst request tới provider |
| P0 | API tốn tài nguyên chưa được rate-limit | Limiter chỉ dùng cho register/login/refresh | Abuse hoặc double-click tạo chi phí và 429 |
| P0 | Không resource isolation | Không có CPU/RAM/PID limit; host không swap | Một service có thể OOM/ảnh hưởng app chung |
| P1 | DB connection/pool chưa được sizing | `create_engine` dùng default pool và timeout | Độ trễ/blocking khi nhiều run cùng truy cập DB |
| P1 | Liveness không đủ readiness | `/health` chỉ trả status; deploy smoke test chỉ gọi endpoint này | Deploy có thể xanh dù dependency nghiệp vụ đang lỗi |
| P1 | Disk pressure | Root disk 77% đã dùng; Prometheus/Loki/DB giữ data | Hết disk có thể làm DB và Docker lỗi đồng thời |
| P1 | Configuration drift | Runtime có service không có trong repo compose | Deploy/rollback thiếu tính tái lập |
| P2 | Monitoring agent đặc quyền | cAdvisor `privileged` và mount host runtime | Tăng blast radius nếu monitoring container bị compromise |
| P2 | Secret hygiene | Runbook cục bộ chứa credential plaintext | Rủi ro lộ credential; cần rotate và chuyển sang vault/key-only |

## 4. Roadmap triển khai

### Phase 0 — đặt guardrail và đo baseline (trước khi mở rộng pilot)

**Đã implement (chưa deploy tại thời điểm cập nhật tài liệu):**

- API enqueue `Run` durable; `src.worker` claim job bằng `FOR UPDATE SKIP
  LOCKED` và requeue job stale sau timeout.
- Worker container và Redis service được khai báo ở compose dev/production;
  pipeline deploy khởi động worker.
- Guardrail mặc định: 3 run toàn hệ thống, 1 run active/user, 3 sources/run,
  range 31 ngày, tối đa 20 LLM batch/run và 1 LLM batch đồng thời/run.
- Redis-backed rate-limit theo user + IP: `/runs` 3/minute, `/chat` 30/minute,
  conversation message 20/minute, SSE 30/minute và OAuth start/callback
  20/minute.
- Quota chat durable: participant/mentor 10 câu/ngày; admin exempt để test.
- SSE đọc event đã persist bằng DB polling, nên API và worker ở hai process vẫn
  stream/replay được tiến trình.
- Worker chỉ khởi động sau khi backend healthy, bảo đảm migration runtime đã
  hoàn tất trước khi claim queue.

**Còn phải làm:**

1. Chuẩn hoá body và `Retry-After` của mọi phản hồi `429` theo API contract.
2. Thêm metrics: active/queued runs, run duration, batch/source count, LLM
   request latency/error/429, DB pool checked-out, HTTP status và SSE clients.
3. Đặt alert: disk 80% warning/85% critical, RAM pressure, backend restart,
   non-zero run failure rate, LLM 429, Prometheus target down.
4. Viết load-test kịch bản deterministic/mock LLM: API đọc, chat và Sync với
   1/3/5 concurrent runs; lưu kết quả p50/p95, errors, CPU/RAM và DB pool.

**Exit criteria:** 3 simultaneous runs hoàn thành không error ngoài failure đã
inject; p95 và resource peak được lưu làm baseline; dashboard/alerts hiển thị
được các signal trên.

### Phase 1 — tăng retry semantics và độ bền vận hành

Các phần đã hoàn thành: durable PostgreSQL queue, worker độc lập, stale-run
recovery và SSE đọc/replay event từ DB. Các phần tiếp theo:

1. Worker có per-provider concurrency/rate limit, retry backoff,
   idempotency và dead-letter state.
2. Cấu hình DB pool size, `pool_timeout`, statement timeout và connection
   budget theo số API/worker replica.
3. Thêm readiness `/readyz`: kiểm tra DB và các dependency bắt buộc; giữ
   `/health` là liveness nhẹ.

**Exit criteria:** restart API/worker giữa Sync không mất job; job được retry
đúng một lần logic; test cover success, denied/quota, worker restart và retry.

### Phase 2 — resource isolation, vận hành và scale ngang

1. Đặt reservation/limit CPU, memory, PID và log rotation cho toàn bộ service
   P-004; chừa headroom cho host dùng chung.
2. Xác định ownership/retention cho Postgres, MinIO, Prometheus, Loki và
   Grafana; thiết lập backup + restore drill định kỳ.
3. Reconcile compose runtime với repository (bao gồm Loki/Promtail); review
   orphan container trước khi dùng `--remove-orphans`.
4. Triển khai rolling/blue-green cho backend, rollback theo immutable image tag
   và smoke test `/readyz` + critical authenticated API.
5. Chỉ scale API/worker replicas sau khi limiter và SSE/job state đã shared.

**Exit criteria:** quota được enforce trong `docker inspect`; restore drill
thành công; deploy rollback được diễn tập; benchmark lặp lại đạt SLO đã chốt.

## 5. Capacity test plan và cách công bố

Không suy luận capacity từ CPU/RAM idle. Mỗi thay đổi Phase 0/1 phải chạy test
theo bậc 1 → 3 → 5 → 10 concurrent runs, mỗi bậc đủ thời gian warm-up và đo
ổn định. Chỉ tăng bậc khi thỏa toàn bộ điều kiện:

- HTTP/run error rate dưới ngưỡng SLO đã chốt và không có unhandled exception;
- p95 của API đọc/chat/run được ghi nhận, không tăng mất kiểm soát;
- CPU/RAM/disk/DB pool còn headroom đã định;
- không có LLM/provider 429 vượt quota thiết kế;
- job queue lag trở về 0 trong thời gian mục tiêu sau burst.

Capacity công bố phải kèm profile, ví dụ: “N concurrent Sync với X sources,
Y messages/source, model/provider Z, p95 ≤ T”. Không dùng một số “users” chung
cho cả đọc API và tác vụ AI.

## 6. Definition of done cho từng PR remediation

- Có regression test hành vi: overload bị từ chối/queued đúng, quota theo user,
  retry/idempotency, hoặc recovery sau restart tương ứng.
- Test success **và** denied/failure path cho rate limit, queue và auth.
- Chạy unit/integration test liên quan, lint/typecheck/build theo `AGENTS.md`.
- Cập nhật dashboard/alert hoặc configuration validation khi đổi runtime.
- Ghi benchmark/bằng chứng production-safe vào PR; không đưa secret, payload
  người dùng hay raw log nhạy cảm vào repo.

## 7. Các quyết định cần chốt

1. Postgres queue đã chọn cho P0; cần chốt owner vận hành, retry policy và DLQ.
2. Ngân sách CPU/RAM riêng P-004 trên VM dùng chung, hoặc thời điểm tách VM.
3. SLO cho API đọc, chat, Sync và maximum acceptable provider cost/429 rate.
4. Chính sách backup/restore và retention cho DB, MinIO, Prometheus và Loki.
5. Kế hoạch rotate credential đang ghi plaintext trong runbook và chuyển hoàn
   toàn sang SSH key/password manager.

## 8. Deploy và xác nhận production cho P0

CI deploy tự pull backend image mới và chạy `redis`, `p004-backend` và `worker`.
Trước khi push, đặt/kiểm tra các biến sau trong `/opt/p-004/.env` (không commit
secret):

```dotenv
REDIS_URL=redis://redis:6379/0
MAX_CONCURRENT_RUNS=3
MAX_RUNS_PER_USER=1
MAX_SYNC_SOURCES=3
MAX_SYNC_RANGE_DAYS=31
MAX_TOTAL_LLM_BATCHES_PER_RUN=20
MAX_LLM_BATCHES_PER_RUN=1
LLM_QUESTIONS_PER_DAY=10
```

Sau CI xanh, xác nhận read-only trên VM:

```bash
cd /opt/p-004
docker compose -f docker-compose.prod.yml ps redis p004-backend worker
docker compose -f docker-compose.prod.yml logs --tail 100 worker
curl -fsS https://p004-api.duckdns.org/health
```

Kỳ vọng: cả ba service `Up`, worker không loop exception, health trả 200. Sau đó
chạy một Sync pilot và kiểm tra row `runs` chuyển `queued → running → succeeded`.
Không nâng giới hạn 3 concurrent runs nếu chưa có kết quả load test lưu ở PR.

### Bằng chứng pre-deploy 2026-08-10

- `ruff check src/ tests/`: pass.
- `pytest`: 336 passed, 2 skipped.
- `docker compose ... config -q`: pass cho cả compose development và production.
- Frontend `tsc -b --force`, `npm run lint`, `npm run build`: pass; lint còn 4
  warning Fast Refresh/hooks có sẵn, không có error.

### Kết quả rollout production 2026-08-10

- Commit production: `a6fa3d2`; backend và worker dùng image Linux AMD64
  `p004-backend:a6fa3d2`.
- Backup trước rollout: `.env.bak-2026-08-10-capacity-97cfff5` và
  `docker-compose.prod.yml.bak-2026-08-10-capacity-97cfff5`; backup trước lần
  nâng hard cap cuối là `.env.bak-2026-08-10-batch-cap-a6fa3d2` trong
  `/opt/p-004`.
- Chỉ tạo/recreate `redis`, `p004-backend`, `worker`; DB, MinIO, observability
  và các hệ thống dùng chung khác không bị restart.
- Redis `PONG`; backend healthy, restart count 0; worker running, restart count
  0. HTTP healthcheck thừa hưởng từ image được disable cho worker vì process
  này không mở web server.
- Runtime đã xác nhận `MAX_TOTAL_LLM_BATCHES_PER_RUN=20`.
- PostgreSQL có đủ `runs.attempts`, `runs.claimed_at`,
  `users.llm_quota_day`, `users.llm_questions_used`.
- Public `/health` trả `{"status":"ok","env":"production"}` và
  `/api/v1/status` trả agent `ready`.
- GitHub Actions của SHA này đã được kích hoạt nhưng self-hosted runner còn
  queued; rollout dùng đường SSH key theo runbook sau khi local checks pass.
