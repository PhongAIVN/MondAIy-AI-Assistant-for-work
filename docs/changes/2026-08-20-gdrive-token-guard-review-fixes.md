# 2026-08-20 · Lane A2 — vá 3 đường lách tầng chống spam token (review chéo)

## Mục tiêu

Reviewer độc lập soi diff của lane A và tìm ra 3 lỗi thật, cả 3 đều thuộc loại
"lách được tầng chống spam" — đúng thứ tính năng này sinh ra để chặn. Vá hết,
kèm test hồi quy cho từng lỗi.

Nhánh: `integrate/gdrive-docs` (đã merge sẵn lane frontend; lane frontend đã
ngưng ghi, lane A2 là người viết duy nhất). Base: `d0eb918`.

## Lỗi 1 (chặn merge) — trừ quota không nguyên tử

`src/services/document_read_quota.py`: SELECT → `reads_used += 1` ở Python →
commit. N request song song cùng đọc N rồi cùng ghi N+1 → chạy N lượt phân tích
mà chỉ trừ 1 lượt.

Vá: toàn bộ phép cộng nằm trong một câu
`UPDATE … SET reads_used = reads_used + 1 WHERE user_id=? AND quota_day=? AND reads_used < limit`
kèm `RETURNING reads_used`; có hàng trả về nghĩa là giành được lượt. Ba nhánh
phụ cũng nguyên tử: rollover sang ngày mới bằng `UPDATE … WHERE quota_day != today`,
tạo hàng đầu tiên bằng INSERT bắt `IntegrityError` rồi quay lại nhánh UPDATE,
và chỉ khi hàng tồn tại đúng ngày mà UPDATE không ăn mới raise 429.

`RETURNING` được chọn thay vì SELECT lại sau commit vì con số trả cho người
dùng phải là của chính lượt vừa giành: SELECT lại có thể đã cộng thêm lượt của
request song song, khiến hai người cùng thấy "còn 0 lượt". Chạy được trên cả
sqlite (≥3.35) lẫn postgres.

## Lỗi 2 — hàng/ô đơn lẻ vượt ngưỡng vẫn được giữ nguyên

`cap_values()` có nhánh `and kept` nên hàng đầu tiên luôn được giữ, dù dài hơn
cả ngưỡng, và `truncated=False`. Probe của reviewer: `limit=20000 →
retained=20001, truncated=False`. Tức chỉ cần dồn hết nội dung vào một hàng là
lách được cap.

Vá: thêm `_cap_row()` cắt tới mức TỪNG Ô theo ngân sách ký tự còn lại. Tổng số
ký tự giữ lại không bao giờ vượt `google_document_max_chars`.

## Lỗi 3 — tải toàn bộ payload về RAM rồi mới cắt

Cả `read_values()` (Sheets) lẫn `read_document()` (Docs) đều `await client.get()`
xong mới cắt: cap 20.000 ký tự chỉ giới hạn token, không giới hạn RAM/băng thông.

Vá, hai lớp:

- **Sheets xin đúng vùng cần dùng**: `bounded_range()` dựng A1 range
  `'<tab>'!A1:U501` (dư đúng 1 dòng + 1 cột so với ngưỡng để vẫn phát hiện được
  truncation). Nháy đơn trong tên tab được nhân đôi theo cú pháp A1 — trước đây
  một tab tên `Tuần 'A'` sẽ làm hỏng cả biểu thức range.
- **Guard kích thước phản hồi dùng chung**: `src/connectors/google_http.py`
  ·`fetch_json_capped()` kiểm `Content-Length` trước khi đọc, và đọc theo luồng
  để huỷ giữa chừng khi máy chủ không khai độ dài. Ngưỡng mới
  `google_api_max_response_bytes` (mặc định 8 MB) khai ở `src/config.py`.

`GoogleResponseTooLargeError` là lớp **anh em** của `GoogleDocsAPIError` /
`GoogleSheetsAPIError` (không kế thừa) để thứ tự `except` ở tầng API không thể
vô tình nuốt nó thành 502. Tatejo chốt: map sang **422** đã có trong contract,
KHÔNG thêm mã mới — frontend đã code và test theo contract đó. Detail tiếng
Việt nêu rõ dung lượng thực tế so với ngưỡng.

