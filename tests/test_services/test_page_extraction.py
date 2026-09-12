"""Test rule engine `is_task_like` và hybrid `summarize_page_extraction` (xem
src/services/page_extraction.py) dựa trên golden dataset dùng chung ở
"ml/model for extension/data/" (chuyển từ eval/golden_dataset/task_extraction/
sang đây vì đây là data huấn luyện riêng của model_for_extension — vẫn theo
đúng convention JSON tự chứa như eval/golden_dataset/evidence_verification/).

Bộ golden đó cũng được scripts/eval_task_classifiers.py dùng để so sánh 3
hướng xử lý (rule-based / LLM / hybrid) — sửa dataset ở một chỗ duy nhất.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import get_settings
from src.db import Base
from src.models.user import User
from src.services.memory_store import EvidenceRef, record_memory
from src.services.page_extraction import (
    _ExtractedTaskItem,
    _summarize_via_line_rules,
    _TaskExtractionResult,
    confidence_tier,
    is_task_like,
    summarize_page_extraction,
)

_DATASET_DIR = Path(__file__).resolve().parents[2] / "eval" / "golden_dataset" / "task_extraction"

# In-memory DB riêng cho file test này — summarize_page_extraction giờ đọc
# user_profile/long_term_memories (src/services/memory_store.py,
# profile_memory.py) trước khi gọi LLM, cần Session thật (khớp pattern
# tests/test_services/v1/test_memory_store.py).
_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(bind=_engine)
_counter = iter(range(1, 100000))


@pytest.fixture
def db():
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def user_id(db) -> str:
    index = next(_counter)
    user = User(email=f"page-extraction-{index}@example.com", password_hash="x")
    db.add(user)
    db.commit()
    return str(user.id)


def _load(name: str) -> list[dict]:
    return json.loads((_DATASET_DIR / name).read_text(encoding="utf-8"))


_CASES = _load("task_extraction_cases.json")
POSITIVE_CASES = [c["input"]["text"] for c in _CASES if c["expected"]["is_task"] is True]
NEGATIVE_CASES = [c["input"]["text"] for c in _CASES if c["expected"]["is_task"] is False]


def test_golden_dataset_has_expected_size():
    """Chốt kích thước bộ dữ liệu — sửa JSON mà quên cập nhật số lượng dự kiến
    thì test này báo ngay."""
    assert len(POSITIVE_CASES) == 110
    assert len(NEGATIVE_CASES) == 110
    # Không câu nào trùng lặp trong mỗi nhóm — trùng thì coi như bớt tín hiệu
    # thật của bộ test dù tổng số câu vẫn đúng.
    assert len(set(POSITIVE_CASES)) == len(POSITIVE_CASES)
    assert len(set(NEGATIVE_CASES)) == len(NEGATIVE_CASES)


@pytest.mark.parametrize("case", _CASES, ids=lambda c: c["id"])
def test_golden_case_matches_expected(case: dict):
    text = case["input"]["text"]
    expected = case["expected"]["is_task"]
    assert is_task_like(text) is expected, f"{case['id']}: kỳ vọng {expected} nhưng rule trả khác — {text!r}"


def test_golden_dataset_overall_accuracy_at_least_90_percent():
    """Ngưỡng chấp nhận cho rule-based: không kỳ vọng 100% (rule luôn có trần
    precision/recall so với hiểu ngữ nghĩa thật), nhưng dưới 90% nghĩa là rule
    đang thiếu pattern quan trọng hoặc quá tay bắt nhầm — cần xem lại trước khi
    dùng làm mặc định cho tab "Lấy dữ liệu"."""
    correct = sum(1 for c in _CASES if is_task_like(c["input"]["text"]) is c["expected"]["is_task"])
    total = len(_CASES)
    accuracy = correct / total
    assert accuracy >= 0.90, f"Accuracy {accuracy:.1%} ({correct}/{total}) dưới ngưỡng 90%"


# ---------------------------------------------------------------------------
# confidence_tier — đoạn cực ngắn kiểu nhãn nút UI ("Gửi nhanh", "Gửi số"...)
# phải bị loại thẳng ở tầng rule (strong_negative), không lọt xuống LLM. Trước
# fix này, dòng dạng này rơi vào "ambiguous" → LLM thật nhận một chuỗi 2 từ
# không có ngữ cảnh, dễ đoán nhầm thành task (bug thật gặp khi trích xuất
# trang Messenger/Zalo — nút "Gửi nhanh"/"Gửi số" lẫn vào nội dung lấy được).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["Gửi nhanh", "Gửi số", "Đặt lịch"])
def test_confidence_tier_marks_bare_short_action_fragment_as_strong_negative(text: str):
    assert confidence_tier(text) == "strong_negative"


def test_confidence_tier_still_ambiguous_for_longer_bare_action_sentence():
    """Ngưỡng chỉ áp cho đoạn cực ngắn — câu đủ dài dù chỉ có động từ hành
    động trần vẫn phải qua LLM như cũ, không được loại oan."""
    assert confidence_tier("Chuẩn bị tài liệu họp tuần sau") == "ambiguous"


@pytest.mark.asyncio
async def test_line_rules_fallback_skips_llm_for_ui_button_label_fragment():
    """Nhánh fallback rule+LLM hybrid per-line (_summarize_via_line_rules —
    dùng khi LLM một-lượt lỗi hoặc mock_llm=True): nhãn nút UI lẫn vào lúc
    trích xuất trang không được tốn lời gọi LLM lẫn bị nhận nhầm thành task."""
    text = "Gửi nhanh"
    fake_llm = AsyncMock()
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm) as mock_get_llm,
    ):
        summaries = await _summarize_via_line_rules("https://example.com", "Trang mẫu", text, [text])

    mock_get_llm.assert_not_called()
    assert len(summaries) == 1
    assert summaries[0].title == "Trang mẫu"  # fallback: không dòng nào khớp task


# ---------------------------------------------------------------------------
# summarize_page_extraction — đường chính LLM một lượt trên toàn đoạn, fallback
# rule+LLM hybrid per-line khi mock_llm=True hoặc LLM lỗi (xem module
# docstring). mock_llm=True để test tất định, không tốn API thật.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_page_extraction_returns_separate_suggestions_for_non_adjacent_task_lines(db, user_id):
    """Dòng khớp việc-cần-làm nhưng KHÔNG liền kề nhau (có dòng không khớp xen
    giữa) phải tách thành suggestion riêng — không gộp nhầm 2 việc không liên
    quan chỉ vì cùng xuất hiện trong text."""
    text = "Chào buổi sáng cả nhà\nHãy gửi file trước 5h chiều\nHôm nay trời đẹp quá\n- [ ] Nộp báo cáo tuần"
    settings = get_settings()
    with patch.object(settings, "mock_llm", True):
        summaries = await summarize_page_extraction("https://example.com", "Trang mẫu", text, db, user_id)

    titles = [s.title for s in summaries]
    assert titles == ["Hãy gửi file trước 5h chiều", "- [ ] Nộp báo cáo tuần"]
    assert "Chào buổi sáng cả nhà" not in titles
    assert "Hôm nay trời đẹp quá" not in titles
    assert summaries[0].source_url == "https://example.com"


@pytest.mark.asyncio
async def test_summarize_page_extraction_groups_adjacent_task_like_lines_into_one_suggestion(db, user_id):
    """Nhiều dòng LIÊN TIẾP cùng khớp việc-cần-làm phải gộp thành MỘT
    suggestion — một việc thường viết rải qua vài dòng/tin nhắn liền kề, tách
    vụn từng dòng làm mất ngữ cảnh và tạo nhiều suggestion trùng lặp cho cùng
    một việc."""
    text = "Hãy gửi báo cáo\n- [ ] Đính kèm file hợp đồng\nChào buổi sáng cả nhà\n- [ ] Nộp trước thứ Sáu"
    settings = get_settings()
    with patch.object(settings, "mock_llm", True):
        summaries = await summarize_page_extraction("https://example.com", "Trang mẫu", text, db, user_id)

    assert len(summaries) == 2
    assert summaries[0].title == "Hãy gửi báo cáo"
    assert "Hãy gửi báo cáo" in summaries[0].detail
    assert "Đính kèm file hợp đồng" in summaries[0].detail
    assert summaries[1].title == "- [ ] Nộp trước thứ Sáu"


@pytest.mark.asyncio
async def test_summarize_page_extraction_falls_back_to_raw_text_when_no_task_like_line(db, user_id):
    text = "Chào buổi sáng cả nhà\nHôm nay trời đẹp quá"
    settings = get_settings()
    with patch.object(settings, "mock_llm", True):
        summaries = await summarize_page_extraction("https://example.com", "", text, db, user_id)

    assert len(summaries) == 1
    assert summaries[0].title == "Chào buổi sáng cả nhà"
    assert text in summaries[0].detail
    assert summaries[0].source_url == "https://example.com"


@pytest.mark.asyncio
async def test_summarize_page_extraction_uses_fallback_title_when_nothing_available(db, user_id):
    settings = get_settings()
    with patch.object(settings, "mock_llm", True):
        summaries = await summarize_page_extraction("https://example.com", "", "", db, user_id)

    assert len(summaries) == 1
    assert summaries[0].title == "Việc từ trang đã lấy dữ liệu"
    assert summaries[0].detail == ""
    assert summaries[0].source_url == "https://example.com"


def _fake_llm_returning(tasks: list[_ExtractedTaskItem]) -> tuple[AsyncMock, AsyncMock]:
    fake_structured = AsyncMock()
    fake_structured.ainvoke = AsyncMock(return_value=_TaskExtractionResult(tasks=tasks))
    fake_llm = AsyncMock()
    fake_llm.with_structured_output = lambda *_a, **_kw: fake_structured
    return fake_llm, fake_structured


@pytest.mark.asyncio
async def test_summarize_page_extraction_calls_llm_once_on_whole_text(db, user_id):
    """Đường chính: MỘT lượt gọi LLM trên TOÀN đoạn (không phân loại per-line)
    — LLM tự gom các dòng RẢI RÁC (không liền kề) thuộc cùng một việc thành
    một suggestion, điều rule+per-line không làm được (chỉ gom được dòng liền
    kề, xem _group_consecutive_matches)."""
    text = "Mai có họp lúc 2h\nChào buổi sáng cả nhà\nNhớ mang theo tài liệu dự án X"
    fake_llm, fake_structured = _fake_llm_returning(
        [
            _ExtractedTaskItem(
                title="Họp lúc 2h, mang tài liệu dự án X",
                detail="Mai có họp lúc 2h. Nhớ mang theo tài liệu dự án X.",
            )
        ]
    )
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm) as mock_get_llm,
    ):
        summaries = await summarize_page_extraction("https://example.com", "Trang mẫu", text, db, user_id)

    mock_get_llm.assert_called_once_with(lane="work_response")
    fake_structured.ainvoke.assert_awaited_once()
    assert len(summaries) == 1
    assert summaries[0].title == "Họp lúc 2h, mang tài liệu dự án X"
    assert summaries[0].source_url == "https://example.com"


@pytest.mark.asyncio
async def test_summarize_page_extraction_falls_back_to_line_rules_when_llm_returns_no_tasks(db, user_id):
    """LLM một-lượt xác nhận không có task nào (danh sách rỗng — khác lỗi) thì
    fallback dùng nguyên text thô, không tự bịa task."""
    text = "Chào buổi sáng cả nhà"
    fake_llm, _ = _fake_llm_returning([])
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        summaries = await summarize_page_extraction("https://example.com", "Trang mẫu", text, db, user_id)

    assert len(summaries) == 1
    assert summaries[0].title == "Trang mẫu"


@pytest.mark.asyncio
async def test_summarize_page_extraction_falls_back_to_rule_when_llm_errors(db, user_id):
    """LLM lỗi/hết quota không được chặn hẳn tính năng — fallback về rule."""
    text = "Hãy gửi file trước 5h chiều"  # rule: True qua imperative_start
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", side_effect=RuntimeError("provider down")),
    ):
        summaries = await summarize_page_extraction("https://example.com", "Trang mẫu", text, db, user_id)

    assert len(summaries) == 1
    assert summaries[0].title == text


# ---------------------------------------------------------------------------
# due_at: LLM chỉ trích NGUYÊN VĂN cụm thời hạn (deadline_text), server tự
# resolve_due_at() — BR-05 (PRD §9): chỉ set due_at khi text gốc có đủ
# ngày+giờ+timezone tường minh, mơ hồ thì bỏ qua thay vì đoán.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_page_extraction_sets_due_at_when_deadline_explicit(db, user_id):
    text = "Gửi báo cáo cho khách hàng"
    fake_llm, _ = _fake_llm_returning(
        [
            _ExtractedTaskItem(
                title="Gửi báo cáo",
                detail="Gửi báo cáo cho khách.",
                deadline_text="20/8/2026 14:00 +07:00",
            )
        ]
    )
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        summaries = await summarize_page_extraction("https://example.com", "Trang mẫu", text, db, user_id)

    assert summaries[0].due_at is not None
    assert summaries[0].due_at.year == 2026
    assert summaries[0].due_at.month == 8
    assert summaries[0].due_at.day == 20


@pytest.mark.asyncio
async def test_summarize_page_extraction_keeps_deadline_text_in_detail_when_ambiguous(db, user_id):
    """Cụm thời hạn mơ hồ (thiếu giờ/timezone tường minh) không set due_at
    (BR-05) — nhưng vẫn giữ nguyên cụm gốc trong detail để người dùng thấy và
    tự đặt ngày, không âm thầm mất thông tin."""
    text = "Gửi báo cáo cho khách hàng"
    fake_llm, _ = _fake_llm_returning(
        [_ExtractedTaskItem(title="Gửi báo cáo", detail="Gửi báo cáo cho khách.", deadline_text="chiều mai")]
    )
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        summaries = await summarize_page_extraction("https://example.com", "Trang mẫu", text, db, user_id)

    assert summaries[0].due_at is None
    assert "chiều mai" in summaries[0].detail


@pytest.mark.asyncio
async def test_summarize_page_extraction_resolves_bare_today_to_end_of_day(db, user_id):
    """"hôm nay" thiếu giờ/timezone nên resolve_due_at() (BR-05) trả None —
    nhưng phần NGÀY không hề mơ hồ (luôn là hôm nay), nên
    _resolve_bare_today_or_tomorrow() tự set 23:59:59 ICT thay vì để trống."""
    # text đầu vào (nội dung trang) phải đủ qua được prefilter (chk1-4, xem
    # src/services/prefilter.py) mới tới lượt gọi LLM mock — khác hẳn
    # deadline_text/detail bên dưới (nội dung LLM TRẢ VỀ, độc lập với text vào).
    text = "Cô gửi file ĐRL các bạn trong danh sách TN đợt này, nhớ chấm điểm rèn luyện giúp cô"
    fake_llm, _ = _fake_llm_returning(
        [_ExtractedTaskItem(title="Chấm điểm rèn luyện", detail="chấm điểm.", deadline_text="hết ngày hôm nay")]
    )
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        summaries = await summarize_page_extraction("https://example.com", "Trang mẫu", text, db, user_id)

    due_at = summaries[0].due_at
    assert due_at is not None
    now_ict = datetime.now(timezone(timedelta(hours=7)))
    assert due_at.date() == now_ict.date()
    assert (due_at.hour, due_at.minute, due_at.second) == (23, 59, 59)
    # Ambiguous fallback (dòng "Hạn: ...") chỉ chèn khi due_at vẫn None — đã
    # resolve được thì không lặp lại cụm gốc trong detail nữa.
    assert "Hạn:" not in summaries[0].detail


@pytest.mark.asyncio
async def test_summarize_page_extraction_resolves_bare_tomorrow_to_end_of_day(db, user_id):
    text = "Thầy nhắc cả lớp nộp bài tập giúp thầy"
    fake_llm, _ = _fake_llm_returning(
        [_ExtractedTaskItem(title="Nộp bài tập", detail="Nộp bài.", deadline_text="ngày mai")]
    )
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        summaries = await summarize_page_extraction("https://example.com", "Trang mẫu", text, db, user_id)

    due_at = summaries[0].due_at
    assert due_at is not None
    tomorrow_ict = datetime.now(timezone(timedelta(hours=7))) + timedelta(days=1)
    assert due_at.date() == tomorrow_ict.date()


@pytest.mark.asyncio
async def test_summarize_page_extraction_does_not_resolve_tomorrow_when_explicit_date_present(db, user_id):
    """Bug thật (phản hồi người dùng 2026-08-27): tin nhắn Zalo CŨ ghi "trước
    12PM ngày mai (26/08/2026)" — "ngày mai" neo theo LÚC GỬI TIN, không phải
    lúc trích xuất trang (có thể vài ngày sau). Cụm có kèm ngày/giờ tường
    minh thì _resolve_bare_today_or_tomorrow phải BỎ QUA hẳn (không tự suy
    "ngày mai" từ thời điểm trích xuất — sai ngày thật gặp: ra 28/8 thay vì
    26/8), giữ due_at None và giữ nguyên cụm gốc trong detail."""
    text = "Cô gửi file ĐRL, trước 12PM ngày mai (26/08/2026) không ý kiến gì thì cô gửi file đi nhé"
    fake_llm, _ = _fake_llm_returning(
        [
            _ExtractedTaskItem(
                title="Gửi file ĐRL",
                detail="Cô gửi file ĐRL cho các bạn.",
                deadline_text="trước 12PM ngày mai (26/08/2026)",
            )
        ]
    )
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        summaries = await summarize_page_extraction("https://example.com", "Trang mẫu", text, db, user_id)

    assert summaries[0].due_at is None
    assert "trước 12PM ngày mai (26/08/2026)" in summaries[0].detail


# ---------------------------------------------------------------------------
# Memory context: user_profile/long_term_memories (src/services/memory_store.py,
# profile_memory.py) được inject vào prompt LLM để điền bối cảnh mà text
# không nói rõ (vd dự án nào) — cùng pattern src/agents/nodes/core_nodes.py.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_page_extraction_injects_confirmed_memory_into_llm_prompt(db, user_id):
    record_memory(
        db,
        user_id,
        kind="project",
        subject="user",
        predicate="working_on",
        object_value="Dự án Sao Hoả",
        source_authority="user",
        created_by="user",
        evidence=[EvidenceRef("conversation_message", "m1")],
    )
    db.flush()

    fake_llm, fake_structured = _fake_llm_returning(
        [_ExtractedTaskItem(title="Gửi file", detail="Gửi file cho anh.")]
    )
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        await summarize_page_extraction("https://example.com", "Trang mẫu", "Gửi file cho anh nhé", db, user_id)

    messages = fake_structured.ainvoke.call_args.args[0]
    # Không match substring trên toàn bộ prompt: chính system prompt cũng
    # NHẮC TÊN thẻ <long_term_memory> trong hướng dẫn cách dùng, match kiểu đó
    # sẽ luôn "pass" kể cả khi injection thật sự bị hỏng. Kiểm đúng message
    # RIÊNG chứa khối đã render (mở bằng "<long_term_memory>\n").
    memory_messages = [m for m in messages if m["content"].startswith("<long_term_memory>\n")]
    assert len(memory_messages) == 1
    assert "Dự án Sao Hoả" in memory_messages[0]["content"]


@pytest.mark.asyncio
async def test_summarize_page_extraction_skips_memory_context_when_none_exists(db, user_id):
    """User chưa có memory/profile nào — không chèn thêm message context nào
    ngoài system prompt + text cần xử lý (đúng 2 message)."""
    fake_llm, fake_structured = _fake_llm_returning(
        [_ExtractedTaskItem(title="Gửi file", detail="Gửi file cho anh.")]
    )
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        await summarize_page_extraction("https://example.com", "Trang mẫu", "Gửi file cho anh nhé", db, user_id)

    messages = fake_structured.ainvoke.call_args.args[0]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert not any(m["content"].startswith("<long_term_memory>\n") for m in messages)
    assert not any(m["content"].startswith("<user_profile>\n") for m in messages)


# ---------------------------------------------------------------------------
# source_context: nhãn nguồn client tự đoán (vd tên nhóm chat) — cần thiết cho
# SPA route tĩnh (Zalo web luôn ở chat.zalo.me dù đang mở nhóm nào, khác Gmail
# đổi route theo email đang xem) nên url một mình không đủ xác định nguồn.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_page_extraction_injects_source_context_into_llm_prompt(db, user_id):
    fake_llm, fake_structured = _fake_llm_returning(
        [_ExtractedTaskItem(title="Gửi file", detail="Gửi file cho anh.")]
    )
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        await summarize_page_extraction(
            "https://chat.zalo.me",
            "Zalo",
            "Gửi file cho anh nhé",
            db,
            user_id,
            source_context="S25-64CNTT",
        )

    messages = fake_structured.ainvoke.call_args.args[0]
    source_messages = [m for m in messages if m["content"].startswith("<source_context>\n")]
    assert len(source_messages) == 1
    assert "S25-64CNTT" in source_messages[0]["content"]


@pytest.mark.asyncio
async def test_summarize_page_extraction_skips_source_context_message_when_empty(db, user_id):
    fake_llm, fake_structured = _fake_llm_returning(
        [_ExtractedTaskItem(title="Gửi file", detail="Gửi file cho anh.")]
    )
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        await summarize_page_extraction("https://example.com", "Trang mẫu", "Gửi file cho anh nhé", db, user_id)

    messages = fake_structured.ainvoke.call_args.args[0]
    assert not any(m["content"].startswith("<source_context>\n") for m in messages)


@pytest.mark.asyncio
async def test_summarize_page_extraction_returns_source_context_as_separate_field(db, user_id):
    """source_url/source_label trả RIÊNG khỏi detail (không còn nhét cứng vào
    cuối detail — chật/khó đọc trên panel hẹp, phản hồi người dùng
    2026-08-26). Zalo web url không đổi dù đang mở nhóm nào, source_label
    (từ source_context) mới là thứ phân biệt được nhóm nào."""
    fake_llm, _ = _fake_llm_returning([_ExtractedTaskItem(title="Gửi file", detail="Gửi file cho anh.")])
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        summaries = await summarize_page_extraction(
            "https://chat.zalo.me",
            "Zalo",
            "Gửi file cho anh nhé",
            db,
            user_id,
            source_context="S25-64CNTT",
        )

    assert summaries[0].source_url == "https://chat.zalo.me"
    assert summaries[0].source_label == "S25-64CNTT"
    assert "S25-64CNTT" not in summaries[0].detail
    assert "Nguồn" not in summaries[0].detail


# ---------------------------------------------------------------------------
# Field mở rộng (expected_output, constraint, execution_*, priority, assignee,
# stakeholders, deliver_to) — yêu cầu người dùng 2026-08-26. Extraction-only:
# CHỈ đường LLM một-lượt điền được, và chỉ khi nguồn nêu rõ (không bịa). Trả
# RIÊNG (không gộp vào detail) — client tự gộp lại lúc lưu thật, vì Task DB
# dùng chung nhiều pipeline khác không có cột riêng cho các field này.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_page_extraction_surfaces_extended_fields_when_source_states_them(db, user_id):
    fake_llm, _ = _fake_llm_returning(
        [
            _ExtractedTaskItem(
                title="Làm slide báo cáo quý",
                detail="Làm slide báo cáo quý cho phòng kinh doanh.",
                expected_output="Slide tối đa 10 trang, có biểu đồ doanh thu",
                constraint="Không dùng logo cũ, không gửi qua email cá nhân",
                execution_steps=["Thu thập số liệu quý 3", "Vẽ biểu đồ", "Trình bày theo template công ty"],
                execution_tool="Google Slides",
                execution_method="Làm theo template quý trước",
                priority="gấp lắm",
                assignee="Phong",
                stakeholders="chị Lan (duyệt nội dung)",
                deliver_to="nhóm Kinh doanh trên Zalo",
            )
        ]
    )
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        summaries = await summarize_page_extraction(
            "https://example.com", "Trang mẫu", "Phong làm slide báo cáo quý giúp anh", db, user_id
        )

    result = summaries[0]
    assert result.expected_output == "Slide tối đa 10 trang, có biểu đồ doanh thu"
    assert result.constraint == "Không dùng logo cũ, không gửi qua email cá nhân"
    assert result.execution_steps == ["Thu thập số liệu quý 3", "Vẽ biểu đồ", "Trình bày theo template công ty"]
    assert result.execution_tool == "Google Slides"
    assert result.execution_method == "Làm theo template quý trước"
    assert result.priority == "gấp lắm"
    assert result.assignee == "Phong"
    assert result.stakeholders == "chị Lan (duyệt nội dung)"
    assert result.deliver_to == "nhóm Kinh doanh trên Zalo"


@pytest.mark.asyncio
async def test_summarize_page_extraction_leaves_extended_fields_empty_when_source_silent(db, user_id):
    """Nguồn không nêu — LLM để trống, KHÔNG bịa cho đủ trường (cùng kỷ luật
    BR-05 áp cho deadline_text)."""
    fake_llm, _ = _fake_llm_returning([_ExtractedTaskItem(title="Gửi file", detail="Gửi file cho anh.")])
    settings = get_settings()

    with (
        patch.object(settings, "mock_llm", False),
        patch("src.services.page_extraction.get_llm", return_value=fake_llm),
    ):
        summaries = await summarize_page_extraction(
            "https://example.com", "Trang mẫu", "Gửi file cho anh nhé", db, user_id
        )

    result = summaries[0]
    assert result.expected_output == ""
    assert result.constraint == ""
    assert result.execution_steps == []
    assert result.execution_tool == ""
    assert result.execution_method == ""
    assert result.priority == ""
    assert result.assignee == ""
    assert result.stakeholders == ""
    assert result.deliver_to == ""
