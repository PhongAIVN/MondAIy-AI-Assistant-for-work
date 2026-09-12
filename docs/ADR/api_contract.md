# API Contract: mondaiy P0

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Proposed |
| Date | 2026-08-06 |
| Owner | Thái Hoài An (PM), Tech Lead |
| Scope | API contract cho mondaiy P0 |
| Version | v0.1 |
| Related | PRD mondaiy, ADR-003 Test-driven connector-first, UI flow P0 |

---

## 1. Mục đích

Tài liệu này định nghĩa **API contract** cho mondaiy P0. Mục tiêu là thống nhất cách frontend, backend, connector worker, AI orchestration và evaluation giao tiếp với nhau.

API contract này không phải tài liệu domain split. Nó chỉ mô tả:

- endpoint nào tồn tại;
- request/response shape;
- trạng thái hợp lệ;
- lỗi chuẩn;
- quy tắc quyền truy cập;
- quy tắc idempotency;
- contract cho các tool AI được phép dùng;
- các điều kiện nghiệm thu API.

---

## 2. Phạm vi

### 2.1 Trong phạm vi P0

API contract này bao phủ các nhóm API sau:

1. Authentication context
2. Profile và user context
3. Consent và source connection
4. Source sync status
5. Evidence và citation
6. Memory candidate và confirmed memory
7. Program context
8. Briefing
9. Ask / conversation
10. Action draft / reminder / calendar handoff
11. Data & Privacy
12. Audit trail
13. Feedback
14. Evaluation export
15. AI tool contract nội bộ

### 2.2 Ngoài phạm vi

Các API sau **không có trong P0**:

- Desktop app API.
- Mobile app API riêng.
- API đọc toàn bộ ngữ cảnh sử dụng trên máy.
- API theo dõi màn hình.
- API đọc lịch sử duyệt web.
- API đọc cookie, mật khẩu hoặc session trình duyệt.
- API đọc nội dung trang web bất kỳ.
- API Messenger, Zalo, Facebook Messenger.
- API tự gửi tin nhắn.
- API tự tạo, sửa hoặc xóa calendar event bên ngoài mà không có xác nhận người dùng.
- API để admin xem raw private content của người dùng.

---

## 3. Nguyên tắc API

### 3.1 Evidence-first

Mọi dữ liệu factual trả ra cho người dùng phải có `citation_ids` hoặc trạng thái rõ ràng là `abstained`, `uncertain`, `partial`, `unknown`.

API không được trả về claim chắc chắn nếu claim đó không có evidence người dùng còn quyền mở.

### 3.2 Consent-first

Mọi API đọc dữ liệu nguồn, search evidence, sinh briefing, trả lời câu hỏi hoặc tạo action draft phải kiểm tra quyền truy cập hiện tại.

Dữ liệu đã revoke hoặc delete không được xuất hiện trong retrieval mới.

### 3.3 User-confirmed action

API chỉ được tạo bản nháp hành động trước. Không API nào được thực hiện hành động bên ngoài trước khi người dùng xác nhận.

Luồng bắt buộc:

```text
create draft
→ preview
→ user edits if needed
→ user confirms
→ create in-app reminder or calendar handoff / .ics
```

### 3.4 Idempotency

Các API có thể bị gọi lặp phải hỗ trợ `Idempotency-Key`.

Bắt buộc với:

- source sync ingest;
- create memory candidate;
- create action draft;
- confirm action;
- create reminder;
- open calendar handoff;
- delete/revoke request.

### 3.5 Không log raw private content

Product analytics, audit event và error log không được lưu:

- raw email body;
- raw Discord message;
- raw Gmail thread;
- raw user question;
- raw answer;
- token;
- cookie;
- password;
- private file content.

---

## 4. Chuẩn chung

### 4.1 Base URL

```text
/api/v1
```

### 4.2 Content type

```http
Content-Type: application/json
Accept: application/json
```

### 4.3 Authentication

Frontend gọi API bằng session hiện tại của Supabase/Auth provider.

```http
Authorization: Bearer <user_session_token>
```

Service-to-service dùng service token nội bộ, chỉ nằm ở server.

```http
Authorization: Bearer <internal_service_token>
X-Service-Name: connector-worker | ai-orchestrator | evaluation-runner
```

### 4.4 Correlation ID

Mọi request nên có:

```http
X-Request-ID: req_...
```

Response phải trả lại:

```http
X-Request-ID: req_...
```

### 4.5 Idempotency key

Với write API quan trọng:

```http
Idempotency-Key: idem_...
```

Nếu cùng một key được gửi lại với cùng payload, API phải trả về cùng kết quả logic, không tạo bản ghi trùng.

Nếu cùng một key được gửi lại với payload khác, API trả lỗi `409 IDEMPOTENCY_KEY_CONFLICT`.

---

## 5. Kiểu dữ liệu chuẩn

### 5.1 ID format

```text
user_id: usr_...
profile_id: prof_...
source_id: src_...
connection_id: conn_...
evidence_id: evd_...
citation_id: cit_...
memory_id: mem_...
brief_id: brf_...
conversation_id: conv_...
message_id: msg_...
action_draft_id: actd_...
reminder_id: rem_...
audit_event_id: aud_...
```

### 5.2 Timestamp

Tất cả timestamp dùng ISO 8601.

```json
"2026-08-06T23:30:00+07:00"
```

### 5.3 Pagination

Request:

```json
{
  "limit": 20,
  "cursor": "cur_next_page"
}
```

Response:

```json
{
  "items": [],
  "next_cursor": "cur_next_page_or_null"
}
```

### 5.4 Coverage status

