"""Test tầng lọc rác chk1-3 (src/services/prefilter.py) — dùng ví dụ đã đo
tay trong quá trình thiết kế (drawio review), không phải số liệu bịa.
"""

from src.services.prefilter import (
    _chk1_length,
    _chk2_keyword_and_language,
    _chk3_object_signal,
    _has_object_like_complement,
    run_prefilter,
    strip_junk_lines,
)

_REAL_TASK = "à quên, @Phong gửi giúp file báo cáo quý 3 trước 5h chiều mai"
_AD_NOISE = "Tải app Zalo để trải nghiệm đầy đủ"
_UI_LABEL = "Xem thêm"


def test_chk1_passes_normal_sentence():
    assert _chk1_length(_REAL_TASK) is True


def test_chk1_rejects_short_reply():
    assert _chk1_length("ok") is False


def test_chk1_rejects_text_with_no_letters():
    assert _chk1_length("😂😂😂") is False


def test_chk2_passes_vietnamese_text_with_matching_keyword():
    assert _chk2_keyword_and_language(_REAL_TASK) is True


def test_chk2_rejects_vietnamese_text_without_keyword_match():
    assert _chk2_keyword_and_language(_AD_NOISE) is False


def test_chk2_rejects_non_target_language():
    assert _chk2_keyword_and_language("Ok bro, send me the file pls") is False


def test_has_object_like_complement_true_when_noun_phrase_follows_verb():
    assert _has_object_like_complement("Gửi báo cáo cho khách hàng") is True


def test_has_object_like_complement_false_for_bare_verb_only_fragment():
    assert _has_object_like_complement("Xem thêm") is False


def test_chk3_passes_verb_with_noun_phrase_object():
    assert _chk3_object_signal(_REAL_TASK) is True


def test_chk3_rejects_bare_verb_fragment():
    assert _chk3_object_signal(_UI_LABEL) is False


def test_run_prefilter_passes_real_task():
    result = run_prefilter(_REAL_TASK)
    assert result.passed is True
    assert result.reason == "qua_het"


def test_run_prefilter_rejects_short_reply_at_first_check():
    result = run_prefilter("ok")
    assert result.passed is False
    assert result.reason == "duoi_nguong_ky_tu_token"


def test_run_prefilter_rejects_ad_noise():
    result = run_prefilter(_AD_NOISE)
    assert result.passed is False


def test_strip_junk_lines_removes_pure_emoticon_lines():
    # Case thật từ ảnh chụp side panel — chat Zalo lẫn nhiều dòng reaction
    # thuần giữa nội dung thật.
    text = "\n".join([":o", ":-((", ":-h", ">:>", "Duy Hứa nhớ gửi file báo cáo trước 5h chiều mai nhé"])
    cleaned = strip_junk_lines(text)
    assert cleaned == "Duy Hứa nhớ gửi file báo cáo trước 5h chiều mai nhé"


def test_strip_junk_lines_keeps_short_line_with_enough_letters():
    assert strip_junk_lines("ok nhé") == "ok nhé"


def test_strip_junk_lines_drops_single_letter_line():
    assert strip_junk_lines(":o") == ""

