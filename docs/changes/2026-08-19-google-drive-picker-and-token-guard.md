# 2026-08-19 · Lane A backend — Google Drive picker + tầng chống spam token cho Docs/Sheets

## Mục tiêu

1. Người dùng **duyệt/tìm** file Google Docs & Sheets của chính họ thay vì phải
   dán URL → endpoint mới `GET /api/v1/google-drive/files`.
2. Google Docs **ngang hàng** Google Sheets: nhận `documentId` từ picker, cùng
   luồng `task-proposals`.
3. Tầng chống spam token **dùng chung** cho Docs lẫn Sheets: cap kích thước +
   quota/ngày + cache theo revision.

## Nguồn tham chiếu

- Hợp đồng API do Tatejo chốt (`/private/tmp/p004-CONTRACT.md`), lane frontend
  code song song theo cùng file.
- Code sẵn có: `src/connectors/google_sheets.py`, `src/connectors/google_docs.py`,
  `src/api/rate_limit.py`, `src/services/usage_quota.py` (mẫu quota theo ngày),
  `src/models/sync_cursor.py` (mẫu bảng key/value theo user).
- `AGENTS.md` (identifier tiếng Anh, comment tiếng Việt, config LLM tập trung
  ở `src/config.py`).

## Phạm vi & quyền sở hữu

- Agent: lane A (backend). Worktree `/private/tmp/p004-gdrive-backend`,
  branch `agent/gdrive-backend`, base `main @ b6d6693`.
- Chỉ sửa `src/**`, `tests/**`, `docs/changes/**`. **Không** đụng `client/**`
  (lane frontend sở hữu), `deploy/**`, `.env`.

## Hành vi quan sát được

### 1. `GET /api/v1/google-drive/files`

- Query: `q` (≤100 ký tự), `kind` = `document|spreadsheet|all` (mặc định `all`),
  `pageToken`, `pageSize` (mặc định 20, tối đa 50 — vượt thì 422).
- 200: `{ files: [{ id, name, kind, modifiedTime, webViewLink }], nextPageToken }`.
  Chỉ trả Docs & Sheets; file khác (PDF…) bị loại ngay ở connector.
- 409 khi chưa kết nối Google, hoặc kết nối thiếu scope `drive.readonly`.
- 502 khi Drive API lỗi. Rate limit 30/phút (key `user_or_ip`).
- **Không trừ quota đọc tài liệu**: chỉ lấy metadata, không tốn token nào.
  Quota chỉ dành cho lượt đọc nội dung (Docs/Sheets) — xem "Lệch so với contract".

### 2. `POST /google-docs/task-proposals` và `POST /google-sheets/task-proposals`

- Request nhận `documentUrl` **hoặc** `documentId` (Sheets: `spreadsheetUrl`
  hoặc `spreadsheetId`), đúng một trong hai; thiếu cả hai hoặc đưa cả hai → 422.
  Luồng cũ dán URL giữ nguyên (tương thích ngược).
- Response thêm `truncated: bool` và `quotaRemaining: int`.
- Rate limit 10/phút mỗi endpoint.

### 3. Tầng chống spam token (phần quan trọng nhất)

| Lớp | Ngưỡng | Khai ở |
| --- | --- | --- |
| Cap nội dung Docs | 20.000 ký tự | `settings.google_document_max_chars` |
| Cap bảng Sheets | 500 dòng × 20 cột **và** tổng 20.000 ký tự | `google_sheet_max_rows` / `google_sheet_max_columns` / `google_document_max_chars` |
| Quota | 20 lượt đọc/ngày/user, Docs + Sheets dùng chung | `google_document_reads_per_day` |
| Cache | TTL 15 phút, khoá `(user_id, file_id, revision, sheetName)` | `google_document_cache_ttl_seconds` |

- Hằng số cũ `_MAX_DOCUMENT_TEXT_CHARS = 20_000` trong `google_docs.py` bị **xoá**:
  một khái niệm chỉ được có một tên, nay chỉ còn `settings.google_document_max_chars`.
