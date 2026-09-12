"""task_planner_slice0_estimate_steps

Revision ID: 5c3a646a710f
Revises: e01c887a732b
Create Date: 2026-08-26 10:13:14.974418

ADR-018 slice 0 — chỉ schema, không có logic ghi `actual_minutes` (việc đó
ngoài phạm vi, xem `docs/projects/engineering/adr/adr-018-*.md` mục "Lộ
trình"). Mọi cột thêm vào `tasks` đều NULL, không phá dữ liệu cũ.

`upgrade()` tự kiểm tra cột/bảng/FK đã tồn tại chưa trước khi thêm — không
phải để "an toàn cho vui", mà vì có HAI đường một DB có thể tới revision này:

  * DB đang chạy (production): chưa có 5 cột/bảng mới -> upgrade() thêm mới.
  * DB dựng từ số 0 (dev/CI): `Base.metadata.create_all()` chạy TRƯỚC alembic
    (xem `src/main.py`), và model đã khai 5 cột + `task_steps` từ trước —
    nghĩa là `create_all()` một mình đã dựng DB tới đúng trạng thái mà
    revision này lẽ ra phải tạo ra. Không kiểm tồn tại thì upgrade() ném
    `duplicate column name` ngay bước ADD COLUMN đầu tiên trên một DB mới
    tinh — đã tự reproduce được lỗi này (xem docs/.../guide/alembic.md).

`downgrade()` KHÔNG có guard tương tự — nó luôn xoá thật, để test round-trip
(upgrade rồi downgrade) chứng minh được downgrade đảo ngược được, bất kể cột
đến từ upgrade() hay từ create_all().
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c3a646a710f"
down_revision: str | None = "e01c887a732b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TASK_COLUMNS = {
    "estimate_low_min": lambda: sa.Column("estimate_low_min", sa.Integer(), nullable=True),
    "estimate_high_min": lambda: sa.Column("estimate_high_min", sa.Integer(), nullable=True),
    "actual_minutes": lambda: sa.Column("actual_minutes", sa.Integer(), nullable=True),
    "depends_on_task_id": lambda: sa.Column("depends_on_task_id", sa.Integer(), nullable=True),
    "energy": lambda: sa.Column("energy", sa.String(length=16), nullable=True),
}
_FK_NAME = "fk_tasks_depends_on_task_id_tasks"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Cột thường: ADD COLUMN thẳng, chạy được trên cả Postgres lẫn SQLite,
    # không cần batch mode. Chỉ thêm cột chưa có (xem docstring ở trên).
    existing_columns = {c["name"] for c in inspector.get_columns("tasks")}
    for name, make_column in _NEW_TASK_COLUMNS.items():
        if name not in existing_columns:
            op.add_column("tasks", make_column())

    # FK tự tham chiếu (depends_on_task_id -> tasks.id): Postgres cho ALTER
    # TABLE ADD CONSTRAINT thẳng, không cần batch. SQLite không hỗ trợ ADD
    # CONSTRAINT nên bắt buộc dùng batch (recreate bảng) — cô lập riêng một
    # batch, KHÔNG gộp add_column vào chung batch này: từng thử gộp chung và
    # SQLite ném CircularDependencyError khi batch tự sắp lại thứ tự cột lúc
    # recreate.
    inspector = sa.inspect(bind)
    existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("tasks")}
    if _FK_NAME not in existing_fks:
        with op.batch_alter_table("tasks") as batch_op:
            batch_op.create_foreign_key(_FK_NAME, "tasks", ["depends_on_task_id"], ["id"])

    inspector = sa.inspect(bind)
    if "task_steps" not in inspector.get_table_names():
        op.create_table(
            "task_steps",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("estimate_min", sa.Integer(), nullable=True),
            sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        )

    inspector = sa.inspect(bind)
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("task_steps")}
    if "ix_task_steps_task_id" not in existing_indexes:
        op.create_index("ix_task_steps_task_id", "task_steps", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_task_steps_task_id", table_name="task_steps")
    op.drop_table("task_steps")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint(_FK_NAME, type_="foreignkey")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("energy")
        batch_op.drop_column("depends_on_task_id")
        batch_op.drop_column("actual_minutes")
        batch_op.drop_column("estimate_high_min")
        batch_op.drop_column("estimate_low_min")
