from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from src.agents.pipeline.state import PipelineState
from src.models.cluster import Cluster, ClusterMessage
from src.models.message import Message
from src.models.reminder import Reminder
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.services import schedule_conflicts as schedule_conflicts_service
from src.services.filter_classify import FilterConfig, triage_email
from src.services.reminders import (
    cancel_pending_reminders,
    detect_schedule_conflicts,
    generate_default_reminders,
    generate_proposed_notice,
)

# Task đã ở 1 trong 3 trạng thái này coi như "đã xong việc" — 1 reply mới
# trên đúng thread đã duyệt/hoàn thành nghĩa là việc chưa thật sự xong, phải
# mở lại (yêu cầu người dùng 2026-08-20), không được lặng lẽ bỏ qua hay tạo
# task trùng bên cạnh task cũ.
_REOPENABLE_STATUSES = {"completed", "dismissed", "cancelled"}

# Quyết định của chủ sản phẩm 2026-08-22: task agent tự gom từ cụm email được
# agent TỰ XÁC NHẬN luôn (không bắt user bấm duyệt). Reason này là dấu vết để
# phân biệt với task user đã tự confirm tay — nơi khác (retract, thông báo)
# dựa vào nó mà hành xử, không được xoá khỏi reasons khi cập nhật task.
AUTO_CONFIRMED_REASON = "auto_confirmed"


def _get_or_create_message(db, user_id: str, message_dict: dict) -> tuple[Message, bool]:
    row = db.execute(
        select(Message).where(
            Message.provider == message_dict["provider"],
            Message.source_id == message_dict["source_id"],
            Message.external_id == message_dict["id"],
        )
    ).scalar_one_or_none()
    if row is not None:
        return row, False

    row = Message(
        user_id=user_id,
        connection_id=message_dict.get("connection_id"),
        provider=message_dict["provider"],
        source_id=message_dict["source_id"],
        external_id=message_dict["id"],
        thread_id=message_dict.get("thread_id"),
        author_id=message_dict.get("author_id"),
        author_name=message_dict.get("author_name"),
        is_self=message_dict.get("is_self", False),
        is_dm=message_dict.get("is_dm", False),
        # Cùng bộ metadata hộp thư như _persist_offline_index (filter.py) —
        # đây là nơi ghi Message THỨ HAI, bỏ sót thì nguồn nào không đi qua
        # filter_node lại sinh ra hàng cache rỗng y như bug cũ.
        subject=message_dict.get("subject", "") or "",
        snippet=message_dict.get("snippet", "") or "",
        to_addresses=message_dict.get("to") or [],
        cc_addresses=message_dict.get("cc") or [],
        mailbox_email=message_dict.get("mailbox_email"),
        is_unread=bool(message_dict.get("is_unread", False)),
        has_marketing_boilerplate=bool(message_dict.get("has_marketing_boilerplate", False)),
        text=message_dict["text"],
        sent_at=message_dict["sent_at"],
        deep_link=message_dict["deep_link"],
    )
    db.add(row)
    db.flush()
    return row, True


def _item_from_message(row: Message) -> dict:
    """Dựng lại item chuẩn hoá từ hàng Message đã lưu, đủ để chấm lại bằng bộ
    lọc tất định. Hàng cũ có thể thiếu to/cc/subject (ingest trước khi có các
    cột đó): thiếu người nhận thì filter tự coi là "có gửi cho mình", tức là
    nghiêng về GIỮ — an toàn đúng hướng cho một thao tác thu hồi."""
    return {
        "id": row.external_id,
        "provider": row.provider,
        "source_id": row.source_id,
        "author_id": row.author_id,
        "author_name": row.author_name,
        "subject": row.subject or "",
        "text": row.text or "",
        "normalized_text": row.text or "",
        "to": list(row.to_addresses or []),
        "cc": list(row.cc_addresses or []),
        "mailbox_email": row.mailbox_email,
        "is_unread": bool(row.is_unread),
        "has_marketing_boilerplate": bool(row.has_marketing_boilerplate),
        "sent_at": row.sent_at,
    }


def _is_obvious_noise(row: Message, config: FilterConfig) -> bool:
    """Chỉ đúng khi bộ lọc kết luận rác RÕ RÀNG (negative_state/stale_thread/
    not_addressed -> "obvious_drop"), không tính "low_importance".

    Điểm số có thể thấp đi chỉ vì hàng cũ thiếu metadata (mất 20 điểm
    recipient), nên lấy điểm làm căn cứ xoá là sai. Giọng văn OTP/biên lai/
    digest thì không phụ thuộc metadata."""
    decision = triage_email(_item_from_message(row), config)
    return decision.decision == "drop" and decision.reason == "obvious_drop"


