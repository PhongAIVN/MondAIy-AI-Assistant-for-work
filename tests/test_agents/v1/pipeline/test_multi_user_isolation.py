"""Nhiều người dùng chung một hệ thống thì mỗi người phải chỉ thấy việc của mình.

Đường Jira đặc biệt đáng kiểm: nó không lọc theo người dùng ở tầng API (JQL lấy
cả dự án) mà dựa vào `CurrentUserContext.account_id` ở rule engine. Lấy nhầm
accountId của người khác thì issue của người này bị chấm bằng danh tính người
kia — không rò rỉ dữ liệu, nhưng sai người nhận việc.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete

from src.agents.pipeline.nodes.fetch import _fetch_one
from src.db import SessionLocal
from src.models.connection import Connection
from src.services.jira_rules import CurrentUserContext, NormalizedIssue, evaluate_issue

NOW = datetime(2026, 8, 21, tzinfo=UTC)


@pytest.fixture
def two_users():
    """Hai người dùng, mỗi người một kết nối Jira riêng."""
    created: list[int] = []
    with SessionLocal() as db:
        rows = []
        for _ in range(2):
            row = Connection(
                user_id=f"iso-{uuid.uuid4().hex[:8]}",
                provider="jira",
                provider_user_id=f"acc-{uuid.uuid4().hex[:8]}",
                external_site_id=f"cloud-{uuid.uuid4().hex[:6]}",
            )
            db.add(row)
            rows.append(row)
        db.commit()
        for row in rows:
            db.refresh(row)
            created.append(row.id)
        yield [(row.id, row.user_id, row.provider_user_id) for row in rows]
        db.execute(delete(Connection).where(Connection.id.in_(created)))
        db.commit()


def _issue(assignee: str | None) -> NormalizedIssue:
    return NormalizedIssue(
        issue_id="1",
        issue_key="TAPB-1",
        project="TAPB",
        title="Cần nộp báo cáo",
        description="Vui lòng nộp trước thứ Sáu.",
        assignee_account_id=assignee,
        status="In Progress",
        status_category="In Progress",
        resolution=None,
        priority="High",
        issue_type="Task",
        due_date=None,
        created_at=NOW,
        updated_at=NOW,
        url="https://example.atlassian.net/browse/TAPB-1",
    )


@pytest.mark.asyncio
async def test_a_run_cannot_fetch_another_users_connection(two_users):
    """Chốt chặn quan trọng nhất: `sources` đi từ client lên, nên id kết nối là
    dữ liệu người dùng gửi. Không kiểm chủ sở hữu thì một tài khoản có thể đọc
    hộp thư/bảng Jira của tài khoản khác."""
    (connection_id, owner_id, _), (_, other_user_id, _) = two_users

    with SessionLocal() as db:
        with pytest.raises(ValueError, match="Không tìm thấy connection"):
            await _fetch_one(
                db,
                run_id=1,
                ref={"connection_id": connection_id, "source_id": "TAPB"},
                time_from=NOW,
                time_to=NOW,
                user_id=other_user_id,
            )
        assert owner_id != other_user_id


def test_the_same_issue_is_kept_for_its_assignee_and_dropped_for_everyone_else(two_users):
    """Cùng một issue, hai người dùng, hai kết luận trái ngược — đó chính là
    điều luật "việc của tôi" phải làm được khi nhiều người dùng chung hệ thống."""
    (_, _, owner_account), (_, _, other_account) = two_users
    issue = _issue(assignee=owner_account)

    kept, _ = evaluate_issue(issue, CurrentUserContext(account_id=owner_account, timezone="UTC"), NOW)
    dropped, _ = evaluate_issue(issue, CurrentUserContext(account_id=other_account, timezone="UTC"), NOW)

    assert kept.decision != "DROP"
    assert dropped.decision == "DROP"
    assert dropped.reasons == ("NOT_ASSIGNED_TO_ME",)


def test_an_unassigned_issue_is_dropped_for_everyone(two_users):
    """Quyết định sản phẩm 2026-08-21: hộp việc chỉ chứa việc của chính người
    dùng, issue chưa ai nhận không thuộc về ai cả."""
    (_, _, owner_account), (_, _, other_account) = two_users
    issue = _issue(assignee=None)

    for account in (owner_account, other_account):
        decision, _ = evaluate_issue(issue, CurrentUserContext(account_id=account, timezone="UTC"), NOW)
        assert decision.decision == "DROP"
        assert decision.reasons == ("NOT_ASSIGNED_TO_ME",)


def test_a_connection_without_an_account_id_does_not_leak_everyone_elses_work(two_users):
    """Kết nối chưa lấy được accountId (scope thiếu, API lỗi) làm luật "việc của
    tôi" nằm im. Ghi lại hành vi này cho rõ: KHÔNG loại theo assignee nữa, nên
    người dùng sẽ thấy cả issue của người khác trong cùng dự án.

    Đó là đánh đổi có chủ đích — thà thừa còn hơn im lặng trả về rỗng — nhưng
    `ensure_account_id` phải chạy được thì mới không rơi vào nhánh này.
    """
    (_, _, owner_account) = two_users[0]
    issue = _issue(assignee=owner_account)

    decision, _ = evaluate_issue(issue, CurrentUserContext(account_id="", timezone="UTC"), NOW)

    assert decision.decision != "DROP"