```ts
type CoverageStatus = "complete" | "partial" | "unknown";
```

### 5.5 Confidence

```ts
type Confidence = "certain" | "possible" | "ask_mentor";
```

### 5.6 Source type

```ts
type SourceType = "calendar" | "jira" | "discord" | "vlearn" | "gmail" | "manual";
```

### 5.7 Source status

```ts
type SourceStatus =
  | "not_connected"
  | "connected"
  | "syncing"
  | "paused"
  | "error"
  | "revoked";
```

### 5.8 Action draft status

```ts
type ActionDraftStatus =
  | "drafted"
  | "previewed"
  | "confirmed"
  | "handoff_opened"
  | "completed"
  | "cancelled";
```

### 5.9 Answer kind

```ts
type AnswerKind = "answered" | "abstained" | "uncertain" | "conflict";
```

---

## 6. Error contract

### 6.1 Error response shape

```json
{
  "error": {
    "code": "ACCESS_DENIED",
    "message": "User does not have access to this source.",
    "details": {
      "source_id": "src_123"
    },
    "request_id": "req_123"
  }
}
```

### 6.2 Error codes

| HTTP | Code | Ý nghĩa |
| --- | --- | --- |
| 400 | `BAD_REQUEST` | Request thiếu hoặc sai field |
| 401 | `UNAUTHENTICATED` | Chưa đăng nhập hoặc token không hợp lệ |
| 403 | `ACCESS_DENIED` | Không có quyền truy cập |
| 404 | `NOT_FOUND` | Không tìm thấy resource hoặc resource không thuộc user |
| 409 | `IDEMPOTENCY_KEY_CONFLICT` | Idempotency key trùng nhưng payload khác |
| 409 | `STATE_CONFLICT` | Trạng thái hiện tại không cho phép thao tác |
| 422 | `VALIDATION_ERROR` | Dữ liệu hợp lệ JSON nhưng không đạt rule nghiệp vụ |
| 424 | `SOURCE_UNAVAILABLE` | Nguồn ngoài lỗi hoặc chưa đồng bộ được |
| 429 | `RATE_LIMITED` | Vượt giới hạn |
| 500 | `INTERNAL_ERROR` | Lỗi hệ thống |

---

## 7. API: Profile và user context

### 7.1 Get current user context

```http
GET /api/v1/me/context
```

#### Response

```json
{
  "user": {
    "id": "usr_123",
    "display_name": "An",
    "timezone": "Asia/Ho_Chi_Minh"
  },
  "profile": {
    "id": "prof_123",
    "role": "student",
    "goals": ["hoàn thành milestone tuần này"],
    "support_preferences": ["nhắc deadline", "nêu thay đổi quan trọng"]
  },
  "program": {
    "program_id": "pgm_123",
    "team_id": "team_123",
    "role_ids": ["role_pm"]
  }
}
```

### 7.2 Update profile

```http
PATCH /api/v1/me/profile
```

#### Request

```json
{
  "display_name": "An",
  "timezone": "Asia/Ho_Chi_Minh",
  "role": "student",
  "goals": ["hoàn thành Gate 2"],
  "support_preferences": ["daily brief lúc sáng", "cảnh báo mâu thuẫn"]
}
```

#### Response

```json
{
  "profile_id": "prof_123",
  "version_id": "profv_456",
  "updated_at": "2026-08-06T23:30:00+07:00"
}
```

#### Rules

- Mỗi lần sửa profile phải tạo version mới.
- Không được dùng profile cũ sau khi user sửa trong retrieval mới.

---

## 8. API: Consent và source connection

### 8.1 List source connections

```http
GET /api/v1/sources
```

#### Response

```json
{
  "items": [
    {
      "source_id": "src_calendar_123",
      "type": "calendar",
      "display_name": "Google Calendar",
      "status": "connected",
      "scope_summary": "Read events from selected calendars",
      "last_successful_sync_at": "2026-08-06T22:10:00+07:00",
      "last_attempt_at": "2026-08-06T22:10:00+07:00",
      "coverage": "complete"
    }
  ]
}
```

### 8.2 Create source connection request

```http
POST /api/v1/sources/connect
```

#### Request

```json
{
  "type": "gmail",
  "requested_scopes": ["read_threads", "read_labels"],
  "return_url": "https://app.mondaiy.local/sources/callback"
}
```

#### Response

```json
{
  "connection_request_id": "connreq_123",
  "authorization_url": "https://provider.example/oauth?...",
  "expires_at": "2026-08-06T23:40:00+07:00"
}
```

#### Rules

- API chỉ tạo request cấp quyền.
- Không được lưu token nếu OAuth callback chưa hợp lệ.
- Requested scopes phải là read-only trong P0.

### 8.3 Revoke source consent

```http
POST /api/v1/sources/{source_id}/revoke
Idempotency-Key: idem_revoke_123
```

#### Request

```json
{
  "reason": "user_requested",
  "delete_existing_data": false
}
```

#### Response

```json
{
  "source_id": "src_gmail_123",
  "status": "revoked",
  "sync_stopped": true,
  "effective_at": "2026-08-06T23:30:00+07:00"
}
```

#### Rules

- Revoke phải dừng sync mới.
- Retrieval mới không được dùng dữ liệu từ source đã revoke.
- Nếu `delete_existing_data = true`, phải tạo deletion request riêng và audit event.

### 8.4 Pause source sync

```http
POST /api/v1/sources/{source_id}/pause
Idempotency-Key: idem_pause_123
```

#### Response

```json
{
  "source_id": "src_discord_123",
  "status": "paused",
  "paused_at": "2026-08-06T23:30:00+07:00"
}
```

