"""Thêm tasks.cancelled_at cho thùng rác task

Hợp đồng Thái chốt 27/08: huỷ task là đưa vào thùng rác, giữ 7 ngày để lục lại,
quá hạn thì xoá vĩnh viễn.

Cột này phải RIÊNG, không tái dùng `updated_at`: bất kỳ thao tác nào cũng chạm
`updated_at`, nên lấy nó làm mốc lưu giữ sẽ đẩy hạn xoá lùi mãi, hoặc xoá nhầm
task vừa được khôi phục.

CỐ Ý KHÔNG backfill cho task đã huỷ từ trước. Chúng giữ NULL, và
`purge_expired_trash` bỏ qua NULL, nên chúng nằm trong thùng rác vĩnh viễn cho
tới khi người dùng tự dọn. Backfill bằng `updated_at` sẽ đặt hạn xoá dựa trên
một mốc ta tự bịa — và với những task huỷ đã lâu, hạn đó rơi vào QUÁ KHỨ, tức
vòng dọn đầu tiên sau khi deploy sẽ xoá sạch chúng ngay lập tức, không ai kịp
thấy thùng rác lần nào. Thà để lại rác còn hơn xoá thứ người dùng chưa từng
được cảnh báo.

Revision ID: c4d8f1a2b7e3
Revises: 9a42dcf7b631
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d8f1a2b7e3"
down_revision: str | Sequence[str] | None = "9a42dcf7b631"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `create_all` dựng bảng thẳng từ model nên trên DB mới cột này đã có sẵn;
    # cùng khuôn với 9a42dcf7b631. Kiểm trước khi thêm để migration chạy được
    # cả trên DB đã có schema lẫn DB thật đi lên từ baseline.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("tasks")}
    if "cancelled_at" not in existing:
        op.add_column(
            "tasks",
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        )

    if bind.dialect.name != "postgresql":
        # Index một phần là cú pháp riêng của PostgreSQL. SQLite trong test
        # không cần nó — bảng ở đó nhỏ, và giả vờ tạo được sẽ che mất khác biệt
        # thật giữa hai môi trường.
        return
    if "ix_tasks_trash_cancelled_at" in {ix["name"] for ix in inspector.get_indexes("tasks")}:
        return
    # Task đang ở thùng rác luôn ít hơn hẳn tổng số task, và vòng dọn quét đúng
    # theo hai cột này. Index một phần giữ cho lần quét mỗi ngày không phải đọc
    # toàn bảng chỉ để tìm vài dòng.
    op.create_index(
        "ix_tasks_trash_cancelled_at",
        "tasks",
        ["cancelled_at"],
        unique=False,
        postgresql_where=sa.text("status = 'cancelled' AND cancelled_at IS NOT NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    # Index chỉ được tạo trên PostgreSQL, nên chỉ xoá ở đó — drop vô điều kiện
    # sẽ làm downgrade nổ trên SQLite vì index chưa từng tồn tại.
    if bind.dialect.name == "postgresql":
        op.drop_index("ix_tasks_trash_cancelled_at", table_name="tasks")
    op.drop_column("tasks", "cancelled_at")
