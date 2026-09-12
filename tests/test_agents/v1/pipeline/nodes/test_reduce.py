from types import SimpleNamespace

import pytest

from src.agents.pipeline.nodes import reduce


@pytest.mark.asyncio
async def test_reduce_uses_mock_llm_path_and_preserves_evidence(monkeypatch):
    monkeypatch.setattr(reduce, "get_settings", lambda: SimpleNamespace(mock_llm=True))
    cluster = {
        "cluster_key": "c1",
        "title": "Submit report",
        "items": [{"message": {"id": "m1"}, "evidence_quote": "submit report by Friday"}],
    }

    result = await reduce.reduce_node({"clusters": [cluster], "errors": []})

    assert result["clusters"][0]["detail"] == "submit report by Friday"


@pytest.mark.asyncio
async def test_reduce_jira_only_cluster_never_calls_llm(monkeypatch):
    monkeypatch.setattr(reduce, "get_settings", lambda: SimpleNamespace(mock_llm=False))
    monkeypatch.setattr(reduce, "get_llm", lambda: (_ for _ in ()).throw(AssertionError("LLM called")))
    cluster = {
        "cluster_key": "c1",
        "title": "Hoàn thành báo cáo tuần 3",
        "items": [{"message": {"id": "TO04-42", "provider": "jira"}, "evidence_quote": "Đội cần nộp trước thứ Sáu."}],
    }

    result = await reduce.reduce_node({"clusters": [cluster], "errors": []})

    assert result["clusters"][0]["detail"] == "Đội cần nộp trước thứ Sáu."


@pytest.mark.asyncio
async def test_reduce_mixed_provider_cluster_still_uses_llm(monkeypatch):
    called = {"count": 0}

    class _FakeLLM:
        async def ainvoke(self, _messages):
            called["count"] += 1
            return SimpleNamespace(content="tóm tắt do LLM viết")

    monkeypatch.setattr(reduce, "get_settings", lambda: SimpleNamespace(mock_llm=False, max_llm_batches_per_run=3))
    monkeypatch.setattr(reduce, "get_llm", lambda: _FakeLLM())
    monkeypatch.setattr(reduce, "ground_candidate", lambda *a, **k: SimpleNamespace(status="grounded"))
    cluster = {
        "cluster_key": "c1",
        "title": "Việc gộp từ nhiều nguồn",
        "items": [
            {"message": {"id": "TO04-42", "provider": "jira"}, "evidence_quote": "Đội cần nộp trước thứ Sáu."},
            {"message": {"id": "m1", "provider": "google"}, "evidence_quote": "Please submit by Friday"},
        ],
    }

    result = await reduce.reduce_node({"clusters": [cluster], "errors": []})

    assert called["count"] == 1
    assert result["clusters"][0]["detail"] == "tóm tắt do LLM viết"


def test_system_prompt_switches_language_instruction():
    vi_prompt = reduce._system_prompt("vi")
    en_prompt = reduce._system_prompt("en")

    assert "tiếng Việt" in vi_prompt
    assert "English" in en_prompt


@pytest.mark.asyncio
async def test_reduce_node_passes_run_language_into_system_prompt(monkeypatch):
    captured_languages: list[str] = []

    class _FakeLLM:
        async def ainvoke(self, _messages):
            return SimpleNamespace(content="tóm tắt do LLM viết")

    original_system_prompt = reduce._system_prompt

    def spy_system_prompt(language: str) -> str:
        captured_languages.append(language)
        return original_system_prompt(language)

    monkeypatch.setattr(reduce, "get_settings", lambda: SimpleNamespace(mock_llm=False, max_llm_batches_per_run=3))
    monkeypatch.setattr(reduce, "get_llm", lambda: _FakeLLM())
    monkeypatch.setattr(reduce, "ground_candidate", lambda *a, **k: SimpleNamespace(status="grounded"))
    monkeypatch.setattr(reduce, "_system_prompt", spy_system_prompt)
    cluster = {
        "cluster_key": "c1",
        "title": "Submit report",
        "items": [{"message": {"id": "m1", "provider": "google"}, "evidence_quote": "Please submit by Friday"}],
    }

    await reduce.reduce_node({"clusters": [cluster], "errors": [], "language": "en"})

    assert captured_languages == ["en"]


