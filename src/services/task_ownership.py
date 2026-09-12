"""Ownership rules for turning extracted tasks into personal actions.

Jira data is stored under the connected app user, but an issue can be assigned
to somebody else.  ``Task.user_id`` therefore answers who may read the data,
not who should be reminded to do the work.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.connection import Connection
from src.models.task import Task
from src.models.task_evidence import TaskEvidence


def jira_account_ids(db: Session, user_id: str) -> set[str]:
    """Return the connected Jira account ids belonging to ``user_id``."""

    values = db.scalars(
        select(Connection.provider_user_id).where(
            Connection.user_id == user_id,
            Connection.provider == "jira",
            Connection.status.notin_(
                ["disconnected", "error", "expired", "revoked"]
            ),
            Connection.provider_user_id.is_not(None),
        )
    ).all()
    return {value.strip().casefold() for value in values if value and value.strip()}


def personal_task_ids(
    db: Session,
    user_id: str,
    tasks: Iterable[Task],
) -> set[int]:
    """Return task ids safe to present as the user's own actionable work.

    Tasks without an explicit assignee remain personal: this is the normal
    state for Gmail/Discord extraction and for unresolved ownership.  For Jira
    tasks with an explicit assignee, only the current connected Jira account
    is personal.  Other Jira assignees remain readable as context elsewhere,
    but must not become approval/calendar cards.
    """

    task_list = list(tasks)
    if not task_list:
        return set()

    task_ids = [task.id for task in task_list]
    jira_task_ids = set(
        db.scalars(
            select(TaskEvidence.task_id).where(
                TaskEvidence.task_id.in_(task_ids),
                TaskEvidence.provider == "jira",
            )
        ).all()
    )
    own_accounts = jira_account_ids(db, user_id)

    visible: set[int] = set()
    for task in task_list:
        if task.id not in jira_task_ids:
            visible.add(task.id)
            continue
        if task.assignee is None or task.assignee_ambiguous:
            visible.add(task.id)
            continue
        if task.assignee.strip().casefold() in own_accounts:
            visible.add(task.id)
    return visible
