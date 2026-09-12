from __future__ import annotations

from sqlalchemy import select

from src.agents.pipeline.state import PipelineState
from src.config import get_settings
from src.models.message import Message
from src.models.pipeline_audit import PipelineFilteredMessage
from src.services.filter_classify import FilterConfig, filter_and_classify


def _backfill_mailbox_columns(row: Message, item: dict) -> None:
    """Cập nhật metadata hộp thư cho hàng đã ingest từ trước. Không ghi đè bằng
    giá trị rỗng — nguồn khác (hoặc lần fetch thiếu header) không được xoá dữ
    liệu tốt đã có."""
    if item.get("subject"):
        row.subject = item["subject"]
    if item.get("snippet"):
        row.snippet = item["snippet"]
    if item.get("to"):
        row.to_addresses = list(item["to"])
    if item.get("cc"):
        row.cc_addresses = list(item["cc"])
    if item.get("mailbox_email"):
        row.mailbox_email = item["mailbox_email"]
    if item.get("thread_id") and not row.thread_id:
        row.thread_id = item["thread_id"]
    row.is_unread = bool(item.get("is_unread", row.is_unread))
    row.has_marketing_boilerplate = bool(item.get("has_marketing_boilerplate", row.has_marketing_boilerplate))


def _persist_offline_index(db, user_id: str, items: list[dict]) -> None:
    """Persist useful normalized mail before task extraction/summary branches.

    Summary runs stop after this node, so indexing here makes the interactive
    Gmail path cache-first even when no proposed task is created.
    """
    for item in items:
        if item.get("provider") != "google":
            continue
        exists = db.execute(
            select(Message).where(
                Message.provider == item["provider"],
                Message.source_id == item["source_id"],
                Message.external_id == str(item["id"]),
            )
        ).scalar_one_or_none()
        if exists is not None:
            # Hàng ingest trước khi có các cột metadata hộp thư sẽ mãi mãi rỗng
            # nếu chỉ "đã tồn tại thì bỏ qua" — mà đường đọc-từ-cache lại ưu
            # tiên đúng những hàng cũ đó, nên rerun không bao giờ tự khoẻ lên.
            # Backfill tại chỗ, chỉ ghi khi giá trị mới thật sự có nội dung.
            _backfill_mailbox_columns(exists, item)
            continue
        db.add(
            Message(
                user_id=str(user_id),
                connection_id=item.get("connection_id"),
                provider=item["provider"],
                source_id=item["source_id"],
                external_id=str(item["id"]),
                thread_id=item.get("thread_id"),
                author_id=item.get("author_id"),
                author_name=item.get("author_name"),
                is_self=item.get("is_self", False),
                is_dm=item.get("is_dm", False),
                # Giữ đủ metadata hộp thư để lần đọc lại từ cache lọc được y
                # hệt lần gọi Gmail API — thiếu to/cc/subject thì
                # filter_classify.py không thấy người nhận và mặc định coi
                # mọi mail là "có gửi cho mình".
                subject=item.get("subject", "") or "",
                snippet=item.get("snippet", "") or "",
                to_addresses=item.get("to") or [],
                cc_addresses=item.get("cc") or [],
                mailbox_email=item.get("mailbox_email"),
                is_unread=bool(item.get("is_unread", False)),
                has_marketing_boilerplate=bool(item.get("has_marketing_boilerplate", False)),
                text=item.get("text", ""),
                sent_at=item["sent_at"],
                deep_link=item.get("deep_link"),
            )
        )


def filter_node(state: PipelineState) -> dict:
    """Deterministic scope/filter/score stage; no LLM call. Ghi audit CP0
    song song — mỗi item lọt qua 1 dòng PipelineFilteredMessage."""
    db = state["db"]
    run_id = state["run_id"]

    # Cửa sổ lọc phải bám theo cửa sổ THẬT của lần chạy, không dùng mặc định 14
    # ngày của FilterConfig. Connector đã fetch trong một khoảng có chủ đích rồi;
    # cắt lại lần nữa ở đây chỉ làm hai tầng chống nhau — và đã chống thật: sàn
    # lookback 30 ngày dành riêng cho Jira bị mặc định 14 ngày huỷ sạch, issue
    # lấy về rồi vẫn bị loại là "outside_lookback".
    settings = get_settings()
    time_from = state.get("time_from")
    time_to = state.get("time_to")
    window_days = (time_to - time_from).days + 1 if time_from and time_to else settings.chat_sync_range_hours // 24
    config = FilterConfig(
        user_email=state.get("user_email"),
        trusted_senders=frozenset(state.get("trusted_senders", [])),
        trusted_sender_domains=frozenset(state.get("trusted_sender_domains", [])),
        program_domains=frozenset(state.get("program_domains", [])),
        lookback_days=max(window_days, settings.jira_min_lookback_days),
    )
    result = filter_and_classify(state.get("normalized", []), config)

    filtered: list[dict] = []
    for item in result["items"]:
        row = PipelineFilteredMessage(
            run_id=run_id,
            normalized_message_id=item.get("_pipeline_normalized_message_id"),
            score=item.get("importance_score", 0),
        )
        db.add(row)
        db.flush()
        item["_pipeline_filtered_message_id"] = row.id
        filtered.append(item)

    # Một số đường test/legacy chỉ chạy deterministic filter mà không có user.
    # Offline index là side effect bổ sung, không được làm hỏng kết quả lọc cốt
    # lõi; chỉ persist khi pipeline thật cung cấp danh tính chủ sở hữu.
    user_id = state.get("user_id")
    if user_id is not None:
        _persist_offline_index(db, user_id, filtered)
    db.commit()
    return {"filtered": filtered, "filter_rejected": result["rejected"], "filter_stats": result}