### 8.5 Resume source sync

```http
POST /api/v1/sources/{source_id}/resume
Idempotency-Key: idem_resume_123
```

#### Response

```json
{
  "source_id": "src_discord_123",
  "status": "connected",
  "resumed_at": "2026-08-06T23:31:00+07:00"
}
```

---

## 9. API: Source sync ingest nội bộ

Các API này chỉ dành cho connector worker.

### 9.1 Ingest source item

```http
POST /api/v1/internal/ingest/source-items
Authorization: Bearer <internal_service_token>
X-Service-Name: connector-worker
Idempotency-Key: idem_ingest_123
```

#### Request

```json
{
  "user_id": "usr_123",
  "source_id": "src_jira_123",
  "source_type": "jira",
  "external_id": "TAPB-42",
  "external_url": "https://jira.example/browse/TAPB-42",
  "source_updated_at": "2026-08-06T21:00:00+07:00",
  "observed_at": "2026-08-06T21:05:00+07:00",
  "content_hash": "sha256:abc123",
  "title": "Finalize API contract",
  "raw_content_ref": "storage://source-items/usr_123/TAPB-42.json",
  "normalized": {
    "kind": "task",
    "status": "in_progress",
    "due_at": "2026-08-09T23:59:00+07:00",
    "assignee": "An"
  }
}
```

#### Response

```json
{
  "evidence_id": "evd_123",
  "information_item_id": "info_123",
  "version_id": "infov_456",
  "duplicate": false,
  "version_created": true,
  "stored_at": "2026-08-06T21:05:01+07:00"
}
```

#### Rules

- Phải kiểm tra source consent còn hiệu lực trước khi lưu.
- Cùng `source_id + external_id + content_hash` không tạo version trùng.
- Nếu `content_hash` khác version trước, tạo version mới.
- Connector không được tự tạo memory hoặc brief.

### 9.2 Report sync run

```http
POST /api/v1/internal/sync-runs
Authorization: Bearer <internal_service_token>
X-Service-Name: connector-worker
```

#### Request

```json
{
  "source_id": "src_gmail_123",
  "status": "partial",
  "started_at": "2026-08-06T22:00:00+07:00",
  "finished_at": "2026-08-06T22:00:30+07:00",
  "items_seen": 40,
  "items_stored": 7,
  "duplicates": 33,
  "error_class": "RATE_LIMIT",
  "retry_after_seconds": 300
}
```

#### Response

```json
{
  "sync_run_id": "syncrun_123",
  "source_id": "src_gmail_123",
  "coverage": "partial"
}
```

---

## 10. API: Evidence và citation

### 10.1 Search evidence

```http
POST /api/v1/evidence/search
```

#### Request

```json
{
  "query": "deadline Gate 2 là khi nào?",
  "filters": {
    "source_types": ["jira", "vlearn", "discord", "gmail", "calendar"],
    "program_id": "pgm_123",
    "from": "2026-08-01T00:00:00+07:00",
    "to": "2026-08-06T23:59:59+07:00"
  },
  "limit": 10
}
```

#### Response

```json
{
  "items": [
    {
      "evidence_id": "evd_123",
      "citation_id": "cit_123",
      "source_type": "vlearn",
      "source_name": "VLearn",
      "title": "Gate 2 submission",
      "snippet": "Deadline Gate 2: 2026-08-09 23:59 ICT",
      "source_updated_at": "2026-08-05T10:00:00+07:00",
      "observed_at": "2026-08-05T10:05:00+07:00",
      "confidence": "certain",
      "open_url": "https://vlearn.example/item/123"
    }
  ],
  "coverage": {
    "status": "partial",
    "checked_sources": ["vlearn", "jira"],
    "missing_sources": ["gmail"],
    "reason": "Gmail sync is currently rate limited."
  }
}
```

#### Rules

- Chỉ trả evidence user còn quyền mở.
- Nếu source đã revoke/delete, evidence không được xuất hiện.
- `snippet` phải đủ ngắn, phục vụ kiểm chứng, không thay thế raw private content.

### 10.2 Get evidence detail

```http
GET /api/v1/evidence/{evidence_id}
```

#### Response

```json
{
  "evidence_id": "evd_123",
  "source_type": "jira",
  "source_name": "Jira TAPB",
  "external_id": "TAPB-42",
  "external_url": "https://jira.example/browse/TAPB-42",
  "title": "Finalize API contract",
  "content_excerpt": "Finalize API contract by Sunday.",
  "source_updated_at": "2026-08-06T21:00:00+07:00",
  "observed_at": "2026-08-06T21:05:00+07:00",
  "version": {
    "version_id": "infov_456",
    "status": "current",
    "supersedes_version_id": "infov_123"
  },
  "citation": {
    "citation_id": "cit_123",
    "claim_supported": true
  }
}
```

#### Rules

- Nếu user không còn quyền mở evidence, trả `404 NOT_FOUND` hoặc `403 ACCESS_DENIED` theo policy bảo mật.
- Không trả token hoặc raw credential.

---

## 11. API: Memory

### 11.1 List memories

```http
GET /api/v1/memories?status=confirmed&limit=20
```

#### Response

```json
{
  "items": [
    {
      "memory_id": "mem_123",
      "kind": "user_preference",
      "subject": "usr_123",
      "predicate": "prefers_briefing_time",
      "object": {
        "time": "08:00",
        "timezone": "Asia/Ho_Chi_Minh"
      },
      "status": "confirmed",
      "confidence": "certain",
      "evidence_ids": ["evd_123"],
      "valid_from": "2026-08-01T00:00:00+07:00",
      "valid_to": null
    }
  ]
}
```