@pytest.mark.asyncio
async def test_reduce_node_defaults_to_vi_when_state_has_no_language(monkeypatch):
    captured_languages: list[str] = []

    class _FakeLLM:
        async def ainvoke(self, _messages):
            return SimpleNamespace(content="tóm tắt do LLM viết")

    original_system_prompt = reduce._system_prompt

    def spy_system_prompt(language: str) -> str:
        captured_languages.append(language)
        return original_system_prompt(language)

    monkeypatch.setattr(reduce, "get_settings", lambda: SimpleNamespace(mock_llm=False, max_llm_batches_per_run=3))
    monkeypatch.setattr(reduce, "get_llm", lambda: _FakeLLM())
    monkeypatch.setattr(reduce, "ground_candidate", lambda *a, **k: SimpleNamespace(status="grounded"))
    monkeypatch.setattr(reduce, "_system_prompt", spy_system_prompt)
    cluster = {
        "cluster_key": "c1",
        "title": "Submit report",
        "items": [{"message": {"id": "m1", "provider": "google"}, "evidence_quote": "Please submit by Friday"}],
    }

    await reduce.reduce_node({"clusters": [cluster], "errors": []})

    assert captured_languages == ["vi"]


def test_quote_lines_includes_sender_recipient_header():
    # Bug thật: bản tóm tắt cuối (cái hiển thị UI, do reduce.py viết lại)
    # không có dòng [Từ:]/[Đến:] dù extract_batch.py đã thêm — vì reduce chỉ
    # đọc evidence_quote/detail, không tự đưa lại header vào cho LLM cuối.
    cluster = {
        "items": [
            {
                "message": {
                    "id": "m1",
                    "author_name": "Mentor",
                    "author_id": "mentor@example.com",
                    "to": ["user@example.com"],
                    "cc": [],
                },
                "evidence_quote": "Nộp trước Chủ Nhật",
            }
        ]
    }

    lines = reduce._quote_lines(cluster)

    assert "[Từ: Mentor <mentor@example.com>]" in lines
    assert "[Đến: user@example.com]" in lines


def test_system_prompt_requires_sender_attribution_in_final_summary():
    prompt = reduce._system_prompt("vi")
    assert "[Từ:" in prompt and "[Đến:" in prompt


def test_quote_lines_includes_detail_when_it_differs_from_evidence_quote():
    # detail (viết bởi extract_batch, có thể đã tổng hợp cả attachment_text)
    # trước đây bị reduce bỏ qua hoàn toàn, chỉ dùng evidence_quote — tóm tắt
    # cuối cùng vì vậy không bao giờ nhắc tới nội dung file đính kèm dù model
    # extract_batch đã đọc được.
    cluster = {
        "items": [
            {
                "message": {"id": "m1"},
                "evidence_quote": "Nộp trước Chủ Nhật",
                "detail": "Nộp trước Chủ Nhật — file đính kèm yêu cầu sửa mục MC1, MC2 theo phản hồi review.",
            }
        ]
    }

    lines = reduce._quote_lines(cluster)

    assert "Nộp trước Chủ Nhật" in lines
    assert "MC1, MC2" in lines


def test_quote_lines_skips_duplicate_detail_equal_to_quote():
    cluster = {
        "items": [
            {"message": {"id": "m1"}, "evidence_quote": "Nộp trước Chủ Nhật", "detail": "Nộp trước Chủ Nhật"},
        ]
    }

    lines = reduce._quote_lines(cluster)

    assert lines.count("Nộp trước Chủ Nhật") == 1


