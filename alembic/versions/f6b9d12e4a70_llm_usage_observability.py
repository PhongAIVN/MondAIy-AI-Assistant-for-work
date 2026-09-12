"""Thêm ledger usage LLM nội bộ, không lưu prompt/response.

Revision ID: f6b9d12e4a70
Revises: d7e2a9c1f4b8
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6b9d12e4a70"
down_revision: str | Sequence[str] | None = "d7e2a9c1f4b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "llm_usage_events" in inspector.get_table_names():
        return
    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("lane", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("usage_available", sa.Boolean(), nullable=False),
        sa.Column("price_available", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_usage_user_time", "llm_usage_events", ["user_id", "created_at"])
    op.create_index(
        "ix_llm_usage_model_lane_time",
        "llm_usage_events",
        ["model", "lane", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_usage_model_lane_time", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_user_time", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