### 11.2 Create memory candidate

```http
POST /api/v1/internal/memory-candidates
Authorization: Bearer <internal_service_token>
X-Service-Name: ai-orchestrator
Idempotency-Key: idem_memcand_123
```

#### Request

```json
{
  "user_id": "usr_123",
  "kind": "commitment",
  "subject": "usr_123",
  "predicate": "committed_to",
  "object": {
    "task": "submit Gate 2 API contract",
    "due_at": "2026-08-09T23:59:00+07:00"
  },
  "confidence": "possible",
  "evidence_ids": ["evd_123"],
  "extractor_version": "extractor_0.1"
}
```

#### Response

```json
{
  "memory_candidate_id": "memcand_123",
  "status": "proposed"
}
```

#### Rules

- Candidate phải có ít nhất một `evidence_id` hoặc `user_confirmation_ref`.
- Candidate không được hiển thị như fact đã xác nhận.

### 11.3 Confirm memory

```http
POST /api/v1/memories/{memory_id}/confirm
Idempotency-Key: idem_confirm_mem_123
```

#### Response

```json
{
  "memory_id": "mem_123",
  "status": "confirmed",
  "confirmed_at": "2026-08-06T23:30:00+07:00"
}
```

### 11.4 Reject memory

```http
POST /api/v1/memories/{memory_id}/reject
Idempotency-Key: idem_reject_mem_123
```

#### Request

```json
{
  "reason": "incorrect"
}
```

#### Response

```json
{
  "memory_id": "mem_123",
  "status": "rejected"
}
```

---

## 12. API: Program context

### 12.1 Get current program frame

```http
GET /api/v1/programs/current/frame
```

#### Response

```json
{
  "program_id": "pgm_123",
  "program_name": "AI Build Phase Cohort 3",
  "timezone": "Asia/Ho_Chi_Minh",
  "team": {
    "team_id": "team_004",
    "name": "P-004"
  },
  "roles": [
    {
      "role_id": "role_pm",
      "name": "PM"
    }
  ],
  "milestones": [
    {
      "milestone_id": "ms_gate_2",
      "name": "Gate 2",
      "due_at": "2026-08-09T23:59:00+07:00"
    }
  ],
  "source_authority": [
    {
      "source_type": "vlearn",
      "level": "official"
    },
    {
      "source_type": "discord",
      "level": "reference"
    }
  ]
}
```

#### Rules

- Program frame dùng để lọc và xếp mức thẩm quyền nguồn.
- Không được dùng Program frame để tự bịa deadline nếu không có evidence.

---

## 13. API: Briefing

### 13.1 Generate briefing

```http
POST /api/v1/briefings/generate
Idempotency-Key: idem_brief_123
```

#### Request

```json
{
  "program_id": "pgm_123",
  "briefing_type": "daily",
  "since": "2026-08-05T08:00:00+07:00",
  "include_sections": ["needs_attention", "changes", "your_tasks", "waiting", "sources_checked"]
}
```

#### Response

```json
{
  "brief_id": "brf_123",
  "status": "generated",
  "coverage": {
    "status": "partial",
    "checked_sources": ["jira", "vlearn", "calendar"],
    "missing_sources": ["gmail"],
    "reason": "Gmail sync failed during latest run."
  },
  "sections": [
    {
      "key": "needs_attention",
      "title": "Cần xử lý",
      "items": [
        {
          "brief_item_id": "bitem_123",
          "title": "Hoàn thiện API contract trước Gate 2",
          "summary": "Jira có task đang in progress và VLearn có deadline Gate 2.",
          "confidence": "certain",
          "citation_ids": ["cit_123", "cit_456"],
          "suggested_actions": ["create_reminder", "create_calendar_handoff"]
        }
      ]
    }
  ],
  "generated_at": "2026-08-06T23:30:00+07:00"
}
```

#### Rules

- Mọi brief item factual phải có `citation_ids`.
- Nếu coverage partial, response phải hiển thị rõ.
- Không được giấu conflict.
- Không được tự tạo deadline/owner/status nếu không có evidence.

### 13.2 Get briefing

```http
GET /api/v1/briefings/{brief_id}
```

#### Response

Giống response của generate briefing.

### 13.3 List briefing history

```http
GET /api/v1/briefings?limit=20&cursor=cur_123
```

#### Response

```json
{
  "items": [
    {
      "brief_id": "brf_123",
      "title": "Daily Brief — 2026-08-06",
      "coverage_status": "partial",
      "generated_at": "2026-08-06T08:00:00+07:00"
    }
  ],
  "next_cursor": null
}
```

---

## 14. API: Ask và conversation

### 14.1 Create conversation

```http
POST /api/v1/conversations
Idempotency-Key: idem_conv_123
```

#### Request

```json
{
  "title": "Hỏi về Gate 2",
  "program_id": "pgm_123"
}
```

#### Response

```json
{
  "conversation_id": "conv_123",
  "title": "Hỏi về Gate 2",
  "created_at": "2026-08-06T23:30:00+07:00"
}
```

### 14.2 Submit question

```http
POST /api/v1/conversations/{conversation_id}/messages
Idempotency-Key: idem_msg_123
```

#### Request

```json
{
  "question": "Gate 2 cần nộp gì và khi nào?",
  "context": {
    "brief_id": "brf_123",
    "selected_evidence_ids": [],
    "source_types": ["jira", "vlearn", "discord", "gmail", "calendar"]
  }
}
```

#### Response

