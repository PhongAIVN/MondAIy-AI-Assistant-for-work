# Alembic — cách dùng ở P-004

Nguồn quyết định: [ADR-018](../adr/adr-018-planner-xac-dinh-cho-phan-ra-va-uu-tien-viec.md).
Đọc trước khi đổi bất cứ gì ở đây: `alembic/env.py` lấy `DATABASE_URL` từ
`src/config.py` (`get_settings()`), không hardcode và không đọc `.env` riêng.

**`ensure_runtime_schema()` (`src/db.py`) và `Base.metadata.create_all()`
(`src/main.py`) vẫn chạy như cũ.** Alembic là lớp mới, không thay thế hai cái
đó ở giai đoạn này. Gỡ chúng là việc riêng, sau khi Alembic đã chứng minh ổn.

## DB mới (dev/CI) vs DB đang chạy (production) — hai đường khác nhau

`Base.metadata.create_all()` chạy TRƯỚC alembic mỗi lần app khởi động (giữ
nguyên, xem `src/main.py`). Vì model (`src/models/task.py`) đã khai đủ 5 cột
mới + bảng `task_steps`, một DB dựng từ số 0 được `create_all()` dựng tới
ĐÚNG trạng thái mà revision `5c3a646a710f` lẽ ra phải tạo ra — trước khi
alembic chạy dòng nào. Nghĩa là DB mới đã ở trạng thái `head` ngay từ
`create_all()`, còn DB production thì chưa (cột/bảng đó chưa từng tồn tại
trên production tới khi migration này chạy). Hai điểm xuất phát khác nhau
nên lệnh stamp cũng khác nhau:

| Tình huống | Lệnh |
| --- | --- |
| DB mới, vừa `create_all()` xong (dev, CI, test) | `alembic stamp head` |
| DB production đang chạy, chưa từng chạy alembic | `alembic stamp e01c887a732b` rồi `alembic upgrade head` |

Chạy nhầm `stamp e01c887a732b` trên DB mới rồi `upgrade head` KHÔNG còn gãy
nữa: `upgrade()` của `5c3a646a710f` tự kiểm cột/bảng/FK đã tồn tại chưa qua
`sa.inspect()` trước khi thêm (xem docstring trong file revision) — nếu
`create_all()` đã tạo sẵn thì upgrade() bỏ qua bước đó, không ném
`duplicate column name` nữa. Guard này chỉ có ở `upgrade()`; `downgrade()`
luôn xoá thật (không guard) để đảm bảo nó đảo ngược được, bất kể cột đến từ
`create_all()` hay từ chính migration.

## Stamp một DB production đang tồn tại (chỉ làm MỘT LẦN)

Production hiện có schema nhưng chưa có bảng `alembic_version`. Việc cần làm
là đánh dấu "DB này đã ở trạng thái baseline rồi", KHÔNG chạy `upgrade` từ đầu
(sẽ không có tác dụng gì vì baseline rỗng, nhưng đây là quy trình đúng để mọi
revision sau tính từ đúng điểm xuất phát):

```bash
DATABASE_URL="postgresql://..."   # trỏ đúng DB cần stamp, KHÔNG dùng mặc định sqlite
alembic stamp e01c887a732b
alembic current   # xác nhận in ra e01c887a732b
```

Sau đó mới `alembic upgrade head` để áp các revision thật (vd. revision 2 —
`5c3a646a710f`).

**Không bao giờ chạy `alembic revision --autogenerate` so với production.**
Production có 3 thứ mồ côi (`program_schedule_templates`, `users.program_cohort_slug`,
`chunks.fts`) không khai trong model — autogenerate sẽ đề xuất DROP chúng. Chi
tiết và lý do xem docstring của `alembic/versions/e01c887a732b_*.py`.

## Tạo revision mới

1. Sửa model trong `src/models/*.py` trước.
2. Viết migration TAY (khuyến nghị) hoặc dùng khung sườn:
   ```bash
   alembic revision -m "mo_ta_ngan"
   ```
   rồi tự điền `upgrade()`/`downgrade()`. Không dùng `--autogenerate` vì lý do
   ở trên — diff giữa model và DB thật sẽ luôn lệch do 3 thứ mồ côi.
3. Test trên SQLite tạm trước khi merge (KHÔNG BAO GIỜ chạy `upgrade` lên DB
   thật để thử):
   ```bash
   export DATABASE_URL="sqlite:////tmp/scratch.db"
   alembic upgrade head
   alembic downgrade base   # đảm bảo downgrade() thật sự đảo ngược được
   ```
   Lưu ý: SQLite không hỗ trợ `ALTER TABLE ADD CONSTRAINT`/`DROP COLUMN` trực
   tiếp — dùng `op.batch_alter_table(...)` cho các thao tác đó. Production là
   Postgres nên đừng tin SQLite pass là đủ; nếu hành vi hai dialect khác nhau,
   ghi rõ trong docstring của revision.
4. Migration chỉ thêm cột `NULL`/bảng mới trên bảng đang có dữ liệu thật — nếu
   cần đổi kiểu, `NOT NULL`, hay xoá cột/bảng, đó là thay đổi rủi ro cao hơn,
   bàn với Thái trước khi viết.

## Revision hiện có

| ID | Nội dung |
| --- | --- |
| `e01c887a732b` | baseline RỖNG — cột mốc để `stamp`, không mô tả schema |
| `5c3a646a710f` | ADR-018 slice 0 — thêm 5 cột nullable vào `tasks`, bảng mới `task_steps` |
