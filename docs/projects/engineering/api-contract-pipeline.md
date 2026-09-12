# API contract — đường ống 9 node, SSE và Calendar handoff

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Living — mô tả backend thật |
| Owner | Lê Thị Yến Nhi (UI/UX Lead) |
| Reviewers | Nguyễn Văn Phong (Technical Lead) · Thái Hoài An (PM) · Nguyễn Đức Dũng (PO/QC) |
| Last updated | 2026-08-14 |
| Related | [Architecture](architecture.md) · [Review database.sql](database-schema-review.md) · [ADR-002](adr/adr-002-connector-first-p0-scope.md) · [Evaluation plan](../qa/evaluation-plan.md) · `docs/architecture/architecture.drawio` |

Hình dạng dữ liệu giữa web app và backend cho trang `/run`. Bản cài đặt phía FE
nằm ở `client/web-app/src/types/pipeline.ts` và `client/web-app/src/lib/pipelineApi.ts`;
đổi `src/models/schemas.py` thì phải sửa hai file đó cùng lúc với tài liệu này.

Toàn bộ ví dụ dưới đây lấy từ backend chạy thật, không phải thiết kế trên giấy.

## 0. Quy ước chung

- Mọi endpoint nằm dưới `/api/v1`, xác thực bằng `Authorization: Bearer <access token>`.
- JSON là camelCase (`CamelModel` dùng `alias_generator=to_camel`).
- Mốc thời gian ISO 8601. FE **gửi kèm offset** (`2026-08-05T00:00:00+07:00`)
  vì node `resolve` cần offset thật để quy đổi cụm thời gian.
- FE chỉ lùi về fixture cho capability chưa hỗ trợ hoặc khi
  `VITE_PIPELINE_MOCK=1`, và luôn hiện băng vàng. Calendar handoff đã có backend
  thật nên lỗi route/auth phải hiện ra, không được âm thầm dựng `.ics` local.

## 1. Chọn nguồn

Hai họ endpoint, đừng nhầm:

| Endpoint | Dùng khi nào | Có `id` không |
| --- | --- | --- |
| `GET /connections` | Màn Thư viện nguồn: kết nối, ngắt kết nối, xem hạn token | Không |
| `GET /integrations` | Trang `/run`: chọn nguồn để chạy | **Có** — `POST /runs` cần id này |

```jsonc
// GET /api/v1/integrations
{ "integrations": [
  { "id": 1, "provider": "google",  "accountLabel": "nhi@gmail.com", "expiresAt": "2026-08-12T09:26:16.108259Z" },
  { "id": 2, "provider": "discord", "accountLabel": "nhi#1234",      "expiresAt": "2026-08-12T09:26:16.108259Z" }
] }
```

`provider` là `discord | google | telegram | jira`. Một integration `google`
đại diện cho OAuth connection dùng chung của **Gmail + Calendar**.

`jira` mới thêm ([kế hoạch](jira-connector-plan.md)) — OAuth 2.0 3LO, `sources`
trả về project Jira (`id` = project key, `name` = tên project). Cần
`JIRA_CLIENT_ID`/`JIRA_CLIENT_SECRET` (đăng ký app trên Atlassian Developer
Console) mới connect thật được — code đã sẵn, biến môi trường chưa cấu hình ở
môi trường nào.

Nguồn con của một integration — nhãn Gmail, kênh Discord:

```jsonc
// GET /api/v1/integrations/{id}/sources
{
  "sources": [
    { "id": "INBOX", "name": "Gmail · Hộp thư chính", "itemCount": 128 },
    { "id": "calendar:primary", "name": "Calendar · Lịch chính", "itemCount": null }
  ],
  "warnings": []
}
```

Calendar source có namespace để pipeline chọn đúng connector; Gmail giữ ID cũ
như `INBOX` và route về connector mặc định. Contract này tương thích ngược và
an toàn khi frontend/backend production rollout song song. Nếu token cũ thiếu
`calendar.readonly`, API trả nguồn Gmail kèm warning thay vì làm hỏng cả
integration.

Hiện chỉ provider `google` chạy. Provider khác trả `400`
`"Provider 'discord' chưa hỗ trợ list sources."` — FE bắt riêng `400` và `502`,
hiện dòng "backend chưa liệt kê được nguồn con của kênh này" thay vì báo lỗi đỏ.

**Hệ quả cho Checkpoint 3:** chưa có endpoint này cho Discord thì người dùng
không chọn được nguồn Discord, nên pipeline không chạy đồng thời hai nguồn
được. Đây là việc chặn, không phải việc dọn sau.

## 2. Tạo lần chạy

```jsonc
// POST /api/v1/runs  ->  201
{
  "sources": [{ "connectionId": 1, "sourceId": "INBOX" }],
  "timeFrom": "2026-08-02T00:00:00+07:00",
  "timeTo": "2026-08-05T23:59:59+07:00",
  "timezone": "Asia/Ho_Chi_Minh",
  "idempotencyKey": "1785921962-a1b2c3d4"
}
```

```jsonc
{ "id": 1, "status": "queued", "errorMessage": null, "createdAt": "2026-08-05T09:27:09.189240" }
```

