"""planner workspace preferences

Revision ID: b9d1e4f2a6c8
Revises: a1c4f7e29b30
Create Date: 2026-08-28
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9d1e4f2a6c8"
down_revision: str | Sequence[str] | None = "a1c4f7e29b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bảng có thể đã tồn tại: đường khởi tạo DB mới chạy `create_all` từ model
    # RỒI mới stamp và upgrade, nên tới đây bảng đã có sẵn và `create_table`
    # trần sẽ nổ "table planner_preferences already exists".
    # Migration `f6b9d12e4a70` đã dùng đúng cách này — theo cùng quy ước.
    inspector = sa.inspect(op.get_bind())
    if "planner_preferences" in inspector.get_table_names():
        return

    op.create_table(
        "planner_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("workday_start_minute", sa.Integer(), nullable=False, server_default="480"),
        sa.Column("lunch_start_minute", sa.Integer(), nullable=False, server_default="720"),
        sa.Column("lunch_end_minute", sa.Integer(), nullable=False, server_default="840"),
        sa.Column("workday_end_minute", sa.Integer(), nullable=False, server_default="1080"),
        sa.Column("happy_time_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("happy_time_start_minute", sa.Integer(), nullable=False, server_default="960"),
        sa.Column("happy_time_end_minute", sa.Integer(), nullable=False, server_default="1020"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_planner_preference_user"),
    )
    op.create_index("ix_planner_preferences_user_id", "planner_preferences", ["user_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "planner_preferences" not in inspector.get_table_names():
        return
    op.drop_index("ix_planner_preferences_user_id", table_name="planner_preferences")
    op.drop_table("planner_preferences")
