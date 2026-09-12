"""baseline_existing_schema

Revision ID: e01c887a732b
Revises:
Create Date: 2026-08-26 10:13:14.698667

Cột mốc RỖNG có chủ đích — KHÔNG mô tả schema, KHÔNG autogenerate.

P-004 chưa từng dùng Alembic. Schema production đến nay được dựng bằng
`Base.metadata.create_all()` (chỉ tạo bảng còn thiếu) cộng
`ensure_runtime_schema()` trong `src/db.py` (~25 hàm `_ensure_*` vá cột tay,
vẫn tiếp tục chạy sau khi có Alembic — không đụng tới trong revision này).

Đo trực tiếp production so với `Base.metadata` (2026-08-25) cho thấy production
là TẬP CHA của model — có ba thứ trên DB thật mà model KHÔNG khai:

  * bảng `program_schedule_templates` (17 cột) — mồ côi, 0 tham chiếu trong code.
  * cột `users.program_cohort_slug` — mồ côi. ĐỪNG nhầm với setting
    `settings.program_cohort_slug` ở `src/config.py:30` — hai thứ khác nhau
    hoàn toàn (một là config chọn cohort đang phục vụ, một là cột DB không ai
    dùng nữa).
  * cột `chunks.fts` — CỐ Ý, do `_ensure_postgres_fts_schema()` trong
    `src/db.py` tạo và duy trì; model không bao giờ khai cột này vì nó chỉ
    phục vụ full-text search ở tầng SQL.

Nếu revision này (hoặc bất kỳ revision nào sau) chạy `alembic revision
--autogenerate`, Alembic sẽ so `Base.metadata` với DB thật, thấy ba thứ trên
"thừa" so với model, và sinh migration DROP chúng. Chạy migration đó lên
production là mất một bảng và hai cột dữ liệu thật.

Vì vậy `upgrade()`/`downgrade()` ở đây chỉ có `pass`. Revision này tồn tại để
`alembic stamp e01c887a732b` lên một DB production đang chạy — đánh dấu "mọi
thứ trước đây đã tồn tại rồi", không phải để mô tả hay tái tạo schema đó.
Người dọn dẹp sau này: đừng "dọn" ba thứ mồ côi ở trên chỉ vì autogenerate nói
vậy — kiểm lại với người đã đo (xem AGENTS.md, mục "Measure the thing you are
about to claim") trước khi DROP bất cứ gì trong danh sách này.
"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'e01c887a732b'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
