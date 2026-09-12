import re
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_current_user_id
from src.api.rate_limit import limiter
from src.config import get_settings
from src.db import get_db
from src.models.meeting_note import MeetingActionItem, MeetingNote
from src.models.project import Project
from src.models.schemas import (
    CamelModel,
    MeetingActionItemResponse,
    MeetingNoteCreateRequest,
    MeetingNoteListItemResponse,
    MeetingNoteListResponse,
    MeetingNoteResponse,
    MeetingNoteUpdateRequest,
    TaskResponse,
)
from src.models.task import Task
from src.models.user import User
from src.services.meeting_notes import suggest_meeting_title, summarize_meeting
from src.services.recording_quota import consume_slot, slot_offset_ms
from src.services.recording_quota import get_status as get_quota_status
from src.services.stt import Turn, build_turns, transcribe_chunk, turns_to_transcript
from src.services.usage_quota import consume_meeting_summary

router = APIRouter(prefix="/meeting-notes", tags=["meeting-notes"])

_DEFAULT_TITLE = "Cuộc họp mới"


def _action_items(db: Session, note_id: int) -> list[MeetingActionItem]:
    return list(
        db.execute(
            select(MeetingActionItem).where(MeetingActionItem.meeting_note_id == note_id).order_by(MeetingActionItem.id)
        )
        .scalars()
        .all()
    )


def _to_response(db: Session, note: MeetingNote) -> MeetingNoteResponse:
    items = [MeetingActionItemResponse.model_validate(row, from_attributes=True) for row in _action_items(db, note.id)]
    return MeetingNoteResponse.model_validate(note, from_attributes=True).model_copy(update={"action_items": items})