```json
{
  "message_id": "msg_123",
  "answer": {
    "kind": "answered",
    "text": "Gate 2 cần nộp API contract và các phần liên quan theo task hiện tại. Deadline tìm thấy là 2026-08-09 23:59 ICT.",
    "confidence": "certain",
    "citation_ids": ["cit_123", "cit_456"],
    "coverage": {
      "status": "partial",
      "checked_sources": ["jira", "vlearn"],
      "missing_sources": ["gmail"],
      "reason": "Gmail đang lỗi đồng bộ."
    },
    "conflicts": []
  },
  "suggested_actions": [
    {
      "type": "create_reminder",
      "label": "Tạo nhắc việc"
    }
  ],
  "created_at": "2026-08-06T23:30:00+07:00"
}
```

#### Abstain response

```json
{
  "message_id": "msg_456",
  "answer": {
    "kind": "abstained",
    "text": "Mình chưa tìm thấy bằng chứng trong các nguồn đã kết nối để trả lời chắc chắn.",
    "confidence": "possible",
    "citation_ids": [],
    "coverage": {
      "status": "unknown",
      "checked_sources": ["jira"],
      "missing_sources": ["vlearn", "gmail", "discord", "calendar"],
      "reason": "Một số nguồn chưa được kết nối hoặc đang lỗi."
    },
    "conflicts": []
  }
}
```

#### Rules

- Không lưu raw question vào analytics.
- Raw question có thể nằm trong conversation store của user, theo retention policy.
- Answer factual phải có citation.
- Nếu không đủ evidence, phải `abstained`.
- Nếu có mâu thuẫn, `kind` nên là `conflict` hoặc response phải có `conflicts` không rỗng.

### 14.3 List conversation messages

```http
GET /api/v1/conversations/{conversation_id}/messages?limit=50
```

#### Response

```json
{
  "items": [
    {
      "message_id": "msg_123",
      "role": "user",
      "text": "Gate 2 cần nộp gì?",
      "created_at": "2026-08-06T23:30:00+07:00"
    },
    {
      "message_id": "msg_124",
      "role": "assistant",
      "answer_kind": "answered",
      "text": "...",
      "citation_ids": ["cit_123"],
      "created_at": "2026-08-06T23:30:10+07:00"
    }
  ]
}
```

---

## 15. API: Action draft

### 15.1 Create action draft

```http
POST /api/v1/action-drafts
Idempotency-Key: idem_action_draft_123
```

#### Request

```json
{
  "origin": {
    "type": "brief_item",
    "brief_id": "brf_123",
    "brief_item_id": "bitem_123",
    "evidence_ids": ["evd_123"]
  },
  "action_type": "reminder",
  "draft": {
    "title": "Hoàn thiện API contract",
    "due_at": "2026-08-09T23:59:00+07:00",
    "timezone": "Asia/Ho_Chi_Minh",
    "notes": "Dựa trên task Jira và deadline VLearn."
  }
}
```

#### Response

```json
{
  "action_draft_id": "actd_123",
  "status": "drafted",
  "action_type": "reminder",
  "draft": {
    "title": "Hoàn thiện API contract",
    "due_at": "2026-08-09T23:59:00+07:00",
    "timezone": "Asia/Ho_Chi_Minh",
    "notes": "Dựa trên task Jira và deadline VLearn.",
    "missing_fields": []
  },
  "citation_ids": ["cit_123"],
  "created_at": "2026-08-06T23:30:00+07:00"
}
```

#### Rules

- Nếu thiếu ngày/giờ/timezone, field phải nằm trong `missing_fields`.
- Không được tự điền thời gian mơ hồ.
- Không tạo reminder thật ở bước này.

### 15.2 Preview action draft

```http
POST /api/v1/action-drafts/{action_draft_id}/preview
```

#### Response

```json
{
  "action_draft_id": "actd_123",
  "status": "previewed",
  "preview": {
    "title": "Hoàn thiện API contract",
    "due_at": "2026-08-09T23:59:00+07:00",
    "timezone": "Asia/Ho_Chi_Minh",
    "notes": "Dựa trên task Jira và deadline VLearn.",
    "citation_ids": ["cit_123"]
  }
}
```

### 15.3 Update action draft

```http
PATCH /api/v1/action-drafts/{action_draft_id}
```

#### Request

```json
{
  "draft": {
    "title": "Nộp API contract bản cuối",
    "due_at": "2026-08-09T22:00:00+07:00",
    "timezone": "Asia/Ho_Chi_Minh",
    "notes": "Đã chỉnh giờ nộp sớm hơn deadline."
  }
}
```

#### Response

```json
{
  "action_draft_id": "actd_123",
  "status": "previewed",
  "updated_at": "2026-08-06T23:35:00+07:00"
}
```

### 15.4 Confirm action draft

```http
POST /api/v1/action-drafts/{action_draft_id}/confirm
Idempotency-Key: idem_confirm_action_123
```

#### Request

```json
{
  "confirmation": true
}
```

#### Response for in-app reminder

```json
{
  "action_draft_id": "actd_123",
  "status": "confirmed",
  "result": {
    "type": "reminder",
    "reminder_id": "rem_123",
    "scheduled": true
  },
  "confirmed_at": "2026-08-06T23:36:00+07:00"
}
```

#### Response for calendar handoff

```json
{
  "action_draft_id": "actd_456",
  "status": "confirmed",
  "result": {
    "type": "calendar_handoff",
    "handoff_id": "handoff_123",
    "ics_download_url": "/api/v1/calendar-handoffs/handoff_123.ics",
    "external_open_url": "https://calendar.google.com/calendar/render?..."
  },
  "confirmed_at": "2026-08-06T23:36:00+07:00"
}
```

