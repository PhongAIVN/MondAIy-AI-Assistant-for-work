# Hoàn thiện eval cho Outlook — bổ sung test `fetch_range()`

## Mục tiêu

User yêu cầu "hoàn thiện phần eval cho Outlook". Research trước khi sửa cho
thấy 2 mảng liên quan Outlook đã tồn tại và khác trạng thái:

- `eval/outlook/` (102 case, `tests/test_agents/v1/test_outlook_pipeline_golden.py`)
  — đã đầy đủ theo đúng scope tự khai trong README (normalize -> filter ->
  evidence selection), 102/102 pass, đã commit từ trước phiên này.
- `eval/golden_dataset/fetch_norm_filter/` — chỉ có Gmail+Discord, không có
  Outlook. Đây là dataset **mồ côi**: `fixtures/`+`expected/`+`manifest.jsonl`
  không được bất kỳ test nào đọc (test duy nhất tham chiếu thư mục này,
  `tests/v1/test_gmail_filter_gold.py`, dùng file khác — `filter_cases.json`
  — và là 1 trong 8 test pre-existing fail đã biết, không liên quan task này).

Hỏi user chọn hướng, user trả lời "không ưu tiên" — quyết định theo phán đoán:
không mở rộng dataset mồ côi (thêm 18 fixture Outlook vào đó chỉ tái tạo thứ
không ai đọc). Thay vào đó tìm khoảng trống eval thật: `OutlookConnector.
fetch_range()` và `OutlookConnector._get()` — 2 hàm async gọi Microsoft Graph
API thật (pagination, evidence-first pre-filter, rate-limit retry, lỗi
partial) — **0% test coverage** trước task này. `normalize()`/`deep_link()`
đã có `test_outlook_normalize.py`; layer duy nhất còn trống là fetch.

## Hành vi thay đổi

Không đổi code sản xuất — chỉ thêm test, theo đúng pattern
`tests/test_connectors/v1/test_calendar.py` đã dùng (monkeypatch
`httpx.AsyncClient` bằng fake context manager, monkeypatch `connector._get`
trực tiếp thay vì mock network thật — repo không có `respx`).

## File chính

- `tests/test_connectors/v1/test_outlook_fetch.py` — mới, 8 test:
  - `_get()`: trả JSON khi 200, retry khi 429 rồi thành công, raise
    `OutlookAPIError` sau khi hết lượt retry, raise khi status khác 200/429.
  - `fetch_range()`: propagate lỗi access token; phân trang qua
    `@odata.nextLink` + chỉ fetch full body cho message có tín hiệu
    (unread/importance=high/keyword) — bỏ qua message không tín hiệu; message
    lỗi khi fetch full body bị skip nhưng không chặn message khác; dừng gom
    candidate đúng lúc chạm `_MAX_METADATA_CANDIDATES` (không gọi thêm trang
    sau khi chạm cap).

## Test đã chạy

```
.venv/Scripts/python -m pytest tests/test_connectors/v1/test_outlook_fetch.py -v
# 8 passed

.venv/Scripts/python -m pytest tests/test_connectors/ tests/test_agents/v1/test_outlook_pipeline_golden.py tests/test_api/v1/test_outlook_connection.py -q
# 150 passed
```

## Risk

Thấp — chỉ thêm test, không sửa `src/connectors/outlook.py`.

## Follow-up (ngoài scope task này)

- `eval/golden_dataset/fetch_norm_filter/` (36 case Gmail+Discord) vẫn mồ côi
  — không test nào đọc `fixtures/`/`expected/`/`manifest.jsonl`. Nếu sau này
  cần wire thật, nên theo đúng convention self-validating của `eval/outlook/`
  (case tự validate bằng hàm thật lúc sinh) thay vì tin fixture viết tay.
- ADR-013 mục "Golden dataset mở rộng thêm fixture/expected cho Outlook theo
  cấu trúc `fetch_norm_filter/`" — chưa làm, cân nhắc bỏ yêu cầu này (đổi
  hướng sang `eval/outlook/` đã có) hoặc làm thật cùng lúc sửa dataset mồ côi
  ở trên, tránh nhân đôi công sức không mang thêm coverage.
