# Google Calendar — read, ingest, agent và explicit sync

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Implemented |
| Last updated | 2026-08-11 |
| Write policy | Đọc tự động; agent ghi sau preview + nút Chấp nhận; người dùng thao tác trực tiếp thì ghi ngay kèm Undo ([ADR-007](projects/engineering/adr/adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md)) |

## 1. Một OAuth connection, hai connector

Google OAuth xin `gmail.readonly`, `calendar.readonly` và `calendar.events`.
Một dòng
`connections.provider = google` phục vụ hai connector thật:

```text
Google connection
  ├─ INBOX/...   -> GmailConnector (giữ source ID cũ)
  └─ calendar:*  -> CalendarConnector
```

`GET /api/v1/integrations/{id}/sources` giữ source Gmail như `INBOX` và gắn
namespace cho Calendar, ví dụ `calendar:primary`. Source không prefix route về
Gmail để tương thích client/run cũ và cho phép deploy frontend/backend theo bất
kỳ thứ tự nào. Nếu token cũ chỉ đọc được
Gmail, API vẫn trả nguồn Gmail và thêm `warnings`; người dùng cần kết nối lại
Google để cấp các scope Calendar hiện hành.

Khi chạy pipeline, `fetch_node` bỏ namespace rồi gọi đúng connector. Calendar
event được ghi vào audit raw/normalized với thời gian dạng `datetime`, không còn
lỗi ghi chuỗi vào cột `DateTime`.

## 2. Agent hỏi lịch

```text
câu hỏi “tuần này tôi có lịch gì?”
  -> deterministic calendar intent guard
  -> calendar_search_events
  -> user scope từ access token (model không được tự truyền user_id)
  -> timeMin/timeMax hữu hạn
  -> Google Calendar API có pagination
  -> bỏ event cancelled
  -> trả title/start/end/deep link làm bằng chứng
```

Tool được bind trực tiếp trong `src/agents/nodes/core_nodes.py`. Với model nhỏ
không chịu gọi tool, guard tự route các cụm `lịch`, `sự kiện`, `cuộc hẹn`,
`calendar`, `meeting`, `event`; `hôm nay`, `ngày mai`, `tuần này`, `tuần sau`,
`tháng này` được đổi thành cửa sổ chính xác. Câu không ghi khoảng chỉ đọc 30
ngày tới. Không có nhánh tìm Calendar vô hạn.

`calendar_search_events` vẫn chỉ đọc. Agent có thêm tool ghi giới hạn
`create_productivity_item` cho ba loại `calendar_event`, `task`, `todo`. Tool
chỉ tạo proposal, không ghi ngay. Frontend hiện preview với **Chấp nhận** và
**Từ chối**; endpoint approve mới kiểm tra lại ownership, trạng thái, scope rồi
thực thi đúng draft lưu phía server. **Agent vẫn không được sửa hoặc xóa event** —
hai thao tác đó chỉ mở cho người dùng thao tác trực tiếp, xem mục 4.

Chi tiết state machine và contract trường nằm tại
[Agent productivity actions](agent-productivity-actions.md).

## 3. Task sang lịch

Task phải có `status=confirmed` và `due_at` rõ ràng. FE gọi theo thứ tự:

1. `GET /api/v1/tasks/{id}/calendar-handoff` để tạo/đọc handoff draft;
2. tải `.../calendar-handoff.ics` bằng Bearer token rồi tạo Blob URL;
3. khi người dùng thật sự tải/mở file, gọi
   `POST .../calendar-handoff/opened` để ghi FR-065.

Backend cũng trả `googleCalendarUrl` dạng template. File `.ics` escape text và
fold từng physical line tối đa 75 octet, kể cả tiêu đề UTF-8 tiếng Việt.

Trang `/tasks` có thêm luồng sync trực tiếp:

1. `GET /api/v1/tasks/calendar-events?timeFrom=...&timeTo=...` nạp tối đa 42
   ngày từ mọi calendar nhìn thấy được;
2. người dùng xác nhận task được rút ra từ Gmail/nguồn khác;
3. người dùng bấm **Sync to calendar**;
4. `POST /api/v1/tasks/{id}/calendar-sync` kiểm tra ownership, trạng thái
   `confirmed`, `due_at`, kết nối Google và scope ghi rồi mới gọi Events API;
