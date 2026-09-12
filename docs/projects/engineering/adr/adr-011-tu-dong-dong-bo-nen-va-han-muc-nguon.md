# ADR-011 — Tự động đồng bộ nền, lặp lại đúng bộ nguồn người dùng đã chọn

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Proposed |
| Owner | Thái Hoài An (PM) + Nguyễn Văn Phong (Technical Lead) |
| Author | Nguyễn Văn Phong (Technical Lead) |
| Reviewers | Thái Hoài An (PM), Lê Thị Yến Nhi (UI/UX Lead), Nguyễn Đức Dũng (PO/QC) |
| Last updated | 2026-08-12 |
| Related | [ADR-002](adr-002-connector-first-p0-scope.md) · [ADR-007](adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md) · [PRD](../../product/prd.md) |

## Bối cảnh

Sản phẩm chưa từng tự lấy dữ liệu. `src/worker.py` chỉ poll bảng `runs` tìm
dòng đã `queued`, mà dòng đó chỉ sinh ra khi người dùng bấm Sync trên FE. Hệ
quả: mở app lên lúc nào cũng thấy kết quả của lần bấm gần nhất, và muốn có dữ
liệu mới thì phải bấm rồi ngồi chờ pipeline chín node chạy xong.

Điều đó đánh thẳng vào chỉ số chính của PRD — tỷ lệ hoàn thành việc đến hạn.
Một việc có hạn chiều nay mà chỉ xuất hiện sau khi người dùng nhớ ra là phải bấm
Sync thì lớp nhắc việc của ADR-007 không có gì để nhắc.

Đi kèm là hai hạn mức đặt quá chặt, cùng nằm trong `src/config.py`:

- `max_sync_sources = 3` — trần nguồn mỗi lần Sync. FE không hề biết trần này:
  người dùng tick nguồn thứ tư vẫn được, tới lúc bấm Sync mới ăn 422 và không
  có gợi ý nào về việc phải bỏ bớt nguồn nào.
- `max_concurrent_runs = 3` — trần run đang chạy của **toàn hệ thống**, không
  phải theo user. Ba người sync cùng lúc là người thứ tư ăn 429 "Hệ thống đang
  bận". Có thêm auto-sync thì gần như chắc chắn đụng trần.

## Lựa chọn đã cân nhắc

| Phương án | Ưu | Nhược | Kết luận |
| --- | --- | --- | --- |
| Giữ nguyên, chỉ Sync thủ công | Không phát sinh vấn đề privacy nào | Không giải quyết được điều gì; chỉ số PRD vẫn phụ thuộc trí nhớ người dùng | Loại |
| FE tự gọi Sync khi mở app | Chỉ chạy khi user có mặt, nhẹ về privacy | Lần mở app đầu vẫn phải chờ trọn pipeline — đúng cái đau đang có | Loại |
| Scheduler nền trong worker | Dữ liệu mới sẵn trước khi người dùng mở app | Hệ thống gọi API của người dùng lúc họ vắng mặt → material change về privacy | **Chọn**, kèm bốn ràng buộc dưới |

## Quyết định

### 1. Auto-sync không bao giờ tự chọn nguồn

Run tự động sao chép **nguyên văn** danh sách nguồn từ run **thành công** gần
nhất mà chính người dùng đã tự tay chọn. Chưa từng Sync thủ công thành công lần
nào thì không có auto-sync — không có suy đoán, không có mặc định "quét tất cả
những gì đã kết nối".

Đây là ranh giới giữ cho ADR-011 nằm trong phạm vi ADR-002: auto-sync không mở
rộng tập nguồn được đọc, nó chỉ đọc lại đúng tập người dùng đã đồng ý.

Nguồn lấy từ run thành công chứ không phải run gần nhất: run lỗi có thể mang
theo nguồn đã hỏng, lặp lại nó là lặp lại lỗi mỗi ba tiếng.

### 2. Hai công tắc, phải bật cả hai

| Công tắc | Mặc định | Ai đổi |
| --- | --- | --- |
| `AUTO_SYNC_ENABLED` (toàn hệ thống) | `false` | Vận hành, sau khi ADR này được duyệt |
| `users.auto_sync_enabled` (từng người) | `true` | Chính người dùng |

Công tắc tổng mặc định tắt để nhánh này deploy được mà không tự động bật một
hành vi chưa ai duyệt. Công tắc cá nhân là đường rút lại đồng ý mà không phải
ngắt kết nối nguồn nào.

`GET /runs/limits` trả về `autoSyncEnabled` đã là kết quả AND của hai công tắc,
để FE không phải tự suy và không có cơ hội suy sai.

