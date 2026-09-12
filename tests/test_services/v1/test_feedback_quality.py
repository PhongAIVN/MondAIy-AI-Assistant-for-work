from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.services.feedback_quality import (
    FeedbackAssessmentUnavailableError,
    _parse_assessment,
    assess_feedback_quality,
    feedbacks_are_duplicates,
)


def test_parse_rejected_feedback_keeps_machine_readable_reason_code():
    result = _parse_assessment(
        '{"accepted": false, "code": "rating_mismatch", "reason": "Số sao trái với nội dung."}'
    )

    assert result.accepted is False
    assert result.code == "rating_mismatch"


def test_parse_unknown_rejection_code_falls_back_to_other():
    result = _parse_assessment('{"accepted": false, "code": "invented", "reason": "Không hợp lệ."}')

    assert result.code == "other"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "feedback,rating",
    [
        ("Tóm tắt Gmail có link nguồn nên tôi xác minh nhanh hơn.", 5),
        ("Lịch bị lệch múi giờ khiến tôi bỏ lỡ buổi học; hãy dùng UTC+7.", 1),
    ],
)
async def test_llm_accepts_substantive_praise_and_criticism(feedback, rating):
    model = SimpleNamespace(
        ainvoke=AsyncMock(
            return_value=SimpleNamespace(content='{"accepted": true, "reason": "Có quan sát cụ thể và tác động."}')
        )
    )
    with patch("src.services.feedback_quality.get_llm", return_value=model):
        result = await assess_feedback_quality(feedback, rating)

    assert result.accepted is True
    sent_feedback = model.ainvoke.await_args.args[0][1][1]
    assert feedback in sent_feedback


@pytest.mark.asyncio
async def test_malformed_llm_verdict_fails_closed():
    model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content="looks good")))
    with patch("src.services.feedback_quality.get_llm", return_value=model):
        with pytest.raises(FeedbackAssessmentUnavailableError):
            await assess_feedback_quality("Phản hồi đủ dài và có vẻ cụ thể cho sản phẩm.", 4)


def test_duplicate_detection_ignores_accents_case_and_light_edits():
    original = "Lịch bị lệch múi giờ nên tôi đã bỏ lỡ buổi học hôm nay."
    edited = "LICH bi lech mui gio nen toi da bo lo buoi hoc hom nay!!!"
    different = "Tóm tắt Gmail có đường dẫn nguồn giúp tôi kiểm tra nhanh."

    assert feedbacks_are_duplicates(edited, original)
    assert not feedbacks_are_duplicates(different, original)
