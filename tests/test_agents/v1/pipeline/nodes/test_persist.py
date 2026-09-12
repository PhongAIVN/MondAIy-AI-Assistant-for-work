from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from src.agents.pipeline.nodes.persist import persist_node
from src.models.cluster import ClusterMessage
from src.models.message import Message
from src.models.reminder import Reminder
from src.models.task import Task
from src.models.task_evidence import TaskEvidence


def test_persist_creates_task_and_evidence(pipeline_state):
    item = {
        "message": {
            "id": "m1",
            "provider": "google",
            "source_id": "INBOX",
            "text": "submit report",
            "sent_at": datetime(2026, 8, 8, tzinfo=UTC),
            "deep_link": "https://mail.google.com/mail/u/0/#inbox/m1",
        },
        "evidence_quote": "submit report",
    }
    pipeline_state["clusters"] = [
        {
            "cluster_key": "c1",
            "title": "Submit report",
            "due_at": None,
            "ambiguous": False,
            "assignee": None,
            "assignee_ambiguous": True,
            "source_count": 1,
            "signal_strength": 0.33,
            "items": [item],
        }
    ]

    result = persist_node(pipeline_state)

    assert len(result["tasks_persisted"]) == 1
    task = pipeline_state["db"].get(Task, result["tasks_persisted"][0]["task_id"])
    assert task is not None
    # Nguồn LLM (Gmail) — chưa có rule engine, không suy diễn giá trị giả.
    assert task.decision is None
    # Chính sách tin cậy 2026-08-25: 1 nguồn, không rule -> chưa chắc chắn,
    # task ở proposed đợi người dùng duyệt thay vì tự xác nhận.
    assert task.status == "proposed"
    assert task.reasons == []
    assert task.rule_version is None
    assert task.all_day is False


def test_persist_auto_confirms_only_confident_clusters(pipeline_state):
    """Chính sách 2026-08-25: tự xác nhận CHỈ khi chắc chắn — từ 2 nguồn trở
    lên hoặc rule-based khớp, và giờ hết rõ ràng. Cụm yếu thì proposed."""

    def cluster(key: str, source_count: int, *, ambiguous: bool = False, decision=None) -> dict:
        return {
            "cluster_key": key,
            "title": f"Việc {key}",
            "due_at": None,
            "ambiguous": ambiguous,
            "assignee": None,
            "assignee_ambiguous": True,
            "source_count": source_count,
            "signal_strength": min(1.0, source_count / 3),
            "decision": decision,
            "reasons": [],
            "items": [],
        }

    pipeline_state["clusters"] = [
        cluster("multi-1", 2),
        cluster("rule-1", 1, decision="jira_rule"),
        cluster("amb-1", 2, ambiguous=True),
        cluster("weak-1", 1),
    ]

    result = persist_node(pipeline_state)
    status_by_key = {}
    for persisted in result["tasks_persisted"]:
        row = pipeline_state["db"].get(Task, persisted["task_id"])
        status_by_key[row.cluster_key] = row.status

    assert status_by_key["multi-1"] == "confirmed"
    assert status_by_key["rule-1"] == "confirmed"
    # Giờ mơ hồ thì không tự xác nhận kể cả khi nhiều nguồn cùng xác nhận.
    assert status_by_key["amb-1"] == "proposed"
    assert status_by_key["weak-1"] == "proposed"


def test_persist_marks_evidence_has_attachment_when_message_has_attachments(pipeline_state):
    item = {
        "message": {
            "id": "m-att-1",
            "provider": "google",
            "source_id": "INBOX",
            "text": "Xem file đính kèm.",
            "sent_at": datetime(2026, 8, 8, tzinfo=UTC),
            "deep_link": "https://mail.google.com/mail/u/0/#inbox/m-att-1",
            "attachments": [{"filename": "bao-cao.pdf", "mimeType": "application/pdf", "sizeBytes": 100}],
        },
        "evidence_quote": "Xem file đính kèm.",
    }
    pipeline_state["clusters"] = [
        {
            "cluster_key": "c-att",
            "title": "Xem file đính kèm",
            "due_at": None,
            "ambiguous": False,
            "assignee": None,
            "assignee_ambiguous": True,
            "source_count": 1,
            "signal_strength": 0.33,
            "items": [item],
        }
    ]

    result = persist_node(pipeline_state)
    task_id = result["tasks_persisted"][0]["task_id"]

    evidence = pipeline_state["db"].execute(select(TaskEvidence).where(TaskEvidence.task_id == task_id)).scalars().all()
    assert len(evidence) == 1
    assert evidence[0].has_attachment is True