def _retract_noise_tasks(db, user_id: str, state: PipelineState) -> list[int]:
    """Chuyển về "dismissed" các task ĐANG CHỜ DUYỆT mà mọi mail nguồn của nó
    đều là rác theo bộ lọc hiện tại.

    Trước đây pipeline chỉ biết thêm và cập nhật, không biết rút: siết bộ lọc
    xong thì mail OTP/biên lai không còn vào `filtered`, cụm tương ứng không
    được dựng lại, nên task rác tạo từ lần chạy CŨ nằm lại trong hộp vĩnh
    viễn.

    Chấm lại bằng chứng ĐÃ LƯU của chính task chứ không dựa vào
    `filter_rejected` của lần chạy này: connector chỉ soi
    `_MAX_METADATA_CANDIDATES` mail mới nhất mỗi nguồn, nên mail cũ hơn không
    hề xuất hiện trong lần chạy — không có mặt trong danh sách bị loại thì
    không bao giờ được dọn (bug thật: task OTP ngày 08-15 sống sót qua mọi
    lần resync). Bộ lọc là tất định, không gọi LLM, nên chấm lại rất rẻ.

    Bốn ràng buộc để không xoá nhầm:
      - Chỉ đụng status "proposed" hoặc "confirmed" CÓ reason
        auto_confirmed. Task user tự duyệt tay (không có reason đó) là quyết
        định của họ, pipeline không được lật lại.
      - Chỉ thu hồi khi TOÀN BỘ message của cụm đều là rác rõ ràng.
      - Đặt "dismissed" chứ không xoá: đúng trạng thái nút "Bỏ qua", và
        _REOPENABLE_STATUSES vẫn cho mở lại nếu sau này có reply mới thật sự.
      - Thu hồi xong phải tắt cả mốc nhắc còn treo: task tự xác nhận đã sinh
        task_due ngay lúc tạo, bỏ sót là rác vẫn nhắc đúng hẹn dù task đã
        bị thu hồi.
    """
    config = FilterConfig(
        user_email=state.get("user_email"),
        trusted_senders=frozenset(state.get("trusted_senders", [])),
        trusted_sender_domains=frozenset(state.get("trusted_sender_domains", [])),
        program_domains=frozenset(state.get("program_domains", [])),
    )

    # Cụm do CHÍNH lần chạy này dựng ra là phán quyết mới nhất và đầy đủ nhất
    # (mail vừa qua trọn vẹn vòng lọc với header thật). Chấm lại nó bằng bản
    # cache thiếu metadata rồi tự lật ngược là vô lý.
    fresh_cluster_keys = {cluster["cluster_key"] for cluster in state.get("clusters", [])}

    stmt = (
        select(Task.id, ClusterMessage.message_id)
        .join(Cluster, Cluster.task_id == Task.id)
        .join(ClusterMessage, ClusterMessage.cluster_id == Cluster.id)
        .where(Task.user_id == user_id, Task.status.in_(["proposed", "confirmed"]))
    )
    if fresh_cluster_keys:
        stmt = stmt.where(Task.cluster_key.notin_(fresh_cluster_keys))

    linked: dict[int, set[int]] = {}
    rows = db.execute(stmt).all()
    for task_id, message_id in rows:
        linked.setdefault(task_id, set()).add(message_id)
    if not linked:
        return []

    # 1 message dùng chung cho nhiều task -> chấm 1 lần, dùng lại.
    noise_cache: dict[int, bool] = {}

    def _noise(message_id: int) -> bool:
        if message_id not in noise_cache:
            row = db.get(Message, message_id)
            noise_cache[message_id] = bool(row is not None and _is_obvious_noise(row, config))
        return noise_cache[message_id]

    retracted: list[int] = []
    for task_id, message_ids in linked.items():
        if not message_ids or not all(_noise(message_id) for message_id in message_ids):
            continue
        task_row = db.get(Task, task_id)
        if task_row is None:
            continue
        if task_row.status == "confirmed":
            # Task user tự duyệt tay không có dấu vết auto_confirmed — giữ nguyên.
            if AUTO_CONFIRMED_REASON not in (task_row.reasons or []):
                continue
        elif task_row.status != "proposed":
            continue
        task_row.status = "dismissed"
        task_row.reasons = sorted({*(task_row.reasons or []), "retracted_by_filter"})
        task_row.updated_at = datetime.now(UTC)
        stale_notice = db.execute(
            select(Reminder).where(Reminder.task_id == task_row.id, Reminder.kind == "task_proposed")
        ).scalar_one_or_none()
        if stale_notice is not None:
            db.delete(stale_notice)
        cancel_pending_reminders(db, task_row.id)
        retracted.append(task_id)

    if retracted:
        db.flush()
    return retracted


