# Demo runbook — Sprint 4 (TAPB Stabilize MVP & pilot readiness)

| Thuộc tính | Giá trị |
| --- | --- |
| Mục tiêu | Chạy demo end-to-end không phụ thuộc kết nối OAuth thật (Jira/Gmail/Outlook/Calendar) |
| Liên quan | [Privacy checklist Demo Day](../product/demo-day-privacy-checklist.md) · [seed_demo.py](../../../scripts/seed_demo.py) |
| Verify lần cuối | 2026-08-15 — chạy thật qua curl, xem mục 5 |

## 1. Chuẩn bị máy (1 lần)

```bash
# Backend: cài dependency + tạo .env từ .env.example, điền DATABASE_URL
# (postgresql://... ) và APP_SECRET_KEY tối thiểu. SMTP để trống là được —
# forgot-password chỉ log link ra console, không cần secret thật cho demo.
.venv/Scripts/python.exe -m pip install -r requirements.txt

# Frontend
cd client/web-app && npm install && cd ../..
```

## 2. Tạo schema + seed demo account

```bash
# Bước 1: chạy backend 1 lần để tự tạo bảng (create_all + ensure_runtime_schema
# trong src/main.py lifespan), rồi Ctrl+C dừng lại.
.venv/Scripts/python.exe -m uvicorn src.main:app --port 8000
# (Ctrl+C sau khi thấy "Application startup complete")

# Bước 2: seed account demo + 3 task mẫu (Jira/Gmail/Calendar giả lập, KHÔNG
# gọi API thật). Chạy lại nhiều lần an toàn (idempotent, bỏ qua nếu đã có).
.venv/Scripts/python.exe scripts/seed_demo.py
```

Output in ra email/password demo — mặc định `demo@mondaiy.local` /
`MondaiyDemo2026!` (xem hằng số đầu file `scripts/seed_demo.py` nếu cần đổi).

## 3. Chạy demo (3 process song song)

```bash
# Terminal 1 — API
make run

# Terminal 2 — worker (xử lý Run/Sync queue, reminder, auto-sync)
make worker

# Terminal 3 — frontend
cd client/web-app && npm run dev
```

Mở `http://localhost:5173`.

Nếu chỉ cần demo Tasks/Briefing (không cần sync thật), Terminal 2 (worker) có
thể bỏ qua — task đã seed sẵn thẳng vào DB, không đi qua queue.

## 4. Kịch bản demo (đã verify hoạt động, xem mục 5)

1. Đăng nhập bằng tài khoản demo ở bước 2.
2. Vào **Công việc** (`/tasks`) — thấy 3 task mẫu: 1 từ "Jira" (proposed), 1
   từ "Gmail" (đã confirmed sẵn), 1 từ "Calendar" (proposed). Mỗi task có nút
   "Truy cập nguồn" mở deep_link mẫu (không phải link thật, chỉ minh hoạ UI).
3. Bấm Xác nhận 1 task proposed — chuyển trạng thái, verify UI cập nhật ngay.
4. Vào **Nguồn kết nối** (`/sources`) — đây là nơi disconnect/connect THẬT,
   không phải `/data-privacy`. Nếu muốn demo phần privacy/quyền, dùng trang
   này — xem lý do ở [privacy checklist mục 2](../product/demo-day-privacy-checklist.md#2-gap-đã-xác-nhận--phải-nói-rõ-khi-demo-không-im-lặng-bỏ-qua).
5. KHÔNG vào `/data-privacy` như một tính năng đã hoàn thiện — trang này hiện
   là mock tĩnh, xem chi tiết ở privacy checklist.

## 5. Verify đã chạy thật (bằng chứng, không phải suy đoán)

Chạy 2026-08-15 qua `curl` trực tiếp vào backend đang chạy (không qua UI):

```
POST /api/v1/auth/login (demo@mondaiy.local)        -> 200, token hợp lệ
GET  /api/v1/tasks                                  -> 200, 3 task đúng thứ tự mới nhất trước
POST /api/v1/tasks/1/confirm                        -> 200, status proposed -> confirmed
GET  /api/v1/reminders/notifications?limit=10       -> 200, {"notifications":[]}
GET  /api/v1/conversations                          -> 200, {"conversations":[]}
GET  /api/v1/connections                            -> 200, 5 provider đều connected=false
```

Kết luận: luồng lõi (login → xem task → confirm task) ổn định, KHÔNG phụ
thuộc kết nối OAuth thật. Danh sách connections trống là ĐÚNG kỳ vọng cho demo
account (chưa connect gì) — không phải lỗi.

**Chưa verify được trong phiên này** (cần OAuth thật, không tự động hoá được
từ CLI — cần người có tài khoản Google/Jira/Outlook thật đăng nhập qua trình
duyệt):

- Luồng connect Jira/Gmail/Outlook/Calendar thật + sync pipeline 9-node chạy
  end-to-end với dữ liệu thật.
- Reminder/notification thật sinh ra từ task có due_at (seed script không gọi
  `generate_proposed_notice`, chỉ insert thẳng DB).
- Calendar handoff / export .ics từ task đã confirm.

Nếu Demo Day cần show các luồng này, phải tự tay chạy thử với tài khoản thật
trước ít nhất 1 lần, không dựa vào seed script.

## 6. Reset demo (chạy lại nhiều lần trước Demo Day)

```bash
# Xoá sạch task/message/cluster của demo account, giữ lại account (đăng nhập
# lại không cần đổi password) — chạy tay qua psql hoặc:
.venv/Scripts/python.exe -c "
from sqlalchemy import select, delete
from src.db import SessionLocal
from src.models.user import User
from src.models.task import Task
db = SessionLocal()
user = db.execute(select(User).where(User.email=='demo@mondaiy.local')).scalar_one()
db.execute(delete(Task).where(Task.user_id==str(user.id)))
db.commit()
print('cleared tasks for', user.email)
"
# Rồi seed lại:
.venv/Scripts/python.exe scripts/seed_demo.py
```

`Cluster.task_id` chỉ `SET NULL` khi Task bị xoá (không cascade xoá `Cluster`
đi kèm), và `Message` độc lập hoàn toàn với vòng đời Task/Cluster — xoá Task ở
trên KHÔNG xoá `Cluster`/`Message` liên quan, để lại row mồ côi. Đã verify
2026-08-15: `scripts/seed_demo.py` tự dọn row mồ côi này trước khi tạo lại
(so khớp theo `cluster_key` và `provider+source_id+external_id`) — chạy lại
`seed_demo.py` sau lệnh xoá Task ở trên là đủ, KHÔNG cần tự xoá tay
`Cluster`/`Message`. Đã test 2 vòng reset→reseed liên tiếp, ra đúng 3 task mỗi
lần, không lỗi `UniqueViolation`.

## 7. Sự cố thường gặp

- **Port 8000 đã bị chiếm** — có process backend cũ chưa tắt. Tìm và kill
  trước khi `make run`, hoặc dùng process đang chạy nếu nó đã đúng code mới
  nhất (`git status` sạch trước khi tin process cũ).
- **Log INFO không hiện gì khi debug demo lỗi** — đã fix ở
  [src/main.py:56-64](../../../src/main.py) (Sprint 4, xem lịch sử commit) —
  nếu vẫn không thấy, kiểm tra `LOG_LEVEL` trong `.env` không bị set thành
  `ERROR`/`WARNING`.
- **Forgot-password không gửi mail lúc demo** — bình thường nếu `SMTP_HOST`
  để trống trong `.env`, link reset chỉ log ra console backend (by design,
  xem comment `.env.example`).
