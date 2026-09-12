"""Seed 1 tài khoản demo cố định + vài task mẫu, không phụ thuộc Jira/Gmail/
Outlook/Calendar thật — dùng cho demo nội bộ (TAPB Sprint 4) khi không có kết
nối OAuth sống hoặc mạng chặn.

Idempotent: chạy lại nhiều lần không tạo trùng user/cluster (upsert theo
email/cluster_key). An toàn chạy trên DB dev/demo, KHÔNG chạy trên DB pilot/
production thật (tạo dữ liệu giả trộn vào dữ liệu người dùng thật).

Yêu cầu: DB đã có schema (chạy `make run` một lần trước để tự tạo bảng qua
create_all + ensure_runtime_schema, xem src/main.py lifespan).

    .venv/Scripts/python.exe scripts/seed_demo.py
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Console Windows mac dinh cp1252, khong in duoc dau tieng Viet -> UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from src.db import SessionLocal  # noqa: E402
from src.models.cluster import Cluster, ClusterMessage  # noqa: E402
from src.models.message import Message  # noqa: E402
from src.models.task import Task  # noqa: E402
from src.models.task_evidence import TaskEvidence  # noqa: E402
from src.models.user import User  # noqa: E402
from src.models.user_memory import UserMemory  # noqa: E402
from src.services import auth as auth_service  # noqa: E402

DEMO_EMAIL = "demo@mondaiy.local"
DEMO_PASSWORD = "MondaiyDemo2026!"
DEMO_DISPLAY_NAME = "Demo Pilot"


def _get_or_create_user(db) -> User:
    user = db.execute(select(User).where(User.email == DEMO_EMAIL)).scalar_one_or_none()
    if user is not None:
        print(f"User demo đã tồn tại: {DEMO_EMAIL} (id={user.id})")
        return user

    user = User(
        email=DEMO_EMAIL,
        password_hash=auth_service.hash_password(DEMO_PASSWORD),
        display_name=DEMO_DISPLAY_NAME,
        role="participant",
        program_access_level="A",
        is_active=True,
    )
    db.add(user)
    db.flush()
    print(f"Tạo user demo mới: {DEMO_EMAIL} (id={user.id})")
    return user


def _seed_task(
    db,
    user_id: str,
    cluster_key: str,
    title: str,
    detail: str,
    provider: str,
    author_name: str,
    text: str,
    due_in_hours: float | None,
    status: str,
    deep_link: str,
) -> None:
    existing_task = db.execute(
        select(Task).where(Task.user_id == user_id, Task.cluster_key == cluster_key)
    ).scalar_one_or_none()
    if existing_task is not None:
        print(f"  Bỏ qua (đã có): {cluster_key}")
        return

    # Cluster.task_id la ondelete=SET NULL (khong phai CASCADE), va Message
    # khong co FK toi Cluster/Task (doc lap voi vong doi Task) - xoa rieng
    # Task (vd luc reset demo) khong tu dong xoa Cluster/Message di kem, de
    # lai row mo coi trung unique constraint khi seed lai. Don truoc, khong
    # thi insert vo. Lam script nay tu-heal duoc voi bat ky kieu reset nao.
    external_id = f"{cluster_key}-msg-1"
    orphan_cluster = db.execute(
        select(Cluster).where(Cluster.user_id == user_id, Cluster.cluster_key == cluster_key)
    ).scalar_one_or_none()
    if orphan_cluster is not None:
        db.delete(orphan_cluster)
        db.flush()

    orphan_message = db.execute(
        select(Message).where(
            Message.provider == provider,
            Message.source_id == "demo-seed",
            Message.external_id == external_id,
        )
    ).scalar_one_or_none()
    if orphan_message is not None:
        db.delete(orphan_message)
        db.flush()

    now = datetime.now(UTC)
    due_at = now + timedelta(hours=due_in_hours) if due_in_hours is not None else None

    message = Message(
        user_id=user_id,
        provider=provider,
        source_id="demo-seed",
        external_id=external_id,
        author_id="demo-author",
        author_name=author_name,
        is_self=False,
        is_dm=True,
        text=text,
        sent_at=now - timedelta(hours=2),
        deep_link=deep_link,
    )
    db.add(message)
    db.flush()

    cluster = Cluster(user_id=user_id, cluster_key=cluster_key, signal_strength=0.8, due_at=due_at)
    db.add(cluster)
    db.flush()
    db.add(ClusterMessage(cluster_id=cluster.id, message_id=message.id))

    task = Task(
        user_id=user_id,
        cluster_key=cluster_key,
        title=title,
        detail=detail,
        due_at=due_at,
        status=status,
        source_count=1,
        signal_strength=0.8,
    )
    db.add(task)
    db.flush()
    cluster.task_id = task.id

    db.add(
        TaskEvidence(
            task_id=task.id,
            message_id=message.id,
            provider=provider,
            evidence_quote=text,
            deep_link=deep_link,
        )
    )
    print(f"  Tạo task ({status}): {title}")


def _seed_memory(db, user_id: str) -> None:
    """Seed 3 memories mẫu với status khác nhau (candidate, confirmed, disputed)."""
    now = datetime.now(UTC)
    memories = [
        {
            "memory_key": "demo-response-style-candidate",
            "kind": "preference",
            "subject": "user",
            "predicate": "response_style",
            "value": "concise",
            "status": "candidate",
            "source_authority": "inferred",
            "created_by": "model",
            "confidence": 0.72,
            "importance": 0.6,
            "note": "Chờ xem xét",
        },
        {
            "memory_key": "demo-timezone-confirmed",
            "kind": "context",
            "subject": "user",
            "predicate": "timezone",
            "value": "Asia/Ho_Chi_Minh",
            "status": "confirmed",
            "source_authority": "user",
            "created_by": "user",
            "confidence": 1.0,
            "importance": 0.9,
            "note": "Đã xác nhận",
        },
        {
            "memory_key": "demo-work-hours-disputed",
            "kind": "preference",
            "subject": "user",
            "predicate": "work_hours",
            "value": "8:00-17:00",
            "status": "disputed",
            "source_authority": "inferred",
            "created_by": "model",
            "confidence": 0.45,
            "importance": 0.7,
            "note": "Có phản hồi tiêu cực",
            "negative_feedback_count": 1,
        },
    ]

    for mem_data in memories:
        # Kiểm tra xem memory đã tồn tại chưa (idempotent).
        existing = db.execute(
            select(UserMemory).where(
                UserMemory.user_id == int(user_id),
                UserMemory.memory_key == mem_data["memory_key"],
            )
        ).scalar_one_or_none()

        if existing is not None:
            print(f"  Bỏ qua memory (đã có): {mem_data['memory_key']}")
            continue

        # Tạo memory mới.
        memory = UserMemory(
            user_id=int(user_id),
            memory_key=mem_data["memory_key"],
            version=1,
            kind=mem_data["kind"],
            subject=mem_data["subject"],
            predicate=mem_data["predicate"],
            object_json={"value": mem_data["value"]},
            search_text=f"{mem_data['subject']} {mem_data['predicate']} {mem_data['value']}",
            status=mem_data["status"],
            source_authority=mem_data["source_authority"],
            created_by=mem_data["created_by"],
            confidence=mem_data["confidence"],
            importance=mem_data["importance"],
            first_observed_at=now - timedelta(days=2),
            last_reinforced_at=now,
            reinforcement_count=2 if mem_data["status"] == "confirmed" else 1,
            negative_feedback_count=mem_data.get("negative_feedback_count", 0),
        )
        db.add(memory)
        db.flush()
        print(f"  Tạo memory ({mem_data['status']}): {mem_data['memory_key']} — {mem_data['note']}")


def main() -> int:
    db = SessionLocal()
    try:
        user = _get_or_create_user(db)
        db.commit()

        user_id = str(user.id)
        print("Seed task mẫu:")
        _seed_task(
            db,
            user_id,
            cluster_key="demo-jira-report",
            title="Nộp báo cáo tuần 3",
            detail="Issue TO04-42 — Hoàn thành báo cáo tuần 3, ưu tiên High.",
            provider="jira",
            author_name="Jira Bot",
            text="TO04-42: Hoàn thành báo cáo tuần 3 trước thứ Sáu. Priority: High.",
            due_in_hours=20,
            status="proposed",
            deep_link="https://example.atlassian.net/browse/TO04-42",
        )
        _seed_task(
            db,
            user_id,
            cluster_key="demo-gmail-deadline",
            title="Nộp bài tập Payment API",
            detail="Mentor nhắc hoàn thành module Payment API.",
            provider="google",
            author_name="Mentor Demo",
            text="Nhớ hoàn thành Payment API backend trước 5h chiều mai nhé.",
            due_in_hours=30,
            status="confirmed",
            deep_link="https://mail.google.com/mail/u/0/#all/demo-msg-1",
        )
        _seed_task(
            db,
            user_id,
            cluster_key="demo-calendar-standup",
            title="Standup team AI20K",
            detail="Sự kiện lịch — standup hàng ngày.",
            provider="google",
            author_name="Google Calendar",
            text="Standup team AI20K — 9:00 sáng, phòng họp online.",
            due_in_hours=4,
            status="proposed",
            deep_link="https://calendar.google.com/calendar/event?eid=demo-event-1",
        )
        db.commit()

        print("\nSeed memory mẫu:")
        _seed_memory(db, user_id)
        db.commit()

        print()
        print("Xong. Đăng nhập demo:")
        print(f"  email:    {DEMO_EMAIL}")
        print(f"  password: {DEMO_PASSWORD}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
