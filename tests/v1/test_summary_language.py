"""Ngôn ngữ bản tóm tắt phải theo GIAO DIỆN người dùng, không theo mail nguồn.

Chốt chặn thật không nằm ở prompt mà ở `ground_candidate`: nó chấm bằng trùng
lặp từ vựng giữa bản tóm tắt và tư liệu. Bản dịch gần như không trùng từ nào
với nguồn, nên trước đây mọi bản dịch đều bị đánh trượt và rơi về nhánh nối
trích dẫn nguyên văn — người dùng để giao diện tiếng Việt vẫn nhận lại đúng
đoạn tiếng Anh của mail gốc.
"""

import pytest

from src.agents.pipeline.nodes.extract_batch import _system_prompt as extract_prompt
from src.agents.pipeline.nodes.reduce import _system_prompt as reduce_prompt
from src.guardrail.output import ground_candidate
from src.services.language import (
    SUPPORTED_LANGUAGES,
    empty_result_message,
    resolve,
    safety_net_title,
    summary_instruction,
    title_and_summary_instruction,
)

EN_SOURCE = (
    "Please review the attached benchmark sheet for 15 papers and send back "
    "the updated version before Friday 22/08. Ticket TAPB-178 tracks this."
)
VI_SOURCE = (
    "Em rà soát lại bảng benchmark gồm 15 bài báo đính kèm và gửi lại bản sửa "
    "trước thứ Sáu 22/08. Việc này theo dõi ở ticket TAPB-178."
)


def test_vietnamese_summary_of_an_english_mail_is_accepted():
    candidate = (
        "Mail yêu cầu rà soát bảng benchmark gồm 15 bài báo đính kèm và gửi lại "
        "bản đã sửa trước thứ Sáu 22/08, theo dõi ở ticket TAPB-178."
    )
    assert ground_candidate(candidate, {"m1": EN_SOURCE}).status == "grounded"


def test_english_summary_of_a_vietnamese_mail_is_accepted():
    candidate = (
        "The mail asks you to review the attached benchmark sheet of 15 papers "
        "and return the revised version before Friday 22/08, tracked in TAPB-178."
    )
    assert ground_candidate(candidate, {"m1": VI_SOURCE}).status == "grounded"


def test_a_translated_summary_that_invents_specifics_is_still_rejected():
    """Đổi cách chấm không có nghĩa là bỏ chấm: số, ngày, mã định danh, email —
    những thứ sống sót qua dịch thuật — vẫn phải có mặt trong nguồn."""
    candidate = "Mail yêu cầu rà soát 42 bài báo, nộp trước 30/09, gửi cho ai@fake.com."
    result = ground_candidate(candidate, {"m1": EN_SOURCE})
    assert result.status == "abstain"
    assert set(result.claims[0]["invented"]) >= {"42", "30/09", "ai@fake.com"}


def test_same_language_summaries_keep_the_original_lexical_check():
    """Không được nới lỏng đường cũ: cùng ngôn ngữ mà không bám tư liệu thì
    vẫn phải trượt."""
    unrelated = "Nhóm đã chốt xong ngân sách quảng cáo cho quý sau và không còn vướng mắc."
    assert ground_candidate(unrelated, {"m1": VI_SOURCE}).status == "abstain"


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_every_supported_language_has_all_display_strings(language):
    assert title_and_summary_instruction(language)
    assert summary_instruction(language)
    assert safety_net_title(language)
    assert empty_result_message(language)


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_prompts_carry_the_language_instruction(language):
    assert summary_instruction(language) in reduce_prompt(language)
    assert title_and_summary_instruction(language) in extract_prompt(language)


def test_unknown_language_falls_back_instead_of_crashing_the_run():
    """Ngôn ngữ hiển thị không đáng để đánh sập một lần Sync."""
    assert resolve("tlh") == "vi"
    assert resolve(None) == "vi"
    assert summary_instruction("tlh") == summary_instruction("vi")


def test_language_instruction_tells_the_model_to_translate_not_just_to_write():
    """Chỉ nói "viết bằng X" thì mô hình rất hay bám theo ngôn ngữ tư liệu."""
    assert "dịch sang" in summary_instruction("vi")
    assert "translating" in summary_instruction("en")