> **TODO(OD)** — mặc định của công tắc cá nhân là `true` hay `false` là quyết
> định của PM, không phải của Technical Lead. Bản này chọn `true` với lý do
> công tắc tổng đã chặn sẵn; PM chốt ngược lại thì chỉ đổi một giá trị default.

### 3. Nhìn thấy được, không chạy ngầm im lặng

Auto-sync bật thì trang chọn nguồn hiện băng nói rõ nhịp làm mới và rằng nó
chạy cả khi app đóng. Một hành vi nền mà người dùng không biết là đang có thì
không phải tính năng, là bất ngờ.

### 4. Không chen ngang, không dồn cục

| Ràng buộc | Giá trị | Lý do |
| --- | --- | --- |
| Bỏ qua user đang có run `queued`/`running` | — | Không chen ngang Sync thủ công người dùng đang ngồi chờ |
| Giãn nhịp theo run gần nhất ở **mọi** trạng thái | `AUTO_SYNC_INTERVAL_MINUTES=180` | Chuỗi run lỗi cũng phải giãn đúng nhịp, không thành vòng thử lại |
| Khoá idempotency chốt theo ô thời gian | `auto-{user_id}-{bucket}` | Hai worker replica cùng thấy một user tới hạn vẫn chỉ ra một run |
| Trần user mỗi vòng quét | `AUTO_SYNC_MAX_USERS_PER_TICK=20` | Sáng thứ Hai cả nghìn user cùng tới hạn không dồn một cục vào hàng đợi |
| Cửa sổ quét | `AUTO_SYNC_RANGE_HOURS=24` | Ngắn hơn Sync thủ công vì phần cũ đã nằm trong DB từ các run trước |

### 5. Nới hai hạn mức, và cho FE biết chúng

- `max_sync_sources`: 3 → **10**. Đi kèm điều kiện bắt buộc: FE đọc trần qua
  `GET /runs/limits` và khoá ô tick khi chạm trần, kèm bộ đếm `n/max`. Nới trần
  mà không hiện ra thì chỉ dời chỗ người dùng ăn 422 chứ không sửa gì.
- `max_concurrent_runs`: 3 → **10**. Đây cũng là số consumer loop `run_worker()`
  spawn, nên nâng trần là nâng throughput thật chứ không chỉ nới điều kiện chặn.

Chi phí LLM vẫn bị `max_total_llm_batches_per_run` chặn như cũ; hai con số trên
không đụng tới ngân sách token của một run.

## Hệ quả

**Được:** dữ liệu mới sẵn trước khi người dùng mở app; lớp nhắc việc ADR-007 có
cái để nhắc; chọn nhiều nguồn hơn mà biết trước giới hạn.

**Mất:** hệ thống gọi API của người dùng khi họ vắng mặt — đây là điểm phải nói
rõ trong chính sách quyền riêng tư trước khi bật `AUTO_SYNC_ENABLED` ở
production. Tải nền tăng theo số user đang hoạt động: mỗi user tối đa 8
run/ngày ở nhịp 180 phút.

**Rollback:** đặt `AUTO_SYNC_ENABLED=false`. Vòng quét thoát ngay lúc khởi động
và ghi log lý do; không có schema nào phải hoàn tác, cột `users.auto_sync_enabled`
nằm im vô hại.

## Điều kiện nghiệm thu

- [ ] User chưa từng Sync thủ công thành công không bao giờ có run tự động
- [ ] Run tự động dùng đúng bộ nguồn của run thành công gần nhất, không thừa không thiếu
- [ ] Tắt công tắc cá nhân là hết run tự động, không cần ngắt kết nối nguồn nào
- [ ] Hai vòng quét trong cùng một ô thời gian chỉ tạo một run
- [ ] Auto-sync không bao giờ chen ngang một run đang `queued`/`running`
- [ ] FE khoá ô tick khi chạm trần nguồn và hiện bộ đếm `n/max`
- [ ] Bật auto-sync thì UI nói rõ nhịp làm mới

## Liên quan trong mã

| Thành phần | Vị trí |
| --- | --- |
| Vòng quét nền | `src/services/auto_sync.py`, `src/worker.py::_auto_sync_loop` |
| Luật hạn mức dùng chung API + scheduler | `src/api/runs.py::enqueue_run` |
| Endpoint hạn mức cho FE | `src/api/runs.py::get_run_limits` |
| Công tắc cá nhân | `src/models/user.py::User.auto_sync_enabled` |
| UI trần nguồn + băng auto-sync | `client/web-app/src/components/pipeline/SourcePicker.tsx` |
| Test | `tests/test_services/test_auto_sync.py`, `tests/test_api/test_runs.py` |