- Thứ tự phục vụ một lượt: đọc nội dung (rẻ, không tốn token) → tính khoá cache
  → **cache hit thì trả luôn, không trừ quota, không gọi LLM** → cache miss thì
  trừ quota (hết → 429 kèm mốc reset) → cắt theo cap → LLM → ghi cache.
- Quota và cache lưu ở DB (`document_read_quotas`, `document_read_caches`) chứ
  không ở bộ nhớ tiến trình: nhiều replica dùng chung hạn mức và restart không
  cấp lại lượt cho người dùng.

### 4. OAuth scope

`settings.google_scopes` được bổ sung hai scope:

- `https://www.googleapis.com/auth/drive.readonly` — cần cho picker.
- `https://www.googleapis.com/auth/documents.readonly` — **sửa drift có sẵn**:
  `/google-docs/task-proposals` kiểm tra đúng scope này nhưng luồng cấp quyền
  trước đây không hề xin nó, nên trên thực tế mọi kết nối mới đều bị 409.

## File đã đụng

Mới:

- `src/connectors/google_drive.py` — connector Drive (list/search, escape `q`).
- `src/api/google_drive.py` — endpoint `GET /google-drive/files`.
- `src/models/document_read.py` — bảng `document_read_quotas`, `document_read_caches`.
- `src/services/document_read_quota.py` — quota + cache dùng chung.
- `tests/test_api/test_google_drive.py`, `tests/test_api/test_document_token_guard.py`.

Sửa:

- `src/config.py` — thêm scope + 6 ngưỡng chống spam token.
- `src/models/schemas.py` — schema Drive; `documentId`/`spreadsheetId`;
  `truncated` + `quotaRemaining`.
- `src/connectors/google_docs.py` — `read_document()` trả snapshot (text đã cắt,
  `truncated`, `revision`); cap lấy từ config.
- `src/connectors/google_sheets.py` — `cap_values()`, `read_sheet()` trả snapshot.
- `src/api/google_docs.py`, `src/api/google_sheets.py` — id/URL, quota, cache,
  rate limit 10/phút.
- `src/main.py`, `src/models/__init__.py` — đăng ký router + model mới.
- `tests/test_api/test_google_docs.py`, `tests/test_api/test_google_sheets.py`,
  `tests/test_connectors/test_google_sheets.py` — cập nhật theo API mới.

## Lệnh và kết quả thật

Môi trường: `APP_ENV=test OPENAI_API_KEY=test-key LLM_PROVIDER=openai
APP_SECRET_KEY=…` (giống `.github/workflows/checks.yml`).

```
pytest tests/test_api/test_google_drive.py tests/test_api/test_document_token_guard.py -q
→ 19 passed

pytest tests/test_api/test_google_docs.py tests/test_api/test_google_sheets.py \
       tests/test_connectors/test_google_sheets.py -q
→ 17 passed

pytest tests/ -q
→ 22 failed, 1701 passed, 2 skipped   (trước khi sửa: 17 failed, 1687 passed)
   5 failure chênh lệch nằm ở tests/test_connectors/test_google_sheets.py, đã
   sửa xong (fake settings thiếu ngưỡng cap mới). 17 failure còn lại là
   pre-existing trên base b6d6693 — đo lại bằng `git stash` rồi chạy full suite.

ruff check src/ tests/ --output-format=concise
→ 5 lỗi I001, tất cả ở file KHÔNG thuộc lane này (auth.py, connections.py,
  apple_auth.py, routines.py, test_apple_login.py) — có sẵn trên base.
```

Chạy app thật (uvicorn, HTTP thật, sqlite riêng; chỉ biên Google bị giả lập
bằng `httpx.MockTransport` + token giả — router/quota/cache/rate limit/DB là
code thật):

