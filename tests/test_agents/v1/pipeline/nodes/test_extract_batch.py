from types import SimpleNamespace

import pytest

from src.agents.pipeline.nodes import extract_batch
from src.agents.pipeline.nodes.extract_batch import _quote_is_verbatim
from src.agents.pipeline.schemas import BatchExtraction, ExtractedSignal
from src.models.connection import Connection
from tests.test_agents.v1.pipeline.conftest import gmail_item, jira_item


@pytest.mark.asyncio
async def test_extract_batch_uses_deterministic_mock_and_keeps_source_evidence(pipeline_state, monkeypatch):
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=True, max_total_llm_batches_per_run=20),
    )
    item = gmail_item()
    pipeline_state["batches"] = [[item]]

    result = await extract_batch.extract_batch_node(pipeline_state)

    assert len(result["extracted"]) == 1
    assert result["extracted"][0]["message"]["id"] == "m1"
    assert result["extracted"][0]["evidence_quote"] in item["text"]


@pytest.mark.asyncio
async def test_extract_batch_empty_input_does_not_initialize_llm(pipeline_state, monkeypatch):
    monkeypatch.setattr(extract_batch, "get_settings", lambda: SimpleNamespace(mock_llm=False))
    monkeypatch.setattr(extract_batch, "get_llm", lambda: (_ for _ in ()).throw(AssertionError("LLM called")))

    result = await extract_batch.extract_batch_node(pipeline_state)

    assert result == {"extracted": [], "errors": []}


@pytest.mark.asyncio
async def test_extract_batch_truncates_gracefully_above_total_batch_limit(pipeline_state, monkeypatch):
    # Vượt max_total_llm_batches_per_run KHÔNG được crash cả Run (vd user
    # nghỉ 10 ngày quay lại có 2000 tin) — xử lý đúng số batch cho phép, phần
    # dư bỏ qua kèm cảnh báo trong errors, Run vẫn thành công với dữ liệu đã xử lý.
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=True, max_total_llm_batches_per_run=1),
    )
    pipeline_state["batches"] = [[gmail_item("m1")], [gmail_item("m2")]]

    result = await extract_batch.extract_batch_node(pipeline_state)

    extracted_ids = {signal["message"]["id"] for signal in result["extracted"]}
    assert extracted_ids == {"m1"}
    assert len(result["errors"]) == 1
    assert "1 batch" in result["errors"][0]
    assert "bỏ qua 1 batch" in result["errors"][0]


def _insert_jira_connection(pipeline_state, *, provider_user_id="acc-phong-01") -> int:
    import uuid

    db = pipeline_state["db"]
    # user_id ngẫu nhiên mỗi lần gọi — pipeline_session_factory dùng chung 1
    # SQLite in-memory xuyên suốt session test, (user_id, provider) unique.
    connection = Connection(
        user_id=f"u-test-{uuid.uuid4().hex[:8]}", provider="jira", provider_user_id=provider_user_id
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection.id


@pytest.mark.asyncio
async def test_extract_batch_jira_is_rule_based_and_never_calls_llm(pipeline_state, monkeypatch):
    monkeypatch.setattr(extract_batch, "get_settings", lambda: SimpleNamespace(mock_llm=False))
    monkeypatch.setattr(extract_batch, "get_llm", lambda: (_ for _ in ()).throw(AssertionError("LLM called")))
    connection_id = _insert_jira_connection(pipeline_state)
    pipeline_state["batches"] = [[jira_item(connection_id=connection_id)]]

    result = await extract_batch.extract_batch_node(pipeline_state)

    assert len(result["extracted"]) == 1
    signal = result["extracted"][0]
    assert signal["title"] == "Hoàn thành báo cáo tuần 3"
    assert signal["decision"] == "KEEP"
    assert signal["rule_version"] == "jira-rules-v1"
    assert signal["structured_due_at"].date().isoformat() == "2026-08-15"
    assert signal["structured_assignee"] == "acc-phong-01"
    assert "ASSIGNED_TO_CURRENT_USER" in signal["reasons"]


@pytest.mark.asyncio
async def test_extract_batch_jira_drop_excludes_issue_from_extracted(pipeline_state, monkeypatch):
    monkeypatch.setattr(extract_batch, "get_settings", lambda: SimpleNamespace(mock_llm=False))
    monkeypatch.setattr(extract_batch, "get_llm", lambda: (_ for _ in ()).throw(AssertionError("LLM called")))
    connection_id = _insert_jira_connection(pipeline_state)
    done_issue = jira_item(connection_id=connection_id, status_category="Done", text="Đã xong, không cần làm gì thêm.")
    pipeline_state["batches"] = [[done_issue]]

    result = await extract_batch.extract_batch_node(pipeline_state)

    assert result["extracted"] == []


@pytest.mark.asyncio
async def test_extract_batch_mixed_jira_and_gmail_only_calls_llm_for_gmail(pipeline_state, monkeypatch):
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=True, max_total_llm_batches_per_run=20),
    )
    connection_id = _insert_jira_connection(pipeline_state)
    pipeline_state["batches"] = [[jira_item(connection_id=connection_id), gmail_item("m1")]]

    result = await extract_batch.extract_batch_node(pipeline_state)

    titles = {signal["message"]["id"] for signal in result["extracted"]}
    assert titles == {"TO04-42", "m1"}
    jira_signal = next(s for s in result["extracted"] if s["message"]["id"] == "TO04-42")
    assert jira_signal["decision"] == "KEEP"


