import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db import Base
from src.models.run import Run


@pytest.fixture(scope="session")
def pipeline_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def pipeline_state(pipeline_session_factory):
    db = pipeline_session_factory()
    run = Run(
        user_id=1,
        sources=[],
        range_from=datetime.now(UTC),
        range_to=datetime.now(UTC),
        idempotency_key=f"pipeline-test-{uuid.uuid4()}",
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    state = {
        "db": db,
        "run_id": run.id,
        "user_id": "u-test",
        "user_email": "user@example.com",
        "time_from": datetime(2026, 8, 8, tzinfo=UTC),
        "time_to": datetime(2026, 8, 9, tzinfo=UTC),
        "timezone": "Asia/Ho_Chi_Minh",
        "sources": [],
        "errors": [],
        "normalized": [],
        "filtered": [],
        "batches": [],
        "extracted": [],
        "resolved": [],
        "clusters": [],
    }
    try:
        yield state
    finally:
        db.close()


def gmail_item(
    message_id="m1",
    text="Please submit the report by Friday",
    *,
    connection_id=None,
    attachments=None,
    importance="critical",
    classification_reasons=None,
    subject="",
):
    return {
        "id": message_id,
        "provider": "google",
        "source_id": "INBOX",
        "thread_id": f"t-{message_id}",
        "author_id": "mentor@example.com",
        "author_name": "Mentor",
        "is_self": False,
        "is_dm": False,
        "text": text,
        "subject": subject,
        "sent_at": datetime(2026, 8, 8, 8, tzinfo=UTC),
        "deep_link": f"https://mail.google.com/mail/u/0/#inbox/{message_id}",
        "to": ["user@example.com"],
        "cc": [],
        "connection_id": connection_id,
        "attachments": attachments or [],
        "importance": importance,
        "classification_reasons": classification_reasons or [],
    }


def jira_item(
    issue_key="TO04-42",
    connection_id=1,
    *,
    title="Hoàn thành báo cáo tuần 3",
    text="Đội cần nộp trước thứ Sáu.",
    assignee_account_id="acc-phong-01",
    status_category="In Progress",
    resolution=None,
    priority="High",
    due_date=datetime(2026, 8, 15, tzinfo=UTC),
):
    return {
        "id": issue_key,
        "provider": "jira",
        "source_id": "TO04",
        "thread_id": issue_key,
        "author_id": "acc-reporter-1",
        "author_name": "Reporter",
        "subject": title,
        "is_self": False,
        "is_dm": False,
        "text": text,
        "sent_at": datetime(2026, 8, 10, tzinfo=UTC),
        "deep_link": f"https://vinait004.atlassian.net/browse/{issue_key}",
        "connection_id": connection_id,
        "jira_assignee_account_id": assignee_account_id,
        "jira_status": status_category,
        "jira_status_category": status_category,
        "jira_resolution": resolution,
        "jira_priority": priority,
        "jira_issue_type": "Task",
        "jira_due_date": due_date,
        "jira_created_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