def test_persist_leaves_evidence_has_attachment_false_when_no_attachments(pipeline_state):
    pipeline_state["clusters"] = [_basic_cluster("c-no-att", "m-no-att")]

    result = persist_node(pipeline_state)
    task_id = result["tasks_persisted"][0]["task_id"]

    evidence = pipeline_state["db"].execute(select(TaskEvidence).where(TaskEvidence.task_id == task_id)).scalars().all()
    assert len(evidence) == 1
    assert evidence[0].has_attachment is False


def test_persist_stores_decision_reasons_rule_version_and_all_day_for_jira(pipeline_state):
    due = datetime(2026, 8, 15, tzinfo=UTC)
    item = {
        "message": {
            "id": "TO04-42",
            "provider": "jira",
            "source_id": "TO04",
            "text": "Đội cần nộp trước thứ Sáu.",
            "sent_at": datetime(2026, 8, 10, tzinfo=UTC),
            "deep_link": "https://vinait004.atlassian.net/browse/TO04-42",
        },
        "evidence_quote": "Đội cần nộp trước thứ Sáu.",
        "all_day": True,
    }
    pipeline_state["clusters"] = [
        {
            "cluster_key": "c-jira",
            "title": "Hoàn thành báo cáo tuần 3",
            "due_at": due,
            "all_day": True,
            "ambiguous": False,
            "assignee": "acc-phong-01",
            "assignee_ambiguous": False,
            "source_count": 1,
            "signal_strength": 0.33,
            "decision": "KEEP",
            "reasons": ["HAS_ACTION", "HAS_DEADLINE"],
            "rule_version": "jira-rules-v1",
            "items": [item],
        }
    ]

    result = persist_node(pipeline_state)

    task = pipeline_state["db"].get(Task, result["tasks_persisted"][0]["task_id"])
    assert task.decision == "KEEP"
    # Reason auto_confirmed gộp cùng reasons của rule engine, sort chung.
    assert task.reasons == ["HAS_ACTION", "HAS_DEADLINE", "auto_confirmed"]
    assert task.rule_version == "jira-rules-v1"
    assert task.all_day is True


def _basic_cluster(cluster_key: str, message_id: str) -> dict:
    return {
        "cluster_key": cluster_key,
        "title": "Submit report",
        "due_at": None,
        "ambiguous": False,
        "assignee": None,
        "assignee_ambiguous": True,
        "source_count": 1,
        "signal_strength": 0.33,
        "items": [
            {
                "message": {
                    "id": message_id,
                    "provider": "google",
                    "source_id": "INBOX",
                    "text": "submit report",
                    "sent_at": datetime(2026, 8, 8, tzinfo=UTC),
                    "deep_link": f"https://mail.google.com/mail/u/0/#inbox/{message_id}",
                },
                "evidence_quote": "submit report",
            }
        ],
    }


def test_persist_creates_task_proposed_notice_for_new_task(pipeline_state):
    pipeline_state["clusters"] = [_basic_cluster("c-notice-1", "m-notice-1")]

    result = persist_node(pipeline_state)
    task_id = result["tasks_persisted"][0]["task_id"]

    db = pipeline_state["db"]
    reminders = db.execute(select(Reminder).where(Reminder.task_id == task_id, Reminder.kind == "task_proposed")).scalars().all()
    assert len(reminders) == 1
    assert reminders[0].status == "scheduled"


def test_persist_does_not_duplicate_task_proposed_notice_on_resync(pipeline_state):
    pipeline_state["clusters"] = [_basic_cluster("c-notice-2", "m-notice-2")]
    first = persist_node(pipeline_state)
    task_id = first["tasks_persisted"][0]["task_id"]

    # Resync cùng cluster_key — upsert task đã tồn tại, không phải task mới.
    pipeline_state["clusters"] = [_basic_cluster("c-notice-2", "m-notice-2")]
    persist_node(pipeline_state)

    db = pipeline_state["db"]
    reminders = db.execute(select(Reminder).where(Reminder.task_id == task_id, Reminder.kind == "task_proposed")).scalars().all()
    assert len(reminders) == 1