`status` thuộc `queued | running | succeeded | failed`. Cùng `idempotencyKey`
trả lại run cũ, không chạy lại (unique `(user_id, idempotency_key)`).

## 2.1. Lựa chọn auto-sync

```text
GET   /api/v1/runs/auto-sync-preference
PATCH /api/v1/runs/auto-sync-preference
```

`PATCH` chỉ nhận lựa chọn của chính Bearer token, không nhận `userId`, nguồn,
nhịp chạy hoặc công tắc tổng. Đây là đường để rút lại đồng ý mà không cần ngắt
kết nối nguồn.

```jsonc
// PATCH body
{ "autoSyncEnabled": false }

// GET/PATCH response
{
  "autoSyncEnabled": false,     // hiệu lực = global AND lựa chọn user
  "userAutoSyncEnabled": false, // lựa chọn đã lưu của chính user
  "autoSyncIntervalMinutes": 180
}
```

`autoSyncEnabled` có thể là `false` trong khi `userAutoSyncEnabled` là `true`:
đó là lúc vận hành chưa bật `AUTO_SYNC_ENABLED`. FE phải phân biệt hai trạng
thái này, không suy đoán hay tự bật scheduler. Scheduler chỉ lặp lại bộ nguồn
của run thủ công thành công gần nhất theo [ADR-011](adr/adr-011-tu-dong-dong-bo-nen-va-han-muc-nguon.md).

## 3. Stream tiến trình

`GET /api/v1/runs/{id}/events`, `Content-Type: text/event-stream`.

FE đọc stream bằng `fetch` chứ không dùng `EventSource`, vì `EventSource` không
gắn được header `Authorization` và nhét token vào query string sẽ làm token lọt
vào access log.

Mỗi khung là một dòng `data: <json>` rồi một dòng trống:

```text
data: {"node": "fetch", "status": "ok", "count": 1680, "message": null, "at": "2026-08-05T09:27:09.220875"}

data: {"node": "done", "status": "ok", "count": 4, "message": null, "at": "2026-08-05T09:27:09.328234"}
```

Ba điểm khác với hình dung ban đầu, FE đã bám theo bản thật:

1. **Không có trường `type`.** Chỉ có `node`.
2. **`status` có `ok`, `error` và `item`** — không có `running`. Node đang
   chạy được suy ra là node kế tiếp node vừa xong.
3. **`node` có hai giá trị canh biên**: `done` khi chạy xong, `error` khi
   pipeline chết giữa chừng. Chín tên còn lại là `fetch`, `normalize`,
   `filter`, `make_batches`, `extract_batch`, `resolve`, `cluster`, `reduce`,
   `persist`.

`count` là số bản ghi ra khỏi node, dùng vẽ phễu.

**`status: "item"`** — chỉ `node: "fetch"` phát ra, bắn ngay trong lúc fetch
còn chạy (không đợi node return). `count` là số item đã tải được **trong 1
nguồn** tính đến thời điểm đó (không phải tổng toàn run), `message` dạng
`"[source_id] tiêu đề ngắn"` (Gmail: subject; Jira: summary). Ví dụ:

```text
data: {"node": "fetch", "status": "item", "count": 3, "message": "[INBOX] Nhắc nộp báo cáo tuần 3", "at": "..."}
```

Event `fetch`/`status: "ok"` như cũ vẫn bắn 1 lần cuối khi node `fetch` return
— đánh dấu đã lấy xong, `count` lúc đó là tổng toàn bộ nguồn cộng lại.

Stream **replay được**: mở lại `/events` sau khi run đã xong thì backend bắn
lại toàn bộ event đã ghi rồi đóng — kể cả các event `item` (ghi DB từng dòng
như event khác). F5 giữa chừng không mất tiến trình.

Việc và brief **không đi qua SSE**. Lấy sau khi stream đóng.

## 4. Việc đã trích xuất

```jsonc
// GET /api/v1/tasks
{ "tasks": [ {
  "id": 1,
  "clusterKey": "verify-key-1",
  "title": "Nộp bản đóng băng wireframe cho Gate 2",
  "detail": "",
  "dueAt": "2026-08-07T09:27:46.752593Z",
  "allDay": false,
  "ambiguous": true,
  "status": "proposed",
  "sourceCount": 2,
  "signalStrength": 0.67,
  "calendarEventId": null,
  "createdAt": "...", "updatedAt": "...",
  "evidence": [ {
    "id": 1, "messageId": null, "provider": "discord",
    "evidenceQuote": "Nhi gửi bản wireframe đóng băng trước 17h thứ sáu nhé.",
    "deepLink": "https://discord.com/channels/0/0/1"
  } ]
} ] }
```

Ràng buộc UI dựa vào:

- `evidenceQuote` phải là **nguyên văn** tin gốc. Hộp duyệt việc hiển thị nó
  làm bằng chứng; LLM viết lại là vi phạm ngưỡng unsupported claim trong
  [evaluation plan](../qa/evaluation-plan.md).
- `dueAt` được phép `null`. UI hiện "chưa nhận ra mốc thời gian" và **chặn nút
  Xác nhận** — không tự đoán.