#### Rules

- Draft phải ở trạng thái `previewed` trước khi confirm.
- Nếu thiếu required fields, trả `422 VALIDATION_ERROR`.
- Confirm lặp lại không được tạo reminder/handoff trùng.

### 15.5 Cancel action draft

```http
POST /api/v1/action-drafts/{action_draft_id}/cancel
Idempotency-Key: idem_cancel_action_123
```

#### Response

```json
{
  "action_draft_id": "actd_123",
  "status": "cancelled",
  "cancelled_at": "2026-08-06T23:40:00+07:00"
}
```

---

## 16. API: Reminder

### 16.1 List reminders

```http
GET /api/v1/reminders?status=scheduled&limit=20
```

#### Response

```json
{
  "items": [
    {
      "reminder_id": "rem_123",
      "title": "Nộp API contract bản cuối",
      "due_at": "2026-08-09T22:00:00+07:00",
      "timezone": "Asia/Ho_Chi_Minh",
      "status": "scheduled",
      "source_action_draft_id": "actd_123",
      "citation_ids": ["cit_123"]
    }
  ]
}
```

### 16.2 Complete reminder

```http
POST /api/v1/reminders/{reminder_id}/complete
Idempotency-Key: idem_complete_rem_123
```

#### Response

```json
{
  "reminder_id": "rem_123",
  "status": "completed",
  "completed_at": "2026-08-09T21:30:00+07:00"
}
```

### 16.3 Cancel reminder

```http
POST /api/v1/reminders/{reminder_id}/cancel
Idempotency-Key: idem_cancel_rem_123
```

#### Response

```json
{
  "reminder_id": "rem_123",
  "status": "cancelled",
  "cancelled_at": "2026-08-08T10:00:00+07:00"
}
```

---

## 17. API: Data & Privacy

### 17.1 Get privacy dashboard

```http
GET /api/v1/privacy/dashboard
```

#### Response

```json
{
  "sources": [
    {
      "source_id": "src_gmail_123",
      "type": "gmail",
      "status": "connected",
      "records_stored": 120,
      "last_successful_sync_at": "2026-08-06T22:00:00+07:00",
      "retention_summary": "Stored until user deletes or consent expires"
    }
  ],
  "memories": {
    "confirmed_count": 8,
    "candidate_count": 3
  },
  "actions": {
    "active_reminders": 2,
    "calendar_handoffs": 1
  }
}
```

### 17.2 Create data deletion request

```http
POST /api/v1/privacy/deletion-requests
Idempotency-Key: idem_delete_123
```

#### Request

```json
{
  "target_type": "source",
  "source_id": "src_gmail_123",
  "delete_mode": "exclude_from_future_retrieval",
  "reason": "user_requested"
}
```

#### Response

```json
{
  "deletion_request_id": "delreq_123",
  "status": "accepted",
  "effective_at": "2026-08-06T23:30:00+07:00"
}
```

#### Rules

- Sau khi accepted, retrieval mới không được dùng dữ liệu target.
- Phải ghi audit event.
- Nếu physical deletion async, response phải nói rõ trạng thái.

### 17.3 Export user data index

```http
POST /api/v1/privacy/export-index
Idempotency-Key: idem_export_123
```

#### Response

```json
{
  "export_request_id": "expreq_123",
  "status": "processing",
  "created_at": "2026-08-06T23:30:00+07:00"
}
```

---

## 18. API: Feedback

### 18.1 Submit answer feedback

```http
POST /api/v1/feedback/answers
Idempotency-Key: idem_feedback_123
```

#### Request

```json
{
  "message_id": "msg_123",
  "rating": "helpful_partial",
  "reason_codes": ["missing_source", "unclear"],
  "note": "Thiếu nguồn Gmail nếu có."
}
```

#### Response

```json
{
  "feedback_id": "fb_123",
  "stored": true
}
```

#### Rules

- Feedback note thuộc user content, không được đưa nguyên văn vào product analytics.
- Metric chỉ lưu rating/reason code.

### 18.2 Submit brief item feedback

```http
POST /api/v1/feedback/brief-items
Idempotency-Key: idem_bitem_feedback_123
```

#### Request

```json
{
  "brief_item_id": "bitem_123",
  "rating": "not_useful",
  "reason_codes": ["not_my_task"]
}
```

#### Response

```json
{
  "feedback_id": "fb_456",
  "stored": true
}
```

---

## 19. API: Audit trail

### 19.1 List audit events for current user

```http
GET /api/v1/audit/events?limit=50&cursor=cur_123
```

#### Response

```json
{
  "items": [
    {
      "audit_event_id": "aud_123",
      "event_type": "consent_changed",
      "actor_type": "user",
      "created_at": "2026-08-06T23:30:00+07:00",
      "metadata": {
        "source_type": "gmail",
        "from": "connected",
        "to": "revoked"
      }
    }
  ],
  "next_cursor": null
}
```

#### Rules

- Metadata không chứa raw private content.
- User chỉ xem audit events thuộc phạm vi của họ.

### 19.2 Emit audit event nội bộ

```http
POST /api/v1/internal/audit/events
Authorization: Bearer <internal_service_token>
X-Service-Name: connector-worker | ai-orchestrator | evaluation-runner
```

#### Request

```json
{
  "event_type": "answer_rendered",
  "actor_type": "system",
  "user_id": "usr_123",
  "metadata": {
    "answer_kind": "answered",
    "citation_count": 2,
    "coverage": "partial",
    "abstained": false,
    "conflict": false
  }
}
```

#### Response

```json
{
  "audit_event_id": "aud_456",
  "stored": true
}
```