def test_persist_reopens_completed_task_when_new_reply_arrives_on_same_cluster(pipeline_state):
    # Yêu cầu người dùng 2026-08-20: task đã hoàn thành mà thread đó lại có
    # reply mới (cùng cluster_key, message id chưa từng thấy) -> việc chưa
    # thật sự xong, phải mở lại, không lặng lẽ bỏ qua. Theo chính sách tự xác
    # nhận 2026-08-22, mở lại là agent tự xác nhận lại luôn.
    pipeline_state["clusters"] = [_basic_cluster("c-reopen", "m-reopen-1")]
    first = persist_node(pipeline_state)
    task_id = first["tasks_persisted"][0]["task_id"]

    db = pipeline_state["db"]
    task = db.get(Task, task_id)
    task.status = "completed"
    db.commit()

    reply_cluster = _basic_cluster("c-reopen", "m-reopen-1")
    reply_cluster["items"].append(
        {
            "message": {
                "id": "m-reopen-2",
                "provider": "google",
                "source_id": "INBOX",
                "text": "Re: submit report — vẫn còn thiếu 1 mục",
                "sent_at": datetime(2026, 8, 12, tzinfo=UTC),
                "deep_link": "https://mail.google.com/mail/u/0/#inbox/m-reopen-2",
            },
            "evidence_quote": "vẫn còn thiếu 1 mục",
        }
    )
    pipeline_state["clusters"] = [reply_cluster]
    persist_node(pipeline_state)

    db.expire_all()
    task = db.get(Task, task_id)
    assert task.status == "confirmed"
    assert "reopened_by_new_reply" in task.reasons
    assert "auto_confirmed" in task.reasons

    # Evidence cho message mới (reply) phải được ghi thêm, không chỉ giữ 1
    # dòng của message gốc lúc task tạo lần đầu.
    evidence = db.execute(select(TaskEvidence).where(TaskEvidence.task_id == task_id)).scalars().all()
    assert len(evidence) == 2

    reminders = db.execute(select(Reminder).where(Reminder.task_id == task_id, Reminder.kind == "task_proposed")).scalars().all()
    assert len(reminders) == 1


def test_persist_does_not_reopen_active_task_when_message_resynced_unchanged(pipeline_state):
    # Resync mail y hệt (không có message mới) không được đụng tới status —
    # kể cả khi status đang ở trạng thái reopenable, không có gì mới thì
    # không có gì để mở lại.
    pipeline_state["clusters"] = [_basic_cluster("c-static", "m-static-1")]
    first = persist_node(pipeline_state)
    task_id = first["tasks_persisted"][0]["task_id"]

    db = pipeline_state["db"]
    task = db.get(Task, task_id)
    task.status = "dismissed"
    db.commit()

    pipeline_state["clusters"] = [_basic_cluster("c-static", "m-static-1")]
    persist_node(pipeline_state)

    db.expire_all()
    task = db.get(Task, task_id)
    assert task.status == "dismissed"


def test_persist_dedupes_same_message_appearing_twice_in_one_cluster(pipeline_state):
    """Regression: 2 item cung message_id trong 1 cluster (vd overlap fetch/
    resync) truoc day gay UniqueViolation tren cluster_messages_pkey vi
    session prod dung autoflush=False - SELECT dedupe trong vong lap khong
    thay row vua add() nhung chua flush."""
    db = pipeline_state["db"]
    db.autoflush = False  # khop SessionLocal that (src/db.py)

    message = {
        "id": "m-dup-1",
        "provider": "google",
        "source_id": "INBOX",
        "text": "submit report",
        "sent_at": datetime(2026, 8, 8, tzinfo=UTC),
        "deep_link": "https://mail.google.com/mail/u/0/#inbox/m-dup-1",
    }
    duplicated_item = {"message": message, "evidence_quote": "submit report"}
    pipeline_state["clusters"] = [
        {
            "cluster_key": "c-dup",
            "title": "Submit report",
            "due_at": None,
            "ambiguous": False,
            "assignee": None,
            "assignee_ambiguous": True,
            "source_count": 1,
            "signal_strength": 0.33,
            "items": [duplicated_item, dict(duplicated_item)],
        }
    ]

    result = persist_node(pipeline_state)  # truoc day raise IntegrityError o day
    task_id = result["tasks_persisted"][0]["task_id"]

    message_row = db.execute(select(Message).where(Message.external_id == "m-dup-1")).scalar_one()
    links = db.execute(select(ClusterMessage).where(ClusterMessage.message_id == message_row.id)).all()
    assert len(links) == 1

    evidence = db.execute(select(TaskEvidence).where(TaskEvidence.task_id == task_id)).scalars().all()
    assert len(evidence) == 1


