# Review `src/database.sql`

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Đã xử lý phần lớn ở `bad686d` — xem [mục cập nhật](#cập-nhật-2026-08-05-sau-commit-bad686d) |
| Reviewer | Lê Thị Yến Nhi (UI/UX Lead) |
| Đối tượng review | `src/database.sql` tại commit `cc1cd28`, đối chiếu lại tại `bad686d` |
| Người cần đọc | Nguyễn Văn Phong (Technical Lead) · Thái Hoài An (PM) · Nguyễn Đức Dũng (PO/QC) |
| Last updated | 2026-08-05 |
| Related | [API contract pipeline](api-contract-pipeline.md) · [Architecture](architecture.md) · [ADR-002](adr/adr-002-connector-first-p0-scope.md) · [Evaluation plan](../qa/evaluation-plan.md) · `docs/architecture/architecture.drawio` |

Review từ góc nhìn FE: web app cần gì để bỏ được dữ liệu giả ở trang `/run`,
và Checkpoint 1–3 cần gì để Dũng chấm được.

## Cập nhật 2026-08-05 sau commit `bad686d`

Phần lớn review dưới đây đã được xử lý. Giữ nguyên nội dung gốc để đối chiếu;
bảng này là trạng thái hiện tại.

### Đã sửa

| Mục review | Cách sửa ở `bad686d` |
| --- | --- |
| `connections.user_id` lệch kiểu với model | `VARCHAR(128)` thống nhất |
| `tasks.cluster_key` unique toàn cục | `uq_task_user_cluster_key (user_id, cluster_key)` |
| `clusters.cluster_key` unique toàn cục | `uq_cluster_user_cluster_key (user_id, cluster_key)` |
| `sync_cursors.key` không có `user_id` | `uq_sync_cursor_user_key (user_id, key)` |
| Không có index | 12 index, có đúng `ix_messages_user_sent_at` |
| `messages.deep_link NOT NULL` ép bịa link | Cho `NULL` |
| Thiếu `runs`, `briefs`, `run_node_events` | Đủ cả ba; `runs` có `uq_run_user_idempotency_key` |
| Hai nguồn sự thật schema | Chốt SQLAlchemy models là chuẩn; `src/database.sql` thành snapshot generate lại, header ghi rõ lệnh generate |

### Còn lại

| Vấn đề | Vì sao cần xử |
| --- | --- |
| `user_id` lẫn hai kiểu | `runs.user_id` và `briefs.user_id` là `INTEGER` + FK `users(id)`; `tasks`/`messages`/`clusters`/`connections`/`sync_cursors` là `VARCHAR(128)` **không FK**. Xóa user thì `runs`/`briefs` cascade còn `tasks`/`messages` thành mồ côi |
| `task_evidence.deep_link` vẫn `NOT NULL` | `messages.deep_link` giờ nullable. Message không có link thì insert evidence chết |
| Cột `embedding VECTOR(1536)` biến mất | Drawio ghi cluster gộp bằng vector nhúng; hiện `cluster_node` chỉ dùng fuzzy title + gần ngày. Cắt hẳn hay hoãn thì nên ghi ADR |
| Thiếu `content_hash` và version | Roadmap tuần 2 exit gate là "nguồn thay đổi → phiên bản mới"; chưa có gì để đo |
| Thiếu bảng `batch` | Extract lỗi không chạy lại được riêng một lô |
| Thiếu `keep`/`score`/`matched_signals` (filter) | Dũng không có cột nào để chấm "lọc đúng loại tin rác" |
| Thiếu `time_expression`/`assignee_hint`/`confidence` đã persist | `ExtractedSignal` trong `src/agents/pipeline/schemas.py` có đủ ba trường, nhưng persist bỏ hết, chỉ giữ `evidence_quote`. Hộp duyệt việc không hiện được máy đọc ra gì so với máy tính ra gì |
| `clusters` và `tasks` vẫn trùng cột | `cluster_key`, `due_at`, `ambiguous`, `signal_strength` nằm cả hai nơi |
| `scripts/_backend_test.log.err` bị commit | File log, nên gitignore |

### Lỗi runtime phát hiện khi kiểm chứng

Chi tiết ở [API contract mục 8](api-contract-pipeline.md#8-lỗi-backend-gặp-khi-kiểm-chứng-contract):
`/integrations/{id}/sources` trả 500 khi token `NULL`; 500 chưa bắt làm mất
header CORS; lỗi của `fetch` bị nhân bản sang node khác; run vẫn `succeeded` dù
`fetch` hỏng và không lấy được tin nào.

## Cái đang tốt

- `messages` unique `(provider, source_id, external_id)` — chặn duplicate khi
  connector gửi lại, đúng yêu cầu "retry không tạo bản trùng".
- `task_evidence` giữ `evidence_quote` + `deep_link` — có provenance cho từng
  việc, đúng yêu cầu mọi factual item phải có citation.
- `messages.is_self` và `is_dm` — khớp luật lọc ở tầng 1 trong drawio.
- FK có `ON DELETE CASCADE` — xóa user là dọn sạch, hợp với yêu cầu retention.

## 1. Sai — chạy là hỏng

| Chỗ | Sai gì | Hệ quả | Sửa |
| --- | --- | --- | --- |
| `connections.user_id INTEGER` | Model Python khai `String(128)` (`src/models/connection.py:18`), `deps.py` trả `str` | Postgres ném `column "user_id" is of type integer but expression is of type character varying`. Kết nối Discord/Gmail chết ngay | Chốt một kiểu: model đổi sang `int`, hoặc SQL đổi sang `VARCHAR(128)` |
| `messages.embedding VECTOR(1536)` | Thiếu `CREATE EXTENSION IF NOT EXISTS vector;` | File SQL đứt giữa chừng trên database trắng | Thêm dòng extension đầu file, **và** đổi image trong `docker-compose.yml` từ `postgres:16-alpine` sang `pgvector/pgvector:pg16` |
| `tasks.cluster_key ... UNIQUE` | Unique toàn cục, không kèm `user_id` | Hai user cùng có việc "Nộp wireframe thứ sáu" sinh cùng hash. Nhẹ thì insert fail, nặng thì gộp nhầm việc của hai người | `UNIQUE (user_id, cluster_key)` |
| `clusters.cluster_key ... UNIQUE` | Như trên | Như trên | `UNIQUE (user_id, cluster_key)` |
| `sync_cursors.key ... UNIQUE` | Không có `user_id` | Hai user cùng đọc Discord ghi đè cursor của nhau; người sau nuốt mất tin của người trước | Thêm `user_id`, unique `(user_id, provider, source_id)` |
| `messages.deep_link NOT NULL` | Gmail và Telegram không phải lúc nào cũng dựng được link | Code buộc phải bịa link giả mới insert qua được | Cho phép `NULL`. FE đã xử lý trường hợp thiếu link (ẩn nút xem nguồn) |

Hai dòng `cluster_key` và dòng `sync_cursors` đều là lỗi cross-user.
[Evaluation plan](../qa/evaluation-plan.md#5-release-thresholds) để ngưỡng
cross-user leak = 0 và event loss = 0, nên ba dòng này là blocker phát hành,
không phải việc dọn sau.

## 2. Thiếu

### Thiếu bảng

| Bảng | Không có thì sao |
| --- | --- |
| `runs` | Không có `run_id` thì `GET /runs/{id}/events` không bám vào đâu. `idempotencyKey` không có chỗ lưu nên bấm hai lần là chạy hai lần |
| `briefs` | Node 9 `persist` không lưu được `summary` / `top_priority` / `schedule_conflicts`, không trả được `briefingId` cho FE |
| `run_node_events` | User F5 giữa chừng là mất sạch tiến trình, SSE không replay được các node đã xong |
| `batch` | Extract lỗi thì không chạy lại riêng một lô, không truy được lô nào làm tụt recall. Drawio ghi rõ cắt lô là thứ đẩy recall từ 0,43 lên 0,88 — không đo lại được thì mất luôn bằng chứng đó |

### Thiếu cột

| Node | Cột thiếu | Không có thì sao |
| --- | --- | --- |
| 3 `filter` | `keep`, `score`, `matched_signals` | Dũng không có cột nào để assert cho test "lọc đúng loại tin rác" ở Checkpoint 1 |
| 5 `extract_batch` | `time_phrase`, `assignee_hint`, `confidence` | Hộp duyệt việc không phân biệt được "LLM đọc ra chữ *thứ sáu tuần sau*" với "resolve tính ra 07/08 17:00". Đây đúng chỗ bịa deadline hay xảy ra, mà điều kiện dừng Checkpoint 2 ghi rõ "không tự bịa deadline/assignee" |
| 6 `resolve` | `keep` (việc của người khác), `assignee` đã đối chiếu identity table | Không tách được việc của mình và việc của người khác |
| 1–2 `fetch`/`normalize` | `content_hash`, version | Tin gốc bị sửa thì không phát hiện được. Roadmap tuần 2 exit gate là "nguồn thay đổi → phiên bản mới"; hiện không có gì để đo |

### Thiếu linh tinh

- Index: `messages(user_id, sent_at)` cho truy vấn theo khoảng thời gian,
  `tasks(user_id, status)`, `cluster_messages(message_id)`. Hiện chỉ có PK và
  unique.
- `DEFAULT now()` cho các cột timestamp `NOT NULL`, và trigger cho
  `tasks.updated_at`.
- Cột xóa mềm / retention.
- RLS. [Architecture §7](architecture.md) coi RLS là defense-in-depth. Nếu bỏ
  vì đã rời Supabase thì ghi thành quyết định, đừng để rơi im lặng.

## 3. Nhầm về kiến trúc

**Gộp ba tầng thành một bảng.** Bảng checkpoint yêu cầu `raw_message` →
`normalized_message` → `filtered_message` tách riêng. File này gộp hết vào
`messages`. Mất dấu vết từng tầng làm gì, nên không trả lời được câu "tại sao
tin này bị loại". Cái phễu 1.680 → 90 mất luôn bằng chứng.

**`tasks` đang gánh ba vai.** Vừa là `extracted_item`, vừa là `resolved_item`,
vừa là kết quả cluster. Ba thứ này sinh ra ở ba node khác nhau với độ tin cậy
khác nhau. Nhét chung một bảng thì không phân biệt được cái nào máy đoán, cái
nào máy tính ra — đúng thứ mà hộp duyệt việc phải hiển thị khác nhau.

**`clusters` và `tasks` chép trùng nhau.** Cả hai đều có `cluster_key`,
`due_at`, `ambiguous`, `signal_strength`, lại trỏ vòng qua `clusters.task_id`.
Sửa một bên là bên kia lệch. Chọn một bảng làm chủ.

## 4. Conflict — hai nguồn nói khác nhau

| Nguồn A | Nguồn B | Lệch chỗ nào |
| --- | --- | --- |
| `src/database.sql` | `src/models/*.py` + `Base.metadata.create_all()` tại `src/main.py:23` | Hai schema cùng tồn tại và đã lệch: `connections.user_id` khác kiểu; `users.last_synced_at` và `connections.provider_user_id` chỉ có ở SQL |
| `src/database.sql` | Không có gì nạp nó | `grep database.sql` toàn repo được 0 kết quả. `docker-compose.yml` không mount `/docker-entrypoint-initdb.d`. File hiện chỉ là bản vẽ, không phải schema đang chạy |
| Bảng checkpoint hai tuần (8 bảng pipeline) | File SQL (8 bảng khác tên, khác nghĩa) | Không map 1-1. Dũng chấm theo bảng nào? |
| [Architecture](architecture.md) — Supabase, `source_items`, RLS, 5 connector | File này — Postgres thuần, `messages`, không RLS, 3 nguồn | Chưa ai chốt. Gate 2 checklist còn đòi "Brief → Ask → Act" trong khi bảng hai tuần bỏ Ask |

## Ba bảng FE đang chờ

Đúng theo [API contract](api-contract-pipeline.md) mục 2, 3 và 5:

```sql
CREATE TABLE runs (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  sources VARCHAR(32)[] NOT NULL,
  range_from TIMESTAMPTZ NOT NULL,
  range_to TIMESTAMPTZ NOT NULL,
  idempotency_key VARCHAR(128) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'queued',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT runs_idem_unique UNIQUE (user_id, idempotency_key)
);

CREATE TABLE run_node_events (
  id SERIAL PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  node VARCHAR(32) NOT NULL,
  status VARCHAR(16) NOT NULL,
  count INTEGER,
  message TEXT,
  at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE briefs (
  id SERIAL PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  summary TEXT NOT NULL,
  top_priority JSONB NOT NULL DEFAULT '[]',
  schedule_conflicts JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Và thêm vào `tasks` (hoặc tách hẳn bảng `extracted_item` nếu chọn cách tách
tầng): `time_phrase VARCHAR(255)`, `assignee_hint VARCHAR(255)`,
`assignee VARCHAR(255)`, `confidence VARCHAR(16)`, `keep BOOLEAN`.

## Thứ tự sửa đề xuất

1. **Chốt nguồn sự thật cho schema** — `database.sql` hay SQLAlchemy models.
   Không chốt thì mọi mục dưới đây vô nghĩa vì sẽ phải làm hai lần.
2. Sáu dòng ở mục 1 (Sai). Ba trong sáu dòng là lỗi cross-user, chặn phát hành.
3. Thêm `runs`, `briefs`, `run_node_events` — FE bỏ được dữ liệu giả ở `/run`.
4. Thêm cột filter/extract/resolve — Dũng chấm được Checkpoint 1 và 2.
5. Index, `content_hash`, version.

## Trạng thái FE khi viết review này

Trang `/run` đã dựng xong toàn bộ luồng chọn nguồn → tiến trình 9 node → hộp
duyệt việc → brief → Xác nhận mở `.ics`.

- `GET /api/v1/connections` đang gọi thật, chạy đúng.
- `POST /api/v1/runs` trả 404 nên FE lùi về fixture cục bộ và hiện băng vàng
  "Đang hiển thị dữ liệu mẫu".

Băng vàng đó tự tắt khi bốn endpoint trong
[API contract mục 7](api-contract-pipeline.md#7-việc-phía-backend-còn-thiếu)
chạy thật. Đó là cách kiểm tra bằng mắt cho điều kiện dừng "không mock" của
Checkpoint 3.
