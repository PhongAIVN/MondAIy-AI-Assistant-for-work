"""Luật "câu chat này có kéo đồng bộ không".

Người dùng không còn bấm Sync tay (nút đã ẩn), nên luật này là thứ duy nhất
quyết định dữ liệu có được làm mới hay không. Tách khỏi phần thực thi để kiểm
được bằng test thuần, không cần mạng.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete

from src.db import SessionLocal
from src.models.run import Run
from src.models.schemas import SyncSourceRef
from src.models.user import User
from src.services import chat_sync
from src.services.work_question import asks_about_work

NOW = datetime(2026, 8, 21, 3, 0, tzinfo=UTC)  # 10:00 giờ Việt Nam
TZ = "Asia/Ho_Chi_Minh"


@pytest.fixture
def db_session():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def user(db_session):
    """Xoá sạch sau mỗi test.

    Suite này chạy trên cùng database với môi trường dev, nên một hàng `runs`
    trạng thái "running" bỏ lại sẽ nằm mãi trong bảng và làm nhiễu chính thứ
    module này đọc (`_latest_run`), lẫn các truy vấn chẩn đoán khi debug thật.
    """
    row = User(email=f"chat-sync-{uuid.uuid4().hex[:10]}@example.test", password_hash="x")
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    user_id = row.id
    yield row
    db_session.rollback()
    db_session.execute(delete(Run).where(Run.user_id == user_id))
    db_session.execute(delete(User).where(User.id == user_id))
    db_session.commit()


def _add_run(db_session, user, *, created_at, status="succeeded"):
    run = Run(
        user_id=user.id,
        sources=[{"connection_id": 1, "source_id": "INBOX"}],
        range_from=created_at - timedelta(hours=1),
        range_to=created_at,
        idempotency_key=f"k-{uuid.uuid4().hex[:12]}",
        timezone=TZ,
        language="vi",
        mode="task_extraction",
        status=status,
        created_at=created_at,
    )
    db_session.add(run)
    db_session.commit()
    return run


def test_a_casual_chat_never_syncs_even_as_the_first_chat_of_the_day(db_session, user):
    """"hi" không phải câu hỏi việc — không đáng bắt người dùng chờ hết lượt
    discover_sync_sources() chỉ vì đây là câu chat đầu tiên trong ngày."""
    decision = chat_sync.decide(db_session, user.id, asks_about_work=False, timezone=TZ, now=NOW)
    assert not decision.should_sync
    assert decision.reason == "not_a_work_question"


def test_first_work_question_of_the_day_triggers_a_sync(db_session, user):
    decision = chat_sync.decide(db_session, user.id, asks_about_work=True, timezone=TZ, now=NOW)
    assert decision.should_sync
    assert decision.reason == "first_work_question_of_day"


def test_the_day_boundary_follows_the_user_timezone_not_utc(db_session, user):
    """Run lúc 23:00 giờ Việt Nam hôm trước = 16:00 UTC. Chốt theo UTC thì nó
    vẫn "cùng ngày" với 03:00 UTC hôm sau, và người dùng ở GMT+7 sẽ thấy mốc
    ngày nhảy vào lúc 7 giờ sáng."""
    _add_run(db_session, user, created_at=NOW - timedelta(hours=11))  # 20/08 16:00 UTC
    decision = chat_sync.decide(db_session, user.id, asks_about_work=True, timezone=TZ, now=NOW)
    assert decision.should_sync
    assert decision.reason == "first_work_question_of_day"


def test_second_chat_of_the_same_day_does_not_resync(db_session, user):
    _add_run(db_session, user, created_at=NOW - timedelta(minutes=5))
    decision = chat_sync.decide(db_session, user.id, asks_about_work=True, timezone=TZ, now=NOW)
    assert not decision.should_sync
    assert decision.reason == "recent_enough"


def test_a_work_question_forces_a_resync_once_data_is_stale(db_session, user):
    _add_run(db_session, user, created_at=NOW - timedelta(hours=3))
    decision = chat_sync.decide(db_session, user.id, asks_about_work=True, timezone=TZ, now=NOW)
    assert decision.should_sync
    assert decision.reason == "stale_work_question"


def test_a_work_question_on_fresh_data_does_not_resync(db_session, user):
    _add_run(db_session, user, created_at=NOW - timedelta(minutes=10))
    decision = chat_sync.decide(db_session, user.id, asks_about_work=True, timezone=TZ, now=NOW)
    assert not decision.should_sync


def test_a_run_already_in_flight_is_never_interrupted(db_session, user):
    """Người dùng vẫn nhận được câu trả lời từ dữ liệu sẵn có; xếp thêm run chỉ
    đâm vào trần per-user rồi hỏng."""
    _add_run(db_session, user, created_at=NOW - timedelta(minutes=1), status="running")
    decision = chat_sync.decide(db_session, user.id, asks_about_work=True, timezone=TZ, now=NOW)
    assert not decision.should_sync
    assert decision.reason == "run_in_progress"


def test_two_questions_seconds_apart_share_one_idempotency_key(db_session, user):
    """Cùng khoá thì enqueue_run() trả lại run cũ — không chạy pipeline hai lần
    chỉ vì người dùng hỏi lại."""
    _add_run(db_session, user, created_at=NOW - timedelta(hours=3))
    first = chat_sync.decide(db_session, user.id, asks_about_work=True, timezone=TZ, now=NOW)
    second = chat_sync.decide(
        db_session, user.id, asks_about_work=True, timezone=TZ, now=NOW + timedelta(seconds=8)
    )
    assert first.idempotency_key == second.idempotency_key


def test_the_daily_key_is_stable_across_the_whole_day(db_session, user):
    morning = chat_sync.decide(db_session, user.id, asks_about_work=True, timezone=TZ, now=NOW)
    evening = chat_sync.decide(
        db_session, user.id, asks_about_work=True, timezone=TZ, now=NOW + timedelta(hours=6)
    )
    assert morning.idempotency_key == evening.idempotency_key


def test_an_unknown_timezone_falls_back_instead_of_crashing(db_session, user):
    """Múi giờ do client gửi lên; một chuỗi rác không được đánh sập câu chat."""
    decision = chat_sync.decide(db_session, user.id, asks_about_work=True, timezone="Mars/Olympus", now=NOW)
    assert decision.should_sync


@pytest.mark.parametrize(
    ("language", "message"),
    [
        ("vi", "hôm nay tôi có task gì không?"),
        ("vi", "liệt kê công việc cần làm giúp tôi"),
        ("en", "what tasks do I have today?"),
        ("en", "show me my to-do list"),
        ("ja", "今日のタスクは何かありますか？"),
        ("zh", "我今天有什么待办？"),
        ("ko", "오늘 업무 뭐 있어요?"),
        ("vi", "lịch tuần này thế nào?"),
        ("vi", "gmail có gì mới không?"),
        ("vi", "jira có gì mới không?"),
        ("vi", "đồng bộ xem có gì thay đổi không?"),
    ],
)
def test_work_questions_are_recognised_in_every_language(language, message):
    assert asks_about_work(message), language


@pytest.mark.parametrize(
    "message",
    [
        "",
        "chào buổi sáng",
        "tóm tắt mail hôm nay giúp tôi",
        "how is the weather today?",
        # Câu RA LỆNH tạo việc, không phải câu hỏi xem đang có gì — có danh từ
        # "task" nhưng không được kéo đồng bộ.
        "tạo task nhắc tôi họp lúc 3h",
        "create a task for the standup",
    ],
)
def test_non_work_questions_are_not_recognised(message):
    assert not asks_about_work(message)


class TestSourcePriority:
    """Thứ tự giữ lại khi vượt trần max_sync_sources.

    Lỗi thật: tài khoản Google mang theo 9 lịch Google Classroom, cắt trần theo
    thứ tự connector trả về thì chúng chiếm trọn 10 chỗ — hộp thư INBOX và dự
    án Jira bị đẩy văng, tức lần đồng bộ không quét đúng nguồn việc.
    """

    MAILBOX = {4: "me@gmail.com"}

    def _rank(self, source_id: str, connection_id: int = 4) -> int:
        ref = SyncSourceRef(connection_id=connection_id, source_id=source_id)
        return chat_sync._by_priority(ref, self.MAILBOX)[0]

    def test_inbox_outranks_everything(self):
        assert self._rank("INBOX") < self._rank("TAPB", connection_id=5)
        assert self._rank("INBOX") < self._rank("calendar:me@gmail.com")

    def test_non_calendar_sources_outrank_calendars(self):
        """Dự án Jira/thư mục Outlook chỉ có vài cái mỗi kết nối, không có nguy
        cơ tràn — để lịch chen lên trước chúng là mất nguồn việc thật."""
        assert self._rank("TAPB", connection_id=5) < self._rank("calendar:me@gmail.com")

    def test_the_users_own_calendar_outranks_shared_ones(self):
        assert self._rank("calendar:me@gmail.com") < self._rank(
            "calendar:classroom123@group.calendar.google.com"
        )

    def test_sorting_a_realistic_google_account_keeps_the_important_sources(self):
        refs = [
            SyncSourceRef(connection_id=4, source_id=f"calendar:classroom{i}@group.calendar.google.com")
            for i in range(9)
        ]
        refs.append(SyncSourceRef(connection_id=4, source_id="INBOX"))
        refs.append(SyncSourceRef(connection_id=5, source_id="TAPB"))
        refs.append(SyncSourceRef(connection_id=4, source_id="calendar:me@gmail.com"))

        refs.sort(key=lambda ref: chat_sync._by_priority(ref, self.MAILBOX))

        assert [ref.source_id for ref in refs[:3]] == ["INBOX", "TAPB", "calendar:me@gmail.com"]