## File đã đụng

Mới: `src/connectors/google_http.py`,
`tests/test_services/test_document_read_quota_concurrency.py`,
`tests/test_api/test_document_size_guard.py`.

Sửa: `src/services/document_read_quota.py`, `src/connectors/google_sheets.py`,
`src/connectors/google_docs.py`, `src/api/google_docs.py`,
`src/api/google_sheets.py`, `src/config.py`,
`tests/test_connectors/test_google_docs.py` (client giả tự viết chỉ có `.get()`
→ đổi sang `httpx.MockTransport` vì connector nay đọc theo luồng).

## Lệnh và kết quả thật

Env: `APP_ENV=test OPENAI_API_KEY=test-key LLM_PROVIDER=openai APP_SECRET_KEY=…`

```
pytest tests/test_services/test_document_read_quota_concurrency.py -q  → 7 passed
pytest tests/test_api/test_document_size_guard.py -q                   → 13 passed
pytest tests/ -q  → 17 failed, 1726 passed, 2 skipped
   17 failure trùng KHỚP TÊN với baseline pre-existing đo trên b6d6693
   (test_auth/test_connections_disconnect/test_google_login/test_tasks/
    test_account_deletion/test_crypto/test_routines/test_slack_rules).
   Không có regression nào từ lane này.

ruff check src/ tests/ --output-format=concise → 5 lỗi I001, đều ở file lane
   khác (auth.py, connections.py, apple_auth.py, routines.py, test_apple_login.py),
   có sẵn trên base.
```

Bằng chứng test cạnh tranh THẬT bắt được bug cũ (tạm khôi phục code cũ rồi chạy
lại chính bộ test này):

```
Code CŨ, 20 thread, limit=4, hàng quota đã tồn tại từ trước:
  AssertionError: cấp 16 lượt cho hạn mức 4:
  [3, 3, 2, 2, 1, 1, 2, 1, 1, 'http-429', 'http-429', 'http-429',
   1, 1, 1, 'http-429', 2, 0, 1, 2]
  → 16/20 lượt được cấp cho hạn mức 4, và các giá trị remaining trùng nhau
    (dấu hiệu lost update).
Code CŨ, 16 thread tạo hàng đầu tiên: sqlite3.IntegrityError UNIQUE constraint
    failed: document_read_quotas.user_id

Code MỚI: đúng 4 lượt được cấp, remaining trả về là [0, 1, 2, 3] — phân biệt,
    không trùng; reads_used trong DB = 4.
```

Probe cap sau khi vá (`limit = google_document_max_chars = 20000`):

```
1 hàng 1 ô = limit+1        limit=20000 retained=20000 truncated=True
1 hàng 3 ô, tổng limit+300  limit=20000 retained=20000 truncated=True
2 hàng, hàng đầu = limit    limit=20000 retained=20000 truncated=True
bảng nhỏ bình thường        limit=20000 retained=37    truncated=False
```

## Kiểm tra đã bỏ qua và lý do

- Không chạy lại app thật vòng này: cả 3 lỗi đều nằm dưới tầng HTTP và đã có
  test đi qua đúng endpoint (`/google-docs/task-proposals`,
  `/google-sheets/task-proposals`) qua ASGI thật.
- Không đụng `client/**`: lane frontend vừa vá `extractErrorMessage` ở đó.

## Rủi ro

- `RETURNING` yêu cầu sqlite ≥ 3.35 (Python 3.13 dựng sẵn bản mới hơn) và
  postgres — cả hai môi trường của dự án đều đạt.
- `google_api_max_response_bytes` mặc định 8 MB: tài liệu thật hiếm khi chạm,
  nhưng nếu có người dùng báo 422 oan thì đây là số cần nới, không phải cap
  20.000 ký tự.

## Trạng thái merge/deploy

Commit trên `integrate/gdrive-docs`. Chưa push, chưa merge, chưa deploy.
