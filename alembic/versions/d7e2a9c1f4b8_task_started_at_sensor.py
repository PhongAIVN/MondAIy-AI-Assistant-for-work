"""Thêm tasks.started_at — cảm biến thời gian làm việc (ADR-021)

Hệ hiện chỉ biết task TỒN TẠI và task XONG, không biết gì về khoảng giữa — đúng
khoảng chứa toàn bộ thông tin về thói quen làm việc.

`completed_at` một mình là cảm biến sai: đo trên production 27/08, 9/14 task
được tick vào 0h-1h sáng, nhưng đó là giờ ngồi review lại cả buổi chứ không phải
giờ làm.

CỐ Ý KHÔNG backfill. Suy ngược từ `created_at` sẽ cho ra những khoảng hàng ngày
trời, và reference-class forecasting trong estimate.py sẽ học theo chúng. Một mốc
bịa còn tệ hơn không có mốc.

Revision ID: d7e2a9c1f4b8
Revises: c4d8f1a2b7e3
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7e2a9c1f4b8"
down_revision: str | Sequence[str] | None = "c4d8f1a2b7e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `create_all` dựng bảng thẳng từ model nên trên DB mới cột này đã có sẵn;
    # cùng khuôn với c4d8f1a2b7e3 và 9a42dcf7b631.
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("tasks")}
    if "started_at" not in existing:
        op.add_column("tasks", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "started_at")
