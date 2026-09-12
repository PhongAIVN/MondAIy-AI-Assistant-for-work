# Fix: UniqueViolation cluster_messages_pkey khi resync/overlap fetch

## Mục tiêu

Fix lỗi production:

```
(psycopg2.errors.UniqueViolation) duplicate key value violates unique
constraint "cluster_messages_pkey"
DETAIL: Key (cluster_id, message_id)=(58, 277) already exists.
```

## Agent/lane và ownership

1 agent, sửa trực tiếp trên `main` checkout (không có lane song song, bug fix
đơn giản, 1 file nguồn + 1 file test).

## Base/head

- Base: `76f9970` (HEAD lúc bắt đầu, chưa có commit mới nào).
- Chưa commit — thay đổi đang ở working tree.

## Nguyên nhân

`src/agents/pipeline/nodes/persist.py::persist_node` dùng pattern
SELECT-rồi-INSERT để dedupe `ClusterMessage` trong vòng lặp `for item in
cluster_data["items"]`. `SessionLocal` (`src/db.py`) cấu hình
`autoflush=False`, nên nếu `cluster_data["items"]` chứa 2 item cùng
`message_id` (message xuất hiện lại giữa các batch, ví dụ overlap khoảng
fetch hoặc resync), SELECT ở lần lặp thứ 2 KHÔNG thấy `ClusterMessage` vừa
`db.add()` ở lần lặp trước (chưa flush) → add trùng → khi `db.commit()`,
SQLAlchemy gom 2 object mới cùng mapper vào 1 câu INSERT nhiều value →
Postgres báo `UniqueViolation` trên PK composite `(cluster_id, message_id)`.

`TaskEvidence` có cùng lỗ hổng (không có check dedupe nào), tuy không có
unique constraint nên không throw, nhưng âm thầm ghi trùng evidence cho
cùng 1 message khi task mới tạo.

## Hành vi thay đổi

`persist_node`: thay SELECT-per-item bằng 1 lần SELECT lấy `message_id` đã
link cho cluster đó, giữ trong set Python, dedupe trong bộ nhớ trong suốt
vòng lặp — không phụ thuộc autoflush của session. Áp dụng cùng cách cho
`TaskEvidence` (dedupe theo `message_id` trong phạm vi 1 lần persist).

## File chính

- `src/agents/pipeline/nodes/persist.py` — logic dedupe.
- `tests/test_agents/v1/pipeline/nodes/test_persist.py` — thêm
  `test_persist_dedupes_same_message_appearing_twice_in_one_cluster`.

## Test đã chạy

```
.venv/Scripts/python -m pytest tests/test_agents/v1/pipeline/nodes/test_persist.py -v
# 5 passed

.venv/Scripts/python -m pytest tests/test_agents/ -q
# 238 passed, 1 skipped
```

Đã xác nhận test regression tái hiện đúng lỗi khi stash lại bản sửa
(`sqlite3.IntegrityError: UNIQUE constraint failed:
cluster_messages.cluster_id, cluster_messages.message_id`) — cùng bản chất
lỗi Postgres user báo, trước khi confirm fix hoạt động.

## Phần chưa chạy

- Chưa truy được log/run cụ thể nào đã tạo ra `(cluster_id, message_id) =
  (58, 277)` trên production (không có quyền truy DB production trong phiên
  này) — fix xử lý đúng lớp lỗi (duplicate item trong 1 cluster) bất kể
  nguồn gốc cụ thể là overlap fetch window, resync, hay batch nào khác gây
  duplicate message trong `resolved`/`clusters`.
- Chưa lint/typecheck riêng (ruff/mypy) — chỉ chạy pytest.

## Risk

Thấp. Thay SELECT N lần bằng 1 SELECT + set trong bộ nhớ — hành vi dedupe
tương đương hoặc chặt hơn bản cũ (bản cũ dedupe được với autoflush=True
nhưng vỡ với autoflush=False; bản mới dedupe đúng trong cả 2 trường hợp).

## Migration/config

Không.

## Merge/deploy status

Chưa commit, chưa deploy. Cần user xác nhận trước khi commit/push/deploy
theo AGENTS.md.

## Rollback

`git checkout -- src/agents/pipeline/nodes/persist.py
tests/test_agents/v1/pipeline/nodes/test_persist.py` nếu cần revert (chưa
commit nên chỉ cần discard working tree).

## Follow-up

- Cân nhắc thêm unique constraint hoặc `ON CONFLICT DO NOTHING`-style upsert
  cho `TaskEvidence` nếu muốn chặn ở tầng DB thay vì chỉ ở tầng
  application.
- Điều tra thêm nguồn gốc duplicate message trong `resolved`/`clusters` nếu
  muốn fix từ gốc (không bắt buộc — fix hiện tại đã an toàn ở persist layer).