---

## 20. API: Evaluation

### 20.1 Create evaluation run

```http
POST /api/v1/internal/evaluation/runs
Authorization: Bearer <internal_service_token>
X-Service-Name: evaluation-runner
Idempotency-Key: idem_evalrun_123
```

#### Request

```json
{
  "suite_name": "p0_citation_and_consent",
  "git_sha": "abc123",
  "dataset_version": "golden_2026_08_06",
  "started_at": "2026-08-06T23:30:00+07:00"
}
```

#### Response

```json
{
  "evaluation_run_id": "evalrun_123",
  "status": "running"
}
```

### 20.2 Submit evaluation case result

```http
POST /api/v1/internal/evaluation/runs/{evaluation_run_id}/results
Authorization: Bearer <internal_service_token>
X-Service-Name: evaluation-runner
```

#### Request

```json
{
  "case_id": "case_no_evidence_abstain_001",
  "status": "passed",
  "checks": {
    "has_citation": true,
    "citation_supports_claim": true,
    "used_revoked_data": false,
    "cross_user_leak": false,
    "action_before_confirm": false
  },
  "safe_metadata": {
    "source_types": ["jira", "vlearn"],
    "answer_kind": "abstained"
  }
}
```

#### Response

```json
{
  "stored": true
}
```

#### Rules

- Evaluation result không được chứa raw private content.
- Golden dataset nếu chứa nội dung nguồn thật phải được scrub hoặc dùng fixture.

---

## 21. AI Tool Contract nội bộ

AI orchestration trong P0 chỉ được gọi các tool nội bộ dưới đây. Các tool này không phải public REST API, nhưng phải có contract rõ để tránh AI gọi bừa.

### 21.1 `search_evidence`

#### Purpose

Tìm evidence trong phạm vi user còn quyền truy cập.

#### Input

```json
{
  "user_id": "usr_123",
  "query": "deadline Gate 2",
  "filters": {
    "program_id": "pgm_123",
    "source_types": ["jira", "vlearn", "discord", "gmail", "calendar"],
    "time_range": {
      "from": "2026-08-01T00:00:00+07:00",
      "to": "2026-08-06T23:59:59+07:00"
    }
  },
  "limit": 10
}
```

#### Output

```json
{
  "results": [
    {
      "evidence_id": "evd_123",
      "citation_id": "cit_123",
      "snippet": "Deadline Gate 2: 2026-08-09 23:59 ICT",
      "source_type": "vlearn",
      "confidence": "certain"
    }
  ],
  "coverage": {
    "status": "partial",
    "checked_sources": ["vlearn"],
    "missing_sources": ["gmail"]
  }
}
```

#### Hard rules

- Không trả dữ liệu user không có quyền.
- Không trả dữ liệu đã revoke/delete.
- Không trả token hoặc credential.

### 21.2 `recall_memories`

#### Purpose

Lấy memory hợp lệ để cá nhân hóa briefing/answer.

#### Input

```json
{
  "user_id": "usr_123",
  "kinds": ["profile", "preference", "commitment"],
  "status": ["confirmed"],
  "limit": 10
}
```

#### Output

```json
{
  "memories": [
    {
      "memory_id": "mem_123",
      "kind": "preference",
      "content": {
        "prefers_briefing_time": "08:00"
      },
      "evidence_ids": ["evd_123"],
      "status": "confirmed"
    }
  ]
}
```

#### Hard rules

- Không trả memory đã rejected/deleted/expired.
- Inferred memory phải giữ nhãn `proposed` hoặc `possible`, không được nâng thành confirmed.

### 21.3 `get_user_context`

#### Purpose

Lấy profile và setting cần thiết cho câu trả lời.

#### Input

```json
{
  "user_id": "usr_123"
}
```

#### Output

```json
{
  "timezone": "Asia/Ho_Chi_Minh",
  "display_name": "An",
  "role": "student",
  "goals": ["hoàn thành Gate 2"]
}
```

### 21.4 `get_program_context`

#### Purpose

Lấy Program Frame hiện tại.

#### Input

```json
{
  "user_id": "usr_123",
  "program_id": "pgm_123"
}
```

#### Output

```json
{
  "program_id": "pgm_123",
  "timezone": "Asia/Ho_Chi_Minh",
  "team_id": "team_004",
  "roles": ["PM"],
  "source_authority": [
    {
      "source_type": "vlearn",
      "level": "official"
    },
    {
      "source_type": "discord",
      "level": "reference"
    }
  ]
}
```

#### Hard rules

- Program Context không phải evidence.
- Không được dùng Program Context để tạo fact mới nếu thiếu evidence.

### 21.5 `get_upcoming_actions`

#### Purpose

Lấy reminders/action drafts sắp tới của user.

#### Input

```json
{
  "user_id": "usr_123",
  "from": "2026-08-06T00:00:00+07:00",
  "to": "2026-08-13T23:59:59+07:00"
}
```

#### Output

```json
{
  "actions": [
    {
      "type": "reminder",
      "id": "rem_123",
      "title": "Nộp API contract",
      "due_at": "2026-08-09T22:00:00+07:00",
      "status": "scheduled"
    }
  ]
}
```

### 21.6 `create_action_draft`

#### Purpose

Tạo bản nháp hành động từ evidence.

#### Input

```json
{
  "user_id": "usr_123",
  "origin_evidence_ids": ["evd_123"],
  "action_type": "reminder",
  "draft": {
    "title": "Nộp API contract",
    "due_at": "2026-08-09T22:00:00+07:00",
    "timezone": "Asia/Ho_Chi_Minh",
    "notes": "Dựa trên evidence đã chọn."
  }
}
```