def test_format_batch_includes_attachment_text_when_present():
    item = gmail_item("m1", text="Xem file đính kèm.")
    item["attachment_text"] = "[Đính kèm: bao-cao.pdf]\nNội dung file trích được."

    formatted = extract_batch._format_batch([item])

    assert "[Đính kèm: bao-cao.pdf]" in formatted
    assert "Nội dung file trích được." in formatted


def test_format_batch_includes_sender_and_recipient_header():
    # LLM trước đây không biết ai gửi/ai nhận -> summary không claim được
    # nguồn, cũng không tự lọc được mail nhắc việc của người khác.
    item = gmail_item("m1")

    formatted = extract_batch._format_batch([item])

    assert "[Từ: Mentor <mentor@example.com>]" in formatted
    assert "[Đến: user@example.com]" in formatted


def test_system_prompt_requires_sender_recipient_attribution_in_summary():
    prompt = extract_batch._system_prompt("vi")
    assert "[Từ:" in prompt and "[Đến:" in prompt
    assert "không phải người nhận" in prompt


class _FakeStructuredLLM:
    def __init__(self, result: BatchExtraction) -> None:
        self._result = result

    async def ainvoke(self, messages):
        return self._result


class _FakeLLM:
    def __init__(self, result: BatchExtraction) -> None:
        self._result = result

    def with_structured_output(self, schema):
        return _FakeStructuredLLM(self._result)


@pytest.mark.asyncio
async def test_extract_batch_accepts_evidence_quote_sourced_from_attachment_text(pipeline_state, monkeypatch):
    # Trước fix: quote chỉ được chấp nhận nếu nằm trong message["text"] —
    # attachment_extract_node đưa nội dung file vào attachment_text (KHÔNG
    # ghi đè text), nên quote trích từ file sẽ luôn bị loại nếu không mở
    # rộng điều kiện containment-check.
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=False, max_total_llm_batches_per_run=20, max_llm_batches_per_run=3),
    )
    item = gmail_item("m1", text="Xem file đính kèm để biết chi tiết.")
    item["attachment_text"] = "[Đính kèm: bao-cao.pdf]\nNộp báo cáo trước 17h thứ Sáu."
    fake_result = BatchExtraction(
        items=[
            ExtractedSignal(
                message_id="m1",
                title="Nộp báo cáo",
                evidence_quote="Nộp báo cáo trước 17h thứ Sáu.",
                confidence=0.9,
            )
        ]
    )
    monkeypatch.setattr(extract_batch, "get_llm", lambda: _FakeLLM(fake_result))
    pipeline_state["batches"] = [[item]]

    result = await extract_batch.extract_batch_node(pipeline_state)

    assert len(result["extracted"]) == 1
    assert result["extracted"][0]["evidence_quote"] == "Nộp báo cáo trước 17h thứ Sáu."


@pytest.mark.asyncio
async def test_extract_batch_still_rejects_quote_found_in_neither_text_nor_attachment(pipeline_state, monkeypatch):
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=False, max_total_llm_batches_per_run=20, max_llm_batches_per_run=3),
    )
    item = gmail_item("m1", text="Xem file đính kèm để biết chi tiết.")
    item["attachment_text"] = "[Đính kèm: bao-cao.pdf]\nNộp báo cáo trước 17h thứ Sáu."
    fake_result = BatchExtraction(
        items=[
            ExtractedSignal(
                message_id="m1",
                title="Bịa chuyện",
                evidence_quote="Câu này không có trong mail lẫn file đính kèm.",
                confidence=0.9,
            )
        ]
    )
    monkeypatch.setattr(extract_batch, "get_llm", lambda: _FakeLLM(fake_result))
    pipeline_state["batches"] = [[item]]

    result = await extract_batch.extract_batch_node(pipeline_state)

    assert result["extracted"] == []


