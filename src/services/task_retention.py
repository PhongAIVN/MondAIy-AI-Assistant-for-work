"""Retention rules for completed tasks.

Completed tasks stay queryable for one week so weekly summaries can use them,
then are removed together with their evidence.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from src.models.task import Task
from src.models.task_evidence import TaskEvidence

COMPLETED_TASK_RETENTION = timedelta(days=7)


def purge_expired_completed_tasks(db: Session, user_id: str | None = None) -> int:
    """Delete only completed tasks older than seven days.

    The fallback to ``updated_at`` keeps rows completed before the
    ``completed_at`` migration on the same retention policy.
    """
    cutoff = datetime.now(UTC) - COMPLETED_TASK_RETENTION
    stmt = select(Task).where(
        Task.status == "completed",
        or_(Task.completed_at < cutoff, and_(Task.completed_at.is_(None), Task.updated_at < cutoff)),
    )
    if user_id is not None:
        stmt = stmt.where(Task.user_id == user_id)
    rows = db.execute(stmt).scalars().all()
    if not rows:
        return 0

    task_ids = [row.id for row in rows]
    db.execute(delete(TaskEvidence).where(TaskEvidence.task_id.in_(task_ids)))
    db.execute(delete(Task).where(Task.id.in_(task_ids)))
    db.commit()
    return len(task_ids)