@pytest.mark.asyncio
async def test_reduce_one_final_summary_can_draw_from_attachment_derived_detail(monkeypatch):
    captured_user_content: list[str] = []

    class _FakeLLM:
        async def ainvoke(self, messages):
            captured_user_content.append(messages[1]["content"])
            return SimpleNamespace(content="Sửa bài theo MC1, MC2 và nộp trước Chủ Nhật.")

    monkeypatch.setattr(reduce, "get_settings", lambda: SimpleNamespace(mock_llm=False, max_llm_batches_per_run=3))
    monkeypatch.setattr(reduce, "get_llm", lambda: _FakeLLM())
    monkeypatch.setattr(reduce, "ground_candidate", lambda *a, **k: SimpleNamespace(status="grounded"))
    cluster = {
        "cluster_key": "c1",
        "title": "Sửa bài báo",
        "items": [
            {
                "message": {"id": "m1", "provider": "google"},
                "evidence_quote": "Nộp trước Chủ Nhật",
                "detail": "Nộp trước Chủ Nhật — file đính kèm yêu cầu sửa mục MC1, MC2 theo phản hồi review.",
            }
        ],
    }

    result = await reduce.reduce_node({"clusters": [cluster], "errors": []})

    assert "MC1, MC2" in captured_user_content[0]
    assert result["clusters"][0]["detail"] == "Sửa bài theo MC1, MC2 và nộp trước Chủ Nhật."


@pytest.mark.asyncio
async def test_reduce_keeps_summary_that_names_the_sender_and_attachment(monkeypatch):
    """Bản tóm tắt được yêu cầu mở đầu bằng người gửi và tóm luôn nội dung file
    đính kèm, nhưng nguồn chấm grounding từng chỉ là evidence_quote — hai phần
    đó không có token nào đối chiếu nên tóm tắt đúng yêu cầu lại bị đánh trượt
    về nhánh nối quote thô. Nguồn chấm phải khớp nguồn đã đưa vào prompt."""
    monkeypatch.setattr(reduce, "get_settings", lambda: SimpleNamespace(mock_llm=False, max_llm_batches_per_run=2))

    candidate = (
        "Mail đến từ Mentor <mentor@example.com> gửi cho user@example.com. "
        "File đính kèm nêu ba mục cần sửa: phần mở đầu, bảng số liệu và kết luận."
    )

    class FakeLLM:
        async def ainvoke(self, messages):
            return SimpleNamespace(content=candidate)

    monkeypatch.setattr(reduce, "get_llm", lambda: FakeLLM())

    cluster = {
        "cluster_key": "c1",
        "title": "Sửa báo cáo",
        "items": [
            {
                "message": {
                    "id": "m1",
                    "provider": "google",
                    "author_name": "Mentor",
                    "author_id": "mentor@example.com",
                    "to": ["user@example.com"],
                    "attachment_text": "Ba mục cần sửa: phần mở đầu, bảng số liệu và kết luận.",
                },
                "evidence_quote": "Nhờ em sửa lại báo cáo.",
                "detail": "Mentor nhờ sửa báo cáo theo góp ý trong file.",
            }
        ],
    }

    result = await reduce.reduce_node({"clusters": [cluster], "errors": []})

    assert result["clusters"][0]["detail"] == candidate


@pytest.mark.asyncio
async def test_reduce_fallback_still_names_the_sender(monkeypatch):
    """Nhánh fallback (mock/không grounded) vẫn phải giữ attribution — task tạo
    ra từ nhánh này trước đây chỉ còn câu trích, không biết mail từ đâu."""
    monkeypatch.setattr(reduce, "get_settings", lambda: SimpleNamespace(mock_llm=True))
    cluster = {
        "cluster_key": "c1",
        "title": "Sửa báo cáo",
        "items": [
            {
                "message": {
                    "id": "m1",
                    "provider": "google",
                    "author_name": "Mentor",
                    "author_id": "mentor@example.com",
                    "to": ["user@example.com"],
                },
                "evidence_quote": "Nhờ em sửa lại báo cáo.",
            }
        ],
    }

    result = await reduce.reduce_node({"clusters": [cluster], "errors": []})

    detail = result["clusters"][0]["detail"]
    assert "mentor@example.com" in detail
    assert "Nhờ em sửa lại báo cáo." in detail