def test_system_prompt_instructs_target_language_but_never_translate_quote():
    vi_prompt = extract_batch._system_prompt("vi")
    en_prompt = extract_batch._system_prompt("en")

    assert "tiếng Việt" in vi_prompt
    assert "English" in en_prompt
    # Cả 2 ngôn ngữ đều phải cấm dịch evidence_quote/time_expression — đây là
    # ràng buộc bắt buộc, không phụ thuộc ngôn ngữ target.
    assert "evidence_quote" in vi_prompt and "không dịch" in vi_prompt
    assert "evidence_quote" in en_prompt and "không dịch" in en_prompt


@pytest.mark.asyncio
async def test_extract_batch_node_passes_run_language_into_system_prompt(pipeline_state, monkeypatch):
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=False, max_total_llm_batches_per_run=20, max_llm_batches_per_run=3),
    )
    captured_languages: list[str] = []
    original_system_prompt = extract_batch._system_prompt

    def spy_system_prompt(language: str) -> str:
        captured_languages.append(language)
        return original_system_prompt(language)

    monkeypatch.setattr(extract_batch, "_system_prompt", spy_system_prompt)

    item = gmail_item("m1", text="Please submit the report by Friday.")
    fake_result = BatchExtraction(
        items=[
            ExtractedSignal(
                message_id="m1",
                title="Submit report",
                evidence_quote="Please submit the report by Friday.",
                confidence=0.9,
            )
        ]
    )
    monkeypatch.setattr(extract_batch, "get_llm", lambda: _FakeLLM(fake_result))
    pipeline_state["batches"] = [[item]]
    pipeline_state["language"] = "en"

    await extract_batch.extract_batch_node(pipeline_state)

    assert captured_languages == ["en"]


@pytest.mark.asyncio
async def test_extract_batch_node_defaults_to_vi_when_state_has_no_language(pipeline_state, monkeypatch):
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=False, max_total_llm_batches_per_run=20, max_llm_batches_per_run=3),
    )
    captured_languages: list[str] = []
    original_system_prompt = extract_batch._system_prompt

    def spy_system_prompt(language: str) -> str:
        captured_languages.append(language)
        return original_system_prompt(language)

    monkeypatch.setattr(extract_batch, "_system_prompt", spy_system_prompt)

    item = gmail_item("m1", text="Please submit the report by Friday.")
    fake_result = BatchExtraction(
        items=[
            ExtractedSignal(
                message_id="m1",
                title="Submit report",
                evidence_quote="Please submit the report by Friday.",
                confidence=0.9,
            )
        ]
    )
    monkeypatch.setattr(extract_batch, "get_llm", lambda: _FakeLLM(fake_result))
    pipeline_state["batches"] = [[item]]
    assert "language" not in pipeline_state

    await extract_batch.extract_batch_node(pipeline_state)

    assert captured_languages == ["vi"]


@pytest.mark.asyncio
async def test_safety_net_creates_task_when_llm_misses_deadline_and_action_signal(pipeline_state, monkeypatch):
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=False, max_total_llm_batches_per_run=20, max_llm_batches_per_run=3),
    )
    item = gmail_item(
        "m1",
        text="Nộp báo cáo trước thứ Sáu nhé.",
        subject="Việc cần làm",
        classification_reasons=["deadline_signal", "action_signal"],
    )
    fake_result = BatchExtraction(items=[])  # LLM bỏ sót — 0 tín hiệu
    monkeypatch.setattr(extract_batch, "get_llm", lambda: _FakeLLM(fake_result))
    pipeline_state["batches"] = [[item]]
    pipeline_state["language"] = "vi"

    result = await extract_batch.extract_batch_node(pipeline_state)

    assert len(result["extracted"]) == 1
    signal = result["extracted"][0]
    assert signal["message"]["id"] == "m1"
    assert signal["certainty"] == "uncertain"
    assert signal["confidence"] == 0.3
    assert "Việc cần làm" in signal["title"]
    assert signal["evidence_quote"] in item["text"]


