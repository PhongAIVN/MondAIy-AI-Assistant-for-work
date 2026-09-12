"""Học viên mức A nhận candidate rồi tự tạo task nháp cá nhân."""

import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.config import get_settings
from src.db import get_db
from src.models.announcement_candidate import AnnouncementCandidate
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.models.user import User

router = APIRouter(prefix="/announcement-candidates", tags=["tasks"])


def _require_level_a(user: User) -> str:
    if user.program_access_level != "A":
        raise HTTPException(
            status_code=403,
            detail="Tài khoản chưa khớp danh tính chương trình.",
        )
    return str(user.id)


def out(row: AnnouncementCandidate) -> dict:
    return {
        "id": row.id,
        "preview": row.preview,
        "evidence": row.evidence,
        "rawText": row.raw_text,
    }


@router.get("")
def list_candidates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    _require_level_a(user)
    rows = db.scalars(
        select(AnnouncementCandidate)
        .where(
            AnnouncementCandidate.cohort_slug == get_settings().program_cohort_slug,
            AnnouncementCandidate.status == "published",
        )
        .order_by(AnnouncementCandidate.published_at.desc())
    ).all()
    return {"items": [out(row) for row in rows]}


@router.post("/{candidate_id}/actions/{action_index}/add-task")
def add_task(
    candidate_id: int,
    action_index: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    user_id = _require_level_a(user)
    row = db.get(AnnouncementCandidate, candidate_id)
    if row is None or row.status != "published" or row.cohort_slug != get_settings().program_cohort_slug:
        raise HTTPException(404, "Candidate không tồn tại.")
    items = row.preview.get("items", [])
    if action_index < 0 or action_index >= len(items):
        raise HTTPException(422, "Action index không hợp lệ.")
    action = items[action_index]
    key = "announcement-" + hashlib.sha256(f"{user_id}:{row.id}:{action_index}".encode()).hexdigest()[:48]
    task = db.scalar(select(Task).where(Task.user_id == user_id, Task.cluster_key == key))
    if task is None:
        due_at = datetime.fromisoformat(action["dueAt"]) if action.get("dueAt") else None
        task = Task(
            user_id=user_id,
            cluster_key=key,
            title=action["title"],
            detail=row.raw_text,
            due_at=due_at,
            all_day=bool(action.get("allDay")),
            ambiguous=bool(action.get("ambiguous")),
            status="proposed",
            source_count=1,
            signal_strength=1.0,
            reasons=[
                "Discord announcement candidate",
                f"candidate:{row.id}:action:{action_index}",
            ],
        )
        db.add(task)
        db.flush()
        db.add(
            TaskEvidence(
                task_id=task.id,
                provider="discord-admin-paste",
                evidence_quote=row.raw_text[:2000],
                deep_link=row.evidence.get("deepLink") or "",
                has_attachment=False,
            )
        )
        db.commit()
        db.refresh(task)
    return {"taskId": task.id, "status": task.status}