5. `calendar_event_id` được lưu để retry không tạo event trùng.

Endpoint sync không tự chạy khi task vừa được trích xuất hay vừa xác nhận. Agent
hội thoại tạo item trực tiếp qua executor riêng; không gọi vòng qua endpoint
HTTP này.

## 4. Lưới lịch và thao tác trực tiếp

Router `src/api/calendar.py` phục vụ lưới lịch tuần. Khác với
`/tasks/calendar-events` (luôn gọi Google), nhánh này ưu tiên bộ nhớ đệm:

```text
GET /api/v1/calendar/events?timeFrom&timeTo          -> đọc calendar_events, origin=cache
GET /api/v1/calendar/events?...&refresh=true         -> đồng bộ rồi đọc, origin=refreshed
POST   /api/v1/calendar/events                       -> người dùng tự tạo
PATCH  /api/v1/calendar/events/{event_id}            -> sửa, chỉ gửi trường đã đổi
DELETE /api/v1/calendar/events/{event_id}            -> xoá, giữ bản chụp
POST   /api/v1/calendar/operations/{id}/undo         -> hoàn tác trong 10 giây
```

Ranh giới quyền ghi theo chủ thể khởi tạo: bốn endpoint ghi ở trên chỉ phục vụ
thao tác trực tiếp của người dùng và **không được bind vào agent**. Agent vẫn đi
qua `create_productivity_item` → preview → Chấp nhận như cũ.

`calendar_events` là bộ nhớ đệm khoá theo `(user_id, calendar_id, event_id)`,
ba trạng thái `active` / `deleted` / `stale`. Đồng bộ tăng dần dùng `syncToken`
lưu trong `sync_cursors`; Google trả 410 thì xoá con trỏ và đọc lại toàn bộ
khoảng thay vì báo lỗi. Một lịch lỗi được trả về trong `failedCalendars` chứ
không chặn các lịch còn lại.

Hoàn tác dựa trên bảng `calendar_operations` giữ bản chụp `before`. Xoá rồi
hoàn tác sẽ **tạo sự kiện mới với mã khác** — Google không cho khôi phục sự
kiện đã xoá — nên dòng cũ trong bộ nhớ đệm giữ trạng thái `deleted`.

## 5. Việc còn lại trước production

- OAuth connection đã cấp trước đây với `calendar.readonly` không tự có quyền
  ghi. Người dùng cần reconnect Google một lần để nhận thêm
  `calendar.events`; giao diện hiển thị lỗi 409 hướng dẫn reconnect thay vì tự
  tạo event.
- Google Cloud OAuth consent screen/verification phải khai báo scope
  `calendar.events` (scope nhạy cảm). Không dùng token production cũ để kiểm tra
  luồng ghi nếu chưa hoàn tất bước này.
- Luồng sync hiện ghi vào calendar `primary`, dùng block 30 phút cho task có
  giờ và khoảng một ngày cho task `all_day`. Chọn calendar đích riêng là backlog
  sau khi có nhu cầu thực tế.
- Tool hội thoại hiện hỗ trợ tạo mới event/task/todo; update/delete, recurrence,
  attendee invitation và chọn calendar đích bằng UI chưa nằm trong luồng này.
- Chưa có live integration test với Google API; test hiện tại mock connector và
  kiểm tra ownership, trạng thái, scope, idempotency, định dạng event. Cần chạy
  một smoke test có tài khoản sandbox sau khi cập nhật OAuth credentials.
- Phần nạp todo từ Gmail dùng pipeline/run hiện có; `/tasks` chỉ đọc các task đã
  persist. Nếu muốn tự khởi chạy pipeline mỗi lần mở trang, cần thêm rate limit,
  idempotency và UX trạng thái riêng — chưa bật để tránh crawl mailbox ngoài ý
  muốn.

## 6. Test

```bash
DATABASE_URL=sqlite:////tmp/p004-calendar-test.db .venv/bin/python -m pytest -q \
  tests/test_connectors/test_calendar.py \
  tests/test_services/test_calendar_tools.py \
  tests/test_agents/test_calendar_tool.py \
  tests/test_agents/test_pipeline_fetch.py \
  tests/test_api/test_integrations.py \
  tests/test_api/test_tasks.py \
  tests/test_api/test_calendar.py

cd client/web-app
npm test
npm run build
```
