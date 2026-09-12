"""task_brief_fields

Revision ID: 9a42dcf7b631
Revises: 5c3a646a710f
Create Date: 2026-08-26

ADR-019 — giữ các trường phiếu giao việc đã trích thành cột riêng trên
`tasks`; tất cả nullable để dữ liệu task cũ không đổi. Không autogenerate:
baseline e01c887a732b giải thích các đối tượng production không thuộc model mà
Alembic sẽ nhận nhầm là phải DROP.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a42dcf7b631"
down_revision: str | None = "5c3a646a710f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TASK_COLUMNS = {
    "expected_output": lambda: sa.Column("expected_output", sa.Text(), nullable=True),
    "acceptance_criteria": lambda: sa.Column("acceptance_criteria", sa.Text(), nullable=True),
    "context_input": lambda: sa.Column("context_input", sa.Text(), nullable=True),
    "constraints": lambda: sa.Column("constraints", sa.Text(), nullable=True),
    "execution_tool": lambda: sa.Column("execution_tool", sa.Text(), nullable=True),
    "execution_method": lambda: sa.Column("execution_method", sa.Text(), nullable=True),
    "stated_priority": lambda: sa.Column("stated_priority", sa.String(length=32), nullable=True),
    "stakeholders": lambda: sa.Column(
        "stakeholders", sa.JSON(), nullable=True, server_default=sa.text("'[]'")
    ),
    "deliver_to": lambda: sa.Column("deliver_to", sa.Text(), nullable=True),
}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("tasks")}
    for name, make_column in _NEW_TASK_COLUMNS.items():
        if name not in existing_columns:
            op.add_column("tasks", make_column())


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        for name in reversed(_NEW_TASK_COLUMNS):
            batch_op.drop_column(name)