#### Output

```json
{
  "action_draft_id": "actd_123",
  "status": "drafted",
  "missing_fields": [],
  "requires_user_confirmation": true
}
```

#### Hard rules

- Tool này chỉ tạo draft.
- Không được tạo reminder thật.
- Không được mở calendar handoff.
- Không được gửi tin nhắn.
- Field mơ hồ phải để trong `missing_fields`.

---

## 22. State machine contracts

### 22.1 Source connection state

```text
not_connected
  → connected
  → syncing
  → connected
  → paused
  → connected
  → revoked

connected/syncing
  → error
  → connected | paused | revoked
```

Không cho phép:

- `revoked → syncing` nếu user chưa cấp quyền lại.
- `paused → syncing` nếu chưa resume.

### 22.2 Action draft state

```text
drafted
  → previewed
  → confirmed
  → handoff_opened
  → completed

previewed
  → cancelled

drafted
  → cancelled
```

Không cho phép:

- `drafted → confirmed` nếu chưa preview.
- `confirmed → drafted`.
- `cancelled → confirmed`.
- `completed → cancelled` nếu không có correction flow riêng.

### 22.3 Memory state

```text
proposed
  → confirmed
  → superseded

proposed
  → rejected

confirmed
  → deleted

confirmed
  → superseded
```

Không cho phép:

- `rejected → confirmed` nếu không tạo candidate/version mới.
- `deleted → confirmed`.

---

## 23. Security và privacy requirements

### 23.1 API authorization

Mọi endpoint user-facing phải kiểm tra:

- user đã authenticated;
- resource thuộc user hoặc user có quyền trong program;
- source consent còn hiệu lực;
- RLS ở database không bị bypass.

### 23.2 Internal API authorization

Internal API chỉ nhận request từ service đã định danh.

Mỗi internal request phải có:

- service token;
- `X-Service-Name`;
- `X-Request-ID`;
- audit event khi ghi dữ liệu quan trọng.

### 23.3 Data minimization

API response chỉ trả field cần cho UI hoặc workflow hiện tại.

Không trả:

- OAuth token;
- refresh token;
- cookie;
- password;
- raw private content không cần thiết;
- dữ liệu của source đã revoke/delete.

### 23.4 Cross-user isolation

Bất kỳ endpoint nào nhận ID đều phải xử lý ID như untrusted input.

Ví dụ user A gọi:

```http
GET /api/v1/evidence/evd_of_user_B
```

Kết quả phải là:

```http
403 ACCESS_DENIED
```

hoặc:

```http
404 NOT_FOUND
```

Không được trả metadata làm lộ resource tồn tại.

---

## 24. API acceptance criteria

API contract được coi là đạt P0 khi:

- 100% factual answer có citation mở lại được.
- 100% official memory có evidence hoặc user confirmation.
- 0 case dùng dữ liệu đã revoke/delete trong retrieval mới.
- 0 case action xảy ra trước user confirm.
- 0 case source sync tạo item/version trùng khi retry.
- 0 case worker restart làm mất item đã nhận.
- 0 case cross-user data leak.
- 0 case product analytics/audit log chứa raw private content.
- 100% write API quan trọng có idempotency behavior.
- 100% API lỗi trả theo error contract chuẩn.
- 100% state transition sai bị chặn bằng `409 STATE_CONFLICT` hoặc `422 VALIDATION_ERROR`.

---

## 25. Contract test checklist

```md
- [ ] `GET /me/context` chỉ trả context của user hiện tại.
- [ ] Revoke source xong thì search evidence không trả dữ liệu source đó.
- [ ] Delete request xong thì retrieval mới loại dữ liệu target.
- [ ] Ingest cùng `source_id + external_id + content_hash` hai lần không tạo version trùng.
- [ ] Ingest cùng external item nhưng content hash khác tạo version mới.
- [ ] Briefing item factual không có citation bị chặn.
- [ ] Ask không đủ evidence trả `abstained`.
- [ ] Ask có conflict trả conflict, không tự chọn một bên rồi giấu bên còn lại.
- [ ] Create action draft không tạo reminder thật.
- [ ] Confirm action khi chưa preview bị chặn.
- [ ] Confirm action lặp với cùng idempotency key không tạo reminder/handoff trùng.
- [ ] User A không đọc được evidence/memory/brief/conversation/action của User B.
- [ ] Audit event không chứa raw email/message/question/answer.
- [ ] Error response đúng shape chuẩn.
- [ ] Internal API từ service không hợp lệ bị chặn.
```

---

## 26. Open questions

| ID | Câu hỏi | Owner | Ghi chú |
| --- | --- | --- | --- |
| OQ-01 | Retention policy chi tiết cho raw source item là bao lâu? | PM + Tech Lead | Cần chốt trước pilot |
| OQ-02 | OAuth connector nào đủ ổn định để bật pilot? | Tech Lead | Có thể dùng feature flag |
| OQ-03 | Calendar handoff dùng Google Calendar URL hay chỉ `.ics` trong pilot? | PM + Tech Lead | P0 cho phép `.ics`; direct write để sau |
| OQ-04 | Mức trích excerpt tối đa trong evidence detail là bao nhiêu ký tự? | PM + Privacy reviewer | Cần tránh lộ quá nhiều private content |
| OQ-05 | Admin/mentor được xem gì trong pilot? | PM + Mentor | Không mặc định xem raw private content |

---

## 27. Change log

| Version | Date | Change |
| --- | --- | --- |
| v0.1 | 2026-08-06 | Bản API contract đầu tiên cho mondaiy P0 |