_OTP_TEXT = "Mã OTP có hiệu lực trong vòng 5 phút. Quý khách tuyệt đối không cung cấp mã OTP này cho bất kỳ ai."
_WORK_TEXT = "Nhờ em sửa lại báo cáo và nộp trước thứ Sáu tuần này."


def _cluster(
    cluster_key: str,
    message_id: str,
    title: str,
    text: str = _OTP_TEXT,
    due_at: datetime | None = None,
) -> dict:
    return {
        "cluster_key": cluster_key,
        "title": title,
        "due_at": due_at,
        "ambiguous": False,
        "assignee": None,
        "assignee_ambiguous": True,
        "source_count": 1,
        "signal_strength": 0.33,
        "items": [
            {
                "message": {
                    "id": message_id,
                    "provider": "google",
                    "source_id": "INBOX",
                    "author_id": "mbcard@mbbank.com.vn",
                    "text": text,
                    "sent_at": datetime(2026, 8, 8, tzinfo=UTC),
                    "deep_link": f"https://mail.google.com/mail/u/0/#inbox/{message_id}",
                },
                "evidence_quote": text[:40],
            }
        ],
    }


def test_persist_retracts_auto_confirmed_task_whose_sources_are_obvious_noise(pipeline_state):
    """Siết bộ lọc xong thì mail OTP/biên lai không còn vào `filtered`, cụm
    tương ứng không được dựng lại — task rác tạo từ lần chạy CŨ trước đây nằm
    lại trong hộp vĩnh viễn vì pipeline chỉ biết thêm/cập nhật, không rút.
    Chính sách 2026-08-25: cụm 1 nguồn sinh ra là proposed, và proposed dựng
    trên nguồn toàn rác cũng phải bị thu hồi thay vì treo trong hộp duyệt."""
    db = pipeline_state["db"]
    pipeline_state["clusters"] = [_cluster("junk-1", "otp-1", "Cảnh báo về mã OTP")]
    created = persist_node(pipeline_state)
    task_id = created["tasks_persisted"][0]["task_id"]
    assert db.get(Task, task_id).status == "proposed"

    pipeline_state["clusters"] = []
    result = persist_node(pipeline_state)

    assert result["tasks_retracted"] == [task_id]
    task = db.get(Task, task_id)
    assert task.status == "dismissed"
    assert "retracted_by_filter" in task.reasons


def test_persist_retracts_even_when_the_mail_was_not_fetched_in_this_run(pipeline_state):
    """Connector chỉ soi _MAX_METADATA_CANDIDATES mail mới nhất mỗi nguồn, nên
    mail cũ không hề xuất hiện trong lần chạy. Thu hồi phải chấm lại bằng
    chứng ĐÃ LƯU của task, không dựa vào filter_rejected của lần chạy này —
    nếu không, task OTP cũ sống sót qua mọi lần resync (bug thật)."""
    db = pipeline_state["db"]
    pipeline_state["clusters"] = [_cluster("junk-cap", "otp-cap", "Cảnh báo về mã OTP")]
    task_id = persist_node(pipeline_state)["tasks_persisted"][0]["task_id"]

    # Lần chạy sau không thấy mail đó ở đâu cả: không keep, cũng không reject.
    pipeline_state["clusters"] = []
    pipeline_state["filter_rejected"] = []
    result = persist_node(pipeline_state)

    assert result["tasks_retracted"] == [task_id]
    assert db.get(Task, task_id).status == "dismissed"


def test_persist_never_retracts_a_task_the_user_already_confirmed(pipeline_state):
    """Task user TỰ DUYỆT tay (không mang reason auto_confirmed) là quyết định
    của họ — kể cả khi toàn bộ nguồn sau này thành rác, pipeline không lật."""
    db = pipeline_state["db"]
    pipeline_state["clusters"] = [_cluster("junk-2", "otp-2", "Cảnh báo về mã OTP")]
    task_id = persist_node(pipeline_state)["tasks_persisted"][0]["task_id"]
    # Mô phỏng luồng duyệt tay cũ: proposed -> confirmed không có dấu vết
    # auto_confirmed, khác với task pipeline tự xác nhận ngay lúc tạo.
    manual = db.get(Task, task_id)
    manual.status = "confirmed"
    manual.reasons = []
    db.commit()

    pipeline_state["clusters"] = []
    result = persist_node(pipeline_state)

    assert result["tasks_retracted"] == []
    assert db.get(Task, task_id).status == "confirmed"