- `ambiguous: true` nghĩa là node `resolve` không chắc mốc thời gian. UI hiện
  cảnh báo vàng ngay trên thẻ việc.
- `GET /tasks` trả **mọi** việc của user, không lọc theo run. Hộp duyệt việc
  vì thế cũng hiện việc còn tồn từ lần chạy trước — đúng ý "hộp chờ duyệt".

Duyệt việc:

```text
POST /api/v1/tasks/{id}/confirm   -> 200, status = "confirmed"
POST /api/v1/tasks/{id}/dismiss   -> 200, status = "dismissed"
```

Chỉ đi được từ `proposed`. Gọi lần hai trả `409` với
`"Task đang ở trạng thái 'confirmed', chỉ chuyển được từ 'proposed'."` — không
có đường quay lại, nên UI bỏ hẳn nút Hoàn tác.

Backend **chưa có** endpoint sửa việc. FE vì thế không cho sửa tiêu đề, ngày
hạn hay người phụ trách — sửa mà không lưu được thì tệ hơn là không cho sửa.

## 5. Brief

```jsonc
// GET /api/v1/runs/{id}/brief
{
  "id": 1, "runId": 1,
  "summary": "Tìm thấy 4 việc cần làm.",
  "topPriority": [ { "taskId": 1, "title": "...", "dueAt": "2026-08-07T10:00:00Z" } ],
  "scheduleConflicts": [],
  "createdAt": "..."
}
```

`topPriority` là 3 task có `signalStrength` cao nhất. `scheduleConflicts` vẫn
rỗng ở P0 vì thuật toán đối chiếu task với event chưa được triển khai; điều này
độc lập với Calendar connector và agent read tool đã hoạt động. FE phải nói
"chưa tính trùng lịch" thay vì để trống như thể đã kiểm tra xong.

Run lỗi giữa chừng thì chưa có brief và endpoint trả `404` — FE bỏ qua, không
coi là sự cố.

## 6. Calendar handoff — đã chạy thật

Chỉ task `confirmed` có `dueAt` mới được handoff. P0 không CRUD event bên ngoài
([ADR-002](adr/adr-002-connector-first-p0-scope.md)).

```text
GET  /api/v1/tasks/{id}/calendar-handoff
GET  /api/v1/tasks/{id}/calendar-handoff.ics
POST /api/v1/tasks/{id}/calendar-handoff/opened
```

```jsonc
{
  "taskId": 1,
  "icsUrl": "https://p004-api.duckdns.org/api/v1/tasks/1/calendar-handoff.ics",
  "googleCalendarUrl": "https://calendar.google.com/calendar/render?action=TEMPLATE&…",
  "opened": false,
  "openedAt": null
}
```

Endpoint `.ics` cần Bearer token, nên FE fetch có xác thực rồi mới tạo Blob URL
để tải. Sau click thật, FE gọi endpoint `opened`; mở lại file cũng ghi nhận lại.
Không còn fallback route `/api/v1/calendar/handoff` hoặc `templateUrl` cũ.

File `.ics` là UTF-8, thời gian UTC, escape text và fold physical line tối đa
75 octet theo RFC 5545.

## 7. Việc backend còn thiếu

| Việc | Chủ | Chặn cái gì |
| --- | --- | --- |
| `GET /integrations/{id}/sources` cho Discord | An | Không chọn được nguồn Discord nên pipeline không chạy đồng thời hai nguồn |
| Endpoint sửa việc (`PATCH /tasks/{id}`) | Phong | Người dùng không sửa được ngày hạn máy đọc sai — hiện chỉ nhận hoặc bỏ |

Điều kiện dừng Checkpoint 3 là "không mock". Khi các dòng trên xong, băng vàng
trên `/run` sẽ tự tắt — đó là dấu hiệu duyệt được bằng mắt.

## 8. Lỗi backend gặp khi kiểm chứng contract

Ghi lại để Phong xử, phát hiện lúc chạy thật ngày 2026-08-05:

1. **`GET /integrations/{id}/sources` trả 500** khi connection có
   `access_token_encrypted` là `NULL`: `AttributeError: 'NoneType' object has
   no attribute 'encode'`. Nên trả `4xx` kèm thông điệp "cần kết nối lại".
   Đáng chú ý vì kết nối Telegram **luôn** có token `NULL`
   (`_upsert_connection` gọi với `token_data=None`).
2. **500 chưa bắt làm mất header CORS**, nên trình duyệt chỉ thấy
   `Failed to fetch` và FE không hiện được lý do thật.
3. **Lỗi bị nhân bản sang node không liên quan.** `state["errors"]` cộng dồn và
   mọi node sau đều mang theo, nên `normalize` và `extract_batch` báo lỗi
   `fetch INBOX: ...` dù chúng không hỏng. UI vì thế tô đỏ nhầm node.
4. **Run vẫn `succeeded` dù `fetch` lỗi và không lấy được tin nào.** ADR-002
   mục 4 yêu cầu connector lỗi phải hiển thị trạng thái chưa đầy đủ. Nên có
   `partial` hoặc `failed`.
