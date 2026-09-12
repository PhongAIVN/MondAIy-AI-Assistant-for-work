"""Offline index phải giữ đủ metadata hộp thư để lần đọc lại từ cache lọc
được y hệt lần gọi Gmail API. Thiếu to/cc/subject/mailbox_email thì
filter_classify.py coi mọi mail là "có gửi cho mình" và bỏ luôn vòng lọc
mail-không-mention-mình — lần sync đầu khác hẳn mọi lần rerun."""

from sqlalchemy import select

from src.agents.pipeline.nodes.filter import filter_node
from src.models.message import Message
from tests.test_agents.v1.pipeline.conftest import gmail_item


def _normalized(message_id: str) -> dict:
    item = gmail_item(message_id=message_id, text="Nhờ em gửi báo cáo trước thứ Sáu.", subject="Báo cáo tuần")
    item["mailbox_email"] = "user@example.com"
    item["snippet"] = "Nhờ em gửi báo cáo"
    item["is_unread"] = True
    item["has_marketing_boilerplate"] = False
    return item


def _row(db, external_id: str) -> Message:
    return db.execute(select(Message).where(Message.external_id == external_id)).scalar_one()


def test_offline_index_persists_mailbox_metadata(pipeline_state):
    normalized_item = _normalized("idx-new")
    pipeline_state["normalized"] = [normalized_item]
    pipeline_state["user_id"] = "u-1"

    filter_node(pipeline_state)

    row = _row(pipeline_state["db"], "idx-new")
    assert row.subject == "Báo cáo tuần"
    assert row.to_addresses == ["user@example.com"]
    assert row.mailbox_email == "user@example.com"
    assert row.is_unread is True


def test_offline_index_backfills_rows_ingested_before_the_columns_existed(pipeline_state):
    normalized_item = _normalized("idx-old")
    db = pipeline_state["db"]
    db.add(
        Message(
            user_id="u-1",
            provider="google",
            source_id=normalized_item["source_id"],
            external_id="idx-old",
            text=normalized_item["text"],
            sent_at=normalized_item["sent_at"],
        )
    )
    db.commit()

    pipeline_state["normalized"] = [normalized_item]
    pipeline_state["user_id"] = "u-1"
    filter_node(pipeline_state)

    row = _row(db, "idx-old")
    assert row.to_addresses == ["user@example.com"]
    assert row.mailbox_email == "user@example.com"
    assert row.subject == "Báo cáo tuần"
