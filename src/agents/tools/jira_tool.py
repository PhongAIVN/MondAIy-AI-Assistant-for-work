"""Read-only Jira source tool backed by the canonical task/evidence registry."""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from datetime import datetime

from langchain_core.tools import tool
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from src.models.task import Task
from src.models.task_evidence import TaskEvidence

logger = logging.getLogger(__name__)
_user_id: ContextVar[str | None] = ContextVar("jira_user_id", default=None)
_MAX_RESULTS = 30


def set_jira_scope(user_id: str) -> None:
    _user_id.set(user_id or None)


def reset_jira_scope() -> None:
    _user_id.set(None)


def _format_due(value: datetime | None) -> str:
    return value.isoformat() if value else "chưa có deadline"


def _jira_search_terms(query: str) -> list[str]:
    """Extract stable project/issue identifiers from natural-language follow-ups."""
    terms = re.findall(r"\b[A-Z][A-Z0-9]+-\d+\b", query)
    project = re.search(r"(?:dự án|du an|project)\s+([\w-]+)", query, flags=re.IGNORECASE)
    if project:
        terms.append(project.group(1))
    return list(dict.fromkeys(term.casefold() for term in terms if len(term) > 2))


@tool
def jira_search_issues(query: str = "", due_after: str = "", due_before: str = "") -> str:
    """Đọc issue Jira đã sync và có evidence Jira của user hiện tại."""
    user_id = _user_id.get()
    if not user_id:
        return "Chưa xác định được Jira của người dùng nên chưa đọc."

    from src.agents.tools.time_tool import parse_timestamp
    from src.db import engine

    bounds: dict[str, datetime] = {}
    for name, value in (("due_after", due_after), ("due_before", due_before)):
        if not value.strip():
            continue
        parsed = parse_timestamp(value)
        if parsed is None:
            return f"Không hiểu mốc {name}={value!r}; Jira chưa được đọc."
        bounds[name] = parsed.moment
    if bounds.get("due_after") and bounds.get("due_before") and bounds["due_after"] > bounds["due_before"]:
        return "Khoảng deadline Jira không hợp lệ: due_after muộn hơn due_before."

    base_stmt = (
        select(Task, TaskEvidence)
        .join(TaskEvidence, TaskEvidence.task_id == Task.id)
        .where(Task.user_id == user_id, TaskEvidence.provider == "jira")
        .order_by(Task.due_at.asc(), Task.updated_at.desc())
    )
    stmt = base_stmt
    if bounds.get("due_after"):
        stmt = stmt.where(Task.due_at >= bounds["due_after"])
    if bounds.get("due_before"):
        stmt = stmt.where(Task.due_at < bounds["due_before"])

    needles = _jira_search_terms(query)
    undated_rows: list[tuple[Task, TaskEvidence]] = []
    undated_count = 0
    undated_link = ""

    try:
        with Session(engine) as db:
            rows = db.execute(stmt.limit(_MAX_RESULTS * 3)).all()
            if bounds and needles:
                undated_rows = db.execute(base_stmt.where(Task.due_at.is_(None))).all()
            elif bounds:
                undated_count = db.scalar(
                    select(func.count(distinct(Task.id)))
                    .join(TaskEvidence, TaskEvidence.task_id == Task.id)
                    .where(
                        Task.user_id == user_id,
                        TaskEvidence.provider == "jira",
                        Task.due_at.is_(None),
                    )
                ) or 0
                undated_link = (
                    db.scalar(
                        select(TaskEvidence.deep_link)
                        .join(Task, Task.id == TaskEvidence.task_id)
                        .where(
                            Task.user_id == user_id,
                            TaskEvidence.provider == "jira",
                            Task.due_at.is_(None),
                            func.length(func.trim(TaskEvidence.deep_link)) > 0,
                        )
                        .order_by(Task.updated_at.desc())
                        .limit(1)
                    )
                    or ""
                ).strip()
    except Exception as exc:
        logger.warning("Đọc Jira registry hỏng cho user %s: %s", user_id, exc)
        return f"Không đọc được Jira: {exc}"

    visible: list[tuple[Task, TaskEvidence]] = []
    seen_tasks: set[int] = set()
    for task, evidence in rows:
        haystack = f"{task.title} {task.detail} {evidence.evidence_quote} {evidence.deep_link}".casefold()
        if needles and not any(needle in haystack for needle in needles):
            continue
        if task.id in seen_tasks:
            continue
        seen_tasks.add(task.id)
        visible.append((task, evidence))
        if len(visible) >= _MAX_RESULTS:
            break

    if undated_rows:
        undated_task_ids: set[int] = set()
        for task, evidence in undated_rows:
            haystack = f"{task.title} {task.detail} {evidence.evidence_quote} {evidence.deep_link}".casefold()
            if not any(needle in haystack for needle in needles):
                continue
            undated_task_ids.add(task.id)
            if not undated_link and evidence.deep_link.strip():
                undated_link = evidence.deep_link.strip()
        undated_count = len(undated_task_ids)

    lines = (
        [f"Jira canonical source: {len(visible)} issue/task liên quan."]
        if visible
        else ["Không phát hiện issue Jira nào trong phạm vi canonical Jira đã đồng bộ."]
    )
    for task, evidence in visible:
        assignee = getattr(task, "assignee", None)
        ownership = (
            f"  phan cong Jira: {assignee}"
            if assignee and not getattr(task, "assignee_ambiguous", False)
            else "  phan cong Jira: chua xac minh"
        )
        lines.append(
            f"- {task.title} — trạng thái task {task.status}, deadline {_format_due(task.due_at)}\n"
            f"{ownership} (muc nay dung de xem boi canh; chi task cua ban moi vao danh sach can duyet/len lich)\n"
            f"  evidence Jira: {evidence.evidence_quote[:400]}\n"
            f"  nguồn: {evidence.deep_link}"
        )
    if undated_count:
        if undated_link:
            lines.append(f"Ngoài ra còn {undated_count} issue Jira chưa có deadline — xem tại {undated_link}")
        else:
            lines.append(
                f"Ngoài ra còn {undated_count} issue Jira chưa có deadline — "
                "không có link Jira thật trong dữ liệu đã đồng bộ."
            )
    return "\n".join(lines)