@pytest.mark.asyncio
async def test_safety_net_does_not_duplicate_when_llm_already_caught_it(pipeline_state, monkeypatch):
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=False, max_total_llm_batches_per_run=20, max_llm_batches_per_run=3),
    )
    item = gmail_item(
        "m1",
        text="Nộp báo cáo trước thứ Sáu nhé.",
        classification_reasons=["deadline_signal", "action_signal"],
    )
    fake_result = BatchExtraction(
        items=[
            ExtractedSignal(
                message_id="m1",
                title="Nộp báo cáo",
                evidence_quote="Nộp báo cáo trước thứ Sáu nhé.",
                confidence=0.9,
            )
        ]
    )
    monkeypatch.setattr(extract_batch, "get_llm", lambda: _FakeLLM(fake_result))
    pipeline_state["batches"] = [[item]]

    result = await extract_batch.extract_batch_node(pipeline_state)

    assert len(result["extracted"]) == 1
    assert result["extracted"][0]["confidence"] == 0.9


@pytest.mark.asyncio
async def test_safety_net_skips_items_without_both_signals(pipeline_state, monkeypatch):
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=False, max_total_llm_batches_per_run=20, max_llm_batches_per_run=3),
    )
    item = gmail_item(
        "m1",
        text="Chỉ có deadline, không có action rõ ràng.",
        classification_reasons=["deadline_signal"],
    )
    fake_result = BatchExtraction(items=[])
    monkeypatch.setattr(extract_batch, "get_llm", lambda: _FakeLLM(fake_result))
    pipeline_state["batches"] = [[item]]

    result = await extract_batch.extract_batch_node(pipeline_state)

    assert result["extracted"] == []


@pytest.mark.asyncio
async def test_safety_net_skips_items_flagged_automated_noise(pipeline_state, monkeypatch):
    # Mail tự động (vd ngân hàng) hay khớp deadline_signal/action_signal do
    # regex lỏng ("vui long", ngày dd/mm) dù filter_classify đã tự chấm
    # automated_penalty < 0 cho nó. Lưới an toàn không được tự ý override —
    # nếu LLM đã đọc kỹ và quyết định 0 tín hiệu, tin theo LLM.
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=False, max_total_llm_batches_per_run=20, max_llm_batches_per_run=3),
    )
    item = gmail_item(
        "m1",
        text="Giao dịch thành công lúc 19/08. Vui lòng không trả lời email này.",
        classification_reasons=["deadline_signal", "action_signal"],
    )
    item["component_scores"] = {"automated_penalty": -30, "newsletter_penalty": 0}
    fake_result = BatchExtraction(items=[])  # LLM đúng: không phải task thật
    monkeypatch.setattr(extract_batch, "get_llm", lambda: _FakeLLM(fake_result))
    pipeline_state["batches"] = [[item]]

    result = await extract_batch.extract_batch_node(pipeline_state)

    assert result["extracted"] == []


@pytest.mark.asyncio
async def test_safety_net_signal_includes_sender_recipient_attribution(pipeline_state, monkeypatch):
    # Lưới an toàn không qua LLM (không có bước [Từ:]/[Đến:] của
    # _format_batch) — bug thật: task tạo từ lưới an toàn không nêu người
    # gửi/nhận, giống hệt lỗi extract_batch LLM đã vá nhưng an toàn net thì
    # chưa.
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=False, max_total_llm_batches_per_run=20, max_llm_batches_per_run=3),
    )
    item = gmail_item(
        "m1",
        text="Nộp báo cáo trước thứ Sáu nhé.",
        subject="Việc cần làm",
        classification_reasons=["deadline_signal", "action_signal"],
    )
    fake_result = BatchExtraction(items=[])
    monkeypatch.setattr(extract_batch, "get_llm", lambda: _FakeLLM(fake_result))
    pipeline_state["batches"] = [[item]]

    result = await extract_batch.extract_batch_node(pipeline_state)

    assert len(result["extracted"]) == 1
    detail = result["extracted"][0]["detail"]
    assert "[Từ: Mentor <mentor@example.com>]" in detail
    assert "[Đến: user@example.com]" in detail


