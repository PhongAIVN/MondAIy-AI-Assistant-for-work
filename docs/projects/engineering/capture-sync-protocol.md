# Capture and sync protocol

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Superseded — ngoài P0 theo ADR-002 |
| Owner | Nguyễn Văn Phong (Technical Lead; acting owner) |
| Author | Thái Hoài An (PM) |
| Reviewers | Tech Lead, QA Lead |
| Last updated | 2026-08-02 |
| Related | [ADR-002](adr/adr-002-connector-first-p0-scope.md) · [Architecture](architecture.md) · [PRD](../product/prd.md) |

> Tài liệu này giữ lại làm lịch sử cho phương án browser capture. Không dùng để
> triển khai hoặc đánh giá P0 hiện tại.

## 1. Event envelope

Mỗi observation gửi:

```json
{
  "event_id": "uuid",
  "user_id": "resolved-from-jwt-not-client-trusted",
  "source_type": "web_page",
  "source_connection_id": "uuid",
  "observed_at": "2026-07-30T03:30:00Z",
  "canonical_url": "https://example.com/page",
  "title": "Example",
  "content_text": "clean visible content",
  "content_hash": "sha256",
  "extractor_version": "readability-v1",
  "capture_mode": "allow_list",
  "metadata": {
    "domain": "example.com",
    "language": "vi"
  }
}
```

Backend không tin `user_id` từ payload; resolve từ JWT.

## 2. Local outbox

IndexedDB stores:

- `capture_outbox`
- `capture_receipts`
- `local_document_cache`
- `settings`

States:

`queued → sending → acknowledged` hoặc `queued → retry_wait → sending`.

Không xóa local event trước server ACK. Event stuck vượt retry threshold hiển thị trong receipt.

## 3. Batch API

`POST /v1/captures/batch`

- Tối đa theo byte/event count được config.
- Gzip khi payload vượt threshold.
- Batch có `batch_id`; event có `event_id`.
- Response trả từng event: `accepted`, `duplicate`, `rejected`, `retryable`.
- `accepted` nghĩa evidence đã persist, không nghĩa extraction đã hoàn tất.

## 4. Dedupe và version

- `event_id` unique để idempotent retry.
- `(user_id, canonical_url, content_hash)` xác định content version tương đương.
- Observation cùng hash cập nhật last-observed/visit signal nhưng không tạo document version mới.
- Hash mới tạo immutable `document_version`.
- Normalization/canonical URL rule phải version hóa để có thể backfill.

## 5. Capture policy

- Allow-list mặc định trong pilot.
- All-web chỉ internal dogfood.
- Ignore Chrome system pages, extension pages, password manager/banking mặc định khi nhận diện được.
- Không capture password fields.
- Input/textarea/contenteditable không capture trong P0.
- Respect pause ngay tại client trước extraction/upload.
- Source revoke khiến backend reject event mới dù client stale.

## 6. Retry

- Exponential backoff + jitter.
- 401: refresh auth rồi retry có giới hạn.
- 403 consent revoked: mark non-retryable và dừng source.
- 413: chia batch.
- 429/5xx/network: retryable.
- Malformed/unsupported payload: rejected, hiển thị diagnostic redacted.

## 7. Receipt

UI hiển thị:

- Capture mode và domain count.
- Queued/synced/failed events.
- New versions và duplicate observations.
- Last successful sync.
- Source/time range chưa covered.
- Link tới data controls.

## 8. Contract tests

- Offline → restart service worker → reconnect không mất event.
- Send cùng event/batch nhiều lần không duplicate.
- Cùng URL/hash không tạo version mới.
- Cùng URL/hash mới tạo version.
- Revoke consent trước retry khiến event bị reject.
- Cross-user event injection bị backend bỏ qua/chặn.
- Oversized batch được split.
- Partial batch response chỉ ACK event thành công.