def _is_confident_cluster(cluster_data: dict) -> bool:
    """Ngưỡng tự xác nhận theo độ tin cậy (yêu cầu Thái 2026-08-25).

    AI phải CHẮC CHẮN mới đưa thẳng việc vào danh sách: giờ hết rõ ràng và
    đủ một trong hai bằng chứng mạnh — được từ hai nguồn trở lên cùng xác nhận,
    hoặc rule-based khớp (decision). Còn lại proposed đợi người dùng duyệt.
    """
    if cluster_data.get("ambiguous"):
        return False
    if cluster_data.get("decision") is not None:
        return True
    return cluster_data.get("source_count", 0) >= 2


def persist_node(state: PipelineState) -> dict:
    """Upsert Cluster -> Task -> ClusterMessage -> TaskEvidence, keyed theo
    cluster_key — idempotent, resync không tạo task trùng (FR-012/013)."""
    db = state["db"]
    user_id = state["user_id"]
    tasks_persisted: list[dict] = []

    for cluster_data in state.get("clusters", []):
        cluster_key = cluster_data["cluster_key"]

        cluster_row = db.execute(
            select(Cluster).where(Cluster.user_id == user_id, Cluster.cluster_key == cluster_key)
        ).scalar_one_or_none()
        if cluster_row is None:
            cluster_row = Cluster(user_id=user_id, cluster_key=cluster_key)
            db.add(cluster_row)
        cluster_row.signal_strength = cluster_data["signal_strength"]
        cluster_row.due_at = cluster_data["due_at"]
        cluster_row.ambiguous = cluster_data["ambiguous"]

        task_row = db.execute(
            select(Task).where(Task.user_id == user_id, Task.cluster_key == cluster_key)
        ).scalar_one_or_none()
        is_new_task = task_row is None
        confident = _is_confident_cluster(cluster_data)
        promoted = False
        if task_row is None:
            # Tự xác nhận CHỈ khi bằng chứng đủ mạnh (xem _is_confident_cluster);
            # việc yếu hơn ở trạng thái proposed đợi người dùng duyệt.
            task_row = Task(
                user_id=user_id,
                cluster_key=cluster_key,
                status="confirmed" if confident else "proposed",
            )
            db.add(task_row)
        elif task_row.status == "proposed" and confident:
            # Resync mang thêm bằng chứng (nguồn thứ hai, rule khớp) — đủ tin
            # cậy lúc này nên tự nâng lên confirmed. Task user đã tự chạm
            # (dismissed/cancelled/completed/confirmed) không bị đụng tới.
            task_row.status = "confirmed"
            promoted = True
        task_row.title = cluster_data["title"]
        task_row.detail = cluster_data.get("detail", "")
        task_row.due_at = cluster_data["due_at"]
        task_row.all_day = cluster_data.get("all_day", False)
        task_row.ambiguous = cluster_data["ambiguous"]
        task_row.assignee = cluster_data.get("assignee")
        task_row.assignee_ambiguous = cluster_data.get("assignee_ambiguous", True)
        task_row.source_count = cluster_data["source_count"]
        task_row.signal_strength = cluster_data["signal_strength"]
        # Explainability rule-based (Jira) — None/[] cho task từ nguồn còn
        # dùng LLM (Gmail), không suy diễn giá trị giả. Reason auto_confirmed
        # phải sống sót qua mọi lần resync nên gộp chứ không ghi đè reasons.
        decision = cluster_data.get("decision")
        task_row.decision = decision
        cluster_reasons = cluster_data.get("reasons") or []
        if is_new_task:
            new_reasons = {AUTO_CONFIRMED_REASON, *cluster_reasons} if confident else set(cluster_reasons)
            task_row.reasons = sorted(new_reasons)
        else:
            promoted_reasons = {AUTO_CONFIRMED_REASON, *cluster_reasons} if promoted else set(cluster_reasons)
            task_row.reasons = sorted(promoted_reasons | set(task_row.reasons or []))
        task_row.rule_version = cluster_data.get("rule_version")
        task_row.updated_at = datetime.now(UTC)

        db.flush()
        cluster_row.task_id = task_row.id
        if is_new_task:
            # Task mới thật sự (không phải resync) -> 1 thông báo để pipe
            # delivery đưa ra Telegram/web kèm danh sách việc vừa được gom.
            generate_proposed_notice(db, task_row)
        if task_row.status == "confirmed" and (is_new_task or promoted):
            # Đủ side effect như khi user bấm Confirm thủ công (api/tasks.py):
            # mốc nhắc mặc định cho task có hạn + phát hiện trùng giờ nội bộ
            # và trùng với lịch Google cache. Lịch chỉ bị GHI khi user bấm
            # Sync tường minh — tự xác nhận không bao giờ đụng app ngoài.
            # Task proposed KHÔNG sinh nhắc (FR-062/FR-090: nhắc chỉ có sau
            # khi người dùng xác nhận ở endpoint /confirm).
            generate_default_reminders(db, task_row)
            detect_schedule_conflicts(db, task_row)
            schedule_conflicts_service.detect_for_task(db, task_row)

        # Session dùng autoflush=False (src/db.py) — SELECT trong vòng lặp
        # không thấy row vừa add() nhưng chưa flush. Nếu cluster_data["items"]
        # chứa 2 item cùng message_id (vd resync/overlap fetch), 2 lần add()
        # sẽ tạo 2 ClusterMessage pending trùng PK -> UniqueViolation lúc
        # commit. Dùng set trong bộ nhớ để dedupe, không phụ thuộc autoflush.
        linked_message_ids = {
            row[0]
            for row in db.execute(
                select(ClusterMessage.message_id).where(ClusterMessage.cluster_id == cluster_row.id)
            ).all()
        }
        evidenced_message_ids: set[int] = set()
        has_new_message = False

        for item in cluster_data["items"]:
            message_dict = item["message"]
            message_row, created = _get_or_create_message(db, user_id, message_dict)
            has_new_message = has_new_message or created

            is_new_link = message_row.id not in linked_message_ids
            if is_new_link:
                db.add(ClusterMessage(cluster_id=cluster_row.id, message_id=message_row.id))
                linked_message_ids.add(message_row.id)

            # Evidence ghi cho message MỚI gắn vào cụm (task mới tạo, mọi item
            # đều mới; task cũ resync thì chỉ message thật sự mới — vd 1 reply
            # trên thread đã duyệt/hoàn thành — mới cần evidence, message cũ
            # lặp lại mỗi lần resync không được nhân đôi).
            if is_new_link and message_row.id not in evidenced_message_ids:
                db.add(
                    TaskEvidence(
                        task_id=task_row.id,
                        message_id=message_row.id,
                        provider=message_dict["provider"],
                        evidence_quote=item.get("evidence_quote", ""),
                        deep_link=message_dict["deep_link"],
                        has_attachment=bool(message_dict.get("attachments")),
                    )
                )
                evidenced_message_ids.add(message_row.id)

        if not is_new_task and has_new_message and task_row.status in _REOPENABLE_STATUSES:
            # Task đã duyệt/hoàn thành/huỷ nhưng vừa có 1 message THẬT SỰ mới
            # (vd reply mới trên đúng thread đã duyệt xong) gắn vào cùng cụm —
            # việc chưa thật sự xong, mở lại thay vì lặng lẽ bỏ qua hay tạo
            # task trùng bên cạnh (yêu cầu người dùng 2026-08-20). Theo chính
            # sách tự xác nhận, mở lại là agent tự xác nhận lại luôn; sai thì
            # user xoá như với task mới.
            task_row.status = "confirmed"
            task_row.reasons = sorted({AUTO_CONFIRMED_REASON, *(task_row.reasons or []), "reopened_by_new_reply"})
            db.flush()
            stale_notice = db.execute(
                select(Reminder).where(Reminder.task_id == task_row.id, Reminder.kind == "task_proposed")
            ).scalar_one_or_none()
            if stale_notice is not None:
                db.delete(stale_notice)
                db.flush()
            generate_proposed_notice(db, task_row)
            generate_default_reminders(db, task_row)

        tasks_persisted.append({"task_id": task_row.id, "cluster_key": cluster_key, "title": task_row.title})

    tasks_retracted = _retract_noise_tasks(db, user_id, state)
    db.commit()
    return {"tasks_persisted": tasks_persisted, "tasks_retracted": tasks_retracted}
