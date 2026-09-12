# TODO — P-004

## Admin portal — RBAC và dữ liệu thật

**Trạng thái:** Đã làm
**Ngày:** 2026-08-09

Trước đó `/admin` chỉ được chặn bằng `ProtectedRoute` phía client, mà `role`
nằm trong `localStorage` — sửa devtools là vào được, và backend không có khái
niệm quản trị viên nào cả.

Đã có:

- `users.role` / `display_name` / `is_active` trong `src/models/user.py`, kèm
  migration runtime trong `src/db.py` cho DB đã tồn tại (chưa có Alembic).
- `require_admin` trong `src/api/deps.py`, đọc lại quyền từ DB mỗi request nên
  hạ quyền hoặc khoá tài khoản có hiệu lực ngay dù token còn hạn.
- `src/api/admin.py`: overview, users (kèm đổi role và khoá), sources, runs,
  audit, telemetry. Chỉ số liệu tổng hợp — xem phần đầu file để biết ranh giới
  theo PRD §4.4 và §5.
- Đăng ký không tự đặt được role; nâng quyền qua portal hoặc
  `scripts/grant_role.py <email> admin` (dùng để tạo admin đầu tiên).
- `tests/test_api/test_admin.py` — 20 test, gồm một test chốt chặn quét mọi khoá
  trong response admin để bắt trường nội dung cá nhân lọt vào.
- Frontend: `Dashboard`, `Users`, `Sources`, `Activity`, `Feedback` chạy API
  thật kèm trạng thái loading/rỗng/lỗi.

Còn mock: `Programs`, `Briefings`, `Conflicts`, `Settings` — chưa có model
backend tương ứng, đã gắn banner cảnh báo trên từng trang.

## Admin portal observability & configuration

**Trạng thái:** Chưa triển khai
**Ngày ghi nhận:** 2026-08-08

### Mục tiêu

Hoàn thiện admin portal để quản lý và quan sát tập trung toàn bộ P-004:

- frontend health và frontend errors;
- backend logs, metrics và traces;
- AI runs, latency, token usage, cost, retrieval và feedback;
- product telemetry và audit log;
- frontend/backend configuration có phân quyền, versioning và audit.

### Stack đã nghiên cứu

- **Prometheus:** metrics và alerting cho request rate, latency, error rate, CPU/RAM.
- **Grafana:** dashboard, Explore và alerting.
- **Loki:** tập trung application logs, truy vấn bằng LogQL.
- **Tempo:** distributed tracing, liên kết với Grafana/Loki/Prometheus.
- **OpenTelemetry Collector hoặc Grafana Alloy:** thu thập, chuẩn hóa và export logs/metrics/traces.
- **Sentry Cloud:** frontend/backend error tracking và release regression.
- **LangSmith:** AI tracing, model calls, evaluation và feedback; có thể mở từ portal bằng deep link.
- **PostgreSQL hiện tại:** tiếp tục là nguồn dữ liệu cho `TelemetryEvent` và `AuditEvent`.

### Kiến trúc dự kiến

```text
P-004 Web App
  ├─ frontend errors → Sentry
  ├─ product events → P-004 API → PostgreSQL
  └─ observability → OTel Collector/Alloy

P-004 FastAPI
  ├─ product telemetry/audit → PostgreSQL
  ├─ metrics → Prometheus
  ├─ logs → Loki
  └─ traces → Tempo

AI services
  ├─ sanitized traces/evaluations → LangSmith
  └─ operational telemetry → OTel stack

Admin Portal
  ├─ business data/configuration/audit → P-004 API
  ├─ operational dashboards → Grafana
  ├─ errors → Sentry
  └─ AI observability → LangSmith
```

### Phân rã công việc

- [ ] Chuẩn hóa backend log dạng JSON với `service`, `env`, `level`, `trace_id`, `request_id`.
- [ ] Hoàn thiện key pool OpenRouter: dùng `OPENROUTER_API_KEYS`, xoay vòng khi gọi model/embedding và tạm cooldown key gặp 401/402/429/5xx; đưa secret vào secret manager production.
- [ ] Kiểm tra và hoàn thiện việc tạo `trace_id` xuyên suốt request/frontend → backend → AI.
- [ ] Thêm Prometheus metrics cho FastAPI, database, source sync và AI workflow.
- [ ] Tạo Docker Compose development gồm Grafana, Prometheus, Loki, Tempo và Alloy/OTel Collector.
- [ ] Provision Grafana data sources và dashboard cơ bản.
- [ ] Cấu hình retention, access control và bảo vệ endpoint observability.
- [ ] Thêm Sentry cho web app và backend; gắn release/version.
- [ ] Gắn LangSmith cho các AI chain/agent; thống nhất metadata như `trace_id`, `surface`, `model`.
- [ ] Không gửi raw prompt, answer, email, message hoặc nội dung riêng tư vào metrics/logs/LangSmith nếu chưa có chính sách cho phép.
- [ ] Thêm `/admin/observability` gồm overview, logs, traces, frontend health và AI runs.
- [ ] Thêm `/admin/configuration` cho feature flags, model, rate limit, retention và source sync interval.
- [ ] Lưu version cấu hình và ghi mọi thay đổi vào `AuditEvent`.
- [ ] Thêm deep link từ portal tới Grafana, Sentry và LangSmith; không để admin portal tự quản lý credentials của các hệ thống này.
- [ ] Viết smoke test cho telemetry privacy, RBAC, dashboard datasource và alert routing.

### Thứ tự triển khai khuyến nghị

1. Giữ PostgreSQL telemetry/audit hiện tại làm product source of truth.
2. Chuẩn hóa logs và metrics backend.
3. Chạy stack Grafana local bằng Docker Compose.
4. Bổ sung traces với OpenTelemetry/Tempo.
5. Tích hợp Sentry và LangSmith.
6. Xây các trang observability/configuration trong `/admin`.
7. Thực hiện hardening về privacy, retention, RBAC và alerting trước production.

### Quyết định thiết kế cần chốt sau

- [ ] Self-host toàn bộ hay dùng Grafana Cloud/Sentry Cloud/LangSmith Cloud.
- [ ] Thời gian retention riêng cho logs, traces, metrics và audit events.
- [ ] Phạm vi dữ liệu AI mà admin được xem.
- [ ] Cơ chế xác thực khi mở dashboard ngoài portal.
- [ ] Bộ SLO/alert chính thức của P-004.