```
GET /api/v1/google-drive/files (chưa kết nối Google)
→ 409 {"detail":"Hãy đăng nhập/kết nối Google để duyệt file Google Drive."}

GET /api/v1/google-drive/files (kết nối thiếu drive.readonly)
→ 409 {"detail":"Kết nối Google chưa có quyền duyệt Drive; hãy cấp lại quyền Google."}

GET /api/v1/google-drive/files?q=backlog&kind=all&pageSize=10
→ 200 {"files":[{"id":"doc-1",…,"kind":"document",…},{"id":"sheet-1",…,"kind":"spreadsheet",…}],
       "nextPageToken":"page-2"}          (file PDF trong nguồn đã bị loại)

GET /api/v1/google-drive/files?pageSize=500  → 422 {"detail":"pageSize tối đa là 50."}

POST /google-docs/task-proposals {"documentId":…}  lần 1 → 200, quotaRemaining=1
POST /google-docs/task-proposals {"documentId":…}  lần 2 → 200, quotaRemaining=1  (cache hit)
POST /google-sheets/task-proposals {"spreadsheetId":…} → 200, quotaRemaining=0
POST /google-docs/task-proposals (doc khác, quota cạn)
→ 429 {"detail":"Bạn đã dùng hết 2 lượt đọc Google Docs/Sheets trong hôm nay.
        Hạn mức được cấp lại lúc 00:00 ngày 2026-08-20 (giờ Asia/Ho_Chi_Minh)."}
POST /google-docs/task-proposals (doc cũ, còn cache) → 200   ← vẫn phục vụ khi quota cạn
POST /google-docs/task-proposals {}  → 422 "Cần đúng một trong hai: documentUrl hoặc documentId."

34 lượt GET /google-drive/files liên tiếp → 30×200 rồi 4×429 (đúng 30/minute)

Kiểm tra DB sau phiên: document_read_quotas reads_used = 2 trên 4 lượt
task-proposals thành công → 2 lượt được phục vụ từ cache mà không trừ quota.
```

(chạy với `GOOGLE_DOCUMENT_READS_PER_DAY=2` để chạm nhánh 429 trong một phiên;
mặc định production vẫn là 20.)

## Kiểm tra đã bỏ qua và lý do

- Không gọi Google API thật: không có OAuth token thật trong worktree agent, và
  lane này không được phép chạm secret/production.
- Không chạy typecheck/lint/build frontend: lane này không sửa `client/**`.

## Rủi ro / lệch so với contract

- **Nguồn `revision` cho khoá cache.** Contract ghi "revision/modifiedTime".
  Docs dùng `revisionId` do Docs API trả về (đúng nghĩa revision). Sheets values
  API không trả revision/modifiedTime nào, nên dùng `sha256` của chính vùng dữ
  liệu đã cắt — chặt hơn `modifiedTime` (đổi nội dung mới đổi khoá) và không
  phải phụ thuộc thêm scope Drive cho luồng import. Không đổi shape response,
  không đổi ngưỡng.
- **`GET /google-drive/files` không trừ quota đọc/ngày**, chỉ chịu rate limit
  30/phút (429 của endpoint này đến từ rate limit). Lý do: liệt kê chỉ lấy
  metadata, không tốn token; tính phí nó sẽ khiến người dùng không dám duyệt.
  Nếu Tatejo muốn liệt kê cũng trừ quota thì báo lại, đổi 1 dòng.
- **Cần frontend làm theo** (không tự sửa vì `client/**` là của lane khác):
  người dùng đã kết nối Google từ trước **phải cấp lại quyền** thì mới có
  `drive.readonly` và `documents.readonly`; UI nên bắt 409 của
  `/google-drive/files` và mời kết nối lại.
- **Bảng mới tạo bằng `create_all`** (repo chưa có Alembic — đúng như TODO ở
  `src/main.py`). Hai bảng thuần thêm mới, không sửa bảng cũ, nên không có bước
  migration phá hoại; DB production sẽ tự có bảng ở lần khởi động kế tiếp.

## Trạng thái merge/deploy

Chỉ commit trên `agent/gdrive-backend`. **Chưa** push, **chưa** merge,
**chưa** deploy — theo đúng phạm vi lane.

## Rollback

`git revert` commit của lane, hoặc bỏ branch. Hai bảng mới không có ai khác
đọc/ghi nên để lại cũng vô hại.

## Việc tiếp theo

- Lane frontend: dùng `GET /google-drive/files` làm picker, gửi
  `documentId`/`spreadsheetId`, hiển thị `truncated` và `quotaRemaining`.
- Cần chốt với Tatejo: liệt kê Drive có trừ quota hay không (mục "lệch" ở trên).