def test_persist_retract_cancels_pending_due_reminders_of_auto_confirmed_task(pipeline_state):
    """Regression (Antigravity 2026-08-22): task tự xác nhận có hạn sinh mốc
    nhắc task_due ngay lúc tạo; khi bộ lọc thu hồi task rác, mốc nhắc còn
    `scheduled` phải bị tắt theo — không thì rác vẫn nhắc đúng hẹn dù task đã
    dismissed."""
    due = datetime.now(UTC) + timedelta(days=3)
    db = pipeline_state["db"]
    junk = _cluster("junk-due", "otp-due", "Cảnh báo về mã OTP", due_at=due)
    # Chính sách 2026-08-25: mốc nhắc chỉ sinh cho task TỰ XÁC NHẬN khi đủ
    # tin cậy (2 nguồn) — proposed không sinh nhắc (FR-062/FR-090).
    junk["source_count"] = 2
    junk["signal_strength"] = 0.67
    pipeline_state["clusters"] = [junk]
    task_id = persist_node(pipeline_state)["tasks_persisted"][0]["task_id"]

    scheduled = db.execute(
        select(Reminder).where(
            Reminder.task_id == task_id,
            Reminder.kind == "task_due",
            Reminder.status == "scheduled",
        )
    ).scalars().all()
    assert scheduled, "task có hạn phải sinh mốc nhắc lúc tự xác nhận"

    pipeline_state["clusters"] = []
    result = persist_node(pipeline_state)

    assert result["tasks_retracted"] == [task_id]
    db.expire_all()
    leftovers = db.execute(
        select(Reminder).where(
            Reminder.task_id == task_id,
            Reminder.kind == "task_due",
            Reminder.status == "scheduled",
        )
    ).scalars().all()
    assert leftovers == []


def test_persist_keeps_task_when_one_source_is_still_real_work(pipeline_state):
    """Chỉ thu hồi khi TOÀN BỘ nguồn là rác rõ ràng — 1 mail công việc thật
    trong cụm là đủ để giữ task lại."""
    db = pipeline_state["db"]
    cluster = _cluster("mixed-1", "otp-3", "Cảnh báo về mã OTP")
    work_item = _cluster("ignored", "work-3", "Nộp báo cáo", text=_WORK_TEXT)["items"][0]
    work_item["message"]["author_id"] = "mentor@school.edu"
    cluster["items"] = [cluster["items"][0], work_item]
    pipeline_state["clusters"] = [cluster]
    task_id = persist_node(pipeline_state)["tasks_persisted"][0]["task_id"]

    pipeline_state["clusters"] = []
    result = persist_node(pipeline_state)

    assert result["tasks_retracted"] == []
    # 1 nguồn -> proposed theo chính sách tin cậy 2026-08-25; quan trọng là
    # KHÔNG bị thu hồi vì còn một bằng chứng công việc thật.
    assert db.get(Task, task_id).status == "proposed"


def test_persist_promotes_proposed_task_when_resync_bring_confidence(pipeline_state):
    """Chính sách 2026-08-25: cụm yếu sinh proposed; resync mang thêm bằng
    chứng (nguồn thứ hai) đủ ngưỡng thì tự nâng confirmed kèm mốc nhắc như
    confirm thủ công. Task user đã chạm (dismissed) không bị lật lại."""
    db = pipeline_state["db"]
    weak = _cluster("promo-1", "promo-msg", "Nộp báo cáo tuần này")
    pipeline_state["clusters"] = [weak]
    task_id = persist_node(pipeline_state)["tasks_persisted"][0]["task_id"]
    assert db.get(Task, task_id).status == "proposed"

    weak["source_count"] = 2
    weak["signal_strength"] = 0.67
    persist_node(pipeline_state)

    promoted = db.get(Task, task_id)
    assert promoted.status == "confirmed"
    assert "auto_confirmed" in (promoted.reasons or [])

    # User từ chối sau đó -> resync tiếp không resurrect.
    promoted.status = "dismissed"
    db.commit()
    persist_node(pipeline_state)
    assert db.get(Task, task_id).status == "dismissed"