@pytest.mark.asyncio
async def test_safety_net_signal_includes_attachment_text_in_detail(pipeline_state, monkeypatch):
    # Bug thật đã xảy ra: lưới an toàn chỉ lấy evidence_text/text (thân mail),
    # quên hẳn attachment_text dù attachment_extract_node đã đọc thành công —
    # task tạo ra từ lưới an toàn luôn chung chung dù mail có file đính kèm.
    monkeypatch.setattr(
        extract_batch,
        "get_settings",
        lambda: SimpleNamespace(mock_llm=False, max_total_llm_batches_per_run=20, max_llm_batches_per_run=3),
    )
    item = gmail_item(
        "m1",
        text="Nộp báo cáo trước thứ Sáu nhé.",
        subject="Việc cần làm",
        classification_reasons=["deadline_signal", "action_signal"],
    )
    item["attachment_text"] = "[Đính kèm: review.docx]\nMC1 - Lỗi trích dẫn nghiêm trọng ở Bảng 17a."
    fake_result = BatchExtraction(items=[])  # LLM bỏ sót
    monkeypatch.setattr(extract_batch, "get_llm", lambda: _FakeLLM(fake_result))
    pipeline_state["batches"] = [[item]]

    result = await extract_batch.extract_batch_node(pipeline_state)

    assert len(result["extracted"]) == 1
    signal = result["extracted"][0]
    assert "MC1" in signal["detail"]
    # evidence_quote vẫn chỉ trích thân mail — an toàn cho phần "Truy cập nguồn".
    assert signal["evidence_quote"] in item["text"]

def test_quote_check_matches_the_text_the_model_actually_read():
    """`_format_batch` đưa vào prompt bản đã sanitize (NFKC + gộp khoảng
    trắng). So thẳng với message["text"] gốc là so hai chuỗi khác nhau: dấu câu
    toàn rộng bị đổi ("？" -> "?"), xuống dòng bị gộp. Tiếng Việt/Anh chỉ trượt
    khi trích vắt qua dòng, tiếng Nhật thì trượt gần như mọi lần — mail giao
    việc tiếng Nhật bị bỏ im lặng, không lỗi, không log."""
    message = {"text": "ドラフトファイルを確認してもらえますか？\n特に以下の点をチェックしてください。"}

    # Model trích lại từ bản đã sanitize: dấu ? nửa rộng, xuống dòng thành cách.
    assert _quote_is_verbatim("ドラフトファイルを確認してもらえますか?", message)
    # Trích đúng nguyên bản gốc cũng phải hợp lệ.
    assert _quote_is_verbatim("ドラフトファイルを確認してもらえますか？", message)
    # Trích vắt qua xuống dòng — vốn trượt với cả tiếng Việt/Anh.
    assert _quote_is_verbatim("してもらえますか? 特に以下の点を", message)
    # Bịa thì vẫn phải trượt.
    assert not _quote_is_verbatim("まったく関係のない文章です", message)


def test_quote_check_still_accepts_attachment_text_as_a_source():
    message = {
        "text": "Xem file đính kèm.",
        "attachment_text": "[Trang 1]\nNộp báo cáo trước thứ Sáu.",
    }
    assert _quote_is_verbatim("Nộp báo cáo trước thứ Sáu.", message)

def test_jira_detail_carries_source_line_and_attachment_content():
    """Đường Jira KHÔNG qua LLM (_extract_jira_batch + _mock_reduce), nên dòng
    nguồn và nội dung file phải tự ghép vào detail — không có bước nào phía sau
    làm hộ. Chuỗi này là thứ người dùng đọc gần như nguyên vẹn."""
    from types import SimpleNamespace

    from src.agents.pipeline.nodes.extract_batch import _jira_detail

    item = {
        "provider": "jira",
        "author_name": "HoàiAn Thái",
        "author_id": "acc-hoaian",
        "jira_assignee_name": "Yến Nhi",
        "jira_status": "In Progress",
        "attachment_text": "[Đính kèm: review.pdf]\nSửa bảng 17a trước thứ Sáu.",
    }
    issue = SimpleNamespace(description="Cần rà soát lại phần số liệu.")

    detail = _jira_detail(item, issue, evidence="Cần rà soát")

    assert "[Người báo: HoàiAn Thái]" in detail
    assert "[Giao cho: Yến Nhi]" in detail
    assert "Cần rà soát lại phần số liệu." in detail
    assert "Sửa bảng 17a trước thứ Sáu." in detail


def test_jira_detail_without_attachment_is_just_source_and_body():
    from types import SimpleNamespace

    from src.agents.pipeline.nodes.extract_batch import _jira_detail

    item = {"provider": "jira", "author_name": "An", "author_id": "acc-an"}
    issue = SimpleNamespace(description="Mô tả việc.")

    detail = _jira_detail(item, issue, evidence="Mô tả")

    assert detail.startswith("[Người báo: An]")
    assert detail.endswith("Mô tả việc.")