def _get_owned_note(db: Session, note_id: int, user_id: str) -> MeetingNote:
    row = db.execute(
        select(MeetingNote).where(MeetingNote.id == note_id, MeetingNote.user_id == user_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ghi chú cuộc họp.")
    return row


@router.get("", response_model=MeetingNoteListResponse)
def list_meeting_notes(
    project_id: int | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MeetingNoteListResponse:
    """Danh sách cuộc họp, mới nhất trước.

    Đếm action item bằng một truy vấn gộp theo note thay vì lặp từng cuộc họp,
    để danh sách dài không sinh ra N+1 query.
    """
    statement = select(MeetingNote).where(MeetingNote.user_id == user_id)
    if project_id is not None:
        statement = statement.where(MeetingNote.project_id == project_id)
    notes = list(db.execute(statement.order_by(MeetingNote.created_at.desc())).scalars().all())
    if not notes:
        return MeetingNoteListResponse(meetings=[])

    note_ids = [note.id for note in notes]
    counts = db.execute(
        select(
            MeetingActionItem.meeting_note_id,
            func.count(MeetingActionItem.id),
            func.sum(case((MeetingActionItem.status == "suggested", 1), else_=0)),
        )
        .where(MeetingActionItem.meeting_note_id.in_(note_ids))
        .group_by(MeetingActionItem.meeting_note_id)
    ).all()
    total_by_note = {row[0]: int(row[1] or 0) for row in counts}
    open_by_note = {row[0]: int(row[2] or 0) for row in counts}

    return MeetingNoteListResponse(
        meetings=[
            MeetingNoteListItemResponse(
                id=note.id,
                title=note.title,
                status=note.status,
                started_at=note.started_at,
                ended_at=note.ended_at,
                updated_at=note.updated_at,
                action_item_count=total_by_note.get(note.id, 0),
                open_action_item_count=open_by_note.get(note.id, 0),
            )
            for note in notes
        ]
    )


@router.post("", response_model=MeetingNoteResponse, status_code=201)
def create_meeting_note(
    payload: MeetingNoteCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MeetingNoteResponse:
    if payload.project_id is not None:
        project = db.execute(select(Project).where(Project.id == payload.project_id, Project.user_id == str(user_id))).scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
    row = MeetingNote(
        user_id=user_id,
        title=payload.title.strip() or _DEFAULT_TITLE,
        notes=payload.notes,
        transcript=payload.transcript,
        project_id=payload.project_id,
        status="open",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(db, row)


class RecordingQuotaResponse(CamelModel):
    """Hạn mức ghi âm còn lại trong ngày của người đang đăng nhập."""

    limit_ms: int
    used_ms: int
    remaining_ms: int
    # True với quản trị viên: client ẩn hẳn phần đếm ngược thay vì hiện số vô nghĩa.
    unlimited: bool


# Phải khai báo TRƯỚC "/{note_id}", nếu không FastAPI khớp route theo thứ tự khai
# báo và "recording-quota" sẽ rơi vào note_id rồi chết 422 vì không ép được sang int.
@router.get("/recording-quota", response_model=RecordingQuotaResponse)
def get_recording_quota(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecordingQuotaResponse:
    """Cho client biết còn bao nhiêu thời gian ghi âm trước khi bắt đầu cuộc họp.

    Có endpoint riêng vì hạn mức cần kiểm ở thời điểm bấm nút ghi, chứ không phải
    đợi tới chunk đầu tiên: người dùng còn 1 phút mà mở máy ghi cả cuộc họp thì
    phần lớn nội dung mất trắng, biết trước thì họ chọn cách khác.
    """
    status = get_quota_status(db, user)
    return RecordingQuotaResponse(
        limit_ms=status.limit_ms,
        used_ms=status.used_ms,
        remaining_ms=status.remaining_ms,
        unlimited=status.unlimited,
    )


@router.get("/{note_id}", response_model=MeetingNoteResponse)
def get_meeting_note(
    note_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MeetingNoteResponse:
    return _to_response(db, _get_owned_note(db, note_id, user_id))


@router.patch("/{note_id}", response_model=MeetingNoteResponse)
def update_meeting_note(
    note_id: int,
    payload: MeetingNoteUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MeetingNoteResponse:
    """Autosave phần người dùng đang gõ. Chỉ ghi field thật sự được gửi lên."""
    note = _get_owned_note(db, note_id, user_id)
    if note.status != "open":
        raise HTTPException(
            status_code=409,
            detail="Cuộc họp đã kết thúc, không sửa được nội dung gốc nữa.",
        )
    if payload.title is not None:
        note.title = payload.title.strip() or _DEFAULT_TITLE
    if payload.notes is not None:
        note.notes = payload.notes
    if payload.transcript is not None:
        note.transcript = payload.transcript
    db.commit()
    db.refresh(note)
    return _to_response(db, note)


@router.delete("/{note_id}", status_code=204)
def delete_meeting_note(
    note_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    note = _get_owned_note(db, note_id, user_id)
    # Xoá action item thủ công: sqlite trong dev/test không bật ON DELETE
    # CASCADE nên chỉ dựa vào ràng buộc FK là để lại rác mồ côi.
    for item in _action_items(db, note.id):
        db.delete(item)
    db.delete(note)
    db.commit()


@router.post("/{note_id}/end", response_model=MeetingNoteResponse)
@limiter.limit("5/minute")
async def end_meeting_note(
    request: Request,
    note_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MeetingNoteResponse:
    """Kết thúc cuộc họp: gọi LLM tóm tắt và trích việc cần làm.

    Chỉ chạy được đúng một lần cho mỗi cuộc họp. Chạy lại sẽ phải quyết định số
    phận của những action item người dùng đã chấp nhận hoặc đã bỏ, nên chặn từ
    đây thay vì âm thầm ghi đè lựa chọn của họ.
    """
    note = _get_owned_note(db, note_id, user_id)
    if note.status != "open":
        raise HTTPException(status_code=409, detail="Cuộc họp này đã được tổng hợp rồi.")
    if not note.notes.strip() and not note.transcript.strip():
        raise HTTPException(
            status_code=422,
            detail="Chưa có ghi chú hoặc transcript nào để tổng hợp.",
        )

    # Reserve before the external call so concurrent requests cannot both spend
    # an LLM turn on the same user's daily allowance.
    consume_meeting_summary(db, user_id)

    try:
        result = await summarize_meeting(note.title, note.notes, note.transcript)
    except Exception as exc:  # noqa: BLE001 - lỗi nhà cung cấp LLM, không phải lỗi dữ liệu
        raise HTTPException(status_code=502, detail=f"Không tổng hợp được cuộc họp: {exc}") from exc

    for item in result.action_items:
        db.add(
            MeetingActionItem(
                meeting_note_id=note.id,
                title=item.title,
                detail=item.detail,
                assignee=item.assignee,
                assignee_ambiguous=item.assignee_ambiguous,
                time_expression=item.time_expression,
                due_at=item.due_at,
                ambiguous=item.ambiguous,
                evidence_quote=item.evidence_quote,
                status="suggested",
            )
        )
    note.summary = result.summary
    note.decisions = "\n".join(result.decisions)
    note.status = "summarized"
    # Giữ mốc dừng ghi âm nếu đã có: người dùng có thể bấm tổng hợp nhiều giờ
    # sau cuộc họp, ghi đè bằng thời điểm bấm sẽ thổi phồng thời lượng hiển thị.
    if note.ended_at is None:
        note.ended_at = datetime.now(UTC)

    # Đặt tên theo nội dung tóm tắt, chỉ khi người dùng chưa tự đặt tên. Đến đây
    # mới có tóm tắt nên tiêu đề đặt được sát chủ đề hơn lúc vừa dừng ghi.
    if note.title.strip() in ("", _DEFAULT_TITLE):
        note.title = await suggest_meeting_title(
            note.notes,
            note.transcript,
            note.started_at,
            summary=result.summary,
        )
    db.commit()
    db.refresh(note)
    return _to_response(db, note)


def _get_owned_item(db: Session, note_id: int, item_id: int, user_id: str) -> MeetingActionItem:
    _get_owned_note(db, note_id, user_id)
    row = db.execute(
        select(MeetingActionItem).where(
            MeetingActionItem.id == item_id,
            MeetingActionItem.meeting_note_id == note_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy việc cần làm này trong cuộc họp.")
    return row


@router.post("/{note_id}/action-items/{item_id}/accept", response_model=TaskResponse, status_code=201)
def accept_action_item(
    note_id: int,
    item_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Biến một việc AI đề xuất thành Task thật, chỉ khi người dùng bấm chấp nhận.

    Task sinh ra ở trạng thái "proposed" chứ không phải "confirmed": nó đi tiếp
    vào đúng vòng đời task hiện có, nơi người dùng vẫn xác nhận lần cuối trước
    khi có bất kỳ hành động lịch nào (FR-062).
    """
    item = _get_owned_item(db, note_id, item_id, user_id)
    if item.status != "suggested":
        raise HTTPException(
            status_code=409,
            detail=f"Việc này đang ở trạng thái '{item.status}', không chấp nhận lại được.",
        )

    digest = sha256(f"{user_id}:{uuid4()}:{item.title}".encode()).hexdigest()[:56]
    task = Task(
        user_id=user_id,
        cluster_key=f"meeting-{digest}",
        title=item.title,
        detail=item.detail,
        due_at=item.due_at,
        ambiguous=item.ambiguous,
        assignee=item.assignee,
        assignee_ambiguous=item.assignee_ambiguous,
        status="proposed",
        source_count=1,
        signal_strength=0.0,
    )
    db.add(task)
    db.flush()
    item.status = "accepted"
    item.task_id = task.id
    db.commit()
    db.refresh(task)
    return TaskResponse.model_validate(task, from_attributes=True)


@router.post("/{note_id}/action-items/{item_id}/dismiss", response_model=MeetingActionItemResponse)
def dismiss_action_item(
    note_id: int,
    item_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MeetingActionItemResponse:
    item = _get_owned_item(db, note_id, item_id, user_id)
    if item.status != "suggested":
        raise HTTPException(
            status_code=409,
            detail=f"Việc này đang ở trạng thái '{item.status}', không bỏ qua lại được.",
        )
    item.status = "dismissed"
    db.commit()
    db.refresh(item)
    return MeetingActionItemResponse.model_validate(item, from_attributes=True)


# Nhãn hiển thị của hai kênh thu âm. Client chỉ biết mình đang thu mic hay thu
# tiếng tab, không biết tên người, nên nhãn phải trung tính và cố định.
_SPEAKER_LABELS: dict[str, str] = {"mine": "Tôi", "theirs": "Người khác"}

# Trần kích thước một chunk. Chunk thực tế dài vài chục giây nên chỉ vài trăm KB;
# 25MB là ngưỡng chặn client hỏng hoặc cố tình đẩy file lớn, không phải hạn mức
# dùng bình thường.
_MAX_AUDIO_CHUNK_BYTES = 25 * 1024 * 1024

# Hai định dạng MediaRecorder của trình duyệt sinh ra. Danh sách đóng để không
# vô tình nhận file tuỳ ý rồi đẩy thẳng lên nhà cung cấp STT.
_ALLOWED_AUDIO_CONTENT_TYPES = frozenset({"audio/webm", "audio/ogg"})

# Dòng do luồng ghi âm sinh ra. Dùng cả offset và speaker làm định danh logic
# của chunk: hai kênh có cùng offset vẫn hợp lệ, còn retry cùng kênh/offset thì
# không được nối transcript lần hai.
_RECORDED_LINE_PATTERN = re.compile(r"^\[(\d+):(\d{2})\]\s+([^:]+):")


def _insert_recorded_line(
    current: str,
    line: str,
    *,
    speaker: str,
    offset_ms: int,
) -> tuple[str, bool]:
    """Chèn một chunk theo thời gian và chống ghi trùng khi client retry.

    STT của mic và tiếng tab hoàn tất độc lập, nên thứ tự request khóa được row
    không nhất thiết là thứ tự nói. Transcript vẫn phải tăng dần theo offset.
    Cặp ``(speaker, offset giây)`` là khóa tự nhiên của chunk phía extension;
    gặp lại cặp đó nghĩa là response trước đã thất lạc và client đang retry.
    """
    lines = current.splitlines() if current else []
    new_offset_seconds = max(0, offset_ms) // 1000
    insert_at = len(lines)

    for index, existing in enumerate(lines):
        matched = _RECORDED_LINE_PATTERN.match(existing.strip())
        if matched is None:
            continue
        existing_offset_seconds = int(matched.group(1)) * 60 + int(matched.group(2))
        existing_speaker = matched.group(3).strip()
        if existing_offset_seconds == new_offset_seconds and existing_speaker == speaker:
            return current, False
        if insert_at == len(lines) and existing_offset_seconds > new_offset_seconds:
            insert_at = index

    lines.insert(insert_at, line)
    return "\n".join(lines), True


class MeetingAudioChunkResponse(CamelModel):
    """Kết quả xử lý một chunk: có nối vào transcript không, và text nghe được."""

    appended: bool
    # None khi không nối gì; response_model_exclude_none bỏ hẳn khoá này đi để
    # client không phải phân biệt chuỗi rỗng với "không có".
    text: str | None = None
    # Hạn mức ghi âm còn lại trong ngày, tính bằng mili giây. Trả về sau mỗi
    # chunk để extension đếm ngược được mà không phải gọi thêm endpoint. Quản
    # trị viên luôn nhận nguyên hạn mức vì không bị trừ.
    remaining_ms: int = 0


@router.post(
    "/{note_id}/audio-chunk",
    response_model=MeetingAudioChunkResponse,
    response_model_exclude_none=True,
)
async def append_meeting_audio_chunk(
    note_id: int,
    file: UploadFile = File(...),
    speaker: Literal["mine", "theirs"] = Form(...),
    offset_ms: int = Form(..., ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeetingAudioChunkResponse:
    """Nhận một chunk audio đang thu, nhận dạng ngay và nối vào transcript.

    Cơ chế: kiểm quyền sở hữu cuộc họp trước, chặn định dạng và kích thước lạ,
    đọc chunk vào bộ nhớ rồi gọi STT — audio không bao giờ được ghi xuống đĩa,
    xử lý xong là thả cho GC thu hồi. Chunk chỉ có tiếng ồn sẽ ra text rỗng và
    bị bỏ qua để transcript không đầy dòng trống.

    Trước khi ghi, cuộc họp được đọc lại bằng `with_for_update()` để khoá dòng:
    hai kênh mic và tab gửi chunk gần như cùng lúc lên cùng một note, đọc trước
    rồi mới ghi mà không khoá thì chunk về sau ghi đè lên transcript đã cũ và
    nuốt mất chunk về trước. `populate_existing` là bắt buộc kèm theo, vì không
    có nó ORM trả lại đối tượng cũ trong identity map thay vì giá trị vừa đọc.

    Hạn mức ghi âm được kiểm TRƯỚC khi gọi STT: chunk vượt hạn mức bị chặn ngay
    nên không tốn tiền nhà cung cấp cho phần audio sẽ bị từ chối. Ngược lại,
    hạn mức chỉ bị trừ SAU khi nhận dạng thành công — chunk hỏng vì lỗi mạng
    hoặc lỗi provider không được phép ăn mất phút của người dùng.
    """
    user_id = str(user.id)
    _get_owned_note(db, note_id, user_id)

    status = get_quota_status(db, user)
    if status.exhausted:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Đã dùng hết {status.limit_ms // 60000} phút ghi âm của hôm nay. "
                "Hạn mức làm mới vào 0 giờ (giờ Việt Nam)."
            ),
        )

    # Trình duyệt hay gắn thêm codec vào content type ("audio/webm;codecs=opus"),
    # nên chỉ so phần kiểu MIME đứng trước dấu chấm phẩy.
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Định dạng âm thanh không hỗ trợ. Chỉ nhận audio/webm hoặc audio/ogg.",
        )

    audio = await file.read()
    await file.close()
    if len(audio) > _MAX_AUDIO_CHUNK_BYTES:
        raise HTTPException(status_code=400, detail="Đoạn ghi âm quá lớn, tối đa 25MB mỗi chunk.")

    try:
        text = await transcribe_chunk(audio, file.filename or "chunk.webm")
    except Exception as exc:  # noqa: BLE001 - lỗi nhà cung cấp STT, không phải lỗi dữ liệu
        raise HTTPException(status_code=502, detail=f"Không nhận dạng được đoạn ghi âm: {exc}") from exc

    # Nhận dạng xong là thời gian ghi đã dùng thật, kể cả chunk chỉ có im lặng:
    # người dùng vẫn chiếm bấy nhiêu giây trên trục thời gian cuộc họp và vẫn
    # tốn một lượt gọi nhà cung cấp. Chỉ chunk chết trước bước này được miễn.
    slot_duration_ms = get_settings().recording_chunk_duration_ms
    consume_slot(db, user, note_id, slot_offset_ms(offset_ms, slot_duration_ms), slot_duration_ms)
    remaining_ms = get_quota_status(db, user).remaining_ms

    # Dựng dòng transcript qua đúng bộ hàm của stt để định dạng "[mm:ss] người:
    # nội dung" chỉ có một nơi quyết định. Chunk im lặng cho danh sách rỗng.
    turns: list[Turn] = build_turns([(_SPEAKER_LABELS[speaker], offset_ms, text)])
    if not turns:
        # Vẫn phải commit: lát hạn mức vừa ghi ở trên sẽ bị cuốn ngược khi session
        # đóng nếu nhánh này thoát ra mà không chốt transaction.
        db.commit()
        return MeetingAudioChunkResponse(appended=False, remaining_ms=remaining_ms)
    line = turns_to_transcript(turns)

    locked = db.execute(
        select(MeetingNote)
        .where(MeetingNote.id == note_id, MeetingNote.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if locked is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ghi chú cuộc họp.")

    locked.transcript, appended = _insert_recorded_line(
        locked.transcript or "",
        line,
        speaker=_SPEAKER_LABELS[speaker],
        offset_ms=offset_ms,
    )
    db.commit()
    return MeetingAudioChunkResponse(
        appended=appended,
        text=text if appended else None,
        remaining_ms=remaining_ms,
    )


class FinalizeRecordingResponse(CamelModel):
    """Kết quả khép lại một phiên ghi âm: cuộc họp bị xoá hay được giữ lại."""

    # True khi cuộc họp không thu được nội dung nào và đã bị xoá hẳn.
    deleted: bool
    # None khi deleted=True — không còn cuộc họp nào để trả về.
    title: str | None = None


@router.post(
    "/{note_id}/finalize-recording",
    response_model=FinalizeRecordingResponse,
    # Cùng quy ước với audio-chunk: bỏ hẳn khoá null thay vì bắt client phân
    # biệt "không có tiêu đề" với "tiêu đề rỗng".
    response_model_exclude_none=True,
)
async def finalize_recording(
    note_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> FinalizeRecordingResponse:
    """Khép lại phiên ghi âm: xoá cuộc họp rỗng và ghi mốc dừng.

    Cơ chế: bấm dừng mà không thu được chữ nào (mic tắt, họp chưa bắt đầu, bấm
    nhầm) sẽ để lại một cuộc họp trống trong danh sách — vô dụng và làm loãng
    danh sách thật, nên xoá luôn.

    Tiêu đề tự động được hoãn tới `/end`, khi đã có bản tóm tắt. Nếu đặt
    tên tạm từ transcript ngay tại đây thì `/end` không thể phân biệt nó với tên
    người dùng đã sửa, và sẽ bỏ lỡ tiêu đề tốt hơn dựa trên tóm tắt.
    """
    note = _get_owned_note(db, note_id, user_id)

    if not (note.transcript or "").strip() and not (note.notes or "").strip():
        # Dọn action item thủ công giống delete_meeting_note: sqlite ở dev/test
        # không bật ON DELETE CASCADE nên chỉ xoá note là để lại rác mồ côi.
        for item in _action_items(db, note.id):
            db.delete(item)
        db.delete(note)
        db.commit()
        return FinalizeRecordingResponse(deleted=True)

    # Ghi mốc dừng ghi âm ngay tại đây, không đợi tới lúc bấm tổng hợp: đây mới
    # là thời điểm cuộc họp thật sự kết thúc, và danh sách cần nó để tính thời
    # lượng thay vì hiện "đang diễn ra" mãi cho cuộc họp đã ghi xong.
    if note.ended_at is None:
        note.ended_at = datetime.now(UTC)
    db.commit()
    db.refresh(note)

    return FinalizeRecordingResponse(deleted=False, title=note.title)
